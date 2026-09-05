"""Pinned invariants for ThermochemicalCycleAudit.

The tests pin the construction errors in the task's known_best.md: least-squares
smearing of a giant slip into a fake class drift, the truncated corrected-enthalpy
artifact, the relative recovery gate, and replicate/cross-check error semantics.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Chemistry" / "ThermochemicalCycleAudit"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ThermochemicalCycleAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "tca_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "tca_reference")
        cls.sol = _load(TASK / "solution.py", "tca_baseline")

    def test_closure_holds_exactly_on_the_noise_free_network(self):
        stoichiometry = np.asarray([row[0] for row in self.ev.REACTIONS], dtype=float)
        rng = np.random.default_rng(4)
        for _ in range(8):
            enthalpies = rng.uniform(-250, 150, size=7)
            values = stoichiometry @ enthalpies
            residual = values - stoichiometry @ np.linalg.lstsq(
                stoichiometry, values, rcond=None)[0]
            self.assertAlmostEqual(float(np.abs(residual).max()), 0.0, places=6)

    def test_truth_informed_auditor_scores_one(self):
        def perfect(world):
            def candidate(problem, replicate, cross_check, budget):
                kind = world["kind"]
                truth = world["truth"]
                corrected = {name: float(value) for name, value
                             in zip(self.ev.MEASUREMENT_IDS, truth)}
                if kind == "clean":
                    return {"verdict": "consistent", "flagged_measurements": [],
                            "drift_instrument": "", "corrected_enthalpies": corrected,
                            "confidence": 0.9}
                if kind == "drift":
                    return {"verdict": "instrument_drift",
                            "flagged_measurements": [
                                self.ev.MEASUREMENT_IDS[i]
                                for i in world["corruption"]["indices"]],
                            "drift_instrument": world["corruption"]["instrument"],
                            "corrected_enthalpies": corrected, "confidence": 0.9}
                if kind == "underdetermined":
                    return {"verdict": "underdetermined", "flagged_measurements": [],
                            "drift_instrument": "",
                            "corrected_enthalpies": corrected, "confidence": 0.9}
                return {"verdict": "single_fault",
                        "flagged_measurements": [
                            self.ev.MEASUREMENT_IDS[i]
                            for i in world["corruption"]["indices"]],
                        "drift_instrument": "",
                        "corrected_enthalpies": corrected, "confidence": 0.9}
            return candidate

        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            row = self.ev._evaluate_world(perfect(world), spec, "dev", 0)
            self.assertTrue(row["valid"], spec)
            self.assertAlmostEqual(row["mechanism_score"], 1.0, places=3, msg=spec)

    def test_baseline_and_reference_and_determinism(self):
        first = self.ev.evaluate(self.sol.audit_thermochemical_cycle)
        second = self.ev.evaluate(self.sol.audit_thermochemical_cycle)
        self.assertEqual(first["valid"], 1.0)
        self.assertLessEqual(abs(first["combined_score"]), 0.01)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))
        result = self.ev.evaluate(self.ref.audit_thermochemical_cycle)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], 0.3)
        self.assertEqual(result["development_verdict_score"], 1.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)

    def test_replicates_shrink_random_error_but_not_systematics(self):
        world = self.ev._world((71023, "drift"))
        lab = self.ev._Laboratory(world)
        drifted = [i for i, name in enumerate(world["instruments"])
                   if name == world["corruption"]["instrument"]][0]
        clean = next(i for i, name in enumerate(world["instruments"])
                     if name != world["corruption"]["instrument"])
        clean_errors, drifted_errors = [], []
        for _ in range(3):  # repeated contracts inside one budget draw fresh noise
            r_clean = lab.replicate(self.ev.MEASUREMENT_IDS[clean])
            clean_errors.append(abs(r_clean["value_kj_per_mol"] - world["truth"][clean]))
            r_drift = lab.replicate(self.ev.MEASUREMENT_IDS[drifted])
            drifted_errors.append(abs(r_drift["value_kj_per_mol"] - world["truth"][drifted]))
        self.assertLess(np.mean(clean_errors), world["sigmas"][clean])
        # The systematic offset persists across replicates of the drifted instrument.
        self.assertGreater(np.mean(drifted_errors),
                           0.5 * abs(world["corruption"]["offset"]))

    def test_cross_check_exposes_drift(self):
        world = self.ev._world((71023, "drift"))
        lab = self.ev._Laboratory(world)
        drifted = [i for i, name in enumerate(world["instruments"])
                   if name == world["corruption"]["instrument"]][0]
        report = lab.cross_check(self.ev.MEASUREMENT_IDS[drifted])
        self.assertGreater(abs(report["value_kj_per_mol"] - world["values"][drifted]),
                          1.5 * abs(world["corruption"]["offset"]) / 2)

    def test_pendant_pair_shares_one_instrument(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            self.assertEqual(world["instruments"][11], world["instruments"][12])

    def test_corrected_enthalpies_cover_every_measurement(self):
        # Pins the truncated-artifact bug: drop-and-refit corrections must still be
        # reported for all thirteen determinations.
        world = self.ev._world((71031, "transcription"))
        lab = self.ev._Laboratory(world)
        out = self.ref.audit_thermochemical_cycle(
            self.ev.problem_statement(world), lab.replicate, lab.cross_check, 6)
        self.assertEqual(set(out["corrected_enthalpies"]), set(self.ev.MEASUREMENT_IDS))

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "audit"):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
