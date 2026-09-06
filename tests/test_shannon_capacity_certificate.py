"""ShannonCapacityCertificate: both sides of the interval are proofs, and the free set is worth zero.

The expensive part of this task is finding a code, and the reference takes minutes, so nothing here
runs it. What is tested instead is everything the score rests on: the two copies of the rules agree,
the shipped free sets are genuinely independent and land exactly on the declared zero, the scale is
0 at the free bound and 1 at the published target and uncapped above, the exact rational upper side
reproduces a closed form it never names, and no degenerate submission can score or crash.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
import unittest
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/ShannonCapacityCertificate"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVAL = _load("shannon_eval", TASK / "verification" / "evaluator.py")
GRAPHS = _load("shannon_graphs", TASK / "verification" / "graphs.py")
REFERENCE = _load("shannon_reference", TASK / "verification" / "reference_certificate.py")
BASELINE = _load("shannon_baseline", TASK / "solution.py")
FREE = json.loads((TASK / "references" / "free_sets.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _theta_certificate(cycle):
    """Memoised: the bisection is 80 exact positive-definiteness tests, and the tests reuse it."""
    return REFERENCE.theta_certificate(cycle)


def _upper(cycle):
    matrix, bound = _theta_certificate(cycle)
    return {"matrix": [[[e.numerator, e.denominator] for e in row] for row in matrix],
            "bound": [bound.numerator, bound.denominator]}


class RuleTests(unittest.TestCase):
    def test_the_two_copies_of_the_rules_agree(self):
        # The evaluator inlines graphs.py because the trusted driver loads it by path, so the two
        # can drift. Nothing else would notice.
        for cycle in (7, 13, 19, 23):
            for i in range(cycle):
                for j in range(cycle):
                    self.assertEqual(EVAL.cycle_adjacent(cycle, i, j),
                                     GRAPHS.cycle_adjacent(cycle, i, j), (cycle, i, j))
        for cycle, power in ((7, 3), (13, 2)):
            self.assertEqual(sorted(EVAL.strong_power_shifts(cycle, power)),
                             sorted(GRAPHS.strong_power_shifts(cycle, power)))

    def test_a_shift_by_one_in_every_coordinate_is_adjacent(self):
        for cycle, power in ((7, 5), (13, 4), (19, 3), (23, 3)):
            zero = tuple([0] * power)
            one = tuple([1] * power)
            self.assertIsNotNone(EVAL.independence_failure(cycle, power, [zero, one]))

    def test_a_shift_by_two_in_one_coordinate_is_not_adjacent(self):
        for cycle, power in ((7, 5), (13, 4), (19, 3), (23, 3)):
            zero = tuple([0] * power)
            far = tuple([2] + [1] * (power - 1))
            self.assertIsNone(EVAL.independence_failure(cycle, power, [zero, far]))


class CyclicCodeTests(unittest.TestCase):
    def test_the_vectorised_code_agrees_with_a_plain_loop(self):
        # reference_certificate.cyclic_code is vectorised because the sweep is dominated by building
        # these. The claim that it returns the same set is checked here rather than asserted.
        def loop(cycle, power, modulus, multiplier):
            powers = [1] * power
            for i in range(1, power):
                powers[i] = (powers[i - 1] * multiplier) % modulus
            weights = [cycle ** i for i in range(power)]
            return {sum(((cycle * ((t * powers[i]) % modulus)) // modulus) * weights[i]
                        for i in range(power))
                    for t in range(modulus)}

        for cycle, power, modulus, multiplier in (
                (7, 5, 382, 7), (7, 5, 371, 11), (13, 3, 245, 19),
                (19, 3, 807, 19), (23, 3, 1433, 436)):
            with self.subTest(cycle=cycle, modulus=modulus, multiplier=multiplier):
                self.assertEqual(
                    REFERENCE.cyclic_code(cycle, power, modulus, multiplier),
                    loop(cycle, power, modulus, multiplier))

    def test_the_published_c7_parameters_are_inside_the_swept_window(self):
        # The sweep must be able to find (382, 7) without being told; if the window ever stops
        # containing it, the reference silently gets worse.
        low, high = REFERENCE.PLANS["C7"]["window"]
        self.assertTrue(low <= 382 < high)

    def test_every_window_brackets_the_published_target(self):
        for instance in EVAL.INSTANCES:
            plan = REFERENCE.PLANS[instance["name"]]
            low, high = plan["window"]
            target = instance["target_bound"] ** plan["power"]
            with self.subTest(instance=instance["name"]):
                self.assertLess(low, target)
                self.assertLess(target - low, 2.0 * (high - low))


class FreeSetTests(unittest.TestCase):
    def test_every_shipped_free_set_is_independent(self):
        for name, entry in FREE["witnesses"].items():
            with self.subTest(instance=name):
                words = [tuple(w) for w in entry["vertices"]]
                self.assertEqual(len(set(words)), len(words))
                self.assertIsNone(
                    EVAL.independence_failure(entry["cycle"], entry["power"], words))

    def test_every_shipped_free_set_lands_on_the_declared_zero(self):
        # The free bound is a witness, not a citation: if these two ever disagree, the zero of the
        # scale is a number nobody can exhibit.
        for instance in EVAL.INSTANCES:
            entry = FREE["witnesses"][instance["name"]]
            with self.subTest(instance=instance["name"]):
                bound = len(entry["vertices"]) ** (1.0 / entry["power"])
                self.assertAlmostEqual(bound, instance["free_bound"], places=12)

    def test_the_c7_free_set_matches_the_published_power_four_value(self):
        entry = FREE["witnesses"]["C7"]
        self.assertEqual(entry["power"], 4)
        self.assertEqual(len(entry["vertices"]), 108)

    def test_the_two_coordinate_free_sets_match_the_classical_value(self):
        for name in ("C13", "C19", "C23"):
            entry = FREE["witnesses"][name]
            cycle = entry["cycle"]
            with self.subTest(instance=name):
                self.assertEqual(len(entry["vertices"]), (cycle * (cycle - 1)) // 4)

    def test_submitting_the_free_set_scores_exactly_zero(self):
        def candidate(instance):
            entry = FREE["witnesses"][instance["name"]]
            return {"lower_certificates": [{"power": entry["power"],
                                            "vertices": entry["vertices"]}],
                    "upper_certificate": _upper(instance["cycle"])}

        metrics = EVAL.evaluate(candidate)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        for row in metrics["per_instance"]:
            with self.subTest(instance=row["name"]):
                # A hair below zero before clipping: the rational upper bound is about 1.5e-6 above
                # theta, and theta is where the scale's zero is measured from.
                self.assertEqual(row["instance_score"], 0.0)
                self.assertFalse(row["beats_the_free_bound"])
        self.assertEqual(metrics["combined_score"], 0.0)


class ScaleTests(unittest.TestCase):
    def test_the_free_bound_scores_zero_and_the_published_target_scores_one(self):
        for instance in EVAL.INSTANCES:
            with self.subTest(instance=instance["name"]):
                theta = instance["theta"]
                self.assertAlmostEqual(
                    EVAL._instance_score(instance, instance["free_bound"], theta), 0.0, places=12)
                self.assertAlmostEqual(
                    EVAL._instance_score(instance, instance["target_bound"], theta), 1.0, places=12)

    def test_the_scale_is_uncapped(self):
        for instance in EVAL.INSTANCES:
            beyond = instance["target_bound"] + (instance["theta"] - instance["target_bound"]) / 2
            with self.subTest(instance=instance["name"]):
                self.assertGreater(
                    EVAL._instance_score(instance, beyond, instance["theta"]), 1.0)

    def test_a_larger_code_always_scores_at_least_as_high(self):
        for instance in EVAL.INSTANCES:
            theta = instance["theta"]
            previous = -1.0
            for step in range(21):
                lower = instance["free_bound"] + step * (theta - instance["free_bound"]) / 20.0
                score = EVAL._instance_score(instance, lower, theta)
                self.assertGreaterEqual(score, previous, instance["name"])
                previous = score

    def test_a_looser_upper_bound_costs_score(self):
        for instance in EVAL.INSTANCES:
            tight = EVAL._instance_score(instance, instance["target_bound"], instance["theta"])
            loose = EVAL._instance_score(instance, instance["target_bound"],
                                         instance["theta"] + 0.01)
            with self.subTest(instance=instance["name"]):
                self.assertLess(loose, tight)

    def test_nothing_scores_below_zero(self):
        for instance in EVAL.INSTANCES:
            with self.subTest(instance=instance["name"]):
                self.assertEqual(EVAL._instance_score(instance, 1.0, instance["theta"] + 10.0), 0.0)


class UpperCertificateTests(unittest.TestCase):
    def test_the_rational_certificate_reproduces_the_closed_form(self):
        # theta(C_n) = n cos(pi/n) / (1 + cos(pi/n)) is never named by the reference: it bisects the
        # one free variable of the circulant matrix. Agreement is the check that both are right.
        for cycle in (7, 13, 19, 23):
            _matrix, bound = _theta_certificate(cycle)
            angle = math.cos(math.pi / cycle)
            closed = cycle * angle / (1.0 + angle)
            with self.subTest(cycle=cycle):
                self.assertGreater(float(bound), closed)
                self.assertLess(float(bound) - closed, 1e-5)

    def test_a_bound_below_theta_is_refused(self):
        for cycle in (7, 13, 19, 23):
            matrix, _bound = _theta_certificate(cycle)
            angle = math.cos(math.pi / cycle)
            below = Fraction(math.floor((cycle * angle / (1.0 + angle) - 1e-3) * 10 ** 6), 10 ** 6)
            with self.subTest(cycle=cycle):
                with self.assertRaises(ValueError):
                    EVAL._read_upper(
                        {"matrix": [[[e.numerator, e.denominator] for e in row] for row in matrix],
                         "bound": [below.numerator, below.denominator]},
                        {"cycle": cycle})

    def test_floats_are_rejected_rather_than_rounded(self):
        with self.assertRaises(ValueError):
            EVAL._fraction(3.3176672)

    def test_a_relaxed_forced_entry_is_refused(self):
        cycle = 7
        matrix, bound = _theta_certificate(cycle)
        raw = [[[e.numerator, e.denominator] for e in row] for row in matrix]
        raw[0][3] = [0, 1]
        raw[3][0] = [0, 1]
        with self.assertRaises(ValueError):
            EVAL._read_upper({"matrix": raw, "bound": [bound.numerator, bound.denominator]},
                             {"cycle": cycle})


class BaselineTests(unittest.TestCase):
    def test_baseline_is_valid_and_scores_exactly_zero(self):
        metrics = EVAL.evaluate(BASELINE.build_certificate)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        for row in metrics["per_instance"]:
            self.assertTrue(row["valid"], row.get("reason"))
            self.assertEqual(row["instance_score"], 0.0)

    def test_the_baseline_interval_is_correct_but_enormous(self):
        metrics = EVAL.evaluate(BASELINE.build_certificate)
        for row in metrics["per_instance"]:
            with self.subTest(instance=row["name"]):
                self.assertEqual(row["certified_lower_bound"], row["cycle"] // 2)
                self.assertGreater(row["certified_upper_bound"], row["cycle"])
                self.assertGreater(row["certified_interval_width"], 1.0)


class DegenerateSubmissionTests(unittest.TestCase):
    def _good(self, instance):
        entry = FREE["witnesses"][instance["name"]]
        return {"lower_certificates": [{"power": entry["power"], "vertices": entry["vertices"]}],
                "upper_certificate": _upper(instance["cycle"])}

    def test_degenerate_submissions_score_zero_without_raising(self):
        def with_lower(fn):
            def candidate(instance):
                out = self._good(instance)
                out["lower_certificates"] = fn(instance)
                return out
            return candidate

        cases = {
            "raises": lambda instance: (_ for _ in ()).throw(RuntimeError("boom")),
            "returns_a_string": lambda instance: "3.2578",
            "returns_none": lambda instance: None,
            "empty_mapping": lambda instance: {},
            "adjacent_codewords": with_lower(
                lambda i: [{"power": 2, "vertices": [[0, 0], [1, 1]]}]),
            "duplicate_codewords": with_lower(
                lambda i: [{"power": 2, "vertices": [[0, 0], [0, 0]]}]),
            "coordinate_outside_the_cycle": with_lower(
                lambda i: [{"power": 1, "vertices": [[i["cycle"]]]}]),
            "power_above_the_cap": with_lower(
                lambda i: [{"power": i["max_power"] + 1,
                            "vertices": [[0] * (i["max_power"] + 1)]}]),
            "power_zero": with_lower(lambda i: [{"power": 0, "vertices": [[]]}]),
            "empty_vertices": with_lower(lambda i: [{"power": 2, "vertices": []}]),
            "wrong_codeword_length": with_lower(
                lambda i: [{"power": 3, "vertices": [[0, 0]]}]),
            "every_vertex_at_power_one": with_lower(
                lambda i: [{"power": 1, "vertices": [[v] for v in range(i["cycle"])]}]),
            "too_many_codes": with_lower(
                lambda i: [{"power": 1, "vertices": [[0]]}]
                * (EVAL.MAX_LOWER_CERTIFICATES + 1)),
        }
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                metrics = EVAL.evaluate(candidate)
                self.assertEqual(metrics["combined_score"], 0.0)
                self.assertEqual(metrics["valid"], 0.0)

    def test_a_gigantic_rational_is_refused_before_any_arithmetic(self):
        # The size cap is what keeps exact elimination bounded; without it a well-formed submission
        # could hold the grader.
        with self.assertRaises(ValueError):
            EVAL._fraction([10 ** 4000 + 1, 3 * 10 ** 3999 + 7])

    def test_a_missing_upper_certificate_scores_zero(self):
        metrics = EVAL.evaluate(
            lambda instance: {"lower_certificates":
                              [{"power": 1, "vertices": [[0]]}]})
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["valid"], 0.0)


class CostTests(unittest.TestCase):
    def test_verifying_the_largest_legal_code_is_fast(self):
        # |S| * 3^k membership tests, with |S| and k both capped. This is the bound the card claims.
        cycle, power = 7, 5
        rng_free = FREE["witnesses"]["C7"]["vertices"]
        words = [tuple(w + [0]) for w in rng_free]
        start = time.time()
        EVAL.independence_failure(cycle, power, words)
        self.assertLess(time.time() - start, 5.0)


if __name__ == "__main__":
    unittest.main()
