from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_ocean_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("ocean_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(coverage, mechanism, refusal=1.0, false_discovery=0.0):
    return {
        "world_count": 11,
        "in_library_world_count": 7,
        "in_library_claim_count": int(7 * coverage),
        "in_library_claim_coverage": coverage,
        "mean_in_library_mechanism_score": mechanism,
        "unsupported_world_count": 4,
        "unsupported_correct_refusal_rate": refusal,
        "unsupported_false_discovery_rate": false_discovery,
    }


def _event(step, parent, valid, failure=None, summary=None):
    score = 0.0 if valid else -1e18
    return {
        "step": step,
        "accepted": step == 0,
        "candidate_sha256": str(step) * 64,
        "parent_sha256": parent,
        "combined_score": score,
        "mechanism_score": 1.0 / 3.0 if valid else None,
        "robustness_score": 0.0 if valid else None,
        "heldout_trajectory_prediction_score": 0.0 if valid else None,
        "development_false_discovery_rate": 0.0 if valid else None,
        "mean_experiment_calls": 2.0 if step == 1 and valid else 1.0,
        "mean_experiment_budget_units": 12.0 if step == 1 and valid else 3.0,
        "valid": 1.0 if valid else 0.0,
        "error_message": failure,
        "failure_kind": failure,
        "discovery_summary": summary if valid else None,
    }


def _record(label, mode, budget, tokens, proposals):
    baseline = _event(0, None, True, summary=_summary(0.0, 0.0))
    return {
        "label": label,
        "source_revision": "3" * 40,
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
    parent = "0" * 64
    geometry = _event(1, parent, False, "invalid_experiment_geometry")
    valid_zero = _event(1, parent, True, summary=_summary(0.0, 0.0))
    callback2 = _event(2, parent, False, "callback_schema_misread")
    callback3 = _event(3, parent, False, "callback_schema_misread")
    records = {
        "budget_one": _record("budget_one", "normal", 1, 5500, [geometry]),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 16600,
            [valid_zero, callback2, callback3],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 16100,
            [
                _event(1, parent, False, "callback_schema_misread"),
                callback2,
                callback3,
            ],
        ),
    }
    calibration = {
        "source_revision": "3" * 40,
        "classical_metrics": {
            "combined_score": 0.707,
            "robustness_score": 0.406,
            "heldout_trajectory_prediction_score": 0.55,
            "development_false_discovery_rate": 0.0,
        },
        "classical_discovery_summary": _summary(1.0, 0.578),
    }
    return calibration, records


class OceanCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_separates_refusal_from_in_library_discovery(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        model = report["science_vectors"]["gpt55_only_valid_nonbaseline_proposal"]
        self.assertEqual(model["refusal_R"], 1.0)
        self.assertEqual(model["mechanism_M"], 0.0)
        self.assertEqual(model["in_library_discovery_coverage"], 0.0)
        self.assertEqual(
            report["protocol_failure_counts"]["blind_budget_three"],
            {"callback_schema_misread": 3},
        )

    def test_source_lineage_or_mechanism_change_breaks_observed_gate(self):
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
        records["normal_budget_three"]["trajectory"][1]["discovery_summary"] = _summary(1.0, 0.7)
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
