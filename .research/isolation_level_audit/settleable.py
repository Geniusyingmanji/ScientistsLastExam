"""Which worlds can be settled at all, measured without asking the reference.

A world is settleable when the budget is enough to tell its level apart from everything below it.
That is two separate questions, and both are answered by running a fixed round-robin protocol, not
by the reference's own thresholds:

    reach       does the protocol witness the class that pins the world's own level? Without it the
                verdict never climbs to the truth. (Strict serializable has no class of its own, so
                this clause is vacuous there.)

    separate    for every level below the truth, would a store at *that* level, with the same weak
                rate and the same seed, have given itself away to the same protocol? If it would
                not, then a quiet run here is not evidence against it and no auditor can rule it
                out. (Read uncommitted has nothing below it, so this clause is vacuous there.)

Both are properties of the store and the budget. Neither mentions the reference's MIN_OPP, its
sweep, or its allocation, so a world labelled unsettleable here is one where *declining is the only
answer that is not a guess*, whoever is asking.

    python3 .research/isolation_level_audit/settleable.py [replicates]

`replicates` defaults to the 50 the task card and `known_best.md` quote. Ten is quick but noisy
enough to push a settleable world onto the 0.80 edge, so a smaller count reproduces neither.
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


EV = _load(TASK / "verification/evaluator.py", "isolation_oracle")
REF = _load(TASK / "verification/reference_opportunity_audit.py", "isolation_reference")

OWN = {lv: [c for c, pin in REF.PIN.items() if pin == lv] for lv in EV.LEVELS}


def sweep(level, rate, seed):
    """Round-robin the four patterns until the budget runs out; return the classes witnessed."""
    bench = EV._Bench(level, rate, seed, budget=EV.BUDGET)
    run = bench.api()
    found, spent, key, i = set(), 0, 0, 0
    while True:
        name, fn, cost = REF.PATTERNS[i % len(REF.PATTERNS)]
        if spent + cost > EV.BUDGET:
            break
        try:
            txns, _gave = fn(run, key, key + 1)
        except Exception:                      # the ledger closed mid-pattern
            break
        spent += cost
        key += 2
        i += 1
        found |= set(REF.analyze(txns))
    return found


def caught(level, rate, seed):
    """Did a store at this level exhibit a class that pins it?"""
    return bool(set(OWN[level]) & sweep(level, rate, seed))


def decide(level, rate, seed):
    """Settleability of one draw. The store is seeded, so the protocol on it is deterministic."""
    below = EV.LEVELS[:EV.LEVELS.index(level)]
    if OWN[level] and not caught(level, rate, seed):
        return False
    return all(caught(m, rate, seed) for m in below)


def settleable(level, rate, seed, replicates):
    """The share of re-drawn worlds at this level and rate that a full budget could settle.

    One draw is not the answer: a single protocol run at a level and rate the budget comfortably
    covers still fails now and then, so a label read off the world's own seed alone flips on noise.
    The share over re-drawn seeds is the property of the (level, rate, budget) triple that the
    label is meant to carry.
    """
    return sum(decide(level, rate, seed * 1000 + r) for r in range(replicates)) / replicates


# A world is settleable above the upper edge and starved below the lower one. Nothing may land in
# between: a label that turns on where the line was drawn is not a label worth scoring against.
SETTLED = 0.80
STARVED = 0.35


def main(replicates):
    print("%-8s %-22s %5s %6s  %-10s %s"
          % ("world", "level", "rate", "share", "settleable", "declared"))
    bad = []
    for split in (EV.DEVELOPMENT_WORLDS, EV.HELDOUT_WORLDS):
        for w in split:
            share = settleable(w["level"], w["rate"], w["seed"], replicates)
            label = True if share >= SETTLED else (False if share < STARVED else None)
            note = "ok"
            if label is None:
                note = "AMBIGUOUS, %.2f is between %.2f and %.2f" % (share, STARVED, SETTLED)
                bad.append(w["name"])
            elif label != w["settleable"]:
                note = "DISAGREES with the evaluator"
                bad.append(w["name"])
            print("%-8s %-22s %5.3f %6.2f  %-10s %s"
                  % (w["name"], w["level"], w["rate"], share,
                     {True: "yes", False: "no", None: "?"}[label], note))
    print()
    if bad:
        print("the world set is not clean: %s" % ", ".join(bad))
    else:
        print("every settleable flag in the evaluator matches the measurement, "
              "and no world sits between %.2f and %.2f" % (STARVED, SETTLED))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
