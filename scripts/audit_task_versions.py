#!/usr/bin/env python3
"""Report which recorded runs were made against a version of their task that no longer exists.

A task package is hashed at run time and the hash is written into every run manifest, so the
tree already knows which version of a task each run measured. Nothing was reading it. Twenty of
the fifty-four tasks here turned out to carry more than one hash across cohorts - they were
edited between runs - and the reports were correlating scores across those edits and calling the
difference a model difference. On one task the gap read as eighteen-fold; the two numbers were
measurements of two different tasks.

The reports now refuse to compare across versions. That makes the analysis honest but leaves the
underlying question unanswered: how much of the recorded evidence is about tasks that no longer
exist? This answers it, by hashing every task as it stands today and comparing.

    current      the run measured the task as it is now, and its evidence still applies
    superseded   the task has changed since; the run measures something no longer in the tree
    unknown      the manifest predates the field

A superseded run is not corrupt and is not deleted. It is evidence about an earlier version of a
task, and the only thing wrong with it is using it as though it were evidence about this one.
Re-running is the remedy, and this report exists to size that job: which tasks, how many runs,
under which models.

Usage:
    python scripts/audit_task_versions.py --runs runs --output /tmp/versions.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.common import task_package_sha256  # noqa: E402
from frontier_science.registry import find_task, list_tasks  # noqa: E402


def current_versions() -> dict[str, str]:
    """Hash every task as it stands in the working tree."""
    out = {}
    for spec in list_tasks(None):
        try:
            out[spec.task_id] = task_package_sha256(spec)
        except Exception as error:  # noqa: BLE001 - reported per task, not fatal
            print("could not hash %s: %s" % (spec.task_id, error), file=sys.stderr)
    return out


def read_runs(runs_root: Path) -> list[dict]:
    out = []
    for manifest in runs_root.glob("*/*/run_manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task = document.get("task_id")
        if not task:
            continue
        out.append({
            "task": str(task),
            "cohort": manifest.parent.parent.name,
            "version": str(document.get("task_package_sha256") or ""),
            "model": str((document.get("llm_condition") or {}).get("model") or "unrecorded"),
            "mode": str(document.get("feedback_mode") or ""),
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    runs = read_runs(Path(args.runs))
    current = current_versions()

    per_task: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        per_task[run["task"]][run["version"]].append(run)

    rows, superseded_runs, unknown_runs, current_runs = [], 0, 0, 0
    for task in sorted(per_task):
        now = current.get(task)
        versions = []
        for version, group in sorted(per_task[task].items()):
            if not version:
                state = "unknown"
                unknown_runs += len(group)
            elif now is None:
                # The task is not in the registry any more - quarantined or removed.
                state = "task_absent"
            elif version[:12] == now[:12]:
                state = "current"
                current_runs += len(group)
            else:
                state = "superseded"
                superseded_runs += len(group)
            versions.append({
                "version": version[:12] or "unrecorded",
                "state": state,
                "runs": len(group),
                "cohorts": sorted({r["cohort"] for r in group}),
                "models": sorted({r["model"] for r in group}),
            })
        rows.append({
            "task": task,
            "current_version": (now or "")[:12] or None,
            "in_registry": now is not None,
            "versions": versions,
            "runs": sum(v["runs"] for v in versions),
        })

    stale = [r for r in rows if any(v["state"] == "superseded" for v in r["versions"])]

    print("%-34s %-13s %s" % ("task", "current", "recorded versions"))
    print("-" * 96)
    for row in rows:
        marks = "  ".join(
            "%s:%s(%d)" % (v["version"][:8],
                           {"current": "now", "superseded": "OLD", "unknown": "?",
                            "task_absent": "gone"}[v["state"]],
                           v["runs"])
            for v in row["versions"])
        print("%-34s %-13s %s" % (row["task"].split("/")[-1][:34],
                                  (row["current_version"] or "not in registry")[:13], marks))

    print()
    print("runs measured against the task as it stands now: %d" % current_runs)
    print("runs measured against a version that has since changed: %d" % superseded_runs)
    print("runs whose manifest predates the version field: %d" % unknown_runs)
    print()
    print("tasks holding superseded evidence (%d):" % len(stale))
    for row in stale:
        old = [v for v in row["versions"] if v["state"] == "superseded"]
        print("  %-32s %d run(s) across %s" % (
            row["task"].split("/")[-1][:32],
            sum(v["runs"] for v in old),
            ", ".join(sorted({m for v in old for m in v["models"]}))))
    print()
    print("Superseded runs are not wrong; they measure an earlier version of the task. Re-running")
    print("them is what makes their evidence comparable with everything else, and the counts")
    print("above are the size of that job.")

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "a superseded run is evidence about an earlier version of its task, not a bad run",
        "current_runs": current_runs,
        "superseded_runs": superseded_runs,
        "unknown_version_runs": unknown_runs,
        "tasks_with_superseded_evidence": [r["task"] for r in stale],
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
