from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np

from sle.metric_visibility import search_visible_metrics


ROOT = Path(__file__).resolve().parent.parent


def _oracle():
    path = ROOT / "benchmarks/Engineering/LowThrustTransfer/verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("low_thrust_v2_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LowThrustV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()

    def test_continuous_throttle_maximum_matches_dense_grid(self):
        rng = np.random.default_rng(722)
        longitude = np.linspace(0.0, 2.0 * math.pi, 50001)
        sine, cosine = np.sin(longitude), np.cos(longitude)
        for _ in range(40):
            row = rng.normal(size=7)
            radial = row[1] * sine + row[2] * cosine
            transverse = row[0] + row[3] * sine + row[4] * cosine
            normal = row[5] * sine + row[6] * cosine
            dense = float(np.sqrt(np.max(
                radial * radial + transverse * transverse + normal * normal
            )))
            exact = self.oracle._maximum_control_norm(row)
            self.assertGreaterEqual(exact + 1.0e-9, dense)
            self.assertLess(exact - dense, 1.0e-6)

    def test_mee_cartesian_round_trip_invariants(self):
        for instance in self.oracle._instances():
            elements = instance["initial_elements"]
            position, velocity = self.oracle.mee_to_cartesian(elements)
            angular_momentum = np.cross(position, velocity)
            p_from_cartesian = (
                np.dot(angular_momentum, angular_momentum)
                / self.oracle.MU_EARTH_M3_S2
            )
            eccentricity_vector = (
                np.cross(velocity, angular_momentum)
                / self.oracle.MU_EARTH_M3_S2
                - position / np.linalg.norm(position)
            )
            self.assertAlmostEqual(p_from_cartesian, elements[0], delta=1.0e-6)
            self.assertAlmostEqual(
                np.linalg.norm(eccentricity_vector),
                math.hypot(elements[1], elements[2]),
                delta=1.0e-12,
            )

    def test_reference_controls_are_bounded_and_targets_are_nontrivial(self):
        for instance in self.oracle._instances():
            validated, maximum = self.oracle._validate_coefficients(
                instance["reference_coefficients"]
            )
            self.assertEqual(validated.shape, (4, 7))
            self.assertLess(maximum, 0.80)
            scaled_change = (
                instance["target_elements"][:5]
                - instance["initial_elements"][:5]
            ) / instance["terminal_scales"]
            self.assertGreater(np.max(np.abs(scaled_change)), 5.0)

    def test_zero_baseline_is_valid_but_not_terminal_feasible(self):
        oracle = self.oracle

        def zero(*_args):
            return np.zeros((oracle.N_SEGMENTS, 7))

        metrics = oracle.evaluate(zero)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)
        self.assertEqual(metrics["development_mission_feasibility_rate"], 0.0)
        shown = search_visible_metrics(metrics)
        self.assertEqual(shown["feasibility_rate"], 0.0)
        for key in (
            "robustness_score", "heldout_policy_score",
            "mean_development_phase_score", "per_instance",
        ):
            self.assertNotIn(key, shown)

    def test_invalid_artifacts_fail_closed(self):
        oracle = self.oracle
        invalid = (
            np.zeros((3, 7)),
            np.full((4, 7), np.nan),
            np.full((4, 7), 1.26),
            np.asarray([[0.8, 0.8, 0, 0, 0, 0, 0]] * 4),
        )
        for artifact in invalid:
            metrics = oracle.evaluate(lambda *_args, value=artifact: value)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))


if __name__ == "__main__":
    unittest.main()
