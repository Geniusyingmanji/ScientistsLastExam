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
        self.assertGreater(first["combined_score"], 0.35)
        self.assertLess(first["combined_score"], 0.85)
        self.assertGreater(first["robustness_score"], 0.35)
        self.assertLess(first["robustness_score"], 0.85)
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

    def test_invalid_and_success_metrics_have_identical_keys(self):
        oracle = _load("aquifer_metric_keys", TASK / "verification" / "evaluator.py")
        baseline = _load("aquifer_metric_keys_base", TASK / "solution.py")
        good = oracle.evaluate(baseline.infer_aquifer)
        invalid = oracle.evaluate(lambda problem, measure: {})
        self.assertEqual(set(good), set(invalid))
        self.assertEqual(len(good), 40)

        class BrokenReset:
            def reset_session(self):
                raise RuntimeError("candidate reset failed")

            def __call__(self, problem, measure):
                return baseline.infer_aquifer(problem, measure)

        reset_failure = oracle.evaluate(BrokenReset())
        self.assertEqual(reset_failure["valid"], 0.0)
        self.assertEqual(set(good), set(reset_failure))

    def test_radius_pricing_ids_noise_and_world_order(self):
        oracle = _load("aquifer_pricing", TASK / "verification" / "evaluator.py")
        first_world = oracle._worlds("development")[0]
        second_world = oracle._worlds("development")[1]
        radius = oracle.RADII_M[0]
        times = oracle.TIMES_S[1:7]
        first_rows = [oracle._measure(first_world, radius, time) for time in times]
        second_rows = [oracle._measure(second_world, radius, time) for time in times]
        self.assertEqual(first_rows[0]["cost_units"], 7)
        self.assertTrue(all(row["cost_units"] == 1 for row in first_rows[1:]))
        self.assertEqual(first_rows[-1]["spent_units"], 12)
        self.assertEqual(
            [row["measurement_id"] for row in first_rows],
            [row["measurement_id"] for row in second_rows],
        )
        self.assertNotEqual(
            [row["drawdown_m"] for row in first_rows],
            [row["drawdown_m"] for row in second_rows],
        )
        ordered_world = oracle._worlds("development")[0]
        reversed_world = oracle._worlds("development")[0]
        ordered = [oracle._measure(ordered_world, radius, time) for time in times[:2]]
        reversed_rows = [
            oracle._measure(reversed_world, radius, time) for time in reversed(times[:2])
        ]
        self.assertEqual(
            {row["time_s"]: row["drawdown_m"] for row in ordered},
            {row["time_s"]: row["drawdown_m"] for row in reversed_rows},
        )
        self.assertEqual(
            [world["kind"] for world in oracle._worlds("development")],
            [world["kind"] for world in oracle._worlds("development")],
        )
        self.assertNotEqual(
            [world["kind"] for world in oracle._worlds("development")],
            ["confined"] * 5 + ["leaky_aquifer", "recharge_boundary", "dual_porosity"],
        )

    def test_measurement_id_only_and_other_degenerate_policies_score_zero(self):
        oracle = _load("aquifer_degenerate", TASK / "verification" / "evaluator.py")

        def id_only(problem, measure):
            rows = [
                measure(problem["observation_radii_m"][-1], time)
                for time in problem["observation_times_s"][1:7]
            ]
            diagnoses = ("confined", "leaky_aquifer", "recharge_boundary", "dual_porosity")
            diagnosis = diagnoses[int(rows[0]["measurement_id"][0], 16) % len(diagnoses)]
            return {
                "diagnosis": diagnosis,
                "transmissivity_m2_s": 0.002,
                "storativity": 0.001,
                "predicted_drawdown_m": [0.0] * len(problem["prediction_contexts"]),
                "confidence": 0.5,
                "abstain": diagnosis != "confined",
                "evidence_measurement_ids": [row["measurement_id"] for row in rows],
            }

        result = oracle.evaluate(id_only)
        self.assertEqual(result["development_combined_score"], 0.0)
        self.assertEqual(result["heldout_combined_score"], 0.0)

        for fixed_diagnosis in ("leaky_aquifer", "recharge_boundary", "dual_porosity"):
            def fixed_label(problem, measure, diagnosis=fixed_diagnosis):
                rows = [
                    measure(problem["observation_radii_m"][-1], time)
                    for time in problem["observation_times_s"][1:7]
                ]
                return {
                    "diagnosis": diagnosis,
                    "transmissivity_m2_s": 0.002,
                    "storativity": 0.001,
                    "predicted_drawdown_m": [0.0] * len(problem["prediction_contexts"]),
                    "confidence": 0.5,
                    "abstain": True,
                    "evidence_measurement_ids": [row["measurement_id"] for row in rows],
                }

            with self.subTest(fixed_diagnosis=fixed_diagnosis):
                fixed_result = oracle.evaluate(fixed_label)
                self.assertEqual(fixed_result["combined_score"], 0.0)
                self.assertEqual(fixed_result["robustness_score"], 0.0)

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
        one_radius = oracle.evaluate(ablations.one_radius_half_budget)
        fixed = oracle.evaluate(ablations.fixed_storage)
        never = oracle.evaluate(ablations.never_refuse)
        for key in ("combined_score", "robustness_score"):
            self.assertGreater(full[key] - one_radius[key], 0.10)
            self.assertGreater(full[key], fixed[key])
            self.assertEqual(never[key], 0.0)


if __name__ == "__main__":
    unittest.main()
