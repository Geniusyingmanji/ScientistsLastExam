"""What the reference leaves on the table, and what picking it up actually costs.

`known_best.md` claims headroom in two places. Both are checked here rather than asserted.

    concentrate   the reference keeps sweeping all four patterns, so only a quarter of its rounds
                  are forks. How much does spending the whole budget on forks buy on the starved
                  parallel-snapshot worlds it declines?

    single        if concentrating were enough on its own, a candidate could skip the diagnosis and
                  hard-code one shape. Scores the reference's own decision rule with PATTERNS
                  narrowed, against the 90-per-cent admission bar.

    cycle         `CYCLE_MAX` bounds the anti-dependency cycles the analysis will chase. Raising it
                  should change the score if the bound is really costing anything.

    python3 .research/isolation_level_audit/budget.py [section ...]
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "benchmarks/ComputerScience/IsolationLevelAudit"
sys.path.insert(0, str(TASK))
sys.path.insert(0, str(TASK / "verification"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EV = _load(TASK / "verification/evaluator.py", "isolation_oracle")
REF = _load(TASK / "verification/reference_opportunity_audit.py", "isolation_reference")
ALL_PATTERNS = list(REF.PATTERNS)
FORK = [p for p in ALL_PATTERNS if p[0] == "fork"][0]
REPLICATES = 40


def _sweep(level, rate, seed, patterns):
    """A full-budget round-robin over `patterns`, returning the classes witnessed and the rounds."""
    run = EV._Bench(level, rate, seed, budget=EV.BUDGET).api()
    found, spent, key, i, rounds = set(), 0, 0, 0, 0
    while True:
        _name, fn, cost = patterns[i % len(patterns)]
        if spent + cost > EV.BUDGET:
            break
        try:
            txns, _gave = fn(run, key, key + 1)
        except Exception:                                   # noqa: BLE001 - budget exhausted
            break
        spent += cost
        key += 2
        i += 1
        rounds += 1
        found |= set(REF.analyze(txns))
    return found, rounds


def concentrate():
    """Long-fork hit rate on the starved parallel-snapshot worlds, balanced sweep against fork only.

    These are worlds the reference declines. A hit here is a world a better allocation settles.
    """
    print("%-8s %5s | %-20s | %-20s" % ("world", "rate", "balanced (4 shapes)", "fork only"))
    print("%-8s %5s | %9s %10s | %9s %10s"
          % ("", "", "long_fork", "rounds", "long_fork", "rounds"))
    for w in list(EV.DEVELOPMENT_WORLDS) + list(EV.HELDOUT_WORLDS):
        if w["settleable"] or w["level"] != "parallel_snapshot":
            continue
        hit_b = hit_f = rnd_b = rnd_f = 0
        for r in range(REPLICATES):
            seed = w["seed"] * 1000 + r
            found, rounds = _sweep(w["level"], w["rate"], seed, ALL_PATTERNS)
            hit_b += "long_fork" in found
            rnd_b += rounds
            found, rounds = _sweep(w["level"], w["rate"], seed, [FORK])
            hit_f += "long_fork" in found
            rnd_f += rounds
        print("%-8s %5.3f | %9.2f %10.1f | %9.2f %10.1f"
              % (w["name"], w["rate"], hit_b / REPLICATES, rnd_b / REPLICATES,
                 hit_f / REPLICATES, rnd_f / REPLICATES), flush=True)
    print("\n%d replicate seeds per world. Concentrating raises the number of fork rounds about "
          "fivefold\nwhile the total round count barely moves, because the other three shapes cost "
          "about what a fork does." % REPLICATES)


def single():
    """The reference's rule with PATTERNS narrowed, against the bar. Nothing here may clear it."""
    base = EV.evaluate(REF.audit)["combined_score"]
    print("reference %.4f, bar %.4f" % (base, 0.9 * base))
    print("%-18s %7s %7s %6s %6s %6s %s"
          % ("patterns kept", "dev", "held", "ok", "wrong", "dec", "share"))
    try:
        for keep in (["fork"], ["conflict"], ["repeat"], ["disjoint"], ["fork", "conflict"],
                     ["fork", "repeat"], ["conflict", "repeat"]):
            REF.PATTERNS = [p for p in ALL_PATTERNS if p[0] in keep]
            metrics = EV.evaluate(REF.audit)
            score = metrics["combined_score"]
            print("%-18s %7.4f %7.4f %6.2f %6.2f %6.2f  %3.0f%%%s"
                  % ("+".join(keep), score, metrics["heldout_mechanism_score"],
                     metrics["development_identification_rate"],
                     metrics["development_misidentification_rate"],
                     metrics["development_refusal_rate"], 100 * score / base,
                     "  OVER THE BAR" if score >= 0.9 * base else ""), flush=True)
    finally:
        REF.PATTERNS = ALL_PATTERNS
    print("\nNarrowing blindly costs more than it buys: the shapes that are dropped are the ones "
          "that rule\nout the other boundaries, so the rule declines worlds it used to name. "
          "Concentration pays only\nafter the level is diagnosed, which is the part that is not "
          "cheap.")


def cycle():
    """Whether CYCLE_MAX is costing anything at these pattern sizes."""
    try:
        for bound in (4, 6, 8, 12):
            REF.CYCLE_MAX = bound
            metrics = EV.evaluate(REF.audit)
            print("CYCLE_MAX=%-3d dev %.4f held %.4f wrong %.2f declined %.2f"
                  % (bound, metrics["combined_score"], metrics["heldout_mechanism_score"],
                     metrics["development_misidentification_rate"],
                     metrics["development_refusal_rate"]), flush=True)
    finally:
        REF.CYCLE_MAX = 4
    sizes = {}
    for name, fn, _cost in ALL_PATTERNS:
        run = EV._Bench("snapshot_isolation", 0.5, 7, budget=EV.BUDGET).api()
        sizes[name] = max(len(fn(run, k, k + 1)[0]) for k in range(0, 40, 2))
    print("\nmost transactions one round produces, by shape: %s" % sizes)
    print("A cycle cannot be longer than the round that made it, so the bound is not reached and "
          "raising\nit changes nothing.")


SECTIONS = {"concentrate": concentrate, "single": single, "cycle": cycle}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(SECTIONS):
        print("=" * 78)
        print(name)
        print("=" * 78)
        SECTIONS[name]()
