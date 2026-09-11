"""Discovery-contract pins for JuntaVariableDiscovery.

The public score is mechanism, normalised so that declining every world is exactly zero and so is
naming variables everywhere. A world that is a parity of more than the published junta size is the
unsupported case: declining it is correct, declining everything is not. In a world that is a junta
the answer is the set of variables the function depends on, scored by the fraction it recovers, and
naming an irrelevant variable costs the world.

These tests pin what the construction found the hard way: that the answers obey the published noise
model, that every unsupported world is a parity too large for a junta and no supported one is, that
a named irrelevant variable costs a world, and that malformed candidates never raise out of the
evaluator.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/JuntaVariableDiscovery"

# kappa* of the unsupported worlds: the parity size minus the published junta size
KAPPA = {"dev-08": 2, "dev-09": 3, "dev-10": 4, "dev-11": 5, "dev-12": 6, "held-05": 3, "held-06": 5}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class JuntaVariableDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "junta_oracle")
        cls.baseline = _load(TASK / "solution.py", "junta_baseline")
        cls.reference = _load(TASK / "verification/reference_influence.py", "junta_reference")
        cls.specs = cls.evaluator.DEVELOPMENT_WORLDS + cls.evaluator.HELDOUT_WORLDS
        cls.full = cls.evaluator.evaluate(cls.reference.identify)

    def test_blanket_refusal_in_both_forms_and_blind_claims_score_zero(self):
        ev = self.evaluator
        for submission in ({"verdict": "no_junta", "confidence": 1.0}, {"abstain": True}):
            metrics = ev.evaluate(lambda _p, _q, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)
            self.assertEqual(metrics["development_correct_refusal_rate"], 1.0, submission)
            self.assertAlmostEqual(metrics["development_raw_mechanism"], 5.0 / 12.0, msg=submission)

        def name_all(problem, _q):
            return {"verdict": "junta", "relevant": list(range(problem["max_junta_size"])), "confidence": 0.5}

        def name_random(problem, _q):
            rng = np.random.default_rng(0)
            return {"verdict": "junta",
                    "relevant": sorted(rng.choice(problem["n"], problem["max_junta_size"], replace=False).tolist())}

        for blind in (name_all, name_random):
            metrics = ev.evaluate(blind)
            self.assertEqual(metrics["valid"], 1.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["development_correct_refusal_rate"], 0.0)

    def test_the_worlds_are_the_recorded_ones(self):
        ev = self.evaluator
        dev_kinds = [ev._world(s)["kind"] for s in ev.DEVELOPMENT_WORLDS]
        self.assertEqual(dev_kinds.count("supported"), 7)
        self.assertEqual(dev_kinds.count("unsupported"), 5)
        held_kinds = [ev._world(s)["kind"] for s in ev.HELDOUT_WORLDS]
        self.assertEqual(held_kinds.count("supported"), 4)
        self.assertEqual(held_kinds.count("unsupported"), 2)
        for spec in self.specs:
            world = ev._world(spec)
            if world["kind"] == "supported":
                self.assertEqual(len(world["relevant"]), ev.MAX_JUNTA, spec["name"])
            else:
                self.assertGreater(len(world["relevant"]), ev.MAX_JUNTA, spec["name"])

    def test_every_unsupported_world_is_a_parity_too_large_and_no_supported_one_is(self):
        """kappa* is the excess influence any junta of the published size must leave uncovered:
        zero when the function is a junta that small, the parity size minus the size otherwise."""
        ev = self.evaluator
        for spec in self.specs:
            world = ev._world(spec)
            kappa = ev.detectability(world)
            if world["kind"] == "supported":
                self.assertLess(kappa, 1e-6, spec["name"])
            else:
                self.assertGreaterEqual(kappa, 2.0 - 1e-6, spec["name"])
                self.assertAlmostEqual(kappa, KAPPA[spec["name"]], places=1, msg=spec["name"])

    def test_the_relevant_variables_span_a_wide_influence_range(self):
        """Every supported world has relevant variables that act only through a parity or a gate,
        whose influence is well below the additive block's, so correlation alone cannot see them."""
        ev = self.evaluator
        weak = []
        for spec in ev.DEVELOPMENT_WORLDS:
            world = ev._world(spec)
            if world["kind"] != "supported":
                continue
            infl = ev.influences(world)
            relevant = sorted(world["relevant"])
            self.assertTrue(all(infl[i] > 1e-3 for i in relevant), spec["name"])
            self.assertTrue(all(infl[i] < 1e-3 for i in range(world["n"]) if i not in world["relevant"]), spec["name"])
            weak.append(min(infl[i] for i in relevant))
            self.assertGreater(max(infl[i] for i in relevant), 0.4, spec["name"])  # the additive block
        self.assertLess(max(weak), 0.15)  # every world has relevant variables near 0.12 influence

    def test_the_answers_follow_the_published_noise_model(self):
        ev = self.evaluator
        spec = next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-01")
        world = ev._world(spec)
        query = ev._Bench(world, 7).oracle()
        rng = np.random.default_rng(3)
        X = rng.integers(0, 2, size=(6000, world["n"]))
        flips = np.mean(query(X) != world["f"](X))
        self.assertAlmostEqual(flips, ev.NOISE, delta=0.02)

    def test_the_reference_and_the_baseline(self):
        ev, full = self.evaluator, self.full
        baseline = ev.evaluate(self.baseline.identify)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(baseline["development_false_discovery_rate"], 0.0)
        self.assertEqual(full["valid"], 1.0)
        self.assertGreater(full["combined_score"], 0.45)
        self.assertLess(full["combined_score"], 0.8)
        self.assertEqual(full["development_false_discovery_rate"], 0.0)
        self.assertEqual(full["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(full["development_correct_refusal_rate"], 1.0)
        self.assertEqual(full["heldout_correct_refusal_rate"], 1.0)
        self.assertEqual(full["development_discovery_coverage"], 1.0)
        # it does not recover every relevant variable: the weak ones sit at the edge of the budget
        self.assertLess(full["development_interval_sharpness"], 0.9)
        for row in full["per_instance"]:
            self.assertTrue(row["valid"], row)
            self.assertLessEqual(row["queries_used"], ev.BUDGET, row)

    def test_a_named_irrelevant_variable_costs_a_world_wherever_it_is_made(self):
        ev = self.evaluator
        supported = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-01"))
        unsupported = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-10"))
        R = sorted(supported["relevant"])
        irrelevant = next(i for i in range(supported["n"]) if i not in supported["relevant"])

        exact = ev._metrics(supported, set(R))
        self.assertTrue(exact["covered"])
        self.assertAlmostEqual(exact["mechanism_score"], 1.0)
        half = ev._metrics(supported, set(R[: len(R) // 2]))
        self.assertAlmostEqual(half["mechanism_score"], 0.5)
        self.assertFalse(half["false_discovery"])
        missed = ev._metrics(supported, set(R[:-1]) | {irrelevant})
        self.assertTrue(missed["false_discovery"])
        self.assertEqual(missed["mechanism_score"], -1.0)
        self.assertEqual(ev._metrics(supported, None)["mechanism_score"], 0.0)

        claimed = ev._metrics(unsupported, {0, 1, 2})
        self.assertTrue(claimed["false_discovery"])
        self.assertEqual(claimed["mechanism_score"], 0.0)
        self.assertEqual(ev._metrics(unsupported, None)["mechanism_score"], 1.0)

    def test_two_evaluations_are_identical(self):
        second = self.evaluator.evaluate(self.reference.identify)
        self.assertEqual(json.dumps(self.full, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_malformed_candidates_score_zero_without_raising(self):
        ev = self.evaluator

        def raises(_p, _q):
            raise RuntimeError("boom")

        def overspend(problem, query):
            n = problem["n"]
            while True:
                query(np.zeros((5000, n), dtype=int))

        def overspend_caught(problem, query):
            try:
                overspend(problem, query)
            except RuntimeError:
                pass
            return {"verdict": "junta", "relevant": [0]}

        def patched_budget(problem, query):
            query.budget = 10 ** 9  # a function attribute: the ledger is not reachable
            return overspend(problem, query)

        def bad_shape(problem, query):
            query(np.zeros((4, problem["n"] + 1), dtype=int))
            return {"verdict": "junta", "relevant": [0]}

        def non_binary(problem, query):
            query(np.full((4, problem["n"]), 2, dtype=int))
            return {"verdict": "junta", "relevant": [0]}

        def out_of_range(problem, _q):
            return {"verdict": "junta", "relevant": [problem["n"]]}

        def not_integer(_p, _q):
            return {"verdict": "junta", "relevant": [1.5]}

        def duplicate(_p, _q):
            return {"verdict": "junta", "relevant": [3, 3]}

        def too_many(problem, _q):
            return {"verdict": "junta", "relevant": list(range(problem["max_junta_size"] + 1))}

        def bad_verdict(_p, _q):
            return {"verdict": "maybe"}

        extra = {
            "none": lambda _p, _q: None,
            "empty": lambda _p, _q: {},
            "string": lambda _p, _q: "junta",
            "relevant_missing": lambda _p, _q: {"verdict": "junta"},
            "confidence_nan": lambda _p, _q: {"verdict": "junta", "relevant": [0], "confidence": float("nan")},
            "confidence_str": lambda _p, _q: {"verdict": "junta", "relevant": [0], "confidence": "high"},
            "relevant_bool": lambda _p, _q: {"verdict": "junta", "relevant": [True, 1]},
        }
        candidates = {c.__name__: c for c in (raises, overspend, overspend_caught, patched_budget,
                     bad_shape, non_binary, out_of_range, not_integer, duplicate, too_many, bad_verdict)}
        candidates.update(extra)
        self.assertGreaterEqual(len(candidates), 12)
        for name, candidate in candidates.items():
            metrics = ev.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0, name)
            self.assertEqual(metrics["combined_score"], 0.0, name)
            self.assertEqual(metrics["feasibility_rate"], 0.0, name)


if __name__ == "__main__":
    unittest.main()
