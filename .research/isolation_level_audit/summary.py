"""Recompute every number Task.md and TASK_CARD.yaml quote for IsolationLevelAudit.

    python3 .research/isolation_level_audit/summary.py [section ...]

Sections: scores (the reference, the baseline and the probe grid), shifts (the same under
re-drawn world seeds), sound (no store ever exhibits a class its level forbids), power (the
opportunity and exposure rates the reference's thresholds are read off), detect (what a strategy
that never declines would answer, by level and weak rate).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "benchmarks" / "ComputerScience" / "IsolationLevelAudit"
sys.path.insert(0, str(TASK))
sys.path.insert(0, str(TASK / "verification"))

import reference_opportunity_audit as ref                      # noqa: E402
import probe_naive_refusal, probe_no_refusal                   # noqa: E402
import probe_round_count_power                                 # noqa: E402
import solution                                                # noqa: E402
from verification import evaluator as ev                       # noqa: E402

LADDER, PATTERNS, analyze, level_of = ref.LADDER, ref.PATTERNS, ref.analyze, ref.level_of


# ---- strategies that are measured but not shipped as probes ------------------------------------
def blanket_decline(problem, run):
    return {"abstain": True}


def _fixed(level):
    def f(problem, run):
        return {"level": level}
    return f


def per_key(problem, run):
    """Checks each key on its own: it can see a lost update or an intermediate read, but nothing
    that only shows up across keys, so the top of the ladder is invisible to it."""
    single = {"dirty_write", "aborted_read", "intermediate_read", "lost_update"}
    budget, spent, key, hits = problem["budget"], 0, 0, set()
    while spent + 14 <= budget:
        for _name, fn, cost in PATTERNS:
            if spent + cost > budget:
                break
            txns, _ = fn(run, key, key + 1)
            key += 2
            spent += cost
            hits |= set(analyze(txns)) & single
    return {"level": level_of(next((c for c in LADDER if c in hits), None))}


def abort_rate(problem, run):
    """No anomaly analysis at all: it watches which contention makes transactions abort, which it
    reads as whether the store certifies writes, reads, or neither."""
    budget, spent, key = problem["budget"], 0, 0
    ww = {"n": 0, "ab": 0}
    rw = {"n": 0, "ab": 0}
    while spent + 8 <= budget:
        t = run([[[["r", key], ["a", key]]], [[["r", key], ["a", key]]]])["transactions"]
        ww["n"] += len(t)
        ww["ab"] += sum(1 for x in t if x["status"] != "committed")
        t = run([[[["r", key], ["a", key + 1]]], [[["r", key + 1], ["a", key]]]])["transactions"]
        rw["n"] += len(t)
        rw["ab"] += sum(1 for x in t if x["status"] != "committed")
        key += 2
        spent += 8
    if ww["ab"] / max(1, ww["n"]) < 0.08:
        return {"level": "read_committed"}
    if rw["ab"] / max(1, rw["n"]) < 0.08:
        return {"level": "snapshot_isolation"}
    return {"level": "strict_serializable"}


def undesigned(problem, run):
    """Spends the whole budget on random traffic instead of designed contention, then analyses the
    history it happens to have."""
    budget, rng, spent, found = problem["budget"], random.Random(0), 0, set()
    while spent + 16 <= budget:
        chunk = []
        for _ in range(12):                    # analysed in chunks; one huge graph is intractable
            batch = []
            for _s in range(4):
                ops = [[rng.choice("ra"), rng.randrange(40)] for _ in range(rng.randrange(2, 5))]
                batch.append([ops])
                spent += len(ops)
            chunk += run(batch)["transactions"]
        found |= set(analyze(chunk))
    return {"level": level_of(next((c for c in LADDER if c in found), None))}


def tenth_budget(problem, run):
    """The reference design and the reference statistics, on a tenth of the budget."""
    return ref.audit(dict(problem, budget=problem["budget"] // 10), run)


GRID = [
    ("REFERENCE", ref.audit),
    ("baseline-symptom-scan (solution.py)", solution.audit),
    ("no-refusal", probe_no_refusal.audit),
    ("naive-refusal", probe_naive_refusal.audit),
    ("round-count-power", probe_round_count_power.audit),
    ("blanket-decline", blanket_decline),
    ("always-read-committed", _fixed("read_committed")),
    ("always-snapshot-isolation", _fixed("snapshot_isolation")),
    ("always-strict-serializable", _fixed("strict_serializable")),
    ("per-key-only", per_key),
    ("abort-rate-only", abort_rate),
    ("undesigned-traffic", undesigned),
    ("tenth-budget", tenth_budget),
]


# ---- sections -----------------------------------------------------------------------------------
def scores():
    print("%-38s %7s %7s %6s %6s %6s" % ("strategy", "dev", "held", "ok", "wrong", "dec"))
    base = None
    for name, fn in GRID:
        m = ev.evaluate(fn)
        if base is None:
            base = m["combined_score"]
        share = "" if name == "REFERENCE" else "  (%3.0f%% of reference)" % (
            100 * m["combined_score"] / max(1e-9, base))
        print("%-38s %7.4f %7.4f %6.2f %6.2f %6.2f%s" % (
            name, m["combined_score"], m["heldout_mechanism_score"],
            m["development_identification_rate"], m["development_misidentification_rate"],
            m["development_refusal_rate"], share), flush=True)


def axes():
    """The three discovery axes, read against what each world could have supported."""
    print("%-38s %7s %7s %7s  %7s %7s %7s" % (
        "strategy", "fdr", "refuse", "cover", "h_fdr", "h_ref", "h_cov"))
    for name, fn in GRID:
        m = ev.evaluate(fn)
        print("%-38s %7.3f %7.3f %7.3f  %7.3f %7.3f %7.3f" % (
            name, m["development_false_discovery_rate"], m["development_correct_refusal_rate"],
            m["development_discovery_coverage"], m["heldout_false_discovery_rate"],
            m["heldout_correct_refusal_rate"], m["heldout_discovery_coverage"]), flush=True)


def _shifted(worlds, shift):
    return tuple(dict(w, seed=w["seed"] + 7919 * shift) for w in worlds)


def shifts(n=4):
    dev0, held0 = ev.DEVELOPMENT_WORLDS, ev.HELDOUT_WORLDS
    print("%-38s %7s %7s %7s %7s %7s" % ("strategy", "dev", "dev_min", "held", "held_min", "wrong"))
    base = None
    try:
        for name, fn in GRID:
            rows, dev, held = [], [], []
            for s in range(int(n)):
                ev.DEVELOPMENT_WORLDS = _shifted(dev0, s)
                ev.HELDOUT_WORLDS = _shifted(held0, s)
                m = ev.evaluate(fn)
                dev.append(m["combined_score"])
                held.append(m["heldout_mechanism_score"])
                rows += m["per_instance"]
            if base is None:
                base = sum(dev) / len(dev)
            share = "" if name == "REFERENCE" else "  (%3.0f%% of reference)" % (
                100 * (sum(dev) / len(dev)) / max(1e-9, base))
            print("%-38s %7.4f %7.4f %7.4f %7.4f %7d%s" % (
                name, sum(dev) / len(dev), min(dev), sum(held) / len(held), min(held),
                sum(1 for r in rows if r["wrong"]), share), flush=True)
    finally:
        ev.DEVELOPMENT_WORLDS, ev.HELDOUT_WORLDS = dev0, held0
    print("(%d world-runs per strategy)" % (int(n) * (len(dev0) + len(held0))))


def sound(rounds=300):
    """No store may exhibit a class its level forbids; otherwise a correct reading names the wrong
    level."""
    total = 0
    for level in ev.LEVELS:
        for rate in (0.10, 0.30, 0.50):
            for seed in (11, 12, 13):
                bench = ev._Bench(level, rate, seed, budget=10 ** 7)
                run, k = bench.api(), 0
                for _ in range(int(rounds)):
                    for _name, fn, _cost in PATTERNS:
                        txns, _gave = fn(run, k, k + 1)
                        k += 2
                        extra = set(analyze(txns)) - ev.allowed(level)
                        if extra:
                            total += 1
                            print("VIOLATION %-21s p=%.2f seed=%d %s" % (
                                level, rate, seed, sorted(extra)))
        print("checked %-21s" % level, flush=True)
    print("total violations:", total)


def power(rounds=500):
    """opportunity: how often a round really raced two weak transactions, which is what the budget
    buys. expose: given such a round, how often the store's own level gives itself away."""
    print("%-21s %5s %8s %8s" % ("level", "p", "opp/rnd", "expose"))
    for level in ev.LEVELS[:-1]:
        for rate in (0.10, 0.20, 0.35, 0.50):
            bench = ev._Bench(level, rate, 21, budget=10 ** 8)
            run, k, opp, fired = bench.api(), 0, 0, 0
            for _ in range(int(rounds)):
                for _name, fn, _cost in PATTERNS:
                    txns, gave = fn(run, k, k + 1)
                    k += 2
                    if not gave.get(level):
                        continue
                    opp += 1
                    if any(ev.PIN[c] == level for c in analyze(txns)):
                        fired += 1
            print("%-21s %5.2f %8.3f %8.2f" % (
                level, rate, opp / int(rounds), fired / max(1, opp)), flush=True)


def detect(seeds=10):
    """What a strategy that probes hard and never declines would answer, by level and weak rate."""
    rates = [0.04, 0.07, 0.10, 0.14, 0.20, 0.30, 0.45]
    print("%-21s %s" % ("level", " ".join("%7.3f" % r for r in rates)))
    for level in ev.LEVELS[:-1]:
        row = []
        for rate in rates:
            ok = 0
            for s in range(int(seeds)):
                bench = ev._Bench(level, rate, 300 + s)
                got = probe_no_refusal.audit(ev.public_problem(), bench.api())
                ok += got.get("level") == level
            row.append("%7.2f" % (ok / int(seeds)))
        print("%-21s %s" % (level, " ".join(row)), flush=True)


SECTIONS = {"scores": scores, "axes": axes, "shifts": shifts, "sound": sound, "power": power,
            "detect": detect}

if __name__ == "__main__":
    args = sys.argv[1:] or list(SECTIONS)
    for name in args:
        print("=" * 78)
        print(name)
        print("=" * 78)
        SECTIONS[name]()
