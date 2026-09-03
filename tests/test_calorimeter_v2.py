from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.stats import gamma as gamma_distribution

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Physics/CalorimeterDesign"
CALIBRATION = ROOT / "scripts/calibrate_calorimeter_v2.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CalorimeterV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _load(
            TASK / "verification/evaluator.py", "calorimeter_v2_test"
        )

    def test_reference_witnesses_are_nontrivial_and_sealed(self):
        oracle = self.oracle
        baseline = oracle.evaluate(oracle._weak_baseline_design)
        nominal = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=False)
        )
        robust = oracle.evaluate(
            lambda problem: oracle.reference_policy(problem, robust=True)
        )

        self.assertTrue(oracle.CALORIMETER_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        self.assertEqual(len(oracle.SHIFT_SPECS), 5)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)

        self.assertEqual(nominal["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertAlmostEqual(nominal["heldout_policy_score"], 1.0)
        self.assertEqual(nominal["robustness_score"], 0.0)
        self.assertEqual(nominal["heldout_robustness_score"], 0.0)
        self.assertLess(
            nominal["development_shift_geometry_feasibility_rate"], 0.60
        )
        self.assertLess(
            nominal["development_mean_resolution"],
            baseline["development_mean_resolution"] - 0.02,
        )

        self.assertEqual(robust["valid"], 1.0)
        self.assertGreater(robust["combined_score"], 0.70)
        self.assertLess(robust["combined_score"], 0.90)
        self.assertGreater(robust["heldout_policy_score"], 0.65)
        self.assertLess(robust["heldout_policy_score"], 0.90)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertAlmostEqual(robust["heldout_robustness_score"], 1.0)
        self.assertEqual(
            robust["development_shift_geometry_feasibility_rate"], 1.0
        )
        self.assertEqual(
            robust["heldout_shift_geometry_feasibility_rate"], 1.0
        )
        self.assertLess(
            robust["development_mean_cost_utilization"],
            nominal["development_mean_cost_utilization"] - 0.015,
        )

        visible = search_visible_metrics(nominal)
        for key in (
            "robustness_score",
            "heldout_policy_score",
            "development_mean_resolution",
            "development_linearity_rms",
            "development_minimum_containment",
            "development_mean_cost_utilization",
            "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_gamma_profile_matches_independent_cdf_and_quadrature(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            for energy in problem["energies_gev"]:
                shape = 1.0 + float(problem["shower_profile_b"]) * (
                    math.log(
                        float(energy)
                        / float(problem["critical_energy_gev"])
                    ) - 0.5
                )
                rate = float(problem["shower_profile_b"])
                for depth in (0.25, 2.0, 8.0, 16.0, 28.0, 45.0):
                    expected = gamma_distribution.cdf(
                        depth, a=shape, scale=1.0 / rate
                    )
                    integrated, _ = quad(
                        lambda value: float(
                            oracle._shower_density(value, energy)
                        ),
                        0.0,
                        depth,
                        epsabs=2.0e-13,
                        epsrel=2.0e-13,
                        limit=300,
                    )
                    observed = float(oracle._shower_cdf(depth, energy))
                    self.assertAlmostEqual(observed, expected, delta=3e-12)
                    self.assertAlmostEqual(observed, integrated, delta=3e-11)

    def test_shower_maximum_depth_containment_and_stochastic_invariants(self):
        oracle = self.oracle
        energies = np.geomspace(0.8, 250.0, 25)
        maxima = np.asarray([
            oracle._shower_maximum_x0(value) for value in energies
        ])
        self.assertTrue(np.all(np.diff(maxima) > 0.0))
        for energy, maximum in zip(energies, maxima):
            epsilon = 1.0e-5
            center = float(oracle._shower_density(maximum, energy))
            self.assertGreaterEqual(
                center,
                float(oracle._shower_density(maximum - epsilon, energy)),
            )
            self.assertGreaterEqual(
                center,
                float(oracle._shower_density(maximum + epsilon, energy)),
            )
            depths = np.linspace(0.0, 45.0, 100)
            containment = oracle._shower_cdf(depths, energy)
            self.assertTrue(np.all(np.diff(containment) >= -1e-14))

        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            passive, active = instance["nominal_reference_designs"][1]
            metrics = oracle._metrics_for_design(passive, active, problem)
            for row in metrics["energy_metrics"]:
                self.assertAlmostEqual(
                    row["sampling_resolution"]
                    * math.sqrt(row["energy_gev"]),
                    row["stochastic_coefficient"],
                    delta=3e-15,
                )

    def test_material_budget_and_cost_identities(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            for designs in (
                instance["nominal_reference_designs"],
                instance["robust_reference_designs"],
            ):
                for option, (passive, active) in enumerate(designs):
                    expected_mass = (
                        float(np.sum(passive))
                        * 1.0e-3
                        * problem["lead_density_kg_m3"]
                    )
                    self.assertAlmostEqual(
                        oracle._lead_mass_kg_m2(
                            passive, problem["lead_density_kg_m3"]
                        ), expected_mass
                    )
                    expected_cost = (
                        problem["lead_cost_per_kg"] * expected_mass
                        + problem["active_cost_per_liter"]
                        * float(np.sum(active))
                        + problem["readout_areal_cost_per_layer"]
                        * problem["n_layers"]
                    )
                    geometry = oracle._geometry_metrics(
                        passive, active, problem, option
                    )
                    self.assertTrue(geometry["feasible"])
                    self.assertAlmostEqual(
                        geometry["areal_cost"], expected_cost
                    )
                    _, _, depth = oracle._material_intervals(
                        passive, active
                    )
                    self.assertAlmostEqual(
                        depth,
                        float(np.sum(passive)) / oracle.X0_PB_MM
                        + float(np.sum(active))
                        / oracle.X0_SCINTILLATOR_MM,
                    )

    def test_malformed_nonfinite_duplicate_and_out_of_bound_fail_closed(self):
        oracle = self.oracle

        def baseline(problem):
            return oracle._weak_baseline_design(problem)

        factories = (
            lambda problem: {
                "passive_thicknesses_mm": np.full(
                    (3, problem["n_layers"]), np.nan
                ),
                "active_thicknesses_mm": np.full(
                    (3, problem["n_layers"]), 2.0
                ),
            },
            lambda problem: {
                key: value[:, :-1] for key, value in baseline(problem).items()
            },
            lambda problem: {
                **baseline(problem),
                "active_thicknesses_mm": np.full(
                    (3, problem["n_layers"]), 99.0
                ),
            },
            lambda problem: {
                key: np.repeat(value[:1], 3, axis=0)
                for key, value in baseline(problem).items()
            },
            lambda problem: {
                key: value.astype(complex) + 1e-3j
                for key, value in baseline(problem).items()
            },
            lambda problem: {
                **baseline(problem), "unexpected_diagnostic": 1.0
            },
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertEqual(metrics["candidate_instance_valid_rate"], 0.0)

    def test_public_problems_hide_split_references_and_shifts(self):
        oracle = self.oracle
        forbidden = {
            "name",
            "split",
            "shift",
            "reference",
            "baseline_design",
            "nominal_reference_parameters",
            "robust_reference_parameters",
        }
        for instance in oracle.INSTANCES:
            problem = instance["problem"]
            self.assertTrue(forbidden.isdisjoint(problem))
            self.assertEqual(
                tuple(problem["design_fields"]), oracle.DESIGN_FIELDS
            )

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_all_six_instances_get_fresh_process_and_tmpfs(self):
        spec = find_task(
            "ParticlePhysics/CalorimeterDesign", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def design_calorimeter(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/calorimeter-instance-state')
                with open('/tmp/calorimeter-instance-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_calorimeter_counter', 0)
                np._calorimeter_counter = imported_counter + 1
                n = int(problem['n_layers'])
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return {
                        'passive_thicknesses_mm': np.full((3, n), np.nan),
                        'active_thicknesses_mm': np.full((3, n), np.nan),
                    }
                passive = np.full(
                    (3, n),
                    float(problem['baseline_absorber_depth_x0'])
                    * float(problem['radiation_length_pb_mm']) / n,
                )
                mass = (
                    float(np.sum(passive[0])) * 1e-3
                    * float(problem['lead_density_kg_m3'])
                )
                passive_cost = float(problem['lead_cost_per_kg']) * mass
                fixed = float(problem['readout_areal_cost_per_layer']) * n
                active = np.empty_like(passive)
                for option, cap in enumerate(problem['option_cost_caps']):
                    total = (
                        float(problem['baseline_cost_fraction']) * float(cap)
                        - passive_cost - fixed
                    ) / float(problem['active_cost_per_liter'])
                    active[option] = total / n
                return {
                    'passive_thicknesses_mm': passive,
                    'active_thicknesses_mm': active,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=120)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["candidate_instance_call_count"], 6)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_secure_baseline_and_legacy_driver_use_v2_interface(self):
        spec = find_task(
            "ParticlePhysics/CalorimeterDesign", include_uncertified=True
        )
        secure = evaluate_candidate(
            spec, spec.initial_program_path, timeout_s=120
        )
        self.assertEqual(secure["valid"], 1.0)
        self.assertEqual(secure["combined_score"], 0.0)
        self.assertEqual(secure["raw_score"], 0.0)
        self.assertEqual(secure["candidate_instance_call_count"], 6)

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

    def test_calibration_fast_invariants_pass(self):
        calibration = _load(CALIBRATION, "calorimeter_v2_calibration_test")
        oracle = calibration._load_oracle()
        physics = [
            calibration._physics_checks(oracle, instance)
            for instance in oracle.INSTANCES
        ]
        invalid = calibration._invalid_artifact_checks(oracle)
        self.assertTrue(all(row["passed"] for row in physics))
        self.assertTrue(all(row["passed"] for row in invalid.values()))
        for instance in oracle.INSTANCES:
            for option in range(oracle.ARCHIVE_SIZE):
                nominal = calibration._reference_quality(
                    oracle,
                    instance["problem"],
                    option,
                    instance["nominal_reference_parameters"][option],
                    False,
                )
                robust = calibration._reference_quality(
                    oracle,
                    instance["problem"],
                    option,
                    instance["robust_reference_parameters"][option],
                    True,
                )
                self.assertGreater(
                    nominal,
                    instance["baseline_options"][option]["nominal"][
                        "utility"
                    ],
                )
                self.assertGreater(
                    robust,
                    instance["baseline_options"][option]["robust_utility"],
                )


if __name__ == "__main__":
    unittest.main()
