"""Discovery-contract pins for IsolationLevelAudit.

The public score is +1 for naming the store's isolation level, -1 for naming another and 0 for
declining, clipped below at zero, so declining every world is exactly 0.0 and every fixed guess is
worth less than that. The task only works if two things hold: no store ever exhibits an anomaly
class its level forbids, so that reading the evidence correctly never names a level below the
truth; and an anomaly needs two transactions on the store's weak path at once, so that the budget
buys opportunities rather than operations and a quiet probe can mean two different things.

These tests pin what the construction found the hard way: that declining everything and every
blind guess score zero, that the store is sound at every level, that a transaction on the lock
path is never interrupted (which is what makes the operation clocks a power measure at all), that
the budget fails closed, and that malformed candidates never raise out of the evaluator.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/IsolationLevelAudit"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IsolationLevelAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification/evaluator.py", "isolation_oracle")
        cls.ref = _load(TASK / "verification/reference_opportunity_audit.py", "isolation_reference")
        cls.specs = cls.ev.DEVELOPMENT_WORLDS + cls.ev.HELDOUT_WORLDS

    # ---- the scale -----------------------------------------------------------------------------
    def test_declining_everything_is_exactly_zero_in_both_forms(self):
        for submission in ({"abstain": True}, {"level": "unknown"}, {"level": None}):
            metrics = self.ev.evaluate(lambda _p, _r, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)
            self.assertEqual(metrics["development_refusal_rate"], 1.0, submission)
            self.assertEqual(metrics["development_raw_mechanism"], 0.0, submission)

    def test_every_fixed_guess_scores_zero_and_is_worse_than_declining(self):
        for level in self.ev.LEVELS:
            metrics = self.ev.evaluate(lambda _p, _r, lv=level: {"level": lv})
            self.assertEqual(metrics["valid"], 1.0, level)
            self.assertEqual(metrics["combined_score"], 0.0, level)
            self.assertLess(metrics["development_raw_mechanism"], 0.0, level)

    def test_the_worlds_cover_every_level_and_declare_their_weak_rate(self):
        self.assertEqual({w["level"] for w in self.specs}, set(self.ev.LEVELS))
        for w in self.specs:
            self.assertGreaterEqual(w["rate"], self.ev.MIN_WEAK_RATE, w["name"])
            self.assertLess(w["rate"], 1.0, w["name"])
        # the split of settled and starved worlds Task.md quotes
        self.assertEqual(sum(not w["settleable"] for w in self.ev.DEVELOPMENT_WORLDS), 6)
        self.assertEqual(sum(not w["settleable"] for w in self.ev.HELDOUT_WORLDS), 3)

    def test_every_level_has_a_settleable_development_world(self):
        """A searcher has to see what naming each of the six looks like with the evidence there."""
        settled = {w["level"] for w in self.ev.DEVELOPMENT_WORLDS if w["settleable"]}
        self.assertEqual(settled, set(self.ev.LEVELS))

    def test_no_starved_world_sits_at_either_end_of_the_ladder(self):
        """Strict serializable is what the verdict defaults to when nothing is witnessed, so a
        starved world there would pay a candidate that never declines exactly what it pays one that
        reasoned. Read uncommitted is the other end: a dirty write is the cheapest class to catch,
        and even at `min_weak_rate` the budget settles such a store about half the time, so there
        is no starved world to build there either."""
        for w in self.specs:
            if not w["settleable"]:
                self.assertNotIn(w["level"], ("strict_serializable", "read_uncommitted"), w["name"])

    # ---- the store -----------------------------------------------------------------------------
    def test_no_store_exhibits_a_class_its_level_forbids(self):
        for level in self.ev.LEVELS:
            bench = self.ev._Bench(level, 0.5, 5, budget=10 ** 6)
            run, key = bench.api(), 0
            for _ in range(40):
                for _name, pattern, _cost in self.ref.PATTERNS:
                    txns, _gave = pattern(run, key, key + 1)
                    key += 2
                    extra = set(self.ref.analyze(txns)) - self.ev.allowed(level)
                    self.assertFalse(extra, "%s exhibited %s" % (level, sorted(extra)))

    def test_interleaved_operations_prove_both_transactions_took_the_weak_path(self):
        """The reference reads its power off the operation clocks, and this is why it may."""
        store = self.ev.Store("read_committed", 0.5, 3)
        weak = {}
        begin = store._begin

        def record(session, ops, is_weak):
            txn = begin(session, ops, is_weak)
            weak[txn["tid"]] = bool(is_weak)
            return txn

        store._begin = record
        interleavings = 0
        for key in range(150):
            txns = store.run([[[["r", key], ["a", key], ["r", key]]],
                              [[["r", key], ["a", key], ["r", key]]]])
            for a in txns:
                for b in txns:
                    if a["tid"] == b["tid"]:
                        continue
                    if not any(a["at"][0] < x < a["at"][-1] for x in b["at"]):
                        continue
                    interleavings += 1
                    self.assertTrue(weak[a["tid"]] and weak[b["tid"]],
                                    "a transaction on the lock path was interrupted")
        self.assertGreater(interleavings, 0, "no interleaving was produced at all")

    def test_an_anomaly_needs_two_transactions_on_the_weak_path(self):
        """With the weak path switched off entirely the store is strictly serializable."""
        for level in self.ev.LEVELS:
            bench = self.ev._Bench(level, 0.0, 9, budget=10 ** 6)
            run, key, found = bench.api(), 0, set()
            for _ in range(30):
                for _name, pattern, _cost in self.ref.PATTERNS:
                    txns, _gave = pattern(run, key, key + 1)
                    key += 2
                    found |= set(self.ref.analyze(txns))
            self.assertFalse(found, "%s produced %s with no weak transactions" % (level, found))

    # ---- the contract --------------------------------------------------------------------------
    def test_the_budget_fails_closed_and_the_world_is_lost(self):
        def overrun(problem, run):
            while True:
                run([[[["r", 0], ["a", 0]]]])

        metrics = self.ev.evaluate(overrun)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.0)
        for row in metrics["per_instance"]:
            self.assertFalse(row["valid"])
            self.assertEqual(row["mechanism_score"], -1.0)
            self.assertLessEqual(row["ops_used"], self.ev.BUDGET)

    def test_malformed_candidates_score_the_world_and_never_raise(self):
        def batch_too_wide(_p, run):
            return run([[[["r", 0]]]] * (self.ev.MAX_SESSIONS + 1))

        def transaction_too_long(_p, run):
            return run([[[["r", 0]] * (self.ev.MAX_OPS + 1)]])

        def bad_operation(_p, run):
            return run([[[["x", 0]]]])

        def bad_key(_p, run):
            return run([[[["r", -1]]]])

        cases = [batch_too_wide, transaction_too_long, bad_operation, bad_key,
                 lambda _p, _r: {"level": "eventual"},
                 lambda _p, _r: {"level": "read_committed", "confidence": float("nan")},
                 lambda _p, _r: ["read_committed"],
                 lambda _p, _r: (_ for _ in ()).throw(ZeroDivisionError("boom"))]
        for candidate in cases:
            metrics = self.ev.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(not r["valid"] for r in metrics["per_instance"]))

    def test_the_same_candidate_scores_the_same_twice(self):
        first = self.ev.evaluate(self.ref.audit)
        second = self.ev.evaluate(self.ref.audit)
        self.assertEqual(first["combined_score"], second["combined_score"])
        self.assertEqual([r["said"] for r in first["per_instance"]],
                         [r["said"] for r in second["per_instance"]])

    def test_the_reference_beats_declining_and_names_no_world_wrongly(self):
        metrics = self.ev.evaluate(self.ref.audit)
        self.assertGreater(metrics["combined_score"], 0.4)
        self.assertLess(metrics["combined_score"], 1.0)
        self.assertEqual(metrics["development_misidentification_rate"], 0.0)
        self.assertEqual(metrics["heldout_misidentification_rate"], 0.0)
        self.assertGreater(metrics["development_refusal_rate"], 0.0)

    def test_the_discovery_axes_are_read_against_what_each_world_could_support(self):
        """Blanket abstention is perfect on false discovery and on refusal and discovers nothing."""
        decline = self.ev.evaluate(lambda _p, _r: {"abstain": True})
        self.assertEqual(decline["development_false_discovery_rate"], 0.0)
        self.assertEqual(decline["development_correct_refusal_rate"], 1.0)
        self.assertEqual(decline["development_discovery_coverage"], 0.0)
        self.assertEqual(decline["combined_score"], 0.0)

        guess = self.ev.evaluate(lambda _p, _r: {"level": "strict_serializable"})
        self.assertEqual(guess["development_correct_refusal_rate"], 0.0)
        self.assertEqual(guess["development_discovery_coverage"], 1.0)
        self.assertGreater(guess["development_false_discovery_rate"], 0.5)

    def test_every_published_axis_travels_with_the_count_it_is_a_rate_of(self):
        """A rate alone cannot be read: 1.0 is one world out of one or six out of six."""
        metrics = self.ev.evaluate(lambda _p, _r: {"abstain": True})
        for split, worlds in (("development", self.ev.DEVELOPMENT_WORLDS),
                              ("heldout", self.ev.HELDOUT_WORLDS)):
            starved = sum(not w["settleable"] for w in worlds)
            settled = sum(bool(w["settleable"]) for w in worlds)
            # Declining everything names nothing, so the false-discovery denominator is zero
            # claims; the other two are the worlds that could and could not be settled.
            self.assertEqual(metrics[split + "_false_discovery_denominator"], 0, split)
            self.assertEqual(metrics[split + "_correct_refusal_denominator"], starved, split)
            self.assertEqual(metrics[split + "_correct_refusal_count"], starved, split)
            self.assertEqual(metrics[split + "_discovery_denominator"], settled, split)
            self.assertEqual(metrics[split + "_discovery_count"], 0, split)
        named = self.ev.evaluate(lambda _p, _r: {"level": "strict_serializable"})
        for split, worlds in (("development", self.ev.DEVELOPMENT_WORLDS),
                              ("heldout", self.ev.HELDOUT_WORLDS)):
            # Naming every world makes every world a claim, and the wrong ones are the count.
            self.assertEqual(named[split + "_false_discovery_denominator"], len(worlds), split)
            self.assertEqual(
                named[split + "_false_discovery_count"],
                sum(w["level"] != "strict_serializable" for w in worlds), split)

    def test_the_reference_answer_carries_a_decision_a_probe_can_flip(self):
        """Both keys on every answer, so overriding the flag actually changes the submission.

        The repository audits a task by rerunning the reference with its abstention forced one way
        and then the other. That measures nothing if the reference signals a refusal by omitting
        the level and a claim by omitting the flag, because the override then lands on a key the
        evaluator was never going to read. Both branches carry both keys, and the two forced runs
        score below the reference on opposite sides: forcing refusal everywhere gives up every
        world it had settled, forcing a claim everywhere spends the refusals on wrong levels.
        """
        seen = []

        def watch(problem, run):
            answer = self.ref.audit(problem, run)
            seen.append(answer)
            return answer

        reference = self.ev.evaluate(watch)
        self.assertEqual(len(seen), len(self.specs))
        for answer in seen:
            self.assertIsInstance(answer.get("abstain"), bool)
            self.assertIn(answer.get("level"), self.ev.LEVELS)
        self.assertTrue(any(a["abstain"] for a in seen))
        self.assertTrue(any(not a["abstain"] for a in seen))

        def forced(flag):
            return self.ev.evaluate(
                lambda p, r: dict(self.ref.audit(p, r), abstain=flag))

        refuse_all, claim_all = forced(True), forced(False)
        self.assertEqual(refuse_all["combined_score"], 0.0)
        self.assertEqual(refuse_all["development_refusal_rate"], 1.0)
        self.assertLess(claim_all["combined_score"], reference["combined_score"])
        self.assertEqual(claim_all["development_refusal_rate"], 0.0)
        self.assertGreater(claim_all["development_misidentification_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
