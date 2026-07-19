"""Secure black-box candidate evaluation."""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .secure_eval import INVALID_SCORE, validate_metrics
from .spec import TaskSpec


def _trusted_python() -> str:
    """Keep trusted evaluation independent from optional framework environments."""
    configured = os.environ.get("FRONTIER_SCIENCE_TRUSTED_PYTHON")
    if configured:
        return str(Path(configured).expanduser().resolve())
    system_python = Path("/usr/bin/python3")
    return str(system_python if system_python.is_file() else Path(sys.executable).resolve())


def evaluate_candidate(spec: TaskSpec, candidate_path: Path, timeout_s: float = 300.0) -> dict[str, Any]:
    candidate_path = Path(candidate_path).resolve()
    if not candidate_path.is_file():
        return {"combined_score": INVALID_SCORE, "valid": 0.0,
                "error_message": "candidate is not a regular file"}
    if not spec.entrypoint:
        return {"combined_score": INVALID_SCORE, "valid": 0.0,
                "error_message": "task has no declared entrypoint.txt"}
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        return {"combined_score": INVALID_SCORE, "valid": 0.0,
                "error_message": "timeout must be positive and finite"}
    score_mode = str(spec.metadata.get("score_mode", "clipped"))
    with tempfile.TemporaryDirectory(prefix="fs_trusted_") as tmp:
        result_path = Path(tmp) / "metrics.json"
        cmd = [
            _trusted_python(), "-m", "frontier_science.trusted_driver",
            "--task-dir", str(spec.task_dir), "--candidate", str(candidate_path),
            "--entrypoint", spec.entrypoint, "--score-mode", score_mode,
            "--timeout", str(timeout_s), "--result", str(result_path),
        ]
        proc = subprocess.Popen(
            cmd, cwd=str(Path(__file__).resolve().parent.parent),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            _, stderr = proc.communicate(timeout=timeout_s + 2.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return {"combined_score": INVALID_SCORE, "valid": 0.0, "timeout": 1.0,
                    "error_message": "eval timeout > %ss" % timeout_s}
        if proc.returncode != 0 or not result_path.is_file():
            detail = (stderr or "").strip().splitlines()
            tail = detail[-1] if detail else "trusted evaluator failed"
            if "candidate timeout" in (stderr or ""):
                return {"combined_score": INVALID_SCORE, "valid": 0.0, "timeout": 1.0,
                        "error_message": "eval timeout > %ss" % timeout_s}
            return {"combined_score": INVALID_SCORE, "valid": 0.0,
                    "error_message": tail[-2000:]}
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            return validate_metrics(raw, score_mode)
        except Exception as exc:
            return {"combined_score": INVALID_SCORE, "valid": 0.0,
                    "error_message": "invalid trusted metrics: %s" % exc}
