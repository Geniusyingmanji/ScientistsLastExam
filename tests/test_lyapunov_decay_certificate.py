"""Certificate pins for LyapunovDecayCertificate."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Engineering/LyapunovDecayCertificate"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LyapunovDecayCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "lyapunov_oracle")
        cls.baseline = _load(TASK / "solution.py", "lyapunov_baseline")
        cls.reference = _load(
            TASK / "verification/reference_lyapunov.py", "lyapunov_reference"
        )

    def test_identity_is_a_lyapunov_function_but_a_shear_proves_more(self):
        shear = self.evaluator.INSTANCES[0]
        modes = self.evaluator._parse_modes(shear["mode_matrices"])
        identity = [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]]
        holds, _ = self.evaluator.certificate_holds(modes, identity, Fraction(1, 10000))
        self.assertTrue(holds)
        fails, _ = self.evaluator.certificate_holds(modes, identity, Fraction(1, 2))
        self.assertFalse(fails)
        sheared = [
            [Fraction(1, 9), Fraction(-1, 16)],
            [Fraction(-1, 16), Fraction(4)],
        ]
        better, _ = self.evaluator.certificate_holds(modes, sheared, Fraction(1, 2))
        self.assertTrue(better)

    def test_floats_are_rejected_and_score_zero(self):
        def floats(_instance):
            return {"p11": 1.0, "p12": 0.0, "p22": 1.0, "alpha": 0.0001}

        metrics = self.evaluator.evaluate(floats)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_identity_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.build_lyapunov)
        reference = self.evaluator.evaluate(self.reference.build_lyapunov)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(reference["combined_score"], 0.5)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: "not a mapping")
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_pendulum_controller_or_a_bell_certificate(self):
        from sle.registry import find_task
        spec = find_task("ControlTheory/LyapunovDecayCertificate", include_uncertified=True)
        pendulum = find_task("ControlTheory/InvertedPendulumSwingUp", include_uncertified=True)
        bell = find_task("QuantumFoundations/BellBoundCertificate", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "build_lyapunov")
        self.assertNotEqual(spec.task_dir, pendulum.task_dir)
        self.assertNotEqual(spec.task_dir, bell.task_dir)


if __name__ == "__main__":
    unittest.main()
