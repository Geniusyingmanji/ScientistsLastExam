"""Shared algorithm result and trajectory helpers."""

from __future__ import annotations

import json
import hashlib
import importlib.metadata
import math
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from ..evaluate import INVALID_SCORE
from ..llm import LLMClient
from ..spec import TaskSpec
from ..protocol import (
    SCHEMA_VERSION,
    TrajectoryEvent,
    append_event,
    load_trajectory,
    sha256_text,
    summarize_trajectory,
)

from ..metric_visibility import METRIC_VISIBILITY_SCOPE

PROMPT_FEEDBACK_SCOPE = (
    "proposal prompt sees only allowlisted selection metrics; search selection uses "
    "combined_score; " + METRIC_VISIBILITY_SCOPE
)


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def task_contract_sha256(spec: TaskSpec) -> str:
    paths = [
        spec.task_dir / "Task.md",
        spec.initial_program_path,
        spec.task_dir / "verification" / "evaluator.py",
        spec.eval_dir / "metadata.yaml",
        spec.eval_dir / "constraints.txt",
        spec.eval_dir / "entrypoint.txt",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(spec.task_dir)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def runtime_source_sha256() -> str:
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "frontier_science").rglob("*.py"))
    requirements = root / "requirements-upstream.txt"
    if requirements.is_file():
        paths.append(requirements)
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def llm_condition_sha256(llm: LLMClient) -> str:
    config = getattr(llm, "config", None)
    if config is None:
        return _canonical_hash({"client_type": type(llm).__name__})
    extra_headers = getattr(config, "extra_headers", None) or {}
    return _canonical_hash({
        "wire": getattr(config, "wire", None),
        "base_url": getattr(config, "base_url", None),
        "model": getattr(config, "model", None),
        "max_output_tokens": getattr(config, "max_output_tokens", None),
        "temperature": getattr(config, "temperature", None),
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "timeout_seconds": getattr(config, "timeout_seconds", None),
        # Header values may contain credentials. Their hashes still bind the run
        # condition without writing the secrets to disk.
        "extra_header_value_sha256": {
            str(key): hashlib.sha256(str(value).encode("utf-8")).hexdigest()
            for key, value in sorted(extra_headers.items())
        },
        "input_cost_per_million": getattr(config, "input_cost_per_million", None),
        "output_cost_per_million": getattr(config, "output_cost_per_million", None),
    })


def require_distribution(
    package: str,
    version: str,
    *,
    commit: Optional[str] = None,
) -> dict[str, Any]:
    dist = importlib.metadata.distribution(package)
    if dist.version != version:
        raise RuntimeError(
            "%s version mismatch: expected %s, installed %s"
            % (package, version, dist.version)
        )
    result: dict[str, Any] = {"package": package, "version": dist.version}
    direct_url = dist.read_text("direct_url.json")
    if direct_url:
        result["direct_url"] = json.loads(direct_url)
    if commit is not None:
        installed = ((result.get("direct_url") or {}).get("vcs_info") or {}).get("commit_id")
        if installed != commit:
            raise RuntimeError(
                "%s Git commit mismatch: expected %s, installed %s"
                % (package, commit, installed or "unknown")
            )
    return result


def ensure_run_manifest(
    workdir: Path,
    *,
    spec: TaskSpec,
    llm: LLMClient,
    algorithm: str,
    seed: int,
    feedback_mode: str,
    resume: bool,
    upstream: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "algorithm": algorithm,
        "task_id": spec.task_id,
        "task_contract_sha256": task_contract_sha256(spec),
        "runtime_source_sha256": runtime_source_sha256(),
        "runtime_environment": {
            "python": sys.version,
            "executable": str(Path(sys.executable).resolve()),
            "platform": platform.platform(),
        },
        "seed": int(seed),
        "feedback_mode": feedback_mode,
        "feedback_scope": PROMPT_FEEDBACK_SCOPE,
        "llm_condition_sha256": llm_condition_sha256(llm),
        "upstream": upstream,
    }
    path = Path(workdir) / "run_manifest.json"
    if resume:
        if not path.is_file():
            raise FileNotFoundError("--resume requested but run_manifest.json is missing")
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("run manifest does not match the requested task/algorithm conditions")
    else:
        existing = sorted(item.name for item in Path(workdir).iterdir())
        if existing:
            raise FileExistsError(
                "workdir is not empty; use --resume or a new --workdir: %s"
                % ", ".join(existing[:5])
            )
        atomic_write_text(path, json.dumps(expected, indent=2, allow_nan=False) + "\n")
    return expected


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    temporary = path.with_name(".%s.tmp" % path.name)
    temporary.write_text(text, encoding="utf-8")
    os.replace(str(temporary), str(path))


def reconstruction_path(path: Path) -> Path:
    path = Path(path)
    temporary = path.with_name(".%s.rebuild" % path.name)
    temporary.unlink(missing_ok=True)
    return temporary


def restore_committed_trajectory(path: Path, next_step: int) -> list[dict[str, Any]]:
    """Trim an append-only trajectory to the prefix committed by its checkpoint."""
    committed = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            # A crash can leave a partial uncommitted tail, but never excuse damage to
            # the checkpoint-owned prefix.
            if len(committed) < next_step:
                raise ValueError(
                    "trajectory is corrupt inside the checkpoint-owned prefix at line %d"
                    % line_number
                ) from exc
            break
        if event.get("schema_version") != SCHEMA_VERSION:
            if len(committed) < next_step:
                raise ValueError(
                    "unsupported trajectory schema inside checkpoint-owned prefix"
                )
            break
        step = int(event.get("step", -1))
        if step >= next_step:
            break
        committed.append(event)
    steps = [int(event.get("step", -1)) for event in committed]
    if steps != list(range(next_step)):
        raise ValueError("trajectory/checkpoint prefix is incomplete or non-sequential")
    canonical_lines = [
        json.dumps(event, allow_nan=False, separators=(",", ":")) for event in committed
    ]
    if lines != canonical_lines:
        rendered = "".join(
            line + "\n" for line in canonical_lines
        )
        atomic_write_text(Path(path), rendered)
    # Re-read through the canonical loader to apply all accounting invariants.
    return load_trajectory(Path(path))


@dataclass
class EvolveResult:
    task_id: str
    best_score: float
    baseline_score: float
    best_program: str
    history: list[dict[str, Any]] = field(default_factory=list)
    accepted: int = 0
    evaluated: int = 0
    algorithm: str = "greedy_rewrite"
    seed: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


def metrics_score(metrics: dict[str, Any]) -> tuple[float, bool]:
    try:
        score = float(metrics.get("combined_score", INVALID_SCORE))
        valid = float(metrics.get("valid", 0.0)) >= 1.0
    except (TypeError, ValueError):
        return INVALID_SCORE, False
    if not math.isfinite(score):
        return INVALID_SCORE, False
    return score, valid


def require_evaluation_budget(algorithm: str, count: int, budget: int) -> None:
    """Fail closed if an upstream search spent more evaluations than requested."""
    maximum = int(budget) + 1  # one baseline evaluation plus ``budget`` proposals
    if int(count) > maximum:
        raise RuntimeError(
            "%s produced %d real evaluation rows for a %d-call budget"
            % (algorithm, int(count), maximum)
        )


class TrajectoryRecorder:
    """Record an algorithm-independent, append-only evaluation trajectory."""

    def __init__(
        self,
        path: Path,
        *,
        algorithm: str,
        task_id: str,
        seed: int,
        budget: int,
        feedback_mode: str,
        resume: bool = False,
    ) -> None:
        self.path = Path(path)
        self.algorithm = algorithm
        self.task_id = task_id
        self.seed = int(seed)
        self.budget = int(budget)
        self.feedback_mode = feedback_mode
        self.started = time.monotonic()
        self.events = load_trajectory(self.path) if resume and self.path.is_file() else []
        if not self.events:
            self.path.unlink(missing_ok=True)
        self.cumulative_offset = (
            float(self.events[-1].get("cumulative_wall_seconds", 0.0)) if self.events else 0.0
        )
        self.best_score = max(
            (float(e["best_score"]) for e in self.events if bool(e.get("valid"))),
            default=INVALID_SCORE,
        )

    def record(
        self,
        *,
        step: int,
        oracle_calls: int,
        program: str,
        metrics: dict[str, Any],
        parent_sha256: Optional[str],
        wall_seconds: float,
        budget_units: Optional[int] = None,
        accepted: Optional[bool] = None,
        llm: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        algorithm_metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        score, valid = metrics_score(metrics)
        prior_best = self.best_score
        if valid:
            self.best_score = max(self.best_score, score)
        if accepted is None:
            accepted = valid and (not self.events or score > prior_best)
        event = TrajectoryEvent(
            step=int(step),
            oracle_calls=int(oracle_calls),
            score=score,
            best_score=self.best_score,
            valid=valid,
            accepted=bool(accepted),
            wall_seconds=float(wall_seconds),
            cumulative_wall_seconds=self.cumulative_offset + (time.monotonic() - self.started),
            candidate_sha256=sha256_text(program) if program else "",
            parent_sha256=parent_sha256,
            budget_units=int(budget_units if budget_units is not None else oracle_calls),
            metrics=metrics,
            llm=dict(llm or {}),
            error=error or metrics.get("error_message"),
            algorithm_metadata=dict(algorithm_metadata or {}),
        )
        append_event(self.path, event)
        rendered = event.to_dict()
        self.events.append(rendered)
        return rendered

    def summary(self, *, baseline_score: float, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self.events:
            raise ValueError("cannot summarize an empty trajectory")
        summary = summarize_trajectory(self.events, budget=self.budget + 1)
        summary.update(
            {
                "algorithm": self.algorithm,
                "task_id": self.task_id,
                "seed": self.seed,
                "baseline_score": float(baseline_score),
                "budget": self.budget,
                "feedback_mode": self.feedback_mode,
                "feedback_scope": PROMPT_FEEDBACK_SCOPE,
            }
        )
        if extra:
            summary.update(extra)
        return summary


def write_summary(workdir: Path, summary: dict[str, Any]) -> None:
    atomic_write_text(
        Path(workdir) / "summary.json",
        json.dumps(summary, indent=2, allow_nan=False) + "\n",
    )


def latest_numbered_directory(root: Path, prefix: str) -> Optional[Path]:
    candidates: list[tuple[int, Path]] = []
    for path in Path(root).glob(prefix + "*"):
        if not path.is_dir():
            continue
        try:
            number = int(path.name[len(prefix) :])
        except ValueError:
            continue
        candidates.append((number, path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def validate_feedback_mode(feedback_mode: str, supported: Iterable[str]) -> None:
    choices = tuple(supported)
    if feedback_mode not in choices:
        raise ValueError(
            "feedback_mode %r is unsupported; choose one of: %s"
            % (feedback_mode, ", ".join(choices))
        )
