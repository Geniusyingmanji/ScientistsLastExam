#!/usr/bin/env python3
"""Bind and analyze the three LidDrivenCavity-v2 GPT-5.5 calibrations.

The model runs are single-run calibrations, not population or causal evidence.
This analyzer verifies report/raw-trajectory hashes and proposal lineage, retains
the sealed PDE/held-out/grid axes, and evaluates the selected programs on three
post-hoc Reynolds/grid probes that were absent from the benchmark calls.  Those
probes diagnose solver generality but are not preregistered hidden-test evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


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
from sle.runtime_migration import runtime_source_changes  # noqa: E402
from sle.secure_eval import CandidateProxy  # noqa: E402


CALIBRATION = "experiments/cavity_v2_calibration_2026-07-22.json"
REPORTS = {
    "budget_one": "experiments/gpt55_cavity_v2_b1_2026-07-22.json",
    "normal_budget_three": "experiments/gpt55_cavity_v2_b3_2026-07-22.json",
    "blind_budget_three": "experiments/gpt55_cavity_v2_blind_b3_2026-07-22.json",
}
TASK = "FluidDynamics/LidDrivenCavity"
TASK_RUNTIME_SCOPE = (
    "sle",
    "benchmarks/Engineering/LidDrivenCavity",
    "requirements-upstream.txt",
)
PROBE_SPECS = (
    {"name": "posthoc_re137_n27", "Re": 137.0, "N": 27},
    {"name": "posthoc_re245_n39", "Re": 245.0, "N": 39},
    {"name": "posthoc_re375_n45", "Re": 375.0, "N": 45},
)
FIELDS = (
    "combined_score", "valid", "feasibility_rate", "raw_score",
    "development_score", "ungated_development_score",
    "robustness_score", "ungated_robustness_score",
    "development_validation_gap", "heldout_policy_score",
    "ungated_heldout_policy_score", "heldout_robustness_score",
    "ungated_heldout_robustness_score", "heldout_artifact_valid_rate",
    "development_physics_feasibility_rate",
    "heldout_physics_feasibility_rate",
    "development_grid_feasibility_rate",
    "heldout_grid_feasibility_rate",
    "mean_development_field_similarity", "mean_heldout_field_similarity",
    "mean_development_poisson_relative_residual",
    "mean_heldout_poisson_relative_residual",
    "mean_development_transport_relative_residual",
    "mean_heldout_transport_relative_residual",
    "candidate_call_count", "candidate_call_valid_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_changes(left: str, right: str) -> list[str]:
    return runtime_source_changes(left, right, TASK_RUNTIME_SCOPE, root=ROOT)


def _scalar(metrics: dict[str, Any]) -> dict[str, Any]:
    return {field: metrics.get(field) for field in FIELDS}


def _load_oracle():
    path = ROOT / "benchmarks/Engineering/LidDrivenCavity/verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("cavity_v2_analysis_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load LidDrivenCavity-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_calibration(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("trusted_evidence") is True
        and document.get("passed") is True
        and document.get("execution_passed") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("cavity task calibration is not trusted and passed")
    expected_dimensions = {
        "development_case_count": 4,
        "heldout_case_count": 2,
        "refinement_call_count": 2,
        "total_candidate_call_count": 8,
        "reynolds_range": [100.0, 400.0],
    }
    if document.get("task_dimensions") != expected_dimensions:
        raise ValueError("unexpected cavity task dimensions")
    baseline = document.get("weak_baseline") or {}
    reference = document.get("trusted_reference_policy") or {}
    shortcut = document.get("attenuated_near_reference_shortcut") or {}
    gate = document.get("difficulty_and_integrity_gate") or {}
    if not (
        baseline.get("valid") == 1.0
        and baseline.get("combined_score") == 0.0
        and baseline.get("feasibility_rate") == 0.0
        and float(reference.get("combined_score", 0.0)) > 0.999
        and float(reference.get("heldout_policy_score", 0.0)) > 0.999
        and float(reference.get("robustness_score", 0.0)) > 0.999
        and float(reference.get("heldout_robustness_score", 0.0)) > 0.999
        and shortcut.get("combined_score") == 0.0
        and float(shortcut.get("ungated_development_score", 0.0)) > 0.80
        and all(bool(value) for value in gate.values())
    ):
        raise ValueError("cavity task calibration gate failed")
    return {
        "report": relative,
        "report_sha256": _sha256(path),
        "source_revision": provenance["git_revision"],
        "dimensions": expected_dimensions,
        "public_feasibility_tolerances": document[
            "public_feasibility_tolerances"
        ],
        "weak_baseline": _scalar(baseline),
        "trusted_reference": _scalar(reference),
        "shortcut_gate": {
            "ungated_development_score": shortcut[
                "ungated_development_score"
            ],
            "gated_development_score": shortcut["combined_score"],
            "physics_feasibility_rate": shortcut["feasibility_rate"],
        },
        "independent_ghia_re100_check": document[
            "independent_ghia_re100_check"
        ],
        "maximum_oracle_diagnostic_reproduction_error": document[
            "maximum_oracle_diagnostic_reproduction_error"
        ],
    }


def _selected_event(events: list[dict[str, Any]], best: float) -> dict[str, Any]:
    matches = [
        event for event in events
        if event.get("accepted")
        and abs(float(event["score"]) - float(best)) <= 1.0e-12
    ]
    if not matches:
        raise ValueError("no accepted event matches cavity run best")
    return min(matches, key=lambda event: int(event["step"]))


def _lineage_is_valid(record: dict[str, Any]) -> bool:
    events = record["trajectory"]
    baseline_hash = events[0]["candidate_sha256"]
    if record["feedback_mode"] == "selection_blind":
        return all(
            event["parent_sha256"] == baseline_hash for event in events[1:]
        )
    parent = baseline_hash
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            return False
        if event["accepted"]:
            parent = event["candidate_sha256"]
    return True


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if not (
        document.get("trusted_evidence") is True
        and document.get("passed") is True
        and document.get("execution_passed") is True
        and provenance.get("source_tree_dirty") is False
    ):
        raise ValueError("cavity model report is not trusted and passed: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected one successful cavity run: %s" % relative)
    run = runs[0]
    expected_mode = "selection_blind" if label == "blind_budget_three" else "normal"
    expected_budget = 1 if label == "budget_one" else 3
    expected_seed = 0 if label == "budget_one" else 1
    config = document.get("config") or {}
    if not (
        run.get("task") == TASK
        and run.get("algorithm") == "greedy_rewrite"
        and run.get("feedback_mode") == expected_mode
        and run.get("seed") == expected_seed
        and config.get("budget") == expected_budget
        and (config.get("llm") or {}).get("model") == "gpt-5.5"
    ):
        raise ValueError("unexpected cavity calibration condition")

    trajectory_path = Path(run["workdir"]) / "trajectory.jsonl"
    snapshot = compact_trajectory_snapshot(trajectory_path)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("cavity compact snapshot differs from raw trajectory")
    raw_events = load_trajectory(trajectory_path)
    if len(raw_events) != len(snapshot["events"]):
        raise ValueError("cavity raw and compact trajectory lengths differ")
    trajectory = []
    for compact, raw in zip(snapshot["events"], raw_events):
        if not (
            int(compact["step"]) == int(raw["step"])
            and compact["candidate_sha256"] == raw["candidate_sha256"]
            and compact["parent_sha256"] == raw["parent_sha256"]
        ):
            raise ValueError("cavity raw and compact trajectory lineage differs")
        trajectory.append({
            "step": int(compact["step"]),
            "accepted": bool(compact["accepted"]),
            "candidate_sha256": compact["candidate_sha256"],
            "parent_sha256": compact["parent_sha256"],
            **_scalar(raw.get("metrics") or {}),
        })

    selected = _selected_event(snapshot["events"], float(run["best"]))
    selected_raw = next(
        event for event in raw_events
        if int(event["step"]) == int(selected["step"])
    )
    candidate_path = Path(run["workdir"]) / "best_program.py"
    candidate_hash = _sha256(candidate_path)
    if candidate_hash != selected["candidate_sha256"]:
        raise ValueError("selected cavity candidate differs from best_program.py")
    record = {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": snapshot["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "feedback_mode": run["feedback_mode"],
        "feedback_scope": run["summary"].get("feedback_scope"),
        "selection_policy": run["summary"].get("selection_policy"),
        "seed": int(run["seed"]),
        "proposal_budget": int(config["budget"]),
        "server_side_seed_control": bool(
            config["llm"].get("server_side_seed_control")
        ),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": candidate_hash,
        "selected_candidate_path": str(candidate_path),
        "selected_candidate_line_count": len(
            candidate_path.read_text(encoding="utf-8").splitlines()
        ),
        "selected_metrics": _scalar(selected_raw.get("metrics") or {}),
        "trajectory": trajectory,
    }
    if not _lineage_is_valid(record):
        raise ValueError("cavity proposal lineage is broken")
    expected_policy = (
        "offline_best_of_open_loop_batch"
        if label == "blind_budget_three" else "online_incumbent"
    )
    if record["selection_policy"] != expected_policy:
        raise ValueError("cavity selection policy metadata is wrong")
    if int(run["evaluated"]) != record["oracle_calls"]:
        raise ValueError("cavity oracle-call count mismatch")
    if sum(event["accepted"] for event in trajectory[1:]) != int(run["accepted"]):
        raise ValueError("cavity accepted count mismatch")
    return record


def _velocity(streamfunction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    psi = np.asarray(streamfunction, dtype=float)
    h = 1.0 / (psi.shape[0] - 1)
    u = np.zeros_like(psi)
    v = np.zeros_like(psi)
    u[1:-1, 1:-1] = (
        psi[2:, 1:-1] - psi[:-2, 1:-1]
    ) / (2.0 * h)
    v[1:-1, 1:-1] = -(
        psi[1:-1, 2:] - psi[1:-1, :-2]
    ) / (2.0 * h)
    u[-1, 1:-1] = 1.0
    return u, v


def _probe_diagnostics(psi, omega, reference_psi, reynolds):
    psi = np.asarray(psi, dtype=float)
    omega = np.asarray(omega, dtype=float)
    reference_psi = np.asarray(reference_psi, dtype=float)
    n = psi.shape[0]
    h = 1.0 / (n - 1)
    u, v = _velocity(psi)
    ref_u, ref_v = _velocity(reference_psi)
    interior = (slice(1, -1), slice(1, -1))
    velocity_scale = math.sqrt(float(np.mean(
        ref_u[interior] ** 2 + ref_v[interior] ** 2
    ))) + 1.0e-12
    velocity_error = math.sqrt(float(np.mean(
        (u[interior] - ref_u[interior]) ** 2
        + (v[interior] - ref_v[interior]) ** 2
    ))) / velocity_scale
    psi_scale = math.sqrt(float(np.mean(reference_psi[interior] ** 2))) + 1.0e-12
    psi_error = math.sqrt(float(np.mean(
        (psi[interior] - reference_psi[interior]) ** 2
    ))) / psi_scale
    similarity = float(np.clip(
        1.0 - 0.75 * velocity_error - 0.25 * psi_error, 0.0, 1.0
    ))

    laplacian_psi = (
        psi[2:, 1:-1] + psi[:-2, 1:-1]
        + psi[1:-1, 2:] + psi[1:-1, :-2]
        - 4.0 * psi[1:-1, 1:-1]
    )
    source = h * h * omega[1:-1, 1:-1]
    poisson = laplacian_psi + source
    poisson_scale = math.sqrt(float(np.mean(
        laplacian_psi ** 2 + source ** 2
    ))) + 1.0e-12
    poisson_relative = math.sqrt(float(np.mean(poisson ** 2))) / poisson_scale

    diffusion = (
        omega[2:, 1:-1] + omega[:-2, 1:-1]
        + omega[1:-1, 2:] + omega[1:-1, :-2]
        - 4.0 * omega[1:-1, 1:-1]
    )
    convection = float(reynolds) * h * 0.5 * (
        u[1:-1, 1:-1]
        * (omega[1:-1, 2:] - omega[1:-1, :-2])
        + v[1:-1, 1:-1]
        * (omega[2:, 1:-1] - omega[:-2, 1:-1])
    )
    transport = diffusion - convection
    transport_scale = math.sqrt(float(np.mean(
        diffusion ** 2 + convection ** 2
    ))) + 1.0e-12
    transport_relative = (
        math.sqrt(float(np.mean(transport ** 2))) / transport_scale
    )

    wall_psi = np.concatenate((
        psi[0], psi[-1], psi[1:-1, 0], psi[1:-1, -1],
    ))
    expected = np.zeros_like(omega)
    expected[0, 1:-1] = -2.0 * psi[1, 1:-1] / h**2
    expected[-1, 1:-1] = -2.0 * psi[-2, 1:-1] / h**2 - 2.0 / h
    expected[1:-1, 0] = -2.0 * psi[1:-1, 1] / h**2
    expected[1:-1, -1] = -2.0 * psi[1:-1, -2] / h**2
    observed_walls = np.concatenate((
        omega[0, 1:-1], omega[-1, 1:-1],
        omega[1:-1, 0], omega[1:-1, -1],
    ))
    expected_walls = np.concatenate((
        expected[0, 1:-1], expected[-1, 1:-1],
        expected[1:-1, 0], expected[1:-1, -1],
    ))
    boundary_error = max(
        float(np.max(np.abs(wall_psi))) / 0.01,
        math.sqrt(float(np.mean((observed_walls - expected_walls) ** 2)))
        / (2.0 / h),
    )
    return {
        "field_similarity": similarity,
        "velocity_relative_error": float(velocity_error),
        "streamfunction_relative_error": float(psi_error),
        "poisson_relative_residual": float(poisson_relative),
        "transport_relative_residual": float(transport_relative),
        "boundary_relative_error": float(boundary_error),
    }


def _run_probes(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    oracle = _load_oracle()
    rows = []
    for label, record in records.items():
        candidate = Path(record["selected_candidate_path"])
        for probe in PROBE_SPECS:
            reynolds, n = float(probe["Re"]), int(probe["N"])
            with CandidateProxy(candidate, "solve_cavity", timeout_s=180.0) as proxy:
                returned = proxy(reynolds, n)
            psi, omega = oracle._validate_artifact(returned, n)
            reference_psi, _ = oracle._reference_solution(reynolds, n)
            diagnostics = _probe_diagnostics(
                psi, omega, reference_psi, reynolds
            )
            rows.append({
                "candidate_label": label,
                "candidate_sha256": record["selected_candidate_sha256"],
                **probe,
                **diagnostics,
                "physics_feasible": bool(
                    diagnostics["poisson_relative_residual"] <= 0.03
                    and diagnostics["transport_relative_residual"] <= 0.05
                    and diagnostics["boundary_relative_error"] <= 0.05
                ),
            })
    return rows


def _analyze_records(
    calibration: dict[str, Any],
    records: dict[str, dict[str, Any]],
    probes: list[dict[str, Any]],
    source_equivalent: bool = True,
) -> dict[str, Any]:
    one = records["budget_one"]
    normal = records["normal_budget_three"]
    blind = records["blind_budget_three"]
    revisions = {record["source_revision"] for record in records.values()}
    proposals = [
        event for record in records.values() for event in record["trajectory"][1:]
    ]
    by_probe_candidate = {
        label: [row for row in probes if row["candidate_label"] == label]
        for label in records
    }
    physics_feasible_proposals = sum(
        float(event["feasibility_rate"]) == 1.0 for event in proposals
    )
    all_probe_feasible = bool(
        len(probes) == len(records) * len(PROBE_SPECS)
        and all(row["physics_feasible"] for row in probes)
    )
    normal_minus_blind = {
        field: float(normal["selected_metrics"][field])
        - float(blind["selected_metrics"][field])
        for field in (
            "development_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score",
            "development_physics_feasibility_rate",
            "heldout_physics_feasibility_rate",
        )
    }
    normal_minus_blind.update({
        "total_tokens": normal["total_tokens"] - blind["total_tokens"],
        "oracle_calls": normal["oracle_calls"] - blind["oracle_calls"],
    })
    execution_passed = bool(
        source_equivalent
        and len(revisions) == 1
        and one["proposal_budget"] == 1
        and normal["proposal_budget"] == blind["proposal_budget"] == 3
        and one["oracle_calls"] == 2
        and normal["oracle_calls"] == blind["oracle_calls"] == 4
        and one["feedback_mode"] == normal["feedback_mode"] == "normal"
        and blind["feedback_mode"] == "selection_blind"
        and all(not record["server_side_seed_control"] for record in records.values())
        and all(_lineage_is_valid(record) for record in records.values())
        and len(proposals) == 7
        and all(event["valid"] == 1.0 for event in proposals)
        and all(event["candidate_call_valid_rate"] == 1.0 for event in proposals)
        and physics_feasible_proposals == 5
        and one["best_score"] > 0.9999999
        and 0.85 < normal["best_score"] < 0.95
        and blind["best_score"] > 0.9999999
        and blind["best_score"] > normal["best_score"]
        and sum(event["accepted"] for event in one["trajectory"][1:]) == 1
        and sum(event["accepted"] for event in normal["trajectory"][1:]) == 3
        and sum(event["accepted"] for event in blind["trajectory"][1:]) == 1
        and normal["total_tokens"] > blind["total_tokens"]
        and all_probe_feasible
        and min(
            row["field_similarity"]
            for row in by_probe_candidate["budget_one"]
        ) > 0.9999999
        and min(
            row["field_similarity"]
            for row in by_probe_candidate["blind_budget_three"]
        ) > 0.9999999
        and min(
            row["field_similarity"]
            for row in by_probe_candidate["normal_budget_three"]
        ) > 0.80
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "CAVITY_SOLVER_CALIBRATION_WITH_POSTHOC_PROBES_NOT_CAUSAL_"
            "POPULATION_HIGHER_ORDER_EXPERIMENTAL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_task_source_revision": calibration["source_revision"],
        "input_model_source_revision": (
            next(iter(revisions)) if len(revisions) == 1 else None
        ),
        "input_task_runtime_source_equivalent": bool(source_equivalent),
        "task_calibration": calibration,
        "records": records,
        "observed_model_proposal_pattern": {
            "proposal_count": len(proposals),
            "valid_artifact_count": sum(event["valid"] == 1.0 for event in proposals),
            "physics_feasible_proposal_count": physics_feasible_proposals,
            "minimum_development_score": min(
                float(event["development_score"]) for event in proposals
            ),
            "maximum_development_score": max(
                float(event["development_score"]) for event in proposals
            ),
            "budget_one_near_ceiling": one["best_score"] > 0.9999999,
            "open_loop_near_ceiling": blind["best_score"] > 0.9999999,
            "normal_budget_three_monotonic_accepted_scores": [
                event["development_score"]
                for event in normal["trajectory"][1:]
                if event["accepted"]
            ],
        },
        "normal_minus_blind_diagnostic": normal_minus_blind,
        "posthoc_procedural_probe_protocol": {
            "selected_after_model_runs": True,
            "preregistered": False,
            "benchmark_selection_metric": False,
            "candidate_process_isolation": "fresh sandbox for every candidate/probe pair",
            "reference": (
                "same trusted second-order discrete model at new Reynolds/grid pairs; "
                "not an independent high-order or experimental reference"
            ),
            "specs": list(PROBE_SPECS),
        },
        "posthoc_procedural_probe_results": probes,
        "posthoc_procedural_probe_summary": {
            label: {
                "probe_count": len(rows),
                "physics_feasible_count": sum(
                    row["physics_feasible"] for row in rows
                ),
                "minimum_field_similarity": min(
                    row["field_similarity"] for row in rows
                ),
                "maximum_transport_relative_residual": max(
                    row["transport_relative_residual"] for row in rows
                ),
            }
            for label, rows in by_probe_candidate.items()
        },
        "interpretation": {
            "supported": (
                "In these runs GPT-5.5 generated executable numerical cavity solvers; "
                "the budget-one and selected open-loop programs also matched the same "
                "discrete reference on three post-hoc Reynolds/grid probes."
            ),
            "benchmark_implication": (
                "One-proposal and open-loop near-ceiling solutions leave little iterative "
                "optimization headroom for this model/task contract; retain it as a CFD "
                "solver on-ramp unless harder procedural or multifidelity cases are added."
            ),
            "not_supported": (
                "No result establishes feedback causality, population capability, continuum "
                "or experimental CFD validity, a new physical mechanism, or autonomous "
                "scientific discovery."
            ),
        },
        "limitations": [
            "Each condition has one run; no confidence interval, model ranking or causal feedback estimate is supported.",
            "Normal and selection-blind share a local seed label, but the endpoint exposes no server-side model seed, so generation randomness is not paired.",
            "The budget-three conditions are oracle-call matched but not token- or context-matched; normal used %d more tokens." % (normal["total_tokens"] - blind["total_tokens"]),
            "Budget-one is an independent seed-label calibration rather than a prefix of the budget-three trajectory.",
            "The procedural probes were selected after the model runs and use the same second-order equation/reference family; they are diagnostic, not preregistered hidden or independent high-order validation.",
            "Public deterministic equations and cases may overlap model pretraining; source and transfer behavior do not prove absence of memorized numerical patterns.",
            "The task omits three-dimensionality, transition, turbulence, thermal coupling, geometry variation and experimental uncertainty.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    calibration = _load_calibration(CALIBRATION)
    records = {
        label: _load(label, relative) for label, relative in REPORTS.items()
    }
    revisions = {record["source_revision"] for record in records.values()}
    source_changes: list[str] = []
    source_equivalent = False
    if len(revisions) == 1:
        source_changes = _source_changes(
            next(iter(revisions)), "HEAD"
        )
        source_equivalent = not source_changes
    probes = _run_probes(records)
    report = _analyze_records(
        calibration, records, probes, source_equivalent
    )
    report["input_task_runtime_source_changes"] = source_changes
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
