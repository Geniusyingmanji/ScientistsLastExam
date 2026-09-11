import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "LDMismatchFineMapping"))
OUT = _tempfile.gettempdir()
import sys, importlib.util
sys.path.insert(0, TASK + "/verification")
def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
import evaluator as ev
import reference_conditional_rows as ref
base = _load(TASK + "/solution.py", "ld_baseline")

"""Determinism, malformed candidates, degenerate candidates, budget enforcement, 3.8 syntax."""
import sys, os, json, ast, importlib.util

import numpy as np, json, ast, os

for f in ("verification/evaluator.py", "verification/ldsim.py", "verification/reference_conditional_rows.py", "solution.py"):
    ast.parse(open(os.path.join(TASK, f)).read(), feature_version=(3, 8))
print("python 3.8 syntax ok")

a = ev.evaluate(ref.fine_map); b = ev.evaluate(ref.fine_map)
print("deterministic:", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

for name, sub in (("abstain-all", {"verdict": "unresolved", "confidence": 1.0}), ("abstain-synonym", {"abstain": True})):
    m = ev.evaluate(lambda p, r, s=sub: dict(s))
    print("%-16s combined %.3f valid %d refusal %.2f fdr %.2f" % (name, m["combined_score"], m["valid"], m["development_correct_refusal_rate"], m["development_false_discovery_rate"]))
for conf in (0.9, 0.1):
    m = ev.evaluate(lambda p, r, c=conf: {"verdict": "typed", "causal": [int(np.argmax(np.abs(p["z"])))], "effects": [float(p["z"][int(np.argmax(np.abs(p["z"])))] * p["standard_error"][int(np.argmax(np.abs(p["z"])))])], "confidence": c})
    print("top-|z| conf %.1f  combined %.3f fdr %.2f f1 %.2f" % (conf, m["combined_score"], m["development_false_discovery_rate"], m["development_set_f1"]))
m = ev.evaluate(lambda p, r: {"verdict": "typed", "causal": [0], "effects": [0.1], "confidence": 0.9})
print("fixed variant 0  combined %.3f fdr %.2f" % (m["combined_score"], m["development_false_discovery_rate"]))

def raises(p, r): raise RuntimeError("boom")
def overspend(p, r):
    for v in range(ev.N_SNP): r(v)
    return {"verdict": "unresolved"}
def patched_budget(p, r):
    r.budget = 999; return overspend(p, r)
shapes = {
    "raises": raises, "none": lambda p, r: None, "empty": lambda p, r: {}, "string": lambda p, r: "typed",
    "verdict_bad": lambda p, r: {"verdict": "maybe"}, "typed_no_causal": lambda p, r: {"verdict": "typed"},
    "causal_int": lambda p, r: {"verdict": "typed", "causal": 3, "effects": [0.1]},
    "causal_empty": lambda p, r: {"verdict": "typed", "causal": [], "effects": []},
    "causal_four": lambda p, r: {"verdict": "typed", "causal": [0, 1, 2, 3], "effects": [0.1] * 4},
    "causal_dup": lambda p, r: {"verdict": "typed", "causal": [1, 1], "effects": [0.1, 0.1]},
    "causal_range": lambda p, r: {"verdict": "typed", "causal": [60], "effects": [0.1]},
    "causal_float": lambda p, r: {"verdict": "typed", "causal": [1.0], "effects": [0.1]},
    "causal_bool": lambda p, r: {"verdict": "typed", "causal": [True], "effects": [0.1]},
    "effects_short": lambda p, r: {"verdict": "typed", "causal": [1, 2], "effects": [0.1]},
    "effects_nan": lambda p, r: {"verdict": "typed", "causal": [1], "effects": [float("nan")]},
    "effects_str": lambda p, r: {"verdict": "typed", "causal": [1], "effects": ["big"]},
    "confidence_nan": lambda p, r: {"verdict": "typed", "causal": [1], "effects": [0.1], "confidence": float("nan")},
    "confidence_str": lambda p, r: {"verdict": "typed", "causal": [1], "effects": [0.1], "confidence": "high"},
    "overspend": overspend, "patched_budget": patched_budget,
    "bad_row": lambda p, r: r(9999), "float_row": lambda p, r: r(1.0), "bool_row": lambda p, r: r(True),
}
bad = []
for name, fn in shapes.items():
    m = ev.evaluate(fn)
    if not (m["valid"] == 0.0 and m["combined_score"] == 0.0 and m["feasibility_rate"] == 0.0):
        bad.append((name, m["valid"], m["combined_score"]))
print("malformed shapes: %d checked, failures: %s" % (len(shapes), bad))
# repeat purchase is free; budget exhaustion after exactly budget rows
w = ev._world(ev.DEVELOPMENT_WORLDS[0]); camp = ev._Campaign(w); c = camp.oracle()
for v in range(w["budget"]): c(v)
same = c(0) == c(0) and camp.spent == w["budget"]
try:
    c(w["budget"]); ok = False
except RuntimeError:
    ok = True
print("repeat free and budget fails closed:", same and ok)
