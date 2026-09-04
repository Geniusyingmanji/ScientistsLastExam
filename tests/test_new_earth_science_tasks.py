from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

from sle.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
EARTH = ROOT / "benchmarks" / "EarthScience"
TASKS = {
    "WavePropagation/ActiveFullWaveformInversion":
        ("ActiveFullWaveformInversion", "invert_velocity_model", "discovery"),
    "Paleoclimate/ChronologyAssimilation":
        ("ChronologyAssimilation", "reconstruct_climate", "discovery"),
    "Volcanology/DeformationMechanismInference":
        ("DeformationMechanismInference", "infer_deformation_source", "discovery"),
    "Hydrology/GroundwaterRemediationDesign":
        ("GroundwaterRemediationDesign", "design_remediation", "optimization"),
    "Cryosphere/IceObservationNetworkDesign":
        ("IceObservationNetworkDesign", "design_ice_observation_network", "optimization"),
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class NewEarthSciencePackageTests(unittest.TestCase):
    def test_inventory_has_three_discovery_and_two_optimization_tasks(self):
        roles = []
        for task_id, (_, _, role) in TASKS.items():
            spec = find_task(task_id, include_uncertified=True)
            self.assertEqual(spec.discipline, "EarthScience")
            self.assertEqual(spec.metadata["scientific_role"], role)
            roles.append(role)
        self.assertEqual(roles.count("discovery"), 3)
        self.assertEqual(roles.count("optimization"), 2)

    def test_baselines_are_valid_zero_and_deterministic(self):
        for task_id, (directory, entrypoint, _) in TASKS.items():
            evaluator = _load(EARTH / directory / "verification" / "evaluator.py",
                              "new_earth_evaluator_" + directory)
            baseline = _load(EARTH / directory / "solution.py",
                             "new_earth_baseline_" + directory)
            first = evaluator.evaluate(getattr(baseline, entrypoint))
            second = evaluator.evaluate(getattr(baseline, entrypoint))
            self.assertEqual(first["valid"], 1.0, task_id)
            self.assertLessEqual(abs(first["combined_score"]), 0.01, task_id)
            self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                             json.dumps(second, sort_keys=True, default=str), task_id)

    def test_truth_blind_references_leave_measurable_headroom(self):
        for task_id, (directory, entrypoint, _) in TASKS.items():
            evaluator = _load(EARTH / directory / "verification" / "evaluator.py",
                              "new_earth_reference_evaluator_" + directory)
            reference = _load(EARTH / directory / "verification" / "reference_solver.py",
                              "new_earth_reference_" + directory)
            result = evaluator.evaluate(getattr(reference, entrypoint))
            self.assertEqual(result["valid"], 1.0, task_id)
            self.assertGreater(result["combined_score"], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing_evaluator(self):
        def raises(*args, **kwargs):
            del args, kwargs
            raise RuntimeError("candidate failure")

        def empty(*args, **kwargs):
            del args, kwargs
            return {}

        def wrong_type(*args, **kwargs):
            del args, kwargs
            return "not a scientific artifact"

        for task_id, (directory, _, _) in TASKS.items():
            evaluator = _load(EARTH / directory / "verification" / "evaluator.py",
                              "new_earth_bad_candidate_" + directory)
            for candidate in (raises, empty, wrong_type):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0, task_id)
                self.assertEqual(result["combined_score"], 0.0, task_id)


class NewEarthScienceInvariantTests(unittest.TestCase):
    def test_fwi_exact_model_has_unit_structure_and_waveform_scores(self):
        evaluator = _load(EARTH / "ActiveFullWaveformInversion" / "verification" / "evaluator.py",
                          "new_earth_fwi_invariant")
        world = evaluator._world(evaluator.DEVELOPMENT_SPECS[0])
        model, waveform, mechanism = evaluator._supported_scores(world, world["velocity"])
        self.assertAlmostEqual(model, 1.0, places=10)
        self.assertAlmostEqual(waveform, 1.0, places=10)
        self.assertAlmostEqual(mechanism, 1.0, places=10)

    def test_groundwater_reference_beats_baseline_and_is_shift_feasible(self):
        evaluator = _load(EARTH / "GroundwaterRemediationDesign" / "verification" / "evaluator.py",
                          "new_earth_groundwater_invariant")
        for spec in evaluator.DEVELOPMENT_SPECS:
            problem = evaluator._public_problem(spec)
            baseline, _ = evaluator._hypervolume(problem, evaluator._baseline_archive(problem))
            reference, _ = evaluator._hypervolume(problem, evaluator._reference_archive(problem))
            self.assertGreater(reference, baseline)
            for shift in evaluator.SHIFTS:
                shifted, _ = evaluator._hypervolume(problem, evaluator._reference_archive(problem), shift)
                self.assertGreater(shifted, 0.0)

    def test_ice_additional_observation_reduces_public_posterior_trace(self):
        evaluator = _load(EARTH / "IceObservationNetworkDesign" / "verification" / "evaluator.py",
                          "new_earth_ice_invariant")
        world = evaluator._world(evaluator.DEVELOPMENT_SEEDS[0])
        first = evaluator._plan_metrics(world, np.asarray((0, 1, 2)))
        second = evaluator._plan_metrics(world, np.asarray((0, 1, 2, 3)))
        self.assertLessEqual(second["posterior_trace"], first["posterior_trace"] + 1e-9)

    def test_paleoclimate_crps_is_finite_and_sharp_at_truth(self):
        evaluator = _load(EARTH / "ChronologyAssimilation" / "verification" / "evaluator.py",
                          "new_earth_paleoclimate_invariant")
        truth = np.asarray((-1.0, 0.0, 1.0))
        sharp = evaluator._crps_normal(truth, np.full(3, 0.1), truth)
        broad = evaluator._crps_normal(truth, np.full(3, 1.0), truth)
        self.assertTrue(np.all(np.isfinite(sharp)))
        self.assertTrue(np.all(sharp < broad))

    def test_volcano_mogi_translation_is_equivariant(self):
        evaluator = _load(EARTH / "DeformationMechanismInference" / "verification" / "evaluator.py",
                          "new_earth_volcano_invariant")
        parameters = np.asarray((200.0, -300.0, 1800.0, 4.0e8, 1200.0))
        stations = np.asarray(((-1000.0, 200.0), (700.0, 1300.0)))
        shift = np.asarray((350.0, -120.0))
        original = evaluator.forward_displacement("mogi", parameters, stations)
        moved = parameters.copy()
        moved[:2] += shift
        translated = evaluator.forward_displacement("mogi", moved, stations + shift)
        np.testing.assert_allclose(original, translated, rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
