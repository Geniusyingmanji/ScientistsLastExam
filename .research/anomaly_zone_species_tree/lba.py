"""Long-branch attraction, measured the right way: for each long-branch world and rate class, the
share of gene trees that join the two fast species in the true gene trees, in the sequencing
centre's plain Jukes-Cantor trees and in trees corrected at the world's true shape; the excess of the estimated trees
over the truth is the attraction. Also the minority-imbalance statistic on free versus corrected
trees across all worlds, whether neighbour joining on the mean distance recovers the species tree,
and the per-locus recall of the true gene tree's splits."""
import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, time, numpy as np
sys.path.insert(0, TASK + "/verification")
import evaluator as ev, msc
if _os.environ.get("AZ_PATCH"):
    sys.path.insert(0, _os.path.dirname(_os.environ["AZ_PATCH"])); import patch; print("patch:", patch.apply(ev), flush=True)
WORLDS = [("dev", s) for s in ev.DEVELOPMENT_WORLDS] + [("held", s) for s in ev.HELDOUT_WORLDS]
CELLS = [("slow", 300), ("slow", 800), ("medium", 800), ("fast", 800)]

def locus(w, index):
    gene_tree, scaled, aln = ev._simulate(w, index)
    d = msc.jc_distances(aln); dg = msc.jc_gamma_distances(aln, w["shape"])
    return gene_tree.unrooted_splits(), msc.splits_of(msc.neighbour_joining(d)), msc.splits_of(msc.neighbour_joining(dg)), d, dg

def counts_of(splits_list):
    c = np.zeros((70, 3))
    for s in splits_list:
        for q, t in enumerate(msc.quartet_signature(s)):
            if t >= 0: c[q, t] += 1
    return c
def chi35(counts):
    o = np.sort(counts, axis=1)[:, ::-1]
    x = (o[:, 1] - o[:, 2]) ** 2 / np.maximum(1.0, o[:, 1] + o[:, 2])
    return max(x[[q for q, quart in enumerate(msc.QUARTETS) if t in quart]].sum() for t in range(8))

t0 = time.time()
chi = {}; nj_ok = {}; recall = {}
print("long-branch worlds: share of gene trees joining the two fast species, true / free / corrected, and excess over the truth")
for split, spec in WORLDS:
    w = ev._world(spec); kind = w["kind"]
    fast = sorted(range(8), key=lambda t: -w["multiplier"][t])[:2] if kind == "long_branch" else None
    for rc, sites in CELLS:
        n = w["budget"] // ev.LOCUS_COST[sites]
        idx = [r["locus"] for r in w["catalogue"] if r["rate_class"] == rc and r["sites"] == sites][:n]
        rows = [locus(w, i) for i in idx]
        true_s = [r[0] for r in rows]; free_s = [r[1] for r in rows]; corr_s = [r[2] for r in rows]
        cf, cc = counts_of(free_s), counts_of(corr_s)
        chi.setdefault((rc, sites, kind), []).append((chi35(cf), chi35(cc)))
        if kind != "reticulate":
            truth = set(w["truth_splits"])
            md = np.mean([r[3] for r in rows], axis=0); mdg = np.mean([r[4] for r in rows], axis=0)
            ok_naive = set(msc.splits_of(msc.neighbour_joining(md))) == truth
            ok_corr = set(msc.splits_of(msc.neighbour_joining(mdg))) == truth
            nj_ok.setdefault((rc, sites, kind), []).append((ok_naive, ok_corr))
            recall.setdefault((rc, sites, kind), []).append((
                np.mean([len(set(t) & set(f)) / 5.0 for t, f in zip(true_s, free_s)]),
                np.mean([len(set(t) & set(c)) / 5.0 for t, c in zip(true_s, corr_s)])))
        if kind == "long_branch":
            mask = msc.canonical_split((1 << fast[0]) | (1 << fast[1]))
            rate = lambda L: 100.0 * np.mean([mask in s for s in L])
            tr, fr, cr = rate(true_s), rate(free_s), rate(corr_s)
            print("  %s %-9d %-6s %4d n=%3d  true %5.1f  free %5.1f (%+5.1f)  corr %5.1f (%+5.1f)  imbalance free %6.1f corr %6.1f  mean-distance NJ naive %s corrected %s" % (
                split, spec["seed"], rc, sites, n, tr, fr, fr - tr, cr, cr - tr, chi35(cf), chi35(cc), ok_naive, ok_corr), flush=True)
print("\nminority-imbalance statistic, max over tree worlds vs min over reticulate worlds (free / corrected)")
for rc, sites in CELLS:
    tree = chi[(rc, sites, "anomaly")] + chi[(rc, sites, "long_branch")]; ret = chi[(rc, sites, "reticulate")]
    print("  %-6s %4d  tree max free %6.1f corr %6.1f | reticulate min free %6.1f corr %6.1f" % (
        rc, sites, max(a for a, _ in tree), max(b for _, b in tree), min(a for a, _ in ret), min(b for _, b in ret)))
print("\nneighbour joining on the mean distance, correct topologies over the 12 tree worlds (naive / gamma-corrected)")
for rc, sites in CELLS:
    rows = nj_ok[(rc, sites, "anomaly")] + nj_ok[(rc, sites, "long_branch")]; lb = nj_ok[(rc, sites, "long_branch")]
    print("  %-6s %4d  naive %2d  corrected %2d   (long-branch worlds only: naive %d corrected %d of %d)" % (
        rc, sites, sum(a for a, _ in rows), sum(b for _, b in rows), sum(a for a, _ in lb), sum(b for _, b in lb), len(lb)))
print("\nper-locus recall of the true gene tree's five splits, mean over worlds of a kind (free / corrected)")
for rc, sites in CELLS:
    for kind in ("anomaly", "long_branch"):
        r = np.array(recall[(rc, sites, kind)])
        print("  %-6s %4d  %-11s free %.3f corrected %.3f" % (rc, sites, kind, r[:, 0].mean(), r[:, 1].mean()))
print("total %.0fs" % (time.time() - t0))
