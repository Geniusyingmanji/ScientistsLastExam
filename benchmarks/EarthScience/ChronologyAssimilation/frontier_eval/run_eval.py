"""Launch the shared trusted evaluator without importing project code."""
import argparse
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK_ID = 'Paleoclimate/ChronologyAssimilation'
EVAL_TIMEOUT_S = 300


# The task id is written in, where the previous template derived everything from __file__.
# That is deliberate - `sle eval` needs the registered id, not a path - but it means a wrapper
# copied to a neighbouring task keeps pointing at the task it came from, and scores the new
# candidate against the old oracle without complaining. The directory name is the second half
# of the id, so the copy is cheap to catch here rather than in whoever reads the numbers.
_expected_task = Path(__file__).resolve().parents[1].name
if TASK_ID.split("/")[-1] != _expected_task:
    raise SystemExit(
        "TASK_ID %r does not name this directory (%r); this wrapper was copied from another"
        " task and would score against that task's oracle" % (TASK_ID, _expected_task))


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
            print("evaluation timeout must be positive and finite", file=sys.stderr)
            return 2
        result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout + 150)
        if result.returncode:
            Path(args.metrics_out).unlink(missing_ok=True)
            print("evaluation entrypoint unavailable or infrastructure failure (exit %d)"
                  % result.returncode, file=sys.stderr)
            return 2
        print(result.stdout, end="")
        return 0
    except (OSError, subprocess.TimeoutExpired):
        try:
            Path(args.metrics_out).unlink(missing_ok=True)
        except OSError:
            pass
        print("evaluation entrypoint could not be launched or report cleared", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
