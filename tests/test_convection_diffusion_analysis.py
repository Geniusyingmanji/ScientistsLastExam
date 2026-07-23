from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_convection_diffusion_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location(
        "convection_diffusion_analysis_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load convection-diffusion analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _world_summary(valid=True, all_abstain=True):
    return {
        "world_count": 11,
        "valid_world_count": 11 if valid else 0,
        "supported_world_count": 7,
        "supported_claim_count": 0 if all_abstain else 7,
        "supported_claim_coverage": 0.0 if all_abstain else 1.0,
        "mean_supported_mechanism_quality": 0.0 if all_abstain else 0.8,
        "unsupported_world_count": 4,
        "unsupported_correct_refusal_rate": 1.0,
        "unsupported_false_discovery_rate": 0.0,
        "all_worlds_abstained": all_abstain,
        "failure_kinds": {},
    }


def _event(step, parent, *, valid=True, failure=None, budget=4.0):
    return {
        "step": step,
        "score": 0.0 if valid else -1.0e18,
        "best_score": 0.0,
        "valid": valid,
        "accepted": False,
        "candidate_sha256": str(step) * 64,
        "parent_sha256": parent,
        "failure_kind": failure,
        "world_summary": _world_summary() if valid else None,
        "combined_score": 0.0 if valid else -1.0e18,
        "mechanism_score": 0.0 if valid else None,
        "development_supported_claim_coverage": 0.0 if valid else None,
        "heldout_supported_claim_coverage": 0.0 if valid else None,
        "development_false_discovery_rate": 0.0 if valid else None,
        "heldout_false_discovery_rate": 0.0 if valid else None,
        "development_correct_refusal_rate": 1.0 if valid else None,
        "heldout_correct_refusal_rate": 1.0 if valid else None,
        "development_mean_experiment_calls": 2.0 if budget == 12.0 else 1.0,
        "development_mean_budget_units": budget if valid else None,
    }


def _record(label, mode, budget, tokens, proposal_spec):
    baseline_hash = "b" * 64
    baseline = _event(0, None, valid=True, budget=3.0)
    baseline["accepted"] = True
    baseline["candidate_sha256"] = baseline_hash
    proposals = [
        _event(index, baseline_hash, valid=valid, failure=failure, budget=units)
        for index, (valid, failure, units) in enumerate(proposal_spec, 1)
    ]
    return {
        "label": label,
        "source_revision": _module().EXPECTED_MODEL_SOURCE_REVISION,
        "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "c" * 64,
        "feedback_mode": mode,
        "proposal_budget": budget,
        "seed": 0 if budget == 1 else 1,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "best_score": 0.0,
        "selected_step": 0,
        "trajectory": [baseline, *proposals],
    }


def _fixtures():
    calibration = {
        "source_revision": "a" * 40,
        "two_experiment_metrics": {
            "combined_score": 0.8956,
            "heldout_policy_score": 0.8915,
            "mechanism_score": 0.6495,
            "heldout_mechanism_score": 0.6596,
            "heldout_prediction_score": 0.9997,
            "heldout_robustness_score": 0.8904,
            "heldout_false_discovery_rate": 0.0,
            "heldout_supported_claim_coverage": 1.0,
        },
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", 1, 5660,
            [(False, "invalid_experiment_request", 0.0)],
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 16833,
            [
                (False, "candidate_runtime_error", 0.0),
                (True, None, 4.0),
                (False, "candidate_runtime_error", 0.0),
            ],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 16982,
            [
                (False, "candidate_runtime_error", 0.0),
                (True, None, 12.0),
                (True, None, 4.0),
            ],
        ),
    }
    return calibration, records


class ConvectionDiffusionAnalysisTests(unittest.TestCase):
    def test_analysis_separates_protocol_refusal_and_discovery(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertEqual(
            report["proposal_summary"]["normal_budget_three"][
                "failure_counts"
            ],
            {"candidate_runtime_error": 2},
        )
        model = report["science_vectors"]["valid_gpt55_nonbaseline_proposals"]
        self.assertEqual(model["proposal_count"], 3)
        self.assertEqual(model["supported_discovery_coverage"], 0.0)
        self.assertEqual(model["mechanism_M"], 0.0)
        self.assertEqual(model["refusal_R"], 1.0)
        self.assertEqual(
            report["normal_minus_blind_diagnostic"]["total_tokens"], -149
        )

    def test_source_lineage_or_supported_claim_breaks_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, False
        )["execution_passed"])
        records["blind_budget_three"]["trajectory"][2]["parent_sha256"] = "x" * 64
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])
        calibration, records = _fixtures()
        records["normal_budget_three"]["trajectory"][2][
            "world_summary"
        ] = _world_summary(all_abstain=False)
        self.assertFalse(module._analyze_records(
            calibration, records, True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
