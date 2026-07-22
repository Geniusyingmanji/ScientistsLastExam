from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_climate_v2_calibrations.py"
BASELINE_HASH = "a" * 64


def _module():
    spec = importlib.util.spec_from_file_location(
        "climate_analysis_test", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, heldout, valid=True):
    return {
        "combined_score": score,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": 1.0 if valid else 0.2,
        "raw_score": score,
        "development_mechanism_score": score,
        "robustness_score": score,
        "development_validation_gap": 0.0,
        "heldout_policy_score": heldout,
        "heldout_robustness_score": heldout,
        "development_prediction_score": 0.98 if score else 0.0,
        "heldout_prediction_score": 0.99 if score else 0.0,
        "development_supported_claim_coverage": 1.0 if score else 0.0,
        "heldout_supported_claim_coverage": 1.0 if score else 0.0,
        "development_false_discovery_rate": 0.2 if score else 0.0,
        "heldout_false_discovery_rate": 0.25 if score else 0.0,
        "development_unsupported_refusal_rate": 0.5 if score else 1.0,
        "heldout_unsupported_refusal_rate": 0.5 if score else 1.0,
        "development_confidence_score": 0.8,
        "heldout_confidence_score": 0.7,
        "development_mean_budget_used": 8.0 if score else 0.0,
        "heldout_mean_budget_used": 8.0 if score else 0.0,
        "development_mean_experiment_calls": 3.0 if score else 0.0,
        "heldout_mean_experiment_calls": 3.0 if score else 0.0,
        "heldout_feasibility_rate": 1.0 if valid else 0.2,
        "candidate_world_call_count": 11,
        "candidate_world_valid_rate": 1.0 if valid else 0.2,
        "error_message": (
            None if valid else "candidate invalid: invalid_return_artifact"
        ),
    }


def _fixed_world_summary():
    base = {
        "world_count": 11,
        "valid_world_count": 11,
        "supported_world_count": 7,
        "supported_claim_coverage": 1.0,
        "mean_supported_mechanism_quality": 0.76,
        "minimum_supported_mechanism_quality": 0.17,
        "mean_supported_parameter_quality": 0.64,
        "mean_supported_nominal_prediction_quality": 0.998,
        "mean_supported_claimed_model_shift_fit": 0.997,
        "maximum_supported_parameter_absolute_errors": [
            0.01, 0.23, 17.6, 0.03, 0.01,
        ],
        "unsupported_world_count": 4,
        "unsupported_correct_refusal_rate": 0.5,
        "unsupported_false_discovery_rate": 0.5,
        "false_discovery_count": 2,
        "mean_false_discovery_confidence": 0.95,
        "mean_false_discovery_claimed_nominal_fit": 0.95,
        "mean_false_discovery_claimed_shift_fit": 0.86,
        "mean_budget_used": 8.0,
        "mean_experiment_calls": 3.0,
        "by_kind": {},
    }
    development = dict(base)
    development.update({
        "world_count": 6,
        "supported_world_count": 4,
        "mean_supported_mechanism_quality": 0.86,
    })
    heldout = dict(base)
    heldout.update({
        "world_count": 5,
        "supported_world_count": 3,
        "mean_supported_mechanism_quality": 0.61,
    })
    return {"all": base, "development": development, "heldout": heldout}


def _record(label, mode, budget, tokens, validity, final_score=0.0):
    events = [{
        "step": 0,
        "accepted": True,
        "candidate_sha256": BASELINE_HASH,
        "parent_sha256": None,
        **_metrics(0.0, 0.0, True),
        "world_summary": None,
    }]
    parent = BASELINE_HASH
    for index, is_valid in enumerate(validity, 1):
        score = final_score if index == len(validity) and is_valid else 0.0
        accepted = score > 0.0
        candidate_hash = str(index) * 64
        event = {
            "step": index,
            "accepted": accepted,
            "candidate_sha256": candidate_hash,
            "parent_sha256": BASELINE_HASH if mode == "selection_blind" else parent,
            **_metrics(score, 0.282 if score else 0.0, is_valid),
            "world_summary": _fixed_world_summary() if score else None,
        }
        events.append(event)
        if accepted and mode != "selection_blind":
            parent = candidate_hash
    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: float(event["combined_score"]),
    )
    return {
        "label": label,
        "source_revision": "f" * 40,
        "feedback_mode": mode,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "server_side_seed_control": False,
        "total_tokens": tokens,
        "best_score": selected["combined_score"],
        "selected_step": selected["step"],
        "selected_metrics": {
            key: selected[key] for key in _metrics(0.0, 0.0)
        },
        "selected_world_summary": selected.get("world_summary"),
        "trajectory": events,
    }


def _probe(kind, index, mechanism, prediction, refusal, confidence):
    supported = kind == "in_library"
    claim = supported or not refusal
    return {
        "name": "probe_%d" % index,
        "seed": 6000 + index,
        "kind": kind,
        "split": "posthoc",
        "world_index": index,
        "valid": True,
        "claimed_public_model": claim,
        "abstain": not claim,
        "confidence": confidence,
        "budget_used": 8,
        "experiment_calls": 3,
        "mechanism_quality": mechanism,
        "parameter_quality": mechanism * mechanism if supported else (
            1.0 if refusal else 0.0
        ),
        "nominal_prediction_quality": prediction,
        "forcing_shift_quality": mechanism,
        "claimed_model_nominal_fit": prediction,
        "claimed_model_shift_fit": prediction - 0.01,
        "correct_refusal": refusal,
        "false_discovery": bool(not supported and not refusal),
        "supported_claim": supported,
        "confidence_score": 0.5,
        "parameter_absolute_errors": (
            [0.01, 0.1, 12.0, 0.01, 0.005] if supported else None
        ),
    }


def _fixtures():
    calibration = {
        "source_revision": "e" * 40,
        "classical_metrics": {
            **_metrics(0.809, 0.942),
            "heldout_prediction_score": 0.999,
            "development_false_discovery_rate": 0.0,
            "heldout_false_discovery_rate": 0.0,
            "development_unsupported_refusal_rate": 1.0,
            "heldout_unsupported_refusal_rate": 1.0,
        },
        "short_design_metrics": {
            **_metrics(0.004, 0.0),
            "heldout_prediction_score": 0.99,
        },
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", 1, 4663, [False]
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 14181,
            [False, False, False],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 15297,
            [True, False, True], final_score=0.618,
        ),
    }
    mechanisms = (0.34, 0.16, 0.50, 0.17, 0.98, 0.08)
    probes = [
        _probe("in_library", index, value, 0.995, False, 0.96)
        for index, value in enumerate(mechanisms)
    ]
    probes.extend([
        _probe("null", 6, 1.0, 1.0, True, 0.92),
        _probe("null", 7, 1.0, 1.0, True, 0.92),
        _probe("feedback_drift", 8, 0.0, 0.90, False, 0.94),
        _probe("feedback_drift", 9, 0.0, 0.82, False, 0.94),
        _probe("three_layer", 10, 0.0, 0.998, False, 0.95),
        _probe("three_layer", 11, 0.0, 0.995, False, 0.96),
    ])
    return calibration, records, probes


class ClimateCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_retains_prediction_mechanism_refusal_separation(self):
        module = _module()
        calibration, records, probes = _fixtures()
        report = module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertEqual(
            report["observed_model_proposal_pattern"][
                "invalid_return_artifact_count"
            ],
            5,
        )
        posthoc = report["posthoc_procedural_probe_summary"]
        self.assertGreater(
            posthoc["mean_supported_nominal_prediction_quality"], 0.98
        )
        self.assertLess(posthoc["mean_supported_mechanism_quality"], 0.45)
        self.assertEqual(posthoc["unsupported_false_discovery_rate"], 2.0 / 3.0)
        self.assertFalse(
            report["posthoc_procedural_probe_protocol"]["preregistered"]
        )

    def test_lineage_source_or_refusal_repair_breaks_observed_gate(self):
        module = _module()
        calibration, records, probes = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=False
        )["execution_passed"])

        calibration, records, probes = _fixtures()
        records["blind_budget_three"]["trajectory"][2][
            "parent_sha256"
        ] = "9" * 64
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )["execution_passed"])

        calibration, records, probes = _fixtures()
        for row in probes:
            if row["kind"] in {"feedback_drift", "three_layer"}:
                row["claimed_public_model"] = False
                row["abstain"] = True
                row["correct_refusal"] = True
                row["false_discovery"] = False
                row["mechanism_quality"] = 1.0
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
