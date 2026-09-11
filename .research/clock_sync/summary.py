"""Every number the task's documents quote, recomputed from the recorded runs and a fresh evaluation.

    .venv/bin/python .research/clock_sync/summary.py
"""
import collections
import json
import statistics as st
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from pkg_eval import base, ev, ref  # noqa: E402


def jsonl(name):
    return [json.loads(line) for line in open(HERE / name)]


def counted(identify):
    calls = collections.Counter()

    def wrapped(problem, exchange, wait):
        def e(*a):
            calls["exchange"] += 1
            return exchange(*a)

        def w(*a):
            calls["wait"] += 1
            return wait(*a)
        return identify(problem, e, w)
    return wrapped, calls


for name, identify in (("reference", ref.identify), ("baseline", base.identify)):
    wrapped, calls = counted(identify)
    start = time.time()
    m = ev.evaluate(wrapped)
    print(name, "%.1f s" % (time.time() - start), {k: round(v, 4) for k, v in m.items() if isinstance(v, float)})
    print("  rows", [(r["split"][0] + "%02d" % (r["world_index"] + 1), r["kind"][:3], r["mechanism_score"], r["probes_used"]) for r in m["per_instance"]])
    print("  calls", dict(calls), "max probes", max(r["probes_used"] for r in m["per_instance"]))

print("worlds")
for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
    w = ev._world(spec)
    extra = ("widths us " + " ".join("%.2f" % x for x in w["widths"][1:] * 1e6)) if w["kind"] == "supported" else \
        "%s kappa* %.1f" % (w["fault"], ev.detectability(w))
    print("  %-8s N=%d links=%2d calibrated=%d soft=%d %s" % (spec["name"], w["N"], len(w["links"]), len(w["calibrated"]),
                                                             int((w["sigma"] > 1e-6).sum()), extra))

for f, label in (("pkg_reference_robust.jsonl", "reference"), ("pkg_baseline_robust.jsonl", "baseline")):
    rs = jsonl(f)
    d, h = [r["dev"] for r in rs], [r["held"] for r in rs]
    print("%s robustness: shifts %d dev mean %.4f [%.4f, %.4f] held mean %.4f [%.4f, %.4f] FD %d of %d world-runs, unsupported claimed %d" % (
        label, len(rs), st.mean(d), min(d), max(d), st.mean(h), min(h), max(h),
        sum(1 for r in rs for x in r["rows"] if x[3]), sum(len(r["rows"]) for r in rs),
        sum(1 for r in rs for x in r["rows"] if x[1] == "uns" and x[2] != 1.0)))

rows = collections.defaultdict(list)
for r in jsonl("ladder.jsonl") + jsonl("probe.jsonl"):
    rows[(r["group"], r["candidate"])].append(r)
g0 = {k: next(r for r in v if r["shift"] == 0) for k, v in rows.items()}
R = g0[("ladder", "reference")]
print("ladder and probe: graded seed dev/held, mean over shifts, FD dev/held, unsupported claimed, supported declined")
for (group, name), rs in sorted(rows.items(), key=lambda kv: (kv[0][0], -kv[1][0]["dev"])):
    s0 = g0[(group, name)]
    print("  %-6s %-26s %.3f %.3f (%3.0f%% %3.0f%%) mean %.3f %.3f over %d  FD %d/%d  unsup-claimed %d  sup-declined %d" % (
        group, name, s0["dev"], s0["held"], 100 * s0["dev"] / R["dev"], 100 * s0["held"] / R["held"],
        st.mean(r["dev"] for r in rs), st.mean(r["held"] for r in rs), len(rs),
        sum(1 for r in rs for x in r["rows"] if x[3] and x[0][0] == "d"),
        sum(1 for r in rs for x in r["rows"] if x[3] and x[0][0] == "h"),
        sum(1 for r in rs for x in r["rows"] if x[1] == "uns" and x[2] != 1.0),
        sum(1 for r in rs for x in r["rows"] if x[1] == "sup" and x[2] == 0.0 and not x[3])))
probe = {n: s for (g, n), s in g0.items() if g == "probe"}
best = max(probe, key=lambda n: (probe[n]["dev"], probe[n]["held"]))
print("probe: %d strategies, best %s %.3f (%.0f%%) held %.3f (%.0f%%); scoring above zero: %d" % (
    len(probe), best, probe[best]["dev"], 100 * probe[best]["dev"] / R["dev"], probe[best]["held"],
    100 * probe[best]["held"] / R["held"], sum(1 for s in probe.values() if s["dev"] > 0)))

# the reference's margins, world by world, as its code computes them
from scipy.stats import beta, binom, norm  # noqa: E402
zs, zks, qs = [], [], []
for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
    w = ev._world(spec)
    links, dirs = len(w["links"]), 2 * len(w["links"])
    n = ev.PROBE_BUDGET // (12 * links)
    delta = ref.CFG["delta"]
    zs.append(norm.isf(delta / 4 / (dirs * 12 * n)))
    zks.append(-norm.ppf(beta.ppf(delta / 4 / (dirs * 12), 5, n - 5 + 1)))
    da = delta / 4 / (2 * dirs * 3)
    a_min = int(binom.ppf(da, 4 * n, ev.PI_MIN))
    qs.append(norm.ppf(1 - da ** (1.0 / a_min)) + 0.5)
print("margins: z %.2f to %.2f, fifth order statistic %.2f to %.2f, empty-queue q %.2f to %.2f pair sigmas" % (
    min(zs), max(zs), min(zks), max(zks), min(qs), max(qs)))
for name in ("z2.5", "z2", "headroom_z3"):
    rs = rows[("ladder", name)]
    print("  %s: shifts with a held-out false discovery %s, with a development one %s" % (
        name, sorted({r["shift"] for r in rs if any(x[3] and x[0][0] == "h" for x in r["rows"])}),
        sorted({r["shift"] for r in rs if any(x[3] and x[0][0] == "d" for x in r["rows"])})))
