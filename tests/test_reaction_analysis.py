from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_reaction_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("reaction_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, prediction, robustness, false_discovery, calls):
    raw = 1.0 / 3.0 + 2.0 / 3.0 * score
    return {
        "combined_score": score, "mechanism_score": raw,
        "robustness_score": robustness,
        "heldout_mechanism_score": 0.4 + 0.6 * robustness,
        "development_support_f1": max(score, 0.65 if score else 0.0),
        "heldout_support_f1": max(robustness, 0.6 if robustness else 0.0),
        "development_rate_curve_score": score,
        "heldout_rate_curve_score": robustness,
        "development_prediction_score": prediction,
        "heldout_prediction_score": prediction * 0.75,
        "development_extrapolation_score": prediction + 0.03,
        "heldout_extrapolation_score": prediction * 0.8,
        "development_misspecified_prediction_score": 0.0,
        "heldout_misspecified_prediction_score": 0.0,
        "development_confidence_calibration_score": 0.8,
        "heldout_confidence_calibration_score": 0.8,
        "development_false_discovery_rate": false_discovery,
        "heldout_false_discovery_rate": false_discovery,
        "development_correct_refusal_rate": 1.0 - false_discovery,
        "heldout_correct_refusal_rate": 1.0 - false_discovery,
        "mean_experiment_calls": calls,
        "mean_experiment_budget_units": 10.0 if calls == 2.0 else 3.0,
        "valid": 1.0,
    }


def _event(step, accepted, parent, metrics):
    return {
        "step": step, "accepted": accepted,
        "candidate_sha256": str(step) * 64,
        "parent_sha256": parent, **metrics,
    }


def _record(label, mode, budget, tokens, events, selected_step):
    return {
        "label": label, "source_revision": "3" * 40,
        "feedback_mode": mode,
        "proposal_budget": budget, "oracle_calls": budget + 1,
        "server_side_seed_control": False, "total_tokens": tokens,
        "best_score": events[selected_step]["combined_score"],
        "selected_step": selected_step,
        "selected_metrics": {
            key: value for key, value in events[selected_step].items()
            if key not in {"step", "accepted", "candidate_sha256", "parent_sha256"}
        },
        "trajectory": events,
    }


def _fixtures():
    baseline_metrics = _metrics(0.0, 0.0, 0.0, 0.0, 1.0)
    baseline = _event(0, True, None, baseline_metrics)
    zero = _event(1, False, "0" * 64, baseline_metrics)
    blind_best = _event(1, True, "0" * 64, _metrics(0.343, 0.47, 0.36, 0.5, 2.0))
    blind_low = _event(2, False, "0" * 64, _metrics(0.14, 0.01, 0.01, 0.5, 2.0))
    blind_predictive = _event(3, False, "0" * 64, _metrics(0.259, 0.711, 0.22, 0.5, 2.0))
    calibration = {
        "source_revision": "3" * 40,
        "classical_metrics": _metrics(0.482, 0.86, 0.404, 0.5, 2.0),
    }
    records = {
        "budget_one": _record("budget_one", "normal", 1, 6000,
                              [baseline, zero], 0),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 16000,
            [baseline, zero, dict(zero, step=2, candidate_sha256="2" * 64),
             dict(zero, step=3, candidate_sha256="3" * 64)], 0,
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 15800,
            [baseline, blind_best, blind_low, blind_predictive], 1,
        ),
    }
    return calibration, records


class ReactionCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_retains_prediction_mechanism_refusal_separation(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        counterexample = report["prediction_mechanism_refusal_counterexample"]
        self.assertGreater(counterexample["development_prediction_score"], 0.7)
        self.assertLess(counterexample["combined_score"], 0.3)
        self.assertEqual(counterexample["development_false_discovery_rate"], 0.5)
        self.assertLess(
            report["normal_minus_blind_selected_contrast"]["combined_score"], 0.0
        )

    def test_source_mismatch_or_repaired_refusal_breaks_observed_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, False
        )["execution_passed"])
        records["blind_budget_three"]["selected_metrics"][
            "development_false_discovery_rate"
        ] = 0.0
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
