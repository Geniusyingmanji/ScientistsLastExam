"""Score independent blind first proposals against the reference.

Each candidate is a file defining `audit(problem, run)`, written by a model that saw only Task.md,
solution.py and frontier_eval/constraints.txt. The admission bar is that no first proposal reaches
90 per cent of the reference on the development split.

    python3 .research/isolation_level_audit/blind.py <candidate.py> [...]
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "benchmarks/ComputerScience/IsolationLevelAudit"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load(TASK / "verification/evaluator.py", "isolation_oracle")
ref = _load(TASK / "verification/reference_opportunity_audit.py", "isolation_reference")


def main(paths):
    base = ev.evaluate(ref.audit)["combined_score"]
    bar = 0.9 * base
    print("reference %.4f, bar %.4f" % (base, bar))
    print("%-24s %7s %7s %6s %6s %6s %s"
          % ("candidate", "dev", "held", "ok", "wrong", "dec", "share"))
    for path in paths:
        path = Path(path)
        try:
            module = _load(path, "blind_" + path.stem)
            metrics = ev.evaluate(module.audit)
        except Exception as exc:                          # noqa: BLE001
            print("%-24s failed to load: %s: %s" % (path.name, type(exc).__name__, exc))
            continue
        score = metrics["combined_score"]
        print("%-24s %7.4f %7.4f %6.2f %6.2f %6.2f  %3.0f%%%s"
              % (path.name, score, metrics["heldout_mechanism_score"],
                 metrics["development_identification_rate"],
                 metrics["development_misidentification_rate"],
                 metrics["development_refusal_rate"],
                 100 * score / max(1e-9, base),
                 "  OVER THE BAR" if score >= bar else ""), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
