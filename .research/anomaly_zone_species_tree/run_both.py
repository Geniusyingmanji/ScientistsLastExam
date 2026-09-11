import os as _os, tempfile as _tempfile
TASK = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "benchmarks", "Biology", "AnomalyZoneSpeciesTree"))
OUT = _tempfile.gettempdir()
import sys, time, importlib.util, json
sys.path.insert(0, TASK + "/verification")
import evaluator as ev
if _os.environ.get("AZ_PATCH"):
    sys.path.insert(0, _os.path.dirname(_os.environ["AZ_PATCH"])); import patch; print("patch:", patch.apply(ev), flush=True)
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
ref = load(TASK + "/verification/reference_quartet_consensus.py", "ref")
base = load(TASK + "/solution.py", "base")
for name, fn in [("reference", ref.infer_species_tree), ("baseline", base.infer_species_tree)]:
    t = time.time(); m = ev.evaluate(fn); dt = time.time() - t
    print("== %s  %.1fs" % (name, dt))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != "per_instance"})
    for r in m["per_instance"]:
        print("  %-11s %-11s valid=%s abst=%s topo=%s bl=%.2f mech=%.2f fd=%s spent=%d %s" % (
            r["split"], r["kind"], r["valid"], r["abstained"], r["topology_correct"], r["branch_length_score"],
            r["mechanism_score"], r["false_discovery"], r["budget_spent"], r.get("reason", "")[:60]))
