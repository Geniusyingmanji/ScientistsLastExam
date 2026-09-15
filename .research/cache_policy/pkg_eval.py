"""Evaluate a candidate on the package's own evaluator and print the summary and the per-world rows.

    .venv/bin/python .research/cache_policy/pkg_eval.py [reference|original|baseline] [seed shift ...]
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parents[2] / "benchmarks/ComputerScience/CacheReplacementPolicyID"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = load(TASK / "verification/evaluator.py", "crp_evaluator")
CANDIDATES = {
    "reference": lambda: load(TASK / "verification/reference_permutation_augmented.py", "crp_reference").identify,
    "original": lambda: load(TASK / "verification/reference_lstar_family.py", "crp_original_reference").identify,
    "baseline": lambda: load(TASK / "solution.py", "crp_baseline").identify,
}

if __name__ == "__main__":
    name = (sys.argv[1:] or ["reference"])[0]
    shifts = [int(x) for x in sys.argv[2:]] or [0]
    original = {s["name"]: s["seed"] for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS}
    for shift in shifts:
        for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
            spec["seed"] = original[spec["name"]] + 7919 * shift
        ev._WORLDS.clear()
        start = time.time()
        m = ev.evaluate(CANDIDATES[name]())
        rows = [(r["split"][0] + "%02d" % (r["world_index"] + 1), r["kind"][:4], r["mechanism_score"],
                 "FD" if r["false_discovery"] else "", r["states_submitted"], r["runs_used"], r.get("reason", ""))
                for r in m["per_instance"]]
        print(json.dumps({"candidate": name, "shift": shift, "seconds": round(time.time() - start, 1),
                          "dev": round(m["development_mechanism_score"], 4), "held": round(m["heldout_mechanism_score"], 4),
                          "dev_fdr": m["development_false_discovery_rate"], "held_fdr": m["heldout_false_discovery_rate"],
                          "valid": m["valid"], "rows": rows}), flush=True)
