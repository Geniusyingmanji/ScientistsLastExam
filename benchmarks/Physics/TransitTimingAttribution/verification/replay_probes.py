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
    start = max(map(int, observation["transit_numbers"])) + 1
    ids = [measure(start + offset)["query_id"] for offset in (0, 1)]
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
    start = max(map(int, observation["transit_numbers"])) + 1
    ids = [measure(start + offset)["query_id"] for offset in (0, 1)]
    return {"mechanism": kind, "period": 5.2, "next_offset_days": 0.0,
            "confidence": 1.0, "evidence_query_ids": ids, "abstain": False}
'''

REFERENCE_CALL = '''
    return _attribute_ttv(observation, measure, LIMIT, 1.3, 0.0, 0.5,
                          alternative_gap_limit=ALT_GAP, anchors=(), model_limit=24,
                          bic_temperature=0.08, family_floor=0.0,
                          family_temperature=0.25, between_family_weight=4.0)
'''


def _override(limit, alternative_gap="6.0", prefix=""):
    body = REFERENCE_CALL.replace("LIMIT", limit).replace("ALT_GAP", alternative_gap)
    return "\ndef attribute_ttv(observation, measure, budget_units):\n" + prefix + body


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
        "never_abstain_reference": reference + _override("budget_units", "-1e9"),
        "fixed_schedule_shortcut": (
            TASK / "verification/reference_no_active_design.py"
        ).read_text(encoding="utf-8"),
    }
    for kind in ("planet", "activity", "clock"):
        candidates["constant_" + kind] = CONSTANT.replace("KIND", repr(kind))
    candidates["three_followups"] = reference + _override("min(budget_units, 3)")
    candidates["no_out_of_family_evidence"] = reference + _override(
        "budget_units", "-1e9"
    )
    no_activity = '''
    observation = dict(observation)
    observation["activity_period_grid"] = []
'''
    candidates["no_activity_model"] = reference + _override(
        "budget_units", prefix=no_activity
    )
    forecast = '''
_active_reference = attribute_ttv
def attribute_ttv(observation, measure, budget_units):
    result = _active_reference(observation, measure, budget_units)
    if not result.get("abstain"):
        result["next_offset_days"] = 0.0
    return result
'''
    candidates["constant_forecast"] = reference + forecast

    report = {
        "schema_version": 1,
        "task": TASK_ID,
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_tree_clean": not bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "execution": "Linux trusted driver and bubblewrap",
        "model_generation": False,
        "probes": {},
    }
    with tempfile.TemporaryDirectory(prefix="ttv-probes-") as tmp:
        for name, source in candidates.items():
            candidate = Path(tmp) / (name + ".py")
            candidate.write_text(source, encoding="utf-8")
            results = []
            for _ in range(2):
                run = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "sle",
                        "eval",
                        "--allow-uncertified",
                        "--task",
                        TASK_ID,
                        "--candidate",
                        str(candidate),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if run.returncode:
                    raise RuntimeError(run.stderr[-2000:])
                results.append(json.loads(run.stdout))
            if results[0] != results[1]:
                raise AssertionError("nondeterministic probe: " + name)
            complete = json.dumps(results[0], sort_keys=True, separators=(",", ":"))
            keys = (
                "combined_score",
                "robustness_score",
                "valid",
                "development_design_score",
                "development_mechanism_correct_count",
                "development_mechanism_total_count",
                "development_false_discovery_count",
                "development_false_discovery_denominator",
                "development_correct_refusal_count",
                "development_correct_refusal_denominator",
                "heldout_design_score",
                "heldout_mechanism_correct_count",
                "heldout_mechanism_total_count",
                "heldout_false_discovery_count",
                "heldout_false_discovery_denominator",
                "heldout_correct_refusal_count",
                "heldout_correct_refusal_denominator",
            )
            report["probes"][name] = {
                "complete_metrics_identical_twice": True,
                "complete_metrics_sha256": hashlib.sha256(
                    complete.encode("utf-8")
                ).hexdigest(),
                "metrics": {key: results[0][key] for key in keys},
            }
            print(
                name,
                results[0]["combined_score"],
                results[0]["robustness_score"],
                flush=True,
            )
    Path(args.output).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
