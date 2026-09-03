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
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Chemistry/DistillationColumnDesign"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    return _load(
        TASK / "verification/evaluator.py", "distillation_v2_test_oracle"
    )


def _calibration():
    return _load(
        ROOT / "scripts/calibrate_distillation_v2.py",
        "distillation_v2_test_calibration",
    )


class DistillationV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()
        cls.calibration = _calibration()

    def test_reference_witnesses_are_feasible_nontrivial_and_sealed(self):
        oracle = self.oracle
        baseline = oracle.evaluate(oracle._baseline_design)
        nominal = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=False)
        )
        robust = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=True)
        )

        self.assertTrue(oracle.DISTILLATION_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(len(oracle.SHIFT_SPECS), 5)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["feasibility_rate"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertLessEqual(
            nominal["development_shift_feasibility_rate"], 0.25
        )
        self.assertEqual(nominal["robustness_score"], 0.0)

        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertGreater(robust["combined_score"], 0.90)
        self.assertGreater(robust["heldout_policy_score"], 0.85)
        self.assertEqual(robust["development_shift_feasibility_rate"], 1.0)
        self.assertEqual(robust["heldout_shift_feasibility_rate"], 1.0)

        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            self.assertTrue(instance["baseline_nominal"]["process_feasible"])
            self.assertTrue(instance["nominal_reference"]["process_feasible"])
            self.assertTrue(instance["robust_reference"]["process_feasible"])
            baseline_cost = instance["baseline_nominal"]["annualized_cost"]
            self.assertLess(
                instance["nominal_reference"]["annualized_cost"],
                0.55 * baseline_cost,
            )
            self.assertLess(
                instance["robust_reference"]["annualized_cost"],
                0.60 * baseline_cost,
            )
            rows = [instance["robust_reference"]] + [
                oracle._shifted_metrics(
                    instance["robust_reference_design"], problem, shift
                )
                for shift in oracle.SHIFT_SPECS
            ]
            self.assertTrue(all(row["process_feasible"] for row in rows))
            self.assertGreaterEqual(
                min(
                    self.calibration._constraint_margin(row, problem)
                    for row in rows
                ),
                5.0e-4,
            )

        visible = search_visible_metrics(robust)
        for key in (
            "robustness_score",
            "heldout_policy_score",
            "heldout_robustness_score",
            "development_shift_feasibility_rate",
            "development_mean_annualized_cost",
            "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_independent_least_squares_mesh_matches_all_reference_conditions(self):
        oracle = self.oracle
        calibration = self.calibration
        for instance in oracle.INSTANCES:
            checks = calibration._independent_checks(oracle, instance)
            self.assertTrue(checks["passed"], instance["name"])
            self.assertEqual(len(checks["checks"]), 12)
            self.assertLessEqual(
                checks["maximum_product_composition_error"], 2.0e-8
            )
            self.assertLessEqual(checks["maximum_recovery_error"], 2.0e-8)
            self.assertLessEqual(
                checks["maximum_independent_stage_balance_residual"],
                1.0e-9,
            )
            self.assertLessEqual(
                checks["maximum_independent_overall_balance_residual"],
                2.0e-8,
            )

    def test_analytic_tridiagonal_jacobian_matches_finite_difference(self):
        oracle = self.oracle
        problem = oracle.INSTANCES[0]["problem"]
        tray_count = 8
        epsilon = 1.0e-7
        for feed_stage in (1, 4, 8):
            liquid = np.linspace(0.82, 0.12, tray_count + 1)
            residual, lower, diagonal, upper, _ = (
                oracle._balance_residual_and_jacobian(
                    liquid,
                    tray_count,
                    feed_stage,
                    2.1,
                    0.50,
                    0.50,
                    0.85,
                    2.45,
                )
            )
            analytic = np.diag(diagonal)
            analytic += np.diag(lower, -1)
            analytic += np.diag(upper, 1)
            finite = np.empty_like(analytic)
            for column in range(tray_count + 1):
                plus = liquid.copy()
                minus = liquid.copy()
                plus[column] += epsilon
                minus[column] -= epsilon
                plus_residual = oracle._balance_residual_and_jacobian(
                    plus, tray_count, feed_stage, 2.1, 0.50, 0.50, 0.85, 2.45
                )[0]
                minus_residual = oracle._balance_residual_and_jacobian(
                    minus, tray_count, feed_stage, 2.1, 0.50, 0.50, 0.85, 2.45
                )[0]
                finite[:, column] = (
                    plus_residual - minus_residual
                ) / (2.0 * epsilon)
            self.assertTrue(np.all(np.isfinite(residual)))
            self.assertLess(float(np.max(np.abs(analytic - finite))), 2.0e-8)

    def test_baseline_and_references_close_stage_and_overall_balances(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            designs = (
                instance["baseline_design"],
                instance["nominal_reference_design"],
                instance["robust_reference_design"],
            )
            for design in designs:
                nominal = oracle._solve_column(design, problem)
                self.assertLessEqual(
                    nominal["maximum_stage_balance_residual"],
                    oracle.BALANCE_TOLERANCE,
                )
                self.assertLessEqual(
                    nominal["overall_component_balance_residual"],
                    oracle.BALANCE_TOLERANCE,
                )
            for shift in oracle.SHIFT_SPECS:
                shifted = oracle._shifted_metrics(
                    instance["robust_reference_design"], problem, shift
                )
                self.assertLessEqual(
                    shifted["maximum_stage_balance_residual"],
                    oracle.BALANCE_TOLERANCE,
                )
                self.assertLessEqual(
                    shifted["overall_component_balance_residual"],
                    oracle.BALANCE_TOLERANCE,
                )

    def test_malformed_nonfinite_boolean_nonintegral_and_bounds_fail_closed(self):
        oracle = self.oracle

        def baseline(problem):
            return oracle._baseline_design(problem)

        factories = (
            lambda problem: {
                key: value for key, value in baseline(problem).items()
                if key != "feed_split_gain"
            },
            lambda problem: {**baseline(problem), "extra": 1.0},
            lambda problem: {**baseline(problem), "reflux_ratio": np.nan},
            lambda problem: {**baseline(problem), "distillate_fraction": np.inf},
            lambda problem: {**baseline(problem), "reflux_ratio": "3.0"},
            lambda problem: {**baseline(problem), "reflux_ratio": 3.0 + 0.0j},
            lambda problem: {**baseline(problem), "tray_count": True},
            lambda problem: {**baseline(problem), "feed_stage": np.bool_(True)},
            lambda problem: {**baseline(problem), "tray_count": 12.5},
            lambda problem: {**baseline(problem), "feed_stage": 2.5},
            lambda problem: {**baseline(problem), "feed_stage": 100},
            lambda problem: {**baseline(problem), "reflux_ratio": 20.0},
            lambda problem: {**baseline(problem), "feed_split_gain": -1.0},
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_shift_solver_failure_is_sealed_from_nominal_validity(self):
        oracle = self.oracle
        instance = oracle.DEVELOPMENT_INSTANCES[0]
        design = dict(instance["nominal_reference_design"])
        nominal = oracle._solve_column(design, instance["problem"])
        self.assertTrue(nominal["process_feasible"])

        original = oracle._shifted_metrics

        def shifted_failure(_design, _problem, shift):
            raise ValueError("sealed condition did not converge: " + shift["name"])

        oracle._shifted_metrics = shifted_failure
        try:
            record = oracle._score_instance(lambda _: design, instance)
        finally:
            oracle._shifted_metrics = original

        self.assertTrue(record["valid"])
        self.assertTrue(record["process_feasible"])
        self.assertAlmostEqual(record["score"], 1.0)
        self.assertTrue(all(not row["valid"] for row in record["shifted"]))
        self.assertEqual(record["robustness_score"], 0.0)

    def test_public_problem_does_not_expose_split_references_or_shifts(self):
        oracle = self.oracle
        forbidden = {
            "name", "split", "shift", "shifts", "reference",
            "nominal_reference_design", "robust_reference_design",
            "baseline_design", "score", "ground_truth", "answer_key",
        }
        observed = []

        def policy(problem):
            observed.append(problem)
            return oracle._baseline_design(problem)

        metrics = oracle.evaluate(policy)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(len(observed), 6)
        for problem in observed:
            self.assertTrue(forbidden.isdisjoint(problem))
            self.assertEqual(set(problem["design_fields"]), set(oracle.DESIGN_FIELDS))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_secure_evaluation_resets_process_imports_and_tmpfs_per_instance(self):
        spec = find_task(
            "ChemicalProcess/DistillationColumnDesign",
            include_uncertified=True,
        )
        baseline_source = (TASK / "solution.py").read_text(encoding="utf-8")
        baseline_source = baseline_source.replace(
            "def design_column(problem):",
            "def _baseline_design_column(problem):",
            1,
        )
        source = baseline_source + textwrap.dedent(
            """

            import os
            import math as _state_module
            _module_counter = 0

            def design_column(problem):
                global _module_counter
                _module_counter += 1
                tmp_seen = os.path.exists('/tmp/distillation-instance-state')
                with open('/tmp/distillation-instance-state', 'w') as handle:
                    handle.write(str(_module_counter))
                imported_counter = getattr(
                    _state_module, '_distillation_instance_counter', 0
                )
                _state_module._distillation_instance_counter = imported_counter + 1
                if _module_counter != 1 or tmp_seen or imported_counter != 0:
                    return {
                        'tray_count': float('nan'), 'feed_stage': 1,
                        'reflux_ratio': 1.0, 'distillate_fraction': 0.5,
                        'feed_split_gain': 1.0,
                    }
                return _baseline_design_column(problem)
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()
