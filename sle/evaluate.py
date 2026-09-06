"""Secure black-box candidate evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .runtime_identity import (
    TrustedRuntime,
    task_runtime_distributions,
    validate_runtime_descriptor,
)
from .secure_eval import INVALID_SCORE, validate_metrics
from .spec import TaskSpec


MAX_TRUSTED_CONTEXT_BYTES = 1024 * 1024


def canonical_trusted_context(value: dict[str, Any]) -> bytes:
    """Return the bounded canonical JSON representation used for context binding.

    A trusted context may contain a fresh-world manifest or an external validation
    cohort.  It belongs to the host evaluator, never to the candidate sandbox.  The
    canonical representation gives the caller, trusted driver and result report one
    unambiguous commitment hash.
    """
    if not isinstance(value, dict):
        raise TypeError("trusted evaluation context must be a JSON object")
    try:
        rendered = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted evaluation context must contain finite JSON values") from exc
    if len(rendered) > MAX_TRUSTED_CONTEXT_BYTES:
        raise ValueError("trusted evaluation context exceeds the size limit")
    return rendered


def _trusted_python() -> str:
    """Use the configured oracle entrypoint, or the invoking interpreter when unset."""
    configured = os.environ.get("FRONTIER_SCIENCE_TRUSTED_PYTHON")
    selected = configured or sys.executable
    # Keep the virtualenv entrypoint. Resolving its symlink selects the base
    # interpreter instead and drops the pinned oracle site-packages.
    return str(Path(selected).expanduser().absolute())


def resolve_trusted_runtime(task_dir: Path | None = None) -> TrustedRuntime:
    """Resolve and inspect the interpreter that will execute the trusted oracle."""

    executable = _trusted_python()
    distributions = task_runtime_distributions(task_dir)
    completed = subprocess.run(
        [executable, "-m", "sle.runtime_identity", *distributions],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("trusted evaluator runtime identity probe failed")
    try:
        descriptor = validate_runtime_descriptor(json.loads(completed.stdout))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("trusted evaluator runtime identity probe is invalid") from exc
    return TrustedRuntime(executable=executable, descriptor=descriptor)


def evaluate_candidate(
    spec: TaskSpec,
    candidate_path: Path,
    timeout_s: float = 300.0,
    *,
    trusted_context: dict[str, Any] | None = None,
    trusted_runtime: TrustedRuntime | None = None,
) -> dict[str, Any]:
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
    context_payload = None
    if trusted_context is not None:
        try:
            context_payload = canonical_trusted_context(trusted_context)
        except (TypeError, ValueError):
            return {
                "combined_score": INVALID_SCORE,
                "valid": 0.0,
                "error_message": "invalid trusted evaluation context",
                "infrastructure_failure": 1.0,
            }
    try:
        runtime = trusted_runtime or resolve_trusted_runtime(spec.task_dir)
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return {
            "combined_score": INVALID_SCORE,
            "valid": 0.0,
            "error_message": "trusted evaluator runtime identity unavailable",
            "infrastructure_failure": 1.0,
        }
    score_mode = str(spec.metadata.get("score_mode", "clipped"))
    with tempfile.TemporaryDirectory(prefix="fs_trusted_") as tmp:
        result_path = Path(tmp) / "metrics.json"
        cmd = [
            runtime.executable, "-m", "sle.trusted_driver",
            "--task-dir", str(spec.task_dir), "--candidate", str(candidate_path),
            "--entrypoint", spec.entrypoint, "--score-mode", score_mode,
            "--timeout", str(timeout_s), "--result", str(result_path),
            "--expected-runtime-sha256", runtime.fingerprint_sha256,
        ]
        if context_payload is not None:
            context_path = Path(tmp) / "trusted_context.json"
            context_path.write_bytes(context_payload)
            cmd += ["--trusted-context", str(context_path)]
        trusted_environment = dict(os.environ)
        trusted_environment.update({
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        })
        proc = subprocess.Popen(
            cmd, cwd=str(Path(__file__).resolve().parent.parent),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, start_new_session=True, env=trusted_environment,
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
            if "candidate timeout" in (stderr or ""):
                return {"combined_score": INVALID_SCORE, "valid": 0.0, "timeout": 1.0,
                        "error_message": "candidate invalid: candidate_timeout",
                        "candidate_failure_kind": "candidate_timeout"}
            # Carry why. An infrastructure failure aborts the whole run rather than scoring a
            # candidate, so nothing here reaches the searcher and there is no label-blindness to
            # protect - but without it the abort says only "process failure", and two runs died
            # that way under concurrent cohorts with nothing to diagnose from.
            detail = (stderr or "").strip().splitlines()
            return {"combined_score": INVALID_SCORE, "valid": 0.0,
                    "error_message": "trusted evaluator process failure (rc=%s): %s"
                                     % (proc.returncode, " | ".join(detail[-3:])[:400]
                                        or "no stderr"),
                    "infrastructure_failure": 1.0}
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            if (
                not isinstance(raw, dict)
                or raw.get("trusted_evaluator_runtime_sha256")
                != runtime.fingerprint_sha256
            ):
                return {
                    "combined_score": INVALID_SCORE,
                    "valid": 0.0,
                    "error_message": "trusted evaluator runtime binding mismatch",
                    "infrastructure_failure": 1.0,
                }
            if set(raw) != {
                "schema_version", "trusted_evaluator_runtime_sha256", "metrics"
            } or raw.get("schema_version") != 1 or not isinstance(raw.get("metrics"), dict):
                raise ValueError("trusted evaluator result envelope is invalid")
            # The driver keeps its outward message fixed so nothing a candidate could read holds
            # evaluator internals, and it writes the cause to its stderr instead. Surface that to
            # the operator's log without putting it in `metrics`: an earlier attempt merged it
            # into `error_message`, which reaches the ledger and the trajectory, and a test
            # caught it leaking the oracle's entrypoint name. The record a candidate can reach
            # stays fixed; the log says why.
            if raw["metrics"].get("infrastructure_failure") and (stderr or "").strip():
                print("trusted evaluator failure in %s:\n%s"
                      % (spec.task_id, (stderr or "").strip()[-2000:]), file=sys.stderr)
            metrics = validate_metrics(raw["metrics"], score_mode)
            if context_payload is not None:
                expected = hashlib.sha256(context_payload).hexdigest()
                if metrics.get("trusted_context_sha256") != expected:
                    return {
                        "combined_score": INVALID_SCORE,
                        "valid": 0.0,
                        "error_message": "trusted context binding mismatch",
                        "infrastructure_failure": 1.0,
                    }
            return metrics
        except Exception as exc:
            return {"combined_score": INVALID_SCORE, "valid": 0.0,
                    "error_message": "invalid trusted metrics: %s" % exc}
