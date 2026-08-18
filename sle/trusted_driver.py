"""Internal trusted-evaluation subprocess.

The outer harness supervises this process by wall clock.  It owns the oracle and starts
the nested candidate sandbox; the candidate cannot see its result path or command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path

from .secure_eval import (
    CandidateError,
    INVALID_SCORE,
    sanitized_candidate_failure,
    trusted_evaluate,
)
from .evaluate import canonical_trusted_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--score-mode", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--trusted-context", type=Path, default=None)
    args = parser.parse_args()
    trusted_context_sha256 = None
    try:
        trusted_context = None
        if args.trusted_context is not None:
            trusted_context = json.loads(
                args.trusted_context.read_text(encoding="utf-8")
            )
            context_payload = canonical_trusted_context(trusted_context)
            trusted_context_sha256 = hashlib.sha256(context_payload).hexdigest()
        metrics = trusted_evaluate(
            args.task_dir.resolve(), args.candidate.resolve(), args.entrypoint,
            args.score_mode, args.timeout, trusted_context=trusted_context,
        )
    except (CandidateError, TimeoutError) as exc:
        metrics = sanitized_candidate_failure(exc)
    except Exception:
        # Trusted evaluator failures are infrastructure errors, not candidate feedback.
        # Keep the outward record fixed so evaluator internals and hidden values cannot be
        # exposed through an exception string.
        #
        # The traceback goes to stderr instead, which the trusted parent captures and only ever
        # reports on the path that aborts the run. Keeping it out of this dictionary is what makes
        # the separation structural rather than a rule someone has to remember: nothing a
        # candidate could reach ever holds it. Without it, four runs in a 129-block sweep died
        # saying only "trusted evaluator internal failure", which names no task, no line and no
        # cause, and invalidated the whole campaign's report.
        traceback.print_exc(file=sys.stderr)
        metrics = {
            "combined_score": INVALID_SCORE,
            "valid": 0.0,
            "error_message": "trusted evaluator internal failure",
            "infrastructure_failure": 1.0,
        }
    if trusted_context_sha256 is not None:
        metrics["trusted_context_sha256"] = trusted_context_sha256
    args.result.write_text(json.dumps(metrics, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
