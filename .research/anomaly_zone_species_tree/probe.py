"""Shortcut probe: low-dimensional strategies on the public problem.

Axes: the source of the gene trees (the oracle's free plain-Jukes-Cantor trees; trees the
candidate re-estimates from the alignment with the gamma correction at a guessed shape of 0.2,
0.35, 0.5, 0.7 or 1.0; or, as an upper bound no candidate can reach, at the world's true shape),
the topology
summary (greedy consensus, most frequent gene tree, neighbour joining on the across-locus mean
distance, exhaustive quartet consensus), the purchase (one catalogue cell for the whole budget,
or one cell for the topology and another for the refusal statistic and the branch lengths, half
the budget each), the refusal (never, discordance thresholds, minority-imbalance thresholds) and
the branch lengths (constants or the quartet inversion). Every strategy is scored by the task's
own metric functions on the same loci a candidate would buy.
"""
import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, json, itertools, collections, time, numpy as np
sys.path.insert(0, TASK + "/verification")
import evaluator as ev, msc
if _os.environ.get("AZ_PATCH"):
    sys.path.insert(0, _os.path.dirname(_os.environ["AZ_PATCH"])); import patch; print("patch:", patch.apply(ev), flush=True)
SETS, TABLE = msc.all_topologies()
FULL = msc.FULL_MASK
CELLS = [(rc, s) for rc in ev.RATE_CLASSES for s in ev.LOCUS_SITES]
WORLDS = [("development", i, s) for i, s in enumerate(ev.DEVELOPMENT_WORLDS)] + [("heldout", i, s) for i, s in enumerate(ev.HELDOUT_WORLDS)]
SOURCES = ("free", "shape 0.2", "shape 0.35", "shape 0.5", "shape 0.7", "shape 1.0", "true shape")
def shape_of(source, w):
    return w["shape"] if source == "true shape" else float(source.split()[1])

t0 = time.time()
worlds = {}
cache = {}
for split, index, spec in WORLDS:
    w = ev._world(spec); worlds[(split, index)] = w
    for rc, sites in CELLS:
        n = w["budget"] // ev.LOCUS_COST[sites]
        idx = [r["locus"] for r in w["catalogue"] if r["rate_class"] == rc and r["sites"] == sites][:n]
        data = {src: {"splits": [], "dists": []} for src in SOURCES}
        for i in idx:
            loc = ev._locus(w, i)
            _, adj = msc.parse_newick(loc["nj_tree"])
            aln = msc.from_strings([loc["alignment"][t] for t in msc.TAXA])
            data["free"]["splits"].append(msc.splits_of(adj)); data["free"]["dists"].append(msc.jc_distances(aln))
            for src in SOURCES[1:]:
                d = msc.jc_gamma_distances(aln, shape_of(src, w))
                data[src]["splits"].append(msc.splits_of(msc.neighbour_joining(d))); data[src]["dists"].append(d)
        cache[(split, index, rc, sites)] = data
print("cache built %.0fs" % (time.time() - t0), flush=True)

def compatible(a, b):
    return (a & b) == 0 or (a & b) == a or (a & b) == b or (a | b) == FULL
def greedy(splits_list):
    freq = collections.Counter(m for s in splits_list for m in s)
    chosen = {}
    for m, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
        if all(compatible(m, c) for c in chosen):
            chosen[m] = 1.0
        if len(chosen) == 5: break
    return chosen
def mode(splits_list):
    c = collections.Counter(frozenset(s) for s in splits_list)
    best = max(c.items(), key=lambda kv: (kv[1], sorted(kv[0])))[0]
    return {m: 1.0 for m in best}
def counts_of(splits_list):
    counts = np.zeros((70, 3))
    for s in splits_list:
        for q, t in enumerate(msc.quartet_signature(s)):
            if t >= 0: counts[q, t] += 1
    return counts
def quartet_cons(counts):
    score = counts[np.arange(70)[None, :], TABLE].sum(axis=1)
    return {m: 1.0 for m in SETS[int(np.argmax(score))]}
def chi35(counts):
    o = np.sort(counts, axis=1)[:, ::-1]
    x = (o[:, 1] - o[:, 2]) ** 2 / np.maximum(1.0, o[:, 1] + o[:, 2])
    return max(x[[q for q, quart in enumerate(msc.QUARTETS) if t in quart]].sum() for t in range(8))
def discordance(splits_list, topo):
    ref = set(topo)
    return float(np.mean([len(ref - set(s)) / 5.0 for s in splits_list]))
def quartet_lengths(topo, counts):
    tot = counts.sum(axis=1); out = {}
    for m in topo:
        est = []
        for q, t in msc.branch_length_quartets(topo, m):
            if tot[q] > 0:
                p = counts[q, t] / tot[q]; est.append(max(0.01, -np.log(max(1e-9, 1.5 * (1 - p)))))
        out[m] = float(np.median(est)) if est else 0.01
    return out

TOPOS = ["greedy", "mode", "avg_nj", "quartets"]
# Imbalance thresholds are per locus of the refusal cell (the statistic grows with the number of
# loci): 0.33 to 1.33 times the locus count.
REFUSALS = [("never", None)] + [("discord", th) for th in (0.5, 0.6, 0.7)] + [("chi", th) for th in (0.33, 0.48, 0.67, 1.0, 1.33)]
LENGTHS = [0.05, 0.1, 0.2, 0.4, "quartet"]
# Purchases: one cell with the whole budget, or a topology cell and a refusal cell with half each.
PURCHASES = [(c, c, 1) for c in CELLS] + [(a, b, 2) for a in CELLS for b in CELLS if a != b]

def n_loci(w, cell, share):
    return min((w["budget"] // share) // ev.LOCUS_COST[cell[1]], len(cache[("development", 0) + cell][SOURCES[0]]["splits"]))
view_cache = {}
def view(key, source, n):
    k = key + (source, n)
    if k not in view_cache:
        d = cache[key][source]
        splits = d["splits"][:n]
        view_cache[k] = {"splits": splits, "mean_d": np.mean(d["dists"][:n], axis=0), "counts": counts_of(splits)}
    return view_cache[k]
topo_cache = {}
def topology(key, source, n, method):
    k = key + (source, n, method)
    if k not in topo_cache:
        c = view(key, source, n)
        topo_cache[k] = {"greedy": lambda: greedy(c["splits"]), "mode": lambda: mode(c["splits"]),
                         "avg_nj": lambda: msc.splits_of(msc.neighbour_joining(c["mean_d"])), "quartets": lambda: quartet_cons(c["counts"])}[method]()
    return topo_cache[k]

results = []
for source, (tcell, rcell, share), method, (rname, th), length in itertools.product(SOURCES, PURCHASES, TOPOS, REFUSALS, LENGTHS):
    records = {"development": [], "heldout": []}
    for split, index, spec in WORLDS:
        w = worlds[(split, index)]
        nt, nr = n_loci(w, tcell, share), n_loci(w, rcell, share)
        topo = topology((split, index) + tcell, source, nt, method)
        r = view((split, index) + rcell, source, nr)
        abstain = False
        if rname == "discord": abstain = discordance(r["splits"], topo) > th
        elif rname == "chi": abstain = chi35(r["counts"]) > th * len(r["splits"])
        if abstain or len(topo) != 5:
            m = ev._metrics(w, None, 0.9, True)
        else:
            lengths = quartet_lengths(topo, r["counts"]) if length == "quartet" else {k: length for k in topo}
            m = ev._metrics(w, lengths, 0.9, False)
        m.update({"kind": w["kind"], "abstained": abstain, "valid": True, "confidence_calibration_score": 0.0, "loci_bought": 0, "budget_spent": 0})
        records[split].append(m)
    dev = ev._split_summary(records["development"]); held = ev._split_summary(records["heldout"])
    results.append({"source": source, "topology_cell": "%s/%d" % tcell, "refusal_cell": "%s/%d" % rcell, "purchase": "single" if share == 1 else "split",
                    "topology": method, "refusal": rname, "threshold": th, "length": length,
                    "dev": dev["normalized_mechanism"], "heldout": held["normalized_mechanism"], "topology_rate": dev["topology_rate"],
                    "fdr": dev["false_discovery_rate"], "refusal_rate": dev["correct_refusal_rate"], "coverage": dev["discovery_coverage"]})
results.sort(key=lambda r: -r["dev"])
def show(r):
    return "dev %.3f held %.3f topo %.3f fdr %.2f ref %.2f cov %.2f | %-9s %-10s %-10s %-6s %-8s %-7s %-5s %s" % (
        r["dev"], r["heldout"], r["topology_rate"], r["fdr"], r["refusal_rate"], r["coverage"], r["source"], r["topology_cell"], r["refusal_cell"], r["purchase"], r["topology"], r["refusal"], r["threshold"], r["length"])
print("strategies", len(results))
for r in results[:30]:
    print(show(r))
def best(pred, label):
    rows = [r for r in results if pred(r)]
    print("best %-52s %s" % (label + ":", show(max(rows, key=lambda r: r["dev"])) if rows else "none"))
best(lambda r: r["source"] != "true shape", "without the true shape (what a candidate can do)")
best(lambda r: r["source"] == "free", "on the free gene trees")
best(lambda r: r["source"].startswith("shape"), "at a guessed shape")
for guess in ("0.2", "0.35", "0.5", "0.7", "1.0"):
    best(lambda r, g=guess: r["source"] == "shape " + g, "at shape " + guess)
best(lambda r: r["source"] == "true shape", "at the true shape (oracle upper bound)")
best(lambda r: r["source"] == "true shape" and r["topology"] != "quartets", "true shape, without quartet consensus")
best(lambda r: r["source"] != "true shape" and r["topology"] != "quartets", "without the true shape or quartet consensus")
best(lambda r: r["source"] != "true shape" and r["topology"] != "quartets" and r["length"] != "quartet", "without the true shape, quartet consensus or quartet lengths")
C = lambda r: r["source"] != "true shape"
best(lambda r: C(r) and r["topology"] == "quartets", "quartet consensus, guessed shape or free trees")
best(lambda r: C(r) and r["topology"] == "avg_nj", "mean-distance neighbour joining, guessed shape or free trees")
best(lambda r: C(r) and r["topology"] == "greedy", "greedy consensus, guessed shape or free trees")
best(lambda r: C(r) and r["topology"] == "mode", "most frequent gene tree, guessed shape or free trees")
best(lambda r: C(r) and r["purchase"] == "single", "one cell, guessed shape or free trees")
best(lambda r: C(r) and r["purchase"] == "split", "two cells, guessed shape or free trees")
best(lambda r: C(r) and r["topology_cell"].startswith("slow"), "slow loci for the topology, guessed shape or free trees")
best(lambda r: C(r) and r["topology_cell"].startswith("medium"), "medium loci for the topology, guessed shape or free trees")
best(lambda r: C(r) and r["topology_cell"].startswith("fast"), "fast loci for the topology, guessed shape or free trees")
best(lambda r: C(r) and r["refusal"] == "never", "never refusing, guessed shape or free trees")
best(lambda r: C(r) and r["refusal"] == "discord", "discordance refusal, guessed shape or free trees")
best(lambda r: C(r) and r["refusal"] == "chi", "imbalance refusal, guessed shape or free trees")
best(lambda r: C(r) and r["length"] == "quartet", "quartet lengths, guessed shape or free trees")
best(lambda r: C(r) and r["length"] != "quartet", "constant lengths, guessed shape or free trees")
print("counts per family:", {k: sum(1 for r in results if r["source"] == k) for k in SOURCES})
json.dump(results, open(OUT + "/anomaly_zone_probe_results.json", "w"), indent=1)
print("total %.0fs" % (time.time() - t0))
