#!/usr/bin/env python3
"""Does a task's difficulty ladder actually change the difficulty?

Eight tasks ship a three-level ladder and every one of them sits at level 1. Levels 2 and 3 exist
in the source and have never been scored, so `difficulty_parameterized` currently asserts that a
ladder is *present*, not that it does anything. A ladder whose levels are not ordered by difficulty
is decoration, and worse than none: it makes a saturated task look like it has somewhere to go.

The question matters most for the tasks that are saturated. A saturated task with a working ladder
should be promoted, not retired; a saturated task with a decorative one has nothing left. Deciding
that by reading the level parameters is guesswork - the parameters interact - so this measures it.

Each level is scored by copying the task, rewriting its `DIFFICULTY` constant in the copy, and
running the candidate through the copy's own evaluator. The shipped task is never modified, and the
copy sits under a matching discipline directory so it loads exactly as the original does.

Usage:
    python scripts/report_difficulty_ladder.py --task RNAEngineering/RNAEnsembleDesign \
        --candidate runs/<cohort>/<task>/greedy_rewrite/normal/seed_0/best_program.py
    python scripts/report_difficulty_ladder.py --all-laddered --runs runs
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.registry import find_task, list_tasks  # noqa: E402
from sle.spec import load_task_spec  # noqa: E402

DIFFICULTY_LINE = re.compile(r"^DIFFICULTY\s*=\s*\d+", re.MULTILINE)


def laddered_tasks() -> list[str]:
    out = []
    for spec in list_tasks(None):
        path = spec.task_dir / "verification" / "evaluator.py"
        if path.is_file() and DIFFICULTY_LINE.search(path.read_text(encoding="utf-8")):
            out.append(spec.task_id)
    return out


def _task_at_level(task_id: str, level: int, root: Path):
    """A copy of the task with its difficulty rewritten, loaded as a normal task."""
    spec = find_task(task_id, include_uncertified=True)
    destination = root / spec.task_dir.parent.name / spec.task_dir.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(spec.task_dir, destination,
                    ignore=shutil.ignore_patterns("__pycache__", "runs"))
    evaluator = destination / "verification" / "evaluator.py"
    source = evaluator.read_text(encoding="utf-8")
    rewritten, count = DIFFICULTY_LINE.subn("DIFFICULTY = %d" % level, source, count=1)
    if count != 1:
        raise ValueError("%s has no single DIFFICULTY constant to rewrite" % task_id)
    evaluator.write_text(rewritten, encoding="utf-8")
    return load_task_spec(destination)


def _best_candidate(task_id: str, runs_root: Path) -> Path | None:
    best, best_score = None, None
    for manifest in runs_root.rglob("run_manifest.json"):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if document.get("task_id") != task_id:
            continue
        program = manifest.parent / "best_program.py"
        checkpoint = manifest.parent / "checkpoint.json"
        if not program.is_file() or not checkpoint.is_file():
            continue
        try:
            score = json.loads(checkpoint.read_text(encoding="utf-8")).get("best_score")
        except (OSError, ValueError):
            continue
        if isinstance(score, (int, float)) and (best_score is None or score > best_score):
            best, best_score = program, score
    return best


def measure(task_id: str, candidate: Path, levels, timeout: float) -> dict:
    scores = {}
    for level in levels:
        with tempfile.TemporaryDirectory(prefix="ladder_") as temporary:
            try:
                spec = _task_at_level(task_id, level, Path(temporary))
                metrics = evaluate_candidate(spec, candidate, timeout_s=timeout)
            except Exception as error:  # noqa: BLE001 - reported per level, never fatal
                scores[level] = {"status": "could not score: %s" % str(error)[:160]}
                continue
        scores[level] = {
            "status": "scored",
            "combined_score": metrics.get("combined_score"),
            "valid": metrics.get("valid"),
            "infrastructure_failure": bool(metrics.get("infrastructure_failure")),
        }
    return {"task": task_id, "candidate": str(candidate), "levels": scores}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=None)
    ap.add_argument("--all-laddered", action="store_true")
    ap.add_argument("--candidate", type=Path, default=None)
    ap.add_argument("--runs", type=Path, default=ROOT / "runs")
    ap.add_argument("--levels", default="1,2,3")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args(argv)

    levels = [int(value) for value in args.levels.split(",") if value.strip()]
    tasks = laddered_tasks() if args.all_laddered else ([args.task] if args.task else [])
    if not tasks:
        raise SystemExit("give --task or --all-laddered")

    rows = []
    for task_id in tasks:
        candidate = args.candidate or _best_candidate(task_id, args.runs)
        if candidate is None:
            rows.append({"task": task_id, "status": "no recorded candidate on disk"})
            print("%-46s no recorded candidate" % task_id[:46])
            continue
        row = measure(task_id, candidate, levels, args.timeout)
        scored = {level: value["combined_score"] for level, value in row["levels"].items()
                  if value.get("status") == "scored"}
        # A ladder does something when a higher level is harder for the same program. Equal scores
        # mean the level parameter is not reaching the difficulty; a *higher* score means it is
        # reaching it backwards.
        ordered = [scored[level] for level in sorted(scored)
                   if isinstance(scored[level], (int, float))]
        row["monotone_harder"] = bool(
            len(ordered) >= 2 and all(b <= a + 1e-9 for a, b in zip(ordered, ordered[1:])))
        row["flat"] = bool(len(ordered) >= 2
                           and max(ordered) - min(ordered) <= 1e-9)
        rows.append(row)
        print("%-46s %s   %s" % (
            task_id[:46],
            "  ".join("L%d=%s" % (level, "%.4f" % scored[level]
                                  if isinstance(scored[level], (int, float)) else scored[level])
                      for level in sorted(scored)),
            "FLAT - the ladder changes nothing" if row["flat"]
            else ("harder with level" if row["monotone_harder"] else "not ordered by level")))

    flat = [row["task"] for row in rows if row.get("flat")]
    print()
    print("laddered tasks measured: %d; ladders that change nothing: %d"
          % (sum(1 for row in rows if "levels" in row), len(flat)))
    for task in flat:
        print("   ", task)

    if args.output:
        args.output.write_text(json.dumps({
            "schema_version": 1,
            "note": "each level is scored by copying the task and rewriting DIFFICULTY in the "
                    "copy; the shipped task is never modified",
            "levels": levels,
            "ladders_that_change_nothing": flat,
            "rows": rows,
        }, indent=2) + "\n", encoding="utf-8")
        print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
