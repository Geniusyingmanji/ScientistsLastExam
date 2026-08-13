"""Discover discipline-grouped task packages under ``benchmarks/``."""

from __future__ import annotations

from pathlib import Path

from .spec import TaskSpec, load_task_spec
from .certification import certification_status
from .benchmark_layout import DISCIPLINE_DOMAINS

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "benchmarks"


def discover_task_dirs() -> list[Path]:
    if not BENCHMARKS.is_dir():
        return []
    roots = {path.name for path in BENCHMARKS.iterdir() if path.is_dir()}
    unexpected = roots - set(DISCIPLINE_DOMAINS)
    if unexpected:
        raise ValueError(
            "Unexpected top-level benchmark directories: %s"
            % ", ".join(sorted(unexpected))
        )
    task_dirs = sorted(p.parent for p in BENCHMARKS.glob("*/*/frontier_eval") if p.is_dir())
    nested = sorted(
        path for path in BENCHMARKS.glob("*/*/*/frontier_eval") if path.is_dir()
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
    avail = ", ".join(s.task_id for s in specs) or "(none)"
    raise KeyError(f"Unknown task '{name}'. Available: {avail}")
