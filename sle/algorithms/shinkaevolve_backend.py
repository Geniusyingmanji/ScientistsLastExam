"""Adapter for the official ShinkaEvolve program-evolution system."""

from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..evaluate import resolve_trusted_runtime
from ..llm import LLMClient
from ..metric_visibility import load_full_metrics
from ..protocol import sha256_text
from ..spec import TaskSpec
from ..upstream_evaluator import write_configured_wrapper
from .common import (
    EvolveResult,
    TrajectoryRecorder,
    atomic_write_text,
    ensure_run_manifest,
    metrics_score,
    reconstruction_path,
    require_evaluation_budget,
    require_distribution,
    validate_feedback_mode,
    write_summary,
)

SHINKA_VERSION = "0.0.7"
SHINKA_COMMIT = "b67a07328ab7e21e999d9e20a44f4f0054a4b83c"


def _load_shinka():
    try:
        from shinka.core import EvolutionConfig, ShinkaEvolveRunner
        from shinka.database import DatabaseConfig
        from shinka.launch import LocalJobConfig
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "ShinkaEvolve requires the official SakanaAI/ShinkaEvolve package at commit %s "
            "and Python >=3.10. Install the GitHub package in a dedicated environment."
            % SHINKA_COMMIT[:12]
        ) from exc
    distribution = require_distribution("shinka-evolve", SHINKA_VERSION, commit=SHINKA_COMMIT)
    return EvolutionConfig, ShinkaEvolveRunner, DatabaseConfig, LocalJobConfig, distribution


def _shinka_model(model: str, base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if normalized in {"", "https://api.openai.com", "https://api.openai.com/v1"}:
        return model
    if model.startswith("local/"):
        return model
    return "local/%s@%s" % (model, normalized)


def _load_program_rows(database: Path) -> list[dict[str, Any]]:
    if not database.is_file():
        return []
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, code, parent_id, generation, combined_score, correct, "
            "public_metrics, private_metrics, metadata FROM programs ORDER BY generation, timestamp"
        ).fetchall()
    finally:
        connection.close()
    rendered = []
    for row in rows:
        item = dict(row)
        for key in ("public_metrics", "private_metrics", "metadata"):
            try:
                item[key] = json.loads(item.get(key) or "{}")
            except (TypeError, json.JSONDecodeError):
                item[key] = {}
        rendered.append(item)
    return rendered


def _evaluation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop Shinka's synthetic island copies, which do not consume oracle calls."""
    return [row for row in rows if not bool((row.get("metadata") or {}).get("_is_island_copy"))]


def shinkaevolve(
    spec: TaskSpec,
    llm: LLMClient,
    budget: int = 10,
    timeout_s: float = 300.0,
    workdir: Optional[Path] = None,
    log_fn: Callable[[str], None] = print,
    seed: int = 0,
    resume: bool = False,
    feedback_mode: str = "normal",
) -> EvolveResult:
    validate_feedback_mode(feedback_mode, ("normal", "none"))
    if budget < 0:
        raise ValueError("budget must be non-negative")
    if budget > 0 and llm.config.wire != "chat":
        raise ValueError("official ShinkaEvolve supports OpenAI-compatible chat wire only")
    (EvolutionConfig, ShinkaEvolveRunner, DatabaseConfig, LocalJobConfig,
     distribution) = _load_shinka()

    workdir = Path(
        workdir
        or spec.task_dir / "runs" / ("shinkaevolve_%s" % time.strftime("%Y%m%d_%H%M%S"))
    ).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    trusted_runtime = resolve_trusted_runtime(spec.task_dir)
    ensure_run_manifest(
        workdir, spec=spec, llm=llm, algorithm="shinkaevolve", seed=seed,
        feedback_mode=feedback_mode, resume=resume,
        upstream={"name": "shinkaevolve", "version": SHINKA_VERSION,
                  "commit": SHINKA_COMMIT},
        trusted_runtime=trusted_runtime,
    )
    upstream_dir = workdir / "upstream"
    database_path = upstream_dir / "programs.sqlite"
    if database_path.exists() and not resume:
        raise FileExistsError("ShinkaEvolve workdir already contains a run; use --resume")
    if resume and not database_path.exists():
        raise FileNotFoundError("--resume requested but no ShinkaEvolve database exists")

    os.environ["OPENAI_API_KEY"] = llm.config.api_key or "DUMMY_API_KEY_FOR_LOCAL_GATEWAY"
    os.environ["LOCAL_OPENAI_API_KEY"] = llm.config.api_key or "DUMMY_API_KEY_FOR_LOCAL_GATEWAY"
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    model = _shinka_model(llm.config.model, llm.config.base_url)
    trajectory_path = workdir / "trajectory.jsonl"
    rebuild_path = reconstruction_path(trajectory_path)
    recorder = TrajectoryRecorder(
        rebuild_path,
        algorithm="shinkaevolve",
        task_id=spec.task_id,
        seed=seed,
        budget=budget,
        feedback_mode=feedback_mode,
        resume=False,
    )
    target_generations = budget + 1  # Shinka counts the baseline as generation zero.
    evo = EvolutionConfig(
        init_program_path=str(spec.initial_program_path),
        results_dir=str(upstream_dir),
        language="python",
        task_sys_msg=(
            "Improve this scientific candidate while preserving its entrypoint and output contract.\n\n"
            + spec.agent_visible_text()
        ),
        num_generations=target_generations,
        llm_models=[model],
        llm_kwargs={
            "temperatures": [float(llm.config.temperature or 0.0)],
            "max_tokens": int(llm.config.max_output_tokens),
        },
        embedding_model=None,
        meta_rec_interval=None,
        use_text_feedback=feedback_mode == "normal",
        max_novelty_attempts=1,
    )
    evaluator_file = write_configured_wrapper(
        workdir / "upstream_evaluator.py", spec.task_id, timeout_s,
        full_metrics_dir=workdir / "trusted_full_metrics",
        expected_trusted_runtime_sha256=trusted_runtime.fingerprint_sha256,
    )
    job = LocalJobConfig(
        eval_program_path=str(evaluator_file),
        time="00:%02d:%02d" % (int(timeout_s) // 60, int(timeout_s) % 60),
        numeric_threads_per_job=1,
    )
    database = DatabaseConfig(num_islands=2, archive_size=max(4, min(40, budget + 1)))
    runner = ShinkaEvolveRunner(
        evo_config=evo,
        job_config=job,
        db_config=database,
        banner_style="minimal",
        verbose=False,
        max_evaluation_jobs=1,
        max_proposal_jobs=1,
        max_db_workers=1,
    )
    runner.run()

    rows = _evaluation_rows(_load_program_rows(database_path))
    if not rows:
        raise RuntimeError("ShinkaEvolve produced no persisted programs")
    require_evaluation_budget("ShinkaEvolve", len(rows), budget)
    by_id = {row["id"]: row for row in rows}
    best_row = rows[0]
    baseline_score = float(rows[0]["combined_score"])
    best_score = float("-inf")
    history = []
    for index, row in enumerate(rows):
        generation = int(row["generation"])
        public_metrics = {
            **dict(row.get("public_metrics") or {}),
            **dict(row.get("private_metrics") or {}),
            "combined_score": row.get("combined_score"),
            "valid": 1.0 if bool(row.get("correct")) else 0.0,
        }
        metrics = load_full_metrics(
            workdir / "trusted_full_metrics", str(row["code"]), public_metrics
        )
        score, valid = metrics_score(metrics)
        improved = valid and score > best_score
        if improved:
            best_score = score
            best_row = row
        parent = by_id.get(row.get("parent_id"))
        recorder.record(
            step=index,
            oracle_calls=index + 1,
            budget_units=index + 1,
            program=str(row["code"]),
            metrics=metrics,
            parent_sha256=sha256_text(str(parent["code"])) if parent else None,
            wall_seconds=0.0,
            accepted=improved,
            algorithm_metadata={
                "upstream_generation": generation,
                "source_job_id": (row.get("metadata") or {}).get("source_job_id"),
            },
        )
        history.append({"iter": generation, "score": score, "best": best_score, "accepted": improved})

    best_program = str(best_row["code"])
    summary = recorder.summary(
        baseline_score=baseline_score,
        extra={
            "upstream": {"name": "shinkaevolve", "version": SHINKA_VERSION,
                         "commit": SHINKA_COMMIT},
            "installed_distribution": distribution,
            "accounting_note": "Cost is retained in the upstream SQLite metadata; token counts are provider-dependent.",
        },
    )
    proposal_rows = rows[1:]
    cost_values = [(row.get("metadata") or {}).get("api_costs") for row in proposal_rows]
    total_cost = (
        0.0 if not proposal_rows else
        sum(float(value) for value in cost_values)
        if all(isinstance(value, (int, float)) and not isinstance(value, bool)
               for value in cost_values) else None
    )
    summary["llm"] = {
        "usage_available": "no_calls" if not proposal_rows else "cost_only",
        "calls": 0 if not proposal_rows else None,
        "evaluated_proposals": len(proposal_rows),
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": 0 if not proposal_rows else None,
        "estimated_cost_usd": total_cost,
    }
    os.replace(str(rebuild_path), str(trajectory_path))
    atomic_write_text(workdir / "best_program.py", best_program)
    write_summary(workdir, summary)
    log_fn("[%s] ShinkaEvolve best=%.6f programs=%d" % (spec.task_id, best_score, len(rows)))
    return EvolveResult(
        task_id=spec.task_id,
        best_score=best_score,
        baseline_score=baseline_score,
        best_program=best_program,
        history=history,
        accepted=sum(bool(row["accepted"]) for row in history[1:]),
        evaluated=len(rows),
        algorithm="shinkaevolve",
        seed=seed,
        summary=summary,
    )
