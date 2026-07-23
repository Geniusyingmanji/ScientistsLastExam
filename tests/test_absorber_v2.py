from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.special import jv

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parent.parent


def _oracle():
    path = (
        ROOT
        / "benchmarks/AcousticMetamaterials/BroadbandAbsorber"
        / "verification/evaluator.py"
    )
    spec = importlib.util.spec_from_file_location("absorber_v2_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load absorber evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _independent_cell_impedances(oracle, design, problem):
    design = np.asarray(design, dtype=float)
    frequency = np.geomspace(
        *problem["frequency_band_hz"], problem["frequency_sample_count"]
    )
    omega = 2.0 * np.pi * frequency[:, None]
    density = float(problem["air_density_kg_m3"])
    sound_speed = float(problem["sound_speed_m_s"])
    viscosity = float(problem["dynamic_viscosity_pa_s"])
    depth, length, radius = design.T
    effective_length = length + 1.70 * radius
    opening_fraction = np.pi * radius**2 / float(problem["cell_side_m"]) ** 2
    argument = radius[None, :] * np.sqrt(-1j * omega * density / viscosity)
    correction = 1.0 - 2.0 * jv(1, argument) / (
        argument * jv(0, argument)
    )
    dynamic_density = density / correction
    wavenumber = omega / sound_speed
    neck = (
        1j * omega * dynamic_density * effective_length[None, :]
        + 0.5 * density * sound_speed * (wavenumber * radius[None, :]) ** 2
    )
    cavity = -1j * density * sound_speed / np.tan(
        wavenumber * depth[None, :]
    )
    return frequency, neck / opening_fraction[None, :] + cavity


class BroadbandAbsorberV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()

    def test_reference_witnesses_are_valid_nontrivial_and_sealed(self):
        oracle = self.oracle
        baseline = oracle.evaluate(
            lambda problem: oracle._weak_baseline_design(problem)
        )
        nominal = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=False)
        )
        robust = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=True)
        )

        self.assertTrue(oracle.ABSORBER_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)
        self.assertGreater(baseline["development_exact_utility"], 0.05)
        self.assertLess(baseline["development_exact_utility"], 0.10)

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertGreater(nominal["robustness_score"], 0.90)
        self.assertGreater(nominal["heldout_robustness_score"], 0.90)
        self.assertEqual(robust["valid"], 1.0)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertGreater(robust["combined_score"], 0.90)
        self.assertGreater(robust["heldout_policy_score"], 0.90)
        self.assertTrue(all(row["valid"] for row in nominal["per_instance"]))
        self.assertTrue(all(row["valid"] for row in robust["per_instance"]))

        visible = search_visible_metrics(nominal)
        for key in (
            "robustness_score",
            "heldout_policy_score",
            "development_proxy_utility",
            "development_exact_utility",
            "development_mean_absorption",
            "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_dynamic_density_matches_independent_bessel_implementation(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            design = instance["nominal_reference_design"]
            frequency, expected = _independent_cell_impedances(
                oracle, design, problem
            )
            actual_frequency, actual, density, sound_speed, angle = (
                oracle._cell_impedances(design, problem)
            )
            self.assertTrue(np.array_equal(actual_frequency, frequency))
            self.assertEqual(density, problem["air_density_kg_m3"])
            self.assertEqual(sound_speed, problem["sound_speed_m_s"])
            self.assertEqual(angle, 0.0)
            relative = np.max(
                np.abs(actual - expected) / np.maximum(np.abs(expected), 1.0)
            )
            self.assertLess(float(relative), 2.0e-12)

    def test_impedance_is_passive_and_absorption_is_bounded(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            for design in (
                instance["baseline_design"],
                instance["nominal_reference_design"],
                instance["robust_reference_design"],
            ):
                for shift in (None,) + tuple(oracle.SHIFT_SPECS):
                    _, absorption, panel, cells = oracle._absorption_spectrum(
                        design, instance["problem"], shift=shift
                    )
                    self.assertGreaterEqual(float(np.min(cells.real)), -1e-10)
                    self.assertGreaterEqual(float(np.min(panel.real)), -1e-10)
                    self.assertGreaterEqual(float(np.min(absorption)), 0.0)
                    self.assertLessEqual(float(np.max(absorption)), 1.0)

    def test_manufacturing_over_thickness_is_a_sealed_robustness_failure(self):
        oracle = self.oracle

        def edge_of_envelope(problem):
            count = int(problem["n_resonators"])
            neck_length = np.full(count, 0.004)
            cavity_depth = np.full(
                count, float(problem["maximum_total_depth_m"]) - 0.004
            )
            neck_radius = np.full(count, 0.003)
            return np.column_stack((
                cavity_depth, neck_length, neck_radius
            ))

        metrics = oracle.evaluate(edge_of_envelope)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))
        self.assertTrue(all(
            row["shift_geometry_feasibility_rate"] < 1.0
            for row in metrics["per_instance"]
        ))
        self.assertEqual(metrics["robustness_score"], 0.0)
        self.assertEqual(metrics["heldout_robustness_score"], 0.0)

    def test_malformed_nonfinite_and_out_of_bound_designs_fail_closed(self):
        oracle = self.oracle

        def valid(problem):
            return oracle._weak_baseline_design(problem)

        factories = (
            lambda problem: valid(problem)[:-1],
            lambda problem: np.full(
                (problem["n_resonators"], 3), np.nan
            ),
            lambda problem: np.full(
                (problem["n_resonators"], 3), np.inf
            ),
            lambda problem: valid(problem).astype(complex) + 1j * 0.001,
            lambda problem: valid(problem).astype(str),
            lambda problem: np.column_stack((
                np.full(problem["n_resonators"], 0.001),
                np.full(problem["n_resonators"], 0.010),
                np.full(problem["n_resonators"], 0.003),
            )),
            lambda problem: np.column_stack((
                np.full(
                    problem["n_resonators"],
                    problem["maximum_total_depth_m"] - 0.003,
                ),
                np.full(problem["n_resonators"], 0.010),
                np.full(problem["n_resonators"], 0.003),
            )),
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_public_problems_do_not_expose_split_references_or_shifts(self):
        oracle = self.oracle
        forbidden = {
            "name", "split", "shift", "reference", "baseline_design",
            "nominal_reference_parameters", "robust_reference_parameters",
        }
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            self.assertTrue(forbidden.isdisjoint(problem))
            self.assertEqual(
                tuple(problem["design_columns"]), oracle.DESIGN_COLUMNS
            )

    def test_all_six_instances_get_fresh_process_and_tmpfs(self):
        spec = find_task(
            "AcousticMetamaterials/BroadbandAbsorber",
            include_uncertified=True,
        )
        source = textwrap.dedent("""
            import math
            import os
            import numpy as np

            module_counter = 0

            def design_absorber(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/absorber-instance-state')
                with open('/tmp/absorber-instance-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_absorber_instance_counter', 0)
                np._absorber_instance_counter = imported_counter + 1
                n = int(problem['n_resonators'])
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return np.full((n, 3), np.nan)
                low, high = map(float, problem['frequency_band_hz'])
                target = math.sqrt(low * high)
                radius = np.full(n, 0.003)
                length = np.full(n, 0.010)
                opening = np.pi * radius**2 / float(problem['cell_side_m'])**2
                effective = length + 1.70 * radius
                depth = opening * float(problem['sound_speed_m_s'])**2 / (
                    (2.0 * np.pi * target)**2 * effective
                )
                depth = np.clip(
                    depth,
                    float(problem['cavity_depth_bounds_m'][0]),
                    float(problem['maximum_total_depth_m']) - length - 0.002,
                )
                return np.column_stack((depth, length, radius))
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))

    def test_legacy_driver_uses_v2_entrypoint(self):
        task = ROOT / "benchmarks/AcousticMetamaterials/BroadbandAbsorber"
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(task / "frontier_eval/run_eval.py"),
                    "--candidate", str(task / "solution.py"),
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
