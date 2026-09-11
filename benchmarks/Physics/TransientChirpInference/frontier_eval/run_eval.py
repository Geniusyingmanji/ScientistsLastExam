"""Black-box eval entrypoint for TransientChirpInference."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

INVALID = -1e18
TASK_ID = "Gravitation/TransientChirpInference"
ROOT = Path(__file__).resolve().parents[4]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--metrics-out", required=True)
    ap.add_argument("--timeout", type=float, default=360)
    args = ap.parse_args()
    metrics = {"combined_score": INVALID, "valid": 0.0}
    try:
        p = subprocess.run([sys.executable, "-m", "sle", "eval", "--allow-uncertified", "--task", TASK_ID,
                            "--candidate", str(Path(args.candidate).resolve()), "--timeout", str(args.timeout)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=args.timeout + 120,
                           env={**os.environ, "PYTHONPATH": str(ROOT)})
        if p.returncode:
            raise RuntimeError("sle eval exited %d: %s" % (p.returncode, p.stderr[-500:]))
        metrics.update(json.loads(p.stdout))
    except Exception as exc:
        metrics["error_message"] = "%s: %s" % (type(exc).__name__, exc)
    Path(args.metrics_out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics.get(k) for k in ("combined_score", "valid")}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
