#!/usr/bin/env python3
"""Audit the AlloyHardnessOptimization hash-order stabilization.

The historical calibration and three GPT-5.5 trajectories were produced before
composition keys were sorted prior to floating-point reduction.  This audit
binds that exact source change, compares the complete finite alloy landscape
under several hash seeds, reruns a clean calibration, and replays every retained
selected/terminal candidate against the stabilized evaluator.  Intermediate
proposal source was not retained and is reported as an explicit evidence gap.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402
from frontier_science.runtime_migration import (  # noqa: E402
    RUNTIME_PATHS,
    runtime_migration_status,
    runtime_source_changes,
)


TASK_ID = "MaterialsScience/AlloyHardnessOptimization"
TASK = ROOT / "benchmarks/Chemistry/AlloyHardnessOptimization"
DATA = TASK / "verification/alloy_hardness_v1.json"
INPUT_SOURCE_REVISION = "52dcec0c1a4df2d7f92cdef1d6d2bafa2e81f18e"
HASH_SEEDS = ("0", "1", "2", "17", "123456")
MAX_EXPECTED_ROUNDOFF = 2.0e-16
ALLOWED_RUNTIME_CHANGES = (
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py",
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/evaluator.py",
)
TASK_RUNTIME_SCOPE = (
    "frontier_science/evaluate.py",
    "frontier_science/trusted_driver.py",
    "frontier_science/secure_eval.py",
    "frontier_science/candidate_worker.py",
    "frontier_science/rpc_codec.py",
    "frontier_science/spec.py",
    "frontier_science/registry.py",
    "benchmarks/MaterialsScience/AlloyHardnessOptimization",
    "requirements-upstream.txt",
)
SOURCE_HASH_CONTRACT = {
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/solution.py": {
        "old": "fab66bd9e0f98ca7457cac075b102544355f7d4d4d4008185e942a4d3139117e",
        "new": "9079971176c51f75a0363e59286f29d0f42bf3b78310c8bc65a515b376165bc5",
    },
    "benchmarks/MaterialsScience/AlloyHardnessOptimization/verification/evaluator.py": {
        "old": "bbe175f8ac7b5914fcb815b7ad19030a3efb4bd738fb5e3055108cc4fcf00b6e",
        "new": "6a2ac322d7cb67818ad4fabca24bfc9a21dc0ddb05c3037c91e9f9fab70537ae",
    },
    "scripts/calibrate_alloy_hardness_optimization.py": {
        "old": "f4ca504251fd26044c5ffcb24848acecc7356e579b4c7ffdc98bf240b5fbb8b9",
        "new": "97a2e47b048ad3d9ac28576dafe74329485b2bf5a25ded4dee135b30aa8b8ef4",
    },
}
DATA_SHA256 = "a55effd2a4077b63a19a45a91729698e07b1bd9e89a72da79b87f2528a09d003"
CALIBRATION = "experiments/alloy_hardness_v1_calibration_2026-07-26.json"
CALIBRATION_SHA256 = "4698c739038ab32d6258096d21f26d1ddb2501f8f4b4ff3c121c77ad2c8943c7"
MODEL_REPORTS = {
    "budget_one": {
        "path": "experiments/gpt55_alloy_hardness_v1_b1_2026-07-26.json",
        "sha256": "01cca0c342aec5027e05d56d5b162abe66382f8b3c8f4869a5d9e2632db7d750",
    },
    "normal_budget_three": {
        "path": "experiments/gpt55_alloy_hardness_v1_b3_2026-07-26.json",
        "sha256": "54faaf56551f1e1a2c18f13fc7f5051342cbb984df22b43e3caf0b340f665ff6",
    },
    "blind_budget_three": {
        "path": "experiments/gpt55_alloy_hardness_v1_blind_b3_2026-07-26.json",
        "sha256": "96ebf5a214041f53de8edb974f08b61cd5e4f0dd194cedaf03c36ea7a2584209",
    },
}


LANDSCAPE_PROGRAM = r"""
import importlib.util
import itertools
import json
import sys

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("alloy_migration_oracle", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = {"pairs": {}, "utilities": {}, "best_rows": {}}
for world in module.WORLDS:
    world_id = world["id"]
    pairs = {}
    for left, right in itertools.combinations(world["candidates"], 2):
        key = left["id"] + "|" + right["id"]
        pairs[key] = module._composition_distance(left, right)
    result["pairs"][world_id] = pairs
    utilities = {}
    best_rows = {}
    for field in ("proxy_hardness_hv", "study_hardness_hv"):
        ranked = []
        for rows in itertools.combinations(world["candidates"], 3):
            row_key = "|".join(row["id"] for row in rows)
            value = module._batch_utility(world, rows, field)
            utilities[field + "|" + row_key] = value
            ranked.append((value, row_key))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        best_rows[field] = ranked[0][1]
    result["utilities"][world_id] = utilities
    result["best_rows"][world_id] = best_rows
result["baseline_metrics"] = module.evaluate(module._baseline_policy)
result["reference_metrics"] = module.evaluate(module._reference_policy)
print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
"""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _git_show(revision: str, relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", revision + ":" + relative], cwd=str(ROOT),
    )


def _current_path(relative: str) -> Path:
    prefix = "benchmarks/MaterialsScience/AlloyHardnessOptimization"
    if relative == prefix or relative.startswith(prefix + "/"):
        return TASK / Path(relative).relative_to(prefix)
    return ROOT / relative


def _normalized_current_source(relative: str) -> bytes:
    payload = _current_path(relative).read_bytes()
    if relative == "scripts/calibrate_alloy_hardness_optimization.py":
        payload = payload.replace(
            b'benchmarks/Chemistry/AlloyHardnessOptimization',
            b'benchmarks/MaterialsScience/AlloyHardnessOptimization',
        )
    return payload


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metric_differences(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    """Return stable leaf differences between two JSON-compatible values."""

    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(set(left) | set(right)):
            result.extend(_metric_differences(
                left.get(key), right.get(key), path + "/" + str(key),
            ))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        if len(left) != len(right):
            result.append({
                "path": path + "/length", "old": len(left), "new": len(right),
                "absolute_difference": None,
            })
        for index, (old, new) in enumerate(zip(left, right)):
            result.extend(_metric_differences(
                old, new, path + "/" + str(index),
            ))
        return result
    if left == right:
        return []
    difference = None
    if (
        isinstance(left, (int, float)) and not isinstance(left, bool)
        and isinstance(right, (int, float)) and not isinstance(right, bool)
        and math.isfinite(float(left)) and math.isfinite(float(right))
    ):
        difference = abs(float(left) - float(right))
    return [{
        "path": path or "/", "old": left, "new": right,
        "absolute_difference": difference,
    }]


def _run_landscape(evaluator: Path, seed: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = seed
    rendered = subprocess.check_output(
        [sys.executable, "-c", LANDSCAPE_PROGRAM, str(evaluator)],
        cwd=str(ROOT), env=environment, text=True,
    ).strip()
    return json.loads(rendered)


def _numeric_map_delta(
    left: dict[str, dict[str, float]], right: dict[str, dict[str, float]],
) -> tuple[int, int, float]:
    left_keys = {(world, key) for world, rows in left.items() for key in rows}
    right_keys = {(world, key) for world, rows in right.items() for key in rows}
    if left_keys != right_keys:
        raise ValueError("alloy landscape key space changed")
    deltas = [
        abs(float(left[world][key]) - float(right[world][key]))
        for world, key in sorted(left_keys)
    ]
    return len(deltas), sum(delta != 0.0 for delta in deltas), max(deltas, default=0.0)


def audit_landscape() -> dict[str, Any]:
    """Compare every finite pair and three-alloy utility under five seeds."""

    relative = ALLOWED_RUNTIME_CHANGES[1]
    with tempfile.TemporaryDirectory(prefix="alloy_hash_order_landscape_") as tmp:
        temporary = Path(tmp)
        old_dir = temporary / "old"
        new_dir = temporary / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        for directory in (old_dir, new_dir):
            (directory / "alloy_hardness_v1.json").write_bytes(DATA.read_bytes())
        old_evaluator = old_dir / "evaluator.py"
        new_evaluator = new_dir / "evaluator.py"
        old_evaluator.write_bytes(_git_show(INPUT_SOURCE_REVISION, relative))
        new_evaluator.write_bytes(_current_path(relative).read_bytes())
        old = {seed: _run_landscape(old_evaluator, seed) for seed in HASH_SEEDS}
        new = {seed: _run_landscape(new_evaluator, seed) for seed in HASH_SEEDS}

    records = []
    for seed in HASH_SEEDS:
        pair_total, pair_changed, pair_max = _numeric_map_delta(
            old[seed]["pairs"], new[seed]["pairs"],
        )
        utility_total, utility_changed, utility_max = _numeric_map_delta(
            old[seed]["utilities"], new[seed]["utilities"],
        )
        records.append({
            "python_hash_seed": seed,
            "old_landscape_sha256": _canonical_sha256(old[seed]),
            "new_landscape_sha256": _canonical_sha256(new[seed]),
            "pair_count": pair_total,
            "changed_pair_count": pair_changed,
            "maximum_pair_distance_absolute_difference": pair_max,
            "three_alloy_utility_count": utility_total,
            "changed_three_alloy_utility_count": utility_changed,
            "maximum_three_alloy_utility_absolute_difference": utility_max,
            "proxy_and_truth_optimal_rows_exactly_match": (
                old[seed]["best_rows"] == new[seed]["best_rows"]
            ),
            "baseline_metrics_exactly_match": (
                old[seed]["baseline_metrics"] == new[seed]["baseline_metrics"]
            ),
            "reference_metrics_exactly_match": (
                old[seed]["reference_metrics"] == new[seed]["reference_metrics"]
            ),
        })
    old_hashes = {record["old_landscape_sha256"] for record in records}
    new_hashes = {record["new_landscape_sha256"] for record in records}
    result = {
        "hash_seeds": list(HASH_SEEDS),
        "world_count": len(new[HASH_SEEDS[0]]["pairs"]),
        "pair_count_per_seed": records[0]["pair_count"],
        "three_alloy_utility_count_per_seed": records[0][
            "three_alloy_utility_count"
        ],
        "old_unique_landscape_sha256_count": len(old_hashes),
        "new_unique_landscape_sha256_count": len(new_hashes),
        "old_cross_seed_bit_exact": len(old_hashes) == 1,
        "new_cross_seed_bit_exact": len(new_hashes) == 1,
        "records": records,
    }
    result["passed"] = bool(
        result["world_count"] == 13
        and result["pair_count_per_seed"] == 137
        and result["three_alloy_utility_count_per_seed"] == 318
        and not result["old_cross_seed_bit_exact"]
        and result["new_cross_seed_bit_exact"]
        and all(
            record["maximum_pair_distance_absolute_difference"]
            <= MAX_EXPECTED_ROUNDOFF
            and record["maximum_three_alloy_utility_absolute_difference"]
            <= MAX_EXPECTED_ROUNDOFF
            and record["proxy_and_truth_optimal_rows_exactly_match"]
            and record["baseline_metrics_exactly_match"]
            and record["reference_metrics_exactly_match"]
            for record in records
        )
    )
    return result


def _read_trajectory(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _retained_manifest() -> dict[str, Any]:
    """Bind reports, raw trajectories, and the source artifacts that still exist."""

    expected_metrics: dict[str, dict[str, Any]] = {}
    proposals: set[str] = set()
    artifacts = []
    report_records = []
    for label, contract in MODEL_REPORTS.items():
        report_path = ROOT / contract["path"]
        document = json.loads(report_path.read_text(encoding="utf-8"))
        if _sha256(report_path) != contract["sha256"]:
            raise ValueError("alloy model report hash changed: %s" % label)
        provenance = document.get("source_provenance") or {}
        runs = document.get("runs") or []
        if not (
            document.get("execution_passed") is True
            and document.get("trusted_evidence") is True
            and provenance.get("git_revision") == INPUT_SOURCE_REVISION
            and len(runs) == 1
        ):
            raise ValueError("alloy model report provenance changed: %s" % label)
        run = runs[0]
        workdir = Path(run["workdir"]).resolve()
        try:
            relative_workdir = workdir.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError("alloy workdir is outside repository") from exc
        events = _read_trajectory(workdir / "trajectory.jsonl")
        for event in events:
            source_hash = event["candidate_sha256"]
            metrics = event.get("metrics") or {}
            prior = expected_metrics.setdefault(source_hash, metrics)
            if prior != metrics:
                raise ValueError("one candidate hash has inconsistent trajectory metrics")
        proposals.update(event["candidate_sha256"] for event in events[1:])
        for artifact_name, filename in (
            ("selected_best", "best_program.py"), ("terminal", "solution.py"),
        ):
            path = workdir / filename
            source_hash = _sha256(path)
            matching_steps = [
                int(event["step"]) for event in events
                if event["candidate_sha256"] == source_hash
            ]
            if len(matching_steps) != 1:
                raise ValueError("retained alloy source does not bind one trajectory event")
            artifacts.append({
                "condition": label,
                "artifact": artifact_name,
                "path": str(relative_workdir / filename),
                "source_sha256": source_hash,
                "trajectory_step": matching_steps[0],
            })
        report_records.append({
            "condition": label,
            "path": contract["path"],
            "report_sha256": contract["sha256"],
            "source_revision": provenance["git_revision"],
            "trajectory_event_count": len(events),
        })
    retained = {record["source_sha256"] for record in artifacts}
    return {
        "reports": report_records,
        "artifacts": artifacts,
        "expected_metrics": expected_metrics,
        "proposal_hashes": sorted(proposals),
        "retained_proposal_hashes": sorted(proposals & retained),
        "unretained_proposal_hashes": sorted(proposals - retained),
    }


def audit_retained_artifacts() -> dict[str, Any]:
    manifest = _retained_manifest()
    spec = find_task(TASK_ID, include_uncertified=True)
    by_hash: dict[str, dict[str, Any]] = {}
    for record in manifest["artifacts"]:
        source_hash = record["source_sha256"]
        if source_hash not in by_hash:
            metrics = evaluate_candidate(spec, ROOT / record["path"], timeout_s=90)
            expected = manifest["expected_metrics"][source_hash]
            by_hash[source_hash] = {
                "source_sha256": source_hash,
                "bound_metrics_sha256": _canonical_sha256(expected),
                "stabilized_metrics_sha256": _canonical_sha256(metrics),
                "metrics_exactly_match_bound_trajectory": metrics == expected,
                "valid": metrics.get("valid"),
                "combined_score": metrics.get("combined_score"),
                "heldout_policy_score": metrics.get("heldout_policy_score"),
            }
        record.update(by_hash[source_hash])

    old_solution = _git_show(INPUT_SOURCE_REVISION, ALLOWED_RUNTIME_CHANGES[0])
    with tempfile.TemporaryDirectory(prefix="alloy_old_baseline_") as tmp:
        old_path = Path(tmp) / "solution.py"
        old_path.write_bytes(old_solution)
        old_baseline = evaluate_candidate(spec, old_path, timeout_s=90)
    new_baseline = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
    frozen_calibration = json.loads((ROOT / CALIBRATION).read_text(encoding="utf-8"))
    expected_baseline = frozen_calibration["secure_baseline_metrics"]
    baseline = {
        "old_source_sha256": _sha256_bytes(old_solution),
        "new_source_sha256": _sha256(spec.initial_program_path),
        "frozen_metrics_sha256": _canonical_sha256(expected_baseline),
        "old_source_on_stabilized_evaluator_metrics_sha256": _canonical_sha256(
            old_baseline
        ),
        "new_source_on_stabilized_evaluator_metrics_sha256": _canonical_sha256(
            new_baseline
        ),
        "old_source_exactly_matches_frozen_metrics": old_baseline == expected_baseline,
        "new_source_exactly_matches_frozen_metrics": new_baseline == expected_baseline,
        "old_and_new_source_metrics_exactly_match": old_baseline == new_baseline,
    }
    result = {
        "input_reports": manifest["reports"],
        "artifact_instances": manifest["artifacts"],
        "artifact_instance_count": len(manifest["artifacts"]),
        "unique_retained_source_count": len(by_hash),
        "proposal_record_count": 7,
        "unique_proposal_count": len(manifest["proposal_hashes"]),
        "retained_unique_proposal_count": len(
            manifest["retained_proposal_hashes"]
        ),
        "unretained_unique_proposal_count": len(
            manifest["unretained_proposal_hashes"]
        ),
        "unretained_proposal_sha256": manifest["unretained_proposal_hashes"],
        "baseline_replay": baseline,
        "evidence_limit": (
            "Only selected-best and terminal source artifacts were retained. "
            "Three unique intermediate proposals remain trajectory-hash-bound but "
            "cannot be source-replayed under the stabilized evaluator."
        ),
    }
    result["passed"] = bool(
        result["artifact_instance_count"] == 6
        and result["unique_retained_source_count"] == 4
        and result["unique_proposal_count"] == 7
        and result["retained_unique_proposal_count"] == 4
        and result["unretained_unique_proposal_count"] == 3
        and all(
            record["metrics_exactly_match_bound_trajectory"]
            for record in result["artifact_instances"]
        )
        and all(
            baseline[key] for key in (
                "old_source_exactly_matches_frozen_metrics",
                "new_source_exactly_matches_frozen_metrics",
                "old_and_new_source_metrics_exactly_match",
            )
        )
    )
    return result


def audit_calibration(csv_path: Path) -> dict[str, Any]:
    frozen_path = ROOT / CALIBRATION
    if _sha256(frozen_path) != CALIBRATION_SHA256:
        raise ValueError("frozen alloy calibration hash changed")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    module = _load(
        ROOT / "scripts/calibrate_alloy_hardness_optimization.py",
        "alloy_hash_order_migration_calibration",
    )
    current = module.calibrate(csv_path)
    exact_sections = (
        "data_rebuild", "counts", "anchors", "baseline_metrics",
        "reference_metrics", "secure_baseline_metrics",
        "search_visible_metric_keys", "checks",
    )
    section_matches = {
        key: frozen.get(key) == current.get(key) for key in exact_sections
    }
    frozen_truth = dict(frozen["truth_blind_assay_metrics"])
    current_truth = dict(current["truth_blind_assay_metrics"])
    frozen_per_world = frozen_truth.pop("per_world")
    current_per_world = current_truth.pop("per_world")
    truth_differences = _metric_differences(frozen_per_world, current_per_world)
    result = {
        "frozen_report": CALIBRATION,
        "frozen_report_sha256": CALIBRATION_SHA256,
        "current_calibration_source_revision": current.get(
            "source_provenance", {}
        ).get("git_revision"),
        "current_calibration_source_clean": current.get(
            "source_provenance", {}
        ).get("source_tree_dirty") is False,
        "current_calibration_execution_passed": current.get(
            "execution_passed"
        ) is True,
        "current_calibration_trusted_evidence": current.get(
            "trusted_evidence"
        ) is True,
        "exact_section_matches": section_matches,
        "truth_blind_aggregate_metrics_exactly_match": (
            frozen_truth == current_truth
        ),
        "truth_blind_per_world_differences": truth_differences,
        "truth_blind_per_world_difference_count": len(truth_differences),
        "expected_roundoff_path": "/8/batch_diversity",
        "maximum_truth_blind_absolute_difference": max(
            (
                float(record["absolute_difference"])
                for record in truth_differences
                if record["absolute_difference"] is not None
            ),
            default=0.0,
        ),
        "data_sha256": _sha256(DATA),
    }
    result["passed"] = bool(
        result["current_calibration_execution_passed"]
        and result["current_calibration_trusted_evidence"]
        and result["current_calibration_source_clean"]
        and all(section_matches.values())
        and result["truth_blind_aggregate_metrics_exactly_match"]
        and len(truth_differences) == 1
        and truth_differences[0]["path"] == result["expected_roundoff_path"]
        and truth_differences[0]["absolute_difference"] is not None
        and truth_differences[0]["absolute_difference"] <= MAX_EXPECTED_ROUNDOFF
        and result["data_sha256"] == DATA_SHA256
    )
    return result


def audit_source_contract(current_revision: str) -> dict[str, Any]:
    records = []
    for relative, expected in SOURCE_HASH_CONTRACT.items():
        old_hash = _sha256_bytes(_git_show(INPUT_SOURCE_REVISION, relative))
        new_hash = _sha256_bytes(_normalized_current_source(relative))
        records.append({
            "path": relative,
            "old_sha256": old_hash,
            "expected_old_sha256": expected["old"],
            "new_sha256": new_hash,
            "expected_new_sha256": expected["new"],
            "hash_contract_passed": (
                old_hash == expected["old"] and new_hash == expected["new"]
            ),
        })
    changes = _source_changes(INPUT_SOURCE_REVISION, current_revision)
    alloy_changes = [value for value in changes if value not in RUNTIME_PATHS]
    runtime_changes = [value for value in changes if value in RUNTIME_PATHS]
    runtime_migration = runtime_migration_status(
        INPUT_SOURCE_REVISION, current_revision, runtime_changes,
    ) if runtime_changes else None
    result = {
        "input_source_revision": INPUT_SOURCE_REVISION,
        "audited_target_revision": current_revision,
        "task_runtime_source_changes": changes,
        "allowed_task_runtime_source_changes": list(ALLOWED_RUNTIME_CHANGES),
        "alloy_task_runtime_source_changes": alloy_changes,
        "shared_runtime_source_changes": runtime_changes,
        "shared_runtime_migration": runtime_migration,
        "source_hash_records": records,
        "frozen_data_sha256": _sha256(DATA),
        "semantic_change": (
            "Sort the union of composition element keys before summing absolute "
            "differences in the public baseline, trusted evaluator, and frozen "
            "calibration witness."
        ),
    }
    result["passed"] = bool(
        alloy_changes == list(ALLOWED_RUNTIME_CHANGES)
        and (
            not runtime_changes
            or (runtime_migration or {}).get("accepted") is True
        )
        and all(record["hash_contract_passed"] for record in records)
        and result["frozen_data_sha256"] == DATA_SHA256
    )
    return result


def audit(csv_path: Path) -> dict[str, Any]:
    provenance = source_provenance(ROOT)
    current_revision = str(provenance.get("git_revision"))
    source_contract = audit_source_contract(current_revision)
    landscape = audit_landscape()
    calibration = audit_calibration(csv_path)
    retained = audit_retained_artifacts()
    execution_passed = bool(
        source_contract["passed"]
        and landscape["passed"]
        and calibration["passed"]
        and retained["passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_SOURCE_MIGRATION_AUDIT",
        "evidence_scope": (
            "ALLOY_HASH_ORDER_NUMERICAL_STABILIZATION_MIGRATION_"
            "RETAINED_ARTIFACT_REPLAY_NOT_UNRETAINED_INTERMEDIATE_SOURCE_"
            "REPLAY_PROSPECTIVE_ALLOY_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": provenance,
        "environment": {
            "python": sys.version, "platform": platform.platform(),
        },
        "task": TASK_ID,
        "source_contract": source_contract,
        "finite_landscape_audit": landscape,
        "clean_calibration_audit": calibration,
        "retained_artifact_audit": retained,
        "conclusion": {
            "migration_accepted": execution_passed,
            "scientific_selection_space_changed": False,
            "baseline_or_reference_metrics_changed": False,
            "retained_source_metrics_changed": False,
            "intermediate_unretained_sources_replayed": False,
            "historical_trajectory_claim_scope": (
                "Historical trajectory accounting and retained selected/terminal "
                "results remain supported. Three intermediate candidates cannot be "
                "source-replayed; their stored trajectory metrics remain historical "
                "records and must not be presented as current-revision reruns."
            ),
        },
        "limitations": [
            "Three of seven unique proposal sources were not retained and cannot be rerun.",
            "The finite public replay cannot establish prospective alloy discovery.",
            "The migration audit establishes numerical/source compatibility for this exact patch, not equivalence for future evaluator edits.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    report["conclusion"]["migration_accepted"] = bool(
        report["execution_passed"] and report["trusted_evidence"]
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.csv.resolve())
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
        "migration_accepted": report["conclusion"]["migration_accepted"],
        "unretained_unique_proposal_count": report[
            "retained_artifact_audit"
        ]["unretained_unique_proposal_count"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
