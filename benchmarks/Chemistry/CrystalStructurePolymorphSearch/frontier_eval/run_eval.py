"""Launch the shared trusted evaluator without importing project code."""
import argparse
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK_ID = "MaterialsScience/CrystalStructurePolymorphSearch"
EVAL_TIMEOUT_S = 300

if TASK_ID.split("/")[-1] != Path(__file__).resolve().parents[1].name:
    raise SystemExit("TASK_ID does not name this task directory")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--timeout", type=float, default=EVAL_TIMEOUT_S)
    parser.add_argument("--full-metrics-dir")
    args = parser.parse_args(argv)
    command = [sys.executable, str(ROOT / "sle/frontier_eval_entrypoint.py"),
               "--task", TASK_ID, "--root", str(ROOT), "--timeout", str(args.timeout),
               "--candidate", args.candidate, "--metrics-out", args.metrics_out]
    if args.full_metrics_dir:
        command.extend(["--full-metrics-dir", args.full_metrics_dir])
    try:
        Path(args.metrics_out).unlink(missing_ok=True)
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            return 2
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=args.timeout + 150)
        if result.returncode:
            Path(args.metrics_out).unlink(missing_ok=True)
            print("evaluation infrastructure failure", file=sys.stderr)
            return 2
        print(result.stdout, end="")
        return 0
    except (OSError, subprocess.TimeoutExpired):
        Path(args.metrics_out).unlink(missing_ok=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

