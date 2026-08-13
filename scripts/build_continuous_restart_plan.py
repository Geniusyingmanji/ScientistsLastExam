#!/usr/bin/env python3
"""Compile the frozen continuous-vs-restart preregistration into run cells."""

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

from sle.algorithms.common import task_contract_sha256  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import find_task  # noqa: E402


DEFAULT_PREREG = ROOT / ".research/continuous_restart_preregistration_2026-07-27_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("preregistration must be a JSON object")
    return value


def build_plan(preregistration: Path) -> dict[str, Any]:
    preregistration = preregistration.resolve()
    prereg = _load(preregistration)
    if prereg.get("schema_version") != 1:
        raise ValueError("unsupported preregistration schema")
    tasks = list((prereg.get("selection") or {}).get("tasks") or [])
    arms = list(prereg.get("arms") or [])
    proposal = prereg.get("proposal_budget") or {}
    sentinels = prereg.get("sentinels") or {}
    system = prereg.get("system_condition") or {}
    issues = []
    if len(tasks) != 3 or len(set(tasks)) != 3:
        issues.append("preregistration must freeze exactly three distinct tasks")
    if [row.get("arm") for row in arms] != ["continuous_12h", "fresh_restart_6x2h"]:
        issues.append("unexpected arm definitions")

    cells = []
    for task in tasks:
        spec = find_task(task, include_uncertified=True)
        for arm in arms:
            arm_id = str(arm["arm"])
            count = int(arm["run_count_per_task"])
            horizon = float(arm["active_wall_seconds_per_run"])
            for restart_index in range(count):
                cells.append({
                    "cell_index": len(cells) + 1,
                    "cell_id": "%s|%s|%02d" % (task, arm_id, restart_index),
                    "task": task,
                    "arm": arm_id,
                    "restart_index": restart_index,
                    "local_replicate_identifier": restart_index,
                    "active_wall_horizon_s": horizon,
                    "proposal_budget_upper_bound": int(
                        proposal["configured_upper_bound_per_run"]
                    ),
                    "evaluator_timeout_s": float(
                        proposal["evaluator_timeout_seconds"]
                    ),
                    "sentinel_interval_s": float(
                        sentinels["fixed_grid_interval_seconds"]
                    ),
                    "signed_decisions": True,
                    "signed_decision_policy": str(
                        arm["signed_decision_policy"]
                    ),
                    "initial_state": arm["initial_state"],
                    "inherits_prior_cell_state": False,
                    "task_runtime_contract_sha256": task_contract_sha256(spec),
                    "task_card_sha256": _sha256(spec.task_dir / "TASK_CARD.yaml"),
                })

    by_task = {}
    for task in tasks:
        task_cells = [row for row in cells if row["task"] == task]
        totals = {}
        for arm in ("continuous_12h", "fresh_restart_6x2h"):
            selected = [row for row in task_cells if row["arm"] == arm]
            totals[arm] = sum(row["active_wall_horizon_s"] for row in selected)
        by_task[task] = {
            "cell_count": len(task_cells),
            "total_active_wall_seconds": totals,
            "equal_total_active_wall": len(set(totals.values())) == 1,
        }
        if len(task_cells) != 7 or len(set(totals.values())) != 1:
            issues.append("%s arm totals are not equivalent" % task)

    if len(cells) != 21:
        issues.append("compiled plan must contain 21 cells")
    if any(row["inherits_prior_cell_state"] for row in cells):
        issues.append("fresh cells unexpectedly inherit prior state")
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "TRUSTED_FROZEN_EXPERIMENT_PLAN",
        "evidence_scope": (
            "COMPILED_RESULT_SELECTED_EXPLORATORY_CONTINUOUS_VS_RESTART_PLAN_"
            "NOT_EXECUTION_MODEL_PERFORMANCE_CAUSAL_MEMORY_OR_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "preregistration": {
            "path": str(preregistration.relative_to(ROOT)),
            "sha256": _sha256(preregistration),
            "preregistration_id": prereg["preregistration_id"],
            "claim_limit": prereg["claim_limit"],
        },
        "system_condition": system,
        "task_count": len(tasks),
        "arm_count": len(arms),
        "cell_count": len(cells),
        "by_task": by_task,
        "cells": cells,
        "issues": issues,
        "important_limits": prereg["analysis_restrictions"],
    }
    finalize_report_trust(report, not issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_plan(args.preregistration)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "task_count": report["task_count"],
        "cell_count": report["cell_count"],
        "by_task": report["by_task"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
