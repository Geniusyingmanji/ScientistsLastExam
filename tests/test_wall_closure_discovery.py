"""Invariants for Turbulence/WallClosureDiscovery.

The claim is that two thirds of the cases cannot be answered, for two different reasons, and that a
searcher should say so. Three things have to hold for that to be honest: the solver must be the
physics it says it is, the two refusal reasons must actually be different tests, and both degenerate
strategies must score zero.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest

import numpy as np

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Engineering" / "WallClosureDiscovery"

# channel.py, grammar.py and worlds.py are the readable statements of the model and import each
# other by name; the evaluator inlines them because the trusted driver loads it by path.
sys.path.insert(0, str(TASK / "verification"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("wcd_evaluator", TASK / "verification" / "evaluator.py")
CHANNEL = _load("wcd_channel", TASK / "verification" / "channel.py")
GRAMMAR = _load("wcd_grammar", TASK / "verification" / "grammar.py")
WORLDS = _load("wcd_worlds", TASK / "verification" / "worlds.py")
BASELINE = _load("wcd_baseline", TASK / "solution.py")
REFERENCE = _load("wcd_reference", TASK / "verification" / "reference_analysis.py")

VAN_DRIEST = ["mul", ["const", 41, 100],
              ["mul", ["var", "y"],
               ["sub", ["const", 1, 1],
                ["exp", ["neg", ["div", ["var", "y"], ["const", 26, 1]]]]]]]


def _abstain_always(problem, observe):
    return {"abstain": True, "mixing_length": None, "confidence": 0.0}


class SolverTests(unittest.TestCase):
    def test_the_solver_recovers_the_constants_it_was_given(self):
        """Validates the quadrature, not the physics - the task card says so."""
        for re_tau in (1000.0, 2000.0, 5200.0):
            with self.subTest(re_tau=re_tau):
                y, u = CHANNEL.velocity_profile(CHANNEL.van_driest(0.41, 26.0), re_tau)
                window = (y > 50) & (y < 0.15 * re_tau)
                slope, intercept = np.polyfit(np.log(y[window]), u[window], 1)
                self.assertAlmostEqual(1.0 / slope, 0.41, delta=0.02)
                self.assertTrue(5.0 < intercept < 6.0, intercept)

    def test_the_viscous_sublayer_is_linear(self):
        y, u = CHANNEL.velocity_profile(CHANNEL.van_driest(), 5200.0)
        index = int(np.argmin(np.abs(y - 1.0)))
        self.assertAlmostEqual(u[index], y[index], delta=0.05)

    def test_the_grammar_reproduces_the_closure_it_encodes(self):
        closure = GRAMMAR.compile_closure(VAN_DRIEST)
        for re_tau in (1000.0, 5200.0):
            with self.subTest(re_tau=re_tau):
                _y, mine = CHANNEL.velocity_profile(closure, re_tau)
                _y2, theirs = CHANNEL.velocity_profile(CHANNEL.van_driest(0.41, 26.0), re_tau)
                self.assertLess(float(np.max(np.abs(mine - theirs))), 1e-12)
        self.assertEqual(GRAMMAR.count_nodes(VAN_DRIEST), 11)

    def test_the_inlined_copies_agree_with_the_modules(self):
        self.assertEqual(EVALUATOR.count_nodes(VAN_DRIEST), GRAMMAR.count_nodes(VAN_DRIEST))
        mine = EVALUATOR.build(EVALUATOR.DEV_SEED, 6)
        theirs = WORLDS.build(EVALUATOR.DEV_SEED, 6)
        for left, right in zip(mine, theirs):
            self.assertEqual(left["case_id"], right["case_id"])
            self.assertEqual(left["regime"], right["regime"])
            self.assertEqual(left["sampled_re"], right["sampled_re"])


class ContractTests(unittest.TestCase):
    def test_both_degenerate_strategies_score_zero_and_are_distinguishable(self):
        blanket = EVALUATOR.evaluate(_abstain_always)
        never = EVALUATOR.evaluate(BASELINE.build_closure)
        self.assertEqual(blanket["combined_score"], 0.0)
        self.assertEqual(never["combined_score"], 0.0)
        self.assertEqual(blanket["discovery_coverage"], 0.0)
        self.assertEqual(never["discovery_coverage"], 1.0)
        self.assertEqual(blanket["correct_refusal_rate"], 1.0)
        self.assertEqual(never["correct_refusal_rate"], 0.0)

    def test_the_baseline_recovers_the_law_and_still_scores_zero(self):
        """The fitting is not the hard part; not knowing when to stop is."""
        result = EVALUATOR.evaluate(BASELINE.build_closure)
        self.assertEqual(result["mechanism_score"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_submitting_the_textbook_closure_blindly_scores_zero_despite_recovering(self):
        """Recall buys a recovery number that looks good alone and is worth nothing with refusal."""
        def recall(problem, observe):
            return {"abstain": False, "mixing_length": VAN_DRIEST, "confidence": 1.0}
        result = EVALUATOR.evaluate(recall)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["correct_refusal_rate"], 0.0)
        # The hidden constants are drawn near the published ones, so a blind submission does land
        # some cases. That is the point: a good mechanism score is not a score.
        self.assertGreater(result["mechanism_score"], 0.5)
        self.assertGreater(result["false_discovery_rate"], 0.2)

    def test_the_reference_beats_both(self):
        result = EVALUATOR.evaluate(REFERENCE.build_closure)
        self.assertGreater(result["combined_score"], 0.3)
        self.assertGreater(result["mechanism_score"], 0.5)
        self.assertGreater(result["correct_refusal_rate"], 0.5)

    def test_the_three_axes_are_reported_with_their_denominators(self):
        result = EVALUATOR.evaluate(REFERENCE.build_closure)
        for axis in ("mechanism_score", "false_discovery_rate", "correct_refusal_rate"):
            self.assertIn(axis, result)
        for denominator in ("mechanism_score_denominator", "false_discovery_denominator",
                            "correct_refusal_denominator"):
            self.assertIn(denominator, result)
        self.assertIn("discovery_coverage", result)

    def test_malformed_and_useless_reports_are_different_states(self):
        malformed = EVALUATOR.evaluate(lambda p, o: None)
        useless = EVALUATOR.evaluate(_abstain_always)
        self.assertEqual(malformed["valid"], 0.0)
        self.assertEqual(useless["valid"], 1.0)
        self.assertEqual(malformed["combined_score"], useless["combined_score"])


class RefusalTests(unittest.TestCase):
    def test_degenerate_cases_fit_better_than_answerable_ones(self):
        """The trap: the unanswerable regime has the *lowest* residuals."""
        residuals = {}
        def probe(problem, observe):
            readings = [observe(re) for re in problem["sampled_re_tau"]]
            best = min(REFERENCE._chi_square(k, a, readings)[0]
                       for k in np.linspace(0.34, 0.50, 12)
                       for a in np.linspace(18.0, 36.0, 12))
            points = REFERENCE._chi_square(0.41, 26.0, readings)[1]
            residuals[problem["case_id"]] = best / points
            return {"abstain": True, "mixing_length": None, "confidence": 0.0}
        EVALUATOR.evaluate(probe)
        regimes = {c["case_id"]: c["regime"]
                   for c in WORLDS.build(EVALUATOR.DEV_SEED, EVALUATOR.CASE_COUNT)}
        degenerate = [v for k, v in residuals.items()
                      if regimes[k] == "degenerate_parameters"]
        inconsistent = [v for k, v in residuals.items() if regimes[k] == "inconsistent"]
        self.assertLess(max(degenerate), min(inconsistent),
                        "the residual test must not separate the degenerate regime")

    def test_ignoring_the_nuisances_moves_the_fit_and_projecting_them_out_does_not(self):
        """The systematics have nowhere to go except into the parameter being estimated.

        Asserted as "the naive fit moves and the projected one does not", rather than as a
        direction: the sign depends on the case, and the first version of this test pinned the
        upward direction measured on the narrow span across three profiles and then checked a
        single profile, where it does not hold.
        """
        truth = WORLDS.damped_mixing_length(0.41, 26.0)
        readings = []
        for re_tau in WORLDS.NARROW_RE:
            y, u = CHANNEL.velocity_profile(truth, re_tau)
            corrupted = np.interp(np.clip(y + 0.8, 0.0, None), y, u) * 1.02
            readings.append({"y_plus": y, "u_plus": corrupted,
                             "re_tau": re_tau, "noise_sigma": 0.011 * u[-1]})

        def naive_error(kappa):
            total = 0.0
            for reading in readings:
                y = np.asarray(reading["y_plus"])
                predicted = CHANNEL.velocity_profile(
                    WORLDS.damped_mixing_length(kappa, 26.0), reading["re_tau"])[1]
                total += float(np.sum((predicted - np.asarray(reading["u_plus"])) ** 2))
            return total

        grid = np.linspace(0.34, 0.60, 40)
        naive = grid[int(np.argmin([naive_error(k) for k in grid]))]
        projected = grid[int(np.argmin(
            [REFERENCE._chi_square(k, 26.0, readings)[0] for k in grid]))]
        self.assertLess(abs(projected - 0.41), abs(naive - 0.41),
                        "projecting the nuisances out should get closer to the truth")


class DegenerateSubmissionTests(unittest.TestCase):
    def test_degenerate_submissions_score_zero_without_raising(self):
        cases = {
            "none": lambda p, o: None,
            "empty": lambda p, o: {},
            "abstain_not_bool": lambda p, o: {"abstain": 1, "mixing_length": VAN_DRIEST,
                                              "confidence": 0.5},
            "confidence_nan": lambda p, o: {"abstain": False, "mixing_length": VAN_DRIEST,
                                            "confidence": float("nan")},
            "confidence_out_of_range": lambda p, o: {"abstain": False,
                                                     "mixing_length": VAN_DRIEST,
                                                     "confidence": 9.0},
            "no_formula": lambda p, o: {"abstain": False, "mixing_length": None,
                                        "confidence": 0.5},
            "unknown_operator": lambda p, o: {"abstain": False,
                                              "mixing_length": ["frobnicate", ["var", "y"]],
                                              "confidence": 0.5},
            "unknown_variable": lambda p, o: {"abstain": False, "mixing_length": ["var", "z"],
                                              "confidence": 0.5},
            "float_constant": lambda p, o: {"abstain": False,
                                            "mixing_length": ["const", 0.5, 1],
                                            "confidence": 0.5},
            "zero_denominator": lambda p, o: {"abstain": False, "mixing_length": ["const", 1, 0],
                                              "confidence": 0.5},
            "negative_closure": lambda p, o: {"abstain": False, "mixing_length": ["const", -1, 1],
                                              "confidence": 0.5},
            "raises": lambda p, o: (_ for _ in ()).throw(RuntimeError("boom")),
        }
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["combined_score"], 0.0)

    def test_the_budget_and_the_sampled_set_are_enforced(self):
        def flood(problem, observe):
            for _ in range(80):
                observe(problem["sampled_re_tau"][0])
            return {"abstain": True, "mixing_length": None, "confidence": 0.0}
        def unsampled(problem, observe):
            observe(99999.0)
            return {"abstain": True, "mixing_length": None, "confidence": 0.0}
        for name, candidate in (("flood", flood), ("unsampled_re", unsampled)):
            with self.subTest(candidate=name):
                self.assertEqual(EVALUATOR.evaluate(candidate)["valid"], 0.0)

    def test_an_over_cap_expression_is_refused(self):
        expression = ["var", "y"]
        for _ in range(60):
            expression = ["mul", expression, ["const", 1, 1]]
        result = EVALUATOR.evaluate(
            lambda p, o: {"abstain": False, "mixing_length": expression, "confidence": 0.5})
        self.assertEqual(result["valid"], 0.0)
