#!/usr/bin/env python3
"""Freeze the exact 50-task GPT-5.6 budget-one science census."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.algorithms.common import (  # noqa: E402
    llm_condition_sha256,
    runtime_source_sha256,
    task_contract_sha256,
    task_package_sha256,
)
from sle.certification import certification_status  # noqa: E402
from sle.config import load_llm_client  # noqa: E402
from sle.registry import list_tasks  # noqa: E402
from scripts.batch_evolve import _maturity_contract_sha256  # noqa: E402


DEFAULT_COHORT_OUTPUT = (
    ROOT / ".research/gpt56_science_census_cohort_2026-08-06_v1.json"
)
DEFAULT_PREREGISTRATION_OUTPUT = (
    ROOT / ".research/gpt56_science_census_preregistration_2026-08-06_v1.json"
)
LLM_CONFIG = "sle/conf/llm/local.gpt56.yaml"
WORKDIR = "runs/gpt56_science_census_2026-08-06_v1"
OUTPUT = "experiments/gpt56_science_census_2026-08-06_v1.json"
BLOCK_WORKERS = 8
EXPECTED_PILOT_CONDITION_SHA256 = (
    "60b240fdc2530ab24d202289a497dd4c2fb0ad1380a6ad9e8aca293bb8e4c34d"
)
PREREQUISITES = (
    "experiments/full_test_suite_2026-08-03_v31.json",
    "experiments/task_maturity_audit_2026-08-03_v5.json",
    "experiments/gpt56_science_pilot_analysis_2026-08-06_v1.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _git_revision() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()


def _task_rows() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    admitted = []
    excluded = []
    for spec in list_tasks(None):
        status = certification_status(spec.task_id)
        if status == "quarantined":
            excluded.append({"task": spec.task_id, "status": status})
            continue
        card = spec.task_dir / "TASK_CARD.yaml"
        admitted.append({
            "task": spec.task_id,
            "maturity_contract_sha256": _maturity_contract_sha256(spec),
            "runtime_contract_sha256": task_contract_sha256(spec),
            "task_package_sha256": task_package_sha256(spec),
            "task_card_sha256": _sha256(card),
            "provenance_class": "procedural",
        })
    return admitted, excluded


def build_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    rows, excluded = _task_rows()
    statuses = Counter(
        certification_status(str(row["task"])) for row in rows
    )
    if len(rows) != 50 or statuses != {"certified": 7, "candidate": 43}:
        raise ValueError("admitted census must contain 7 certified and 43 candidate tasks")
    if len(excluded) != 9:
        raise ValueError("census must exclude exactly nine quarantined tasks")
    cohort: dict[str, Any] = {
        "schema_version": 1,
        "manifest_id": "sle_gpt56_science_census_2026_08_06_v1",
        "frozen_at_utc": "2026-08-06",
        "analysis_role": "complete_internal_admission_census_budget_one_headroom_screen",
        "claim_limit": (
            "single_unseeded_provider_draw_per_task_not_population_model_ranking_"
            "feedback_causal_external_validation_recursive_self_improvement_or_"
            "autonomous_discovery_evidence"
        ),
        "selection": {
            "rule": (
                "Include every task whose frozen certification status is certified or "
                "candidate; exclude every quarantined task. Preserve registry order and "
                "retain every scheduled outcome regardless of score or validity."
            ),
            "census_not_sample": True,
            "selected_after_inspecting_gpt55_evidence": True,
            "selected_after_four_task_gpt56_pilot": True,
            "selection_depends_on_gpt56_pilot_outcome": False,
            "confirmatory_reuse_permitted": False,
            "admitted_status_counts": dict(sorted(statuses.items())),
            "excluded_status_counts": {"quarantined": len(excluded)},
            "excluded_tasks": excluded,
        },
        "task_weighting": (
            "retain_per_task_scores_validity_and_science_axes; summarize score "
            "distribution and counts without treating heterogeneous task scores as one "
            "scientific quantity"
        ),
        "failure_policy": (
            "intent_to_evaluate_with_outer_provider_or_evaluator_failures_invalid_code_"
            "schema_runtime_timeout_and_scientific_zero_scores_retained_separately"
        ),
        "tasks": rows,
    }
    cohort_bytes = _json_bytes(cohort)
    cohort_sha256 = hashlib.sha256(cohort_bytes).hexdigest()

    llm = load_llm_client(str(ROOT / LLM_CONFIG))
    condition_sha256 = llm_condition_sha256(llm)
    if condition_sha256 != EXPECTED_PILOT_CONDITION_SHA256:
        raise ValueError("local GPT-5.6 condition differs from the frozen pilot condition")
    if not (
        llm.config.model == "gpt-5.6-sol"
        and llm.config.wire == "responses"
        and llm.config.max_output_tokens == 16000
        and llm.config.reasoning_effort == "low"
        and llm.config.temperature is None
    ):
        raise ValueError("unexpected GPT-5.6 census model configuration")

    task_csv = ",".join(str(row["task"]) for row in rows)
    command = [
        "python3",
        "scripts/batch_evolve.py",
        "--all",
        "--tasks",
        task_csv,
        "--algorithms",
        "greedy_rewrite",
        "--feedback-modes",
        "normal",
        "--seeds",
        "0",
        "--budget",
        "1",
        "--timeout",
        "300",
        "--block-workers",
        str(BLOCK_WORKERS),
        "--llm-config",
        LLM_CONFIG,
        "--run-role",
        "calibration",
        "--preregistration",
        str(DEFAULT_PREREGISTRATION_OUTPUT.relative_to(ROOT)),
        "--cohort-manifest",
        str(DEFAULT_COHORT_OUTPUT.relative_to(ROOT)),
        "--workdir",
        WORKDIR,
        "--output",
        OUTPUT,
    ]
    prerequisite_rows = []
    for relative in PREREQUISITES:
        path = ROOT / relative
        evidence = json.loads(path.read_text(encoding="utf-8"))
        if not (
            evidence.get("execution_passed") is True
            and evidence.get("trusted_evidence") is True
            and evidence.get("passed") is True
        ):
            raise ValueError("prerequisite is not trusted passing evidence: %s" % relative)
        prerequisite_rows.append({"path": relative, "sha256": _sha256(path)})

    preregistration: dict[str, Any] = {
        "schema_version": 1,
        "preregistration_id": (
            "sle_gpt56_science_census_2026_08_06_v1"
        ),
        "frozen_at_utc": "2026-08-06",
        "purpose": (
            "measure_budget_one_gpt56_headroom_validity_and_cross_task_"
            "discrimination_over_the_complete_internally_admitted_inventory"
        ),
        "claim_limit": cohort["claim_limit"],
        "source_cohort": {
            "path": str(DEFAULT_COHORT_OUTPUT.relative_to(ROOT)),
            "sha256": cohort_sha256,
        },
        "frozen_source": {
            "parent_revision": _git_revision(),
            "runtime_source_sha256": runtime_source_sha256(),
            "source_change_rule": (
                "The execution revision must descend from parent_revision with no "
                "changes under sle, scripts, tests, benchmarks, or "
                "requirements-upstream.txt. Research and experiment evidence commits "
                "are allowed."
            ),
        },
        "model_condition": {
            "llm_condition_sha256": condition_sha256,
            "wire": llm.config.wire,
            "endpoint_sha256": hashlib.sha256(
                llm.config.base_url.encode("utf-8")
            ).hexdigest(),
            "model": llm.config.model,
            "max_output_tokens": llm.config.max_output_tokens,
            "temperature": llm.config.temperature,
            "reasoning_effort": llm.config.reasoning_effort,
            "server_side_seed_control": False,
            "replicate_identifier_limit": (
                "The local identifier controls only local ordering; it is not a provider "
                "generation seed and supports no population-performance inference."
            ),
        },
        "design": {
            "tasks": [
                {
                    "task": row["task"],
                    "task_contract_sha256": row["runtime_contract_sha256"],
                    "task_package_sha256": row["task_package_sha256"],
                    "task_card_sha256": row["task_card_sha256"],
                }
                for row in rows
            ],
            "algorithm": "greedy_rewrite",
            "feedback_modes": ["normal"],
            "replicate_identifiers": [0],
            "condition_order": "single_condition_no_order_contrast",
            "proposal_budget": 1,
            "scheduled_cell_count": 50,
            "scheduled_model_call_count": 50,
            "evaluator_timeout_seconds": 300,
            "block_workers": BLOCK_WORKERS,
            "primary_command": command,
        },
        "primary_outcomes": {
            "per_task": [
                "outer_cell_completion",
                "proposal_validity",
                "proposal_failure_kind",
                "baseline_combined_score",
                "proposal_combined_score",
                "terminal_best_combined_score",
                "selected_sealed_science_metrics",
            ],
            "difficulty_bands": {
                "protocol_blocked": "proposal is invalid; do not call this scientific difficulty",
                "executable_floor": "valid proposal and terminal best_score <= 0.01",
                "difficult": "valid proposal and 0.01 < terminal best_score < 0.50",
                "discriminating": "valid proposal and 0.50 <= terminal best_score < 0.95",
                "near_ceiling": "valid proposal and terminal best_score >= 0.95",
            },
            "evolution_candidate_rule": (
                "valid proposal, terminal best score in [0.05,0.95), nonzero public "
                "headroom, and no outer infrastructure failure; this nominates a later "
                "iterative study but is not itself self-evolution evidence"
            ),
        },
        "predeclared_descriptive_gates": {
            "protocol_health": (
                "All 50 cells complete, all 50 scheduled model calls are retained, and "
                "outer provider/evaluator infrastructure failures are reported separately."
            ),
            "scientific_scope": (
                "All 50 tasks retain a current passing internal-science-admission gate, "
                "a valid task card, a named scientific artifact/oracle/metric and citations; "
                "pending external domain review is a limitation, not silently upgraded."
            ),
            "execution_usability": (
                "At least 60% of proposals are executable; lower validity means the census "
                "is dominated by code/interface reliability rather than scientific quality."
            ),
            "challenge": (
                "At least 15 tasks have a valid proposal with terminal best_score below "
                "0.50; protocol-blocked tasks cannot satisfy this gate."
            ),
            "anti_saturation": (
                "No more than 40% of tasks with valid proposals have terminal best_score "
                "at or above 0.95."
            ),
            "discrimination": (
                "At least three of the four executable score bands are occupied and the "
                "task-level executable-score range is at least 0.50, or proposal-validity "
                "rates materially separate disciplines."
            ),
            "self_evolving_fit": (
                "Report the preregistered evolution-candidate count and available prior "
                "budget-three/selection-blind evidence. Budget one cannot establish "
                "feedback benefit, learning, or recursive self-improvement."
            ),
        },
        "leakage_and_failure_policy": {
            "runtime_allowed": (
                "Logical task id and Task.md, public constraints, baseline source, "
                "proposal slot, and the closed allowlist of feasibility/selection metrics."
            ),
            "runtime_prohibited": (
                "Physical discipline, certification status, cohort rationale, historical "
                "GPT-5.5/GPT-5.6 outcomes, task-card review labels, evaluator-only science "
                "metrics, per-instance diagnostics, ground truth and score files."
            ),
            "offline_only": (
                "Discipline/status grouping, task-card and maturity evidence, history, "
                "difficulty bands and sealed science-axis analysis occur only after all "
                "predictions are complete."
            ),
            "failure_retention": (
                "Invalid code, parse/schema/runtime failures, timeouts and outer provider/"
                "evaluator failures remain distinct outcomes; no replacement draw is made "
                "for a terminal candidate failure."
            ),
            "stopping": (
                "Run the complete frozen census unless infrastructure prevents continuation; "
                "do not stop because intermediate scores favor any conclusion."
            ),
        },
        "prerequisites": prerequisite_rows,
    }
    return cohort, preregistration


def validate_documents(
    cohort: dict[str, Any], preregistration: dict[str, Any]
) -> list[str]:
    issues = []
    tasks = [row.get("task") for row in cohort.get("tasks") or []]
    design_tasks = [
        row.get("task")
        for row in (preregistration.get("design") or {}).get("tasks") or []
    ]
    command = (preregistration.get("design") or {}).get("primary_command") or []
    try:
        command_tasks = command[command.index("--tasks") + 1].split(",")
    except (ValueError, IndexError):
        command_tasks = []
    if len(tasks) != 50 or len(set(tasks)) != 50:
        issues.append("cohort does not contain 50 unique tasks")
    if tasks != design_tasks or tasks != command_tasks:
        issues.append("cohort, execution contract and command task order differ")
    if any(certification_status(task) == "quarantined" for task in tasks):
        issues.append("cohort contains a quarantined task")
    expected_hash = hashlib.sha256(_json_bytes(cohort)).hexdigest()
    if (preregistration.get("source_cohort") or {}).get("sha256") != expected_hash:
        issues.append("preregistration cohort hash differs")
    design = preregistration.get("design") or {}
    if design.get("scheduled_cell_count") != 50 or design.get(
        "scheduled_model_call_count"
    ) != 50:
        issues.append("scheduled census size differs")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-output", type=Path, default=DEFAULT_COHORT_OUTPUT)
    parser.add_argument(
        "--preregistration-output",
        type=Path,
        default=DEFAULT_PREREGISTRATION_OUTPUT,
    )
    args = parser.parse_args()
    cohort, preregistration = build_documents()
    issues = validate_documents(cohort, preregistration)
    if issues:
        raise SystemExit("; ".join(issues))
    args.cohort_output.parent.mkdir(parents=True, exist_ok=True)
    args.preregistration_output.parent.mkdir(parents=True, exist_ok=True)
    args.cohort_output.write_bytes(_json_bytes(cohort))
    args.preregistration_output.write_bytes(_json_bytes(preregistration))
    print(json.dumps({
        "cohort_output": str(args.cohort_output),
        "cohort_sha256": _sha256(args.cohort_output),
        "preregistration_output": str(args.preregistration_output),
        "preregistration_sha256": _sha256(args.preregistration_output),
        "task_count": len(cohort["tasks"]),
        "excluded_task_count": len(cohort["selection"]["excluded_tasks"]),
        "issues": issues,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
