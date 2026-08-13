#!/usr/bin/env python3
"""Build portable, non-causal evidence from Antenna-v2 budget calibrations."""

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

from sle.protocol import compact_trajectory_snapshot  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


REPORTS = {
    "budget_one": "experiments/gpt55_antenna_v2_b1_2026-07-21.json",
    "budget_three": "experiments/gpt55_antenna_v2_b3_2026-07-21.json",
}
TASK = "Electromagnetics/AntennaArraySynthesis"
FIELDS = (
    "combined_score", "robustness_score", "heldout_policy_score",
    "heldout_robustness_score", "mean_worst_shifted_quality_db",
    "mean_shifted_target_gain_feasibility_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(label: str, relative: str) -> dict[str, Any]:
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    provenance = document.get("source_provenance") or {}
    if document.get("trusted_evidence") is not True or document.get("passed") is not True:
        raise ValueError("input report is not trusted and passed: %s" % relative)
    if provenance.get("source_tree_dirty") is not False:
        raise ValueError("input report has dirty source: %s" % relative)
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) != 1 or runs[0].get("error"):
        raise ValueError("expected exactly one successful run: %s" % relative)
    run = runs[0]
    if (
        run.get("task") != TASK or run.get("algorithm") != "greedy_rewrite"
        or run.get("feedback_mode") != "normal"
    ):
        raise ValueError("unexpected task/algorithm/feedback mode: %s" % relative)
    trajectory = compact_trajectory_snapshot(Path(run["workdir"]) / "trajectory.jsonl")
    if trajectory != run.get("trajectory_snapshot"):
        raise ValueError("portable snapshot disagrees with raw trajectory: %s" % relative)
    events = trajectory["events"]
    parent = events[0]["candidate_sha256"]
    for event in events[1:]:
        if event["parent_sha256"] != parent:
            raise ValueError("accepted-candidate lineage is broken: %s" % relative)
        if event["accepted"]:
            parent = event["candidate_sha256"]
    if int(run["evaluated"]) != int(run["summary"]["oracle_calls"]):
        raise ValueError("oracle-call count mismatch: %s" % relative)
    if abs(float(events[-1]["best_score"]) - float(run["best"])) > 1.0e-12:
        raise ValueError("terminal trajectory best mismatch: %s" % relative)
    return {
        "label": label,
        "report": relative,
        "report_sha256": _sha256(path),
        "trajectory_sha256": trajectory["trajectory_sha256"],
        "source_revision": provenance["git_revision"],
        "seed": int(run["seed"]),
        "proposal_budget": int(document["config"]["budget"]),
        "server_side_seed_control": bool(
            document["config"]["llm"].get("server_side_seed_control")
        ),
        "oracle_calls": int(run["summary"]["oracle_calls"]),
        "total_tokens": int(run["summary"]["llm"]["total_tokens"]),
        "best_score": float(run["best"]),
        "feedback_scope": run["summary"].get("feedback_scope"),
        "trajectory": [
            {
                "step": int(event["step"]),
                "accepted": bool(event["accepted"]),
                "candidate_sha256": event["candidate_sha256"],
                "parent_sha256": event["parent_sha256"],
                **{field: event["metrics"].get(field) for field in FIELDS},
            }
            for event in events
        ],
    }


def _analyze_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    budget_one = records["budget_one"]
    budget_three = records["budget_three"]
    events = budget_three["trajectory"]
    accepted = [event for event in events[1:] if event["accepted"]]
    visible_differences = [
        accepted[index]["combined_score"] - accepted[index - 1]["combined_score"]
        for index in range(1, len(accepted))
    ]
    robustness_differences = [
        accepted[index]["robustness_score"] - accepted[index - 1]["robustness_score"]
        for index in range(1, len(accepted))
    ]
    shifted_quality_differences = [
        accepted[index]["mean_worst_shifted_quality_db"]
        - accepted[index - 1]["mean_worst_shifted_quality_db"]
        for index in range(1, len(accepted))
    ]
    common_revision = {record["source_revision"] for record in records.values()}
    execution_passed = bool(
        len(common_revision) == 1
        and budget_one["proposal_budget"] == 1
        and budget_three["proposal_budget"] == 3
        and budget_one["oracle_calls"] == 2
        and budget_three["oracle_calls"] == 4
        and not budget_one["server_side_seed_control"]
        and not budget_three["server_side_seed_control"]
        and budget_one["best_score"] > 0.99
        and len(accepted) == 3
        and all(delta > 0.0 for delta in visible_differences)
        and all(delta < 0.0 for delta in robustness_differences)
        and all(delta < 0.0 for delta in shifted_quality_differences)
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_DERIVED_EVIDENCE",
        "evidence_scope": "ANTENNA_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "input_source_revision": next(iter(common_revision)) if len(common_revision) == 1 else None,
        "records": records,
        "budget_three_accepted_step_changes": [
            {
                "from_step": int(accepted[index - 1]["step"]),
                "to_step": int(accepted[index]["step"]),
                "development_score": visible_differences[index - 1],
                "robustness_score": robustness_differences[index - 1],
                "heldout_policy_score": (
                    accepted[index]["heldout_policy_score"]
                    - accepted[index - 1]["heldout_policy_score"]
                ),
                "heldout_robustness_score": (
                    accepted[index]["heldout_robustness_score"]
                    - accepted[index - 1]["heldout_robustness_score"]
                ),
                "mean_worst_shifted_quality_db": shifted_quality_differences[index - 1],
            }
            for index in range(1, len(accepted))
        ],
        "limitations": [
            "Each budget condition has one independent run; no population or causal feedback estimate is supported.",
            "Budget-one and budget-three use different local identifiers and are not prefixes of one trajectory.",
            "The Azure endpoint exposes no server-side model seed, so replicate identifiers do not control generation randomness.",
            "Robustness and held-out metrics were sealed from proposal and selection state.",
            "The within-budget-three dissociation is descriptive: accepted nominal improvements coincide with lower sealed robustness, but no robustness-aware treatment was run.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def analyze() -> dict[str, Any]:
    return _analyze_records({
        label: _load(label, relative) for label, relative in REPORTS.items()
    })


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
