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
                base[split]["science_score"],
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
        never_refuse = oracle.evaluate(ablations.never_refuse)
        rate_only = oracle.evaluate(ablations.rate_only)
        for split in ("development", "heldout"):
            key = "combined_score"
            self.assertGreater(reference_score[split][key], fixed_tau[split][key])
            self.assertGreater(fixed_tau[split][key], never_refuse[split][key])
            self.assertGreater(never_refuse[split][key], rate_only[split][key])


if __name__ == "__main__":
    unittest.main()
