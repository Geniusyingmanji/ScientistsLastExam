"""Pinned invariants for ExactIdentityEvidence.

The tests pin the exact-arithmetic machinery (series against known digits, exact
zero residuals), the cap semantics, the min-cap certification gate, the Decimal
context trap, and the passive-floor normalization.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 200

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Mathematics" / "ExactIdentityEvidence"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExactIdentityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = _load(TASK / "verification" / "evaluator.py", "eie_evaluator")
        cls.ref = _load(TASK / "verification" / "reference_solver.py", "eie_reference")
        cls.sol = _load(TASK / "solution.py", "eie_baseline")

    def test_base_series_match_known_digits(self):
        self.assertEqual(str(Decimal(self.ev._pi_scaled(30)) / 10 ** 30)[:8], "3.141592")
        self.assertEqual(str(Decimal(self.ev._ln_scaled(2, 1, 30)) / 10 ** 30)[:8],
                         "0.693147")
        self.assertEqual(str(Decimal(self.ev._sqrt_scaled(2, 30)) / 10 ** 30)[:8],
                         "1.414213")
        self.assertEqual(str(Decimal(self.ev._e_scaled(30)) / 10 ** 30)[:7], "2.71828")
        self.assertEqual(str(Decimal((10 ** 30 + self.ev._sqrt_scaled(5, 30)) // 2)
                             / 10 ** 30)[:7], "1.61803")

    def test_exact_claims_have_identically_zero_residuals(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            for claim in world["claims"]:
                if claim["kind"] != "exact":
                    continue
                total = Decimal(0)
                for name, coefficient in zip(claim["values"], claim["coefficients"]):
                    total += coefficient * Decimal(
                        self.ev._digits(world, name, 150))
                self.assertEqual(total, 0, (spec, claim["id"]))

    def test_hard_epsilons_are_visible_but_capped_epsilons_never(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            for value in world["values"]:
                sign, kappa = value["epsilon"] or (0, 0)
                if value["name"] == "q11" or value["name"] == "q12":
                    clean = sum(c * self.ev._basis_scaled(80)[k] for c, k in zip(
                        value["vector"], ("pi", "ln2", "ln3", "sqrt2", "e", "phi")))
                    with_epsilon = int(self.ev._digits(world, value["name"], 80)
                                       .replace(".", ""))
                    self.assertNotEqual(with_epsilon, clean)
                if value["cap"] < 70:
                    below = value["cap"] // 2
                    at_cap = int(self.ev._digits(world, value["name"], value["cap"])
                                 .replace(".", ""))
                    clean = sum(c * self.ev._basis_scaled(value["cap"])[k] for c, k in
                                zip(value["vector"],
                                    ("pi", "ln2", "ln3", "sqrt2", "e", "phi")))
                    # The epsilon below the cap can never appear in purchased digits.
                    self.assertEqual(at_cap, clean)

    def test_passive_floor_scores_zero_and_truth_scores_one(self):
        first = self.ev.evaluate(self.sol.audit_identity_claims)
        self.assertEqual(first["valid"], 1.0)
        self.assertLessEqual(abs(first["combined_score"]), 0.01)

        def truth(world):
            def candidate(problem, purchase, budget):
                verdicts, coefficients = {}, {}
                for claim in world["claims"]:
                    if claim["kind"] == "exact":
                        verdicts[claim["id"]] = "exact"
                        coefficients[claim["id"]] = list(claim["coefficients"])
                    elif claim["kind"] == "undecidable":
                        verdicts[claim["id"]] = "undecidable"
                    else:
                        verdicts[claim["id"]] = "false"
                return {"verdicts": verdicts, "coefficients": coefficients,
                        "confidence": 0.9}
            return candidate

        for spec in self.ev._BASE_DEVELOPMENT_SPECS:
            world = self.ev._world(spec)
            row = self.ev._evaluate_world(truth(world), spec, "dev", 0)
            self.assertAlmostEqual(row["normalized"], 1.0, places=9)

    def test_reference_deterministic_with_zero_false_discoveries(self):
        first = self.ev.evaluate(self.ref.audit_identity_claims)
        second = self.ev.evaluate(self.ref.audit_identity_claims)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))
        self.assertEqual(first["valid"], 1.0)
        self.assertGreater(first["combined_score"], 0.5)
        self.assertEqual(first["development_false_discovery_rate"], 0.0)

    def test_false_rejection_is_penalized_below_abstention(self):
        claim = {"id": "X", "values": ["a", "b", "c"], "kind": "exact",
                 "coefficients": [2, 3, 1]}
        self.assertEqual(self.ev._score_claim(claim, "undecidable", None), 0.0)
        self.assertEqual(self.ev._score_claim(claim, "false", None), -0.5)
        self.assertEqual(self.ev._score_claim(claim, "exact", [2, 3, 1]), 1.0)
        self.assertEqual(self.ev._score_claim(claim, "exact", [-2, -3, -1]), 1.0)

    def test_purchase_tiers_and_caps(self):
        world = self.ev._world(91011)
        library = self.ev._Library(world)
        with self.assertRaises(ValueError):
            library.purchase("q01", 55)
        self.assertTrue(library.violated)
        library2 = self.ev._Library(world)
        # A capped value truncates even when a higher tier is requested.
        report = library2.purchase("q13", 150)
        capped_value = next(v for v in world["values"] if v["name"] == "q13")
        self.assertEqual(len(report["digits"].split(".")[1]), capped_value["cap"])

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "audit"):
            result = self.ev.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
