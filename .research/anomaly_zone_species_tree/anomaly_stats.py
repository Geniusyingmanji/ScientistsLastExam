"""For every tree world, the gene-tree probability of the species-tree topology and of the most
frequent topology, their difference and its standard error, from N simulated gene trees. The
anomaly-zone worlds must show the species tree behind the top topology; the long-branch worlds are
built with moderate internal branches and are expected to show the species tree on top."""
import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, collections, numpy as np
sys.path.insert(0, TASK + "/verification")
import evaluator as ev, msc
if _os.environ.get("AZ_PATCH"):
    sys.path.insert(0, _os.path.dirname(_os.environ["AZ_PATCH"])); import patch; print("patch:", patch.apply(ev), flush=True)
N = int(_os.environ.get("AZ_N", "100000")); SEED = 5
ONLY = _os.environ.get("AZ_ONLY")
print("N = %d gene trees per world, rng seed %d; se is that of p_top - p_species under the multinomial" % (N, SEED))
for split, specs in (("development", ev.DEVELOPMENT_WORLDS), ("heldout", ev.HELDOUT_WORLDS)):
    for spec in specs:
        if spec["kind"] == "reticulate" or (ONLY and str(spec["seed"]) != ONLY):
            continue
        w = ev._world(spec); truth = frozenset(w["truth_splits"])
        rng = np.random.default_rng(SEED); ctr = collections.Counter()
        for _ in range(N):
            g, _ = msc.simulate_gene_tree(w["trees"][0], rng); ctr[frozenset(g.unrooted_splits())] += 1
        top_key, top_n = ctr.most_common(1)[0]
        p_top = top_n / N; p_sp = ctr[truth] / N
        se = np.sqrt((p_top * (1 - p_top) + p_sp * (1 - p_sp) + 2 * p_top * p_sp) / N)
        rank = sorted(ctr.values(), reverse=True).index(ctr[truth]) + 1
        print("  %-11s %-11s %d  p_species %.4f  p_top %.4f  diff %+.4f  se %.4f  diff/se %5.1f  rank %d  distinct %d" % (
            split, spec["kind"], spec["seed"], p_sp, p_top, p_top - p_sp, se, (p_top - p_sp) / se, rank, len(ctr)), flush=True)
        # The most frequent topology, for the test that compares the species tree against a
        # competitor fixed in advance rather than against the empirical maximum.
        print("      most frequent: %s" % msc.splits_to_newick({m: 1.0 for m in top_key}), flush=True)
