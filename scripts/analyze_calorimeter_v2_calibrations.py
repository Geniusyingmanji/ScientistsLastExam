#!/usr/bin/env python3
"""Bind and analyze the CalorimeterDesign-v2 GPT-5.5 calibrations.

The three inputs are single runs.  They do not estimate a population, scaling
law or feedback effect, and they are not GEANT4, test-beam, detector-validation
or autonomous-discovery evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
)
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from sle.runtime_migration import (  # noqa: E402
    runtime_migration_status,
    runtime_source_changes,
)


TASK = "ParticlePhysics/CalorimeterDesign"
CALIBRATION = "experiments/calorimeter_v2_calibration_2026-07-25.json"
REPORTS = {
    "budget_one": "experiments/gpt55_calorimeter_v2_b1_2026-07-25.json",
    "normal_budget_three": (
        "experiments/gpt55_calorimeter_v2_b3_2026-07-25.json"
    ),
    "blind_budget_three": (
        "experiments/gpt55_calorimeter_v2_blind_b3_2026-07-25.json"
    ),
}
EXPECTED_MODEL_SOURCE_REVISION = (
    "f6a7b7365809bbe64c655777f8e4f72eb8182da4"
)
TASK_RUNTIME_SCOPE = (
    "sle/evaluate.py",
    "sle/trusted_driver.py",
    "sle/secure_eval.py",
    "sle/candidate_worker.py",
    "sle/rpc_codec.py",
    "sle/spec.py",
    "sle/registry.py",
    "benchmarks/Physics/CalorimeterDesign",
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
    "development_mean_resolution",
    "heldout_mean_resolution",
    "development_linearity_rms",
    "heldout_linearity_rms",
    "development_minimum_containment",
    "heldout_minimum_containment",
    "development_mean_cost_utilization",
    "heldout_mean_cost_utilization",
    "development_shift_geometry_feasibility_rate",
    "heldout_shift_geometry_feasibility_rate",
    "candidate_instance_call_count",
    "candidate_instance_valid_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _science(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in SCIENCE_FIELDS}


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


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    dimensions = document.get("task_dimensions") or {}
    physics = document.get("independent_physics_checks") or []
    references = document.get("reference_regeneration") or []
    invalid = document.get("invalid_artifact_checks") or {}
    weak = document.get("weak_baseline") or {}
    nominal = document.get("nominal_reference_policy") or {}
    robust = document.get("robust_reference_policy") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and provenance.get("git_revision") == EXPECTED_MODEL_SOURCE_REVISION
        and dimensions.get("development_instance_count") == 4
        and dimensions.get("heldout_instance_count") == 2
        and dimensions.get("archive_size") == 3
        and dimensions.get("shift_count") == 5
        and dimensions.get("total_regime_option_count") == 18
        and len(physics) == 6
        and all(row.get("passed") is True for row in physics)
        and len(references) == 6
        and all(row.get("passed") is True for row in references)
        and len(invalid) == 6
        and all(row.get("passed") is True for row in invalid.values())
        and weak.get("combined_score") == 0.0
        and weak.get("valid") == 1.0
        and nominal.get("combined_score") == 1.0
        and nominal.get("heldout_policy_score") == 1.0
        and nominal.get("robustness_score") == 0.0
        and robust.get("robustness_score") == 1.0
        and robust.get("heldout_robustness_score") == 1.0
        and document.get("difficulty_gate", {}).get("passed") is True
    ):
        raise ValueError("CalorimeterDesign-v2 task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "evidence_scope": document["evidence_scope"],
        "task_dimensions": dimensions,
        "weak_baseline": weak,
        "nominal_reference_policy": nominal,
        "robust_reference_policy": robust,
        "difficulty_gate": document["difficulty_gate"],
        "invalid_artifact_checks": invalid,
        "limitations": document["limitations"],
    }


def _retained_terminal_diagnosis(path: Path, oracle) -> dict[str, Any]:
    module = _load_module(path, "calorimeter_retained_" + _sha256(path)[:12])
    policy = getattr(module, "design_calorimeter")
    metrics = oracle.evaluate(policy)
    reasons = [
        str(row.get("reason")) for row in metrics.get("per_instance", [])
    ]
    normalized = Counter()
    for reason in reasons:
        if "radiation_length_scint_mm" in reason:
            normalized["missing_public_key:radiation_length_scint_mm"] += 1
        elif "light_yield_per_gev" in reason:
            normalized["missing_public_key:light_yield_per_gev"] += 1
        else:
            normalized["other"] += 1
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256(path),
        "compiles_and_imports": True,
        "direct_oracle_valid": float(metrics.get("valid", 0.0)),
        "direct_oracle_score": float(metrics.get("combined_score", 0.0)),
        "candidate_instance_valid_rate": float(
            metrics.get("candidate_instance_valid_rate", 0.0)
        ),
        "per_instance_reasons": reasons,
        "normalized_reason_counts": dict(sorted(normalized.items())),
    }


def _load_model(label: str, relative: str, oracle) -> dict[str, Any]:
    report_path = ROOT / relative
    document = json.loads(report_path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
        and provenance.get("source_tree_dirty") is False
        and provenance.get("source_changes") == []
        and provenance.get("git_revision") == EXPECTED_MODEL_SOURCE_REVISION
    ):
        raise ValueError("model report is not trusted and passed: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one completed run: %s" % relative)
    run = runs[0]
    config = document.get("config") or {}
    expected_mode = (
        "selection_blind" if label == "blind_budget_three" else "normal"
    )
    expected_budget = 1 if label == "budget_one" else 3
    expected_seed = 0 if label == "budget_one" else 1
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and config.get("budget") == expected_budget
        and run.get("seed") == expected_seed
        and config.get("llm", {}).get("model") == "gpt-5.5"
        and config.get("llm", {}).get("server_side_seed_control") is False
    ):
        raise ValueError("unexpected calorimeter calibration condition")

    workdir = Path(run["workdir"]).resolve()
    try:
        relative_workdir = workdir.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("model workdir is outside repository") from exc
    trajectory_path = workdir / "trajectory.jsonl"
    raw_events = load_trajectory(trajectory_path)
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot differs from raw trajectory")
    if len(raw_events) != expected_budget + 1:
        raise ValueError("trajectory lacks baseline plus every proposal")

    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("raw and compact trajectory lineage differs")
        metrics = raw.get("metrics") or {}
        trajectory.append({
            "step": int(raw["step"]),
            "oracle_calls": int(raw["oracle_calls"]),
            "budget_units": int(raw["budget_units"]),
            "score": float(raw["score"]),
            "best_score": float(raw["best_score"]),
            "valid": bool(raw["valid"]) and metrics.get("valid") == 1.0,
            "accepted": bool(raw["accepted"]),
            "candidate_sha256": raw["candidate_sha256"],
            "parent_sha256": raw["parent_sha256"],
            "candidate_failure_kind": metrics.get("candidate_failure_kind"),
            "infrastructure_failure": bool(
                metrics.get("infrastructure_failure")
            ),
            "science_metrics": _science(metrics),
            "llm": raw.get("llm") or {},
            "algorithm_metadata": raw.get("algorithm_metadata") or {},
        })

    proposals = trajectory[1:]
    best_program = workdir / "best_program.py"
    terminal_program = workdir / "solution.py"
    baseline_hash = trajectory[0]["candidate_sha256"]
    if _sha256(best_program) != baseline_hash:
        raise ValueError("zero-score best program is not the valid baseline")
    if _sha256(terminal_program) != trajectory[-1]["candidate_sha256"]:
        raise ValueError("terminal source differs from terminal proposal hash")
    terminal = _retained_terminal_diagnosis(terminal_program, oracle)

    manifest_path = workdir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = run.get("summary") or {}
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if expected_mode == "selection_blind" else "online_incumbent"
    )
    failure_counts = Counter(
        str(event["candidate_failure_kind"])
        for event in proposals if event["candidate_failure_kind"]
    )
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(report_path),
        "source_revision": provenance["git_revision"],
        "source_scope": provenance.get("source_scope"),
        "llm_condition_sha256": config.get("llm_condition_sha256"),
        "model": config.get("llm", {}).get("model"),
        "server_side_seed_control": False,
        "feedback_mode": expected_mode,
        "feedback_scope": summary.get("feedback_scope"),
        "selection_policy": summary.get("selection_policy"),
        "seed": expected_seed,
        "proposal_budget": expected_budget,
        "oracle_calls": int(summary["oracle_calls"]),
        "budget_units": int(summary["budget_units"]),
        "llm_calls": int(summary["llm"]["calls"]),
        "provider_usage_records": int(
            summary["llm"]["provider_usage_records"]
        ),
        "input_tokens": summary["llm"].get("input_tokens"),
        "output_tokens": summary["llm"].get("output_tokens"),
        "total_tokens": summary["llm"].get("total_tokens"),
        "wall_seconds": float(summary["wall_seconds"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "best_so_far_auc": float(summary["best_so_far_auc"]),
        "accepted_proposals": int(run["accepted"]),
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "invalid_proposal_count": sum(not event["valid"] for event in proposals),
        "failure_counts": dict(sorted(failure_counts.items())),
        "infrastructure_failure_count": sum(
            event["infrastructure_failure"] for event in proposals
        ),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "run_manifest_sha256": _sha256(manifest_path),
        "task_contract_sha256": manifest.get("task_contract_sha256"),
        "runtime_source_sha256": manifest.get("runtime_source_sha256"),
        "baseline_candidate_sha256": baseline_hash,
        "best_program": str(relative_workdir / "best_program.py"),
        "best_program_sha256": _sha256(best_program),
        "terminal_program": str(relative_workdir / "solution.py"),
        "terminal_program_sha256": _sha256(terminal_program),
        "terminal_source_diagnosis": terminal,
        "artifact_retention_scope": (
            "baseline-selected best and terminal proposal source are retained; "
            "intermediate proposal sources are not retained, but hashes, lineage, "
            "sanitized failure kinds and accounting remain bound"
        ),
        "trajectory": trajectory,
    }
    record["integrity_passed"] = bool(
        _lineage_is_valid(record)
        and record["selection_policy"] == expected_policy
        and record["oracle_calls"] == expected_budget + 1
        and record["budget_units"] == expected_budget + 1
        and record["llm_calls"] == expected_budget
        and record["provider_usage_records"] == expected_budget
        and int(run["evaluated"]) == expected_budget + 1
        and record["accepted_proposals"] == 0
        and record["valid_proposal_count"] == 0
        and record["failure_counts"] == {
            "candidate_runtime_error": expected_budget
        }
        and record["infrastructure_failure_count"] == 0
        and record["baseline_score"] == record["best_score"] == 0.0
        and manifest.get("task_id") == TASK
        and manifest.get("feedback_mode") == expected_mode
        and manifest.get("seed") == expected_seed
        and manifest.get("llm_condition_sha256")
        == config.get("llm_condition_sha256")
        and terminal["sha256"] == trajectory[-1]["candidate_sha256"]
        and terminal["direct_oracle_valid"] == 0.0
        and terminal["candidate_instance_valid_rate"] == 0.0
    )
    if not record["integrity_passed"]:
        raise ValueError("calorimeter lineage, accounting or artifact gate failed")
    return record


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    runtime_source_equivalent: bool = True,
    runtime_source_changes: list[str] | None = None,
    runtime_migration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    scopes = {tuple(record["source_scope"] or []) for record in records.values()}
    conditions = {record["llm_condition_sha256"] for record in records.values()}
    contracts = {record["task_contract_sha256"] for record in records.values()}
    runtimes = {record["runtime_source_sha256"] for record in records.values()}
    all_proposals = [
        event
        for record in records.values()
        for event in record["trajectory"][1:]
    ]
    b3_token_delta = normal["total_tokens"] - blind["total_tokens"]
    b3_wall_delta = normal["wall_seconds"] - blind["wall_seconds"]
    terminal_reason_counts = Counter()
    for record in records.values():
        terminal_reason_counts.update(
            record["terminal_source_diagnosis"]["normalized_reason_counts"]
        )
    execution_passed = bool(
        calibration["source_revision"] == EXPECTED_MODEL_SOURCE_REVISION
        and revisions == {EXPECTED_MODEL_SOURCE_REVISION}
        and runtime_source_equivalent
        and len(scopes) == 1
        and len(conditions) == 1
        and None not in conditions
        and len(contracts) == 1
        and None not in contracts
        and len(runtimes) == 1
        and None not in runtimes
        and all(record["integrity_passed"] for record in records.values())
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["seed"] == 0
        and normal["seed"] == blind["seed"] == 1
        and len(all_proposals) == 7
        and sum(event["valid"] for event in all_proposals) == 0
        and sum(event["infrastructure_failure"] for event in all_proposals) == 0
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and normal["baseline_candidate_sha256"]
        == blind["baseline_candidate_sha256"]
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "REDUCED_ORDER_CALORIMETER_SINGLE_RUN_GPT55_CALIBRATION_NOT_"
            "FEEDBACK_CAUSAL_POPULATION_GEANT4_TEST_BEAM_ENGINEERING_OR_"
            "AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "model_source_revision": EXPECTED_MODEL_SOURCE_REVISION,
        "input_task_runtime_source_equivalent": runtime_source_equivalent,
        "input_task_runtime_source_changes": runtime_source_changes or [],
        "input_task_runtime_source_migration": runtime_migration,
        "input_source_scope_equivalent": len(scopes) == 1,
        "input_llm_condition_equivalent": len(conditions) == 1,
        "input_task_contract_equivalent": len(contracts) == 1,
        "input_runtime_manifest_equivalent": len(runtimes) == 1,
        "task_calibration": calibration,
        "records": records,
        "proposal_hurdle_summary": {
            "proposal_count": len(all_proposals),
            "valid_proposal_count": sum(event["valid"] for event in all_proposals),
            "invalid_proposal_count": sum(not event["valid"] for event in all_proposals),
            "candidate_runtime_error_count": sum(
                event["candidate_failure_kind"] == "candidate_runtime_error"
                for event in all_proposals
            ),
            "infrastructure_failure_count": sum(
                event["infrastructure_failure"] for event in all_proposals
            ),
            "retained_terminal_source_count": len(records),
            "unretained_intermediate_source_count": (
                len(all_proposals) - len(records)
            ),
            "retained_terminal_normalized_reason_counts": dict(
                sorted(terminal_reason_counts.items())
            ),
        },
        "normal_minus_blind_budget_three_descriptive_contrast": {
            "best_score": normal["best_score"] - blind["best_score"],
            "valid_proposal_count": (
                normal["valid_proposal_count"] - blind["valid_proposal_count"]
            ),
            "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
            "input_tokens": normal["input_tokens"] - blind["input_tokens"],
            "output_tokens": normal["output_tokens"] - blind["output_tokens"],
            "total_tokens": b3_token_delta,
            "wall_seconds": b3_wall_delta,
        },
        "reference_tradeoff_context": {
            "weak_baseline_development_score": calibration["weak_baseline"][
                "combined_score"
            ],
            "nominal_reference_development_score": calibration[
                "nominal_reference_policy"
            ]["combined_score"],
            "nominal_reference_development_robustness": calibration[
                "nominal_reference_policy"
            ]["robustness_score"],
            "robust_reference_development_score": calibration[
                "robust_reference_policy"
            ]["combined_score"],
            "robust_reference_development_robustness": calibration[
                "robust_reference_policy"
            ]["robustness_score"],
            "robust_reference_heldout_score": calibration[
                "robust_reference_policy"
            ]["heldout_policy_score"],
        },
        "descriptive_findings": {
            "all_seven_model_proposals_are_runtime_invalid": (
                len(all_proposals) == 7
                and not any(event["valid"] for event in all_proposals)
            ),
            "no_infrastructure_failure": (
                not any(event["infrastructure_failure"] for event in all_proposals)
            ),
            "normal_budget_three_cannot_repair_exact_api_contract": (
                normal["valid_proposal_count"] == 0
                and normal["proposal_count"] == 3
            ),
            "blind_budget_three_has_no_valid_proposal": (
                blind["valid_proposal_count"] == 0
                and blind["proposal_count"] == 3
            ),
            "normal_and_blind_are_oracle_call_matched": (
                normal["oracle_calls"] == blind["oracle_calls"] == 4
            ),
            "normal_and_blind_are_token_matched": b3_token_delta == 0,
            "normal_and_blind_share_baseline_hash": (
                normal["baseline_candidate_sha256"]
                == blind["baseline_candidate_sha256"]
            ),
            "retained_terminal_sources_compile_but_use_nonexistent_keys": (
                terminal_reason_counts
                == Counter({
                    "missing_public_key:radiation_length_scint_mm": 12,
                    "missing_public_key:light_yield_per_gev": 6,
                })
            ),
            "model_reaches_nominal_robust_tradeoff_curve": False,
            "feedback_effect_identified": False,
            "detector_or_autonomous_discovery_demonstrated": False,
        },
        "limitations": [
            "Each condition has one run; no confidence interval, population, leaderboard or scaling-law estimate is supported.",
            "The Azure endpoint exposes no server-side generation seed, so equal local seed labels do not pair model randomness.",
            "Normal and selection-blind match oracle calls and local seed labels but differ in prompts, feedback semantics, generated programs, output tokens and wall time; their contrast is descriptive, not causal.",
            "Budget one uses local seed label zero and budget three label one; they are independent calibrations, not prefixes of one trajectory.",
            "Candidate exception text is intentionally sanitized during secure evaluation; all seven failures are publicly classified only as candidate_runtime_error.",
            "Only the terminal proposal source from each condition is retained. The three retained sources permit exact offline KeyError diagnosis; the four intermediate proposal sources are not retained and cannot be assigned a narrower failure cause.",
            "The retained source diagnosis runs the frozen oracle outside the secure sandbox only after search and is excluded from all prompts and selection.",
            "The task is a deterministic repository-visible reduced-order model, not GEANT4, electronics simulation, manufacturing validation or test-beam evidence.",
            "No independent detector-physics review, fabricated detector or experimental confirmation is present.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    oracle = _load_module(
        ROOT
        / "benchmarks/Physics/CalorimeterDesign/verification/evaluator.py",
        "calorimeter_analysis_oracle",
    )
    records = {
        label: _load_model(label, relative, oracle)
        for label, relative in REPORTS.items()
    }
    current_revision = source_provenance(ROOT).get("git_revision")
    changes = _source_changes(EXPECTED_MODEL_SOURCE_REVISION, current_revision)
    migration = runtime_migration_status(
        EXPECTED_MODEL_SOURCE_REVISION, current_revision, changes,
    ) if changes else None
    equivalent = bool(not changes or (migration or {}).get("accepted") is True)
    return _analyze_records(
        calibration,
        records,
        runtime_source_equivalent=equivalent,
        runtime_source_changes=changes,
        runtime_migration=migration,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
