"""Invariants for QuantumFoundations/BellBoundCertificate.

The claim this task makes is unusually strong - a submitted number is a *proof* - so the tests are
about soundness rather than about scores. If the oracle can be talked into certifying a bound that
is not true, the task is worse than useless, because it would report a false result confidently.
"""
from __future__ import annotations

import importlib.util
import itertools
import math
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "BellBoundCertificate"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("bell_evaluator", TASK / "verification" / "evaluator.py")
ALGEBRA = _load("bell_algebra", TASK / "verification" / "algebra.py")
REFERENCE = _load("bell_reference", TASK / "verification" / "reference_certificate.py")
BASELINE = _load("bell_baseline", TASK / "solution.py")


def _words(settings):
    return ([[[], []]]
            + [[[x], []] for x in range(settings[0])]
            + [[[], [y]] for y in range(settings[1])])


class TranscriptionTests(unittest.TestCase):
    """The functional is quoted from a paper whose wording does not match its own numbers."""

    def test_i3322_classical_bound_is_zero(self):
        # arXiv:2607.14755 states the classical bound is 0. Read as +-1 correlators its eq. (18)
        # gives 8; the stored form is the Collins-Gisin conversion, and this is what proves it.
        best = -math.inf
        for a in itertools.product((1, -1), repeat=3):
            for b in itertools.product((1, -1), repeat=3):
                total = -4
                for (left, right), coefficient in EVALUATOR.I3322_TIMES_FOUR.items():
                    value = 1
                    for x in left:
                        value *= a[x]
                    for y in right:
                        value *= b[y]
                    total += coefficient * value
                best = max(best, total / 4)
        self.assertEqual(best, 0.0)

    def test_chsh_classical_bound_is_two(self):
        best = -math.inf
        for a in itertools.product((1, -1), repeat=2):
            for b in itertools.product((1, -1), repeat=2):
                total = sum(coefficient * a[left[0]] * b[right[0]]
                            for (left, right), coefficient in EVALUATOR.CHSH.items())
                best = max(best, total)
        self.assertEqual(best, 2.0)

    def test_the_three_copies_of_the_algebra_agree(self):
        # The evaluator and the reference each inline these rules because both are loaded by path
        # and the reference also runs inside the sandbox, where a sibling import fails.
        for letters in itertools.product(range(3), repeat=4):
            self.assertEqual(EVALUATOR.reduce_side(letters), ALGEBRA.reduce_side(letters))
            self.assertEqual(REFERENCE.reduce_side(letters), ALGEBRA.reduce_side(letters))
        for u in (((0,), ()), ((), (1,)), ((0, 1), (2,)), ((), ())):
            for v in (((0,), ()), ((1,), (1,)), ((), ()), ((2,), (0, 1))):
                self.assertEqual(EVALUATOR.multiply(u, v), ALGEBRA.multiply(u, v))
                self.assertEqual(REFERENCE.multiply(u, v), ALGEBRA.multiply(u, v))


class SoundnessTests(unittest.TestCase):
    """Every bound the oracle certifies must be above a value that is actually achievable."""

    TWO_QUBIT_I3322 = 0.25
    CHSH_TSIRELSON = 2.0 * math.sqrt(2.0)

    def test_baseline_certificates_are_above_the_achievable_value(self):
        result = EVALUATOR.evaluate(BASELINE.build_certificate)
        for row in result["per_instance"]:
            self.assertTrue(row["valid"], row)
            floor = self.CHSH_TSIRELSON if row["name"] == "chsh" else self.TWO_QUBIT_I3322
            self.assertGreaterEqual(row["certified_bound"], floor - 1e-12, row["name"])

    def test_the_identity_coefficient_cannot_be_driven_negative(self):
        # beta is the coefficient of the identity, which collects exactly the diagonal cells, so it
        # is sum_k w_k * |v_k|^2 with every w_k >= 0. There is no submission that makes it negative,
        # which is what stops a certificate from claiming an arbitrarily strong bound.
        instance = EVALUATOR.INSTANCES[0]
        basis = [(( ), ()), ((0,), ()), ((), (0,))]
        weights = [Fraction(3), Fraction(1, 7)]
        vectors = [[Fraction(-5), Fraction(2), Fraction(-9)],
                   [Fraction(11), Fraction(-3), Fraction(4)]]
        beta = sum(w * sum(v * v for v in vec) for w, vec in zip(weights, vectors))
        self.assertGreater(beta, 0)
        with self.assertRaises(ValueError):
            # It is not a certificate for this functional, and it fails on the identity rather than
            # being scored with a negative bound.
            EVALUATOR.certified_bound(basis, weights, vectors, instance)


class ContractTests(unittest.TestCase):
    def test_baseline_is_valid_and_scores_exactly_zero(self):
        result = EVALUATOR.evaluate(BASELINE.build_certificate)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["feasibility_rate"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_floats_are_rejected_rather_than_rounded(self):
        # Load-bearing: accepting floats would make this "call an SDP solver".
        for value in (0.5, [0.5, 1], [1, 0.5], float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                EVALUATOR._fraction(value)

    def test_degenerate_submissions_score_zero_without_raising(self):
        settings = EVALUATOR.INSTANCES[0]["settings"]
        size = 1 + settings[0] + settings[1]
        cases = {
            "empty": lambda i: {},
            "none": lambda i: None,
            "no_basis": lambda i: {"basis": [], "squares": [{"weight": [1, 1], "vector": []}]},
            "no_squares": lambda i: {"basis": _words(i["settings"]), "squares": []},
            "negative_weight": lambda i: {
                "basis": _words(i["settings"]),
                "squares": [{"weight": [-1, 1], "vector": [[1, 1]] * size}]},
            "zero_vector": lambda i: {
                "basis": _words(i["settings"]),
                "squares": [{"weight": [1, 1], "vector": [[0, 1]] * size}]},
            "unreduced_word": lambda i: {
                "basis": [[[0, 0], []]], "squares": [{"weight": [1, 1], "vector": [[1, 1]]}]},
            "duplicate_words": lambda i: {
                "basis": [[[], []], [[], []]],
                "squares": [{"weight": [1, 1], "vector": [[1, 1], [1, 1]]}]},
            "over_budget": lambda i: {
                "basis": _words(i["settings"]) * 40,
                "squares": [{"weight": [1, 1], "vector": [[1, 1]] * (size * 40)}]},
            "huge_rational": lambda i: {
                "basis": _words(i["settings"]),
                "squares": [{"weight": [10 ** 5000, 1], "vector": [[1, 1]] * size}]},
            "zero_denominator": lambda i: {
                "basis": _words(i["settings"]),
                "squares": [{"weight": [1, 0], "vector": [[1, 1]] * size}]},
            "boolean": lambda i: {
                "basis": _words(i["settings"]),
                "squares": [{"weight": True, "vector": [[1, 1]] * size}]},
            "raises": lambda i: (_ for _ in ()).throw(RuntimeError("boom")),
        }
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["combined_score"], 0.0)
                self.assertEqual(result["valid"], 0.0)


class ScoringTests(unittest.TestCase):
    def test_the_free_bound_scores_zero_and_the_published_target_scores_one(self):
        for instance in EVALUATOR.INSTANCES:
            with self.subTest(instance=instance["name"]):
                free, _ = EVALUATOR._instance_score(instance, instance["easy_bound"])
                target, _ = EVALUATOR._instance_score(instance, instance["target_bound"])
                self.assertAlmostEqual(free, 0.0, places=9)
                self.assertAlmostEqual(target, 1.0, places=9)

    def test_a_tighter_bound_always_scores_higher(self):
        instance = [i for i in EVALUATOR.INSTANCES if i["name"] == "i3322_k24"][0]
        ladder = [0.375, 0.30, 0.2757, 0.2515, 0.25102173, 0.2509]
        scores = [EVALUATOR._instance_score(instance, b)[0] for b in ladder]
        self.assertEqual(scores, sorted(scores))

    def test_the_scale_is_uncapped(self):
        instance = [i for i in EVALUATOR.INSTANCES if i["name"] == "i3322_k40"][0]
        beyond, _ = EVALUATOR._instance_score(instance, 0.2509)
        self.assertGreater(beyond, 1.0)

    def test_a_bound_below_the_published_quantum_value_is_flagged_not_rewarded(self):
        instance = [i for i in EVALUATOR.INSTANCES if i["name"] == "i3322_k24"][0]
        score, flagged = EVALUATOR._instance_score(instance, 0.24)
        self.assertEqual(score, 0.0)
        self.assertTrue(flagged)
