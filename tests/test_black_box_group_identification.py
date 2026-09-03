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
        cls.reference = _load(TASK / "verification/reference_cayley_closure.py", "group_reference")

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
        self.assertGreater(reference["combined_score"], 0.5)
        self.assertLess(reference["combined_score"], 1.0)
        self.assertEqual(reference["development_identification_rate"], 1.0)
        # The reference keeps one designed error (an unlisted group named after a catalogue entry
        # with the same order profile and centre), so its false-discovery rate is small, not zero.
        self.assertLess(reference["development_false_discovery_rate"],
                        baseline["development_false_discovery_rate"])
        self.assertGreater(baseline["development_false_discovery_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
