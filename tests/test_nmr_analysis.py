from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIELDS = (
    "combined_score", "mechanism_score", "robustness_score",
    "heldout_mechanism_score", "development_reconstruction_score",
    "heldout_reconstruction_score",
    "development_confidence_calibration_score",
    "heldout_confidence_calibration_score",
    "development_false_discovery_rate", "heldout_false_discovery_rate",
    "development_correct_refusal_rate", "heldout_correct_refusal_rate",
)


def _module():
    path = ROOT / "scripts/analyze_nmr_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("nmr_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(step, score, robustness, reconstruction, heldout_reconstruction,
           development_false, heldout_false, accepted, parent):
    values = {
        "combined_score": score,
        "mechanism_score": 0.33 + 0.67 * score,
        "robustness_score": robustness,
        "heldout_mechanism_score": 0.5 + 0.5 * robustness,
        "development_reconstruction_score": reconstruction,
        "heldout_reconstruction_score": heldout_reconstruction,
        "development_confidence_calibration_score": 0.8,
        "heldout_confidence_calibration_score": 0.75,
        "development_false_discovery_rate": development_false,
        "heldout_false_discovery_rate": heldout_false,
        "development_correct_refusal_rate": 1.0 - development_false,
        "heldout_correct_refusal_rate": 1.0 - heldout_false,
    }
    return {
        "step": step, "accepted": accepted, "valid": True,
        "candidate_sha256": chr(ord("a") + step) * 64,
        "parent_sha256": parent,
        **{field: values[field] for field in FIELDS},
    }


def _record(label, budget, events, selected_step):
    return {
        "label": label, "report": label + ".json",
        "report_sha256": "1" * 64, "trajectory_sha256": "2" * 64,
        "source_revision": "3" * 40, "seed": budget,
        "proposal_budget": budget, "server_side_seed_control": False,
        "oracle_calls": budget + 1, "total_tokens": budget * 100,
        "best_score": events[selected_step]["combined_score"],
        "selected_step": selected_step,
        "selected_candidate_sha256": events[selected_step]["candidate_sha256"],
        "feedback_scope": "synthetic sealed metrics", "trajectory": events,
    }


def _fixtures():
    calibration = {
        "report": "calibration.json", "report_sha256": "0" * 64,
        "source_revision": "3" * 40,
        "classical_metrics": {
            "combined_score": 0.27, "robustness_score": 0.15,
            "development_reconstruction_score": 0.88,
            "heldout_reconstruction_score": 0.85,
            "development_false_discovery_rate": 1.0,
            "heldout_false_discovery_rate": 0.5,
        },
        "exact_reference_score": 1.0, "exact_reference_heldout_score": 1.0,
        "always_abstain_score": 0.0, "always_abstain_heldout_score": 0.0,
    }
    baseline = _event(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, True, None)
    one = _event(1, 0.43, 0.18, 0.87, 0.88, 0.5, 0.5, True, "a" * 64)
    first = _event(1, 0.38, 0.0, 0.82, 0.87, 0.5, 1.0, True, "a" * 64)
    second = _event(2, 0.21, 0.0, 0.82, 0.88, 1.0, 1.0, False, "b" * 64)
    third = _event(3, 0.16, 0.0, 0.78, 0.68, 1.0, 1.0, False, "b" * 64)
    records = {
        "budget_one": _record("budget_one", 1, [baseline, one], 1),
        "budget_three": _record(
            "budget_three", 3, [baseline, first, second, third], 1
        ),
    }
    return calibration, records


class NMRCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_retains_reconstruction_mechanism_refusal_separation(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records)
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["evidence_scope"],
            "NMR_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        )
        self.assertGreater(
            report["budget_one_minus_classical"]["combined_score"], 0.0
        )
        self.assertEqual(len(report["budget_three_rejected_after_feedback"]), 2)
        self.assertTrue(all(
            row["development_false_discovery_rate"] == 1.0
            and row["development_reconstruction_score"] > 0.75
            for row in report["budget_three_rejected_after_feedback"]
        ))

    def test_repaired_false_discovery_breaks_observed_pattern_gate(self):
        module = _module()
        calibration, records = _fixtures()
        records["budget_three"]["trajectory"][2][
            "development_false_discovery_rate"
        ] = 0.0
        self.assertFalse(
            module._analyze_records(calibration, records)["execution_passed"]
        )


if __name__ == "__main__":
    unittest.main()
