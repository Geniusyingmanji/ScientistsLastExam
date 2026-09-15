from __future__ import annotations

import importlib.util
import copy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_catalyst_deactivation_lab_calibrations.py"
SPEC = importlib.util.spec_from_file_location("catalyst_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _metrics(
    score=0.0,
    coverage=0.0,
    refusal=1.0,
    false_discovery=0.0,
    physical_acts=3.0,
    out_of_order=0.0,
):
    result = {field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS}
    result.update({
        "combined_score": score,
        "raw_score": score,
        "feasibility_rate": 1.0,
        "heldout_feasibility_rate": 1.0,
        "development_lineage_score": 1.0,
        "heldout_lineage_score": 1.0,
        "development_mechanism_score": 0.14 if score else 0.0,
        "heldout_mechanism_score": 0.25 if score else 0.0,
        "development_prediction_score": 0.001 if score else 0.0,
        "heldout_prediction_score": 0.16 if score else 0.0,
        "development_decision_score": 0.0,
        "heldout_decision_score": 0.35 if score else 0.0,
        "development_supported_claim_coverage": coverage,
        "heldout_supported_claim_coverage": coverage,
        "development_unsupported_refusal_rate": refusal,
        "heldout_unsupported_refusal_rate": refusal,
        "development_false_discovery_rate": false_discovery,
        "heldout_false_discovery_rate": false_discovery,
        "development_mean_physical_acts": physical_acts,
        "heldout_mean_physical_acts": physical_acts,
        "development_mean_coupon_reactions": max(0.0, physical_acts - 4.0),
        "heldout_mean_coupon_reactions": max(0.0, physical_acts - 4.0),
        "development_mean_out_of_order_batches": out_of_order,
        "heldout_mean_out_of_order_batches": out_of_order,
        "candidate_instance_call_count": 8.0,
        "candidate_instance_valid_rate": 1.0,
    })
    return result


def _event(step, candidate, parent, metrics, valid=True, accepted=False, failure=None):
    return {
        "step": step,
        "score": metrics["combined_score"],
        "best_score": metrics["combined_score"],
        "valid": valid,
        "accepted": accepted,
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "failure_kind": failure,
        "infrastructure_failure": False,
        "science_metrics": metrics,
    }


def _record(label, mode, events, best_index, tokens):
    budget = len(events) - 1
    selected = events[best_index]
    best_hash = selected["candidate_sha256"]
    terminal_hash = events[-1]["candidate_sha256"]
    proposals = events[1:]
    valid = [event for event in proposals if event["valid"]]
    highest = max(valid, key=lambda event: event["score"])
    return {
        "label": label,
        "source_revision": "model",
        "source_scope": ["sle", "benchmarks"],
        "llm_condition_sha256": "condition",
        "task_contract_sha256": "contract",
        "runtime_source_sha256": "runtime",
        "trusted_evaluator_runtime_sha256": "trusted-runtime",
        "feedback_mode": mode,
        "seed": 0 if label == "budget_one" else 1,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "best_score": selected["score"],
        "best_so_far_auc": selected["score"] / 2.0,
        "accepted_proposals": sum(event["accepted"] for event in proposals),
        "selected_metrics": selected["science_metrics"],
        "highest_scoring_valid_proposal_metrics": highest["science_metrics"],
        "valid_proposal_count": len(valid),
        "retained_artifact_scans": {
            "best_program": {"passed": True},
            "terminal_program": {"passed": True},
        },
        "best_program_sha256": best_hash,
        "terminal_program_sha256": terminal_hash,
        "integrity_passed": True,
        "trajectory": events,
    }


def _records():
    baseline = _event(0, "base", None, _metrics(), accepted=True)
    one_proposal = _event(
        1, "one", "base", _metrics(physical_acts=5.0), accepted=False
    )
    one = _record(
        "budget_one", "normal", [baseline, one_proposal], 0, 5000
    )

    normal_events = [baseline]
    parent = "base"
    for step, score, accepted in ((1, 0.05, True), (2, 0.075, True), (3, 0.07, False)):
        candidate = "normal%d" % step
        normal_events.append(_event(
            step,
            candidate,
            parent,
            _metrics(score, 1.0, 0.0, 0.4, 12.0),
            accepted=accepted,
        ))
        if accepted:
            parent = candidate
    normal = _record(
        "normal_budget_three", "normal", normal_events, 2, 25000
    )

    blind_events = [baseline]
    blind_events.append(_event(
        1,
        "blind1",
        "base",
        _metrics(physical_acts=12.0),
        valid=False,
        failure="invalid_submission",
    ))
    blind_events.append(_event(
        2,
        "blind2",
        "base",
        _metrics(0.041, 1.0, 0.0, 0.4, 12.0, 2.0),
        accepted=True,
    ))
    blind_events.append(_event(
        3, "blind3", "base", _metrics(physical_acts=3.0), accepted=False
    ))
    blind = _record(
        "blind_budget_three", "selection_blind", blind_events, 2, 18000
    )
    return {
        "budget_one": one,
        "normal_budget_three": normal,
        "blind_budget_three": blind,
    }


class CatalystDeactivationAnalysisTests(unittest.TestCase):
    def test_analysis_separates_science_hurdles_and_state_use(self):
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"},
            _records(),
            calibration_source_revision="calibration",
            model_source_revision="model",
        )
        self.assertTrue(report["execution_passed"], report)
        self.assertTrue(report["input_trusted_evaluator_runtime_equivalent"])
        hurdle = report["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 6)
        self.assertEqual(hurdle["failure_counts"], {"invalid_submission": 1})
        self.assertEqual(hurdle["infrastructure_failure_count"], 0)
        self.assertEqual(hurdle["valid_all_refusal_proposal_count"], 2)
        findings = report["descriptive_findings"]
        self.assertTrue(findings[
            "budget_one_proposal_is_valid_conservative_all_refusal"
        ])
        self.assertTrue(findings[
            "normal_and_blind_selected_fail_all_unsupported_refusals"
        ])
        self.assertTrue(findings["blind_selected_uses_out_of_order_batches"])
        self.assertFalse(findings["normal_selected_uses_out_of_order_batches"])
        self.assertFalse(findings["feedback_effect_identified"])

    def test_shortcut_scan_rejects_world_and_evaluator_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = Path(temporary) / "clean.py"
            clean.write_text(
                "def investigate_catalyst(problem, experiment):\n"
                "    return {'abstain': True}\n",
                encoding="utf-8",
            )
            bad = Path(temporary) / "bad.py"
            bad.write_text(
                "def investigate_catalyst(problem, experiment):\n"
                "    return '18401', 'verification/evaluator.py'\n",
                encoding="utf-8",
            )
            self.assertTrue(ANALYSIS._shortcut_scan(clean)["passed"])
            scan = ANALYSIS._shortcut_scan(bad)
            self.assertFalse(scan["passed"])
            self.assertEqual(scan["fixed_world_literal_hits"], ["18401"])
            self.assertEqual(
                scan["evaluator_source_term_hits"],
                ["evaluator.py", "verification/evaluator"],
            )

    def test_lineage_distinguishes_online_and_frozen_parent(self):
        records = _records()
        self.assertTrue(ANALYSIS._lineage_is_valid(
            records["normal_budget_three"]
        ))
        self.assertTrue(ANALYSIS._lineage_is_valid(
            records["blind_budget_three"]
        ))
        records["blind_budget_three"]["trajectory"][3]["parent_sha256"] = "blind2"
        self.assertFalse(ANALYSIS._lineage_is_valid(
            records["blind_budget_three"]
        ))

    def test_failure_kind_uses_per_world_invalid_submission(self):
        event = {
            "metrics": {
                "per_world": [
                    {"failure_kind": "invalid_submission"},
                    {"failure_kind": "invalid_submission"},
                ]
            }
        }
        self.assertEqual(ANALYSIS._failure_kind(event), "invalid_submission")

    def test_runtime_source_change_fails_closed(self):
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"},
            _records(),
            runtime_source_equivalent=False,
            runtime_source_changes=["benchmarks/Chemistry/CatalystDeactivationLab/x.py"],
            calibration_source_revision="calibration",
            model_source_revision="model",
        )
        self.assertFalse(report["execution_passed"])

    def test_trusted_evaluator_runtime_mismatch_fails_closed(self):
        records = copy.deepcopy(_records())
        records["blind_budget_three"][
            "trusted_evaluator_runtime_sha256"
        ] = "other-runtime"
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"}, records,
            calibration_source_revision="calibration",
            model_source_revision="model",
        )
        self.assertFalse(report["execution_passed"])


if __name__ == "__main__":
    unittest.main()
