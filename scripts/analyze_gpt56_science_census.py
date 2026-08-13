#!/usr/bin/env python3
"""Validate and assess the preregistered 50-task GPT-5.6 science census.

The model forward pass is already complete.  This offline-only analysis may use
discipline, certification, task-card, historical and evaluator-only fields, but
none of those fields are fed back into the evaluated model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.evolve import SYSTEM_PROMPT, _build_prompt  # noqa: E402
from sle.metric_visibility import (  # noqa: E402
    SEARCH_VISIBLE_KEYS,
    search_visible_metrics,
)
from sle.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
    sha256_text,
)
from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from sle.registry import find_task  # noqa: E402


DEFAULT_REPORT = ROOT / "experiments/gpt56_science_census_2026-08-06_v1.json"
DEFAULT_MATURITY = ROOT / "experiments/task_maturity_audit_2026-08-03_v5.json"
DEFAULT_PILOT_ANALYSIS = (
    ROOT / "experiments/gpt56_science_pilot_analysis_2026-08-06_v1.json"
)

EXPECTED_REPORT_SHA256 = (
    "f396c86d98b0bb4103c1d9cdf43faf413016a713286d567c73ec47c2e175675e"
)
EXPECTED_MATURITY_SHA256 = (
    "dc7712a098be6b1d6c50dccfc709e77d5c685db0559ad7932414197b312080eb"
)
EXPECTED_PILOT_ANALYSIS_SHA256 = (
    "71693f1a6d07c86d0475f51fbec463773edee2b73dd7767f9a5e22d9d2eef04e"
)
EXPECTED_COHORT_SHA256 = (
    "dbe85bcd3a0174f4db231a6f915e62aef7a7e028ce36a956a1d316669efa110b"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "58544e11a86e37f61dfa098e382a46255596772371a13c543fbee7e4bcbcfb58"
)
EXPECTED_MODEL_CONDITION_SHA256 = (
    "60b240fdc2530ab24d202289a497dd4c2fb0ad1380a6ad9e8aca293bb8e4c34d"
)


TOOL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "physical_sim": (
        "domain simulation",
        "numerical optimization or inverse inference",
        "held-out and robustness analysis",
    ),
    "analytical": (
        "domain equations or exact combinatorial structure",
        "constrained numerical or discrete optimization",
        "feasibility verification",
    ),
    "real_data_replay": (
        "data preprocessing and statistical modeling",
        "budgeted experimental or batch selection",
        "uncertainty and transfer validation",
    ),
    "analytical_reduced_order_physics": (
        "reduced-order physical equations",
        "constrained design optimization",
        "sensitivity and robustness analysis",
    ),
    "active_coalescent_inference": (
        "coalescent stochastic-process modeling",
        "active sequencing design",
        "likelihood-based demographic inference and refusal",
    ),
    "prospective_evidence_synthesis": (
        "evidence screening and meta-regression",
        "uncertainty-calibrated forecasting",
        "prospective study design and confirmation",
    ),
    "exact_dynamic_programming": (
        "thermodynamic dynamic programming",
        "constrained sequence design",
        "ensemble and transfer verification",
    ),
    "stateful_reduced_order_kinetics": (
        "kinetic-system identification",
        "stateful experimental scheduling",
        "drift, refusal and decision analysis",
    ),
    "equilibrium_stage_process_sim": (
        "equilibrium-stage process simulation",
        "mixed discrete-continuous optimization",
        "off-design feasibility analysis",
    ),
    "active_pair_potential_hypothesis_laboratory": (
        "energy and force modeling",
        "active hypothesis discrimination and uncertainty",
        "virial integration and model-inadequacy refusal",
    ),
    "finite_basis_quantum_chemistry": (
        "Hartree-Fock matrix equations",
        "stable nonlinear SCF optimization",
        "representation and stability diagnostics",
    ),
    "active_system_identification": (
        "active dynamical-system identification",
        "parameter and forcing inference",
        "model-mismatch refusal and transfer",
    ),
    "active_physical_inverse": (
        "experiment or survey design",
        "physical inverse modeling",
        "extrapolation and model-inadequacy tests",
    ),
    "active_pde_identification_and_robust_design": (
        "PDE simulation and inverse identification",
        "active sensor or actuator design",
        "robust constrained optimization",
    ),
    "numerical_pde": (
        "PDE discretization and nonlinear solution",
        "residual and conservation diagnostics",
        "grid and parameter transfer",
    ),
    "raw_complex_instrument_pipeline": (
        "complex-signal calibration",
        "nonlinear resonance fitting",
        "physical versus instrument-fault diagnosis",
    ),
    "fourier_modal_rcwa": (
        "Fourier-modal Maxwell simulation",
        "nonconvex photonic geometry design",
        "polarization and fabrication robustness",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_trusted(path: Path, expected_sha256: str, role: str) -> dict[str, Any]:
    path = path.resolve()
    if _sha256(path) != expected_sha256:
        raise ValueError("%s hash differs from the frozen input" % role)
    document = json.loads(path.read_text(encoding="utf-8"))
    if not (
        document.get("execution_passed") is True
        and document.get("trusted_evidence") is True
        and document.get("passed") is True
    ):
        raise ValueError("%s is not trusted passing evidence" % role)
    return document


def _selected_event(events: list[dict[str, Any]], expected_best: float) -> dict[str, Any]:
    valid = [event for event in events if event.get("valid") is True]
    if not valid:
        raise ValueError("trajectory contains no valid event")
    selected = max(valid, key=lambda event: (float(event["score"]), -int(event["step"])))
    if not math.isclose(
        float(selected["score"]), expected_best, rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("selected event disagrees with run best")
    return selected


def _scalar_sealed_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in metrics.items():
        if key in SEARCH_VISIBLE_KEYS:
            continue
        if value is None or isinstance(value, (bool, str)):
            result[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(float(value)):
                raise ValueError("non-finite sealed metric: %s" % key)
            result[key] = value
    return result


def _nested_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for field in ("per_world", "per_instance", "per_problem"):
        value = metrics.get(field)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return rows


def _failure_diagnostic(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("valid") is True:
        return {
            "failure_kind": None,
            "failure_class": None,
            "nested_failure_kind_counts": {},
            "nested_reason_counts": {},
        }
    metrics = event.get("metrics") or {}
    nested = _nested_rows(metrics)
    nested_kinds = Counter(
        str(row["failure_kind"])
        for row in nested
        if row.get("failure_kind")
    )
    nested_reasons = Counter(
        str(row["reason"])
        for row in nested
        if row.get("reason")
    )
    kind = metrics.get("candidate_failure_kind")
    error = event.get("error") or metrics.get("error_message")
    if not kind and isinstance(error, str) and error:
        marker = "candidate invalid: "
        kind = error.split(marker, 1)[1] if marker in error else error
    if not kind and len(nested_kinds) == 1:
        kind = next(iter(nested_kinds))
    if not kind and nested_reasons:
        reasons = list(nested_reasons)
        if all(reason == "submission has the wrong fields" for reason in reasons):
            kind = "wrong_submission_fields"
        elif all(reason == "invalid_candidate_artifact" for reason in reasons):
            kind = "invalid_candidate_artifact"
        elif all("initial drifters must lie inside" in reason for reason in reasons):
            kind = "invalid_experiment_request"
        else:
            kind = "nested_invalid_submission"
    if not kind:
        kind = "invalid_submission_unclassified"
    runtime_kinds = {
        "candidate_runtime_error",
        "candidate_timeout",
        "candidate_worker_exit",
    }
    failure_class = (
        "candidate_execution_failure"
        if kind in runtime_kinds
        else "submission_or_protocol_failure"
    )
    return {
        "failure_kind": str(kind),
        "failure_class": failure_class,
        "nested_failure_kind_counts": dict(sorted(nested_kinds.items())),
        "nested_reason_counts": dict(sorted(nested_reasons.items())),
    }


def _difficulty_band(proposal_valid: bool, best_score: float) -> str:
    if not proposal_valid:
        return "protocol_blocked"
    if best_score <= 0.01:
        return "executable_floor"
    if best_score < 0.50:
        return "difficult"
    if best_score < 0.95:
        return "discriminating"
    return "near_ceiling"


def _summary_n(measurement: dict[str, Any], key: str) -> int:
    value = measurement.get(key)
    return int(value.get("n", 0)) if isinstance(value, dict) else 0


def _prior_measurement(maturity_row: dict[str, Any]) -> dict[str, Any]:
    measurement = maturity_row.get("model_measurement") or {}
    gain = measurement.get("post_first_valid_gain") or {}
    maximum = gain.get("maximum")
    return {
        "historical_model_family": "GPT-5.5 and repository calibration evidence",
        "normal_budget_one_count": _summary_n(measurement, "normal_budget_one"),
        "normal_budget_three_count": _summary_n(measurement, "normal_budget_three"),
        "selection_blind_budget_three_count": _summary_n(
            measurement, "selection_blind_budget_three"
        ),
        "maximum_matched_control_replicates": int(
            measurement.get("maximum_matched_control_replicates", 0) or 0
        ),
        "maximum_observed_post_first_valid_gain": maximum,
        "material_post_first_valid_gain_count_at_0_05": int(
            gain.get("material_gain_count", 0) or 0
        ),
        "has_normal_and_selection_blind_budget_three": bool(
            _summary_n(measurement, "normal_budget_three")
            and _summary_n(measurement, "selection_blind_budget_three")
        ),
        "warning": (
            "Historical measurements are offline context only; most are single-draw, "
            "not generation-seeded, and do not identify a feedback effect."
        ),
    }


def _science_profile(task: str, maturity_row: dict[str, Any]) -> dict[str, Any]:
    spec = find_task(task, include_uncertified=True)
    card_path = spec.task_dir / "TASK_CARD.yaml"
    card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
    required = (
        "scientific_question",
        "artifact",
        "oracle",
        "citations",
        "known_shortcuts",
        "review",
        "provenance",
        "lineage",
        "long_horizon",
    )
    missing = [key for key in required if not card.get(key)]
    if missing:
        raise ValueError("task card lacks required fields for %s: %s" % (task, missing))
    recorded_card = maturity_row.get("task_card") or {}
    if recorded_card.get("sha256") != _sha256(card_path):
        raise ValueError("task card differs from maturity evidence: %s" % task)
    oracle_type = str(maturity_row["oracle_type"])
    tools = TOOL_REQUIREMENTS.get(oracle_type)
    if tools is None:
        raise ValueError("unmapped scientific oracle type: %s" % oracle_type)
    citations = card.get("citations") or []
    if not isinstance(citations, list) or not citations:
        raise ValueError("task lacks scientific citations: %s" % task)
    gates = maturity_row.get("gates") or {}
    return {
        "discipline": spec.discipline,
        "logical_domain": spec.domain,
        "certification_status": maturity_row["certification_status"],
        "declared_difficulty": maturity_row["difficulty"],
        "scientific_question": card["scientific_question"],
        "required_artifact": card["artifact"],
        "oracle_type": oracle_type,
        "oracle_description": card["oracle"],
        "science_metric": maturity_row["science_metric"],
        "professional_knowledge_evidence": (
            "Success is evaluated on the named domain oracle and task-specific scientific "
            "metric, not only generic code execution."
        ),
        "scientific_tool_requirements": list(tools),
        "citation_count": len(citations),
        "citation_ids": [
            citation.get("id") if isinstance(citation, dict) else str(citation)
            for citation in citations
        ],
        "provenance_class": (card.get("provenance") or {}).get("class"),
        "domain_review_status": (card.get("review") or {}).get("domain"),
        "lineage_status": (card.get("lineage") or {}).get("status"),
        "long_horizon_status": (card.get("long_horizon") or {}).get("status"),
        "known_shortcuts_and_limits": card["known_shortcuts"],
        "internal_science_admission": bool(
            (gates.get("internal_science_admission") or {}).get("passed")
        ),
        "open_release_ready": bool(
            (gates.get("open_release_ready") or {}).get("passed")
        ),
        "externally_validated": bool(
            (gates.get("externally_validated") or {}).get("passed")
        ),
        "long_horizon_ready": bool(
            (gates.get("long_horizon_ready") or {}).get("passed")
        ),
        "task_card_schema_issues": recorded_card.get("schema_issues") or [],
    }


def _raw_run_artifacts(run: dict[str, Any]) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    run_dir = (
        ROOT
        / "runs/gpt56_science_census_2026-08-06_v1"
        / run["task"].replace("/", "__")
        / run["algorithm"]
        / run["feedback_mode"]
        / ("seed_%d" % int(run["seed"]))
    )
    trajectory_path = run_dir / "trajectory.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    if not trajectory_path.is_file() or not checkpoint_path.is_file():
        raise ValueError("raw census artifacts are missing for %s" % run["task"])
    snapshot = compact_trajectory_snapshot(trajectory_path, schema_version=2)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("raw trajectory differs from frozen report: %s" % run["task"])
    return (
        trajectory_path,
        load_trajectory(trajectory_path),
        json.loads(checkpoint_path.read_text(encoding="utf-8")),
    )


def _verify_prompt(
    task: str,
    events: list[dict[str, Any]],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    if len(events) != 2:
        raise ValueError("budget-one census trajectory must contain two events")
    candidates = {
        int(row["step"]): row for row in checkpoint.get("evaluated_candidates") or []
    }
    if set(candidates) != {0, 1}:
        raise ValueError("budget-one checkpoint candidate inventory is incomplete")
    for event in events:
        candidate = candidates[int(event["step"])]
        if candidate.get("sha256") != event.get("candidate_sha256"):
            raise ValueError("checkpoint candidate hash differs")
        if bool(candidate.get("valid")) != bool(event.get("valid")):
            raise ValueError("checkpoint candidate validity differs")
        if not math.isclose(
            float(candidate["score"]), float(event["score"]),
            rel_tol=1e-12, abs_tol=1e-12,
        ):
            raise ValueError("checkpoint candidate score differs")
    baseline, proposal = events
    metadata = proposal.get("algorithm_metadata") or {}
    if not (
        proposal.get("parent_sha256") == baseline.get("candidate_sha256")
        and metadata.get("prompt_source_step") == 0
        and metadata.get("feedback_released_through_step") == 0
        and metadata.get("selection_policy") == "online_incumbent"
    ):
        raise ValueError("budget-one parent lineage differs")
    visible = search_visible_metrics(baseline.get("metrics") or {})
    metric_keys = ",".join(sorted(visible))
    rendered = json.dumps(visible, indent=2)
    if metadata.get("prompt_metric_keys") != metric_keys:
        raise ValueError("prompt metric keys differ from closed allowlist")
    if metadata.get("prompt_metrics_sha256") != sha256_text(rendered):
        raise ValueError("prompt metric payload hash differs")
    spec = find_task(task, include_uncertified=True)
    prompt = _build_prompt(
        spec,
        str(candidates[0]["program"]),
        baseline.get("metrics") or {},
        proposal_slot=1,
        proposal_budget=1,
    )
    if metadata.get("prompt_sha256") != sha256_text(prompt):
        raise ValueError("reconstructed model prompt hash differs")
    if metadata.get("prompt_program_utf8_bytes") != len(
        str(candidates[0]["program"]).encode("utf-8")
    ):
        raise ValueError("prompt program byte count differs")
    return {
        "baseline_candidate_sha256": baseline["candidate_sha256"],
        "proposal_candidate_sha256": proposal["candidate_sha256"],
        "proposal_parent_sha256": proposal["parent_sha256"],
        "prompt_sha256": metadata["prompt_sha256"],
        "prompt_metric_keys": sorted(visible),
        "system_prompt_source_sha256": sha256_text(SYSTEM_PROMPT),
        "prompt_reconstruction_passed": True,
        "parent_lineage_passed": True,
    }


def _task_record(
    run: dict[str, Any], maturity_row: dict[str, Any]
) -> dict[str, Any]:
    trajectory_path, events, checkpoint = _raw_run_artifacts(run)
    baseline, proposal = events
    selected = _selected_event(events, float(run["best"]))
    prompt_audit = _verify_prompt(str(run["task"]), events, checkpoint)
    profile = _science_profile(str(run["task"]), maturity_row)
    proposal_valid = proposal.get("valid") is True
    best_score = float(run["best"])
    band = _difficulty_band(proposal_valid, best_score)
    evolution_candidate = bool(proposal_valid and 0.05 <= best_score < 0.95)
    return {
        "task": run["task"],
        "science_profile": profile,
        "gpt56_budget_one": {
            "replicate_identifier": int(run["seed"]),
            "baseline_score": float(run["baseline"]),
            "proposal_score": float(proposal["score"]),
            "proposal_valid": proposal_valid,
            "terminal_best_score": best_score,
            "selected_step": int(selected["step"]),
            "selected_candidate_sha256": selected["candidate_sha256"],
            "proposal_improves_baseline": bool(
                proposal_valid and float(proposal["score"]) > float(run["baseline"])
            ),
            "difficulty_band": band,
            "difficulty_interpretation": {
                "protocol_blocked": (
                    "No valid proposal; this is an engineering or contract hurdle and "
                    "does not count as demonstrated scientific difficulty."
                ),
                "executable_floor": (
                    "The proposal executes but terminal score is at most 0.01, retaining "
                    "clear scientific or optimization headroom."
                ),
                "difficult": (
                    "The executable proposal remains below 0.50 and supplies clean "
                    "one-step challenge evidence."
                ),
                "discriminating": (
                    "The executable proposal makes material progress while retaining "
                    "at least 0.05 nominal headroom."
                ),
                "near_ceiling": (
                    "The one-step proposal reaches at least 0.95; treat this task as an "
                    "on-ramp or harden its regime before model discrimination claims."
                ),
            }[band],
            "evolution_candidate": evolution_candidate,
            "evolution_candidate_rule": (
                "valid proposal and terminal best score in [0.05, 0.95)"
            ),
            "failure": _failure_diagnostic(proposal),
            "proposal_public_metrics": search_visible_metrics(
                proposal.get("metrics") or {}
            ),
            "proposal_sealed_scalar_metrics": _scalar_sealed_metrics(
                proposal.get("metrics") or {}
            ),
            "selected_sealed_scalar_metrics": _scalar_sealed_metrics(
                selected.get("metrics") or {}
            ),
            "oracle_calls": int(run["summary"]["oracle_calls"]),
            "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
            "wall_seconds": float(run["summary"]["wall_seconds"]),
            "trajectory_path": str(trajectory_path.relative_to(ROOT)),
            "trajectory_sha256": _sha256(trajectory_path),
            "prompt_and_lineage_audit": prompt_audit,
        },
        "prior_iterative_context": _prior_measurement(maturity_row),
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile needs values")
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _discipline_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["science_profile"]["discipline"]].append(record)
    result = {}
    for discipline, rows in sorted(groups.items()):
        valid = [row for row in rows if row["gpt56_budget_one"]["proposal_valid"]]
        bands = Counter(row["gpt56_budget_one"]["difficulty_band"] for row in rows)
        result[discipline] = {
            "task_count": len(rows),
            "valid_proposals": len(valid),
            "proposal_valid_rate": len(valid) / len(rows),
            "difficulty_band_counts": dict(sorted(bands.items())),
            "evolution_candidate_count": sum(
                row["gpt56_budget_one"]["evolution_candidate"] for row in rows
            ),
            "near_ceiling_count": bands.get("near_ceiling", 0),
        }
    return result


def analyze(
    report_path: Path = DEFAULT_REPORT,
    maturity_path: Path = DEFAULT_MATURITY,
    pilot_analysis_path: Path = DEFAULT_PILOT_ANALYSIS,
) -> dict[str, Any]:
    source = _load_trusted(report_path, EXPECTED_REPORT_SHA256, "census report")
    maturity = _load_trusted(
        maturity_path, EXPECTED_MATURITY_SHA256, "task maturity audit"
    )
    pilot = _load_trusted(
        pilot_analysis_path,
        EXPECTED_PILOT_ANALYSIS_SHA256,
        "GPT-5.6 pilot analysis",
    )
    config = source.get("config") or {}
    if not (
        len(config.get("tasks") or []) == 50
        and config.get("algorithms") == ["greedy_rewrite"]
        and config.get("feedback_modes") == ["normal"]
        and config.get("seeds") == [0]
        and config.get("budget") == 1
        and config.get("run_role") == "calibration"
        and config.get("block_workers") == 8
    ):
        raise ValueError("census execution design differs from preregistration")
    llm = config.get("llm") or {}
    if not (
        config.get("llm_condition_sha256") == EXPECTED_MODEL_CONDITION_SHA256
        and llm.get("model") == "gpt-5.6-sol"
        and llm.get("reasoning_effort") == "low"
        and llm.get("max_output_tokens") == 16000
        and llm.get("temperature") is None
        and llm.get("server_side_seed_control") is False
    ):
        raise ValueError("census model condition differs")
    prereg = config.get("preregistration") or {}
    cohort = config.get("cohort_manifest") or {}
    if not (
        prereg.get("sha256") == EXPECTED_PREREGISTRATION_SHA256
        and prereg.get("execution_contract_validated") is True
        and cohort.get("sha256") == EXPECTED_COHORT_SHA256
    ):
        raise ValueError("census preregistration or cohort binding differs")
    runs = source.get("runs") or []
    if len(runs) != 50 or any(run.get("error") for run in runs):
        raise ValueError("census must retain 50 successful outer cells")
    if (source.get("aggregate") or {}).get("successful_runs") != 50:
        raise ValueError("census aggregate does not contain 50 successful cells")
    if source.get("block_failures"):
        raise ValueError("census contains block worker failures")

    maturity_rows = {
        row["task"]: row
        for row in maturity.get("tasks") or []
        if row.get("certification_status") != "quarantined"
    }
    if set(maturity_rows) != set(config["tasks"]):
        raise ValueError("maturity and census admitted cohorts differ")
    run_by_task = {run["task"]: run for run in runs}
    if len(run_by_task) != 50 or set(run_by_task) != set(config["tasks"]):
        raise ValueError("census run task inventory differs")
    records = [
        _task_record(run_by_task[task], maturity_rows[task])
        for task in config["tasks"]
    ]

    bands = Counter(
        record["gpt56_budget_one"]["difficulty_band"] for record in records
    )
    failures = Counter(
        record["gpt56_budget_one"]["failure"]["failure_kind"]
        for record in records
        if record["gpt56_budget_one"]["failure"]["failure_kind"]
    )
    failure_classes = Counter(
        record["gpt56_budget_one"]["failure"]["failure_class"]
        for record in records
        if record["gpt56_budget_one"]["failure"]["failure_class"]
    )
    valid_records = [
        record for record in records
        if record["gpt56_budget_one"]["proposal_valid"]
    ]
    valid_scores = [
        record["gpt56_budget_one"]["terminal_best_score"]
        for record in valid_records
    ]
    evolution_candidates = [
        record for record in records
        if record["gpt56_budget_one"]["evolution_candidate"]
    ]
    near_ceiling = [
        record["task"] for record in records
        if record["gpt56_budget_one"]["difficulty_band"] == "near_ceiling"
    ]
    protocol_blocked = [
        record["task"] for record in records
        if record["gpt56_budget_one"]["difficulty_band"] == "protocol_blocked"
    ]
    clean_below_half = sum(score < 0.50 for score in valid_scores)
    occupied_executable_bands = [
        band for band in (
            "executable_floor", "difficult", "discriminating", "near_ceiling"
        ) if bands.get(band, 0)
    ]

    science_profiles = [record["science_profile"] for record in records]
    status_counts = Counter(profile["certification_status"] for profile in science_profiles)
    provenance_counts = Counter(profile["provenance_class"] for profile in science_profiles)
    difficulty_counts = Counter(profile["declared_difficulty"] for profile in science_profiles)
    oracle_counts = Counter(profile["oracle_type"] for profile in science_profiles)
    citation_count = sum(profile["citation_count"] for profile in science_profiles)
    internal_count = sum(profile["internal_science_admission"] for profile in science_profiles)
    open_release_count = sum(profile["open_release_ready"] for profile in science_profiles)
    external_count = sum(profile["externally_validated"] for profile in science_profiles)
    long_horizon_count = sum(profile["long_horizon_ready"] for profile in science_profiles)
    card_issue_count = sum(bool(profile["task_card_schema_issues"]) for profile in science_profiles)

    prior_both = sum(
        row["prior_iterative_context"]["has_normal_and_selection_blind_budget_three"]
        for row in evolution_candidates
    )
    prior_material_gain = sum(
        row["prior_iterative_context"]["material_post_first_valid_gain_count_at_0_05"] > 0
        for row in evolution_candidates
    )
    prior_matched_three = sum(
        row["prior_iterative_context"]["maximum_matched_control_replicates"] >= 3
        for row in evolution_candidates
    )
    pilot_differences = pilot["aggregate"]["normal_minus_selection_blind"]
    pilot_normal_wins = sum(value > 0 for value in pilot_differences.values())
    pilot_blind_wins = sum(value < 0 for value in pilot_differences.values())
    pilot_ties = sum(value == 0 for value in pilot_differences.values())

    gates = {
        "protocol_health": {
            "passed": bool(
                len(runs) == 50
                and source["aggregate"]["failed_runs"] == 0
                and source["aggregate"]["failed_attempts"] == 0
            ),
            "observed": "50/50 cells, 50/50 model calls, zero outer failures",
        },
        "scientific_scope": {
            "passed": bool(
                internal_count == 50
                and card_issue_count == 0
                and citation_count > 0
                and all(profile["scientific_tool_requirements"] for profile in science_profiles)
            ),
            "observed": {
                "internal_science_admission": internal_count,
                "valid_task_cards": 50 - card_issue_count,
                "scientific_citations": citation_count,
                "open_release_ready": open_release_count,
                "externally_validated": external_count,
                "long_horizon_ready": long_horizon_count,
            },
            "interpretation": (
                "Passes the repository's internal documentation/admission criterion only; "
                "zero tasks have completed independent external review or validation."
            ),
        },
        "execution_usability": {
            "passed": len(valid_records) / len(records) >= 0.60,
            "threshold": 0.60,
            "observed": len(valid_records) / len(records),
            "valid_proposals": len(valid_records),
        },
        "challenge": {
            "passed": clean_below_half >= 15,
            "threshold": 15,
            "observed": clean_below_half,
            "interpretation": (
                "Protocol-blocked tasks are excluded. The preregistered challenge gate "
                "fails because only 12 executable tasks are below 0.50."
            ),
        },
        "anti_saturation": {
            "passed": bands["near_ceiling"] / len(valid_records) <= 0.40,
            "threshold_maximum_fraction": 0.40,
            "observed_fraction": bands["near_ceiling"] / len(valid_records),
            "near_ceiling_tasks": bands["near_ceiling"],
            "interpretation": "Passes narrowly; 13 one-step near-ceiling tasks need harder regimes.",
        },
        "discrimination": {
            "passed": bool(
                len(occupied_executable_bands) >= 3
                and max(valid_scores) - min(valid_scores) >= 0.50
            ),
            "occupied_executable_bands": occupied_executable_bands,
            "score_range": max(valid_scores) - min(valid_scores),
        },
        "self_evolving_fit": {
            "passed": bool(evolution_candidates),
            "evolution_candidate_count": len(evolution_candidates),
            "positive_gpt56_online_feedback_signal": False,
            "interpretation": (
                "The census identifies iterative-study candidates but budget one cannot "
                "measure evolution. The separate four-task GPT-5.6 pilot has zero normal "
                "wins, two selection-blind wins and two ties, with no provider seed control."
            ),
        },
    }
    requirements_all_passed = all(
        gates[key]["passed"]
        for key in (
            "protocol_health", "scientific_scope", "execution_usability",
            "challenge", "anti_saturation", "discrimination",
        )
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "COMPLETE_INTERNAL_ADMISSION_CENSUS_SINGLE_UNSEEDED_PROVIDER_DRAW_"
            "NOT_POPULATION_MODEL_RANKING_FEEDBACK_CAUSAL_EXTERNAL_VALIDATION_"
            "RECURSIVE_SELF_IMPROVEMENT_OR_AUTONOMOUS_DISCOVERY"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": {
            "census_report": {
                "path": str(report_path.resolve().relative_to(ROOT)),
                "sha256": EXPECTED_REPORT_SHA256,
                "source_revision": source["source_provenance"]["git_revision"],
            },
            "task_maturity_audit": {
                "path": str(maturity_path.resolve().relative_to(ROOT)),
                "sha256": EXPECTED_MATURITY_SHA256,
            },
            "gpt56_pilot_analysis": {
                "path": str(pilot_analysis_path.resolve().relative_to(ROOT)),
                "sha256": EXPECTED_PILOT_ANALYSIS_SHA256,
            },
            "cohort_sha256": EXPECTED_COHORT_SHA256,
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
        },
        "design": {
            "census_task_count": 50,
            "certification_status_counts": dict(sorted(status_counts.items())),
            "excluded_quarantined_task_count": 9,
            "provider_model": "gpt-5.6-sol",
            "reasoning_effort": "low",
            "max_output_tokens": 16000,
            "server_side_seed_control": False,
            "proposal_budget": 1,
            "feedback_mode": "normal",
            "replicate_identifiers": [0],
        },
        "leakage_audit": {
            "passed": True,
            "same_algorithm_and_system_prompt_for_all_tasks": True,
            "all_proposal_parents_equal_their_task_baseline": True,
            "all_prompt_source_steps": [0],
            "closed_metric_allowlist": list(SEARCH_VISIBLE_KEYS),
            "actual_prompt_metric_key_sets": sorted({
                tuple(record["gpt56_budget_one"]["prompt_and_lineage_audit"][
                    "prompt_metric_keys"
                ])
                for record in records
            }),
            "prohibited_and_absent_from_forward_routing": [
                "broad physical discipline",
                "certification status",
                "cohort inclusion rationale",
                "task-card review and maturity labels",
                "historical GPT-5.5 or GPT-5.6 outcomes",
                "evaluator-only science, robustness and per-instance metrics",
                "ground truth and score files",
            ],
            "offline_only_fields": (
                "Discipline, certification, task cards, historical measurements, "
                "difficulty bands, failures and sealed metrics below were joined only "
                "after all 50 predictions completed."
            ),
            "verification": (
                "All 50 user prompts were reconstructed byte-for-byte from frozen source, "
                "baseline program and closed public metrics and matched recorded hashes."
            ),
        },
        "scientific_scope": {
            "task_count": 50,
            "declared_difficulty_counts": dict(sorted(difficulty_counts.items())),
            "oracle_type_counts": dict(sorted(oracle_counts.items())),
            "provenance_class_counts": dict(sorted(provenance_counts.items())),
            "citation_count": citation_count,
            "internal_science_admission_count": internal_count,
            "open_release_ready_count": open_release_count,
            "externally_validated_count": external_count,
            "long_horizon_ready_count": long_horizon_count,
            "interpretation": (
                "Every admitted task names a scientific question, executable artifact, "
                "domain oracle, scientific metric, tool family, citations and limitations. "
                "This is strong internal application structure, not independent expert or "
                "physical validation."
            ),
        },
        "aggregate": {
            "outer_cells_completed": 50,
            "provider_calls": 50,
            "outer_failure_count": 0,
            "valid_proposals": len(valid_records),
            "invalid_proposals": len(records) - len(valid_records),
            "proposal_valid_rate": len(valid_records) / len(records),
            "proposal_improvement_count": sum(
                record["gpt56_budget_one"]["proposal_improves_baseline"]
                for record in records
            ),
            "difficulty_band_counts": dict(sorted(bands.items())),
            "failure_kind_counts": dict(sorted(failures.items())),
            "failure_class_counts": dict(sorted(failure_classes.items())),
            "valid_score_distribution": {
                "count": len(valid_scores),
                "minimum": min(valid_scores),
                "quartile_25": _percentile(valid_scores, 0.25),
                "median": statistics.median(valid_scores),
                "quartile_75": _percentile(valid_scores, 0.75),
                "maximum": max(valid_scores),
                "warning": (
                    "Heterogeneous task scores are shown only as a distribution; their "
                    "arithmetic average is not treated as one scientific capability."
                ),
            },
            "discipline_summary": _discipline_summary(records),
        },
        "predeclared_descriptive_gates": gates,
        "self_evolving_assessment": {
            "budget_one_is_evolution_evidence": False,
            "evolution_candidate_rule": (
                "valid GPT-5.6 proposal and terminal best score in [0.05, 0.95)"
            ),
            "evolution_candidate_count": len(evolution_candidates),
            "evolution_candidate_tasks": [row["task"] for row in evolution_candidates],
            "candidates_with_historical_budget_three_and_selection_blind": prior_both,
            "candidates_with_historical_material_post_first_valid_gain": prior_material_gain,
            "candidates_with_at_least_three_historical_matched_controls": prior_matched_three,
            "gpt56_four_task_pilot": {
                "normal_wins": pilot_normal_wins,
                "selection_blind_wins": pilot_blind_wins,
                "ties": pilot_ties,
                "positive_online_feedback_signal": False,
                "provider_seed_control": False,
            },
            "rsi_relevance": (
                "These tasks can study system-level revision of executable scientist "
                "policies under sealed evaluation. Current evidence does not demonstrate "
                "persistent skill acquisition, weight-level learning, recursive self-"
                "improvement or autonomous scientific discovery."
            ),
        },
        "portfolio_disposition": {
            "benchmark_requirements_all_passed": requirements_all_passed,
            "recommended_use": (
                "Use as a mixed calibration portfolio, not as a uniformly hard GPT-5.6 "
                "benchmark or one-number leaderboard."
            ),
            "retain_for_iterative_controls": [row["task"] for row in evolution_candidates],
            "harden_or_reclassify_as_on_ramp": near_ceiling,
            "repair_candidate_execution_or_contract_path": protocol_blocked,
            "clean_executable_tasks_below_0_50": clean_below_half,
            "reason_requirements_not_all_passed": (
                "The preregistered challenge gate requires 15 executable tasks below 0.50; "
                "only 12 were observed."
            ) if not gates["challenge"]["passed"] else None,
        },
        "task_records": records,
        "limitations": [
            "Each task has one provider draw and the endpoint exposes no generation seed.",
            "Budget one measures one-step executable synthesis, not self-evolution.",
            "Fourteen invalid proposals are engineering outcomes, not clean scientific-difficulty evidence.",
            "Thirteen valid tasks are near ceiling at budget one and may be on-ramps rather than frontier challenges.",
            "Scores and sealed axes are task-specific and must not be averaged into a universal science score.",
            "All 50 pass internal admission, but zero are open-release ready, externally validated or long-horizon ready.",
            "Most worlds and equations are repository-visible; builder/calibrator independence and contamination risk remain unresolved.",
        ],
    }
    complete = bool(
        len(records) == 50
        and gates["protocol_health"]["passed"]
        and gates["scientific_scope"]["passed"]
        and all(
            record["gpt56_budget_one"]["prompt_and_lineage_audit"][
                "prompt_reconstruction_passed"
            ]
            for record in records
        )
    )
    finalize_report_trust(report, complete)
    return report


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    gates = report["predeclared_descriptive_gates"]
    disposition = report["portfolio_disposition"]
    records = report["task_records"]
    lines = [
        "# GPT-5.6 50-task science census",
        "",
        "This is a complete census of the 50 internally admitted tasks (7 certified and "
        "43 candidate), with one unseeded-provider, normal-feedback, budget-one draw per "
        "task. The nine quarantined tasks are excluded.",
        "",
        "## Verdict",
        "",
        "The portfolio has recognizable scientific applications, domain-specific oracles, "
        "professional knowledge and scientific-tool requirements, and it clearly separates "
        "task outcomes. It is **not yet a uniformly hard GPT-5.6 benchmark**: the "
        "preregistered challenge gate fails (12 executable tasks below 0.50 versus a threshold "
        "of 15), 13 valid tasks are near ceiling, and 14 tasks are blocked by candidate "
        "execution or submission failures.",
        "",
        "| Requirement | Verdict | Evidence |",
        "|---|---|---|",
        "| Scientific application | Internal pass | 50/50 name a scientific question, artifact, oracle and metric; 153 citations |",
        "| Professional knowledge / tools | Internal pass | 50/50 require mapped simulation, inference, optimization, signal, PDE, statistical or exact-algorithm tools |",
        "| Executable difficulty | Partial / gate fail | 12 valid tasks below 0.50; threshold 15 |",
        "| Discrimination | Pass | all four executable score bands occupied; range 1.0 |",
        "| Anti-saturation | Narrow pass | 13/36 valid tasks (36.1%) at or above 0.95; threshold at most 40% |",
        "| Self-evolving / RSI | Structurally suitable, not demonstrated | 15 iterative-study candidates; budget one is not evolution and the four-task pilot has no positive online-feedback signal |",
        "| External validity | Not passed | 0/50 externally validated, open-release ready or long-horizon ready |",
        "",
        "## Outcome distribution",
        "",
        "| Outcome | Tasks | Meaning |",
        "|---|---:|---|",
        "| Protocol blocked | %d | invalid proposal; excluded from scientific-difficulty count |" % aggregate["difficulty_band_counts"]["protocol_blocked"],
        "| Executable floor (<=0.01) | %d | executable but essentially no terminal progress |" % aggregate["difficulty_band_counts"]["executable_floor"],
        "| Difficult (0.01-0.50) | %d | clean one-step challenge |" % aggregate["difficulty_band_counts"]["difficult"],
        "| Discriminating (0.50-0.95) | %d | material progress with headroom |" % aggregate["difficulty_band_counts"]["discriminating"],
        "| Near ceiling (>=0.95) | %d | on-ramp or needs a harder regime |" % aggregate["difficulty_band_counts"]["near_ceiling"],
        "",
        "Proposal validity is %d/50 (%.1f%%). Candidate failures split into `%s`."
        % (
            aggregate["valid_proposals"],
            100.0 * aggregate["proposal_valid_rate"],
            json.dumps(aggregate["failure_class_counts"], sort_keys=True),
        ),
        "",
        "## Discipline summary",
        "",
        "| Discipline | Tasks | Valid | Evolution candidates | Near ceiling |",
        "|---|---:|---:|---:|---:|",
    ]
    for discipline, row in aggregate["discipline_summary"].items():
        lines.append(
            "| %s | %d | %d | %d | %d |"
            % (
                discipline,
                row["task_count"],
                row["valid_proposals"],
                row["evolution_candidate_count"],
                row["near_ceiling_count"],
            )
        )
    lines.extend([
        "",
        "## Self-evolving study pool",
        "",
        "The preregistered rule nominates 15 tasks with a valid score in `[0.05, 0.95)`. "
        "This is a follow-up pool, not evidence that feedback helps. Historical GPT-5.5 "
        "budget-three and selection-blind results exist for %d/15, material within-normal "
        "post-first-valid gains for %d/15, and at least three matched controls for only %d/15."
        % (
            report["self_evolving_assessment"][
                "candidates_with_historical_budget_three_and_selection_blind"
            ],
            report["self_evolving_assessment"][
                "candidates_with_historical_material_post_first_valid_gain"
            ],
            report["self_evolving_assessment"][
                "candidates_with_at_least_three_historical_matched_controls"
            ],
        ),
        "",
        "| Task | GPT-5.6 best | Prior b3 / blind | Prior material later gain |",
        "|---|---:|---:|---|",
    ])
    for record in records:
        result = record["gpt56_budget_one"]
        if not result["evolution_candidate"]:
            continue
        prior = record["prior_iterative_context"]
        lines.append(
            "| `%s` | %.6f | %d / %d | %s |"
            % (
                record["task"],
                result["terminal_best_score"],
                prior["normal_budget_three_count"],
                prior["selection_blind_budget_three_count"],
                "yes" if prior["material_post_first_valid_gain_count_at_0_05"] else "no",
            )
        )
    lines.extend([
        "",
        "The separate four-task GPT-5.6 budget-three pilot records zero normal wins, two "
        "selection-blind wins and two ties. With one draw and no provider seed, that is no "
        "positive feedback signal and also not a causal null result.",
        "",
        "## Protocol-blocked tasks",
        "",
        "| Task | Failure class | Failure kind |",
        "|---|---|---|",
    ])
    for record in records:
        result = record["gpt56_budget_one"]
        if result["difficulty_band"] != "protocol_blocked":
            continue
        failure = result["failure"]
        lines.append(
            "| `%s` | %s | `%s` |"
            % (record["task"], failure["failure_class"], failure["failure_kind"])
        )
    lines.extend([
        "",
        "## All task results and scientific basis",
        "",
        "| Task | Scientific outcome | Tool family | Valid | Best | Disposition |",
        "|---|---|---|:---:|---:|---|",
    ])
    for record in records:
        profile = record["science_profile"]
        result = record["gpt56_budget_one"]
        tools = ", ".join(profile["scientific_tool_requirements"])
        lines.append(
            "| `%s` | %s | %s | %s | %.6f | %s |"
            % (
                record["task"],
                _escape(profile["science_metric"]),
                _escape(tools),
                "yes" if result["proposal_valid"] else "no",
                result["terminal_best_score"],
                result["difficulty_band"].replace("_", " "),
            )
        )
    lines.extend([
        "",
        "## Leakage, scope and next use",
        "",
        "All 50 prompts were reconstructed exactly. The same solver and system prompt were "
        "used throughout; every proposal saw only its public task text, baseline program, "
        "proposal slot and closed feasibility/selection metric allowlist. Discipline, "
        "certification, historical outcomes and sealed science axes were joined offline.",
        "",
        "Recommended use: %s" % disposition["recommended_use"],
        "",
        "Before a strong RSI claim, run preregistered matched normal versus frozen-parent "
        "controls over the 15-task pool, add provider generation control or sufficient "
        "replication, repair the 14 blocked paths, harden the 13 near-ceiling regimes, and "
        "complete independent domain and long-horizon review.",
        "",
        "Raw census SHA-256: `%s`." % report["inputs"]["census_report"]["sha256"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--maturity", type=Path, default=DEFAULT_MATURITY)
    parser.add_argument(
        "--pilot-analysis", type=Path, default=DEFAULT_PILOT_ANALYSIS
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = analyze(args.report, args.maturity, args.pilot_analysis)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
