from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/MOSFETDoping"
VERIFICATION = TASK / "verification"
CALIBRATION = ROOT / "scripts/calibrate_mosfet_v2.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_device():
    return _load(VERIFICATION / "device.py", "mosfet_device_test")


def _load_oracle():
    sys.path.insert(0, str(VERIFICATION))
    try:
        return _load(VERIFICATION / "evaluator.py", "mosfet_oracle_test")
    finally:
        sys.path.pop(0)


class MOSFETCompactModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = _load_device()
        cls.oracle = _load_oracle()

    def test_doping_and_temperature_have_expected_physical_directions(self):
        design = np.asarray([16.2, 17.1, 17.1, 0.16, 0.84, 0.08])
        condition = self.oracle.INSTANCES[0]["device"]
        lower = design.copy()
        lower[:3] -= 0.5
        higher = design.copy()
        higher[:3] += 0.5
        low_record = self.device.evaluate_device(lower, condition)
        high_record = self.device.evaluate_device(higher, condition)
        hot_record = self.device.evaluate_device(
            design, condition, {"temperature_delta_k": 35.0}
        )
        nominal = self.device.evaluate_device(design, condition)
        self.assertGreater(
            high_record["threshold_voltage_v"], low_record["threshold_voltage_v"]
        )
        self.assertLess(
            high_record["effective_mobility_cm2_vs"],
            low_record["effective_mobility_cm2_vs"],
        )
        self.assertGreater(
            hot_record["subthreshold_swing_mv_dec"],
            nominal["subthreshold_swing_mv_dec"],
        )
        self.assertGreater(
            hot_record["off_current_na_per_um"], nominal["off_current_na_per_um"]
        )
        for record in (low_record, high_record, hot_record, nominal):
            self.assertTrue(all(
                np.isfinite(value) for value in record.values()
                if isinstance(value, (float, np.floating))
            ))

    def test_source_drain_reversal_reverses_asymmetric_profile(self):
        design = np.asarray([16.2, 17.5, 16.6, 0.14, 0.82, 0.07])
        x = np.linspace(0.0, 1.0, self.device.GRID_SIZE)
        nominal = self.device.gaussian_profile_cm3(design, x)
        reversed_profile = self.device.gaussian_profile_cm3(
            design, x, {"reverse_source_drain": True}
        )
        np.testing.assert_allclose(reversed_profile, nominal[::-1], rtol=0, atol=0)


class MOSFETV2EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _load_oracle()

    def policy(self, kind):
        oracle = self.oracle

        def design(problem):
            for instance in oracle.INSTANCES:
                if instance["problem"] == problem:
                    if kind == "baseline":
                        return oracle._baseline_archive(problem)
                    return oracle._reference_archive(instance, kind)
            raise ValueError("unknown public MOSFET problem")

        return design

    def test_baseline_nominal_and_robust_witnesses_define_real_tradeoff(self):
        oracle = self.oracle
        baseline = oracle.evaluate(self.policy("baseline"))
        nominal = oracle.evaluate(self.policy("nominal"))
        robust = oracle.evaluate(self.policy("robust"))
        self.assertTrue(oracle.MOSFET_DOPING_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(len(oracle.SHIFT_SPECS), 6)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0, delta=1e-14)
        self.assertAlmostEqual(
            baseline["heldout_policy_score"], 0.0, delta=1e-14
        )

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertEqual(nominal["robustness_score"], 0.0)
        self.assertLess(nominal["development_shift_feasibility_rate"], 0.90)
        self.assertLess(nominal["heldout_shift_feasibility_rate"], 0.90)

        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertEqual(robust["development_shift_feasibility_rate"], 1.0)
        self.assertEqual(robust["heldout_shift_feasibility_rate"], 1.0)
        self.assertGreater(robust["combined_score"], 0.85)
        self.assertLess(robust["combined_score"], 0.98)
        self.assertGreater(robust["heldout_policy_score"], 0.80)
        self.assertLess(robust["heldout_policy_score"], 0.98)

        visible = search_visible_metrics(robust)
        self.assertEqual(
            set(visible),
            {"combined_score", "valid", "feasibility_rate", "raw_score"},
        )
        for key in (
            "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_shift_feasibility_rate",
            "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_reference_indices_and_frozen_anchors_recompute_exactly(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            baseline = oracle._baseline_archive(problem)
            nominal = oracle._reference_archive(instance, "nominal")
            robust = oracle._reference_archive(instance, "robust")
            observed = {
                "baseline_nominal_hypervolume": oracle._hypervolume(
                    problem, oracle._evaluate_archive(baseline, instance["device"])
                ),
                "reference_nominal_hypervolume": oracle._hypervolume(
                    problem, oracle._evaluate_archive(nominal, instance["device"])
                ),
                "baseline_shifted_hypervolumes": tuple(
                    oracle._hypervolume(
                        problem,
                        oracle._evaluate_archive(baseline, instance["device"], shift),
                    )
                    for shift in oracle.SHIFT_SPECS
                ),
                "reference_shifted_hypervolumes": tuple(
                    oracle._hypervolume(
                        problem,
                        oracle._evaluate_archive(robust, instance["device"], shift),
                    )
                    for shift in oracle.SHIFT_SPECS
                ),
            }
            expected = oracle.CALIBRATED_ANCHORS[instance["name"]]
            for key in (
                "baseline_nominal_hypervolume", "reference_nominal_hypervolume"
            ):
                self.assertAlmostEqual(observed[key], expected[key], delta=1e-14)
            for key in (
                "baseline_shifted_hypervolumes", "reference_shifted_hypervolumes"
            ):
                np.testing.assert_allclose(
                    observed[key], expected[key], rtol=0.0, atol=1e-14
                )
            self.assertTrue(all(
                record["process_feasible"]
                for record in oracle._evaluate_archive(nominal, instance["device"])
            ))
            self.assertTrue(all(
                record["process_feasible"]
                for shift in oracle.SHIFT_SPECS
                for record in oracle._evaluate_archive(
                    robust, instance["device"], shift
                )
            ))

    def test_calibration_rebuild_matches_committed_literals(self):
        calibration = _load(CALIBRATION, "mosfet_calibration_test")
        report = calibration.build_report()
        self.assertTrue(report["execution_passed"])
        self.assertTrue(report["committed_literals_checked"])
        self.assertTrue(report["committed_literals_match"])
        self.assertTrue(all(report["directional_checks"].values()))
        self.assertTrue(all(report["witness_tradeoff_checks"].values()))

    def test_calibration_rejects_broadcastable_anchor_shape_mismatch(self):
        calibration = _load(CALIBRATION, "mosfet_calibration_shape_test")
        expected = {
            "device": {
                "baseline_nominal_hypervolume": 0.25,
                "reference_nominal_hypervolume": 0.75,
                "baseline_shifted_hypervolumes": (0.25,),
                "reference_shifted_hypervolumes": (0.75,),
            }
        }
        observed = {
            "device": {
                "baseline_nominal_hypervolume": 0.25,
                "reference_nominal_hypervolume": 0.75,
                "baseline_shifted_hypervolumes": (0.25, 0.25),
                "reference_shifted_hypervolumes": (0.75, 0.75),
            }
        }
        self.assertTrue(np.allclose(
            observed["device"]["baseline_shifted_hypervolumes"],
            expected["device"]["baseline_shifted_hypervolumes"],
            rtol=0.0,
            atol=1e-14,
        ))
        self.assertFalse(calibration._anchors_match(observed, expected))

    def test_malformed_nonfinite_bool_bounds_duplicates_and_infeasible_fail(self):
        oracle = self.oracle
        factories = (
            lambda _problem: np.ones((4, 3)),
            lambda _problem: np.full((4, 6), np.nan),
            lambda problem: np.repeat(oracle._baseline_archive(problem)[:1], 4, 0),
            lambda problem: oracle._baseline_archive(problem)[:3],
            lambda problem: np.vstack((
                oracle._baseline_archive(problem)[:3],
                [18.0, 15.3, 15.3, 0.16, 0.84, 0.08],
            )),
            lambda _problem: [[True, 15.3, 15.3, 0.16, 0.84, 0.08]] * 4,
            lambda _problem: np.asarray([
                [17.4, 18.25, 18.25, 0.06, 0.66, 0.035],
                [17.4, 18.25, 18.20, 0.061, 0.661, 0.036],
                [17.4, 18.20, 18.25, 0.062, 0.662, 0.037],
                [17.4, 18.20, 18.20, 0.063, 0.663, 0.038],
            ]),
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)

    def test_public_problem_omits_split_shift_reference_and_hidden_labels(self):
        for instance in self.oracle.INSTANCES:
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

    def test_all_six_devices_get_fresh_process_and_tmpfs(self):
        spec = find_task("MOSFETDoping", include_uncertified=True)
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def design_doping_archive(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/mosfet-device-state')
                with open('/tmp/mosfet-device-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_mosfet_device_counter', 0)
                np._mosfet_device_counter = imported_counter + 1
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return np.full((4, 6), np.nan)
                return np.asarray([
                    [16.4, 15.3, 15.3, 0.16, 0.84, 0.08],
                    [16.6, 15.3, 15.3, 0.16, 0.84, 0.08],
                    [16.8, 15.3, 15.3, 0.16, 0.84, 0.08],
                    [17.0, 15.3, 15.3, 0.16, 0.84, 0.08],
                ])
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=30)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))

    def test_secure_baseline_executes_with_v2_entrypoint(self):
        spec = find_task("MOSFETDoping", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "design_doping_archive")
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=30)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertAlmostEqual(
            metrics["combined_score"], 0.0, delta=1e-14, msg=metrics
        )
        self.assertEqual(metrics["candidate_instance_call_count"], 6, metrics)

    def test_legacy_driver_uses_v2_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(TASK / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0, delta=1e-14)
        self.assertAlmostEqual(metrics["raw_score"], 0.0, delta=1e-14)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()
