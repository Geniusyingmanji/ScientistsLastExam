from __future__ import annotations

import importlib.util
import math
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Optics/DiffractionGratingDesign"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "grating_rcwa_test_oracle")
CALIBRATION = _load(
    ROOT / "scripts/calibrate_diffraction_grating_rcwa.py",
    "grating_rcwa_test_calibration",
)


class DiffractionGratingRCWATests(unittest.TestCase):
    def evaluate_source(self, source, timeout=120):
        spec = find_task(
            "Optics/DiffractionGratingDesign", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_worlds_references_and_headroom(self):
        self.assertTrue(ORACLE.RCWA_GRATING_V2)
        self.assertEqual(len(ORACLE.DEVELOPMENT_WORLDS), 4)
        self.assertEqual(len(ORACLE.HELDOUT_WORLDS), 2)
        self.assertEqual(len(ORACLE.SHIFT_SPECS), 4)
        for world in ORACLE.WORLDS:
            self.assertGreater(
                world["reference_utility"], world["baseline_utility"] + 0.25
            )
            self.assertGreater(
                world["reference_robust_utility"],
                world["baseline_robust_utility"] + 0.24,
            )
        baseline = ORACLE.evaluate(ORACLE.baseline_policy)
        reference = ORACLE.evaluate(ORACLE.reference_policy)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertAlmostEqual(reference["combined_score"], 1.0)
        self.assertAlmostEqual(reference["robustness_score"], 1.0)
        self.assertAlmostEqual(reference["heldout_policy_score"], 1.0)
        self.assertAlmostEqual(reference["heldout_robustness_score"], 1.0)

    def test_uniform_interface_matches_fresnel_and_conserves_energy(self):
        for polarization in ORACLE.POLARIZATIONS:
            record = CALIBRATION._uniform_fresnel_check(ORACLE, polarization)
            self.assertLess(record["absolute_error"], 1.0e-12)
            self.assertLess(record["energy_residual"], 1.0e-12)

    def test_default_solver_conserves_energy_for_te_tm_and_oblique_incidence(self):
        world = ORACLE.WORLDS[0]
        problem = world["problem"]
        design = world["reference_design"]
        for wavelength_scale in (0.97, 1.03):
            for angle in (-6.0, 6.0):
                for polarization in ORACLE.POLARIZATIONS:
                    result = ORACLE._rcwa_efficiencies(
                        design,
                        problem["center_wavelength_um"] * wavelength_scale,
                        problem["period_um"],
                        problem["incident_index"],
                        problem["substrate_index"],
                        problem["ridge_index"],
                        angle,
                        polarization,
                    )
                    self.assertAlmostEqual(result["energy_sum"], 1.0, places=10)
                    self.assertGreaterEqual(result["target_efficiency"], 0.0)
                    self.assertLessEqual(result["target_efficiency"], 1.0)

    def test_fourier_order_convergence_preserves_utility(self):
        records, maximum_utility_delta, maximum_point_delta = (
            CALIBRATION._convergence_records(ORACLE)
        )
        self.assertEqual(len(records), 12)
        self.assertLess(maximum_utility_delta, 0.004)
        self.assertLess(maximum_point_delta, 0.025)

    def test_public_problem_hides_world_identity_and_sealed_shifts(self):
        forbidden = {
            "name", "split", "reference_parameters", "reference_design",
            "baseline_design", "anchors", "shift", "robustness",
        }
        for world in ORACLE.WORLDS:
            problem = world["problem"]
            self.assertTrue(forbidden.isdisjoint(problem))
            self.assertEqual(problem["layer_count"], 5)
            self.assertEqual(problem["polarizations"], ("TE", "TM"))

    def test_secure_baseline_is_valid_and_science_metrics_are_sealed(self):
        spec = find_task(
            "Optics/DiffractionGratingDesign", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
        self.assertEqual(secure["valid"], 1.0, secure)
        self.assertEqual(secure["combined_score"], 0.0)
        self.assertEqual(secure["candidate_instance_call_count"], 6)
        self.assertEqual(secure["candidate_instance_valid_rate"], 1.0)
        visible = search_visible_metrics(secure)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )
        self.assertNotIn("robustness_score", visible)
        self.assertNotIn("heldout_policy_score", visible)
        self.assertNotIn("per_instance", visible)

    def test_malformed_nonfinite_bounds_feature_and_total_depth_fail_closed(self):
        bodies = (
            "return []",
            "return [[float('nan'), 0.5, 0.5]] * problem['layer_count']",
            "return [[problem['depth_bounds_um'][0], 0.01, 0.5]] * problem['layer_count']",
            "return [[problem['depth_bounds_um'][1], 0.5, 0.5]] * problem['layer_count']",
            "return [[problem['depth_bounds_um'][0], 0.5, 1.0]] * problem['layer_count']",
        )
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(
                    "def design_grating(problem):\n    " + body
                )
                self.assertEqual(result["valid"], 0.0, result)

    def test_fresh_process_per_world(self):
        source = """
            import os
            import numpy as np
            CALLS = 0
            def design_grating(problem):
                global CALLS
                CALLS += 1
                marker = '/tmp/grating-world-seen'
                imported = getattr(np, '_grating_world_seen', 0)
                if CALLS != 1 or os.path.exists(marker) or imported:
                    return []
                with open(marker, 'w') as handle:
                    handle.write('seen')
                np._grating_world_seen = 1
                depth = min(problem['depth_bounds_um'][1],
                            0.11 * problem['period_um'])
                return [[depth, 0.5, 0.5]] * problem['layer_count']
        """
        result = self.evaluate_source(source)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_instance_call_count"], 6)

    def test_task_calibration_gate_executes(self):
        report = CALIBRATION.audit()
        self.assertTrue(report["execution_passed"], report)
        self.assertLess(
            report["frozen_anchor_recalculation"]["maximum_anchor_error"],
            1.0e-12,
        )
        self.assertLess(
            report["fourier_order_convergence"]["maximum_utility_delta"],
            0.004,
        )
        self.assertTrue(report["secure_baseline_exactly_matches_direct"])


if __name__ == "__main__":
    unittest.main()
