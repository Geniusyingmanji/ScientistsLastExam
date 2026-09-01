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


def feedback_scope(feedback_mode: str) -> str:
    """Describe exactly how feedback can affect later proposals."""
    if feedback_mode == "selection_blind":
        return (
            "open-loop proposal batch: every proposal sees the frozen baseline program and "
            "its allowlisted baseline metrics; evaluated scores are retained only for offline "
            "best-of-batch analysis and never change a later parent or prompt; "
            + METRIC_VISIBILITY_SCOPE
        )
    if feedback_mode == "none":
        return (
            "proposal prompts omit metrics, but true combined_score still selects the next "
            "incumbent program; " + METRIC_VISIBILITY_SCOPE
        )
    if feedback_mode == "score_only":
        return (
            "proposal prompts receive only the scalar combined_score for the true-score-selected "
            "current incumbent; validity, feasibility, raw-score and diagnostic fields are "
            "omitted; evaluator-only metrics remain sealed; this is a feedback-bandwidth "
            "treatment, not a no-feedback control"
        )
    if feedback_mode == "delayed_replay":
        return (
            "one-proposal delayed replay: proposal k sees the best program and allowlisted "
            "metrics released only through proposal k-2 (the baseline is available at start); "
            "each evaluated proposal is released on that fixed lag, while the observer retains "
            "all scores for offline final selection; " + METRIC_VISIBILITY_SCOPE
        )
    if feedback_mode == "shuffled":
        return (
            "proposal prompts receive a randomly selected prior allowlisted metric record, "
            "while true combined_score still selects the next incumbent program; "
            + METRIC_VISIBILITY_SCOPE
        )
    if feedback_mode == "normal":
        return PROMPT_FEEDBACK_SCOPE
    raise ValueError("unknown feedback mode %r" % feedback_mode)


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


# Directories a task grows by being used rather than by being written. Their contents are
# outputs, not part of what the task asks or how it scores, and hashing them made a task's
# identity depend on whether anyone had run it.
GENERATED_DIRECTORIES = {"__pycache__", "runs", ".pytest_cache", ".ipynb_checkpoints"}


def task_package_sha256(spec: TaskSpec) -> str:
    """Bind every task source/data file while excluding generated output.

    `runs` is excluded for the same reason `__pycache__` is, and its absence from the original
    exclusion list caused real damage. Several tasks accumulate a `runs/` directory inside the
    task directory when they are executed, so the hash meant to identify the task changed every
    time the task was run. Three consequences, all observed:

    the hashes recorded in eleven tasks' manifests are reproduced by no revision in this
    repository, because they are hashes of a tree that contained run output;

    two runs of an unedited task record different `task_package_sha256` values, and the
    comparability guard in the reports reads that as two different versions of the task and
    refuses to compare them; and

    the frozen-cohort preflight can fail its `frozen_task_package` check because somebody ran the
    task, which is not what that check is for.

    Excluding them changes the hash of any task that has been run in place. That is intended: the
    new value is the one that identifies the task rather than the task plus its history.
    """

    digest = hashlib.sha256()
    paths = sorted(
        path for path in spec.task_dir.rglob("*")
        if path.is_file()
        and not GENERATED_DIRECTORIES & set(path.relative_to(spec.task_dir).parts)
        and path.suffix not in {".pyc", ".pyo"}
    )
    for path in paths:
        digest.update(
            path.relative_to(spec.task_dir).as_posix().encode("utf-8") + b"\0"
        )
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def runtime_source_sha256() -> str:
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "sle").rglob("*.py"))
    requirements = root / "requirements-upstream.txt"
    if requirements.is_file():
        paths.append(requirements)
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def llm_condition_descriptor(llm: LLMClient) -> dict[str, Any]:
    """The searcher condition in readable form, for answering 'which model produced this run'.

    The hash beside it binds the condition and detects drift, but a hash cannot be read back.
    Without this, a result can be reproduced but not attributed, and a comparison across runs
    cannot be checked for having held the model fixed.

    Credential-bearing fields are excluded: header values are covered by the hash only, and the
    base URL is reduced to its host so a query-string token cannot reach disk.
    """
    config = getattr(llm, "config", None)
    if config is None:
        return {"client_type": type(llm).__name__}
    base_url = getattr(config, "base_url", None)
    host = None
    if base_url:
        try:
            from urllib.parse import urlsplit

            parts = urlsplit(str(base_url))
            host = parts.netloc or None
        except Exception:  # noqa: BLE001 - a malformed URL must not break a run
            host = None
    return {
        "model": getattr(config, "model", None),
        "wire": getattr(config, "wire", None),
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "temperature": getattr(config, "temperature", None),
        "max_output_tokens": getattr(config, "max_output_tokens", None),
        "timeout_seconds": getattr(config, "timeout_seconds", None),
        "stream": getattr(config, "stream", False),
        "base_url_host": host,
    }


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
        "stream": getattr(config, "stream", False),
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


def _without(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in mapping.items() if name != key}


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
    protocol: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "algorithm": algorithm,
        "task_id": spec.task_id,
        "task_contract_sha256": task_contract_sha256(spec),
        "task_package_sha256": task_package_sha256(spec),
        "runtime_source_sha256": runtime_source_sha256(),
        "runtime_environment": {
            "python": sys.version,
            "executable": str(Path(sys.executable).resolve()),
            "platform": platform.platform(),
        },
        "seed": int(seed),
        "feedback_mode": feedback_mode,
        "feedback_scope": feedback_scope(feedback_mode),
        "llm_condition_sha256": llm_condition_sha256(llm),
        "llm_condition": llm_condition_descriptor(llm),
        "upstream": upstream,
    }
    if protocol is not None:
        expected["protocol"] = protocol
    path = Path(workdir) / "run_manifest.json"
    if resume:
        if not path.is_file():
            raise FileNotFoundError("--resume requested but run_manifest.json is missing")
        actual = json.loads(path.read_text(encoding="utf-8"))
        # `llm_condition` is descriptive: the binding check is `llm_condition_sha256`, which is
        # compared below like every other field. Excluding it from the equality test keeps runs
        # recorded before it existed resumable, and stops a purely cosmetic field from being
        # able to invalidate a resume.
        if _without(actual, "llm_condition") != _without(expected, "llm_condition"):
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
                "feedback_scope": feedback_scope(self.feedback_mode),
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
