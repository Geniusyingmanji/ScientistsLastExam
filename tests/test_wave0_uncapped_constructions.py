"""Wave-0 combinatorial packages: no required solution, records are brushable.

Each task ships a weak valid baseline that scores 0, rejects bad candidates without
crashing, and exposes `_normalized` so a result past the published witness exceeds 1.
A mid-ladder construction, where one exists, must land strictly between 0 and 1.
"""
from __future__ import annotations

import importlib.util
import itertools
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import find_task  # noqa: E402

WAVE0 = (
    "Mathematics/RamseyLowerBound",
    "Mathematics/KissingNumber",
    "Algorithm/TensorRank555",
    "Mathematics/Superpermutation",
    "Mathematics/CapSetFrontier",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task_modules(task_id: str):
    spec = find_task(task_id, include_uncertified=True)
    evaluator = _load(spec.task_dir / "verification/evaluator.py", task_id.replace("/", "_") + "_eval")
    baseline = _load(spec.initial_program_path, task_id.replace("/", "_") + "_base")
    return spec, evaluator, baseline


class Wave0ContractTests(unittest.TestCase):
    def test_every_wave0_task_is_uncapped_optimization(self):
        for task_id in WAVE0:
            spec = find_task(task_id, include_uncertified=True)
            self.assertEqual(spec.metadata.get("scientific_role"), "optimization", task_id)
            self.assertEqual(spec.metadata.get("score_mode"), "uncapped", task_id)
            self.assertTrue((spec.task_dir / "references/known_best.md").is_file(), task_id)

    def test_the_two_anchor_helper_exceeds_one_past_the_witness(self):
        for task_id in WAVE0:
            _, evaluator, _ = _task_modules(task_id)
            helper = evaluator._normalized
            self.assertGreater(helper(1.5, 0.0, 1.0), 1.0, task_id)
            self.assertAlmostEqual(helper(1.0, 0.0, 1.0), 1.0, msg=task_id)
            self.assertAlmostEqual(helper(-1.0, 0.0, 1.0), 0.0, msg=task_id)


class RamseyLowerBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.evaluator, cls.baseline = _task_modules("Mathematics/RamseyLowerBound")

    def test_the_bipartite_baseline_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(self.baseline.build_coloring)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)

    def test_a_monochromatic_clique_scores_zero_without_raising(self):
        def all_red(s, t):
            n = 6
            adj = np.zeros((n, n), dtype=np.int8)
            return adj

        metrics = self.evaluator.evaluate(all_red)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_an_oversized_coloring_scores_zero_without_raising(self):
        def huge(s, t):
            n = 51 if (s, t) == (5, 5) else 43
            adj = np.zeros((n, n), dtype=np.int8)
            return adj

        metrics = self.evaluator.evaluate(huge)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_matching_the_exoo_order_would_score_one(self):
        helper = self.evaluator._normalized
        self.assertAlmostEqual(helper(42.0, 8.0, 42.0), 1.0)
        self.assertAlmostEqual(helper(35.0, 10.0, 35.0), 1.0)
        self.assertGreater(helper(43.0, 8.0, 42.0), 1.0)

    def test_a_raise_scores_zero_without_crashing(self):
        def boom(_s, _t):
            raise RuntimeError("deliberate")

        metrics = self.evaluator.evaluate(boom)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_paley_17_is_a_valid_mid_ladder_for_five_five(self):
        """Paley-17 is a known strongly regular graph; ω=2 or 3, so no K_5."""
        q = 17
        residues = {pow(i, 2, q) for i in range(1, q)}
        adj = np.zeros((q, q), dtype=np.int8)
        for i in range(q):
            for j in range(i + 1, q):
                color = 0 if ((j - i) % q) in residues else 1
                adj[i, j] = adj[j, i] = color

        def paley(s, t):
            if (s, t) == (5, 5):
                return adj
            return self.baseline.build_coloring(s, t)

        metrics = self.evaluator.evaluate(paley)
        self.assertEqual(metrics["valid"], 1.0)
        five = next(row for row in metrics["per_pair"] if row["s"] == 5)
        self.assertTrue(five["valid"])
        self.assertEqual(five["n"], 17)
        self.assertGreater(five["score"], 0.0)
        self.assertLess(five["score"], 1.0)


class KissingNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.evaluator, cls.baseline = _task_modules("Mathematics/KissingNumber")

    def test_the_axis_baseline_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(self.baseline.build_kissing)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)

    def test_a_pair_closer_than_sixty_degrees_scores_zero(self):
        def collapsed(d):
            a = [1.0] + [0.0] * (d - 1)
            b = [1.0, 0.1] + [0.0] * (d - 2)
            return [a, b]

        metrics = self.evaluator.evaluate(collapsed)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_overflowing_norms_cannot_fake_a_record(self):
        def collapsed(d):
            return [
                [1e200, 0.1 + i * 1e-6] + [0.0] * (d - 2)
                for i in range(842)
            ]

        metrics = self.evaluator.evaluate(collapsed)
        self.assertEqual(metrics["valid"], 0.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertFalse(metrics["beat_sota"], metrics)
        self.assertTrue(all(not row["valid"] for row in metrics["per_dim"]))

    def test_tiny_vectors_that_round_to_zero_are_rejected(self):
        for d in self.evaluator.SIZES:
            tiny = [[1e-13] + [0.0] * (d - 1)]
            valid, _, _ = self.evaluator.verify_kissing(tiny, d)
            self.assertFalse(valid, d)

        def baseline_plus_tiny(d):
            vectors = self.baseline.build_kissing(d)
            vectors.append([1e-13] + [0.0] * (d - 1))
            return vectors

        metrics = self.evaluator.evaluate(baseline_plus_tiny)
        self.assertEqual(metrics["valid"], 0.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertTrue(all(not row["valid"] for row in metrics["per_dim"]))

    def test_floating_witnesses_do_not_overclaim_scientific_records(self):
        task = (self.spec.task_dir / "Task.md").read_text(encoding="utf-8")
        card = (self.spec.task_dir / "TASK_CARD.yaml").read_text(encoding="utf-8")
        known_best = (self.spec.task_dir / "references/known_best.md").read_text(
            encoding="utf-8"
        )
        constraints = (self.spec.task_dir / "frontier_eval/constraints.txt").read_text(
            encoding="utf-8"
        )
        for text in (task, card, known_best, constraints):
            self.assertIn("exact or interval", text)
        self.assertIn("fixed-tolerance numerical", task)
        self.assertIn("non-integral floating", known_best)
        self.assertIn("numerical floor", card)

    def test_empty_or_malformed_witnesses_are_invalid(self):
        for witness in ({}, None, "not vectors"):
            metrics = self.evaluator.evaluate(lambda _d, value=witness: value)
            self.assertEqual(metrics["valid"], 0.0, witness)
            self.assertEqual(metrics["combined_score"], 0.0, witness)

    def test_a_scaled_copy_of_an_axis_is_deduped_not_rejected(self):
        def scaled(d):
            vecs = self.baseline.build_kissing(d)
            extra = [0] * d
            extra[0] = 2
            vecs.append(extra)
            return vecs

        metrics = self.evaluator.evaluate(scaled)
        self.assertEqual(metrics["valid"], 1.0)
        for row in metrics["per_dim"]:
            self.assertEqual(row["size"], 2 * row["d"])

    def test_the_d_lattice_is_a_valid_mid_ladder(self):
        """D_d is 2d(d-1) vectors of two ±1 entries: 60° contacts, below the Cohn bound."""

        def d_lattice(d):
            vecs = []
            for i in range(d):
                for j in range(i + 1, d):
                    for si, sj in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                        v = [0] * d
                        v[i] = si
                        v[j] = sj
                        vecs.append(v)
            return vecs

        metrics = self.evaluator.evaluate(d_lattice)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertGreater(metrics["combined_score"], 0.0)
        self.assertLess(metrics["combined_score"], 1.0)
        for row in metrics["per_dim"]:
            self.assertEqual(row["size"], 2 * row["d"] * (row["d"] - 1))
            self.assertGreater(row["score"], 0.0)
            self.assertLess(row["score"], 1.0)


class TensorRank555Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.evaluator, cls.baseline = _task_modules("Algorithm/TensorRank555")

    def test_the_schoolbook_baseline_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(self.baseline.build_algorithm)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)

    def test_an_inexact_decomposition_scores_zero(self):
        def zeros(m, n, p):
            R = 1
            return (np.zeros((R, m * n)), np.zeros((R, n * p)), np.zeros((m * p, R)))

        metrics = self.evaluator.evaluate(zeros)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_contract_describes_fixed_tolerance_numerical_acceptance(self):
        constraints = (self.spec.task_dir / "frontier_eval/constraints.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("fixed numerical tolerance", constraints)
        self.assertNotIn("EXACT", constraints)
        self.assertIn("fixed-tolerance numerical", self.evaluator.__doc__.lower())

        zeros = (
            np.zeros((1, 25)),
            np.zeros((1, 25)),
            np.zeros((25, 1)),
        )
        valid, _, reason = self.evaluator.verify_decomposition(*zeros, 5, 5, 5)
        self.assertFalse(valid)
        self.assertIn("outside numerical tolerance", reason)

    def test_nonfinite_reconstruction_cannot_bypass_the_tensor_check(self):
        null_coefficients = {
            5: (4, -32, -40, -10),
            6: (4, -20, 10, -4),
        }

        def fixed_probe_interpolant(m, n, p):
            rng = np.random.default_rng(0)
            inputs_a = []
            inputs_b = []
            outputs = []
            for _ in range(3):
                A = rng.integers(-4, 5, (m, n)).astype(float)
                B = rng.integers(-4, 5, (n, p)).astype(float)
                inputs_a.append(A.reshape(-1))
                inputs_b.append(B.reshape(-1))
                outputs.append((A @ B).reshape(-1))
            inputs_a = np.asarray(inputs_a)
            inputs_b = np.asarray(inputs_b)
            U = np.linalg.solve(inputs_a @ inputs_a.T, inputs_a)
            V = np.asarray([row / (row @ row) for row in inputs_b])
            W = np.asarray(outputs).T

            null_vector = np.zeros(m * n)
            null_vector[:4] = null_coefficients[m]
            self.assertTrue(np.array_equal(inputs_a @ null_vector, np.zeros(3)))
            U = np.vstack((U, null_vector, null_vector))
            huge_v = np.zeros((2, n * p))
            huge_v[:, 0] = 1e200
            V = np.vstack((V, huge_v))
            huge_w = np.zeros((m * p, 2))
            huge_w[0] = (1e200, -1e200)
            W = np.hstack((W, huge_w))
            return U, V, W

        metrics = self.evaluator.evaluate(fixed_probe_interpolant)
        self.assertEqual(metrics["valid"], 0.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertFalse(metrics["beat_sota"], metrics)
        self.assertTrue(all(not row["valid"] for row in metrics["per_size"]))

    def test_a_rank_below_the_witness_would_exceed_one(self):
        helper = self.evaluator._normalized
        self.assertGreater(helper(-92.0, -125.0, -93.0), 1.0)


class SuperpermutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.evaluator, cls.baseline = _task_modules("Mathematics/Superpermutation")

    def test_the_concatenation_baseline_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(self.baseline.build_superpermutation)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)

    def test_a_string_missing_a_permutation_scores_zero(self):
        def truncated(n):
            alphabet = "".join(str(i) for i in range(1, n + 1))
            perms = ["".join(p) for p in itertools.permutations(alphabet)]
            return "".join(perms[:-1])

        metrics = self.evaluator.evaluate(truncated)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_a_length_below_the_record_would_exceed_one(self):
        helper = self.evaluator._normalized
        self.assertGreater(helper(-5905.0, -35280.0, -5906.0), 1.0)

    def test_the_n8_reference_is_current_and_synchronized(self):
        self.assertEqual(self.evaluator.SIZES[8]["sota_ref"], 46205)
        for relative_path in (
            "Task.md",
            "TASK_CARD.yaml",
            "frontier_eval/metadata.yaml",
            "references/known_best.md",
        ):
            text = (self.spec.task_dir / relative_path).read_text(encoding="utf-8")
            self.assertIn("46205", text, relative_path)
            self.assertNotIn("46204", text, relative_path)

        known_best = (self.spec.task_dir / "references/known_best.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("https://github.com/urdvr/superpermutations-hunter", known_best)


class CapSetFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.evaluator, cls.baseline = _task_modules("Mathematics/CapSetFrontier")

    def test_the_hypercube_baseline_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(self.baseline.build_capset)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)

    def test_a_collinear_triple_scores_zero(self):
        def line(n):
            z = [0] * n
            e = [0] * n
            e[0] = 1
            t = [0] * n
            t[0] = 2
            return [z, e, t]

        metrics = self.evaluator.evaluate(line)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_empty_or_malformed_witnesses_are_invalid_without_crashing(self):
        for witness in ({}, None, "not vectors"):
            metrics = self.evaluator.evaluate(lambda _n, value=witness: value)
            self.assertEqual(metrics["valid"], 0.0, witness)
            self.assertEqual(metrics["combined_score"], 0.0, witness)

    def test_an_entry_outside_zero_one_two_is_rejected(self):
        def wrapped(n):
            vecs = self.baseline.build_capset(n)
            bad = [3] + [0] * (n - 1)
            vecs.append(bad)
            return vecs

        metrics = self.evaluator.evaluate(wrapped)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_open_dimension_score_anchors_have_primary_sources(self):
        known_best = (self.spec.task_dir / "references/known_best.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("10.1007/BF01388452", known_best)
        self.assertIn("Figure C.5", known_best)
        self.assertNotIn("OEIS A090245", known_best)

    def test_a_size_above_the_record_would_exceed_one(self):
        helper = self.evaluator._normalized
        self.assertGreater(helper(513.0, 256.0, 512.0), 1.0)


class Wave0InstanceDisjointnessTests(unittest.TestCase):
    """The two Wave-0 packages that share an oracle family with a certified task
    must not reuse that task's instance set. Merging sizes into CapSet or
    MatrixMultiplicationRank would change a certified oracle and invalidate v9."""

    def test_capset_frontier_dims_are_not_the_certified_capset_dims(self):
        certified = _load(
            ROOT / "benchmarks/Mathematics/CapSet/verification/evaluator.py",
            "capset_certified",
        )
        frontier = _load(
            ROOT / "benchmarks/Mathematics/CapSetFrontier/verification/evaluator.py",
            "capset_frontier",
        )
        overlap = set(certified.SIZES) & set(frontier.SIZES)
        self.assertEqual(overlap, set())
        self.assertEqual(set(certified.SIZES), {4, 5, 6})
        self.assertEqual(set(frontier.SIZES), {7, 8, 9})

    def test_tensor_rank_555_sizes_are_not_the_certified_matmul_sizes(self):
        certified = _load(
            ROOT / "benchmarks/ComputerScience/MatrixMultiplicationRank/verification/evaluator.py",
            "matmul_certified",
        )
        frontier = _load(
            ROOT / "benchmarks/ComputerScience/TensorRank555/verification/evaluator.py",
            "tensor_rank_555",
        )
        certified_mnp = {tuple(row["mnp"]) for row in certified.SIZES}
        frontier_mnp = {tuple(row["mnp"]) for row in frontier.SIZES}
        self.assertEqual(certified_mnp & frontier_mnp, set())
        self.assertEqual(certified_mnp, {(2, 2, 2), (3, 3, 3), (4, 4, 4)})
        self.assertEqual(frontier_mnp, {(5, 5, 5), (6, 6, 6)})


if __name__ == "__main__":
    unittest.main()
