"""Pinned invariants for PermutationFlowShop.

The tests pin the accelerated insertion evaluation against brute force, the NEH
zero-anchor, the frozen witness table, and fresh-seed determinism of the instances.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Engineering" / "PermutationFlowShop"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PermutationFlowShopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "pfs_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "pfs_reference")
        cls.sol = _load(TASK / "solution.py", "pfs_baseline")

    def test_accelerated_insertion_matches_brute_force(self):
        rng = np.random.default_rng(11)
        for _ in range(30):
            n, m = int(rng.integers(4, 12)), int(rng.integers(2, 7))
            times = rng.integers(1, 100, size=(n, m))
            sequence = list(rng.permutation(n))
            job = sequence[int(rng.integers(0, n))]
            rest = [j for j in sequence if j != job]
            prefix = self.ref._prefix_tables(times, rest)
            suffix = self.ref._suffix_tables(times, rest)
            fast = self.ref._insertion_positions(times, job, prefix, suffix)
            brute = [self.ref.makespan_of(times, rest[:k] + [job] + rest[k:])
                     for k in range(len(rest) + 1)]
            self.assertEqual(fast, brute)

    def test_instances_are_fresh_and_deterministic(self):
        for spec in self.ev.DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS:
            first = self.ev.instance(spec)
            second = self.ev.instance(spec)
            self.assertEqual(json.dumps(first), json.dumps(second))
            self.assertTrue(first["seed"] >= 44011)
            times = np.asarray(first["processing_times"])
            self.assertTrue(times.min() >= 1 and times.max() <= 99)

    def test_witness_values_are_real_achievable_makespans(self):
        # The frozen literals must be at least as good as a short deterministic run.
        for spec in self.ev.DEVELOPMENT_SPECS:
            problem = self.ev.instance(spec)
            order = self.ref.schedule_flow_shop(problem, iterations=25, seed=0)
            achieved = self.ev.makespan(problem["processing_times"], order)
            self.assertLessEqual(self.ev.WITNESS_MAKESPAN[spec[0]], achieved)

    def test_witness_reaches_one_and_baseline_zero(self):
        baseline = self.ev.evaluate(self.sol.schedule_flow_shop)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertLessEqual(abs(baseline["combined_score"]), 0.01)
        def witness(problem):
            return self.ref.schedule_flow_shop(problem, iterations=3000, seed=0)
        # Spot-check one small instance at full witness budget (fast) and verify the
        # frozen literal is exactly the witness search's output for it.
        small = self.ev.instance(self.ev.DEVELOPMENT_SPECS[0])
        order = self.ref.schedule_flow_shop(small, iterations=3000, seed=0)
        self.assertEqual(self.ev.makespan(small["processing_times"], order),
                         self.ev.WITNESS_MAKESPAN[44011])

    def test_malformed_permutations_score_zero(self):
        for candidate in (lambda p: [0, 0, 1, 1], lambda p: list(range(3)),
                          lambda p: None, lambda p: "perm"):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)

    def test_neh_anchor_scores_zero(self):
        def neh_candidate(problem):
            return self.ref._neh(np.asarray(problem["processing_times"], dtype=int))
        result = self.ev.evaluate(neh_candidate)
        self.assertEqual(result["valid"], 1.0)
        self.assertLessEqual(abs(result["combined_score"]), 0.01)


if __name__ == "__main__":
    unittest.main()
