"""New discovery submissions must honor their documented scalar contracts."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATORS = (
    "benchmarks/Chemistry/CrowdedSpectrumAssignment/verification/evaluator.py",
    "benchmarks/Chemistry/QuinaryConvexHull/verification/evaluator.py",
    "benchmarks/ComputerScience/SurvivorshipConfoundedDesign/verification/evaluator.py",
    "benchmarks/EarthScience/AMOCTippingRefusal/verification/evaluator.py",
    "benchmarks/Physics/ComplexBoseLaw/verification/evaluator.py",
    "benchmarks/Physics/LookElsewhereAnomaly/verification/evaluator.py",
    "benchmarks/Physics/PTAHellingsDowns/verification/evaluator.py",
)

REQUIRED_BOOLEAN_FIELDS = (
    (
        "benchmarks/ComputerScience/SurvivorshipConfoundedDesign/verification/evaluator.py",
        "has_treatment_effect",
    ),
    (
        "benchmarks/EarthScience/AMOCTippingRefusal/verification/evaluator.py",
        "has_tipping",
    ),
    (
        "benchmarks/Physics/LookElsewhereAnomaly/verification/evaluator.py",
        "discovery",
    ),
)


def _load(relative_path):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(
        "confidence_contract_%s" % path.parent.parent.name, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoveryConfidenceContractTests(unittest.TestCase):
    def test_out_of_range_confidence_is_invalid_in_every_new_discovery_task(self):
        for relative_path in EVALUATORS:
            evaluator = _load(relative_path)
            for confidence in (-0.1, 1.1):
                with self.subTest(evaluator=relative_path, confidence=confidence):
                    metrics = evaluator.evaluate(
                        lambda *_args, value=confidence: {
                            "abstain": True,
                            "confidence": value,
                        }
                    )
                    self.assertEqual(metrics["valid"], 0.0, metrics)
                    self.assertEqual(metrics["combined_score"], 0.0, metrics)
                    self.assertTrue(
                        all(not row["valid"] for row in metrics["per_instance"]),
                        metrics,
                    )

    def test_non_boolean_abstention_is_invalid_in_every_new_discovery_task(self):
        for relative_path in EVALUATORS:
            with self.subTest(evaluator=relative_path):
                metrics = _load(relative_path).evaluate(
                    lambda *_args: {"abstain": "false", "confidence": 0.0}
                )
                self.assertEqual(metrics["valid"], 0.0, metrics)
                self.assertTrue(
                    all(not row["valid"] for row in metrics["per_instance"]),
                    metrics,
                )

    def test_non_boolean_discovery_fields_are_invalid(self):
        for relative_path, field in REQUIRED_BOOLEAN_FIELDS:
            with self.subTest(evaluator=relative_path, field=field):
                metrics = _load(relative_path).evaluate(
                    lambda *_args, key=field: {
                        key: 0,
                        "abstain": False,
                        "confidence": 0.0,
                    }
                )
                self.assertEqual(metrics["valid"], 0.0, metrics)
                self.assertTrue(
                    all(not row["valid"] for row in metrics["per_instance"]),
                    metrics,
                )


if __name__ == "__main__":
    unittest.main()
