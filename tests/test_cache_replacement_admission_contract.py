"""Bounded admission fixtures; no complete learner screen or model calls."""
from __future__ import annotations

import importlib.util
import random
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _sandbox_tools import skip_unless_sandbox
from sle.secure_eval import CandidateProxy

TASK = ROOT / "benchmarks/ComputerScience/CacheReplacementPolicyID"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CacheReplacementAdmissionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = load(TASK / "verification/evaluator.py", "cache_admission_evaluator")
        cls.ref = load(TASK / "verification/reference_permutation_augmented.py", "cache_augmented_reference")

    def test_caught_malformed_trace_never_earns_refusal_credit(self):
        for trace in ([], [False], [-1], [2 ** 31], [0.5], "0123", [0] * 4097):
            def candidate(_problem, run):
                try:
                    run(trace)
                except (ValueError, TypeError):
                    pass
                return {"abstain": True}
            metrics = self.ev.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0, trace)
            self.assertEqual(metrics["feasibility_rate"], 0.0, trace)
            for row in metrics["per_instance"]:
                self.assertFalse(row["valid"], row)
                self.assertEqual(row["mechanism_score"], 0.0, row)
                self.assertFalse(row["correct_refusal"], row)

    def test_ratios_recompute_from_planned_world_counts(self):
        for candidate in (lambda _p, _r: {"abstain": True}, lambda _p, _r: {}):
            metrics = self.ev.evaluate(candidate)
            for split in ("development", "heldout"):
                rows = [r for r in metrics["per_instance"] if r["split"] == split]
                det = [r for r in rows if r["kind"] == "deterministic"]
                unsupported = [r for r in rows if r["kind"] == "randomized"]
                prefix = split + "_"
                self.assertEqual(metrics[prefix + "world_count"], len(rows))
                self.assertEqual(metrics[prefix + "determinable_world_count"], len(det))
                self.assertEqual(metrics[prefix + "unsupported_world_count"], len(unsupported))
                for count, rate, denominator in (
                    ("correct_refusal_count", "correct_refusal_rate", len(unsupported)),
                    ("discovery_attempt_count", "discovery_coverage", len(det)),
                ):
                    self.assertEqual(metrics[prefix + rate], metrics[prefix + count] / denominator)
                claims = [r for r in rows if r["valid"] and not r["abstained"]]
                false_claims = sum(r["false_discovery"] for r in claims)
                self.assertEqual(metrics[prefix + "policy_claim_count"], len(claims))
                self.assertEqual(metrics[prefix + "false_claim_count"], false_claims)
                self.assertEqual(metrics[prefix + "false_discovery_rate"], false_claims / len(claims) if claims else 0.0)
                expected = max(0.0, (sum(r["mechanism_score"] for r in rows) - len(unsupported)) / len(det))
                self.assertAlmostEqual(metrics[prefix + "mechanism_score"], expected)

    def test_claim_conditional_fdr_excludes_refusals_and_invalid_worlds(self):
        def row(kind, valid=True, abstained=False, false=False, recovered=False, score=0.0):
            return {"kind": kind, "valid": valid, "abstained": abstained,
                    "false_discovery": false, "recovered": recovered, "mechanism_score": score,
                    "correct_refusal": kind == "randomized" and valid and abstained,
                    "confidence_calibration_score": 0.0, "runs_used": 0}
        rows = [row("deterministic", recovered=True, score=1.0),
                row("deterministic", false=True, score=-1.0),
                row("deterministic", abstained=True),
                row("deterministic", valid=False, abstained=True),
                row("randomized", abstained=True, score=1.0),
                row("randomized", false=True),
                row("randomized", valid=False, abstained=True)]
        summary = self.ev._split_summary(rows)
        self.assertEqual(summary["false_claim_count"], 2)
        self.assertEqual(summary["policy_claim_count"], 3)
        self.assertEqual(summary["false_discovery_rate"], 2 / 3)
        self.assertEqual(summary["false_claim_world_rate"], 2 / 7)
        self.assertEqual(summary["discovery_coverage"], 2 / 4)
        self.assertEqual(summary["correct_refusal_rate"], 1 / 3)

    @skip_unless_sandbox("bwrap")
    def test_caught_malformed_trace_remains_invalid_through_real_rpc(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text("def identify(problem, run):\n"
                                 "    try:\n        run([])\n"
                                 "    except Exception:\n        pass\n"
                                 "    return {'abstain': True}\n", encoding="utf-8")
            with CandidateProxy(candidate, "identify", timeout_s=60) as proxy:
                result = self.ev.evaluate(proxy)
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(len(result["per_instance"]), 18)
        for row in result["per_instance"]:
            self.assertFalse(row["valid"], row)
            self.assertFalse(row["correct_refusal"], row)
            self.assertEqual(row["mechanism_score"], 0.0, row)

    def test_written_permutation_tables_match_recorded_generator_seeds(self):
        engine = load(ROOT / ".research/cache_policy/engine.py", "cache_builder_engine")
        sources = {
            "dev-03": engine.random_permutation_policy(4, 101),
            "dev-04": engine.lip_like(4, 2, 6),
            "dev-06": engine.lip_like(6, 0, 1),
            "held-02": engine.random_permutation_policy(4, 606),
            "held-03": engine.lip_like(6, 0, 9),
        }
        for spec in self.ev.DEVELOPMENT_WORLDS + self.ev.HELDOUT_WORLDS:
            if spec["name"] in sources:
                actual, generated = spec["policy"](), sources[spec["name"]]
                self.assertEqual(actual.hp, tuple(generated.hp))
                self.assertEqual(actual.mp, generated.mp)
                self.assertEqual(actual.start, generated.start)

    def test_permutation_inference_algebra_with_exact_victim_fixture(self):
        # This exercises algebra only, not noise, budget sufficiency or admission.
        engine = load(ROOT / ".research/cache_policy/engine.py", "cache_builder_engine_fixture")
        for policy in (engine.lip_like(4, 0, 7), engine.lip_like(6, 0, 1)):
            class VictimFixture:
                W = policy.W

                def victim(self, prefix):
                    state = policy.reset()
                    for symbol in prefix:
                        state = policy.miss(state)[1] if symbol == "M" else policy.hit(state, symbol)
                    return policy.miss(state)[0]
            inferred = self.ref._fit_permutation(VictimFixture())
            truth = self.ev.policy_machine(policy)
            self.assertIsNotNone(inferred)
            self.assertIsNone(self.ev.distinguishing_word(inferred, truth))

    def test_augmented_reference_uses_permutation_family_before_generic_learner(self):
        machine = (1, [[0] * 4], [(0, 0)])
        with patch.object(self.ref, "_random_looking", return_value=False), \
                patch.object(self.ref, "_fit_library", return_value=None), \
                patch.object(self.ref, "_fit_permutation", return_value=machine) as fit, \
                patch.object(self.ref, "_check", return_value=None), \
                patch.object(self.ref, "_LStar", side_effect=AssertionError("must first use fitted family")):
            self.assertEqual(self.ref._learn(object(), random.Random(0)), machine)
            fit.assert_called_once()
        source = (TASK / "verification/reference_permutation_augmented.py").read_text()
        self.assertNotIn("import evaluator", source)
        self.assertNotIn("import engine", source)
        self.assertNotIn("DEVELOPMENT_WORLDS", source)

    def test_reset_failure_escapes_scientific_scoring(self):
        class BrokenReset:
            def reset_session(self):
                raise RuntimeError("isolation unavailable")
        with self.assertRaisesRegex(RuntimeError, "isolation unavailable"):
            self.ev.evaluate(BrokenReset())

    @skip_unless_sandbox("bwrap")
    def test_real_process_tmpfs_and_import_state_reset_across_all_worlds(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent('''
                import os
                import random
                calls = 0
                def identify(problem, run):
                    global calls
                    calls += 1
                    marker = "/tmp/cache-policy-world-state"
                    if calls != 1 or os.path.exists(marker) or getattr(random, "_cache_policy_seen", False):
                        raise RuntimeError("state crossed a scientific world boundary")
                    random._cache_policy_seen = True
                    with open(marker, "w") as handle:
                        handle.write("within-world")
                    first = run([0])
                    second = run([0])
                    if len(first) != 1 or len(second) != 1 or calls != 1:
                        raise RuntimeError("callback did not preserve world session")
                    with open(marker) as handle:
                        if handle.read() != "within-world":
                            raise RuntimeError("tmpfs changed inside world")
                    return {"abstain": True}
            '''), encoding="utf-8")
            with CandidateProxy(candidate, "identify", timeout_s=60) as proxy:
                result = self.ev.evaluate(proxy)
        rows = result["per_instance"]
        self.assertEqual(len(rows), 18)
        self.assertEqual({r["split"] for r in rows}, {"development", "heldout"})
        specs = self.ev.DEVELOPMENT_WORLDS + self.ev.HELDOUT_WORLDS
        for row, spec in zip(rows, specs):
            self.assertTrue(row["valid"], row)
            self.assertEqual(row["runs_used"], 2 * (spec["policy"]().W + 1))
