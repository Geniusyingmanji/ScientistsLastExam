"""Evaluate a candidate on the package's own evaluator and print the summary and the per-world rows.

    .venv/bin/python .research/clock_sync/pkg_eval.py NAME [run seed shift ...]

NAME is reference, baseline, or reference@key=value,... to override the reference's configuration
(values are JSON). A shift adds 7919 per step to every world's run seed, so the queueing and the
jitter are re-drawn and the worlds are not.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parents[2] / "benchmarks/ComputerScience/ClockSyncInversion"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = load(TASK / "verification/evaluator.py", "csi_evaluator")
ref = load(TASK / "verification/reference_envelope_lp.py", "csi_reference")
base = load(TASK / "solution.py", "csi_baseline")
ORIGINAL = {s["name"]: s["run_seed"] for s in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS}


def candidate(name):
    if name == "baseline":
        return base.identify
    if name == "reference":
        return ref.identify
    if name.startswith("reference@"):
        cfg = {k: json.loads(v) for k, v in (kv.split("=", 1) for kv in name.split("@", 1)[1].split(","))}
        return lambda p, e, w: ref.identify(p, e, w, cfg)
    raise KeyError(name)


def run(identify, shift):
    for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
        spec["run_seed"] = ORIGINAL[spec["name"]] + 7919 * shift
    try:
        return ev.evaluate(identify)
    finally:
        for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
            spec["run_seed"] = ORIGINAL[spec["name"]]


def record(name, shift, m, seconds):
    rows = [(r["split"][0] + "%02d" % (r["world_index"] + 1), r["kind"][:3], r["mechanism_score"],
             "FD" if r["false_discovery"] else "", r["sharpness"], r["probes_used"], r.get("reason", ""))
            for r in m["per_instance"]]
    return {"candidate": name, "shift": shift, "seconds": round(seconds, 1),
            "dev": round(m["development_mechanism_score"], 4), "held": round(m["heldout_mechanism_score"], 4),
            "dev_fdr": m["development_false_discovery_rate"], "held_fdr": m["heldout_false_discovery_rate"],
            "valid": m["valid"], "rows": rows}


if __name__ == "__main__":
    name = (sys.argv[1:] or ["reference"])[0]
    for shift in [int(x) for x in sys.argv[2:]] or [0]:
        start = time.time()
        m = run(candidate(name), shift)
        print(json.dumps(record(name, shift, m, time.time() - start)), flush=True)
