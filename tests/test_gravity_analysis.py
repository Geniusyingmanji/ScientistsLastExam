from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_gravity_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("gravity_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, robustness, prediction, valid=True, error=None):
    return {
        "combined_score": score, "mechanism_score": (1 + 2 * score) / 3,
        "robustness_score": robustness,
        "heldout_mechanism_score": 0.4 + 0.6 * robustness,
        "development_body_support_f1": score,
        "heldout_body_support_f1": robustness,
        "development_field_component_score": score,
        "heldout_field_component_score": robustness,
        "development_mass_moment_score": score,
        "heldout_mass_moment_score": robustness,
        "development_observed_fit_score": prediction,
        "heldout_observed_fit_score": prediction,
        "development_prediction_score": prediction,
        "heldout_prediction_score": prediction,
        "development_extrapolation_score": prediction,
        "heldout_extrapolation_score": prediction,
        "development_false_discovery_rate": 0.0,
        "heldout_false_discovery_rate": 0.0,
        "development_correct_refusal_rate": 1.0,
        "heldout_correct_refusal_rate": 1.0,
        "mean_survey_calls": 3.0, "mean_survey_budget_units": 21.0,
        "valid": valid, "error_message": error,
    }


def _event(step, accepted, parent, metrics):
    return {
        "step": step, "accepted": accepted,
        "candidate_sha256": str(step) * 64, "parent_sha256": parent,
        **metrics,
    }


def _fixtures():
    base = _event(0, True, None, _metrics(0.0, 0.0, 0.0))
    invalid = _event(
        1, False, "0" * 64,
        _metrics(-1e18, 0.0, 0.0, False, "invalid budget_cost protocol"),
    )
    first = _event(1, True, "0" * 64, _metrics(0.993, 0.754, 0.987))
    second = _event(2, False, "1" * 64, _metrics(0.992, 0.778, 0.989))
    final = _event(3, True, "1" * 64, _metrics(0.994, 0.767, 0.989))
    common = {
        "source_revision": "3" * 40, "server_side_seed_control": False,
    }
    records = {
        "budget_one": {
            **common, "proposal_budget": 1, "oracle_calls": 2,
            "selected_step": 0, "best_score": 0.0,
            "selected_metrics": {key: value for key, value in base.items()
                                 if key not in {"step", "accepted", "candidate_sha256", "parent_sha256"}},
            "trajectory": [base, invalid], "selected_worlds": [],
        },
        "budget_three": {
            **common, "proposal_budget": 3, "oracle_calls": 4,
            "selected_step": 3, "best_score": 0.994,
            "selected_metrics": {key: value for key, value in final.items()
                                 if key not in {"step", "accepted", "candidate_sha256", "parent_sha256"}},
            "trajectory": [base, first, second, final],
            "selected_worlds": [{
                "split": "heldout", "world_index": 0, "kind": "in_library",
                "mechanism_score": 0.35, "body_support_f1": 0.34,
                "field_component_score": 0.34, "mass_moment_score": 0.37,
                "observed_fit_score": 0.94,
                "interpolation_prediction_score": 0.975,
                "extrapolation_prediction_score": 0.92,
                "correct_refusal": False, "false_discovery": False,
                "abstained": False, "n_true_bodies": 3,
                "n_predicted_bodies": 3, "survey_calls": 3,
                "survey_budget_units": 21,
            }],
        },
    }
    calibration = {"source_revision": "3" * 40}
    return calibration, records


class GravityCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_preserves_field_mechanism_and_selection_gaps(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertGreater(
            report["field_prediction_internal_geology_counterexample"][
                "interpolation_prediction_score"
            ], 0.95,
        )
        self.assertLess(
            report["field_prediction_internal_geology_counterexample"][
                "mechanism_score"
            ], 0.4,
        )
        self.assertGreater(
            report["rejected_candidate_with_higher_heldout_mechanism"][
                "robustness_score"
            ], report["selected_science_vector"]["validity_V"],
        )

    def test_source_mismatch_or_erased_mechanism_gap_breaks_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, False
        )["execution_passed"])
        records["budget_three"]["selected_worlds"][0]["mechanism_score"] = 0.8
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
