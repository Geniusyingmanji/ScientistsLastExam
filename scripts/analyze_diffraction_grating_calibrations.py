#!/usr/bin/env python3
"""Bind and analyze the DiffractionGratingDesign-v2 GPT-5.5 calibrations.

The inputs are three single-run model calibrations, a deterministic RCWA task
calibration, and an independent ``grcwa`` numerical cross-check.  This script
binds clean-source provenance, raw trajectories, manifests, retained source
artifacts, deterministic replays, online/frozen-parent lineage, and a narrow
shortcut scan.  The result is descriptive computational evidence: it is not a
feedback effect, a fabricated/experimentally measured device, a global optimum,
or prospective autonomous scientific discovery.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from scripts.repo_paths import resolve_run_workdir  # noqa: E402
from sle.registry import find_task  # noqa: E402
from sle.runtime_migration import (  # noqa: E402
    compare_json_values,
    runtime_migration_status,
    runtime_source_changes,
)


TASK = "Optics/DiffractionGratingDesign"
TASK_DIR = ROOT / "benchmarks/Physics/DiffractionGratingDesign"
TASK_CALIBRATION_SOURCE_REVISION = (
    "e920e1c1c045bb20d1104e8b4f9a6188a34fbff5"
)
MODEL_SOURCE_REVISION = "aa9261836c0ba00c4858d76db6e308df2c94c1cb"
CALIBRATION = "experiments/diffraction_grating_v2_calibration_2026-07-26.json"
CROSSCHECK = (
    "experiments/diffraction_grating_v2_grcwa_crosscheck_2026-07-26.json"
)
REPORTS = {
    "budget_one": (
        "experiments/gpt55_diffraction_grating_v2_b1_2026-07-26.json"
    ),
    "normal_budget_three": (
        "experiments/gpt55_diffraction_grating_v2_b3_2026-07-26.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_diffraction_grating_v2_blind_b3_2026-07-26.json"
    ),
}
EXPECTED_CONDITIONS = {
    "budget_one": {"mode": "normal", "budget": 1, "seed": 0},
    "normal_budget_three": {"mode": "normal", "budget": 3, "seed": 1},
    "blind_budget_three": {
        "mode": "selection_blind",
        "budget": 3,
        "seed": 1,
    },
}
BASELINE_SHA256 = (
    "f2abe37d10285154574c5805325f5a0fdcc863e058e8503a5087359fdeba3046"
)
EXPECTED_TASK_CONTRACT_SHA256 = (
    "8af05515bbe25350e3e543cd2751f76e195125c8db8eab80dacaebd64700ff27"
)
EXPECTED_RUNTIME_SOURCE_SHA256 = (
    "c6e07c45b86985390dfe9510369cba3a93414f93a7142003ea4cb6ae5d7c0ae1"
)
EXPECTED_LLM_CONDITION_SHA256 = (
    "5b0df4671481f6b3505155bc6c5654a64c4da5591422fb806904e7d0f44fc4d2"
)
CALIBRATION_SHA256 = (
    "ea8e74b609fca6c4d01a6f7ca75861d71babdc22260c7a7d5cb2abbcae2ab4d6"
)
CROSSCHECK_SHA256 = (
    "4ca80525aed02cf613b60a5cc94ba632c51335057def94b3b7794f413671f8dc"
)
TASK_CONFIRMATION_MIGRATION_PATH = (
    "benchmarks/Optics/DiffractionGratingDesign/verification/evaluator.py"
)
CURRENT_EVALUATOR_PATH = (
    "benchmarks/Physics/DiffractionGratingDesign/verification/evaluator.py"
)
TASK_CONFIRMATION_BASE_SHA256 = (
    "b2662c9b531d969dcba58e9e40a51ea868a64cda9d47070d9b71ca89f124706a"
)
TASK_CONFIRMATION_CURRENT_SHA256 = (
    "6b02d2e25baa0c272d4eb568880dd5df8b373d25db6080f8dc5fba07f1b78a23"
)
REPLAY_NUMERIC_TOLERANCE = 5.0e-10
TASK_RUNTIME_SCOPE = (
    "sle/evaluate.py",
    "sle/trusted_driver.py",
    "sle/secure_eval.py",
    "sle/candidate_worker.py",
    "sle/rpc_codec.py",
    "sle/spec.py",
    "sle/registry.py",
    "benchmarks/Physics/DiffractionGratingDesign",
    "requirements-upstream.txt",
)
SCIENCE_FIELDS = (
    "combined_score",
    "raw_score",
    "robustness_score",
    "heldout_policy_score",
    "heldout_robustness_score",
    "feasibility_rate",
    "heldout_feasibility_rate",
    "development_mean_target_efficiency",
    "heldout_mean_target_efficiency",
    "development_minimum_target_efficiency",
    "heldout_minimum_target_efficiency",
    "development_te_mean_target_efficiency",
    "heldout_te_mean_target_efficiency",
    "development_tm_mean_target_efficiency",
    "heldout_tm_mean_target_efficiency",
    "development_maximum_energy_residual",
    "heldout_maximum_energy_residual",
    "development_shift_geometry_feasibility",
    "heldout_shift_geometry_feasibility",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)
INSTANCE_FIELDS = (
    "name",
    "split",
    "valid",
    "failure_kind",
    "score",
    "robustness_score",
    "nominal_utility",
    "robust_utility",
    "mean_target_efficiency",
    "twentieth_percentile_target_efficiency",
    "minimum_target_efficiency",
    "te_mean_target_efficiency",
    "tm_mean_target_efficiency",
    "maximum_energy_residual",
    "maximum_condition_number",
    "all_shift_geometries_feasible",
)
WORLD_NAMES = (
    "dev_visible_titania",
    "heldout_red_silicon_nitride",
    "dev_near_ir_silicon_nitride",
    "dev_blue_titania",
    "heldout_telecom_silicon",
    "dev_green_titania",
)
WORLD_LITERAL_VALUES = {
    0.64,
    0.72,
    0.82,
    0.94,
    1.24,
    0.50,
    0.66,
    1.31,
    1.72,
    0.56,
    0.74,
    2.22,
    2.05,
    2.03,
    2.35,
    2.06,
    2.28,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _science_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _source_scan(path: Path) -> dict[str, Any]:
    """Screen retained source for fixed worlds, evaluator access, I/O and network."""

    source = path.read_text(encoding="utf-8")
    source_hash = _sha256(path)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "source_sha256": source_hash,
            "source_bytes": len(source.encode("utf-8")),
            "source_lines": len(source.splitlines()),
            "syntax_valid": False,
            "syntax_error": "%s:%s" % (exc.lineno, exc.offset),
            "fixed_world_name_literal_hits": [],
            "fixed_world_numeric_literal_hits": [],
            "evaluator_or_verification_term_hits": [],
            "forbidden_import_hits": [],
            "forbidden_call_hits": [],
            "passed": False,
        }

    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    numeric_literals = {
        float(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    }
    world_name_hits = sorted(set(WORLD_NAMES) & string_literals)
    # 0.5 and 0.94 are ordinary fill/apodization constants in grating code, so
    # neither is a distinctive world fingerprint without a second identifier.
    numeric_hits = sorted(
        (WORLD_LITERAL_VALUES - {0.50, 0.94}) & numeric_literals
    )
    lower = source.lower()
    source_terms = (
        "verification/evaluator",
        "verification/",
        "evaluator.py",
        "frontier_eval",
        "world_specs",
        "development_worlds",
        "heldout_worlds",
        "reference_parameters",
        "reference_policy",
        "baseline_utility",
        "reference_utility",
        "shift_specs",
    )
    source_term_hits = sorted(term for term in source_terms if term in lower)
    forbidden_import_roots = {
        "http",
        "importlib",
        "inspect",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    import_hits: set[str] = set()
    call_hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_hits.update(
                alias.name.split(".")[0]
                for alias in node.names
                if alias.name.split(".")[0] in forbidden_import_roots
            )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden_import_roots:
                import_hits.add(root)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "__import__",
                "compile",
                "eval",
                "exec",
                "open",
            }:
                call_hits.add(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {
                    "read_bytes",
                    "read_text",
                    "urlopen",
                }
            ):
                call_hits.add(node.func.attr)
    passed = not (
        world_name_hits
        or numeric_hits
        or source_term_hits
        or import_hits
        or call_hits
    )
    return {
        "source_sha256": source_hash,
        "source_bytes": len(source.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "syntax_valid": True,
        "syntax_error": None,
        "fixed_world_name_literal_hits": world_name_hits,
        "fixed_world_numeric_literal_hits": numeric_hits,
        "evaluator_or_verification_term_hits": source_term_hits,
        "forbidden_import_hits": sorted(import_hits),
        "forbidden_call_hits": sorted(call_hits),
        "runtime_network_and_filesystem_isolation_checked_separately": True,
        "passed": passed,
    }


def _compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return _science_metrics(metrics)


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    dimensions = document.get("dimensions") or {}
    anchors = document.get("frozen_anchor_recalculation") or {}
    convergence = document.get("fourier_order_convergence") or {}
    fresnel = document.get("uniform_interface_fresnel_checks") or {}
    baseline = document.get("direct_weak_baseline") or {}
    reference = document.get("direct_reference") or {}
    invalid = document.get("invalid_submission_checks") or {}
    visible = (document.get("metric_sealing") or {}).get("visible_metric_keys")
    hashes = document.get("task_source_sha256") or {}
    historical_task_path = "benchmarks/Optics/DiffractionGratingDesign"
    expected_hash_paths = {
        historical_task_path + "/Task.md",
        historical_task_path + "/TASK_CARD.yaml",
        historical_task_path + "/solution.py",
        historical_task_path + "/verification/evaluator.py",
        historical_task_path + "/frontier_eval/metadata.yaml",
        historical_task_path + "/frontier_eval/run_eval.py",
        "scripts/calibrate_diffraction_grating_rcwa.py",
    }
    if not (
        _sha256(path) == CALIBRATION_SHA256
        and document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == TASK_CALIBRATION_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and dimensions == {
            "development_world_count": 4,
            "heldout_world_count": 2,
            "sealed_shift_count": 4,
            "layer_count": 5,
            "default_fourier_order": 9,
            "polarizations": ["TE", "TM"],
            "nominal_conditions_per_world": 18,
        }
        and anchors.get("maximum_anchor_error") == 0.0
        and float(anchors.get("minimum_nominal_headroom", 0.0)) > 0.25
        and float(anchors.get("minimum_robust_headroom", 0.0)) > 0.24
        and float(anchors.get("maximum_nominal_energy_residual", 1.0)) < 1e-10
        and convergence.get("lower_order") == 13
        and convergence.get("higher_order") == 19
        and len(convergence.get("records") or []) == 12
        and float(convergence.get("maximum_utility_delta", 1.0)) < 0.004
        and float(
            convergence.get("maximum_condition_efficiency_delta", 1.0)
        ) < 0.025
        and set(fresnel) == {"TE", "TM"}
        and all(row.get("absolute_error", 1.0) < 1e-12 for row in fresnel.values())
        and all(row.get("energy_residual", 1.0) < 1e-12 for row in fresnel.values())
        and baseline.get("valid") == 1.0
        and abs(float(baseline.get("combined_score", 1.0))) < 1e-12
        and abs(float(baseline.get("robustness_score", 1.0))) < 1e-12
        and abs(float(baseline.get("heldout_policy_score", 1.0))) < 1e-12
        and abs(float(baseline.get("heldout_robustness_score", 1.0))) < 1e-12
        and reference == {
            "combined_score": 1.0,
            "robustness_score": 1.0,
            "heldout_policy_score": 1.0,
            "heldout_robustness_score": 1.0,
            "valid": 1.0,
        }
        and document.get("secure_baseline_exactly_matches_direct") is True
        and visible == ["combined_score", "feasibility_rate", "raw_score", "valid"]
        and set(invalid) == {"bad_shape", "nonfinite", "minimum_feature"}
        and all(row.get("valid") == 0.0 for row in invalid.values())
        and set(hashes) == expected_hash_paths
        and hashes.get(
            historical_task_path + "/solution.py"
        ) == BASELINE_SHA256
    ):
        raise ValueError("DiffractionGratingDesign RCWA calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "dimensions": dimensions,
        "minimum_nominal_headroom": anchors["minimum_nominal_headroom"],
        "minimum_robust_headroom": anchors["minimum_robust_headroom"],
        "maximum_anchor_error": anchors["maximum_anchor_error"],
        "maximum_convergence_utility_delta": convergence[
            "maximum_utility_delta"
        ],
        "maximum_convergence_efficiency_delta": convergence[
            "maximum_condition_efficiency_delta"
        ],
        "uniform_interface_fresnel_checks": fresnel,
        "baseline": _compact_metrics(baseline),
        "reference": reference,
        "visible_metric_keys": visible,
        "task_source_sha256": hashes,
        "references": document.get("references") or [],
        "limitations": document.get("limitations") or [],
    }


def _load_crosscheck(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    configuration = document.get("configuration") or {}
    external = document.get("external_implementation") or {}
    summary = document.get("summary") or {}
    records = document.get("records") or []
    if not (
        _sha256(path) == CROSSCHECK_SHA256
        and document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == TASK_CALIBRATION_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and document.get("task") == TASK
        and configuration.get("internal_fourier_order") == 19
        and configuration.get("external_requested_harmonics") == 81
        and configuration.get("external_grid_points_per_period") == 768
        and configuration.get("world_count") == 6
        and configuration.get("artifacts_per_world") == 2
        and configuration.get("angles_per_artifact") == 3
        and configuration.get("polarizations") == ["TE", "TM"]
        and external.get("package") == "grcwa"
        and external.get("version") == "0.1.2"
        and external.get("paper_doi") == "10.1021/acsphotonics.0c00768"
        and external.get("wheel_sha256")
        == "65dbc0151d46a22985c1fe7f1070347e67562363fcb04371e9d158e3ba6140ee"
        and external.get("runtime_dependency_of_benchmark") is False
        and len(records) == 72
        and summary.get("condition_count") == 72
        and float(
            summary.get("maximum_absolute_efficiency_difference", 1.0)
        ) < 0.01
        and float(summary.get("mean_absolute_efficiency_difference", 1.0)) < 0.003
        and float(summary.get("q95_absolute_efficiency_difference", 1.0)) < 0.007
        and float(summary.get("maximum_internal_energy_residual", 1.0)) < 1e-10
        and float(summary.get("maximum_external_energy_residual", 1.0)) < 2e-12
        and {row.get("world") for row in records} == set(WORLD_NAMES)
        and {row.get("artifact") for row in records} == {"baseline", "reference"}
        and {row.get("polarization") for row in records} == {"TE", "TM"}
    ):
        raise ValueError("DiffractionGratingDesign grcwa cross-check gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "configuration": configuration,
        "external_implementation": external,
        "summary": summary,
        "limitations": document.get("limitations") or [],
    }


def _lineage_is_valid(record: dict[str, Any]) -> bool:
    events = record["trajectory"]
    baseline = events[0]["candidate_sha256"]
    if record["feedback_mode"] == "selection_blind":
        return all(event["parent_sha256"] == baseline for event in events[1:])
    parent = baseline
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _proposal_failure_taxonomy(per_instance: list[dict[str, Any]]) -> str | None:
    invalid = [row for row in per_instance if not row.get("valid")]
    if not invalid:
        return None
    if len(invalid) == len(per_instance):
        return "invalid_grating_submission_all_worlds"
    valid_names = {row.get("name") for row in per_instance if row.get("valid")}
    titania_names = {
        "dev_visible_titania",
        "dev_blue_titania",
        "dev_green_titania",
    }
    invalid_names = {row.get("name") for row in invalid}
    other_names = set(WORLD_NAMES) - titania_names
    if valid_names == titania_names and invalid_names == other_names:
        return "invalid_grating_submission_non_titania_transfer_worlds"
    return "invalid_grating_submission_partial_worlds"


def _instance_failure_diagnosis(per_instance: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row for row in per_instance if not row.get("valid")]
    shift_infeasible = [
        row
        for row in per_instance
        if row.get("valid") and not row.get("all_shift_geometries_feasible")
    ]
    return {
        "proposal_failure_kind": _proposal_failure_taxonomy(per_instance),
        "invalid_world_count": len(invalid),
        "invalid_world_names": [row.get("name") for row in invalid],
        "invalid_development_world_count": sum(
            row.get("split") == "development" for row in invalid
        ),
        "invalid_heldout_world_count": sum(
            row.get("split") == "heldout" for row in invalid
        ),
        "invalid_world_failure_counts": dict(sorted(Counter(
            str(row.get("failure_kind")) for row in invalid
        ).items())),
        "nominally_valid_but_shift_infeasible_world_count": len(shift_infeasible),
        "nominally_valid_but_shift_infeasible_world_names": [
            row.get("name") for row in shift_infeasible
        ],
        "shift_infeasible_development_world_count": sum(
            row.get("split") == "development" for row in shift_infeasible
        ),
        "shift_infeasible_heldout_world_count": sum(
            row.get("split") == "heldout" for row in shift_infeasible
        ),
    }


def _replay_retained_sources(
    sources: dict[str, Path], expected: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    spec = find_task(TASK, include_uncertified=True)
    results: dict[str, dict[str, Any]] = {}
    by_hash: dict[str, dict[str, Any]] = {}
    for name, path in sources.items():
        source_hash = _sha256(path)
        if source_hash not in by_hash:
            metrics = evaluate_candidate(spec, path, timeout_s=120)
            target = expected[source_hash]
            comparison = compare_json_values(
                target, metrics,
                numeric_tolerance=REPLAY_NUMERIC_TOLERANCE,
            )
            by_hash[source_hash] = {
                "source_sha256": source_hash,
                "valid": metrics.get("valid"),
                "combined_score": metrics.get("combined_score"),
                "robustness_score": metrics.get("robustness_score"),
                "heldout_policy_score": metrics.get("heldout_policy_score"),
                "heldout_robustness_score": metrics.get(
                    "heldout_robustness_score"
                ),
                "metrics_exactly_match_bound_trajectory": metrics == target,
                "metrics_numerically_equivalent_to_bound_trajectory": (
                    comparison["equivalent"]
                ),
                "non_numeric_difference_count": comparison[
                    "non_numeric_difference_count"
                ],
                "maximum_absolute_numeric_difference": comparison[
                    "maximum_absolute_numeric_difference"
                ],
            }
        results[name] = dict(by_hash[source_hash])
    return results


def _load_model(
    label: str, relative: str, replay_retained_sources: bool = True,
) -> dict[str, Any]:
    expected = EXPECTED_CONDITIONS[label]
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("passed") is True
        and document.get("trusted_evidence") is True
        and provenance.get("git_revision") == MODEL_SOURCE_REVISION
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
    ):
        raise ValueError("untrusted diffraction-grating model report: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful diffraction-grating model run")
    run = runs[0]
    config = document.get("config") or {}
    llm_config = config.get("llm") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected["mode"]
        and run.get("seed") == expected["seed"]
        and config.get("budget") == expected["budget"]
        and config.get("llm_condition_sha256") == EXPECTED_LLM_CONDITION_SHA256
        and llm_config.get("model") == "gpt-5.5"
        and llm_config.get("reasoning_effort") == "low"
        and llm_config.get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected diffraction-grating calibration condition")
    workdir = resolve_run_workdir(run["workdir"], ROOT)
    relative_workdir = workdir.relative_to(ROOT)
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable diffraction-grating snapshot differs from raw trajectory")
    if len(raw_events) != expected["budget"] + 1:
        raise ValueError("diffraction-grating trajectory is incomplete")

    trajectory = []
    expected_by_hash: dict[str, dict[str, Any]] = {}
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and portable diffraction-grating lineage differs")
        metrics = raw.get("metrics") or {}
        science = _science_metrics(metrics)
        if any(
            value is not None and not _finite_number(value)
            for value in science.values()
        ):
            raise ValueError("diffraction-grating science metric is non-finite")
        per_instance = metrics.get("per_instance") or []
        if len(per_instance) != 6:
            raise ValueError("diffraction-grating event does not retain all six worlds")
        if [row.get("name") for row in per_instance] != list(WORLD_NAMES):
            raise ValueError("diffraction-grating world order differs")
        if sum(row.get("split") == "development" for row in per_instance) != 4:
            raise ValueError("diffraction-grating development world count differs")
        if sum(row.get("split") == "heldout" for row in per_instance) != 2:
            raise ValueError("diffraction-grating held-out world count differs")
        compact_instances = [
            {field: row.get(field) for field in INSTANCE_FIELDS}
            for row in per_instance
        ]
        expected_by_hash[raw["candidate_sha256"]] = metrics
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw.get("valid")) and metrics.get("valid") == 1.0,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "science_metrics": science,
            "valid_world_count": sum(bool(row.get("valid")) for row in per_instance),
            "invalid_world_count": sum(not bool(row.get("valid")) for row in per_instance),
            "world_diagnosis": _instance_failure_diagnosis(compact_instances),
            "per_instance": compact_instances,
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    summary = run.get("summary") or {}
    manifest_path = workdir / "run_manifest.json"
    checkpoint_path = workdir / "checkpoint.json"
    summary_path = workdir / "summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected["mode"] == "selection_blind"
        else "online_incumbent"
    )
    best_program_path = workdir / "best_program.py"
    terminal_program_path = workdir / "solution.py"
    best_hash = _sha256(best_program_path)
    terminal_hash = _sha256(terminal_program_path)
    selected_events = [
        event for event in trajectory if event["candidate_sha256"] == best_hash
    ]
    if len(selected_events) != 1:
        raise ValueError("diffraction-grating best program does not identify one event")
    selected = selected_events[0]
    proposals = trajectory[1:]
    failure_counts = dict(sorted(Counter(
        event["world_diagnosis"]["proposal_failure_kind"]
        for event in proposals
        if event["world_diagnosis"]["proposal_failure_kind"]
    ).items()))
    scans = {
        "selected_best": _source_scan(best_program_path),
        "terminal": _source_scan(terminal_program_path),
    }
    retained_paths = {
        "selected_best": best_program_path,
        "terminal": terminal_program_path,
    }
    replay = (
        _replay_retained_sources(retained_paths, expected_by_hash)
        if replay_retained_sources
        else {}
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": llm_config.get("model"),
        "reasoning_effort": llm_config.get("reasoning_effort"),
        "server_side_seed_control": False,
        "feedback_mode": expected["mode"],
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": expected["budget"],
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(summary["llm"]["provider_usage_records"]),
        "input_tokens": summary["llm"].get("input_tokens"),
        "output_tokens": summary["llm"].get("output_tokens"),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "best_so_far_auc": float(summary["best_so_far_auc"]),
        "accepted_proposals": int(run["accepted"]),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "summary_sha256": _sha256(summary_path),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "baseline_candidate_sha256": trajectory[0]["candidate_sha256"],
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": best_hash,
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": terminal_hash,
        "checkpoint_best_program_sha256": checkpoint.get("best_sha256"),
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": selected["science_metrics"],
        "selected_world_diagnosis": selected["world_diagnosis"],
        "selected_per_instance": selected["per_instance"],
        "terminal_candidate_sha256": trajectory[-1]["candidate_sha256"],
        "trajectory": trajectory,
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "failure_counts": failure_counts,
        "retained_artifact_scans": scans,
        "retained_artifact_replays": replay,
        "artifact_retention_scope": (
            "selected-best and terminal source artifacts; all intermediate "
            "candidates remain trajectory-hash-bound but unretained"
        ),
    }
    record["integrity_passed"] = bool(
        record["baseline_candidate_sha256"] == BASELINE_SHA256
        and _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected["budget"] + 1
        and record["budget_units"] == expected["budget"] + 1
        and record["llm_calls"] == expected["budget"]
        and record["provider_usage_records"] == expected["budget"]
        and int(run["evaluated"]) == expected["budget"] + 1
        and record["accepted_proposals"]
        == sum(event["accepted"] for event in proposals)
        and abs(record["best_score"] - selected["score"]) < 1e-12
        and record["checkpoint_best_program_sha256"] == best_hash
        and record["terminal_program_sha256"] == record["terminal_candidate_sha256"]
        and all(scan["passed"] for scan in scans.values())
        and (
            not replay_retained_sources
            or all(
                item["metrics_numerically_equivalent_to_bound_trajectory"]
                for item in replay.values()
            )
        )
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected["mode"]
        and manifest.get("seed") == expected["seed"]
        and manifest.get("llm_condition_sha256") == EXPECTED_LLM_CONDITION_SHA256
        and record["task_contract_sha256"] == EXPECTED_TASK_CONTRACT_SHA256
        and record["runtime_source_sha256"] == EXPECTED_RUNTIME_SOURCE_SHA256
    )
    if not record["integrity_passed"]:
        raise ValueError(
            "diffraction-grating lineage, replay, accounting, or shortcut gate failed"
        )
    return record


def _analyze_records(
    calibration: dict[str, Any],
    crosscheck: dict[str, Any],
    records: dict[str, dict[str, Any]],
    calibration_to_model_source_equivalent: bool = True,
    calibration_to_model_source_changes: list[str] | None = None,
    model_to_runtime_source_equivalent: bool = True,
    model_to_runtime_source_changes: list[str] | None = None,
    model_to_runtime_migration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    task_contracts = {record["task_contract_sha256"] for record in records.values()}
    runtime_sources = {record["runtime_source_sha256"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    failures = dict(sorted(Counter(
        event["world_diagnosis"]["proposal_failure_kind"]
        for event in proposals
        if event["world_diagnosis"]["proposal_failure_kind"]
    ).items()))
    invalid_world_failures = dict(sorted(Counter(
        failure
        for event in proposals
        for failure, count in event["world_diagnosis"][
            "invalid_world_failure_counts"
        ].items()
        for _ in range(count)
    ).items()))
    contrast = {
        field: normal["selected_metrics"][field]
        - blind["selected_metrics"][field]
        for field in SCIENCE_FIELDS
    }
    contrast.update({
        "best_score": normal["best_score"] - blind["best_score"],
        "best_so_far_auc": normal["best_so_far_auc"] - blind["best_so_far_auc"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
        "input_tokens": normal["input_tokens"] - blind["input_tokens"],
        "output_tokens": normal["output_tokens"] - blind["output_tokens"],
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "wall_seconds": normal["wall_seconds"] - blind["wall_seconds"],
    })
    blind_selected = blind["trajectory"][blind["selected_step"]]
    blind_diag = blind_selected["world_diagnosis"]
    execution_passed = bool(
        calibration["source_revision"] == TASK_CALIBRATION_SOURCE_REVISION
        and crosscheck["source_revision"] == TASK_CALIBRATION_SOURCE_REVISION
        and revisions == {MODEL_SOURCE_REVISION}
        and calibration_to_model_source_equivalent
        and model_to_runtime_source_equivalent
        and tuple(calibration.get("source_scope") or []) in scopes
        and tuple(crosscheck.get("source_scope") or []) in scopes
        and len(scopes) == 1
        and conditions == {EXPECTED_LLM_CONDITION_SHA256}
        and task_contracts == {EXPECTED_TASK_CONTRACT_SHA256}
        and runtime_sources == {EXPECTED_RUNTIME_SOURCE_SHA256}
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and one["seed"] == 0
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and normal["seed"] == blind["seed"] == 1
        and normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and len(proposals) == 7
        and sum(event["valid"] for event in proposals) == 1
        and sum(not event["valid"] for event in proposals) == 6
        and failures == {
            "invalid_grating_submission_all_worlds": 2,
            "invalid_grating_submission_non_titania_transfer_worlds": 4,
        }
        and invalid_world_failures == {"invalid_grating_submission": 24}
        and one["selected_step"] == normal["selected_step"] == 0
        and blind["selected_step"] == 2
        and abs(blind["best_score"] - 0.18712975471717022) < 1e-12
        and abs(
            blind["selected_metrics"]["heldout_policy_score"]
            - 0.17300751374006115
        ) < 1e-12
        and abs(
            blind["selected_metrics"]["robustness_score"]
            - 0.1088319162022236
        ) < 1e-12
        and blind["selected_metrics"]["heldout_robustness_score"] == 0.0
        and blind_diag["nominally_valid_but_shift_infeasible_world_count"] == 3
        and blind_diag["shift_infeasible_development_world_count"] == 1
        and blind_diag["shift_infeasible_heldout_world_count"] == 2
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "DETERMINISTIC_1D_RCWA_GRATING_SINGLE_RUN_GPT55_CALIBRATION_"
            "WITH_INDEPENDENT_GRCWA_NUMERICAL_CROSSCHECK_NOT_FEEDBACK_CAUSAL_"
            "FABRICATED_DEVICE_MEASUREMENT_GLOBAL_OPTIMUM_POPULATION_"
            "PERFORMANCE_OR_PROSPECTIVE_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_calibration_source_revision": TASK_CALIBRATION_SOURCE_REVISION,
        "model_source_revision": MODEL_SOURCE_REVISION,
        "calibration_to_model_task_runtime_source_equivalent": (
            calibration_to_model_source_equivalent
        ),
        "calibration_to_model_task_runtime_source_changes": (
            calibration_to_model_source_changes or []
        ),
        "model_to_analysis_task_runtime_source_equivalent": (
            model_to_runtime_source_equivalent
        ),
        "model_to_analysis_task_runtime_source_changes": (
            model_to_runtime_source_changes or []
        ),
        "model_to_analysis_task_runtime_source_migration": (
            model_to_runtime_migration
        ),
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(task_contracts) == 1,
        "input_runtime_source_hash_equivalent": len(runtime_sources) == 1,
        "task_calibration": calibration,
        "independent_grcwa_crosscheck": crosscheck,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(proposals),
            "valid_proposal_count": sum(event["valid"] for event in proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in proposals),
            "positive_development_count": sum(
                event["valid"] and event["score"] > 0.0 for event in proposals
            ),
            "all_six_worlds_valid_count": sum(
                event["valid_world_count"] == 6 for event in proposals
            ),
            "proposal_failure_counts": failures,
            "invalid_world_failure_counts": invalid_world_failures,
        },
        "normal_minus_blind_budget_three_descriptive_contrast": contrast,
        "selected_science_axes": {
            label: {
                "selected_step": record["selected_step"],
                "development_visible_score": record["best_score"],
                "heldout_visible_score": record["selected_metrics"][
                    "heldout_policy_score"
                ],
                "development_robustness_score": record["selected_metrics"][
                    "robustness_score"
                ],
                "heldout_robustness_score": record["selected_metrics"][
                    "heldout_robustness_score"
                ],
                "development_mean_target_efficiency": record[
                    "selected_metrics"
                ]["development_mean_target_efficiency"],
                "heldout_mean_target_efficiency": record["selected_metrics"][
                    "heldout_mean_target_efficiency"
                ],
                "development_shift_geometry_feasibility": record[
                    "selected_metrics"
                ]["development_shift_geometry_feasibility"],
                "heldout_shift_geometry_feasibility": record[
                    "selected_metrics"
                ]["heldout_shift_geometry_feasibility"],
            }
            for label, record in records.items()
        },
        "selected_blind_robustness_gap": {
            "selected_step": blind_selected["step"],
            "nominally_valid_world_count": blind_selected["valid_world_count"],
            "nominally_valid_but_shift_infeasible_world_count": blind_diag[
                "nominally_valid_but_shift_infeasible_world_count"
            ],
            "development_shift_infeasible_world_count": blind_diag[
                "shift_infeasible_development_world_count"
            ],
            "heldout_shift_infeasible_world_count": blind_diag[
                "shift_infeasible_heldout_world_count"
            ],
            "shift_infeasible_world_names": blind_diag[
                "nominally_valid_but_shift_infeasible_world_names"
            ],
            "development_robustness_score": blind["selected_metrics"][
                "robustness_score"
            ],
            "heldout_robustness_score": blind["selected_metrics"][
                "heldout_robustness_score"
            ],
        },
        "descriptive_findings": {
            "one_of_seven_model_proposals_is_nominally_valid": sum(
                event["valid"] for event in proposals
            ) == 1,
            "six_of_seven_model_proposals_fail_protocol_validity": sum(
                not event["valid"] for event in proposals
            ) == 6,
            "four_invalid_proposals_fail_only_non_titania_transfer_worlds": (
                failures.get(
                    "invalid_grating_submission_non_titania_transfer_worlds"
                ) == 4
            ),
            "two_invalid_proposals_fail_all_six_worlds": (
                failures.get("invalid_grating_submission_all_worlds") == 2
            ),
            "blind_selected_improves_nominal_development_and_heldout_scores": (
                blind["best_score"] > one["best_score"]
                and blind["selected_metrics"]["heldout_policy_score"]
                > one["selected_metrics"]["heldout_policy_score"]
            ),
            "blind_selected_has_zero_heldout_robustness": (
                blind["selected_metrics"]["heldout_robustness_score"] == 0.0
            ),
            "all_blind_selected_heldout_worlds_have_shift_geometry_failure": (
                blind_diag["shift_infeasible_heldout_world_count"] == 2
            ),
            "normal_and_blind_are_oracle_call_matched": (
                contrast["oracle_calls"] == 0
            ),
            "normal_and_blind_are_input_token_matched": (
                contrast["input_tokens"] == 0
            ),
            "normal_and_blind_are_total_token_matched": (
                contrast["total_tokens"] == 0
            ),
            "retained_artifacts_pass_shortcut_scan": all(
                scan["passed"]
                for record in records.values()
                for scan in record["retained_artifact_scans"].values()
            ),
            "retained_artifact_replays_are_deterministic": all(
                replay["metrics_numerically_equivalent_to_bound_trajectory"]
                for record in records.values()
                for replay in record["retained_artifact_replays"].values()
            ),
            "independent_solver_is_experimental_validation": False,
            "feedback_effect_identified": False,
            "global_optimum_demonstrated": False,
            "fabricated_or_measured_device_demonstrated": False,
            "prospective_autonomous_scientific_discovery_demonstrated": False,
        },
        "limitations": [
            "Each model condition has one run; no confidence interval, population estimate, leaderboard ranking or scaling law is supported.",
            "The endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match input tokens and oracle calls but differ in output tokens, prompts, source artifacts and wall time; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; they are independent calibrations, not trajectory prefixes.",
            "Only selected-best and terminal source artifacts are retained; intermediate source text is unavailable, although every proposal remains hash- and trajectory-bound.",
            "The evaluator collapses validation exceptions to invalid_grating_submission, so intermediate-source root causes cannot be recovered beyond their per-world failure pattern.",
            "Static scanning and a networkless sandbox cannot rule out pretraining memorization or semantically hidden problem-specific behavior.",
            "The external grcwa result is independent software agreement within finite truncation tolerances, not physical experimental validation.",
            "The task is a deterministic lossless isotropic 1D simulation and omits absorption, anisotropy, roughness, finite aperture, 2D patterning, fabrication yield and detector response.",
            "The worlds are repository-visible; held-out here means evaluator-only selection metrics, not secret or contamination-free external test data.",
            "No device was fabricated or measured, no global optimum was proved, and no prospective autonomous scientific discovery occurred.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze(replay_retained_sources: bool = True) -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    crosscheck = _load_crosscheck(CROSSCHECK)
    records = {
        label: _load_model(
            label, relative, replay_retained_sources=replay_retained_sources,
        )
        for label, relative in REPORTS.items()
    }
    current_revision = source_provenance(ROOT).get("git_revision")
    calibration_to_model_changes = _source_changes(
        TASK_CALIBRATION_SOURCE_REVISION, MODEL_SOURCE_REVISION
    )
    model_to_runtime_changes = _source_changes(MODEL_SOURCE_REVISION, current_revision)
    old_evaluator_sha256 = hashlib.sha256(subprocess.check_output(
        ["git", "show", MODEL_SOURCE_REVISION + ":" + TASK_CONFIRMATION_MIGRATION_PATH],
        cwd=str(ROOT),
    )).hexdigest()
    current_evaluator_sha256 = _sha256(ROOT / CURRENT_EVALUATOR_PATH)
    confirmation_checks = {
        "old_evaluator_hash_matches": (
            old_evaluator_sha256 == TASK_CONFIRMATION_BASE_SHA256
        ),
        "current_evaluator_hash_matches": (
            current_evaluator_sha256 == TASK_CONFIRMATION_CURRENT_SHA256
        ),
        "legacy_replays_are_equivalent": all(
            replay["metrics_numerically_equivalent_to_bound_trajectory"]
            for record in records.values()
            for replay in record["retained_artifact_replays"].values()
        ),
    }
    migration = runtime_migration_status(
        MODEL_SOURCE_REVISION, current_revision, model_to_runtime_changes,
        additional_allowed_changes=(CURRENT_EVALUATOR_PATH,),
        additional_checks=confirmation_checks,
    ) if model_to_runtime_changes else None
    model_to_runtime_equivalent = bool(
        not model_to_runtime_changes or (migration or {}).get("accepted") is True
    )
    return _analyze_records(
        calibration,
        crosscheck,
        records,
        calibration_to_model_source_equivalent=not calibration_to_model_changes,
        calibration_to_model_source_changes=calibration_to_model_changes,
        model_to_runtime_source_equivalent=model_to_runtime_equivalent,
        model_to_runtime_source_changes=model_to_runtime_changes,
        model_to_runtime_migration=migration,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="skip deterministic retained-source re-evaluation",
    )
    args = parser.parse_args()
    report = analyze(replay_retained_sources=not args.skip_replay)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
