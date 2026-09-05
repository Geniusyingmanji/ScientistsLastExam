"""Invariants for Exoplanets/TransmissionSpectrumSpecies.

The claim this task makes is that three quarters of its systems cannot be decided, and that a
searcher should say so. Two things have to hold for that to be honest: the unidentifiable regimes
must really be unidentifiable at the stated budget, and both degenerate strategies - abstain on
everything, abstain on nothing - must score zero. Those are what the tests are about.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "TransmissionSpectrumSpecies"


# world.py and systems.py are the readable statements of the model and import each other by name.
# The evaluator does not: it inlines both, because the trusted driver loads it by path and a sibling
# import fails there. Loading the readable copies here needs their own directory on the path.
sys.path.insert(0, str(TASK / "verification"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("tss_evaluator", TASK / "verification" / "evaluator.py")
WORLD = _load("tss_world", TASK / "verification" / "world.py")
SYSTEMS = _load("tss_systems", TASK / "verification" / "systems.py")
BASELINE = _load("tss_baseline", TASK / "solution.py")
REFERENCE = _load("tss_reference", TASK / "verification" / "reference_analysis.py")


def _abstain_always(problem, observe):
    return {"abstain": True, "species": {}, "confidence": 0.0}


class WorldTests(unittest.TestCase):
    def test_the_inlined_world_agrees_with_the_module(self):
        # The evaluator inlines these because the trusted driver loads it by path.
        self.assertEqual(list(EVALUATOR.SPECIES_ORDER), list(WORLD.SPECIES_ORDER))
        self.assertEqual(set(EVALUATOR.CONFUSABLE), set(WORLD.CONFUSABLE))
        np.testing.assert_allclose(EVALUATOR.cross_sections(), WORLD.cross_sections())
        mine = EVALUATOR.build(EVALUATOR.DEV_SEED, 8)
        theirs = SYSTEMS.build(EVALUATOR.DEV_SEED, 8)
        for left, right in zip(mine, theirs):
            self.assertEqual(left["system_id"], right["system_id"])
            self.assertEqual(left["regime"], right["regime"])
            self.assertEqual(left["present"], right["present"])

    def test_the_unidentifiable_regimes_cannot_reach_unit_signal_to_noise(self):
        """The whole budget on the best band still does not see the species."""
        points = WORLD.WAVELENGTHS.size / (len(WORLD.BAND_EDGES) - 1)
        blank = np.zeros(len(WORLD.SPECIES_ORDER))
        for system in EVALUATOR.build(EVALUATOR.DEV_SEED, EVALUATOR.SYSTEM_COUNT):
            signal = WORLD.spectrum(system["abundances"], system["grey"], system["rayleigh"],
                                    system["depth"], system["scale"])
            flat = WORLD.spectrum(blank, system["grey"], system["rayleigh"],
                                  system["depth"], system["scale"])
            best = system["noise_per_transit"] / np.sqrt(EVALUATOR.BUDGET_TRANSITS * points)
            ratio = float(np.max(np.abs(signal - flat))) / best
            with self.subTest(system=system["system_id"], regime=system["regime"]):
                if system["regime"] in ("muted", "sparse"):
                    self.assertLess(ratio, 1.0)
                else:
                    self.assertGreater(ratio, 10.0)

    def test_the_confusable_pair_is_inseparable_not_merely_hard(self):
        edges, grid = WORLD.BAND_EDGES, WORLD.WAVELENGTHS
        sections = WORLD.cross_sections()
        rows = [sections[:, (grid >= edges[i]) & (grid < edges[i + 1])].mean(axis=1)
                for i in range(len(edges) - 1)
                if ((grid >= edges[i]) & (grid < edges[i + 1])).any()]
        design = np.column_stack([np.asarray(rows), np.ones(len(rows))])
        covariance = np.linalg.inv(design.T @ design)
        errors = np.sqrt(np.diag(covariance))
        a, b = (list(WORLD.SPECIES_ORDER).index(n) for n in sorted(WORLD.CONFUSABLE))
        correlation = covariance[a, b] / (errors[a] * errors[b])
        self.assertLess(correlation, -0.99)
        inflation = 1.0 / np.sqrt(max(1e-12, 1.0 - correlation ** 2))
        self.assertGreater(inflation, 15.0)

    def test_no_other_pair_is_degenerate(self):
        sections = WORLD.cross_sections()
        names = list(WORLD.SPECIES_ORDER)
        for i, left in enumerate(names):
            for j, right in enumerate(names):
                if j <= i or {left, right} == set(WORLD.CONFUSABLE):
                    continue
                with self.subTest(pair=(left, right)):
                    self.assertLess(abs(np.corrcoef(sections[i], sections[j])[0, 1]), 0.85)


class DeterminismTests(unittest.TestCase):
    def test_the_noise_seed_does_not_depend_on_python_hash_randomisation(self):
        # The bug this pins: seeding from hash() of the system id made the same reference score
        # 0.4231 in one interpreter and 0.2092 in the next.
        source = (TASK / "verification" / "evaluator.py").read_text(encoding="utf-8")
        self.assertNotIn("hash(system", source)
        self.assertIn("crc32", source)

    def test_two_evaluations_agree_exactly(self):
        first = EVALUATOR.evaluate(REFERENCE.analyze)
        second = EVALUATOR.evaluate(REFERENCE.analyze)
        self.assertEqual(first["combined_score"], second["combined_score"])
        self.assertEqual(first["mechanism_recovery"], second["mechanism_recovery"])
        self.assertEqual(first["correct_refusal_rate"], second["correct_refusal_rate"])


class ContractTests(unittest.TestCase):
    def test_the_three_axes_are_reported_with_their_denominators(self):
        result = EVALUATOR.evaluate(REFERENCE.analyze)
        for axis in ("mechanism_recovery", "false_discovery_rate", "correct_refusal_rate"):
            self.assertIn(axis, result)
            self.assertIn(axis.replace("_rate", "") + "_denominator", result)
        self.assertIn("attempted_rate", result)

    def test_both_degenerate_strategies_score_zero_and_are_distinguishable(self):
        blanket = EVALUATOR.evaluate(_abstain_always)
        never = EVALUATOR.evaluate(BASELINE.analyze)
        self.assertEqual(blanket["combined_score"], 0.0)
        self.assertEqual(never["combined_score"], 0.0)
        # Same score, opposite failure - the report has to tell them apart.
        self.assertEqual(blanket["attempted_rate"], 0.0)
        self.assertEqual(never["attempted_rate"], 1.0)
        self.assertEqual(blanket["correct_refusal_rate"], 1.0)
        self.assertEqual(never["correct_refusal_rate"], 0.0)

    def test_the_reference_beats_both(self):
        reference = EVALUATOR.evaluate(REFERENCE.analyze)
        self.assertGreater(reference["combined_score"], 0.0)
        self.assertGreater(reference["mechanism_recovery"], 0.0)
        self.assertGreater(reference["correct_refusal_rate"], 0.0)

    def test_naming_either_confusable_member_is_a_false_discovery(self):
        def name_one(problem, observe):
            pick = sorted(problem["known_confusable_group"])[0]
            return {"abstain": False, "species": {pick: True}, "confidence": 1.0}
        result = EVALUATOR.evaluate(name_one)
        self.assertGreater(result["false_discovery_rate"], 0.0)

    def test_malformed_and_useless_reports_are_different_states(self):
        malformed = EVALUATOR.evaluate(lambda p, o: None)
        useless = EVALUATOR.evaluate(_abstain_always)
        self.assertEqual(malformed["valid"], 0.0)
        self.assertEqual(useless["valid"], 1.0)
        self.assertEqual(malformed["combined_score"], useless["combined_score"])


class BudgetTests(unittest.TestCase):
    def test_overspending_the_budget_is_refused(self):
        def greedy(problem, observe):
            bands = len(problem["band_edges_um"]) - 1
            observe([problem["budget_transits"]] * bands)
            return {"abstain": True, "species": {}, "confidence": 0.0}
        self.assertEqual(EVALUATOR.evaluate(greedy)["valid"], 0.0)

    def test_negative_and_non_integer_counts_are_refused(self):
        for bad in (-3, 1.5, True):
            with self.subTest(value=bad):
                def submit(problem, observe, bad=bad):
                    bands = len(problem["band_edges_um"]) - 1
                    observe([bad] + [0] * (bands - 1))
                    return {"abstain": True, "species": {}, "confidence": 0.0}
                self.assertEqual(EVALUATOR.evaluate(submit)["valid"], 0.0)

    def test_a_band_with_no_transits_returns_nothing(self):
        seen = {}
        def submit(problem, observe):
            bands = len(problem["band_edges_um"]) - 1
            reading = observe([problem["budget_transits"]] + [0] * (bands - 1))
            seen["bands"] = reading["bands"]
            return {"abstain": True, "species": {}, "confidence": 0.0}
        EVALUATOR.evaluate(submit)
        self.assertIsNotNone(seen["bands"][0]["depth"])
        self.assertIsNone(seen["bands"][1]["depth"])
