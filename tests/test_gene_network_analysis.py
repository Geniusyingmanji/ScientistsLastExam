from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_gene_network_intervention_calibrations.py"
SPEC = importlib.util.spec_from_file_location("gene_network_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _event(step, valid, failure=None, all_refusal=False):
    metrics = {field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS}
    if all_refusal:
        metrics.update({
            "development_unsupported_refusal_rate": 1.0,
            "heldout_unsupported_refusal_rate": 1.0,
        })
    return {
        "step": step,
        "valid": valid,
        "score": 0.0,
        "best_score": 0.0,
        "accepted": step == 0,
        "candidate_sha256": str(step),
        "parent_sha256": None if step == 0 else "0",
        "failure_kind": failure,
        "science_metrics": metrics,
    }


def _record(label, mode, budget, proposal_events, tokens):
    trajectory = [_event(0, True, all_refusal=True)] + proposal_events
    failure_counts = {}
    for event in proposal_events:
        failure = event["failure_kind"]
        if failure:
            failure_counts[failure] = failure_counts.get(failure, 0) + 1
    return {
        "label": label,
        "source_revision": "model",
        "source_scope": ["sle", "benchmarks"],
        "llm_condition_sha256": "condition",
        "feedback_mode": mode,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "best_score": 0.0,
        "valid_proposal_count": sum(e["valid"] for e in proposal_events),
        "invalid_proposal_count": sum(not e["valid"] for e in proposal_events),
        "valid_nonzero_proposal_count": 0,
        "valid_all_refusal_proposal_count": sum(
            e["valid"]
            and e["science_metrics"]["development_supported_claim_coverage"] == 0.0
            and e["science_metrics"]["heldout_supported_claim_coverage"] == 0.0
            and e["science_metrics"]["development_unsupported_refusal_rate"] == 1.0
            and e["science_metrics"]["heldout_unsupported_refusal_rate"] == 1.0
            for e in proposal_events
        ),
        "failure_counts": failure_counts,
        "integrity_passed": True,
        "trajectory": trajectory,
    }


class GeneNetworkAnalysisTests(unittest.TestCase):
    def test_hurdle_summary_separates_invalid_and_valid_refusal(self):
        one = _record(
            "budget_one", "normal", 1,
            [_event(1, False, "candidate_callback_schema_error")], 100,
        )
        normal = _record(
            "normal_budget_three", "normal", 3,
            [
                _event(1, False, "invalid_experiment"),
                _event(2, False, "candidate_callback_schema_error"),
                _event(3, False, "invalid_experiment"),
            ], 300,
        )
        blind = _record(
            "blind_budget_three", "selection_blind", 3,
            [
                _event(1, False, "invalid_experiment"),
                _event(2, False, "invalid_experiment"),
                _event(3, True, all_refusal=True),
            ], 250,
        )
        report = ANALYSIS._analyze_records(
            {"source_revision": ANALYSIS.EXPECTED_TASK_SOURCE_REVISION},
            {
                "budget_one": one,
                "normal_budget_three": normal,
                "blind_budget_three": blind,
            },
            runtime_source_equivalent=True,
            expected_model_source_revision="model",
        )
        hurdle = report["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 1)
        self.assertEqual(hurdle["invalid_proposal_count"], 6)
        self.assertEqual(hurdle["valid_all_refusal_proposal_count"], 1)
        self.assertEqual(hurdle["failure_counts"]["invalid_experiment"], 4)
        self.assertEqual(
            hurdle["failure_counts"]["candidate_callback_schema_error"], 2
        )
        self.assertTrue(report["execution_passed"])
        self.assertFalse(
            report["descriptive_findings"]["feedback_effect_identified"]
        )

    def test_failure_kind_prefers_sanitized_taxonomy(self):
        event = {
            "metrics": {
                "candidate_failure_kind": "candidate_callback_schema_error",
                "error_message": "candidate invalid: something_else",
            },
            "error": "candidate invalid: third_value",
        }
        self.assertEqual(
            ANALYSIS._failure_kind(event), "candidate_callback_schema_error"
        )


if __name__ == "__main__":
    unittest.main()
