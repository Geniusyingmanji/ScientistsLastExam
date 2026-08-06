#!/usr/bin/env python3
"""Validate and summarize the preregistered GPT-5.6 science pilot.

This is an offline analysis.  It reads evaluator-only metrics only after all
model proposals have been generated, and it never feeds them back into search.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.evolve import SYSTEM_PROMPT, _build_prompt  # noqa: E402
from frontier_science.metric_visibility import (  # noqa: E402
    SEARCH_VISIBLE_KEYS,
    search_visible_metrics,
)
from frontier_science.protocol import (  # noqa: E402
    compact_trajectory_snapshot,
    load_trajectory,
    sha256_text,
)
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


DEFAULT_REPORT = ROOT / "experiments/gpt56_science_pilot_2026-08-06_v1.json"
EXPECTED_REPORT_SHA256 = (
    "ccb005a14f566e75e7d3924d3756a763d4d3ba62fad687e5c48cf3ab6c437916"
)
EXPECTED_COHORT_SHA256 = (
    "f0e2df25bb2a907f12f9f9df0d0cf0b715a08da19f423df4b076030ac0b6c67e"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "f1fbb79242f863468054e4a45e14a4e838b7db9e821e1b4f7aa5c108ccf02285"
)
EXPECTED_TASKS = (
    "DynamicalSystems/ActiveLawDiscovery",
    "Optics/DiffractionGratingDesign",
    "MolecularDynamics/ForceFieldCalibration",
    "Sensors/QuartzCrystalMicrobalanceLab",
)
EXPECTED_PROMPT_METRIC_KEYS = (
    "combined_score,feasibility_rate,raw_score,valid"
)

HEADLINE_METRICS: dict[str, tuple[str, ...]] = {
    "DynamicalSystems/ActiveLawDiscovery": (
        "combined_score",
        "mechanism_score",
        "development_prediction_score",
        "validation_prediction_score",
        "robustness_score",
        "development_false_discoveries",
        "validation_false_discoveries",
        "development_correct_abstentions",
        "validation_correct_abstentions",
        "feasibility_rate",
    ),
    "Optics/DiffractionGratingDesign": (
        "combined_score",
        "development_mean_target_efficiency",
        "development_minimum_target_efficiency",
        "heldout_policy_score",
        "heldout_mean_target_efficiency",
        "robustness_score",
        "heldout_robustness_score",
        "development_shift_geometry_feasibility",
        "heldout_shift_geometry_feasibility",
        "feasibility_rate",
    ),
    "MolecularDynamics/ForceFieldCalibration": (
        "combined_score",
        "candidate_instance_valid_rate",
        "development_lineage_score",
        "development_acquisition_score",
        "development_hypothesis_score",
        "development_model_selection_score",
        "development_parameter_score",
        "development_prediction_score",
        "development_virial_score",
        "development_supported_claim_coverage",
        "development_unsupported_refusal_rate",
        "heldout_policy_score",
        "robustness_score",
        "heldout_robustness_score",
        "feasibility_rate",
    ),
    "Sensors/QuartzCrystalMicrobalanceLab": (
        "combined_score",
        "candidate_instance_valid_rate",
        "development_calibration_score",
        "development_extraction_score",
        "development_mechanism_score",
        "development_prediction_score",
        "development_decision_score",
        "development_fault_diagnosis_accuracy",
        "development_supported_claim_coverage",
        "development_unsupported_refusal_rate",
        "heldout_policy_score",
        "robustness_score",
        "heldout_robustness_score",
        "feasibility_rate",
    ),
}

SCIENCE_PROFILES: dict[str, dict[str, Any]] = {
    "DynamicalSystems/ActiveLawDiscovery": {
        "scientific_application": (
            "Active recovery of controlled governing equations with explicit null and "
            "out-of-library refusal cases."
        ),
        "professional_knowledge": (
            "Sparse system identification, controlled ODEs, experimental design, "
            "stability, extrapolative rollout and model-inadequacy testing."
        ),
        "scientific_tools": (
            "Numerical integration, sparse regression, conditioning-aware experiment "
            "selection and validation rollouts."
        ),
        "pilot_interpretation": (
            "Scientifically substantive, but one open-loop draw reached 0.997892. "
            "The task shows a budget-three saturation risk for this model even though "
            "the normal selected artifact retained misspecification false discoveries."
        ),
        "difficulty_evidence": "mixed_near_ceiling_in_one_condition",
        "execution_confound": "low",
    },
    "Optics/DiffractionGratingDesign": {
        "scientific_application": (
            "Constrained multilayer diffraction-grating design evaluated by a "
            "Fourier-modal Maxwell solver and fabrication/material shifts."
        ),
        "professional_knowledge": (
            "RCWA, diffraction orders, TE/TM balance, optical constraints, transfer "
            "and fabrication robustness."
        ),
        "scientific_tools": (
            "Electromagnetic simulation and constrained, nonconvex geometry optimization."
        ),
        "pilot_interpretation": (
            "All proposals executed, while scores ranged from 0.007664 to 0.661339 "
            "and selected held-out robustness ranged from zero to 0.737597. This is "
            "direct scientific-design difficulty rather than a code-validity floor."
        ),
        "difficulty_evidence": "clear_non_saturated_scientific_headroom",
        "execution_confound": "low",
    },
    "MolecularDynamics/ForceFieldCalibration": {
        "scientific_application": (
            "Active discrimination of pair-potential hypotheses with uncertainty, "
            "force prediction, virial inference and calibrated refusal."
        ),
        "professional_knowledge": (
            "Mie/Morse potentials, force matching, nonlinear inference, uncertainty, "
            "model selection, virial integration and misspecification."
        ),
        "scientific_tools": (
            "Active querying, weighted nonlinear fitting, covariance intervals, "
            "hypothesis management and numerical quadrature."
        ),
        "pilot_interpretation": (
            "The contract is scientifically rich, but all six proposals were invalid "
            "before a scientifically scorable artifact was obtained. The pilot measures "
            "an execution/protocol hurdle here, not resolved force-field reasoning."
        ),
        "difficulty_evidence": "unresolved_due_to_execution_hurdle",
        "execution_confound": "dominant",
    },
    "Sensors/QuartzCrystalMicrobalanceLab": {
        "scientific_application": (
            "Raw complex-I/Q QCM calibration, resonance extraction, film inference, "
            "fault diagnosis and deposition stop control."
        ),
        "professional_knowledge": (
            "Complex affine calibration, BVD resonance fitting, Sauerbrey physics, "
            "uncertainty, overtone checks and instrument/physics fault separation."
        ),
        "scientific_tools": (
            "Complex signal calibration, nonlinear spectral fitting, robust regression "
            "and diagnostic decision logic."
        ),
        "pilot_interpretation": (
            "Four proposals were executable yet all retained zero calibration, extraction, "
            "mechanism, prediction and decision score; two more failed submission validity. "
            "This supplies scientific-pipeline difficulty evidence with a secondary "
            "protocol confound."
        ),
        "difficulty_evidence": "clear_zero_science_score_among_executable_proposals",
        "execution_confound": "secondary",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selected_event(events: list[dict[str, Any]], expected_best: float) -> dict[str, Any]:
    valid = [event for event in events if event.get("valid") is True]
    if not valid:
        raise ValueError("trajectory contains no valid event")
    selected = max(valid, key=lambda event: (float(event["score"]), -int(event["step"])))
    if not math.isclose(
        float(selected["score"]), float(expected_best), rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("selected event disagrees with run best")
    return selected


def _failure_kind(event: dict[str, Any]) -> str | None:
    metrics = event.get("metrics") or {}
    explicit = metrics.get("candidate_failure_kind")
    if isinstance(explicit, str) and explicit:
        return explicit
    error = event.get("error") or metrics.get("error_message")
    if isinstance(error, str) and error:
        marker = "candidate invalid: "
        return error.split(marker, 1)[1] if marker in error else error
    nested = []
    for field in ("per_world", "per_instance"):
        rows = metrics.get(field) or []
        if isinstance(rows, list):
            nested.extend(
                row.get("failure_kind")
                for row in rows
                if isinstance(row, dict) and row.get("failure_kind")
            )
    kinds = sorted(set(str(value) for value in nested))
    if len(kinds) == 1:
        return kinds[0]
    if kinds:
        return "mixed:" + "+".join(kinds)
    return None


def _post_first_valid(events: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        event for event in events
        if int(event.get("step", 0)) >= 1 and event.get("valid") is True
    ]
    if not valid:
        return {
            "first_valid_step": None,
            "first_valid_score": None,
            "later_best_score": None,
            "later_gain": None,
            "estimable": False,
        }
    first = valid[0]
    later = valid[1:]
    later_best = max((float(event["score"]) for event in later), default=None)
    return {
        "first_valid_step": int(first["step"]),
        "first_valid_score": float(first["score"]),
        "later_best_score": later_best,
        "later_gain": (
            later_best - float(first["score"]) if later_best is not None else None
        ),
        "estimable": bool(later),
    }


def _verify_prompt_and_lineage(
    task: str,
    mode: str,
    events: list[dict[str, Any]],
    checkpoint: dict[str, Any],
    budget: int,
) -> dict[str, Any]:
    spec = find_task(task, include_uncertified=True)
    candidates = {
        int(row["step"]): row
        for row in checkpoint.get("evaluated_candidates") or []
    }
    if set(candidates) != set(range(budget + 1)):
        raise ValueError("checkpoint candidate inventory is incomplete")
    event_by_step = {int(event["step"]): event for event in events}
    baseline_hash = events[0]["candidate_sha256"]
    observed_metric_keys = set()
    prompt_hashes = []
    for event in events:
        step = int(event["step"])
        candidate = candidates[step]
        if candidate.get("sha256") != event.get("candidate_sha256"):
            raise ValueError("checkpoint candidate hash differs from trajectory")
        if bool(candidate.get("valid")) != bool(event.get("valid")):
            raise ValueError("checkpoint candidate validity differs from trajectory")
        if not math.isclose(
            float(candidate["score"]), float(event["score"]),
            rel_tol=1e-12, abs_tol=1e-12,
        ):
            raise ValueError("checkpoint candidate score differs from trajectory")
        if step == 0:
            continue
        metadata = event.get("algorithm_metadata") or {}
        source_step = int(metadata.get("prompt_source_step", -1))
        if mode == "selection_blind":
            if source_step != 0 or event.get("parent_sha256") != baseline_hash:
                raise ValueError("selection_blind proposal is not frozen at baseline")
            if metadata.get("selection_policy") != "offline_best_of_open_loop_batch":
                raise ValueError("selection_blind selection metadata is invalid")
        elif mode == "normal":
            if metadata.get("selection_policy") != "online_incumbent":
                raise ValueError("normal selection metadata is invalid")
            if source_step < 0 or source_step >= step:
                raise ValueError("normal prompt source step is invalid")
        else:
            raise ValueError("unexpected feedback mode")
        source_event = event_by_step[source_step]
        source_candidate = candidates[source_step]
        if event.get("parent_sha256") != source_event.get("candidate_sha256"):
            raise ValueError("proposal parent does not match its prompt source event")
        visible = search_visible_metrics(source_event.get("metrics") or {})
        metric_keys = ",".join(sorted(visible))
        if metadata.get("prompt_metric_keys") != metric_keys:
            raise ValueError("recorded prompt metric keys differ from closed allowlist")
        if metric_keys != EXPECTED_PROMPT_METRIC_KEYS:
            raise ValueError("pilot prompt metric key set differs from preregistration")
        observed_metric_keys.update(visible)
        rendered = json.dumps(visible, indent=2)
        if metadata.get("prompt_metrics_sha256") != sha256_text(rendered):
            raise ValueError("prompt metric payload hash differs")
        prompt = _build_prompt(
            spec,
            str(source_candidate["program"]),
            source_event.get("metrics") or {},
            proposal_slot=step,
            proposal_budget=budget,
        )
        if metadata.get("prompt_sha256") != sha256_text(prompt):
            raise ValueError("reconstructed model prompt hash differs")
        if metadata.get("prompt_program_utf8_bytes") != len(
            str(source_candidate["program"]).encode("utf-8")
        ):
            raise ValueError("prompt program byte count differs")
        prompt_hashes.append(metadata["prompt_sha256"])
    return {
        "baseline_candidate_sha256": baseline_hash,
        "proposal_prompt_hashes": prompt_hashes,
        "prompt_metric_keys": sorted(observed_metric_keys),
        "system_prompt_sha256": sha256_text(SYSTEM_PROMPT),
        "prompt_reconstruction_passed": True,
        "parent_lineage_passed": True,
    }


def _load_raw_run(run: dict[str, Any]) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    task_dir = run["task"].replace("/", "__")
    run_dir = (
        ROOT
        / "runs/gpt56_science_pilot_2026-08-06_v1"
        / task_dir
        / run["algorithm"]
        / run["feedback_mode"]
        / ("seed_%d" % int(run["seed"]))
    )
    trajectory_path = run_dir / "trajectory.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    if not trajectory_path.is_file() or not checkpoint_path.is_file():
        raise ValueError("raw pilot artifacts are missing for %s" % run["task"])
    snapshot = compact_trajectory_snapshot(trajectory_path, schema_version=2)
    if snapshot != run.get("trajectory_snapshot"):
        raise ValueError("raw trajectory differs from frozen report snapshot")
    events = load_trajectory(trajectory_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return trajectory_path, events, checkpoint


def _run_record(run: dict[str, Any], budget: int) -> dict[str, Any]:
    trajectory_path, events, checkpoint = _load_raw_run(run)
    selected = _selected_event(events, float(run["best"]))
    selected_metrics = selected.get("metrics") or {}
    task = str(run["task"])
    missing = [key for key in HEADLINE_METRICS[task] if key not in selected_metrics]
    if missing:
        raise ValueError("selected event lacks science metrics: %s" % ", ".join(missing))
    proposals = [event for event in events if int(event["step"]) >= 1]
    failure_counts = Counter(
        kind for kind in (_failure_kind(event) for event in proposals) if kind
    )
    lineage = _verify_prompt_and_lineage(
        task, str(run["feedback_mode"]), events, checkpoint, budget
    )
    sealed = {
        key: value
        for key, value in selected_metrics.items()
        if key not in SEARCH_VISIBLE_KEYS
    }
    return {
        "task": task,
        "feedback_mode": run["feedback_mode"],
        "replicate_identifier": int(run["seed"]),
        "baseline_score": float(run["baseline"]),
        "best_score": float(run["best"]),
        "selected_step": int(selected["step"]),
        "selected_candidate_sha256": selected["candidate_sha256"],
        "proposal_scores": [float(event["score"]) for event in proposals],
        "proposal_validity": [bool(event["valid"]) for event in proposals],
        "proposal_count": len(proposals),
        "valid_proposal_count": sum(event.get("valid") is True for event in proposals),
        "proposal_valid_rate": (
            sum(event.get("valid") is True for event in proposals) / len(proposals)
        ),
        "failure_kind_counts": dict(sorted(failure_counts.items())),
        "first_valid_and_later_gain": _post_first_valid(events),
        "best_so_far_auc": float(run["summary"]["best_so_far_auc"]),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "wall_seconds": float(run["summary"]["wall_seconds"]),
        "trajectory": {
            "path": str(trajectory_path.relative_to(ROOT)),
            "sha256": _sha256(trajectory_path),
        },
        "lineage_and_prompt_audit": lineage,
        "selected_headline_metrics": {
            key: selected_metrics[key] for key in HEADLINE_METRICS[task]
        },
        "selected_sealed_science_metrics": sealed,
    }


def _task_summaries(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for task in EXPECTED_TASKS:
        rows = {row["feedback_mode"]: row for row in records if row["task"] == task}
        if set(rows) != {"normal", "selection_blind"}:
            raise ValueError("task lacks both pilot conditions: %s" % task)
        normal = rows["normal"]
        blind = rows["selection_blind"]
        total_valid = normal["valid_proposal_count"] + blind["valid_proposal_count"]
        total_proposals = normal["proposal_count"] + blind["proposal_count"]
        profile = dict(SCIENCE_PROFILES[task])
        profile.update({
            "normal_best_score": normal["best_score"],
            "selection_blind_best_score": blind["best_score"],
            "normal_minus_selection_blind": (
                normal["best_score"] - blind["best_score"]
            ),
            "best_across_conditions": max(normal["best_score"], blind["best_score"]),
            "proposal_valid_rate": total_valid / total_proposals,
            "valid_proposals": total_valid,
            "proposal_count": total_proposals,
            "normal_post_first_valid_gain": normal[
                "first_valid_and_later_gain"
            ]["later_gain"],
            "selection_blind_post_first_valid_batch_gain": blind[
                "first_valid_and_later_gain"
            ]["later_gain"],
            "self_evolving_interpretation": (
                "The task structurally permits iterative program revision, but this single "
                "unseeded-provider pair cannot identify a feedback effect. A gain inside "
                "selection_blind is open-loop batch diversity, not self-evolution."
            ),
        })
        result[task] = profile
    return result


def analyze(report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    report_path = report_path.resolve()
    if _sha256(report_path) != EXPECTED_REPORT_SHA256:
        raise ValueError("pilot report hash differs from frozen result")
    source = json.loads(report_path.read_text(encoding="utf-8"))
    if not (
        source.get("trusted_evidence") is True
        and source.get("execution_passed") is True
        and source.get("passed") is True
        and source.get("source_provenance", {}).get("source_tree_dirty") is False
    ):
        raise ValueError("pilot source report is not trusted clean evidence")
    config = source.get("config") or {}
    expected_config = {
        "tasks": list(EXPECTED_TASKS),
        "algorithms": ["greedy_rewrite"],
        "feedback_modes": ["normal", "selection_blind"],
        "seeds": [0],
        "budget": 3,
        "run_role": "calibration",
    }
    for key, value in expected_config.items():
        if config.get(key) != value:
            raise ValueError("pilot config mismatch for %s" % key)
    llm = config.get("llm") or {}
    if not (
        llm.get("model") == "gpt-5.6-sol"
        and llm.get("reasoning_effort") == "low"
        and llm.get("max_output_tokens") == 16000
        and llm.get("server_side_seed_control") is False
    ):
        raise ValueError("pilot model condition differs")
    prereg = config.get("preregistration") or {}
    cohort = config.get("cohort_manifest") or {}
    if prereg.get("sha256") != EXPECTED_PREREGISTRATION_SHA256:
        raise ValueError("pilot preregistration binding differs")
    if cohort.get("sha256") != EXPECTED_COHORT_SHA256:
        raise ValueError("pilot cohort binding differs")
    runs = source.get("runs") or []
    if len(runs) != 8 or any(run.get("error") for run in runs):
        raise ValueError("pilot must retain eight successful outer run cells")
    keys = [(run["task"], run["feedback_mode"], int(run["seed"])) for run in runs]
    if len(set(keys)) != 8:
        raise ValueError("pilot contains duplicate run cells")
    records = [_run_record(run, budget=3) for run in runs]
    records.sort(key=lambda row: (EXPECTED_TASKS.index(row["task"]), row["feedback_mode"]))
    tasks = _task_summaries(records)

    proposal_count = sum(row["proposal_count"] for row in records)
    valid_proposals = sum(row["valid_proposal_count"] for row in records)
    failures = Counter()
    for row in records:
        failures.update(row["failure_kind_counts"])
    task_bests = [tasks[task]["best_across_conditions"] for task in EXPECTED_TASKS]
    score_bands = sorted(set(min(9, int(max(0.0, score) * 10)) for score in task_bests))
    normal_material_gains = [
        tasks[task]["normal_post_first_valid_gain"]
        for task in EXPECTED_TASKS
        if tasks[task]["normal_post_first_valid_gain"] is not None
    ]
    gates = {
        "protocol_health": {
            "passed": bool(
                source.get("aggregate", {}).get("successful_runs") == 8
                and source.get("aggregate", {}).get("failed_runs") == 0
                and proposal_count == 24
            ),
            "evidence": "8/8 cells and 24/24 scheduled proposal events completed.",
        },
        "challenge": {
            "passed": bool(
                sum(score < 0.95 for score in task_bests) >= 2
                and any(score < 0.50 for score in task_bests)
                and tasks["Sensors/QuartzCrystalMicrobalanceLab"]["valid_proposals"] > 0
            ),
            "evidence": (
                "Three task-level maxima are below 0.95; ForceField and QCM are below "
                "0.50, and QCM retains four executable zero-scoring proposals."
            ),
        },
        "discrimination": {
            "passed": bool(
                max(task_bests) - min(task_bests) >= 0.10
                and (
                    len(score_bands) >= 2
                    or max(tasks[task]["proposal_valid_rate"] for task in EXPECTED_TASKS)
                    - min(tasks[task]["proposal_valid_rate"] for task in EXPECTED_TASKS)
                    >= 0.25
                )
            ),
            "score_range": max(task_bests) - min(task_bests),
            "occupied_tenth_bands": score_bands,
            "proposal_validity_range": (
                max(tasks[task]["proposal_valid_rate"] for task in EXPECTED_TASKS)
                - min(tasks[task]["proposal_valid_rate"] for task in EXPECTED_TASKS)
            ),
        },
        "short_horizon_self_evolution_signal": {
            "passed": False,
            "evidence": (
                "Normal feedback loses to selection-blind on the two tasks with positive "
                "scores and ties on the other two. No normal run has a post-first-valid "
                "gain at or above the preregistered descriptive 0.05 materiality scale."
            ),
            "normal_material_gain_count_at_0_05": sum(
                gain >= 0.05 for gain in normal_material_gains
            ),
            "interpretation": (
                "No evidence that short-horizon online feedback outperforms open-loop "
                "best-of-batch generation; n=1 and absent provider seed control also "
                "preclude a causal null claim."
            ),
        },
        "anti_saturation": {
            "passed": sum(score >= 0.95 for score in task_bests) <= 2,
            "task_count_at_or_above_0_95": sum(score >= 0.95 for score in task_bests),
        },
    }
    all_gates_except_signal = all(
        value["passed"] for key, value in gates.items()
        if key != "short_horizon_self_evolution_signal"
    )
    derived: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "FOUR_TASK_SINGLE_IDENTIFIER_GPT56_CALIBRATION_NOT_POPULATION_"
            "PERFORMANCE_FEEDBACK_CAUSAL_EXTERNAL_VALIDATION_OR_AUTONOMOUS_DISCOVERY"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": {
            "pilot_report": {
                "path": str(report_path.relative_to(ROOT)),
                "sha256": _sha256(report_path),
                "source_revision": source["source_provenance"]["git_revision"],
            },
            "cohort_sha256": EXPECTED_COHORT_SHA256,
            "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
        },
        "design": {
            "tasks": list(EXPECTED_TASKS),
            "conditions": ["normal", "selection_blind"],
            "replicate_identifiers": [0],
            "proposal_budget": 3,
            "provider_model": "gpt-5.6-sol",
            "provider_reasoning_effort": "low",
            "server_side_seed_control": False,
            "paired_difference_direction": "normal_minus_selection_blind",
        },
        "leakage_audit": {
            "passed": True,
            "runtime_inputs": [
                "logical task id and Task.md",
                "public constraints",
                "current parent program",
                "preregistered proposal slot",
                "closed allowlist of feasibility/selection metrics",
            ],
            "closed_metric_allowlist": list(SEARCH_VISIBLE_KEYS),
            "actual_prompt_metric_keys": EXPECTED_PROMPT_METRIC_KEYS.split(","),
            "prohibited_and_absent": [
                "broad physical discipline",
                "certification status",
                "task-card review labels",
                "historical GPT-5.5 outcomes",
                "evaluator-only validation/mechanism/robustness/per-world metrics",
                "ground truth and score files",
            ],
            "verification": (
                "All 24 proposal prompts were reconstructed from the frozen source, "
                "parent program and allowlisted metrics and matched their recorded SHA-256. "
                "All selection-blind parents and prompt-source steps remained at baseline."
            ),
        },
        "run_records": records,
        "task_assessment": tasks,
        "aggregate": {
            "run_cells": len(records),
            "provider_calls": proposal_count,
            "proposal_count": proposal_count,
            "valid_proposals": valid_proposals,
            "proposal_valid_rate": valid_proposals / proposal_count,
            "failure_kind_counts": dict(sorted(failures.items())),
            "task_level_best_scores": {
                task: tasks[task]["best_across_conditions"] for task in EXPECTED_TASKS
            },
            "normal_minus_selection_blind": {
                task: tasks[task]["normal_minus_selection_blind"]
                for task in EXPECTED_TASKS
            },
        },
        "predeclared_descriptive_gates": gates,
        "overall_assessment": {
            "scientific_application_coverage": "4/4 recognizable scientific workflows",
            "professional_knowledge_and_tools_coverage": (
                "4/4 require task-specific equations, inference or simulation tools"
            ),
            "difficulty_and_discrimination": (
                "Pilot passes challenge, discrimination and anti-saturation gates, but "
                "ForceField is execution-confounded and ActiveLaw has a near-ceiling draw."
            ),
            "self_evolving_fit": (
                "The tasks can measure iterative artifact revision, but this pilot supplies "
                "no positive evidence that online feedback beats frozen-parent generation."
            ),
            "rsi_relevance": (
                "The benchmark is relevant to system-level self-improvement of executable "
                "scientist policies under sealed evaluation. It does not yet demonstrate "
                "weight-level self-improvement, persistent skill acquisition, recursive "
                "self-improvement or autonomous scientific discovery."
            ),
            "pilot_quality_gates_passed_excluding_positive_self_evolution_signal": (
                all_gates_except_signal
            ),
        },
        "limitations": [
            "Only four deliberately selected tasks were tested; this is not the 50-task cohort.",
            "Each condition has one local identifier and the provider exposes no generation seed.",
            "Scores from heterogeneous scientific tasks are not averaged into one model score.",
            "Normal and selection-blind token use is not matched.",
            "A low score is not automatically evidence of benchmark quality; proposal validity and science axes are reported separately.",
            "Task generators and equations are repository-visible and external domain review remains pending.",
        ],
    }
    complete = bool(
        len(records) == 8
        and proposal_count == 24
        and all(
            row["lineage_and_prompt_audit"]["prompt_reconstruction_passed"]
            for row in records
        )
        and all_gates_except_signal
    )
    finalize_report_trust(derived, complete)
    return derived


def render_markdown(report: dict[str, Any]) -> str:
    tasks = report["task_assessment"]
    lines = [
        "# GPT-5.6 science pilot analysis",
        "",
        "This is a four-task, single-identifier calibration, not a 50-task model ranking, "
        "causal feedback study, external validation, or autonomous-discovery result.",
        "",
        "## Outcome",
        "",
        "The pilot passes its protocol-health, challenge, discrimination and anti-saturation "
        "gates. It does **not** show that short-horizon online feedback outperforms "
        "frozen-parent best-of-batch generation.",
        "",
        "| Task | normal best | blind best | valid proposals | diagnosis |",
        "|---|---:|---:|---:|---|",
    ]
    for task in EXPECTED_TASKS:
        row = tasks[task]
        lines.append(
            "| `%s` | %.6f | %.6f | %d/%d | %s |"
            % (
                task,
                row["normal_best_score"],
                row["selection_blind_best_score"],
                row["valid_proposals"],
                row["proposal_count"],
                row["difficulty_evidence"].replace("_", " "),
            )
        )
    aggregate = report["aggregate"]
    lines.extend([
        "",
        "Across 24 proposals, %d were valid (%.1f%%). Failure kinds were `%s`."
        % (
            aggregate["valid_proposals"],
            100.0 * aggregate["proposal_valid_rate"],
            json.dumps(aggregate["failure_kind_counts"], sort_keys=True),
        ),
        "",
        "## Interpretation",
        "",
        "- ActiveLaw is scientifically meaningful but has a near-ceiling open-loop draw; "
        "its normal selected artifact still makes misspecification false discoveries.",
        "",
        "- Diffraction is the cleanest scientific-difficulty case: every proposal executes, "
        "yet nominal and sealed robustness outcomes remain widely separated.",
        "",
        "- ForceField is dominated by executable-contract failures, so zero cannot be read "
        "as resolved evidence about force-field reasoning difficulty.",
        "",
        "- QCM retains four executable proposals with zero calibration/extraction/mechanism/"
        "prediction/decision score, which is a substantive scientific-pipeline failure; two "
        "additional proposals are invalid submissions.",
        "",
        "The tasks fit an RSI/self-evolving study at the level of revising executable "
        "scientist policies under sealed evaluation. This pilot does not establish persistent "
        "skill acquisition, weight updates, recursive self-improvement, or scientific discovery.",
        "",
        "## Leakage and provenance",
        "",
        "All 24 proposal prompts were reconstructed exactly. The runtime saw only Task.md, "
        "public constraints, the parent program, proposal slot and the closed public metric "
        "allowlist. Certification, broad physical discipline, historical scores and sealed "
        "science metrics were absent. Every selection-blind parent was the frozen baseline.",
        "",
        "Raw report SHA-256: `%s`." % report["inputs"]["pilot_report"]["sha256"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = analyze(args.report)
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
