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

import time
for name, fn in (("reference", ref.fine_map), ("baseline", base.fine_map)):
    t0 = time.time(); m = ev.evaluate(fn)
    print("== %s %.1fs" % (name, time.time() - t0))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != "per_instance"})
    for r in m["per_instance"]:
        print("   %-11s %-10s true %-12s claimed %-14s abst %d mech %.2f fd %d eff %.2f rows %d %s" % (
            r["split"], r["kind"], r["true_causal"], r["claimed_causal"], r["abstained"], r["mechanism_score"], r["false_discovery"], r["effect_score"], r["rows_bought"], r.get("reason", "")[:50]))
