"""Discovery-contract pins for BlackBoxGroupIdentification.

The public score is mechanism, normalised so that declining every world with the better blanket
reason is exactly zero. A non-group and an unlisted group are the unsupported cases and their
reasons differ; a catalogue group is determinable and its name is the answer. This file also pins
what makes the catalogue fair: every construction is a group of the stated order, no two catalogue
entries of one order share the scoring invariants, and no outside-catalogue world shares them with
a catalogue entry - so "outside" is a determinable answer.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Mathematics/BlackBoxGroupIdentification"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BlackBoxGroupIdentificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "group_oracle")
        cls.baseline = _load(TASK / "solution.py", "group_baseline")
        cls.reference = _load(TASK / "verification/reference_partial_closure.py", "group_reference")

    def test_every_construction_is_a_group_with_unambiguous_invariants(self):
        ev = self.evaluator
        for order, entries in ev.CATALOGUE.items():
            seen = {}
            for name, _presentation, construction in entries:
                table = ev.build(construction)
                self.assertEqual(table.shape[0], order, name)
                self.assertTrue(ev.is_group(table), name)
                fp = ev.fingerprint(table)
                self.assertNotIn(fp, seen, "%s and %s share invariants" % (name, seen.get(fp)))
                seen[fp] = name
            for name, construction in ev.OUTSIDE[order]:
                table = ev.build(construction)
                self.assertEqual(table.shape[0], order, name)
                self.assertTrue(ev.is_group(table), name)
                self.assertNotIn(ev.fingerprint(table), seen, "outside group %s matches a catalogue entry" % name)

    def test_blanket_refusal_with_either_reason_scores_zero(self):
        for reason in self.evaluator.ABSTAIN_REASONS:
            metrics = self.evaluator.evaluate(lambda _p, _m, r=reason: {"abstain": True, "abstain_reason": r})
            self.assertEqual(metrics["valid"], 1.0, reason)
            self.assertEqual(metrics["combined_score"], 0.0, reason)
            self.assertEqual(metrics["development_correct_refusal_rate"], 1.0, reason)
            self.assertEqual(metrics["development_discovery_coverage"], 0.0, reason)

    def test_the_order_profile_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.identify)
        reference = self.evaluator.evaluate(self.reference.identify)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.0)
        self.assertLess(reference["combined_score"], 1.0)
        # The reference identifies the two-generated worlds, where the closure fits in the budget,
        # and loses the rest. Half is the designed level, not an accident.
        self.assertGreaterEqual(reference["development_identification_rate"], 0.5)
        self.assertLess(reference["development_false_discovery_rate"],
                        baseline["development_false_discovery_rate"])
        self.assertGreater(baseline["development_false_discovery_rate"], 0.5)

    def test_the_budget_cannot_pay_for_a_rank_three_reconstruction(self):
        """Closure over k generators costs k * order; the budget must sit between two and three."""
        multiplier = self.evaluator.BUDGET_MULTIPLIER
        self.assertGreater(multiplier, 2.0, "a two-generated world must stay reconstructible")
        self.assertLess(multiplier, 3.0, "a rank-three world must not be reconstructible")

    def test_rank_and_order_profile_do_not_separate_the_catalogue(self):
        """If they did, the centre would be optional and the last queries would not matter."""
        ev = self.evaluator
        collisions = 0
        for order, entries in ev.CATALOGUE.items():
            seen = {}
            for name, _presentation, construction in entries:
                table = ev.build(construction)
                key = (ev.fingerprint(table)[0], self._rank(ev, table))
                if key in seen:
                    collisions += 1
                seen[key] = name
        self.assertGreater(collisions, 0, "the catalogue no longer needs the centre to be read")

    @staticmethod
    def _rank(ev, table):
        import itertools
        n = table.shape[0]
        for k in range(1, 6):
            for combo in itertools.combinations(range(n), k):
                reached, frontier = {0}, [0]
                while frontier:
                    new = []
                    for x in frontier:
                        for g in combo:
                            y = int(table[g, x])
                            if y not in reached:
                                reached.add(y); new.append(y)
                    frontier = new
                if len(reached) == n:
                    return k
        return 99


if __name__ == "__main__":
    unittest.main()
