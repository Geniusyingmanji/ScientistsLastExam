from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_radiative_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("radiative_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(coverage, mechanism, prediction, refusal=1.0, false_discovery=0.0):
    return {
        "world_count": 11,
        "supported_world_count": 7,
        "supported_claim_count": int(7 * coverage),
        "supported_discovery_coverage": coverage,
        "mean_supported_mechanism_score": mechanism,
        "mean_supported_radiance_prediction_score": prediction,
        "unsupported_world_count": 4,
        "unsupported_correct_refusal_rate": refusal,
        "unsupported_false_discovery_rate": false_discovery,
    }


def _event(step, parent, budget, calls, accepted=False):
    return {
        "step": step,
        "accepted": accepted,
        "candidate_sha256": str(step) * 64,
        "parent_sha256": parent,
        "combined_score": 0.0,
        "mechanism_score": 1.0 / 3.0,
        "robustness_score": 0.0,
        "development_supported_mechanism_score": 0.0,
        "heldout_supported_mechanism_score": 0.0,
        "development_discovery_coverage": 0.0,
        "heldout_discovery_coverage": 0.0,
        "development_false_discovery_rate": 0.0,
        "heldout_false_discovery_rate": 0.0,
        "development_correct_refusal_rate": 1.0,
        "heldout_correct_refusal_rate": 1.0,
        "development_radiance_prediction_score": 0.014,
        "heldout_radiance_prediction_score": 0.0,
        "mean_experiment_calls": calls,
        "mean_experiment_budget_units": budget,
        "valid": 1.0,
        "error_message": None,
        "candidate_failure_kind": None,
        "discovery_summary": _summary(0.0, 0.0, 0.0),
    }


def _record(label, mode, budget, tokens, usage):
    baseline = _event(0, None, 4.0, 1.0, accepted=True)
    parent = baseline["candidate_sha256"]
    proposals = [
        _event(index, parent, units, calls)
        for index, (units, calls) in enumerate(usage, 1)
    ]
    return {
        "label": label,
        "source_revision": "4" * 40,
        "feedback_mode": mode,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "server_side_seed_control": False,
        "total_tokens": tokens,
        "best_score": 0.0,
        "selected_step": 0,
        "trajectory": [baseline, *proposals],
    }


def _fixtures():
    calibration = {
        "source_revision": "4" * 40,
        "classical_metrics": {
            "combined_score": 0.614,
            "robustness_score": 0.491,
            "heldout_radiance_prediction_score": 0.812,
            "development_false_discovery_rate": 0.0,
        },
        "classical_discovery_summary": _summary(1.0, 0.61, 0.83),
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", 1, 5309, [(18.0, 2.0)]
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 17083,
            [(18.0, 2.0), (0.0, 0.0), (18.0, 2.0)],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 15961,
            [(0.0, 0.0), (18.0, 2.0), (18.0, 2.0)],
        ),
    }
    return calibration, records


class RadiativeCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_separates_validity_refusal_and_discovery(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        model = report["science_vectors"]["all_gpt55_nonbaseline_proposals"]
        self.assertEqual(model["proposal_count"], 7)
        self.assertEqual(model["refusal_R"], 1.0)
        self.assertEqual(model["mechanism_M"], 0.0)
        self.assertEqual(model["supported_discovery_coverage"], 0.0)
        self.assertEqual(
            report["proposal_usage"]["normal_budget_three"][
                "zero_experiment_proposal_count"
            ], 1,
        )

    def test_source_lineage_or_discovery_change_breaks_observed_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, False
        )["execution_passed"])
        records["blind_budget_three"]["trajectory"][2]["parent_sha256"] = "9" * 64
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])
        calibration, records = _fixtures()
        records["normal_budget_three"]["trajectory"][1][
            "discovery_summary"
        ] = _summary(1.0, 0.7, 0.9)
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
