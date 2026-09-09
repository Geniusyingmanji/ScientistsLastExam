from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Biology" / "SpikeHistoryInference"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SpikeHistoryInferenceTests(unittest.TestCase):
    def test_mechanism_axis_is_family_accuracy_not_composite(self):
        from unittest.mock import patch
        oracle = _load("spike_mechanism", TASK / "verification" / "evaluator.py")
        rows = [
            {"kind": "supported", "valid": True, "abstained": False, "correct_refusal": False, "mechanism_correct": True},
            {"kind": "supported", "valid": True, "abstained": False, "correct_refusal": False, "mechanism_correct": False},
            {"kind": "unsupported", "valid": True, "abstained": True, "correct_refusal": True, "mechanism_correct": True},
        ]
        summary = dict(combined_score=0.2, valid=1.0, science_score=0.3,
                       false_discovery_rate=0.0, correct_refusal_rate=1.0,
                       supported_discovery_coverage=0.5)
        with patch.object(oracle, "DEVELOPMENT_WORLDS", [None] * 3), \
             patch.object(oracle, "HELDOUT_WORLDS", [None] * 3), \
             patch.object(oracle, "_evaluate_world", side_effect=rows * 2), \
             patch.object(oracle, "_summary", return_value=summary):
            result = oracle.evaluate(None)
        for split in ("development", "heldout"):
            self.assertEqual(result[split + "_mechanism_score"], 2 / 3)
            self.assertEqual(result[split + "_mechanism_correct_count"], 2)
            self.assertEqual(result[split + "_mechanism_total_count"], 3)
        self.assertEqual(result["combined_score"], 0.2)

    def test_reference_is_deterministic_and_baseline_is_zero(self):
        oracle = _load("spike_evaluator", TASK / "verification" / "evaluator.py")
        reference = _load("spike_reference", TASK / "verification" / "reference_solver.py")
        first = oracle.evaluate(reference.infer_spike_history)
        second = oracle.evaluate(reference.infer_spike_history)
        self.assertEqual(first, second)

        unsupported = [row for row in first["per_instance"] if row["kind"] != "supported"]
        supported = [row for row in first["per_instance"] if row["kind"] == "supported"]
        self.assertTrue(all(row["correct_refusal"] for row in unsupported))
        self.assertTrue(all(not row["false_discovery"] for row in unsupported))
        self.assertTrue(all(not row["abstained"] for row in supported))

        baseline = _load("spike_baseline", TASK / "solution.py")
        base = oracle.evaluate(baseline.infer_spike_history)
        self.assertEqual(base["development_combined_score"], 0.0)
        self.assertEqual(base["heldout_combined_score"], 0.0)
        self.assertEqual(base["valid"], 1.0)
        for split in ("development", "heldout"):
            self.assertEqual(
                base[f"{split}_mechanism_score"],
                base[split + "_mechanism_correct_count"] / base[split + "_mechanism_total_count"],
            )
            self.assertEqual(
                base[f"{split}_false_discovery_rate"],
                base[split]["false_discovery_rate"],
            )
            self.assertEqual(
                base[f"{split}_correct_refusal_rate"],
                base[split]["correct_refusal_rate"],
            )
            self.assertEqual(
                base[f"{split}_discovery_coverage"],
                base[split]["supported_discovery_coverage"],
            )

    def test_recent_spike_reduces_supported_probability(self):
        oracle = _load("spike_probability", TASK / "verification" / "evaluator.py")
        spec = oracle.DEVELOPMENT_WORLDS[0]
        problem = oracle.public_problem(spec)
        probabilities = oracle._truth_probabilities(spec, problem)
        for stimulus_index in range(3):
            no_history = probabilities[stimulus_index]
            recent_spike = probabilities[3 + stimulus_index]
            self.assertLess(recent_spike, no_history)
        self.assertTrue(np.all(np.diff(probabilities[:3]) > 0.0))

    def test_malformed_submission_is_invalid(self):
        oracle = _load("spike_bad", TASK / "verification" / "evaluator.py")
        result = oracle.evaluate(lambda problem: {})
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_wrong_supported_diagnosis_and_fixed_refusal_label_score_zero(self):
        oracle = _load("spike_degenerate", TASK / "verification" / "evaluator.py")
        baseline = _load("spike_degenerate_baseline", TASK / "solution.py")

        def wrong_supported_diagnosis(problem):
            result = baseline.infer_spike_history(problem)
            result.update(diagnosis="burst_history", abstain=False, confidence=0.5)
            return result

        def fixed_refusal_label(problem):
            result = baseline.infer_spike_history(problem)
            result.update(diagnosis="burst_history", abstain=True, confidence=0.5)
            return result

        wrong = oracle.evaluate(wrong_supported_diagnosis)
        fixed = oracle.evaluate(fixed_refusal_label)
        for split in ("development", "heldout"):
            self.assertEqual(wrong[f"{split}_combined_score"], 0.0)
            self.assertEqual(fixed[f"{split}_combined_score"], 0.0)
        self.assertEqual(wrong["development_mechanism_score"], 0.0)

    def test_world_sessions_are_reset_and_candidate_cannot_mutate_contract(self):
        oracle = _load("spike_reset", TASK / "verification" / "evaluator.py")
        baseline = _load("spike_reset_baseline", TASK / "solution.py")

        class StatefulCandidate:
            def __init__(self):
                self.reset_count = 0

            def reset_session(self):
                self.reset_count += 1

            def __call__(self, problem):
                result = baseline.infer_spike_history(problem)
                problem["prediction_contexts"].clear()
                return result

        candidate = StatefulCandidate()
        result = oracle.evaluate(candidate)
        self.assertEqual(candidate.reset_count, len(oracle.DEVELOPMENT_WORLDS) + len(oracle.HELDOUT_WORLDS))
        self.assertEqual(result["valid"], 1.0)
        self.assertTrue(np.isfinite(result["combined_score"]))

    def test_submission_fault_matrix(self):
        oracle = _load("spike_faults", TASK / "verification" / "evaluator.py")
        baseline = _load("spike_base_faults", TASK / "solution.py")
        changes = [
            lambda s: s.pop("confidence"),
            lambda s: s.update(extra=1),
            lambda s: s.update(diagnosis="unknown"),
            lambda s: s.update(abstain="yes"),
            lambda s: s.update(intercept=float("nan")),
            lambda s: s.update(stimulus_gain=float("inf")),
            lambda s: s.update(refractory_tau_ms=-1),
            lambda s: s.update(prediction_probabilities=[]),
            lambda s: s.update(confidence=2),
            lambda s: s.update(evidence_trial_ids=["fabricated"] * 4),
            lambda s: s.update(evidence_trial_ids=[]),
        ]
        for change in changes:
            def candidate(problem):
                claim = baseline.infer_spike_history(problem)
                change(claim)
                return claim
            with self.subTest(change=change):
                result = oracle.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)

    def test_ablation_ladder_measures_reference_capabilities(self):
        oracle = _load("spike_ablation_eval", TASK / "verification" / "evaluator.py")
        sys.path.insert(0, str(TASK / "verification"))
        try:
            reference = _load("spike_ablation_ref", TASK / "verification" / "reference_solver.py")
            ablations = _load("spike_ablations", TASK / "verification" / "ablation_solvers.py")
        finally:
            sys.path.pop(0)
        reference_score = oracle.evaluate(reference.infer_spike_history)
        fixed_tau = oracle.evaluate(ablations.fixed_tau_20)
        midpoint_parameters = oracle.evaluate(ablations.midpoint_parameters)
        never_refuse = oracle.evaluate(ablations.never_refuse)
        rate_only = oracle.evaluate(ablations.rate_only)
        for split in ("development", "heldout"):
            key = "combined_score"
            self.assertGreater(reference_score[split][key] - fixed_tau[split][key], 0.02)
            self.assertGreater(reference_score[split][key] - midpoint_parameters[split][key], 0.10)
            self.assertEqual(never_refuse[split][key], 0.0)
            self.assertEqual(rate_only[split][key], 0.0)


if __name__ == "__main__":
    unittest.main()
