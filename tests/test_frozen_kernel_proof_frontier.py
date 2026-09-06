"""Invariants for Mathematics/FrozenKernelProofFrontier."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Mathematics" / "FrozenKernelProofFrontier"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("kernel_evaluator", TASK / "verification" / "evaluator.py")
BASELINE = _load("kernel_baseline", TASK / "solution.py")
REFERENCE = _load("kernel_reference", TASK / "verification" / "reference_proofs.py")


class FrozenKernelTests(unittest.TestCase):
    def test_baseline_is_valid_and_scores_exactly_zero(self):
        result = EVALUATOR.evaluate(BASELINE.build_proofs)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["feasibility_rate"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)
        for row in result["per_instance"]:
            self.assertEqual(row["proof_size"], EVALUATOR.SIZE_CAP)

    def test_reference_scores_below_one_on_the_log_size_scale(self):
        result = EVALUATOR.evaluate(REFERENCE.build_proofs)
        self.assertEqual(result["valid"], 1.0)
        self.assertAlmostEqual(result["combined_score"], 0.640515, places=5)
        self.assertGreater(result["combined_score"], 0.3)
        self.assertLess(result["combined_score"], 0.8)

    def test_visible_baseline_does_not_name_the_short_proofs(self):
        source = (TASK / "solution.py").read_text(encoding="utf-8")
        self.assertNotIn("SHORT", source)
        self.assertNotIn("_pad", source)

    def test_a_reference_length_prefix_of_the_baseline_is_not_the_theorem(self):
        """I-first padding: a compiled-size prefix proves goal→goal, not the goal."""

        compiled = {row["name"]: row["compiled_size"] for row in EVALUATOR.THEOREMS}

        def candidate(problem):
            proofs = BASELINE.build_proofs(problem)
            return {row["name"]: proofs[row["name"]][: compiled[row["name"]]]
                    for row in problem["theorems"]}

        result = EVALUATOR.evaluate(candidate)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["valid"], 0.0)

    def test_swapping_in_the_hidden_identity_proof_beats_the_baseline(self):
        def candidate(problem):
            proofs = BASELINE.build_proofs(problem)
            proofs["identity"] = REFERENCE.build_proofs(problem)["identity"]
            return proofs

        result = EVALUATOR.evaluate(candidate)
        self.assertGreater(result["combined_score"], 0.0)
        self.assertLess(result["combined_score"], 0.3)
        by_name = {row["name"]: row for row in result["per_instance"]}
        self.assertAlmostEqual(by_name["identity"]["instance_score"], 0.833078, places=5)
        self.assertLess(by_name["identity"]["instance_score"], 1.0)

    def test_malformed_submissions_score_zero_without_raising(self):
        identity = {"axiom": "K", "subst": {"X": "A", "Y": "A"}}
        cases = {
            "none": lambda problem: None,
            "empty": lambda problem: {},
            "list": lambda problem: [],
            "string": lambda problem: "not a mapping",
            "missing_theorem": lambda problem: {"identity": [identity]},
            "sorry": lambda problem: {
                row["name"]: [{"axiom": "sorry", "subst": {"X": "A", "Y": "B"}}]
                for row in problem["theorems"]},
            "unknown_axiom": lambda problem: {
                row["name"]: [{"axiom": "T", "subst": {"X": "A", "Y": "B"}}]
                for row in problem["theorems"]},
            "mp_out_of_range": lambda problem: {
                row["name"]: [identity, {"mp": [0, 9]}]
                for row in problem["theorems"]},
            "too_long": lambda problem: {
                row["name"]: [identity] * (EVALUATOR.SIZE_CAP + 1)
                for row in problem["theorems"]},
            "float_atom": lambda problem: {
                row["name"]: [{"axiom": "K", "subst": {"X": 1.5, "Y": "A"}}]
                for row in problem["theorems"]},
            "boolean_axiom": lambda problem: {
                row["name"]: [{"axiom": True, "subst": {"X": "A", "Y": "B"}}]
                for row in problem["theorems"]},
            "raises": lambda problem: (_ for _ in ()).throw(RuntimeError("boom")),
        }
        self.assertGreaterEqual(len(cases), 10)
        for name, candidate in cases.items():
            with self.subTest(candidate=name):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["combined_score"], 0.0)
                self.assertEqual(result["valid"], 0.0)


if __name__ == "__main__":
    unittest.main()
