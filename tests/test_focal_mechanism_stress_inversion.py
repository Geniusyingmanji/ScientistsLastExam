"""Pinned invariants for FocalMechanismStressInversion.

The tests pin the Aki-Richards geometry round trip, the Wallace-Bott construction,
the plane-order shuffle, budget semantics and the refusal-world separation.
"""

from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "EarthScience" / "FocalMechanismStressInversion"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FocalMechanismStressInversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "fms_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "fms_reference")
        cls.sol = _load(TASK / "solution.py", "fms_baseline")

    def test_plane_geometry_round_trip(self):
        rng = np.random.default_rng(5)
        for _ in range(60):
            strike = float(rng.uniform(0, 360))
            dip = float(rng.uniform(10, 85))
            rake = float(rng.uniform(-179, 179))
            tr, dp, lam = map(math.radians, (strike, dip, rake))
            normal = np.asarray((-math.sin(dp) * math.sin(tr),
                                 -math.sin(dp) * math.cos(tr), math.cos(dp)))
            slip = (math.cos(lam) * np.asarray((math.cos(tr), -math.sin(tr), 0.0))
                    + math.sin(lam) * np.asarray((math.cos(dp) * math.sin(tr),
                                                  math.cos(dp) * math.cos(tr),
                                                  math.sin(dp))))
            self.assertAlmostEqual(float(normal @ slip), 0.0, places=12)
            got_strike, got_dip, got_rake = self.ev._plane_from_normal_slip(normal, slip)
            self.assertAlmostEqual((got_strike - strike + 180) % 360 - 180, 0.0, places=6)
            self.assertAlmostEqual(got_dip, dip, places=6)
            self.assertAlmostEqual((got_rake - rake + 180) % 360 - 180, 0.0, places=6)

    def test_wallace_bott_slip_lies_along_shear(self):
        world = self.ev._world((33011, "supported"))
        tensor = world["tensor"]
        for normal, slip in world["events"]:
            traction = tensor @ normal
            shear = traction - (traction @ normal) * normal
            cosine = float(shear @ slip / np.linalg.norm(shear))
            self.assertAlmostEqual(abs(cosine), 1.0, places=10)

    def test_truth_submission_scores_one(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            if world["kind"] != "supported":
                continue
            def candidate(problem, reanalyze, budget, world=world):
                t1, p1 = self.ev._angles_from_axis(world["sigma1"])
                t3, p3 = self.ev._angles_from_axis(world["sigma3"])
                return {"sigma1": [t1, p1], "sigma3": [t3, p3], "R": world["ratio"],
                        "plane_assignments": list(world["assignments"]),
                        "abstain": False, "confidence": 0.9}
            row = self.ev._evaluate_world(candidate, spec, "dev", 0)
            self.assertTrue(row["valid"])
            self.assertGreater(row["mechanism_score"], 0.999)

    def test_baseline_and_reference_and_determinism(self):
        first = self.ev.evaluate(self.sol.infer_stress_orientation)
        second = self.ev.evaluate(self.sol.infer_stress_orientation)
        self.assertEqual(first["valid"], 1.0)
        self.assertLessEqual(abs(first["combined_score"]), 0.01)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))
        result = self.ev.evaluate(self.ref.infer_stress_orientation)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], 0.3)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)

    def test_reanalysis_is_charged_once_per_event(self):
        world = self.ev._world((33011, "supported"))
        observatory = self.ev._Observatory(world)
        observatory.reanalyze(0)
        with self.assertRaises(RuntimeError):
            observatory.reanalyze(0)
        self.assertTrue(observatory.violated)

    def test_plane_order_is_shuffled(self):
        # Roughly half the events list the true fault plane first; a fixed order
        # would leak the assignment.
        counts = []
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            if world["kind"] != "supported":
                continue
            counts.append(float(np.mean(world["assignments"])))
        self.assertGreater(np.mean(counts), 0.2)
        self.assertLess(np.mean(counts), 0.8)

    def test_refusal_worlds_separate_from_supported_misfits(self):
        # The converged misfit distribution must separate supported from mixed and
        # incoherent worlds (the gate calibration pin).
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            observatory = self.ev._Observatory(world)
            result = self.ref.infer_stress_orientation(
                self.ev.problem_statement(world), observatory.reanalyze,
                self.ev.REANALYSIS_BUDGET)
            if spec[1] == "supported":
                self.assertFalse(result["abstain"], spec)
            else:
                self.assertTrue(result["abstain"], spec)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "tensor"):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
