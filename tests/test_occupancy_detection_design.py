from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Biology" / "OccupancyDetectionDesign"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("test_occupancy_evaluator", TASK / "verification" / "evaluator.py")
REFERENCE = _load("test_occupancy_reference", TASK / "verification" / "reference_solver.py")
BASELINE = _load("test_occupancy_baseline", TASK / "solution.py")


class OccupancyDetectionDesignTests(unittest.TestCase):
    def test_baseline_is_valid_and_zero(self):
        metrics = EVALUATOR.evaluate(BASELINE.infer_occupancy)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_reference_is_key_deterministic(self):
        first = EVALUATOR.evaluate(REFERENCE.infer_occupancy)
        second = EVALUATOR.evaluate(REFERENCE.infer_occupancy)
        self.assertEqual(first, second)
        self.assertGreater(first["combined_score"], 0.2)

    def test_blanket_abstention_is_zero(self):
        def blanket(problem, survey):
            evidence = [survey(row["site_id"], "rapid")["query_id"]
                        for row in problem["site_descriptors"][:4]]
            return {"abstain": True, "confidence": 0.5, "evidence_query_ids": evidence}
        metrics = EVALUATOR.evaluate(blanket)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_overspend_fails_closed_even_if_caught(self):
        def overspend(problem, survey):
            evidence = []
            for row in problem["site_descriptors"]:
                try:
                    for _ in range(3):
                        evidence.append(survey(row["site_id"], "intensive")["query_id"])
                except Exception:
                    break
            return {"abstain": True, "confidence": 0.5, "evidence_query_ids": evidence[:4]}
        metrics = EVALUATOR.evaluate(overspend)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_supported_and_unsupported_worlds_are_present(self):
        kinds = {row["kind"] for row in EVALUATOR.DEVELOPMENT_WORLDS}
        self.assertEqual(kinds, {"linear", "quadratic", "spatial"})


if __name__ == "__main__":
    unittest.main()
