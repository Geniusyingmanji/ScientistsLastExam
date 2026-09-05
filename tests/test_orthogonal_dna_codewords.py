"""Pinned invariants for OrthogonalDNACodewords.

The tests pin the construction errors in the task's known_best.md: the diagonal in
the Hamming matrix, the self-dimer check before any word is accepted, and the
trivial-pair zero anchor.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Biology" / "OrthogonalDNACodewords"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OrthogonalDNACodewordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "odc_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "odc_reference")
        cls.sol = _load(TASK / "solution.py", "odc_baseline")

    def test_hamming_diagonal_is_exempt_but_self_dimer_is_not(self):
        family = self.ev.FAMILIES[0]
        ok, _ = self.ev.check_library(
            family, ["ACACACACACACACAC", "GTGTGTGTGTGTGTGT"])
        self.assertFalse(ok)  # alternating complements cross-dimer at every alignment
        codes = self.ev._encode(["AAAAACCCCCGGGGGT", "ACACACACACACACAC"])
        hamming = self.ev._min_hamming_matrix(codes)
        self.assertEqual(int(hamming[0, 0]), 0)  # a word is not its own pair
        dimer = self.ev._max_crossdimer_matrix(codes)
        self.assertGreater(int(dimer[0, 0]), 0)  # but self-dimerization counts

    def test_greedy_reference_stays_below_the_frozen_witness(self):
        # The shipped reference is greedy only; the frozen witness sizes require
        # the removal-repair phase it deliberately omits. At 240 restarts the
        # greedy plateau is exactly 28/27, short runs stay at or below it.
        library = self.ref.build_codeword_library(self.ev.problem_statement(),
                                                  restarts=240, seed=0)
        self.assertEqual({family: len(words) for family, words in library.items()},
                         {"dna16": 28, "dna12": 27})
        for family in self.ev.FAMILIES:
            self.assertLess(len(library[family["family"]]),
                            self.ev.WITNESS_SIZE[family["family"]])
        short = self.ref.build_codeword_library(self.ev.problem_statement(),
                                                restarts=5, seed=0)
        for family in self.ev.FAMILIES:
            self.assertLessEqual(len(short[family["family"]]),
                                 len(library[family["family"]]))

    def test_trivial_pair_baseline_scores_zero(self):
        first = self.ev.evaluate(self.sol.build_codeword_library)
        second = self.ev.evaluate(self.sol.build_codeword_library)
        self.assertEqual(first["valid"], 1.0)
        self.assertLessEqual(abs(first["combined_score"]), 0.01)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))

    def test_reference_scores_below_the_frozen_witness(self):
        # 28/27 against the 32/29 witness anchor: (28-2)/(32-2) and (27-2)/(29-2)
        # average to 0.8963 — the deliberate gap a first proposal must not close.
        result = self.ev.evaluate(self.ref.build_codeword_library)
        self.assertEqual(result["valid"], 1.0)
        self.assertAlmostEqual(result["combined_score"], 0.8963, places=3)
        self.assertLess(result["combined_score"], 0.95)

    def test_constraint_violations_score_zero(self):
        family = self.ev.FAMILIES[0]
        probes = {
            "wrong gc": ["A" * 16, "C" * 8 + "G" * 8],
            "bad alphabet": ["ACGTACGTACGTACGX", "ACGTACGTACGTCGAT"],
            "crossdimer": ["ACGTACGTACGTACGT", "ACGTACGTACGTACGA"],
            "homopolymer": ["AAAAACCCCGGGGTT", "AAAACCCCGGGGTTT"],
        }
        for _label, words in probes.items():
            ok, _reason = self.ev.check_library(family, words)
            self.assertFalse(ok, _label)

    def test_cap_rejects_oversized_libraries(self):
        family = dict(self.ev.FAMILIES[0])
        ok, reason = self.ev.check_library(family, ["ACGTACGTACGTACGA"] * 513)
        self.assertFalse(ok)
        self.assertIn("cap", reason)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for candidate in (raises, lambda p: {}, lambda p: None):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
