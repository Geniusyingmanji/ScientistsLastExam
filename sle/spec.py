"""Task spec loader — reads the per-task black-box contract.

A Frontier-Science task lives at ``benchmarks/<Discipline>/<Task>/`` and provides a
``frontier_eval/`` directory with the contract files. Its metadata ``domain`` and task
directory name form the stable logical ``<Domain>/<Task>`` id. This mirrors the
Frontier-Engineering ``UnifiedTask`` layout so tasks are added with no harness change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .benchmark_layout import discipline_for_domain


def _read_text(p: Path) -> str | None:
    return p.read_text(encoding="utf-8") if p.is_file() else None


def _read_scalar(p: Path) -> str | None:
    txt = _read_text(p)
    if txt is None:
        return None
    for line in txt.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def _read_list(p: Path) -> list[str]:
    txt = _read_text(p)
    if not txt:
        return []
    out = []
    for line in txt.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


@dataclass
class TaskSpec:
    task_id: str                 # e.g. "Chemistry/LennardJonesCluster"
    task_dir: Path
    eval_dir: Path
    metadata: dict = field(default_factory=dict)
    candidate_destination: str = "solution.py"
    eval_command: str = ""
    constraints: str = ""
    task_md: str = ""
    agent_files: list[str] = field(default_factory=list)
    entrypoint: str = ""

    @property
    def initial_program_path(self) -> Path:
        rel = _read_scalar(self.eval_dir / "initial_program.txt") or self.candidate_destination
        return (self.task_dir / rel).resolve()

    @property
    def difficulty(self) -> str:
        return str(self.metadata.get("difficulty", "unknown"))

    @property
    def domain(self) -> str:
        return str(self.metadata.get("domain", self.task_id.split("/")[0]))

    @property
    def task_family_id(self) -> str:
        """Stable family identity; legacy one-wave tasks are their own family."""

        return str(self.metadata.get("task_family_id", self.task_id))

    @property
    def wave_id(self) -> str | None:
        value = self.metadata.get("wave_id")
        return str(value) if value is not None else None

    @property
    def discipline(self) -> str:
        """Broad physical directory category; not part of the stable task id."""

        return self.task_dir.parent.name

    def agent_visible_text(self) -> str:
        """The only task context the agent is allowed to see."""
        parts = [f"# Task: {self.task_id}\n", self.task_md.strip()]
        if self.constraints.strip():
            parts.append("\n## Constraints\n" + self.constraints.strip())
        return "\n".join(parts)


def load_task_spec(task_dir: Path) -> TaskSpec:
    task_dir = task_dir.resolve()
    eval_dir = task_dir / "frontier_eval"
    if not eval_dir.is_dir():
        raise FileNotFoundError(f"No frontier_eval/ in {task_dir}")
    meta = yaml.safe_load(_read_text(eval_dir / "metadata.yaml") or "") or {}
    domain = meta.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError(f"Missing metadata domain in {eval_dir / 'metadata.yaml'}")
    domain = domain.strip()
    expected_discipline = discipline_for_domain(domain)
    if task_dir.parent.name != expected_discipline:
        raise ValueError(
            f"Domain {domain!r} belongs under benchmarks/{expected_discipline}, "
            f"not benchmarks/{task_dir.parent.name}"
        )
    task_id = f"{domain}/{task_dir.name}"
    return TaskSpec(
        task_id=task_id,
        task_dir=task_dir,
        eval_dir=eval_dir,
        metadata=meta,
        candidate_destination=_read_scalar(eval_dir / "candidate_destination.txt") or "solution.py",
        eval_command=_read_scalar(eval_dir / "eval_command.txt") or "",
        constraints=_read_text(eval_dir / "constraints.txt") or "",
        task_md=_read_text(task_dir / "Task.md") or "",
        agent_files=_read_list(eval_dir / "agent_files.txt"),
        entrypoint=_read_scalar(eval_dir / "entrypoint.txt") or "",
    )
