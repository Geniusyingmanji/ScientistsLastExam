"""Why the reference solves its LPs with revised simplex, and what that costs in score.

    .venv/bin/python .research/clock_sync/solver_check.py [run seed shift ...]

Part one counts the native threads of this process before and after one `linprog(method="highs")`
call. The candidate sandbox denies clone/clone3 (sle/secure_eval.py, `_seccomp_no_processes`),
so a solver that starts worker threads dies there with `candidate_worker_exit`.

Part two evaluates the package reference twice per shift, once with its own solver and once with
every `linprog` call redirected to HiGHS on the same rows, objective and bounds, and prints the
largest per-world difference in mechanism score, whether every verdict agrees, and any world where
either solver raised. HiGHS is the comparison because it is the solver the oracle itself uses.
"""
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import scipy.optimize as so

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from pkg_eval import ref, run  # noqa: E402

warnings.simplefilter("ignore")


def native_threads():
    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text().splitlines():
            if line.startswith("Threads:"):
                return int(line.split()[1])
    out = subprocess.run(["ps", "-M", str(os.getpid())], capture_output=True, text=True).stdout
    return len(out.strip().splitlines()) - 1


def highs(c, **kw):
    kw.pop("method", None)
    kw.pop("options", None)
    return so.linprog(c, method="highs", **kw)


def evaluate(shift):
    start = time.time()
    metrics = run(ref.identify, shift)
    rows = metrics["per_instance"]
    return {"dev": metrics["development_mechanism_score"], "held": metrics["heldout_mechanism_score"],
            "seconds": time.time() - start,
            "scores": [r["mechanism_score"] for r in rows],
            "verdicts": [(r["false_discovery"], r.get("correct_refusal")) for r in rows],
            "errors": [r["split"][0] + "%02d" % (r["world_index"] + 1) for r in rows if r.get("reason")]}


if __name__ == "__main__":
    before = native_threads()
    so.linprog([1.0, 1.0], A_ub=[[-1.0, -1.0]], b_ub=[-1.0], method="highs")
    print("native threads before one HiGHS call %d, after %d" % (before, native_threads()))
    package = ref.linprog
    worst = 0.0
    for shift in [int(x) for x in sys.argv[1:]] or [0, 1, 2, 3, 4, 5, 6, 7]:
        ref.linprog = package
        own = evaluate(shift)
        ref.linprog = highs
        other = evaluate(shift)
        ref.linprog = package
        diff = max(abs(a - b) for a, b in zip(own["scores"], other["scores"]))
        worst = max(worst, diff)
        print("shift %d: package dev %.6f held %.6f (%.1f s) | highs dev %.6f held %.6f (%.1f s) | "
              "max world diff %.2e | verdicts %s | errors package %s highs %s" % (
                  shift, own["dev"], own["held"], own["seconds"], other["dev"], other["held"], other["seconds"],
                  diff, "same" if own["verdicts"] == other["verdicts"] else "DIFFER", own["errors"], other["errors"]),
              flush=True)
    print("largest per-world difference over all shifts %.2e" % worst)
