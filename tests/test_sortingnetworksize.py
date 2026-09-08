"""Pinned invariants for SortingNetworkSize.

The tests pin the 0-1-principle checker (a full bitmask simulation over all 2^n
zero-one inputs), its output-direction convention, the Batcher baseline's exact
0.0 anchor, the ledger/evaluator anchor match, and the fail-closed behaviour of the
oracle against malformed candidates. They reverify attributed public constructions and their independent raw metrics.
"""

from __future__ import annotations

import importlib.util
import json
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "ComputerScience" / "SortingNetworkSize"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def naive_sorts(net, n: int, inputs=None) -> bool:
    """Independent brute-force simulation on zero-one inputs (full 2^n by default)."""
    if inputs is None:
        inputs = range(1 << n)
    for x in inputs:
        wires = [(x >> w) & 1 for w in range(n)]
        for i, j in net:
            a, b = wires[i], wires[j]
            wires[i] = a if a < b else b
            wires[j] = b if a < b else a
        for w in range(n - 1):
            if wires[w] > wires[w + 1]:
                return False
    return True


def batcher(n: int):
    """Batcher odd-even mergesort on N = 2^ceil(log2 n) wires, sentinel gates removed.

    A sorting network on N >= n wires restricted to the real wires (padding with +inf
    sentinels makes every gate touching a sentinel a no-op) still sorts the first n
    wires, so deleting those gates yields a legal mid-ladder network for any n.
    """
    size = 1
    while size < n:
        size <<= 1
    net = []

    def compare(i: int, j: int) -> None:
        if max(i, j) < n:
            net.append([min(i, j), max(i, j)])

    def merge(lo: int, length: int, r: int) -> None:
        m = r * 2
        if m < length:
            merge(lo, length, m)
            merge(lo + r, length, m)
            for i in range(lo + r, lo + length - r, m):
                compare(i, i + r)
        else:
            compare(lo, lo + r)

    def sort(lo: int, length: int) -> None:
        if length > 1:
            sort(lo, length // 2)
            sort(lo + length // 2, length // 2)
            merge(lo, length, 1)

    sort(0, size)
    return net


class SortingNetworkSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "sns_evaluator")
        cls.sol = _load(TASK / "solution.py", "sns_baseline")

    def test_exported_reference_runs_without_adjacent_data_files(self):
        reference = _load(TASK / "verification/reference_reconstruction.py", "export_reference")
        namespace = {}
        exec(compile(reference.export_source(), "isolated_reference.py", "exec"), namespace)
        for n in self.ev.SIZES:
            self.assertEqual(namespace["build_network"](n), reference.build_network(n))

    def test_search_probe_is_standalone_deterministic_and_exact(self):
        source = (TASK / "verification/reference_search.py").read_text()
        namespace = {"__name__": "isolated_search"}
        # No __file__ or neighboring data directory is provided.
        exec(compile(source, "isolated_search.py", "exec"), namespace)
        first = namespace["search_network"](6, trials=20)
        second = namespace["search_network"](6, trials=20)
        self.assertEqual(first, second)
        self.assertTrue(naive_sorts(first, 6))
        self.assertTrue(self.ev.verify_network(first, 6)[0])

    # ------------------------------------------------ 0-1 principle checker

    def test_bitmask_checker_agrees_with_brute_force_on_random_networks(self):
        rng = random.Random(20260908)
        for n, trials, max_gates in ((4, 30, 16), (6, 30, 24), (8, 30, 32),
                                     (10, 20, 40), (13, 8, 25)):
            for _ in range(trials):
                count = rng.randint(5, max_gates)
                net = []
                for _ in range(count):
                    i = rng.randrange(n - 1)
                    j = rng.randrange(i + 1, n)
                    net.append([i, j])
                ok, size, _ = self.ev.verify_network(net, n)
                self.assertEqual(ok, naive_sorts(net, n), (n, net))
                self.assertEqual(size, len(net))

    def test_checker_agrees_on_batcher_networks_for_every_scored_n(self):
        rng = random.Random(7)
        for n in sorted(self.ev.SIZES):
            net = batcher(n)
            ok, size, _ = self.ev.verify_network(net, n)
            self.assertTrue(ok, n)
            self.assertEqual(size, len(net))
            if n <= 13:
                self.assertTrue(naive_sorts(net, n))       # full 2^n sweep
            else:                                           # sampled sweep, full is slow here
                inputs = [0, (1 << n) - 1] + [rng.randrange(1 << n) for _ in range(4000)]
                self.assertTrue(naive_sorts(net, n, inputs))

    def test_output_direction_is_ascending(self):
        # The gate contract is ascending (min on the lower wire), so a descending output
        # cannot be built directly; pin the checker's direction with micro-cases instead.
        # A reversed-direction subset test would reject these valid two/three-wire sorters.
        for net, n in (
            ([[0, 1]], 2),
            ([[0, 1], [0, 1]], 2),          # duplicate gate is a no-op but legal
            ([[0, 1], [1, 2], [0, 1]], 3),  # classic three-wire sorter
        ):
            ok, _, _ = self.ev.verify_network(net, n)
            self.assertTrue(ok, (net, n))
        # Networks that leave a lower wire above a higher one must be rejected: on the
        # zero-one input (1,0,0) the gate [1,2] never touches wire 0, and on (0,1,0)
        # the pair [0,1] never touches wire 2.
        for net, n in (
            ([[1, 2]], 3),
            ([[0, 1], [0, 1]], 3),
        ):
            ok, _, _ = self.ev.verify_network(net, n)
            self.assertFalse(ok, (net, n))

    def test_empty_network_rejected_for_scored_sizes(self):
        for n in self.ev.SIZES:
            ok, _, _ = self.ev.verify_network([], n)
            self.assertFalse(ok, n)

    # ------------------------------------------------------ anchors & score

    def test_baseline_is_valid_scores_exactly_zero_and_recomputes(self):
        for n, ref in self.ev.SIZES.items():
            net = self.sol.build_network(n)
            self.assertEqual(len(net), {13: 48, 14: 53, 15: 59, 16: 63, 17: 75}[n])
            ok, size, _ = self.ev.verify_network(net, n)
            self.assertTrue(ok, n)
            self.assertEqual(size, ref["baseline"], n)
            self.assertAlmostEqual(
                self.ev.score_n(n, ref, self.sol.build_network)["score"], 0.0)

    def test_anchor_ledger_matches_evaluator_and_baseline_formula(self):
        ledger = json.loads((TASK / "references" / "anchors.json").read_text())
        anchors = {e["name"]: e for e in ledger["anchors"]}
        for n, ref in self.ev.SIZES.items():
            self.assertEqual(ref["baseline"], len(self.sol.build_network(n)), n)
            self.assertEqual(anchors[f"lower_bound_n{n}"]["value"], ref["lower_bound"])
            entry = anchors[f"sota_ref_n{n}"]
            self.assertEqual(entry["value"], ref["sota_ref"], n)
            self.assertTrue(entry["source_url"].startswith("http"), n)
            self.assertTrue(entry["derivation"], n)

    def test_bound_target_is_distinct_from_constructive_record(self):
        helper = self.ev._normalized
        self.assertEqual(helper(1.5, 0.0, 1.0), 1.0)
        self.assertAlmostEqual(helper(1.0, 0.0, 1.0), 1.0)
        self.assertAlmostEqual(helper(-1.0, 0.0, 1.0), 0.0)
        # This is normalization arithmetic, not a claim that a 44-gate network exists.
        self.assertAlmostEqual(helper(-45.0, -48.0, -44.0), 0.75)
        self.assertAlmostEqual(helper(-44.0, -48.0, -44.0), 1.0)
        self.assertAlmostEqual(helper(-48.0, -48.0, -44.0), 0.0)
        for n, ref in self.ev.SIZES.items():
            self.assertLess(ref["lower_bound"], ref["sota_ref"])
            self.assertGreaterEqual(ref["lower_bound"], self.ev.conservative_lower_bound(n))

    def test_batcher_is_the_recomputed_zero_anchor(self):
        for n, ref in self.ev.SIZES.items():
            ok, size, _ = self.ev.verify_network(batcher(n), n)
            self.assertTrue(ok, n)
            score = self.ev.score_n(n, ref, lambda m: batcher(m))["score"]
            self.assertEqual(score, 0.0, n)

    def test_public_reconstruction_is_valid_but_not_full_score(self):
        ref = _load(TASK / "verification" / "reference_reconstruction.py", "sns_reconstruction")
        metrics = self.ev.evaluate(ref.build_network)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertGreater(metrics["combined_score"], 0.0)
        self.assertLess(metrics["combined_score"], 1.0)
        self.assertEqual(metrics["raw_score"], -(45 + 51 + 56 + 60 + 71) / 5)
        for row in metrics["per_n"]:
            self.assertEqual(row["record_gap"], 0)
            self.assertGreater(row["lower_bound_gap"], 0)
            self.assertFalse(row["target_attained"])

    def test_reconstruction_assets_match_attributed_hashes(self):
        import hashlib
        sources = json.loads((TASK / "references" / "reference_sources.json").read_text())
        for entry in sources["files"]:
            self.assertEqual(hashlib.sha256((TASK / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])

    # -------------------------------------------------- malformed candidates

    def test_malformed_candidates_score_zero_without_raising(self):
        def oversized(n):
            return [[i % (n - 1), i % (n - 1) + 1] for i in range(n * n + 5)]

        def not_sorting(n):
            return [[0, 1], [2, 3]]

        def junk_pair(n):
            return [[0, 1], [1, "x"]]

        def float_index(n):
            return [[0.5, 1.5]]

        def equal_index(n):
            return [[3, 3]]

        def reversed_index(n):
            return [[5, 2]]

        def out_of_range(n):
            return [[0, n]]

        bad = [
            lambda n: (_ for _ in ()).throw(RuntimeError("deliberate")),
            lambda n: None,
            lambda n: 42,
            lambda n: 3.14,
            lambda n: "network",
            lambda n: {"0": [0, 1]},
            lambda n: True,
            lambda n: [],
            lambda n: [[0, float("nan")]],
            lambda n: [[0, float("inf")]],
            lambda n: [[0, float("-inf")]],
            lambda n: [(i for i in () if False)],
            oversized,
            not_sorting,
            junk_pair,
            float_index,
            equal_index,
            reversed_index,
            out_of_range,
        ]
        for maker in bad:
            with self.subTest(maker=maker.__name__ or repr(maker)):
                metrics = self.ev.evaluate(lambda n, m=maker: m(n))
                self.assertEqual(metrics["combined_score"], 0.0)
                self.assertEqual(metrics["raw_score"], -1e18)
                self.assertEqual(metrics["valid"], 0.0)
                self.assertEqual(metrics["feasibility_rate"], 0.0)

    def test_partial_invalid_submission_has_no_search_credit(self):
        reference = _load(TASK / "verification/reference_reconstruction.py", "partial_reference")
        metrics = self.ev.evaluate(lambda n: reference.build_network(n) if n == 13 else [])
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], -1e18)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 0.2)
        self.assertIn("error_message", metrics)

    def test_bound_contradiction_is_distinguished_from_malformed_output(self):
        from unittest.mock import patch
        sizes = {n: dict(row) for n, row in self.ev.SIZES.items()}
        sizes[13]["lower_bound"] = sizes[13]["baseline"] + 1
        with patch.object(self.ev, "SIZES", sizes):
            metrics = self.ev.evaluate(self.sol.build_network)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], -1e18)
        self.assertEqual(metrics["bound_contradiction"], 1.0)
        self.assertIn("audit_required", metrics["error_message"])
        self.assertIn("n=13", metrics["error_message"])

    def test_oversized_list_is_rejected_before_iteration(self):
        class Oversized(list):
            def __iter__(self):
                raise AssertionError("oversized sequence must not be copied")
        ok, size, reason = self.ev.verify_network(Oversized([[0, 1]] * 170), 13)
        self.assertFalse(ok)
        self.assertEqual(size, 170)
        self.assertIn("cap", reason)

    def test_liberal_but_valid_formats_are_accepted(self):
        import numpy as np

        base = {n: self.sol.build_network(n) for n in self.ev.SIZES}
        variants = {
            "tuples": lambda n: [tuple(p) for p in base[n]],
            "numpy": lambda n: np.array(base[n], dtype=int),
            "numpy_float32": lambda n: np.array(base[n], dtype=np.float32),
            "numpy_float64": lambda n: np.array(base[n], dtype=np.float64),
            "integral_floats": lambda n: [[float(i), float(j)] for i, j in base[n]],
            "generator": lambda n: (p for p in base[n]),
            "iterable_of_arrays": lambda n: [np.array(p) for p in base[n]],
        }
        for name, maker in variants.items():
            metrics = self.ev.evaluate(maker)
            self.assertEqual(metrics["valid"], 1.0, name)
            self.assertAlmostEqual(metrics["combined_score"], 0.0, name)

    def test_infinite_generator_is_capped_not_hung(self):
        def endless(n):
            counter = [0]

            def gen():
                while True:
                    i = counter[0] % (n - 1)
                    counter[0] += 1
                    yield [i, i + 1]
            return gen()

        metrics = self.ev.evaluate(endless)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    # -------------------------------------------------------------- oracle

    def test_evaluate_is_deterministic(self):
        first = self.ev.evaluate(self.sol.build_network)
        second = self.ev.evaluate(self.sol.build_network)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_evaluate_reports_per_instance_structure(self):
        metrics = self.ev.evaluate(self.sol.build_network)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        self.assertFalse(metrics["beat_sota"])
        self.assertEqual(sorted(r["n"] for r in metrics["per_n"]), [13, 14, 15, 16, 17])
        for row in metrics["per_n"]:
            self.assertTrue(row["valid"])
            self.assertIn("size", row)
            self.assertIn("sota_ref", row)
            self.assertIn("record_gap", row)
            self.assertIn("lower_bound_gap", row)


if __name__ == "__main__":
    unittest.main()
