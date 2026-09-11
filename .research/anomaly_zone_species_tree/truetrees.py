"""How often exhaustive quartet consensus over 240 or 500 TRUE gene trees names the species tree of
each anomaly-zone world: the sampling limit of the worlds, independent of sequence estimation."""
import os as _os
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
import sys, time, numpy as np
sys.path.insert(0, TASK + "/verification")
import evaluator as ev, msc
ns = {}; exec(compile(open(TASK + "/verification/reference_quartet_consensus.py").read(), "ref", "exec"), ns)
edges_list, split_sets, table = ns["_all_trees"]()
QUARTETS = ns["QUARTETS"]; qt = ns["_quartet_topology"]
REPS = 200
t0 = time.time()
for spec in [s for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS if s["kind"] == "anomaly"]:
    w = ev._world(spec); truth = set(w["truth_splits"]); rng = np.random.default_rng(spec["seed"] + 999)
    hits = {240: 0, 500: 0}
    splits_true = truth
    for rep in range(REPS):
        counts = np.zeros((len(QUARTETS), 3))
        for i in range(500):
            g, _ = msc.simulate_gene_tree(w["trees"][0], rng)
            splits = set(g.unrooted_splits())
            for q, quartet in enumerate(QUARTETS):
                t = qt(splits, quartet)
                if t >= 0: counts[q, t] += 1
            if i + 1 in hits:
                sc = counts[np.arange(len(QUARTETS))[None, :], table].sum(axis=1)
                best = int(np.argmax(sc))
                if set(split_sets[best]) == truth: hits[i + 1] += 1
    print("  %d  240 true gene trees: %.3f   500: %.3f" % (spec["seed"], hits[240] / REPS, hits[500] / REPS), flush=True)
print("total %.0fs" % (time.time() - t0))
