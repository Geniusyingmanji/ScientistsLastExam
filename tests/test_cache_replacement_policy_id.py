"""Discovery-contract pins for CacheReplacementPolicyID.

The public score is mechanism, normalised so that declining every world is exactly zero and so is
claiming a machine everywhere. A randomised policy is the unsupported case: declining it is
correct, declining everything is not; a deterministic policy is determinable and its machine is
the answer.

Five of these tests pin what the construction found the hard way: that the simulator behind `run`
and the machine the score compares against are the same policy, that the worlds are distinct
minimal machines of the recorded sizes, that one policy differs from LRU only after a run of six
misses, that the pooled determinism test is what keeps the rarely random policies from being
claimed, and that a wrong machine costs a world.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/CacheReplacementPolicyID"
REFERENCE = TASK / "verification/reference_lstar_family.py"

STATES = {"dev-01": 255, "dev-02": 15, "dev-03": 24, "dev-04": 24, "dev-05": 24, "dev-06": 720,
          "dev-07": 128, "dev-08": 120, "dev-09": 134, "held-01": 40, "held-02": 24, "held-03": 720,
          "held-04": 78}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _predict(machine, trace, W):
    _n, H, M = machine
    s, ways, out = 0, list(range(W)), []
    for b in trace:
        if b in ways:
            s = H[s][ways.index(b)]
            out.append(True)
        else:
            v, s = M[s]
            ways[v] = b
            out.append(False)
    return out


def _single_state(W, **override):
    machine = {"hit": [[0] * W], "miss": [[0, 0]]}
    machine.update(override)
    return {"verdict": "policy", "machine": machine, "confidence": 0.5}


class CacheReplacementPolicyIDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "cache_policy_oracle")
        cls.baseline = _load(TASK / "solution.py", "cache_policy_baseline")
        cls.reference = _load(REFERENCE, "cache_policy_reference")
        cls.specs = cls.evaluator.DEVELOPMENT_WORLDS + cls.evaluator.HELDOUT_WORLDS
        cls.full = cls.evaluator.evaluate(cls.reference.identify)

    def _variant(self, old, new):
        source = REFERENCE.read_text(encoding="utf-8")
        self.assertEqual(source.count(old), 1, old)
        namespace = {"__name__": "reference_variant"}
        exec(compile(source.replace(old, new), "reference_variant", "exec"), namespace)  # noqa: S102
        return namespace["identify"]

    def test_blanket_refusal_in_both_forms_and_a_blind_claim_score_zero(self):
        for submission in ({"verdict": "no_policy", "confidence": 1.0}, {"abstain": True}):
            metrics = self.evaluator.evaluate(lambda _p, _r, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)
            self.assertEqual(metrics["development_correct_refusal_rate"], 1.0, submission)
            self.assertEqual(metrics["development_raw_mechanism"], 3.0 / 12.0, submission)

        lru = self.baseline

        def blind(problem, _r):
            # LRU written out without a single run: right in exactly one development world
            return {"verdict": "policy", "machine": lru._machine(lru._LRU(problem["ways"]), 1024),
                    "confidence": 0.9}
        metrics = self.evaluator.evaluate(blind)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertGreater(metrics["development_false_discovery_rate"], 0.8)

    def test_the_cache_and_the_scored_machine_are_the_same_policy(self):
        """`run` simulates the policy object; the score compares against the policy's minimised
        reachable machine. With the noise off, the two must give the same outcome everywhere."""
        ev = self.evaluator
        rng = random.Random(5)
        for spec in self.specs:
            policy = spec["policy"]()
            if policy.randomized:
                continue
            machine = ev.policy_machine(policy)
            for _ in range(40):
                trace = [rng.choice(range(policy.W + 3)) if rng.random() < 0.7 else rng.randrange(10, 10 ** 6)
                         for _ in range(rng.randint(1, 60))]
                self.assertEqual(ev._execute(policy, trace, 0.0, random.Random(0)),
                                 _predict(machine, trace, policy.W), spec["name"])

    def test_the_worlds_are_distinct_minimal_machines_of_the_recorded_sizes(self):
        ev = self.evaluator
        machines = {}
        for spec in self.specs:
            world = ev._world(spec)
            if spec["kind"] == "randomized":
                self.assertTrue(world["policy"].randomized, spec["name"])
                self.assertIsNone(world["truth"], spec["name"])
                continue
            n, H, M = world["truth"]
            self.assertEqual(n, STATES[spec["name"]], spec["name"])
            self.assertEqual(ev._minimise(n, H, M)[0], n, spec["name"])
            machines[spec["name"]] = world["truth"]
        self.assertEqual(len(machines), 13)
        for (a, ma), (b, mb) in itertools.combinations(machines.items(), 2):
            if len(ma[1][0]) == len(mb[1][0]):
                self.assertIsNotNone(ev.distinguishing_word(ma, mb), (a, b))

    def test_one_policy_differs_from_lru_only_after_six_misses_in_a_row(self):
        ev = self.evaluator
        switch = next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-08")
        word = ev.distinguishing_word(ev._world(switch)["truth"], ev.policy_machine(ev._LRU(4)))
        self.assertEqual(word, ["M"] * 6)
        row = next(r for r in self.full["per_instance"] if r["split"] == "development" and r["world_index"] == 7)
        self.assertTrue(row["abstained"])      # the reference does not claim it

    def test_the_reference_and_the_baseline(self):
        ev, full = self.evaluator, self.full
        baseline = ev.evaluate(self.baseline.identify)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(baseline["development_false_discovery_rate"], 0.8)
        self.assertEqual(full["valid"], 1.0)
        self.assertGreater(full["combined_score"], 0.45)
        self.assertLess(full["combined_score"], 0.8)
        self.assertEqual(full["development_false_discovery_rate"], 0.0)
        self.assertEqual(full["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(full["development_correct_refusal_rate"], 1.0)
        self.assertEqual(full["heldout_correct_refusal_rate"], 1.0)
        # The reference leaves deterministic policies unclaimed on purpose; if it claims every one
        # the task has stopped measuring the axis it was built around.
        self.assertLess(full["development_discovery_coverage"], 1.0)
        self.assertLess(full["heldout_discovery_coverage"], 1.0)
        for row in full["per_instance"]:
            self.assertTrue(row["valid"], row)
            self.assertLessEqual(row["runs_used"], ev.RUN_BUDGET, row)
            if row["kind"] == "randomized":
                self.assertTrue(row["abstained"], row)

    def test_the_pooled_determinism_test_keeps_rare_randomness_from_being_claimed(self):
        """Without the pooled test on bursts and loops, a policy that is random once in 32 or 64
        misses passes as deterministic and its majority-vote machine is claimed."""
        no_pooled = self._variant("    return _per_position(box, rng) or _pooled(box, rng)",
                                  "    return _per_position(box, rng)")
        metrics = self.evaluator.evaluate(no_pooled)
        claimed = [r for r in metrics["per_instance"] if r["kind"] == "randomized" and not r["abstained"]]
        self.assertGreaterEqual(len(claimed), 2)
        self.assertLess(metrics["combined_score"], self.full["combined_score"] - 0.15)
        self.assertLess(metrics["heldout_mechanism_score"], self.full["heldout_mechanism_score"] - 0.2)

    def test_the_library_and_lstar_both_earn(self):
        no_library = self._variant("    m = _fit_library(box, rng)\n", "    m = None\n")
        no_lstar = self._variant("    learner = _LStar(box)\n", "    return None\n    learner = _LStar(box)\n")
        full = self.full["combined_score"]
        self.assertLess(self.evaluator.evaluate(no_library)["combined_score"], full - 0.1)
        self.assertLess(self.evaluator.evaluate(no_lstar)["combined_score"], full - 0.3)

    def test_a_wrong_machine_costs_a_world_wherever_it_is_made(self):
        ev = self.evaluator
        lru = ev.policy_machine(ev._LRU(4))
        deterministic = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-03"))
        randomized = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-10"))
        wrong = ev._metrics(deterministic, lru)
        self.assertTrue(wrong["false_discovery"])
        self.assertEqual(wrong["mechanism_score"], -1.0)
        self.assertEqual(ev._metrics(deterministic, None)["mechanism_score"], 0.0)
        right = ev._metrics(deterministic, deterministic["truth"])
        self.assertTrue(right["recovered"])
        self.assertEqual(right["mechanism_score"], 1.0)
        claimed = ev._metrics(randomized, lru)
        self.assertTrue(claimed["false_discovery"])
        self.assertEqual(claimed["mechanism_score"], 0.0)
        self.assertEqual(ev._metrics(randomized, None)["mechanism_score"], 1.0)

    def test_two_evaluations_are_identical(self):
        second = self.evaluator.evaluate(self.reference.identify)
        self.assertEqual(json.dumps(self.full, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_malformed_candidates_score_zero_without_raising(self):
        ev = self.evaluator

        def raises(_p, _r):
            raise RuntimeError("boom")

        def overspend(problem, run):
            while True:
                run([0] * problem["max_trace_length"])

        def overspend_caught(problem, run):
            try:
                overspend(problem, run)
            except RuntimeError:
                pass
            return {"verdict": "no_policy"}

        def patched_budget(problem, run):
            run.budget = 10 ** 9  # a function attribute: the ledger is not reachable
            return overspend(problem, run)

        def shaped(**override):
            return lambda p, _r: _single_state(p["ways"], **{k: v(p["ways"]) for k, v in override.items()})

        def answer(**fields):
            return lambda p, _r: dict(_single_state(p["ways"]), **fields)

        shapes = {
            "raises": raises,
            "none": lambda _p, _r: None,
            "empty": lambda _p, _r: {},
            "string": lambda _p, _r: "policy",
            "verdict_bad": lambda _p, _r: {"verdict": "maybe"},
            "machine_missing": lambda _p, _r: {"verdict": "policy"},
            "machine_list": answer(machine=[[0, 0, 0, 0]]),
            "hit_not_list": shaped(hit=lambda W: "0"),
            "row_short": shaped(hit=lambda W: [[0] * (W - 1)]),
            "state_out_of_range": shaped(hit=lambda W: [[1] * W]),
            "victim_out_of_range": shaped(miss=lambda W: [[W, 0]]),
            "miss_not_pair": shaped(miss=lambda W: [[0]]),
            "lengths_differ": shaped(miss=lambda W: [[0, 0], [0, 0]]),
            "no_states": shaped(hit=lambda W: [], miss=lambda W: []),
            "too_many_states": shaped(hit=lambda W: [[0] * W] * (ev.MAX_STATES + 1),
                                      miss=lambda W: [[0, 0]] * (ev.MAX_STATES + 1)),
            "state_float": shaped(hit=lambda W: [[0.0] * W]),
            "state_bool": shaped(miss=lambda W: [[False, 0]]),
            "confidence_nan": answer(confidence=float("nan")),
            "confidence_str": answer(confidence="high"),
            "overspend": overspend,
            "overspend_caught": overspend_caught,
            "patched_budget": patched_budget,
            "trace_empty": lambda _p, r: r([]),
            "trace_too_long": lambda p, r: r([0] * (p["max_trace_length"] + 1)),
            "trace_float": lambda _p, r: r([0.0, 1]),
            "trace_negative": lambda _p, r: r([-1]),
            "trace_bool": lambda _p, r: r([True]),
            "trace_huge_block": lambda _p, r: r([2 ** 31]),
            "trace_string": lambda _p, r: r("0123"),
        }
        self.assertGreaterEqual(len(shapes), 12)
        for name, candidate in shapes.items():
            metrics = ev.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0, name)
            self.assertEqual(metrics["combined_score"], 0.0, name)
            self.assertEqual(metrics["feasibility_rate"], 0.0, name)

    def test_runs_are_charged_and_the_budget_fails_closed(self):
        ev = self.evaluator
        world = ev._world(self.specs[0])
        W = world["policy"].W
        bench = ev._Bench(world)
        run = bench.oracle()
        trace = [b % (W + 2) for b in range(ev.MAX_TRACE)]
        first, again = run(trace), run(trace)
        self.assertEqual(len(first), ev.MAX_TRACE)
        self.assertNotEqual(first, again)          # the same trace twice gives fresh runs
        self.assertEqual(bench.spent, 2 * (W + ev.MAX_TRACE))
        with self.assertRaises(RuntimeError):
            while True:
                run(trace)
        self.assertTrue(bench.violated)
        self.assertLessEqual(bench.spent, world["budget"])
        # outcomes do not depend on the order in which different traces are run
        a, b = ev._Bench(world).oracle(), ev._Bench(world).oracle()
        t1, t2 = [0, 1, 7, 8, 9, 0, 1], [3, 2, 11, 12, 3]
        x1 = a(t1); y1 = a(t2)
        y2 = b(t2); x2 = b(t1)
        self.assertEqual((x1, y1), (x2, y2))

    def test_hidden_axes_stay_out_of_the_search_view(self):
        from sle.metric_visibility import SEARCH_VISIBLE_KEYS

        for key in SEARCH_VISIBLE_KEYS:
            self.assertNotIn("heldout", key)
            self.assertNotIn("mechanism", key)
            self.assertNotIn("policy_recovery", key)


if __name__ == "__main__":
    unittest.main()
