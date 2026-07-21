#!/usr/bin/env python3
"""Validate and summarize the preregistered strict-feedback pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import mean_confidence_interval  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


REPORTS = (
    "experiments/feedback_pilot_pendulum_2026-07-21.json",
    "experiments/feedback_pilot_gate_2026-07-21.json",
    "experiments/feedback_pilot_active_law_2026-07-21.json",
    "experiments/feedback_pilot_opf_2026-07-21.json",
)

TASK_METRICS = {
    "ControlTheory/InvertedPendulumSwingUp": (
        "robustness_score",
        "development_robustness_gap",
    ),
    "QuantumControl/GateSynthesis": (
        "robustness_score",
        "heldout_policy_score",
        "heldout_robustness_score",
    ),
    "DynamicalSystems/ActiveLawDiscovery": (
        "mechanism_score",
        "development_prediction_score",
        "robustness_score",
        "validation_prediction_score",
        "development_false_discoveries",
        "validation_false_discoveries",
    ),
    "PowerSystems/OptimalPowerFlow": (
        "robustness_score",
        "heldout_policy_score",
        "heldout_robustness_score",
        "mean_contingency_constraint_feasibility",
        "mean_contingency_feasibility_rate",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selected_event(run: dict[str, Any]) -> dict[str, Any]:
    events = (run.get("trajectory_snapshot") or {}).get("events") or []
    valid = [event for event in events if event.get("valid") is True]
    if not valid:
        raise ValueError("run has no valid trajectory event")
    # Strict improvement retains the first event at a tied maximum.
    selected = max(valid, key=lambda event: (float(event["score"]), -int(event["step"])))
    if not math.isclose(
        float(selected["score"]), float(run["best"]), rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("selected trajectory event disagrees with run best")
    return selected


def _verify_blind_lineage(run: dict[str, Any]) -> None:
    snapshot = run.get("trajectory_snapshot") or {}
    events = snapshot.get("events") or []
    if len(events) != 4:
        raise ValueError("expected baseline plus three proposal events")
    baseline_hash = events[0]["candidate_sha256"]
    for event in events[1:]:
        if event.get("parent_sha256") != baseline_hash:
            raise ValueError("selection_blind proposal parent is not the frozen baseline")
        metadata = event.get("algorithm_metadata") or {}
        if metadata.get("selection_policy") != "offline_best_of_open_loop_batch":
            raise ValueError("selection_blind trajectory lacks offline selection metadata")


def _paired_summary(values: list[float]) -> dict[str, Any]:
    return mean_confidence_interval(values)


def analyze(paths: list[Path]) -> dict[str, Any]:
    documents = []
    input_records = []
    revisions = set()
    condition_hashes = set()
    for path in paths:
        path = path.resolve()
        document = json.loads(path.read_text(encoding="utf-8"))
        provenance = document.get("source_provenance") or {}
        if document.get("trusted_evidence") is not True or document.get("passed") is not True:
            raise ValueError("pilot input is not trusted/passed: %s" % path)
        if provenance.get("source_tree_dirty") is not False:
            raise ValueError("pilot input has dirty provenance: %s" % path)
        config = document.get("config") or {}
        expected = {
            "algorithms": ["greedy_rewrite"],
            "feedback_modes": ["normal", "selection_blind"],
            "seeds": [0, 1, 2],
            "budget": 3,
        }
        for key, value in expected.items():
            if config.get(key) != value:
                raise ValueError("pilot config mismatch for %s in %s" % (key, path))
        if config.get("condition_order") != "as_listed_for_even_seeds_reversed_for_odd_seeds":
            raise ValueError("pilot condition order was not counterbalanced")
        llm = config.get("llm") or {}
        if llm.get("model") != "gpt-5.5" or llm.get("server_side_seed_control") is not False:
            raise ValueError("unexpected model or server seed declaration")
        revisions.add(provenance["git_revision"])
        condition_hashes.add(config.get("llm_condition_sha256"))
        documents.append(document)
        input_records.append({
            "report": str(path.relative_to(ROOT)),
            "sha256": _sha256(path),
            "source_revision": provenance["git_revision"],
            "task": config["tasks"][0],
        })

    if len(revisions) != 1 or len(condition_hashes) != 1:
        raise ValueError("pilot reports do not share one source/model condition")
    expected_tasks = set(TASK_METRICS)
    if {record["task"] for record in input_records} != expected_tasks:
        raise ValueError("pilot task set does not match preregistration")

    runs = [run for document in documents for run in document.get("runs", [])]
    if len(runs) != 24 or any(run.get("error") for run in runs):
        raise ValueError("pilot must contain 24 successful conditions")
    keyed: dict[tuple[str, int, str], dict[str, Any]] = {}
    selected_rows = []
    for run in runs:
        task = run["task"]
        seed = int(run["seed"])
        mode = run["feedback_mode"]
        key = (task, seed, mode)
        if key in keyed:
            raise ValueError("duplicate pilot condition %r" % (key,))
        keyed[key] = run
        if mode == "selection_blind":
            _verify_blind_lineage(run)
            if run["summary"].get("selection_policy") != "offline_best_of_open_loop_batch":
                raise ValueError("blind summary has wrong selection policy")
        elif run["summary"].get("selection_policy") != "online_incumbent":
            raise ValueError("normal summary has wrong selection policy")
        event = _selected_event(run)
        metrics = event.get("metrics") or {}
        missing = [metric for metric in TASK_METRICS[task] if metric not in metrics]
        if missing:
            raise ValueError("selected event is missing metrics: %s" % ", ".join(missing))
        selected_rows.append({
            "task": task,
            "replicate_id": seed,
            "condition": mode,
            "selected_step": int(event["step"]),
            "selected_candidate_sha256": event["candidate_sha256"],
            "best_visible_score": float(run["best"]),
            "best_so_far_auc": float(run["summary"]["best_so_far_auc"]),
            "oracle_calls": int(run["summary"]["oracle_calls"]),
            "total_tokens": run["summary"]["llm"]["total_tokens"],
            "wall_seconds": float(run["summary"]["wall_seconds"]),
            "science_metrics": {metric: metrics[metric] for metric in TASK_METRICS[task]},
        })

    paired = []
    task_summaries = {}
    rows_by_key = {
        (row["task"], row["replicate_id"], row["condition"]): row
        for row in selected_rows
    }
    for task in sorted(TASK_METRICS):
        task_pairs = []
        for seed in (0, 1, 2):
            normal = rows_by_key[(task, seed, "normal")]
            blind = rows_by_key[(task, seed, "selection_blind")]
            differences = {
                "best_visible_score": normal["best_visible_score"] - blind["best_visible_score"],
                "best_so_far_auc": normal["best_so_far_auc"] - blind["best_so_far_auc"],
                **{
                    metric: (
                        float(normal["science_metrics"][metric])
                        - float(blind["science_metrics"][metric])
                    )
                    for metric in TASK_METRICS[task]
                },
            }
            row = {"task": task, "replicate_id": seed, "normal_minus_blind": differences}
            paired.append(row)
            task_pairs.append(row)
        fields = ("best_visible_score", "best_so_far_auc", *TASK_METRICS[task])
        task_summaries[task] = {
            field: _paired_summary([
                pair["normal_minus_blind"][field] for pair in task_pairs
            ])
            for field in fields
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "THREE_REPLICATE_IMPLEMENTATION_PILOT_NOT_CONFIRMATORY_CAUSAL_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "design": {
            "tasks": sorted(TASK_METRICS),
            "conditions": ["normal", "selection_blind"],
            "replicate_ids": [0, 1, 2],
            "proposal_budget": 3,
            "server_side_seed_control": False,
            "paired_difference_direction": "normal_minus_selection_blind",
        },
        "inputs": input_records,
        "selected_candidates": selected_rows,
        "paired_differences": paired,
        "task_summaries": task_summaries,
        "limitations": [
            "Three replicate identifiers provide diagnostic intervals only.",
            "The endpoint exposes no server-side random seed, so pairs do not share random draws.",
            "Selection blindness changes both parent-program adaptation and access to prior scores.",
            "Task-specific science metrics are not averaged across tasks.",
        ],
    }
    complete = bool(
        len(paths) == len(REPORTS)
        and {record["report"] for record in input_records} == set(REPORTS)
        and len(selected_rows) == 24
        and len(paired) == 12
    )
    finalize_report_trust(report, complete)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("reports", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.reports or [ROOT / path for path in REPORTS]
    report = analyze(paths)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
