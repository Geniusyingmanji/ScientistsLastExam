"""Replay public-input probes through the trusted Linux sandbox, not in-process."""
from __future__ import annotations
import argparse
import hashlib
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
NEVER_ABSTAIN = '''
def attribute_ttv(observation, measure, budget_units):
    return _attribute_ttv(observation, measure, budget_units, 99.0, -99.0, 99.0)
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
        "never_abstain_reference": reference + "\n" + NEVER_ABSTAIN,
        "fixed_schedule_shortcut": (TASK / "verification/shortcut_family_a.py").read_text(
            encoding="utf-8"),
    }
    for kind in ("planet", "activity", "clock"):
        candidates["constant_" + kind] = CONSTANT.replace("KIND", repr(kind))
    for budget in (2, 3, 4):
        candidates["followups_%d" % budget] = reference.replace(
            "return _attribute_ttv(observation,measure,budget_units,1.00,6.0,0.80)",
            "return _attribute_ttv(observation,measure,min(budget_units,%d),1.00,6.0,0.80)" % budget)
    candidates["no_activity_model"] = reference.replace(
        'for p in observation["activity_period_grid"]', 'for p in []')
    candidates["constant_forecast"] = reference.replace(
        '"next_offset_days":_predict(best[2],forecast)', '"next_offset_days":0.0')
    report = {"schema_version":1,"task": TASK_ID, "source_revision": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_tree_clean": not bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "execution": "Linux trusted driver and bubblewrap", "model_generation":False,
        "probes": {}}
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
            complete=json.dumps(results[0],sort_keys=True,separators=(",",":"))
            keys=("combined_score","robustness_score","valid",
                  "development_mechanism_correct_count","development_mechanism_total_count",
                  "development_false_discovery_count","development_false_discovery_denominator",
                  "development_correct_refusal_count","development_correct_refusal_denominator",
                  "heldout_mechanism_correct_count","heldout_mechanism_total_count",
                  "heldout_false_discovery_count","heldout_false_discovery_denominator",
                  "heldout_correct_refusal_count","heldout_correct_refusal_denominator")
            report["probes"][name]={
                "complete_metrics_identical_twice":True,
                "complete_metrics_sha256":hashlib.sha256(complete.encode("utf-8")).hexdigest(),
                "metrics":{key:results[0][key] for key in keys},
            }
            print(name, results[0]["combined_score"], results[0]["robustness_score"], flush=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
