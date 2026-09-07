"""Shared CLI for task-local frontier evaluation wrappers.

Always launch ``sle eval`` in a subprocess: it owns the candidate sandbox.
Importing a candidate directly here would execute untrusted code in the trusted
oracle process and bypass that isolation, even for a convenience CLI.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path


def run(task_id: str, root: Path, timeout: float = 300.0) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=timeout)
    args = parser.parse_args()
    metrics = {"combined_score": -1e18, "valid": 0.0}
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        root = root.resolve()
        done = subprocess.run(
            [sys.executable, "-m", "sle", "eval", "--task", task_id,
             "--allow-uncertified", "--candidate", str(Path(args.candidate).resolve()),
             "--timeout", str(args.timeout)],
            cwd=str(root), capture_output=True, text=True,
            timeout=args.timeout + 120,
            env={**os.environ, "PYTHONPATH": str(root)},
        )
        if done.returncode:
            raise RuntimeError(
                "sle eval exited %d: %s"
                % (done.returncode, (done.stderr or "").strip()[-500:])
            )
        result = json.loads(done.stdout)
        # Validate before updating so malformed evaluator output cannot leave a
        # partially successful result in the failure report.
        if not isinstance(result, dict):
            raise ValueError("sle eval metrics must be a JSON object")
        for key in ("combined_score", "valid"):
            value = result.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("sle eval metrics require a finite numeric %s" % key)
        metrics.update(result)
        metrics.setdefault("raw_score", metrics["combined_score"])
    except Exception as exc:
        metrics["error_message"] = "%s: %s" % (type(exc).__name__, exc)
    try:
        Path(args.metrics_out).write_text(
            json.dumps(metrics, indent=2, default=str), encoding="utf-8"
        )
    except OSError as exc:
        # A failed report write must be visible to the caller, including when an
        # older metrics file still exists at this path.
        print("cannot write metrics: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    print(json.dumps({key: metrics.get(key) for key in ("combined_score", "valid")}))
    return 0
