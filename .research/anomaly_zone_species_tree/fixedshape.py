"""The reference with the site-rate shape fixed at a guess instead of estimated: which tree worlds
of each kind it still reads. The numbers behind the claim that no single guess reads more than two
of the four long-branch worlds of the development split."""
import os as _os
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
import sys, collections
sys.path.insert(0, TASK + "/verification")
import evaluator as ev
SRC = open(TASK + "/verification/reference_quartet_consensus.py").read()
LINE = "    shape, _observed, _error = _estimate_shape(bought[:SHAPE_LOCI])\n"
assert LINE in SRC
for guess in (0.2, 0.25, 0.3, 0.342, 0.4, 0.5, 0.585, 0.7, 0.85, 1.0):
    ns = {}; exec(compile(SRC.replace(LINE, "    shape = %r\n" % guess), "fixed", "exec"), ns)
    m = ev.evaluate(ns["infer_species_tree"])
    ok = collections.Counter(); declined = collections.Counter()
    for row in m["per_instance"]:
        if row["kind"] in ("anomaly", "long_branch"):
            key = (row["split"], row["kind"])
            ok[key] += int(bool(row.get("topology_correct", row.get("topology", False))))
            declined[key] += int(bool(row.get("abstained")))
    print("guess %.3f dev %.3f held %.3f | dev anomaly %d/4 (declined %d) long_branch %d/4 (declined %d) | held anomaly %d/2 long_branch %d/2" % (
        guess, m["combined_score"], m["heldout_mechanism_score"],
        ok[("development", "anomaly")], declined[("development", "anomaly")], ok[("development", "long_branch")], declined[("development", "long_branch")],
        ok[("heldout", "anomaly")], ok[("heldout", "long_branch")]), flush=True)
