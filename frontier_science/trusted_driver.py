"""Internal trusted-evaluation subprocess.

The outer harness supervises this process by wall clock.  It owns the oracle and starts
the nested candidate sandbox; the candidate cannot see its result path or command line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .secure_eval import (
    CandidateError,
    INVALID_SCORE,
    sanitized_candidate_failure,
    trusted_evaluate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--score-mode", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        metrics = trusted_evaluate(
            args.task_dir.resolve(), args.candidate.resolve(), args.entrypoint,
            args.score_mode, args.timeout,
        )
    except (CandidateError, TimeoutError) as exc:
        metrics = sanitized_candidate_failure(exc)
    except Exception:
        # Trusted evaluator failures are infrastructure errors, not candidate feedback.
        # Keep the outward record fixed so evaluator internals and hidden values cannot be
        # exposed through an exception string.
        metrics = {
            "combined_score": INVALID_SCORE,
            "valid": 0.0,
            "error_message": "trusted evaluator internal failure",
            "infrastructure_failure": 1.0,
        }
    args.result.write_text(json.dumps(metrics, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
