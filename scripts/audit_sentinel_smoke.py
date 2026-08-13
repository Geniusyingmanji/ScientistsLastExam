#!/usr/bin/env python3
"""Audit the expected-failing seven-task fixed-duration sentinel smoke."""

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
from sle.sentinels import load_sentinel_events  # noqa: E402


DEFAULT_RAW = ROOT / "experiments/exploratory_2h_sentinel_smoke_2026-07-27_v1.json"
DEFAULT_COHORT = ROOT / ".research/exploratory_2h_cohort_manifest_2026-07-27_v1.json"
EXPECTED_INCOMPLETE = "proposal_budget_exhausted_before_active_wall_horizon"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def _recorded_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_report(raw_path: Path, cohort_path: Path) -> dict[str, Any]:
    raw_path = raw_path.resolve()
    cohort_path = cohort_path.resolve()
    raw = _load(raw_path)
    cohort = _load(cohort_path)
    expected_tasks = [row["task"] for row in cohort["tasks"]]
    config = raw.get("config") or {}
    aggregate = raw.get("aggregate") or {}
    rows = []
    issues = []

    if raw.get("execution_passed") is not False:
        issues.append("raw negative smoke unexpectedly passed")
    if raw.get("trust_decision") != "execution_failed":
        issues.append("raw negative smoke has the wrong trust decision")
    if config.get("tasks") != expected_tasks:
        issues.append("raw task cohort differs from frozen manifest")
    bound = config.get("cohort_manifest") or {}
    if bound.get("sha256") != _sha256(cohort_path):
        issues.append("raw report does not bind the current cohort manifest")
    if bound.get("confirmatory_reuse_permitted") is not False:
        issues.append("raw report lost the no-confirmatory-reuse restriction")
    if config.get("active_wall_horizon_s") != 7200:
        issues.append("raw smoke horizon is not 7200 seconds")
    if config.get("sentinel_interval_s") != 1800:
        issues.append("raw smoke sentinel interval is not 1800 seconds")

    for run in raw.get("runs") or []:
        workdir = Path(run["workdir"])
        snapshot = (run.get("summary") or {}).get("sentinel_snapshot") or {}
        ledger_path = workdir / str(snapshot.get("ledger_path"))
        try:
            events = load_sentinel_events(ledger_path, workdir=workdir)
        except Exception as exc:  # noqa: BLE001
            issues.append("%s sentinel replay failed: %s" % (run.get("task"), exc))
            events = []
        replay_hash = _sha256(ledger_path) if ledger_path.is_file() else None
        checks = {
            "protocol_incomplete_is_expected": run.get("protocol_incomplete") == EXPECTED_INCOMPLETE,
            "horizon_not_reached": (run.get("summary") or {}).get("horizon_reached") is False,
            "baseline_did_not_cross_horizon": (run.get("summary") or {}).get("baseline_crossed_horizon") is False,
            "sentinel_snapshot_hash_matches": replay_hash == snapshot.get("ledger_sha256"),
            "sentinel_snapshot_events_match": events == snapshot.get("events"),
            "exact_t0_and_terminal": [row.get("sentinel_type") for row in events] == ["t0", "terminal"],
            "terminal_binds_baseline": bool(
                len(events) == 2
                and events[0].get("artifact_sha256") == events[1].get("artifact_sha256")
                and events[0].get("source_step") == 0
                and events[1].get("source_step") == 0
            ),
            "terminal_reason_is_expected": bool(
                len(events) == 2 and events[1].get("reason") == EXPECTED_INCOMPLETE
            ),
            "terminal_feedback_hidden": bool(
                len(events) == 2 and events[1].get("feedback_visible") is False
            ),
        }
        if not all(checks.values()):
            issues.append(
                "%s failed sentinel checks: %s" % (
                    run.get("task"),
                    ", ".join(key for key, passed in checks.items() if not passed),
                )
            )
        rows.append({
            "task": run.get("task"),
            "workdir": str(workdir),
            "checks": checks,
            "sentinel_ledger_sha256": replay_hash,
            "t0_artifact_sha256": events[0].get("artifact_sha256") if events else None,
            "terminal_artifact_sha256": events[-1].get("artifact_sha256") if events else None,
        })

    if [row["task"] for row in rows] != expected_tasks:
        issues.append("audited run order differs from the frozen cohort")
    if len(rows) != 7:
        issues.append("expected seven audited runs")
    if aggregate.get("protocol_incomplete_attempts") != 7:
        issues.append("aggregate does not retain seven protocol-incomplete attempts")
    intent = aggregate.get("intent_to_evaluate") or {}
    if intent.get("scheduled_runs") != 7 or intent.get("successful_runs") != 0:
        issues.append("intent-to-evaluate denominator is wrong")
    if intent.get("run_cells_with_protocol_incomplete_attempt") != 7:
        issues.append("protocol-incomplete cells disappeared from the aggregate")

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_NEGATIVE_PROTOCOL_AUDIT",
        "evidence_scope": (
            "BASELINE_ONLY_EXPECTED_FAIL_FIXED_DURATION_SENTINEL_AND_COHORT_BINDING_"
            "AUDIT_NOT_MODEL_PERFORMANCE_LONG_HORIZON_HEADROOM_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "inputs": [
            {"path": _recorded_path(raw_path), "sha256": _sha256(raw_path)},
            {"path": _recorded_path(cohort_path), "sha256": _sha256(cohort_path)},
        ],
        "expected_negative_outcome": {
            "raw_execution_passed": False,
            "protocol_incomplete_attempts": 7,
            "reason": EXPECTED_INCOMPLETE,
        },
        "task_count": len(rows),
        "task_audits": rows,
        "issues": issues,
        "limitations": [
            "Budget zero exercises baseline and terminal capture only; no GPT-5.5 proposal is requested.",
            "No first-valid, submission, commit, abstain or fixed-grid event occurs in this negative smoke.",
            "Passing this audit validates fail-closed protocol accounting, not a completed two-hour run.",
        ],
    }
    finalize_report_trust(report, not issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.raw, args.cohort)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "task_count": report["task_count"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
