from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.evaluate import evaluate_candidate
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parent.parent


def _oracle():
    path = ROOT / "benchmarks/FluidDynamics/LidDrivenCavity/verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("cavity_v2_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LidDrivenCavityV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()

    def test_reference_residuals_literature_and_grid_refinement(self):
        oracle = self.oracle
        for scenario in oracle.INSTANCES:
            psi, omega = oracle._reference_solution(
                scenario["Re"], scenario["N"]
            )
            poisson, transport = oracle._relative_residuals(
                psi, omega, scenario["Re"]
            )
            self.assertLess(poisson, 1.0e-6)
            self.assertLess(transport, 1.0e-6)
            self.assertLess(oracle._boundary_error(psi, omega), 1.0e-10)

        reference = oracle.evaluate(
            lambda reynolds, n: tuple(
                field.copy()
                for field in oracle._reference_solution(reynolds, n)
            )
        )
        self.assertGreater(reference["combined_score"], 0.999)
        self.assertGreater(reference["heldout_policy_score"], 0.999)
        self.assertGreater(reference["robustness_score"], 0.999)
        self.assertGreater(reference["heldout_robustness_score"], 0.999)
        self.assertEqual(reference["feasibility_rate"], 1.0)
        self.assertEqual(reference["heldout_physics_feasibility_rate"], 1.0)
        self.assertLess(reference["ghia_re100"]["u_centerline_rmse"], 0.012)
        self.assertLess(reference["ghia_re100"]["v_centerline_rmse"], 0.015)
        self.assertTrue(all(
            row["reference_grid_difference"] < 0.08
            for row in reference["grid_refinement"]
        ))

    def test_weak_baseline_is_valid_but_not_a_physical_solution(self):
        oracle = self.oracle
        metrics = oracle.evaluate(
            lambda _reynolds, n: oracle._weak_baseline_fields(n)
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)
        self.assertEqual(metrics["heldout_policy_score"], 0.0)
        self.assertEqual(metrics["robustness_score"], 0.0)
        shown = search_visible_metrics(metrics)
        self.assertEqual(shown["feasibility_rate"], 0.0)
        for key in (
            "robustness_score", "heldout_policy_score", "ghia_re100",
            "grid_refinement", "per_instance",
        ):
            self.assertNotIn(key, shown)

    def test_nonphysical_field_injection_cannot_spoof_full_oracle(self):
        oracle = self.oracle

        def injection(_reynolds, n):
            psi, omega = oracle._weak_baseline_fields(n)
            psi[:, n // 2] = np.linspace(0.0, -0.05, n)
            return psi, omega

        metrics = oracle.evaluate(injection)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)
        self.assertTrue(all(
            not row["physics_feasible"] for row in metrics["per_instance"]
        ))
        self.assertTrue(any(
            row["boundary_relative_error"] > 1.0
            for row in metrics["per_instance"]
        ))

    def test_near_reference_similarity_cannot_bypass_physics_gate(self):
        oracle = self.oracle
        attenuation = 0.95

        def attenuated_reference(reynolds, n):
            psi, omega = oracle._reference_solution(reynolds, n)
            _baseline_psi, baseline_omega = oracle._weak_baseline_fields(n)
            # This preserves the Poisson equation and wall-vorticity formula
            # under linear scaling, but violates nonlinear transport.
            return (
                attenuation * psi,
                attenuation * omega + (1.0 - attenuation) * baseline_omega,
            )

        metrics = oracle.evaluate(attenuated_reference)
        self.assertGreater(metrics["ungated_development_score"], 0.80)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)
        self.assertTrue(all(
            row["score"] == 0.0 and not row["physics_feasible"]
            for row in metrics["per_instance"]
        ))
        self.assertTrue(all(
            row["score"] == 0.0 and not row["physics_feasible"]
            for row in metrics["grid_refinement"]
        ))
        shown = search_visible_metrics(metrics)
        self.assertNotIn("ungated_development_score", shown)

    def test_invalid_artifacts_fail_closed(self):
        oracle = self.oracle
        invalid = (
            lambda n: (np.zeros((n - 1, n)), np.zeros((n, n))),
            lambda n: (np.full((n, n), np.nan), np.zeros((n, n))),
            lambda n: (np.full((n, n), 2.01), np.zeros((n, n))),
            lambda n: (np.zeros((n, n)), np.full((n, n), 12.01 * n)),
            lambda n: np.zeros((n, n)),
        )
        for factory in invalid:
            metrics = oracle.evaluate(
                lambda _reynolds, n, factory=factory: factory(n)
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_all_eight_cases_get_fresh_sandbox_sessions(self):
        spec = find_task(
            "FluidDynamics/LidDrivenCavity", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def solve_cavity(Re, N):
                global module_counter
                del Re
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/cavity-instance-state')
                with open('/tmp/cavity-instance-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_cavity_instance_counter', 0)
                np._cavity_instance_counter = imported_counter + 1

                n = int(N)
                psi = np.zeros((n, n), dtype=float)
                omega = np.zeros((n, n), dtype=float)
                omega[-1, 1:-1] = -2.0 * (n - 1)
                omega[-1, 0] = omega[-1, -1] = -(n - 1)
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return psi[:-1], omega
                return psi, omega
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)

        self.assertEqual(metrics["candidate_call_count"], 8)
        self.assertEqual(metrics["candidate_call_valid_rate"], 1.0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["heldout_artifact_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))
        self.assertTrue(all(row["valid"] for row in metrics["grid_refinement"]))


if __name__ == "__main__":
    unittest.main()
