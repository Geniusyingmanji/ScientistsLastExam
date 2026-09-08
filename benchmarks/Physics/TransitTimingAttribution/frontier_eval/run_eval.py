"""Use the trusted driver and sandbox; never import a candidate beside the oracle."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

TASK_ID = "Exoplanets/TransitTimingAttribution"
ROOT = Path(__file__).resolve().parents[4]
EVAL_TIMEOUT_S = 300


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S)
    args = parser.parse_args()
    metrics = {"combined_score": 0.0, "valid": 0.0}
    exit_code = 0
    try:
        result = subprocess.run(
            [sys.executable, "-m", "sle", "eval", "--allow-uncertified", "--task", TASK_ID,
             "--candidate", str(Path(args.candidate).resolve()), "--timeout", str(args.timeout)],
            cwd=ROOT, capture_output=True, text=True, timeout=args.timeout + 120,
            env={**os.environ, "PYTHONPATH": str(ROOT)})
        if result.returncode:
            exit_code = result.returncode
            raise RuntimeError("sle eval exited %d: %s" % (exit_code, result.stderr[-500:]))
        metrics.update(json.loads(result.stdout))
    except Exception as exc:
        exit_code = exit_code or 1
        metrics["error_message"] = "%s: %s" % (type(exc).__name__, exc)
    Path(args.metrics_out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("combined_score", "valid")}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
