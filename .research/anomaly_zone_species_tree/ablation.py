import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, json, importlib.util, collections, numpy as np
sys.path.insert(0, TASK + "/verification")
import evaluator as ev, msc
if _os.environ.get("AZ_PATCH"):
    sys.path.insert(0, _os.path.dirname(_os.environ["AZ_PATCH"])); import patch; print("patch:", patch.apply(ev), flush=True)
SRC = open(TASK + "/verification/reference_quartet_consensus.py").read()
BASE = open(TASK + "/solution.py").read()
FULL = msc.FULL_MASK
def compatible(a, b): return (a & b) == 0 or (a & b) == a or (a & b) == b or (a | b) == FULL
def variant(name, patches, inject=None):
    src = SRC
    for old, new in patches:
        assert old in src, (name, old)
        src = src.replace(old, new)
    ns = {"_oracle_splits": lambda locus: msc.splits_of(msc.parse_newick(locus["nj_tree"])[1])}
    if inject: ns.update(inject)
    exec(compile(src, "variant_" + name, "exec"), ns)
    return ns["infer_species_tree"]
def greedy_from_counts(counts):
    # greedy consensus needs split frequencies, not quartet counts; handled by patching the loop instead
    raise NotImplementedError
CORR = "splits = _splits(_neighbour_joining(_gamma_distances(seqs, shape)))"
# the free trees are not kept by the reference, so the oracle-tree rungs keep them in a side list
ORACLE = [
 ("    bought = []\n", "    bought = []\n    _FREE.clear()\n"),
 ('        bought.append(_encode(locus["alignment"], taxa))\n', '        bought.append(_encode(locus["alignment"], taxa))\n        _FREE.append(locus)\n'),
 ("    for seqs in bought:\n", "    for _i, seqs in enumerate(bought):\n"),
 (CORR, "splits = _oracle_splits(_FREE[_i])"),
]
rows = []
variants = [
 ("reference", []),
 ("oracle NJ trees, no gamma correction", ORACLE),
 ("medium loci instead of slow", [('CHOSEN_CLASS = "slow"', 'CHOSEN_CLASS = "medium"')]),
 ("fast loci instead of slow", [('CHOSEN_CLASS = "slow"', 'CHOSEN_CLASS = "fast"')]),
 ("300-site loci (all 500 in the catalogue)", [("CHOSEN_SITES = 800", "CHOSEN_SITES = 300")]),
 ("2000-site loci (200 of them)", [("CHOSEN_SITES = 800", "CHOSEN_SITES = 2000")]),
 ("never refusing", [("REFUSAL_STATISTIC = 260.0", "REFUSAL_STATISTIC = 1e9")]),
 ("refusal threshold 180", [("REFUSAL_STATISTIC = 260.0", "REFUSAL_STATISTIC = 180.0")]),
 ("refusal threshold 340", [("REFUSAL_STATISTIC = 260.0", "REFUSAL_STATISTIC = 340.0")]),
 ("constant branch lengths 0.1", [("lengths[mask] = float(np.median(estimates)) if estimates else MIN_LENGTH", "lengths[mask] = 0.1")]),
 ("half the budget", [('budget = int(problem["locus_budget"])', 'budget = int(problem["locus_budget"]) // 2')]),
 ("quarter of the budget", [('budget = int(problem["locus_budget"])', 'budget = int(problem["locus_budget"]) // 4')]),
 ("oracle trees and fast loci", ORACLE + [('CHOSEN_CLASS = "slow"', 'CHOSEN_CLASS = "fast"')]),
 ("oracle trees, never refusing", ORACLE + [("REFUSAL_STATISTIC = 260.0", "REFUSAL_STATISTIC = 1e9")]),
]
# greedy consensus variant: patch the quartet argmax to a greedy consensus of split frequencies
GREEDY_PATCH = [
 ("        for q, quartet in enumerate(QUARTETS):\n            topology = _quartet_topology(splits, quartet)",
  "        _SPLIT_FREQ.update(splits.keys())\n        for q, quartet in enumerate(QUARTETS):\n            topology = _quartet_topology(splits, quartet)"),
 ("    best = int(np.argmax(score))\n", "    best = _greedy_index(_SPLIT_FREQ, split_sets)\n    _SPLIT_FREQ.clear()\n"),
]
def _greedy_index(freq, split_sets):
    chosen = []
    for m, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
        if all(compatible(m, c) for c in chosen):
            chosen.append(m)
        if len(chosen) == 5: break
    target = set(chosen)
    for i, s in enumerate(split_sets):
        if set(s) == target: return i
    return 0
SHAPE_LINE = "    shape, _observed, _error = _estimate_shape(bought[:SHAPE_LOCI])\n"
variants += [
 ("shape fixed at 0.5 instead of estimated", [(SHAPE_LINE, "    shape = 0.5\n")]),
 ("shape fixed at 0.2 instead of estimated", [(SHAPE_LINE, "    shape = 0.2\n")]),
 ("shape fixed at 1.0 instead of estimated", [(SHAPE_LINE, "    shape = 1.0\n")]),
 ("shape estimated from 20 loci instead of 60", [("SHAPE_LOCI = 60", "SHAPE_LOCI = 20")]),
 ("the true shape (an oracle no candidate has)", [(SHAPE_LINE, "    shape = _CURRENT['shape']\n")]),
]
variants.append(("greedy consensus instead of quartets", GREEDY_PATCH))
# mean-distance variant: neighbour joining once on the gamma-corrected distance averaged over the loci
MEAN_PATCH = [
 (CORR, "_dist = _gamma_distances(seqs, shape)\n        _MEAN_D.append(_dist)\n        splits = _splits(_neighbour_joining(_dist))"),
 ("    best = int(np.argmax(score))\n", "    best = _mean_index(_MEAN_D, split_sets)\n    _MEAN_D.clear()\n"),
]
def _mean_index(dists, split_sets):
    target = set(_ref_ns["_splits"](_ref_ns["_neighbour_joining"](np.mean(dists, axis=0))))
    for i, s in enumerate(split_sets):
        if set(s) == target: return i
    return 0
variants.append(("mean corrected distance, one neighbour joining, instead of quartets", MEAN_PATCH))
_ref_ns = {}
exec(compile(SRC, "reference_for_mean", "exec"), _ref_ns)
_CURRENT = {}
_orig_world = ev._world
def _tracking_world(spec):
    w = _orig_world(spec); _CURRENT["shape"] = w["shape"]; return w
ev._world = _tracking_world
inject = {"_FREE": [], "_SPLIT_FREQ": collections.Counter(), "_greedy_index": _greedy_index, "_MEAN_D": [], "_mean_index": _mean_index, "_CURRENT": _CURRENT}
ONLY = _os.environ.get("AZ_ONLY")
for name, patches in variants:
    if ONLY and ONLY not in name:
        continue
    fn = variant(name.replace(" ", "_"), patches, inject)
    m = ev.evaluate(fn)
    rows.append((name, m))
    print("%-42s dev %.3f held %.3f topo %.2f bl %.2f fdr %.2f refusal %.2f cov %.2f loci %.0f" % (
        name, m["combined_score"], m["heldout_mechanism_score"], m["development_topology_rate"], m["development_branch_length_score"],
        m["development_false_discovery_rate"], m["development_correct_refusal_rate"], m["development_discovery_coverage"], m["development_mean_loci_bought"]), flush=True)
ns = {}; exec(compile(BASE, "baseline", "exec"), ns); m = ev.evaluate(ns["infer_species_tree"]); rows.append(("baseline: fast long loci, concatenation, never refusing", m))
print("%-42s dev %.3f held %.3f topo %.2f bl %.2f fdr %.2f refusal %.2f cov %.2f" % ("baseline", m["combined_score"], m["heldout_mechanism_score"], m["development_topology_rate"], m["development_branch_length_score"], m["development_false_discovery_rate"], m["development_correct_refusal_rate"], m["development_discovery_coverage"]))
m = ev.evaluate(lambda p, s: {"verdict": "reticulate", "confidence": 1.0}); rows.append(("declining everything", m))
print("declining everything dev %.3f held %.3f fdr %.2f" % (m["combined_score"], m["heldout_mechanism_score"], m["development_false_discovery_rate"]))
json.dump([(n, {k: v for k, v in m.items() if k != "per_instance"}) for n, m in rows], open(OUT + "/anomaly_zone_ablation.json", "w"), indent=1)
