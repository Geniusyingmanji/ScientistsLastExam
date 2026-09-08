"""CLI bridge for tasks supported by ``sle eval`` and its candidate sandbox.

Never import candidates here. Legacy in-process oracle/CandidateProxy wrappers
must first migrate to that trusted protocol. The public file/stdout contain only
search-visible metrics; task-specific fields (including beat_sota) are preserved
in a trusted sidecar, not implicitly added to the search allowlist. Harnesses
must keep the sidecar directory outside the proposal agent's readable workspace.

Task-local wrappers launch this file using only the standard library, preserving
an explicit TASK_ID and EVAL_TIMEOUT_S. Exit 2 means evaluation infrastructure
failed: no score file or stdout score is produced, including on import failure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path


SENSITIVE_MARKERS = ("API_KEY", "AUTHORIZATION", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
CANDIDATE_FAILURES = frozenset((
    "candidate_timeout", "blocked_or_missing_import", "blocked_operation",
    "blocked_or_missing_file", "non_finite_candidate_value",
    "candidate_callback_schema_error", "candidate_response_too_large",
    "candidate_worker_exit", "candidate_runtime_error",
))


def _public_error(result):
    kind = result.get("candidate_failure_kind")
    if isinstance(kind, str) and kind in CANDIDATE_FAILURES:
        return "candidate invalid: " + kind
    if result.get("timeout"):
        return "candidate evaluation timed out"
    return "evaluation rejected; details retained in trusted diagnostics"


def run(task_id: str, root: Path, timeout: float, argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--full-metrics-dir")
    parser.add_argument("--timeout", type=float, default=timeout)
    args = parser.parse_args(argv)
    output = Path(args.metrics_out).resolve()
    trusted = (Path(args.full_metrics_dir).resolve() if args.full_metrics_dir else
               output.parent / ".trusted_metrics" / task_id.replace("/", "_"))
    stage = "initialization"
    diagnostic = {}
    try:
        # Never let a failed attempt leave a previous candidate's usable score.
        output.unlink(missing_ok=True)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        root = root.resolve()
        sys.path.insert(0, str(root))
        # Delayed imports keep package initialization failures on the no-score path.
        stage = "loading trusted evaluation support"
        from sle.metric_visibility import search_visible_metrics, store_full_metrics

        candidate = Path(args.candidate).resolve()
        environment = {k: v for k, v in os.environ.items()
                       if not any(marker in k.upper() for marker in SENSITIVE_MARKERS)}
        environment["PYTHONPATH"] = str(root)
        stage = "launching trusted evaluation"
        done = subprocess.run(
            [sys.executable, "-m", "sle", "eval", "--task", task_id,
             "--allow-uncertified", "--candidate", str(candidate),
             "--timeout", str(args.timeout)],
            cwd=str(root), capture_output=True, text=True,
            timeout=args.timeout + 120, env=environment,
        )
        diagnostic.update(returncode=done.returncode, stderr=(done.stderr or "")[-4000:])
        if done.returncode:
            raise RuntimeError("trusted evaluation exited %d" % done.returncode)
        stage = "reading trusted evaluation result"
        result = json.loads(done.stdout)
        if not isinstance(result, dict):
            raise ValueError("metrics must be a JSON object")
        diagnostic["metrics"] = result
        if result.get("infrastructure_failure"):
            raise RuntimeError("trusted evaluator reported infrastructure failure")
        # Defensive validation for alternate/future trusted CLI implementations.
        for key in ("combined_score", "valid"):
            value = result.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("metrics require a finite numeric %s" % key)
        result.setdefault("raw_score", result["combined_score"])
        if "error_message" in result:
            result["trusted_error_message"] = result["error_message"]
            result["error_message"] = _public_error(result)
        public = search_visible_metrics(result)
        stage = "persisting trusted metrics"
        trusted.mkdir(parents=True, exist_ok=True, mode=0o700)
        if candidate.is_file():
            store_full_metrics(trusted, candidate, result)
        else:
            # A missing candidate has no source digest; retain its failed attempt.
            (trusted / "last_missing_candidate.json").write_text(
                json.dumps(result, indent=2, default=str), encoding="utf-8")
        stage = "writing public metrics"
        rendered = json.dumps(public, indent=2, default=str, allow_nan=False)
        output.write_text(rendered, encoding="utf-8")
        print(json.dumps(public, default=str, allow_nan=False))
        return 0
    except Exception as exc:
        diagnostic.update(stage=stage, exception_type=type(exc).__name__, message=str(exc))
        try:
            output.unlink(missing_ok=True)
            trusted.mkdir(parents=True, exist_ok=True, mode=0o700)
            (trusted / "last_infrastructure_failure.json").write_text(
                json.dumps(diagnostic, indent=2, default=str), encoding="utf-8")
        except OSError:
            pass
        # Only controlled text reaches the search harness; traceback/source/env
        # from contributed trusted code is never a public diagnostic string.
        print("evaluation infrastructure failure during " + stage, file=sys.stderr)
        return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    args, remaining = parser.parse_known_args(argv)
    return run(args.task, args.root, args.timeout, remaining)


if __name__ == "__main__":
    raise SystemExit(main())
