"""Discover discipline-grouped task packages under ``benchmarks/``."""

from __future__ import annotations

import difflib
from pathlib import Path

from .spec import TaskSpec, load_task_spec
from .certification import certification_status
from .benchmark_layout import DISCIPLINE_DOMAINS

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"


def discover_task_dirs() -> list[Path]:
    if not BENCHMARKS.is_dir():
        return []
    roots = {path.name for path in BENCHMARKS.iterdir()
             if path.is_dir() and path.name != "__pycache__"}
    unexpected = roots - set(DISCIPLINE_DOMAINS)
    if unexpected:
        raise ValueError(
            "Unexpected top-level benchmark directories: %s"
            % ", ".join(sorted(unexpected))
        )
    task_dirs = sorted(p.parent for p in BENCHMARKS.glob("*/*/frontier_eval")
                       if p.is_dir() and p.parent.parent.name in DISCIPLINE_DOMAINS)
    nested = sorted(
        path for path in BENCHMARKS.glob("*/*/*/frontier_eval")
        if path.is_dir() and path.parents[2].name in DISCIPLINE_DOMAINS
    )
    if nested:
        raise ValueError(
            "Benchmark tasks must be direct children of a discipline: %s"
            % ", ".join(str(path.parent.relative_to(BENCHMARKS)) for path in nested)
        )
    return task_dirs


def list_tasks(status: str | None = "certified") -> list[TaskSpec]:
    """List tasks by certification status; ``None`` explicitly returns the inventory."""
    specs = [load_task_spec(d) for d in discover_task_dirs()]
    if status is None or status == "all":
        return specs
    if status not in {"certified", "candidate", "quarantined"}:
        raise ValueError("unknown certification status: %s" % status)
    return [s for s in specs if certification_status(s.task_id) == status]


def find_task(name: str, include_uncertified: bool = False) -> TaskSpec:
    """Match by full id (Domain/Task) or by task name (case-insensitive)."""
    name_l = name.lower().strip("/")
    specs = list_tasks(None) if include_uncertified else list_tasks()
    for spec in specs:
        if spec.task_id.lower() == name_l or spec.task_dir.name.lower() == name_l:
            return spec
    # Name the closest matches, not the whole inventory. The full list is 80+ ids and it
    # travels inside a single exception message: any caller that tail-slices the text (the
    # frontier_eval wrappers keep the last 500 characters of stderr) ends up reporting a
    # fragment of the task list instead of the actual error. Below ~8 candidates the ids are
    # cheap enough to name outright, which is what the old message did well.
    by_id = {s.task_id.lower(): s.task_id for s in specs}
    by_dir = {s.task_dir.name.lower(): s.task_id for s in specs}
    close = [task_id for key, task_id in by_id.items() if name_l in key]
    close += [task_id for key, task_id in by_dir.items()
              if name_l in key and task_id not in close]
    if not close:
        # Match on the bare directory name, but report the stable public id either way, so a
        # reader never has to guess which of the two forms they were handed.
        close = [by_dir[key] for key in difflib.get_close_matches(
            name_l, list(by_dir), n=8, cutoff=0.5)]
    if close:
        hint = "Closest: %s." % ", ".join(sorted(close)[:8])
    else:
        hint = "No close match."
    # The count has to come from the inventory, not from `specs`: on the default path `specs`
    # holds only the certified tasks, so reporting its length states that the repository has
    # five tasks while the caller is asking about one of the other seventy-odd.
    total = len(specs) if include_uncertified else len(list_tasks(None))
    scope = ("" if include_uncertified else
             " This lookup covered certified tasks only; pass --allow-uncertified"
             " (or include_uncertified=True) to search all of them.")
    raise KeyError(
        f"Unknown task '{name}'. {hint}"
        f" {total} tasks are registered; run `python -m sle list --all` for the full list."
        f"{scope}"
    )
