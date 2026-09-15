"""Every number the task's documents quote, recomputed from the recorded runs and a fresh evaluation.

    .venv/bin/python .research/cache_policy/summary.py
"""
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from grid import CELLS  # noqa: E402
from pkg_eval import CANDIDATES, ev  # noqa: E402


def jsonl(name):
    return [json.loads(line) for line in open(HERE / name)]


def fresh(name):
    for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
        spec["seed"] = ORIGINAL[spec["name"]]
    ev._WORLDS.clear()
    return ev.evaluate(CANDIDATES[name]())


ORIGINAL = {s["name"]: s["seed"] for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS}
for name in ("reference", "original", "baseline"):
    m = fresh(name)
    print(name, {k: round(v, 4) for k, v in m.items() if isinstance(v, float)})
    print("  runs", [(r["split"][0] + "%02d" % (r["world_index"] + 1), r["runs_used"], r["mechanism_score"]) for r in m["per_instance"]])

for f, label in (("pkg_reference_robust.jsonl", "reference"), ("pkg_original_robust.jsonl", "original reference"),
                 ("pkg_baseline_robust.jsonl", "baseline")):
    rs = jsonl(f)
    dev, held = [r["dev"] for r in rs], [r["held"] for r in rs]
    print("%s robustness: shifts %d dev mean %.4f [%.4f, %.4f] held mean %.4f [%.4f, %.4f] false discoveries %d of %d, max runs in a world %d" % (
        label, len(rs), st.mean(dev), min(dev), max(dev), st.mean(held), min(held), max(held),
        sum(1 for r in rs for x in r["rows"] if x[3]), sum(len(r["rows"]) for r in rs), max(x[5] for r in rs for x in r["rows"])))
rs = jsonl("pkg_reference_robust.jsonl")
declined = collections.Counter(x[0] for r in rs for x in r["rows"] if x[1] == "dete" and x[2] == 0.0)
print("  reference: deterministic worlds declined, by world over the shifts", dict(sorted(declined.items())))

ladder = collections.defaultdict(list)
for r in jsonl("ladder.jsonl"):
    ladder[r["name"]].append(r)
ref = [r for r in ladder["reference"] if r["shift"] == 0][0]["dev"]
print("\nladder (graded seed dev/held, mean over shifts, false discoveries dev/held, shifts, coverage, per cent of reference)")
print("%-28s %6s %6s %6s %6s %5s %5s %4s %5s" % ("strategy", "g.dev", "g.held", "m.dev", "m.held", "fd.d", "fd.h", "n", "cov"))
for name, rs in ladder.items():
    g = [r for r in rs if r["shift"] == 0][0]
    print("%-28s %6.3f %6.3f %6.3f %6.3f %5d %5d %4d %5.2f  %3.0f%%" % (
        name, g["dev"], g["held"], st.mean(r["dev"] for r in rs), st.mean(r["held"] for r in rs),
        sum(r["dev_fd"] for r in rs), sum(r["held_fd"] for r in rs), len(rs), g["dev_coverage"], 100 * g["dev"] / ref))
print("max run calls in one world, reference:", max(r["max_calls"] for r in ladder["reference"]),
      "total per evaluation:", [r["total_calls"] for r in ladder["reference"] if r["shift"] == 0][0])

grid = collections.defaultdict(list)
for r in jsonl("grid.jsonl"):
    grid[r["name"]].append(r)
declared = [n for n, _ in CELLS]
g0 = {n: next(r for r in rs if r["shift"] == 0) for n, rs in grid.items()}
missing = [n for n in declared if n not in g0]
print("\ngrid: %d cells declared, %d run on the graded seed, missing %s, %d cells above zero" % (
    len(declared), len(g0), missing, sum(1 for s in g0.values() if s["dev"] > 0)))
def family(n):
    if n.startswith("blind_"):
        return "blind"
    return re.sub(r"(_l[0-9.]+|_cap\d+)?_(nocheck|c\d+)_(det|no_det|pooled_only|position_only)$", "", n)


fams = collections.defaultdict(list)
for n, s in g0.items():
    fams[family(n)].append(s)
print("%-18s %5s %6s %6s %s" % ("family", "cells", "b.dev", "b.held", "best cell"))
for f, ss in sorted(fams.items(), key=lambda kv: -max(s["dev"] for s in kv[1])):
    b = max(ss, key=lambda s: (s["dev"], s["held"]))
    print("%-18s %5d %6.3f %6.3f %s" % (f, len(ss), b["dev"], b["held"], b["name"]))
top = sorted(g0.values(), key=lambda s: (-s["dev"], -s["held"]))
print("cells at the top development score %.4f: %d" % (top[0]["dev"], sum(1 for s in top if s["dev"] == top[0]["dev"])))
print("cells at or above 90%% of the reference (%.4f): %d" % (0.9 * ref, sum(1 for s in top if s["dev"] >= 0.9 * ref - 1e-9)))
print("best cells re-run on further shifts:")
for n, rs in grid.items():
    if len(rs) > 1:
        print("  %-30s graded %.3f %.3f  mean over %d shifts %.3f %.3f  fd %d/%d  (%3.0f%% / %3.0f%% of the reference mean)" % (
            n, g0[n]["dev"], g0[n]["held"], len(rs), st.mean(r["dev"] for r in rs), st.mean(r["held"] for r in rs),
            sum(r["dev_fd"] for r in rs), sum(r["held_fd"] for r in rs),
            100 * st.mean(r["dev"] for r in rs) / st.mean(r["dev"] for r in jsonl("pkg_reference_robust.jsonl")[:8]),
            100 * st.mean(r["held"] for r in rs) / st.mean(r["held"] for r in jsonl("pkg_reference_robust.jsonl")[:8])))

det = jsonl("det_diag.jsonl")
for kind in ("deterministic", "randomized"):
    rows = [r for r in det if r["kind"] == kind]
    for n in ("24", "32"):
        zs = [r["det2"][n][0] for r in rows]
        ws = [r["det2"][n][1] for r in rows]
        print("det2 %-13s n=%s z [%.2f, %.2f] worst tail [%.2f, %.2f] det1 max %.2f  (%d world-runs)" % (
            kind, n, min(zs), max(zs), min(ws), max(ws), max(r["det1"] for r in rows), len(rows)))
for w in ("dev-10", "dev-11", "dev-12", "held-05", "held-06"):
    rows = [r for r in det if r["world"] == w]
    print("  %s min z at 24 %.2f, at 32 %.2f" % (w, min(r["det2"]["24"][0] for r in rows), min(r["det2"]["32"][0] for r in rows)))
