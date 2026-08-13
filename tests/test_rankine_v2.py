from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parent.parent
IF97_PATH = (
    ROOT / "benchmarks/Engineering/RankineCycleOpt/verification/if97.py"
)
VERIFICATION = IF97_PATH.parent
CALIBRATION_PATH = ROOT / "scripts/calibrate_rankine_v2.py"


def _load_if97():
    spec = importlib.util.spec_from_file_location("rankine_if97_test", IF97_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load IF97 module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cycle():
    sys.path.insert(0, str(VERIFICATION))
    try:
        spec = importlib.util.spec_from_file_location(
            "rankine_cycle_test", VERIFICATION / "cycle.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load Rankine cycle module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _load_oracle():
    sys.path.insert(0, str(VERIFICATION))
    try:
        spec = importlib.util.spec_from_file_location(
            "rankine_oracle_test", VERIFICATION / "evaluator.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load Rankine evaluator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _load_calibration():
    spec = importlib.util.spec_from_file_location(
        "rankine_v2_calibration_test", CALIBRATION_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load Rankine calibration module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IF97VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.if97 = _load_if97()

    def assert_properties(self, observed, expected):
        for key, value in expected.items():
            self.assertAlmostEqual(
                observed[key], value, delta=max(1.0e-9, abs(value) * 2.0e-8),
                msg=key,
            )

    def test_region1_matches_iapws_r7_97_2012_table5(self):
        rows = (
            (300.0, 3.0, {
                "v": 0.100215168e-2, "h": 0.115331273e3,
                "u": 0.112324818e3, "s": 0.392294792,
                "cp": 0.417301218e1, "w": 0.150773921e4,
            }),
            (300.0, 80.0, {
                "v": 0.971180894e-3, "h": 0.184142828e3,
                "u": 0.106448356e3, "s": 0.368563852,
                "cp": 0.401008987e1, "w": 0.163469054e4,
            }),
            (500.0, 3.0, {
                "v": 0.120241800e-2, "h": 0.975542239e3,
                "u": 0.971934985e3, "s": 0.258041912e1,
                "cp": 0.465580682e1, "w": 0.124071337e4,
            }),
        )
        for temperature, pressure, expected in rows:
            with self.subTest(temperature=temperature, pressure=pressure):
                self.assert_properties(
                    self.if97.region1(temperature, pressure), expected
                )

    def test_region2_matches_iapws_r7_97_2012_table15(self):
        rows = (
            (300.0, 0.0035, {
                "v": 0.394913866e2, "h": 0.254991145e4,
                "u": 0.241169160e4, "s": 0.852238967e1,
                "cp": 0.191300162e1, "w": 0.427920172e3,
            }),
            (700.0, 0.0035, {
                "v": 0.923015898e2, "h": 0.333568375e4,
                "u": 0.301262819e4, "s": 0.101749996e2,
                "cp": 0.208141274e1, "w": 0.644289068e3,
            }),
            (700.0, 30.0, {
                "v": 0.542946619e-2, "h": 0.263149474e4,
                "u": 0.246861076e4, "s": 0.517540298e1,
                "cp": 0.103505092e2, "w": 0.480386523e3,
            }),
        )
        for temperature, pressure, expected in rows:
            with self.subTest(temperature=temperature, pressure=pressure):
                self.assert_properties(
                    self.if97.region2(temperature, pressure), expected
                )

    def test_region4_matches_iapws_tables35_and36(self):
        for temperature, pressure in (
            (300.0, 0.353658941e-2),
            (500.0, 0.263889776e1),
            (600.0, 0.123443146e2),
        ):
            with self.subTest(temperature=temperature):
                self.assertAlmostEqual(
                    self.if97.saturation_pressure(temperature), pressure,
                    delta=pressure * 2.0e-8,
                )
        for pressure, temperature in (
            (0.1, 0.372755919e3),
            (1.0, 0.453035632e3),
            (10.0, 0.584149488e3),
        ):
            with self.subTest(pressure=pressure):
                self.assertAlmostEqual(
                    self.if97.saturation_temperature(pressure), temperature,
                    delta=temperature * 2.0e-8,
                )

    def test_pressure_property_inversions_round_trip_regions_and_mixture(self):
        for state in (
            self.if97.region1(450.0, 12.0),
            self.if97.region2(780.0, 12.0),
            self.if97.region2(700.0, 2.0),
        ):
            with self.subTest(region=state["region"], pressure=state["P"]):
                by_entropy = self.if97.state_ps(state["P"], state["s"])
                by_enthalpy = self.if97.state_ph(state["P"], state["h"])
                self.assertAlmostEqual(by_entropy["T"], state["T"], delta=2e-7)
                self.assertAlmostEqual(by_enthalpy["T"], state["T"], delta=2e-7)
        saturation = self.if97.saturation_state(0.01)
        liquid = saturation["liquid"]
        vapor = saturation["vapor"]
        entropy = liquid["s"] + 0.9 * (vapor["s"] - liquid["s"])
        mixture = self.if97.state_ps(0.01, entropy)
        self.assertEqual(mixture["region"], 4.0)
        self.assertAlmostEqual(mixture["x"], 0.9, delta=1e-12)

    def test_region3_saturation_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError, "Region 3"):
            self.if97.saturation_state(20.0)


class ReheatCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cycle = _load_cycle()

    @staticmethod
    def condition(**updates):
        value = {
            "condenser_pressure_kpa": 8.0,
            "hp_turbine_efficiency": 0.88,
            "lp_turbine_efficiency": 0.90,
            "pump_efficiency": 0.85,
            "boiler_pressure_loss_fraction": 0.03,
            "reheat_pressure_loss_fraction": 0.02,
            "max_boiler_pressure_mpa": 15.0,
            "max_steam_temperature_c": 600.0,
            "minimum_hp_exit_quality": 0.88,
            "minimum_lp_exit_quality": 0.88,
        }
        value.update(updates)
        return value

    def test_nominal_cycle_closes_energy_balance_and_has_physical_scale(self):
        result = self.cycle.evaluate_cycle(
            [12.0, 565.0, 0.22, 565.0], self.condition()
        )
        self.assertTrue(result["process_feasible"])
        self.assertGreater(result["thermal_efficiency"], 0.38)
        self.assertLess(result["thermal_efficiency"], 0.43)
        self.assertGreater(result["specific_net_work_kj_kg"], 1400.0)
        self.assertGreaterEqual(result["lp_exit_quality"], 0.88)
        self.assertLessEqual(abs(result["energy_balance_residual_kj_kg"]), 1e-9)

    def test_turbine_degradation_cannot_improve_cycle(self):
        design = [12.0, 565.0, 0.22, 565.0]
        nominal = self.cycle.evaluate_cycle(design, self.condition())
        degraded = self.cycle.evaluate_cycle(
            design,
            self.condition(hp_turbine_efficiency=0.82, lp_turbine_efficiency=0.84),
        )
        self.assertLess(
            degraded["thermal_efficiency"], nominal["thermal_efficiency"]
        )
        self.assertLess(
            degraded["specific_net_work_kj_kg"],
            nominal["specific_net_work_kj_kg"],
        )

    def test_moisture_material_and_region_limits_fail_closed(self):
        wet = self.cycle.evaluate_cycle(
            [12.0, 500.0, 0.42, 500.0],
            self.condition(minimum_lp_exit_quality=0.95),
        )
        material = self.cycle.evaluate_cycle(
            [15.0, 590.0, 0.20, 590.0],
            self.condition(max_boiler_pressure_mpa=14.0),
        )
        region3 = self.cycle.evaluate_cycle(
            [16.0, 590.0, 0.20, 590.0],
            self.condition(max_boiler_pressure_mpa=18.0),
        )
        self.assertFalse(wet["process_feasible"])
        self.assertEqual(wet["failure"], "lp_moisture_limit")
        self.assertFalse(material["process_feasible"])
        self.assertEqual(material["failure"], "pressure_material_limit")
        self.assertFalse(region3["process_feasible"])
        self.assertEqual(region3["failure"], "if97_region_limit")


class RankineV2EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _load_oracle()

    def test_independent_iapws_check_is_optional_but_fail_closed_when_required(self):
        calibration = _load_calibration()
        with mock.patch.dict(sys.modules, {"iapws": None}):
            optional = calibration._independent_iapws_check(
                self.oracle, require=False
            )
            required = calibration._independent_iapws_check(
                self.oracle, require=True
            )
        self.assertFalse(optional["performed"])
        self.assertTrue(optional["passed"])
        self.assertFalse(required["performed"])
        self.assertFalse(required["passed"])
        self.assertEqual(required["expected_version"], "1.5.4")
        self.assertEqual(
            required["expected_sdist_sha256"],
            "9f0faa39a967d76fc5e5f95f61d922e135453192e02bf875d07242f13d6eaa55",
        )

    def policy(self, kind):
        oracle = self.oracle

        def design(problem):
            for instance in oracle.INSTANCES:
                if instance["problem"] == problem:
                    if kind == "baseline":
                        return oracle._baseline_archive(problem)
                    return oracle._reference_archive(instance, kind)
            raise ValueError("unknown public Rankine problem")

        return design

    def test_baseline_nominal_and_robust_witnesses_define_real_tradeoff(self):
        oracle = self.oracle
        baseline = oracle.evaluate(self.policy("baseline"))
        nominal = oracle.evaluate(self.policy("nominal"))
        robust = oracle.evaluate(self.policy("robust"))

        self.assertTrue(oracle.RANKINE_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(len(oracle.SHIFT_SPECS), 5)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)
        self.assertEqual(baseline["development_shift_feasibility_rate"], 1.0)
        self.assertEqual(baseline["heldout_shift_feasibility_rate"], 1.0)

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertLess(nominal["development_shift_feasibility_rate"], 0.80)
        self.assertLess(nominal["heldout_shift_feasibility_rate"], 0.80)

        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertEqual(robust["development_shift_feasibility_rate"], 1.0)
        self.assertEqual(robust["heldout_shift_feasibility_rate"], 1.0)
        self.assertGreater(robust["combined_score"], 0.40)
        self.assertLess(robust["combined_score"], 0.60)

        for result in (baseline, nominal, robust):
            for record in result["per_instance"]:
                self.assertLessEqual(
                    record.get("maximum_front_energy_balance_residual_kj_kg", 0.0),
                    2.0e-8,
                )

        visible = search_visible_metrics(robust)
        self.assertEqual(
            set(visible),
            {"combined_score", "valid", "feasibility_rate", "raw_score"},
        )
        for key in (
            "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_shift_feasibility_rate",
            "development_mean_front_efficiency", "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_reference_indices_and_frozen_anchors_recompute_exactly(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            baseline = oracle._baseline_archive(problem)
            nominal = oracle._reference_archive(instance, "nominal")
            robust = oracle._reference_archive(instance, "robust")
            shifted_conditions = [
                oracle._shift_condition(instance["operating_condition"], shift)
                for shift in oracle.SHIFT_SPECS
            ]
            baseline_nominal = oracle._evaluate_archive(
                baseline, instance["operating_condition"]
            )
            reference_nominal = oracle._evaluate_archive(
                nominal, instance["operating_condition"]
            )
            baseline_shifts = [
                oracle._evaluate_archive(baseline, condition)
                for condition in shifted_conditions
            ]
            reference_shifts = [
                oracle._evaluate_archive(robust, condition)
                for condition in shifted_conditions
            ]
            observed = {
                "baseline_nominal_hypervolume": oracle._hypervolume(
                    problem, baseline_nominal
                ),
                "reference_nominal_hypervolume": oracle._hypervolume(
                    problem, reference_nominal
                ),
                "baseline_shifted_hypervolumes": tuple(
                    oracle._hypervolume(problem, records)
                    for records in baseline_shifts
                ),
                "reference_shifted_hypervolumes": tuple(
                    oracle._hypervolume(problem, records)
                    for records in reference_shifts
                ),
            }
            expected = oracle.CALIBRATED_ANCHORS[instance["name"]]
            for key in ("baseline_nominal_hypervolume", "reference_nominal_hypervolume"):
                self.assertAlmostEqual(observed[key], expected[key], delta=1e-14)
            for key in ("baseline_shifted_hypervolumes", "reference_shifted_hypervolumes"):
                np.testing.assert_allclose(
                    observed[key], expected[key], rtol=0.0, atol=1e-14
                )
            self.assertTrue(all(record["process_feasible"] for record in baseline_nominal))
            self.assertTrue(all(record["process_feasible"] for record in reference_nominal))
            self.assertTrue(all(
                record["process_feasible"]
                for records in reference_shifts for record in records
            ))

    def test_malformed_nonfinite_duplicate_bounds_and_infeasible_fail_closed(self):
        oracle = self.oracle

        def baseline(problem):
            return oracle._baseline_archive(problem)

        factories = (
            lambda _problem: np.ones((4, 3)),
            lambda _problem: np.full((4, 4), np.nan),
            lambda problem: np.repeat(baseline(problem)[:1], 4, axis=0),
            lambda problem: baseline(problem)[:3],
            lambda problem: np.vstack((
                baseline(problem)[:3], [16.0, 590.0, 0.2, 590.0]
            )),
            lambda problem: np.asarray([
                [15.0, 600.0, 0.45, 450.0],
                [15.0, 600.0, 0.44, 451.0],
                [15.0, 600.0, 0.43, 452.0],
                [15.0, 600.0, 0.42, 453.0],
            ]),
            lambda _problem: [[True, 500.0, 0.2, 500.0]] * 4,
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)

    def test_public_problem_omits_split_shift_reference_and_hidden_labels(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            rendered = repr(instance["problem"])
            self.assertNotIn(instance["name"], rendered)
            self.assertNotIn(instance["split"], rendered)
            self.assertNotIn("SHIFT_SPECS", rendered)
            self.assertNotIn("reference", rendered.lower())
            self.assertNotIn("sobol", rendered.lower())

    def test_candidate_gets_six_fresh_sandbox_sessions(self):
        oracle = self.oracle

        class CountingPolicy:
            def __init__(self):
                self.calls = 0
                self.resets = 0

            def __call__(self, problem):
                self.calls += 1
                return oracle._baseline_archive(problem)

            def reset_session(self):
                self.resets += 1

        policy = CountingPolicy()
        metrics = oracle.evaluate(policy)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(policy.calls, 6)
        self.assertEqual(policy.resets, 5)

    def test_secure_baseline_executes_with_v2_entrypoint(self):
        spec = find_task("RankineCycleOpt", include_uncertified=True)
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=30)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["robustness_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_instance_call_count"], 6, metrics)


if __name__ == "__main__":
    unittest.main()
