import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, time, importlib.util, json, ast
sys.path.insert(0, TASK + "/verification")
import evaluator as ev
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
ref = load(TASK + "/verification/reference_quartet_consensus.py", "ref")
# A. determinism
a = ev.evaluate(ref.infer_species_tree); b = ev.evaluate(ref.infer_species_tree)
print("determinism identical payload:", a == b, "json identical:", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
# B. malformed submissions
bad = {
 "raises": lambda p, s: (_ for _ in ()).throw(RuntimeError("boom")),
 "none": lambda p, s: None, "empty": lambda p, s: {}, "string": lambda p, s: "tree",
 "verdict_bad": lambda p, s: {"verdict": "maybe"}, "tree_no_newick": lambda p, s: {"verdict": "tree"},
 "newick_int": lambda p, s: {"verdict": "tree", "newick": 5}, "newick_garbage": lambda p, s: {"verdict": "tree", "newick": "((A,B"},
 "missing_taxon": lambda p, s: {"verdict": "tree", "newick": "((A:1,B:1):1,(C:1,D:1):1,(E:1,(F:1,G:1):1):1);"},
 "duplicate_taxon": lambda p, s: {"verdict": "tree", "newick": "((A:1,A:1):1,(C:1,D:1):1,(E:1,(F:1,(G:1,H:1):1):1):1);"},
 "no_lengths": lambda p, s: {"verdict": "tree", "newick": "((A,B),(C,D),(E,(F,(G,H))));"},
 "negative_length": lambda p, s: {"verdict": "tree", "newick": "((A:1,B:1):-1,(C:1,D:1):1,(E:1,(F:1,(G:1,H:1):1):1):1);"},
 "nan_length": lambda p, s: {"verdict": "tree", "newick": "((A:1,B:1):nan,(C:1,D:1):1,(E:1,(F:1,(G:1,H:1):1):1):1);"},
 "unresolved": lambda p, s: {"verdict": "tree", "newick": "(A:1,B:1,C:1,D:1,E:1,F:1,G:1,H:1);"},
 "confidence_nan": lambda p, s: {"verdict": "reticulate", "confidence": float("nan")},
 "confidence_str": lambda p, s: {"verdict": "reticulate", "confidence": "high"},
 "overspend": lambda p, s: [s(i) for i in range(300)] and {"verdict": "reticulate"},
 "bad_locus": lambda p, s: s(-1), "float_locus": lambda p, s: s(1.5), "huge_newick": lambda p, s: {"verdict": "tree", "newick": "(" * 5000},
}
for name, fn in bad.items():
    try:
        m = ev.evaluate(fn)
        print("  %-18s valid=%s combined=%s feas=%.2f" % (name, m["valid"], m["combined_score"], m["feasibility_rate"]))
    except Exception as e:
        print("  %-18s RAISED %s: %s" % (name, type(e).__name__, e))
# extra: abstain True form and valid tree with extra taxa lengths
m = ev.evaluate(lambda p, s: {"abstain": True}); print("abstain-form blanket:", m["valid"], m["combined_score"])
m = ev.evaluate(lambda p, s: {"verdict": "tree", "newick": "((A:1,B:1):0.1,(C:1,D:1):0.1,(E:1,(F:1,(G:1,H:1):0.1):0.1):0.1);", "confidence": 0.9})
print("fixed tree:", m["valid"], m["combined_score"], m["development_false_discovery_rate"])
# C. budget not free: reference restricted to 50 loci / 25 loci
src = open(TASK + "/verification/reference_quartet_consensus.py").read()
for n in (125, 250, 375):
    ns = {}; exec(compile(src.replace("    for row in chosen:\n", "    for row in chosen[:%d]:\n" % n), "ref_%d" % n, "exec"), ns)
    m = ev.evaluate(ns["infer_species_tree"])
    print("reference with %d loci: dev %.3f held %.3f topo %.2f refusal %.2f fdr %.2f" % (n, m["combined_score"], m["heldout_mechanism_score"], m["development_topology_rate"], m["development_correct_refusal_rate"], m["development_false_discovery_rate"]))
# H. python 3.8 syntax
for f in ["verification/msc.py", "verification/evaluator.py", "verification/reference_quartet_consensus.py", "solution.py"]:
    ast.parse(open(TASK + "/" + f).read(), feature_version=(3, 8)); print("py38 syntax ok", f)
