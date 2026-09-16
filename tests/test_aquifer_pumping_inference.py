from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "EarthScience" / "AquiferPumpingInference"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AquiferPumpingInferenceTests(unittest.TestCase):
    def test_reference_is_deterministic_and_baseline_is_zero(self):
        oracle = _load("aquifer_eval", TASK / "verification" / "evaluator.py")
        reference = _load("aquifer_ref", TASK / "verification" / "reference_solver.py")
        first = oracle.evaluate(reference.infer_aquifer)
        second = oracle.evaluate(reference.infer_aquifer)
        self.assertEqual(first, second)
        self.assertEqual(first["valid"], 1.0)
        self.assertGreater(first["combined_score"], 0.70)
        self.assertGreater(first["robustness_score"], 0.65)
        baseline = _load("aquifer_base", TASK / "solution.py")
        result = oracle.evaluate(baseline.infer_aquifer)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["robustness_score"], 0.0)
        self.assertEqual(result["valid"], 1.0)

    def test_theis_physics_invariants(self):
        oracle = _load("aquifer_physics", TASK / "verification" / "evaluator.py")
        times = np.asarray([100.0, 1000.0, 10000.0])
        radii = np.asarray([20.0, 60.0, 180.0])
        with_time = oracle.theis_drawdown(0.002, 0.001, 50.0, times)
        with_radius = oracle.theis_drawdown(0.002, 0.001, radii, 5000.0)
        self.assertTrue(np.all(np.diff(with_time) > 0.0))
        self.assertTrue(np.all(np.diff(with_radius) < 0.0))
        # The similarity variable makes this scaled radius/time pair identical.
        a = oracle.theis_drawdown(0.002, 0.001, 20.0, 1000.0)
        b = oracle.theis_drawdown(0.002, 0.001, 40.0, 4000.0)
        self.assertAlmostEqual(float(a), float(b), places=12)

    def test_fault_matrix_and_budget_fail_closed(self):
        oracle = _load("aquifer_faults", TASK / "verification" / "evaluator.py")
        baseline = _load("aquifer_fault_base", TASK / "solution.py")
        changes = [
            lambda s: s.pop("confidence"), lambda s: s.update(extra=1),
            lambda s: s.update(diagnosis="unknown"), lambda s: s.update(abstain="yes"),
            lambda s: s.update(transmissivity_m2_s=float("nan")),
            lambda s: s.update(storativity=float("inf")),
            lambda s: s.update(storativity=-1.0),
            lambda s: s.update(predicted_drawdown_m=[]),
            lambda s: s.update(predicted_drawdown_m=[-1.0] * 8),
            lambda s: s.update(confidence=2.0),
            lambda s: s.update(evidence_measurement_ids=["fabricated"] * 12),
            lambda s: s.update(evidence_measurement_ids=[]),
        ]
        for change in changes:
            def candidate(problem, measure):
                claim = baseline.infer_aquifer(problem, measure)
                change(claim)
                return claim
            with self.subTest(change=change):
                result = oracle.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)

        def overspend(problem, measure):
            for _ in range(problem["measurement_budget_units"] + 1):
                try:
                    measure(problem["observation_radii_m"][0], problem["observation_times_s"][0])
                except RuntimeError:
                    pass
            return baseline.infer_aquifer(problem, measure)
        self.assertEqual(oracle.evaluate(overspend)["valid"], 0.0)

    def test_mechanism_bookkeeping_has_explicit_denominators(self):
        oracle = _load("aquifer_metrics", TASK / "verification" / "evaluator.py")
        template = {"combined_score": 0.2, "parameter_recovery_score": 0.1,
                    "prediction_score": 0.1, "attempted": True,
                    "false_discovery": False, "correct_refusal": False,
                    "abstained": False, "valid": True}
        rows = [
            {**template, "kind": "confined", "correct_mechanism": True},
            {**template, "kind": "confined", "correct_mechanism": False,
             "attempted": False, "abstained": True},
            {**template, "kind": "leaky_aquifer", "correct_mechanism": True,
             "correct_refusal": True, "abstained": True},
        ]
        result = oracle._summary(rows)
        self.assertEqual(result["mechanism_correct_count"], 2)
        self.assertEqual(result["mechanism_total_count"], 3)
        self.assertEqual(result["mechanism_score"], 2 / 3)
        self.assertNotEqual(result["mechanism_score"], result["combined_score"])

    def test_ablation_ladder(self):
        oracle = _load("aquifer_ablation_eval", TASK / "verification" / "evaluator.py")
        sys.path.insert(0, str(TASK / "verification"))
        try:
            reference = _load("aquifer_ablation_ref", TASK / "verification" / "reference_solver.py")
            ablations = _load("aquifer_ablations", TASK / "verification" / "ablation_solvers.py")
        finally:
            sys.path.pop(0)
        full = oracle.evaluate(reference.infer_aquifer)
        two = oracle.evaluate(ablations.two_radii_only)
        fixed = oracle.evaluate(ablations.fixed_storage)
        never = oracle.evaluate(ablations.never_refuse)
        for key in ("combined_score", "robustness_score"):
            self.assertGreater(full[key], two[key])
            self.assertGreater(full[key], fixed[key])
            self.assertGreater(full[key], never[key])


if __name__ == "__main__":
    unittest.main()
