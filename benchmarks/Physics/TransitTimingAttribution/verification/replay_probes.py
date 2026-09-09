"""Replay public-input probes through the trusted Linux sandbox, not in-process."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
TASK = Path(__file__).resolve().parents[1]
TASK_ID = "Exoplanets/TransitTimingAttribution"

CONSTANT = '''
def attribute_ttv(observation, measure, budget_units):
    ids = [measure(n)["query_id"] for n in (20, 30)]
    return {"mechanism": KIND, "period": 5.2, "next_offset_days": 0.0,
            "confidence": 1.0, "evidence_query_ids": ids, "abstain": False}
'''
ORDER = '''
index = 0
def attribute_ttv(observation, measure, budget_units):
    global index
    kind = ("planet", "activity", "clock", "planet", "activity", None)[index % 6]
    index += 1
    if kind is None:
        return {"abstain": True}
    ids = [measure(n)["query_id"] for n in (20, 30)]
    return {"mechanism": kind, "period": 5.2, "next_offset_days": 0.0,
            "confidence": 1.0, "evidence_query_ids": ids, "abstain": False}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reference = (TASK / "verification/reference_solver.py").read_text(encoding="utf-8")
    candidates = {
        "baseline": (TASK / "solution.py").read_text(encoding="utf-8"),
        "reference": reference,
        "always_abstain": 'def attribute_ttv(*args): return {"abstain": True}\n',
        "order_keyed": ORDER,
        "never_abstain_reference": reference.replace(
            'if rms > 1.4*noise:', 'if False:').replace('if gap < 10.0:', 'if False:'),
    }
    for kind in ("planet", "activity", "clock"):
        candidates["constant_" + kind] = CONSTANT.replace("KIND", repr(kind))
    for budget in (2, 3, 4):
        candidates["followups_%d" % budget] = reference.replace(
            "picks[:int(budget_units)]", "picks[:min(int(budget_units), %d)]" % budget)
    candidates["no_activity_model"] = reference.replace('observation["activity_period_grid"]:', '[]:')
    candidates["constant_forecast"] = reference.replace(
        '"next_offset_days":_predict(best[2],forecast)', '"next_offset_days":0.0')
    report = {"task": TASK_ID, "source_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_tree_clean": not bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "execution": "Linux trusted driver and bubblewrap; no model generation", "probes": {}}
    with tempfile.TemporaryDirectory(prefix="ttv-probes-") as tmp:
        for name, source in candidates.items():
            candidate = Path(tmp) / (name + ".py")
            candidate.write_text(source, encoding="utf-8")
            results = []
            for _ in range(2):
                run = subprocess.run([sys.executable, "-m", "sle", "eval", "--allow-uncertified",
                    "--task", TASK_ID, "--candidate", str(candidate)], cwd=ROOT,
                    capture_output=True, text=True, timeout=300)
                if run.returncode:
                    raise RuntimeError(run.stderr[-2000:])
                results.append(json.loads(run.stdout))
            if results[0] != results[1]:
                raise AssertionError("nondeterministic probe: " + name)
            report["probes"][name] = {"complete_metrics_identical_twice": True, "metrics": results[0]}
            print(name, results[0]["combined_score"], results[0]["robustness_score"], flush=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
