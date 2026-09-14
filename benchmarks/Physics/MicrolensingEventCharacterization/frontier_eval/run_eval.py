"""Launch the shared trusted evaluator."""
import argparse
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "Exoplanets/MicrolensingEventCharacterization"
EVAL_TIMEOUT_S = 360

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True); p.add_argument("--metrics-out", required=True)
    p.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S); p.add_argument("--full-metrics-dir")
    a = p.parse_args(argv)
    if not math.isfinite(a.timeout) or a.timeout <= 0: return 2
    cmd = [sys.executable, str(ROOT / "sle/frontier_eval_entrypoint.py"), "--task", TASK_ID,
           "--root", str(ROOT), "--timeout", str(a.timeout), "--candidate", a.candidate,
           "--metrics-out", a.metrics_out]
    if a.full_metrics_dir: cmd += ["--full-metrics-dir", a.full_metrics_dir]
    try:
        Path(a.metrics_out).unlink(missing_ok=True)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout + 150)
        if r.returncode:
            Path(a.metrics_out).unlink(missing_ok=True); return 2
        print(r.stdout, end=""); return 0
    except (OSError, subprocess.TimeoutExpired):
        Path(a.metrics_out).unlink(missing_ok=True); return 2

if __name__ == "__main__":
    raise SystemExit(main())
