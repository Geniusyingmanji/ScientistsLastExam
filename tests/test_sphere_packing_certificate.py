"""Invariants for DiscreteGeometry/SpherePackingCertificate.

The task's claim is that a submitted number is a proof of a packing bound, so the tests are about
soundness. A bound below what a known lattice actually achieves is the failure that would matter,
and the grid linear program produces exactly that, which is why it is pinned here as a negative
control rather than only described in prose.
"""
from __future__ import annotations

import importlib.util
import math
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Mathematics" / "SpherePackingCertificate"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("sphere_evaluator", TASK / "verification" / "evaluator.py")
ALGEBRA = _load("sphere_algebra", TASK / "verification" / "lp_algebra.py")
BASELINE = _load("sphere_baseline", TASK / "solution.py")

ONE = [[1, 1]]


def _two_term(instance):
    return BASELINE.build_certificate(instance)


class AlgebraTests(unittest.TestCase):
    def test_laguerre_matches_scipy(self):
        from scipy.special import genlaguerre
        for dimension in (4, 8, 12, 13):
            alpha = Fraction(dimension, 2) - 1
            for order in range(6):
                with self.subTest(dimension=dimension, order=order):
                    mine = [float(v) for v in ALGEBRA.laguerre(order, alpha)]
                    theirs = list(genlaguerre(order, float(alpha)).coefficients)[::-1]
                    for a, b in zip(mine, theirs):
                        self.assertAlmostEqual(a, b, places=9)

    def test_the_inlined_copy_agrees_with_the_module(self):
        # The evaluator inlines these because the trusted driver loads it by path.
        for order in range(5):
            for dimension in (8, 13):
                alpha = Fraction(dimension, 2) - 1
                self.assertEqual(EVALUATOR.laguerre(order, alpha),
                                 ALGEBRA.laguerre(order, alpha))

    def test_shift_is_exact(self):
        poly = [Fraction(1), Fraction(-2), Fraction(3)]
        for offset in (Fraction(0), Fraction(3), Fraction(-5, 2)):
            shifted = ALGEBRA.poly_shift(poly, offset)
            for point in (Fraction(0), Fraction(1), Fraction(7, 3)):
                self.assertEqual(ALGEBRA.poly_eval(shifted, point),
                                 ALGEBRA.poly_eval(poly, point + offset))

    def test_half_line_certificate_is_sound_and_complete_on_known_cases(self):
        one = [Fraction(1)]
        self.assertTrue(ALGEBRA.nonnegative_on_half_line(
            [Fraction(1), Fraction(-2), Fraction(1)], [(Fraction(1), [Fraction(-1), Fraction(1)])], []))
        self.assertTrue(ALGEBRA.nonnegative_on_half_line(
            [Fraction(0), Fraction(1)], [], [(Fraction(1), one)]))
        # w - 1 is negative near zero; no certificate of this shape reconstructs it.
        self.assertFalse(ALGEBRA.nonnegative_on_half_line(
            [Fraction(-1), Fraction(1)], [(Fraction(1), one)], []))


class BaselineTests(unittest.TestCase):
    def test_the_two_term_bound_matches_its_closed_form(self):
        result = EVALUATOR.evaluate(_two_term)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["feasibility_rate"], 1.0)
        for row in result["per_instance"]:
            with self.subTest(dimension=row["dimension"]):
                n = row["dimension"]
                closed = ((n + 2) / (2.0 * math.pi)) ** (n / 2.0) * (n + 2) / 2.0 ** (n + 1)
                self.assertAlmostEqual(row["certified_bound"], closed, places=9)

    def test_the_baseline_is_exactly_the_zero_of_the_scale(self):
        self.assertEqual(EVALUATOR.evaluate(_two_term)["combined_score"], 0.0)

    def test_every_baseline_bound_is_above_the_best_packing_known(self):
        for row in EVALUATOR.evaluate(_two_term)["per_instance"]:
            with self.subTest(dimension=row["dimension"]):
                self.assertGreater(row["certified_bound"], row["best_packing_known"])
                self.assertFalse(row["below_best_packing_known"])


class SoundnessTests(unittest.TestCase):
    def test_a_bound_below_an_exhibited_packing_is_flagged_not_rewarded(self):
        # This is the shape the grid linear program produces: 0.06237 in dimension 8, below the
        # 0.0625 that E8 achieves. It must never be scored.
        instance = [i for i in EVALUATOR.INSTANCES if i["dimension"] == 8][0]
        score, flagged = EVALUATOR._instance_score(instance, 0.06237)
        self.assertEqual(score, 0.0)
        self.assertTrue(flagged)

    def test_floats_are_rejected_rather_than_rounded(self):
        for value in (0.5, [0.5, 1], [1, 0.5], float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                EVALUATOR._fraction(value)

    def test_a_certificate_that_does_not_reconstruct_its_target_is_refused(self):
        def wrong(instance):
            good = _two_term(instance)
            good["transform_nonnegative"] = {"sigma0": [{"weight": [1, 1], "poly": ONE}],
                                             "sigma1": []}
            return good
        result = EVALUATOR.evaluate(wrong)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["valid"], 0.0)

    def test_negative_weights_cannot_forge_non_negativity(self):
        def forged(instance):
            good = _two_term(instance)
            good["transform_nonnegative"]["sigma0"][0]["weight"] = [-2, 1]
            return good
        self.assertEqual(EVALUATOR.evaluate(forged)["valid"], 0.0)


class ScoringTests(unittest.TestCase):
    def test_the_two_term_bound_scores_zero_and_the_published_bound_scores_one(self):
        for instance in EVALUATOR.INSTANCES:
            with self.subTest(dimension=instance["dimension"]):
                easy, _ = EVALUATOR._instance_score(
                    instance, EVALUATOR.trivial_bound(instance["dimension"]))
                target, _ = EVALUATOR._instance_score(instance, instance["cohn_elkies"])
                self.assertAlmostEqual(easy, 0.0, places=9)
                self.assertAlmostEqual(target, 1.0, places=9)

    def test_a_tighter_bound_always_scores_higher(self):
        instance = [i for i in EVALUATOR.INSTANCES if i["dimension"] == 12][0]
        ladder = [0.209, 0.18, 0.15, 0.10, 0.0628]
        scores = [EVALUATOR._instance_score(instance, b)[0] for b in ladder]
        self.assertEqual(scores, sorted(scores))

    def test_the_scale_is_uncapped(self):
        instance = [i for i in EVALUATOR.INSTANCES if i["dimension"] == 12][0]
        beyond, flagged = EVALUATOR._instance_score(instance, 0.05)
        self.assertGreater(beyond, 1.0)
        self.assertFalse(flagged)


class DegenerateSubmissionTests(unittest.TestCase):
    def test_degenerate_submissions_score_zero_without_raising(self):
        cases = {
            "empty": lambda i: {},
            "none": lambda i: None,
            "float_coefficients": lambda i: dict(_two_term(i), coefficients=[0.5, 1.0]),
            "negative_threshold": lambda i: dict(_two_term(i), threshold=[-5, 1]),
            "zero_threshold": lambda i: dict(_two_term(i), threshold=[0, 1]),
            "zero_denominator": lambda i: dict(_two_term(i), threshold=[1, 0]),
            "no_coefficients": lambda i: dict(_two_term(i), coefficients=[]),
            "huge_rational": lambda i: dict(_two_term(i), coefficients=[[10 ** 5000, 1], [1, 1]]),
            "over_degree_cap": lambda i: dict(_two_term(i), coefficients=[[1, 1]] * 200),
            "boolean": lambda i: dict(_two_term(i), threshold=True),
            "missing_tail": lambda i: {k: v for k, v in _two_term(i).items()
                                       if k != "tail_nonpositive"},
            "raises": lambda i: (_ for _ in ()).throw(RuntimeError("boom")),
        }
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["combined_score"], 0.0)
                self.assertEqual(result["valid"], 0.0)
