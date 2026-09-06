"""Trusted CLI wrapper for GoldenGateAssemblyFrontier."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

INVALID = -1e18
TASK_ID = "SyntheticBiology/GoldenGateAssemblyFrontier"
ROOT = Path(__file__).resolve().parents[4]
EVAL_TIMEOUT_S = 30


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S)
    args = parser.parse_args()
    metrics = {"combined_score": INVALID, "valid": 0.0}
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "sle",
                "eval",
                "--task",
                TASK_ID,
                "--allow-uncertified",
                "--candidate",
                str(Path(args.candidate).resolve()),
                "--timeout",
                str(args.timeout),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=args.timeout + 120,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"sle eval exited {completed.returncode}: "
                f"{(completed.stderr or '').strip()[-500:]}"
            )
        metrics.update(json.loads(completed.stdout))
        metrics.setdefault("raw_score", metrics.get("combined_score"))
    except Exception as exc:  # noqa: BLE001 - evaluation failure is reported as data
        metrics["error_message"] = f"{type(exc).__name__}: {exc}"
    Path(args.metrics_out).write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({key: metrics.get(key) for key in ("combined_score", "valid")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
