from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np

from sle.registry import find_task


TASK_ID = "Geophysics/UPbConcordiaInference"


def _load(relative_path, name):
    root = find_task(TASK_ID, include_uncertified=True).task_dir
    spec = importlib.util.spec_from_file_location(name, root / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UPbConcordiaInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _load("verification/evaluator.py", "upb_oracle_test")
        cls.evaluator = cls.oracle
        cls.reference = _load("verification/reference_solver.py", "upb_reference_test")
        cls.baseline = _load("solution.py", "upb_baseline_test")

    def test_concordia_uses_both_decay_constants(self):
        age = 1710.0
        point = self.evaluator._concordia(age)
        self.assertAlmostEqual(point[0], math.expm1(self.evaluator.LAMBDA_235 * age * 1e6), places=12)
        self.assertAlmostEqual(point[1], math.expm1(self.evaluator.LAMBDA_238 * age * 1e6), places=12)
        self.assertNotAlmostEqual(point[0], point[1], places=3)

    def test_supported_lead_loss_is_one_discordia(self):
        world = self.evaluator._make_world({"kind": "lead_loss", "seed": 731001})
        young = self.evaluator._concordia(world["lead_loss_age_myr"])
        old = self.evaluator._concordia(world["crystallization_age_myr"])
        direction = old - young
        cross = [abs(direction[0] * (point - young)[1] - direction[1] * (point - young)[0])
                 for point in world["clean"]]
        self.assertLess(max(cross), 1e-10)

    def test_multi_event_world_is_resolvably_rejected(self):
        metrics = self.oracle.evaluate(self.reference.infer_upb_history)
        unsupported = [row for row in metrics["per_instance"] if row["kind"] == "multi_event"]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["correct_refusal"] for row in unsupported))

    def test_baseline_is_valid_and_normalized_to_zero(self):
        metrics = self.oracle.evaluate(self.baseline.infer_upb_history)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)

    def test_reference_has_skill_and_headroom(self):
        metrics = self.oracle.evaluate(self.reference.infer_upb_history)
        self.assertGreater(metrics["combined_score"], 0.75)
        self.assertLess(metrics["combined_score"], 0.97)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 1.0)

    def test_blanket_abstention_is_exactly_zero(self):
        def abstain(problem, measure):
            row = measure(problem["grain_descriptors"][0]["grain_id"], "screen")
            return {"abstain": True, "confidence": 0.5,
                    "evidence_query_ids": [row["query_id"]]}
        metrics = self.oracle.evaluate(abstain)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_denominator"], 2)
        self.assertEqual(metrics["development_discovery_coverage_denominator"], 8)

    def test_overspend_and_malformed_outputs_fail_closed(self):
        def overspend(problem, measure):
            for row in problem["grain_descriptors"][:7]:
                measure(row["grain_id"], "analytical")
            return {}
        metrics = self.oracle.evaluate(overspend)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)

    def test_oracle_is_key_deterministic(self):
        first = self.oracle.evaluate(self.reference.infer_upb_history)
        second = self.oracle.evaluate(self.reference.infer_upb_history)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
