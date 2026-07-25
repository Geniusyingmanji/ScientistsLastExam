from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_qcm_raw_pipeline_calibrations.py"
SPEC = importlib.util.spec_from_file_location("qcm_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _metrics(coverage=0.0, refusal=1.0, false_discovery=0.0, diagnosis=0.0):
    result = {field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS}
    result.update({
        "combined_score": 0.0,
        "raw_score": 0.0,
        "feasibility_rate": 1.0,
        "heldout_feasibility_rate": 1.0,
        "development_lineage_score": 1.0,
        "heldout_lineage_score": 1.0,
        "development_supported_claim_coverage": coverage,
        "heldout_supported_claim_coverage": coverage,
        "development_unsupported_refusal_rate": refusal,
        "heldout_unsupported_refusal_rate": refusal,
        "development_false_discovery_rate": false_discovery,
        "heldout_false_discovery_rate": false_discovery,
        "development_fault_diagnosis_accuracy": diagnosis,
        "heldout_fault_diagnosis_accuracy": diagnosis,
        "candidate_instance_call_count": 10.0,
        "candidate_instance_valid_rate": 1.0,
    })
    return result


def _event(step, candidate, parent, metrics, accepted=False):
    return {
        "step": step,
        "score": 0.0,
        "best_score": 0.0,
        "valid": True,
        "accepted": accepted,
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "failure_kind": None,
        "infrastructure_failure": False,
        "science_metrics": metrics,
    }


def _record(label, mode, events, tokens):
    budget = len(events) - 1
    selected = events[0]
    return {
        "label": label,
        "source_revision": "model",
        "source_scope": ["frontier_science", "benchmarks"],
        "llm_condition_sha256": "condition",
        "task_contract_sha256": "contract",
        "runtime_source_sha256": "runtime",
        "feedback_mode": mode,
        "seed": 0 if label == "budget_one" else 1,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "best_score": 0.0,
        "best_so_far_auc": 0.0,
        "accepted_proposals": 0,
        "selected_step": 0,
        "selected_metrics": selected["science_metrics"],
        "highest_scoring_valid_proposal_metrics": events[1]["science_metrics"],
        "valid_proposal_count": budget,
        "retained_artifact_scans": {
            "best_program": {"passed": True},
            "terminal_program": {"passed": True},
        },
        "best_program_sha256": "base",
        "terminal_program_sha256": events[-1]["candidate_sha256"],
        "integrity_passed": True,
        "trajectory": events,
    }


def _records():
    baseline = _event(0, "base", None, _metrics(), accepted=True)
    one = _record(
        "budget_one", "normal",
        [baseline, _event(1, "one", "base", _metrics(diagnosis=0.5))],
        6058,
    )

    normal_events = [baseline]
    normal_events.append(_event(
        1, "normal1", "base", _metrics(1.0, 0.0, 0.5)
    ))
    normal_events.append(_event(2, "normal2", "base", _metrics()))
    normal_events.append(_event(
        3, "normal3", "base", _metrics(diagnosis=0.5)
    ))
    normal = _record(
        "normal_budget_three", "normal", normal_events, 18662
    )

    blind_events = [baseline]
    blind_events.append(_event(
        1, "blind1", "base", _metrics(diagnosis=0.5)
    ))
    partial = _metrics(2.0 / 3.0, 1.0 / 3.0, 0.5, 0.5)
    partial["heldout_supported_claim_coverage"] = 0.0
    partial["heldout_unsupported_refusal_rate"] = 0.5
    partial["heldout_false_discovery_rate"] = 1.0
    blind_events.append(_event(2, "blind2", "base", partial))
    blind_events.append(_event(
        3, "blind3", "base", _metrics(diagnosis=0.5)
    ))
    blind = _record(
        "blind_budget_three", "selection_blind", blind_events, 17797
    )
    return {
        "budget_one": one,
        "normal_budget_three": normal,
        "blind_budget_three": blind,
    }


class QCMRawPipelineAnalysisTests(unittest.TestCase):
    def test_analysis_separates_valid_zero_score_failure_modes(self):
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"},
            _records(),
            calibration_source_revision="calibration",
            model_source_revision="model",
        )
        self.assertTrue(report["execution_passed"], report)
        hurdle = report["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 7)
        self.assertEqual(hurdle["valid_nonzero_proposal_count"], 0)
        self.assertEqual(hurdle["valid_all_refusal_proposal_count"], 5)
        self.assertEqual(hurdle["valid_all_claim_proposal_count"], 1)
        self.assertEqual(
            hurdle["valid_partial_development_nontransfer_proposal_count"], 1
        )
        self.assertEqual(
            hurdle["valid_zero_science_pipeline_proposal_count"], 7
        )
        findings = report["descriptive_findings"]
        self.assertTrue(findings[
            "all_seven_proposals_are_valid_but_score_zero"
        ])
        self.assertTrue(findings[
            "one_proposal_claims_every_world_and_has_false_discoveries"
        ])
        self.assertFalse(findings["normal_and_blind_are_token_matched"])
        self.assertFalse(findings["feedback_effect_identified"])

    def test_shortcut_scan_rejects_world_and_evaluator_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = Path(temporary) / "clean.py"
            clean.write_text(
                "def analyze_qcm(problem):\n    return {'abstain': True}\n",
                encoding="utf-8",
            )
            bad = Path(temporary) / "bad.py"
            bad.write_text(
                "def analyze_qcm(problem):\n"
                "    return '31801', 'verification/evaluator.py'\n",
                encoding="utf-8",
            )
            self.assertTrue(ANALYSIS._shortcut_scan(clean)["passed"])
            scan = ANALYSIS._shortcut_scan(bad)
            self.assertFalse(scan["passed"])
            self.assertEqual(scan["fixed_world_literal_hits"], ["31801"])
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
        records["blind_budget_three"]["trajectory"][3][
            "parent_sha256"
        ] = "blind2"
        self.assertFalse(ANALYSIS._lineage_is_valid(
            records["blind_budget_three"]
        ))

    def test_runtime_source_change_fails_closed(self):
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"},
            _records(),
            runtime_source_equivalent=False,
            runtime_source_changes=["benchmarks/Sensors/x.py"],
            calibration_source_revision="calibration",
            model_source_revision="model",
        )
        self.assertFalse(report["execution_passed"])


if __name__ == "__main__":
    unittest.main()
