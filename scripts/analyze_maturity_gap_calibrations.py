#!/usr/bin/env python3
"""Freeze a claim-bounded analysis of the three current-contract gap calibrations."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


DEFAULT_B1 = ROOT / "experiments/gpt55_maturity_gap_b1_current_v1_2026-07-26.json"
DEFAULT_B3 = ROOT / "experiments/gpt55_maturity_gap_current_v1_2026-07-26.json"
EXPECTED_TASKS = {
    "DynamicalSystems/LyapunovControl",
    "Geophysics/SeismicInversion",
    "NuclearEngineering/NeutronDiffusionCriticality",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("trusted_evidence") is not True or document.get("execution_passed") is not True:
        raise ValueError("input report must be trusted and passed: %s" % path)
    return document


def _events(run: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = run.get("trajectory_snapshot") or {}
    events = snapshot.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("run lacks a trajectory snapshot")
    return events


def _record(run: dict[str, Any]) -> dict[str, Any]:
    events = _events(run)
    proposals = [event for event in events if int(event.get("step", 0)) >= 1]
    if not proposals:
        raise ValueError("run lacks proposals")
    valid = [event for event in proposals if event.get("valid") is True]
    first_valid = valid[0] if valid else None
    return {
        "task": run["task"],
        "feedback_mode": run["feedback_mode"],
        "seed": run["seed"],
        "baseline_score": run["baseline"],
        "best_score": run["best"],
        "proposal_count": len(proposals),
        "valid_proposal_count": len(valid),
        "first_valid_proposal_score": first_valid.get("score") if first_valid else None,
        "proposal_scores": [event.get("score") for event in proposals],
        "oracle_calls": run["summary"]["oracle_calls"],
        "total_tokens": run["summary"]["llm"]["total_tokens"],
        "wall_seconds": run["summary"]["wall_seconds"],
        "selection_policy": run["summary"].get("selection_policy"),
        "trajectory_sha256": run["trajectory_snapshot"]["trajectory_sha256"],
    }


def build_report(b1_path: Path, b3_path: Path) -> dict[str, Any]:
    b1 = _load(b1_path)
    b3 = _load(b3_path)
    records = [_record(run) for run in b1["runs"] + b3["runs"]]
    by_task: dict[str, dict[str, Any]] = {}
    for task in sorted(EXPECTED_TASKS):
        task_records = [row for row in records if row["task"] == task]
        b1_rows = [row for row in task_records if row["proposal_count"] == 1]
        normal = [
            row for row in task_records
            if row["feedback_mode"] == "normal" and row["proposal_count"] == 3
        ]
        blind = [
            row for row in task_records
            if row["feedback_mode"] == "selection_blind" and row["proposal_count"] == 3
        ]
        if len(b1_rows) != 1 or len(normal) != 1 or len(blind) != 1:
            raise ValueError("incomplete task evidence: %s" % task)
        b1_row, normal_row, blind_row = b1_rows[0], normal[0], blind[0]
        by_task[task] = {
            "budget_one_score": b1_row["best_score"],
            "normal_budget_three_scores": normal_row["proposal_scores"],
            "normal_budget_three_best": normal_row["best_score"],
            "selection_blind_budget_three_scores": blind_row["proposal_scores"],
            "selection_blind_budget_three_best": blind_row["best_score"],
            "normal_minus_selection_blind_best": (
                normal_row["best_score"] - blind_row["best_score"]
            ),
            "normal_total_tokens": normal_row["total_tokens"],
            "selection_blind_total_tokens": blind_row["total_tokens"],
            "all_proposals_valid": all(
                row["valid_proposal_count"] == row["proposal_count"]
                for row in task_records
            ),
            "current_disposition": (
                "one_step_saturated_on_ramp"
                if task != "NuclearEngineering/NeutronDiffusionCriticality"
                else "fixed_single_regime_near_ceiling_on_ramp"
            ),
        }

    execution_passed = bool(
        set(by_task) == EXPECTED_TASKS
        and len(records) == 9
        and all(row["all_proposals_valid"] for row in by_task.values())
        and by_task["DynamicalSystems/LyapunovControl"]["budget_one_score"] >= 0.999
        and by_task["Geophysics/SeismicInversion"]["budget_one_score"] >= 0.99
        and by_task["NuclearEngineering/NeutronDiffusionCriticality"]["budget_one_score"] >= 0.90
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": (
            "THREE_TASK_CURRENT_CONTRACT_SINGLE_SEED_HEADROOM_CALIBRATION_NOT_"
            "FEEDBACK_CAUSAL_POPULATION_LONG_HORIZON_EXTERNAL_VALIDATION_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": [
            {
                "path": str(b1_path.relative_to(ROOT)),
                "sha256": _sha256(b1_path),
                "source_revision": b1["source_provenance"]["git_revision"],
            },
            {
                "path": str(b3_path.relative_to(ROOT)),
                "sha256": _sha256(b3_path),
                "source_revision": b3["source_provenance"]["git_revision"],
            },
        ],
        "records": records,
        "task_findings": by_task,
        "portfolio_implications": [
            "LyapunovControl and SeismicInversion reproduce known numerical workflows at or near the score ceiling in the first proposal; they are on-ramps, not long-horizon headline tasks.",
            "NeutronDiffusion shows within-run normal improvement, but the selection-blind batch scores higher with fewer tokens; one single-seed contrast supports no feedback-effect claim.",
            "NeutronDiffusion still exposes one fixed public reduced-order slab and therefore lacks procedural transfer and post-two-hour headroom evidence even though its normal trajectory is nonflat.",
            "All three tasks need substantive procedural redesign rather than additional sampling of the same fixed contract before long-horizon allocation.",
        ],
        "limitations": [
            "Each condition has one independent provider draw; the Azure endpoint exposes no server-side generation seed.",
            "Normal and selection-blind runs match proposal and oracle-call budgets but not realized tokens, context, or wall time.",
            "Budget-one and budget-three conditions are independent runs, not prefixes of one trajectory.",
            "A clipped or near-ceiling score on these fixed public tasks is not evidence of scientific novelty or external validity.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-one", type=Path, default=DEFAULT_B1)
    parser.add_argument("--budget-three", type=Path, default=DEFAULT_B3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.budget_one.resolve(), args.budget_three.resolve())
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "task_findings": report["task_findings"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
