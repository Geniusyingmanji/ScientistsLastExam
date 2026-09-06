"""Invariants for AtmosphericChemistry/MethaneSourceAttribution.

The claim is that half the cases cannot be attributed, for two different reasons, and that a
searcher should say so. Three things must hold: the box model must close against the observed
atmosphere rather than be fitted to it, the sink/source confounding must be complete, and both
degenerate strategies must score zero.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "EarthScience" / "MethaneSourceAttribution"

# box.py, worlds.py and instruments.py are the readable statements of the model and import each
# other by name; the evaluator inlines them because the trusted driver loads it by path.
sys.path.insert(0, str(TASK / "verification"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("msa_evaluator", TASK / "verification" / "evaluator.py")
BOX = _load("msa_box", TASK / "verification" / "box.py")
WORLDS = _load("msa_worlds", TASK / "verification" / "worlds.py")
INSTRUMENTS = _load("msa_instruments", TASK / "verification" / "instruments.py")
BASELINE = _load("msa_baseline", TASK / "solution.py")
REFERENCE = _load("msa_reference", TASK / "verification" / "reference_attribution.py")


def _abstain_always(problem, measure):
    return {"abstain": True, "changed_sources": {}, "confidence": 0.0}


class ModelClosureTests(unittest.TestCase):
    def test_the_budget_closes_on_the_observed_atmosphere(self):
        """The atmospheric value is not an input; it falls out of the mix and the fractionation."""
        nominal = np.array([BOX.SOURCES[n]["nominal"] for n in BOX.SOURCE_ORDER])
        signatures = np.array([BOX.SOURCES[n]["signature"] for n in BOX.SOURCE_ORDER])
        weighted = float((nominal * signatures).sum() / nominal.sum())
        self.assertAlmostEqual(weighted + BOX.KIE_PERMIL, -47.2, delta=0.1)
        self.assertTrue(6.0 <= BOX.KIE_PERMIL <= 7.0,
                        "the effective total-sink fractionation must stay in the published band")

    def test_the_model_is_steady_when_nothing_changes(self):
        years = WORLDS.WINDOW_YEARS
        nominal = np.array([BOX.SOURCES[n]["nominal"] for n in BOX.SOURCE_ORDER])
        burden, delta = BOX.integrate(np.tile(nominal, (years, 1)), np.ones(years), years)
        self.assertLess(abs(burden[-1] - burden[0]), 5.0)
        self.assertLess(abs(delta[-1] - delta[0]), 0.05)

    def test_the_inlined_copies_agree_with_the_modules(self):
        self.assertEqual(list(EVALUATOR.SOURCE_ORDER), list(BOX.SOURCE_ORDER))
        self.assertEqual(EVALUATOR.KIE_PERMIL, BOX.KIE_PERMIL)
        self.assertEqual(dict(EVALUATOR.COSTS), dict(INSTRUMENTS.COSTS))
        mine = EVALUATOR.build(EVALUATOR.DEV_SEED, 8)
        theirs = WORLDS.build(EVALUATOR.DEV_SEED, 8)
        for left, right in zip(mine, theirs):
            self.assertEqual(left["case_id"], right["case_id"])
            self.assertEqual(left["regime"], right["regime"])
            self.assertEqual(left["changed"], right["changed"])


class ConfoundingTests(unittest.TestCase):
    def test_a_sink_only_change_still_raises_the_burden_and_lowers_d13c(self):
        """Which is what makes it look like a source: the direction is the same."""
        for case in WORLDS.build(EVALUATOR.DEV_SEED, 12):
            if case["regime"] != "sink_confounded":
                continue
            with self.subTest(case=case["case_id"]):
                self.assertEqual(case["changed"], frozenset())
                start = WORLDS.CHANGE_YEAR - 1
                self.assertGreater(case["burden"][-1] - case["burden"][start], 0.0)
                self.assertLess(case["delta"][-1] - case["delta"][start], 0.0)

    def test_the_sink_proxy_is_uninformative_exactly_where_it_matters(self):
        for case in WORLDS.build(EVALUATOR.DEV_SEED, 12):
            with self.subTest(case=case["case_id"], regime=case["regime"]):
                reading = INSTRUMENTS.Network(case, budget=99).measure("oh_proxy")
                if case["regime"] == "sink_confounded":
                    self.assertIsNone(reading["oh_change_fraction"])
                else:
                    self.assertIsNotNone(reading["oh_change_fraction"])

    def test_only_the_tracer_regime_raises_d13c(self):
        """Fossil and biomass burning are the only sources heavier than the emission-weighted mean."""
        start = WORLDS.CHANGE_YEAR - 1
        for case in WORLDS.build(EVALUATOR.DEV_SEED, 24):
            change = case["delta"][-1] - case["delta"][start]
            with self.subTest(case=case["case_id"], regime=case["regime"]):
                if case["regime"] == "tracer_identifiable":
                    self.assertGreater(change, 0.0)
                else:
                    self.assertLess(change, 0.0)

    def test_the_budget_cannot_buy_both_tracers_and_the_sink_proxy(self):
        costs = INSTRUMENTS.COSTS
        everything = costs["ethane"] + costs["radiocarbon"] + costs["oh_proxy"]
        self.assertGreater(everything, INSTRUMENTS.BUDGET,
                           "the allocation has to be a real choice")


class ContractTests(unittest.TestCase):
    def test_both_degenerate_strategies_score_zero_and_are_distinguishable(self):
        blanket = EVALUATOR.evaluate(_abstain_always)
        never = EVALUATOR.evaluate(BASELINE.attribute)
        self.assertEqual(blanket["combined_score"], 0.0)
        self.assertEqual(never["combined_score"], 0.0)
        self.assertEqual(blanket["discovery_coverage"], 0.0)
        self.assertEqual(never["discovery_coverage"], 1.0)
        self.assertEqual(blanket["correct_refusal_rate"], 1.0)
        self.assertEqual(never["correct_refusal_rate"], 0.0)

    def test_the_baseline_is_competent_where_isotopes_suffice_and_still_scores_zero(self):
        result = EVALUATOR.evaluate(BASELINE.attribute)
        by_regime = {}
        for row in result["per_case"]:
            hit, total = by_regime.get(row["regime"], (0, 0))
            by_regime[row["regime"]] = (hit + int(row["recovered"]), total + 1)
        hits, total = by_regime["tracer_identifiable"]
        self.assertEqual(hits, total, "isotopes alone should settle the tracer regime")
        self.assertEqual(result["combined_score"], 0.0)

    def test_the_baseline_walks_into_the_sink_trap(self):
        """A sink-only rise looks like a modest increase in a source lighter than the mean."""
        result = EVALUATOR.evaluate(BASELINE.attribute)
        named = [row for row in result["per_case"]
                 if row["regime"] == "sink_confounded" and row["claimed"]]
        self.assertGreater(len(named), len([r for r in result["per_case"]
                                            if r["regime"] == "sink_confounded"]) // 2,
                           "the trap should fire on most sink-only cases")

    def test_the_reference_beats_the_baseline_and_refuses_correctly(self):
        result = EVALUATOR.evaluate(REFERENCE.attribute)
        self.assertGreater(result["combined_score"], 0.4)
        self.assertGreater(result["correct_refusal_rate"], 0.8)
        self.assertLess(result["false_discovery_rate"], 0.2)

    def test_the_three_axes_are_reported_with_their_denominators(self):
        result = EVALUATOR.evaluate(REFERENCE.attribute)
        for axis in ("mechanism_score", "false_discovery_rate", "correct_refusal_rate"):
            self.assertIn(axis, result)
        for denominator in ("mechanism_score_denominator", "false_discovery_denominator",
                            "correct_refusal_denominator"):
            self.assertIn(denominator, result)
        self.assertIn("discovery_coverage", result)

    def test_malformed_and_useless_reports_are_different_states(self):
        malformed = EVALUATOR.evaluate(lambda p, m: None)
        useless = EVALUATOR.evaluate(_abstain_always)
        self.assertEqual(malformed["valid"], 0.0)
        self.assertEqual(useless["valid"], 1.0)
        self.assertEqual(malformed["combined_score"], useless["combined_score"])


class DegenerateSubmissionTests(unittest.TestCase):
    def test_degenerate_submissions_score_zero_without_raising(self):
        cases = {
            "none": lambda p, m: None,
            "empty": lambda p, m: {},
            "claim_everything": lambda p, m: {
                "abstain": False,
                "changed_sources": {n: True for n in p["source_catalogue"]}, "confidence": 1.0},
            "claim_nothing": lambda p, m: {
                "abstain": False,
                "changed_sources": {n: False for n in p["source_catalogue"]}, "confidence": 1.0},
            "guess_without_measuring": lambda p, m: {
                "abstain": False, "changed_sources": {"wetlands": True}, "confidence": 1.0},
            "abstain_not_bool": lambda p, m: {"abstain": 1, "changed_sources": {},
                                              "confidence": 0.5},
            "confidence_nan": lambda p, m: {"abstain": False, "changed_sources": {},
                                            "confidence": float("nan")},
            "confidence_out_of_range": lambda p, m: {"abstain": False, "changed_sources": {},
                                                     "confidence": 5.0},
            "unknown_source": lambda p, m: {"abstain": False,
                                            "changed_sources": {"unicorns": True},
                                            "confidence": 0.5},
            "flag_not_bool": lambda p, m: {"abstain": False, "changed_sources": {"fossil": 1},
                                           "confidence": 0.5},
            "raises": lambda p, m: (_ for _ in ()).throw(RuntimeError("boom")),
        }
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                self.assertEqual(EVALUATOR.evaluate(candidate)["combined_score"], 0.0)

    def test_the_budget_and_the_menu_are_enforced(self):
        def overspend(problem, measure):
            for _ in range(10):
                measure("oh_proxy")
            return {"abstain": True, "changed_sources": {}, "confidence": 0.0}

        def unknown(problem, measure):
            measure("psychic")
            return {"abstain": True, "changed_sources": {}, "confidence": 0.0}

        def sectorless(problem, measure):
            measure("inventory")
            return {"abstain": True, "changed_sources": {}, "confidence": 0.0}

        for name, candidate in (("overspend", overspend), ("unknown_measurement", unknown),
                                ("inventory_without_sector", sectorless)):
            with self.subTest(candidate=name):
                self.assertEqual(EVALUATOR.evaluate(candidate)["valid"], 0.0)
