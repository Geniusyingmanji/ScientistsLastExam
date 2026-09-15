"""Pinned invariants for the 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""


from __future__ import annotations


import importlib.util
import hashlib


import json


import subprocess


import sys


import tempfile


import unittest


from pathlib import Path
from _sandbox_tools import skip_unless_sandbox
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


TASKS = {'Mathematics/EllipticCurveRecovery': ('benchmarks/Mathematics/EllipticCurveRecovery',
                                       'recover_curve')}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RoundFourPackageTests(unittest.TestCase):
    def test_baselines_valid_zero_and_deterministic(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_" + entrypoint)
            baseline = _load(ROOT / directory / "solution.py",
                             "r4_baseline_" + entrypoint)
            first = evaluator.evaluate(getattr(baseline, entrypoint))
            second = evaluator.evaluate(getattr(baseline, entrypoint))
            self.assertEqual(first["valid"], 1.0, task_id)
            self.assertLessEqual(abs(first["combined_score"]), 0.01, task_id)
            self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                             json.dumps(second, sort_keys=True, default=str), task_id)

    def test_references_valid_and_above_floor(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_ref_" + entrypoint)
            reference = _load(ROOT / directory / "verification" / "reference_solver.py",
                              "r4_reference_" + entrypoint)
            result = evaluator.evaluate(getattr(reference, entrypoint))
            self.assertEqual(result["valid"], 1.0, task_id)
            self.assertGreater(result["combined_score"], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_bad_" + entrypoint)
            for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "junk"):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0, task_id)
                self.assertEqual(result["combined_score"], 0.0, task_id)


class EllipticCurvePins(unittest.TestCase):
    def test_public_budget_matches_evaluator_contract(self):
        task = ROOT / "benchmarks/Mathematics/EllipticCurveRecovery"
        ev = _load(task / "verification/evaluator.py", "ec_budget_contract")
        task_text = (task / "Task.md").read_text(encoding="utf-8")
        self.assertEqual(ev.BUDGET_UNITS, 5)
        self.assertIn("budget_units      5", task_text)

    def test_reference_recovers_with_real_evidence(self):
        task = ROOT / "benchmarks/Mathematics/EllipticCurveRecovery"
        ev = _load(task / "verification/evaluator.py", "ec_evidence")
        ref = _load(task / "verification/reference_solver.py", "ec_reference")
        result = ev.evaluate(ref.recover_curve)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], .5)
        self.assertLess(result["combined_score"], 1)
        for row in result['per_world']:
            if row['evidence_support_score']:
                self.assertEqual(row['compatible_curve_count'], 1)
                self.assertGreaterEqual(row['queried_prime_count'], 2)

    def test_counts_match_direct_enumeration(self):
        ev = _load("benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py",
                   "r4_ec")
        self.assertEqual(ev._legendre_count_cubic(11, 0, 1), 12)  # 11 + 1 + 0? direct:
        # y^2 = x^3 + 1 over F_11 has 12 points (a classical count).
        self.assertEqual(ev._legendre_count_cubic(7, 0, 0), 7 + 1 + 0)

    def test_singular_worlds_have_zero_discriminant(self):
        ev = _load("benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py",
                   "r4_ec")
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world["kind"] == "singular":
                self.assertEqual(4 * world["a"] ** 3 + 27 * world["b"] ** 2, 0)


@skip_unless_sandbox("bwrap")
class RunnerIntegrationTests(unittest.TestCase):
    """The black-box entrypoint must survive a real subprocess launch.

    Pins the 2026-09-07 fix for the unrendered-template artifacts: an f-string
    with literal ``{{...}}`` braces and a set-literal ``{{key: ...}}`` print that
    crashed the runner with ``TypeError: unhashable type: 'dict'`` *after* the
    metrics file was already written, so exit code 1 hid a completed evaluation.
    """

    SCORE_KEYS = ("combined_score", "raw_score", "robustness_score", "valid",
                  "development_evidence_support_score",
                  "heldout_evidence_support_score")

    def _run_entrypoint(self, candidate: str) -> tuple[int, dict, dict]:
        task = ROOT / "benchmarks/Mathematics/EllipticCurveRecovery"
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as private:
            metrics_path = Path(tmp) / "metrics.json"
            candidate_path = task / candidate
            completed = subprocess.run(
                [sys.executable, str(task / "frontier_eval/run_eval.py"),
                 "--candidate", str(candidate_path), "--metrics-out", str(metrics_path),
                 "--full-metrics-dir", private],
                cwd=ROOT, capture_output=True, text=True, timeout=480)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            stdout = json.loads(completed.stdout.strip().splitlines()[-1])
            public = json.loads(metrics_path.read_text())
            self.assertEqual(stdout, public)
            self.assertNotIn('robustness_score', public)
            self.assertNotIn('per_world', public)
            digest = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
            metrics = json.loads((Path(private) / (digest + '.json')).read_text())
        return completed.returncode, stdout, metrics

    def test_reference_exits_zero_and_reports_score_keys(self):
        returncode, stdout, metrics = self._run_entrypoint(
            "verification/reference_solver.py")
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout["valid"], 1.0)
        self.assertEqual(stdout["combined_score"], metrics["combined_score"])
        for key in self.SCORE_KEYS:
            self.assertIn(key, metrics)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertGreater(metrics["combined_score"], .5)
        self.assertGreater(metrics["robustness_score"], .5)
        self.assertNotIn("error_message", metrics)

    def test_literal_counter_does_not_survive_world_boundaries(self):
        returncode, stdout, metrics = self._run_entrypoint("verification/shortcut_memo_0.py")
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout['valid'], 1)
        self.assertEqual(stdout['combined_score'], 0)
        # The literal fixture's first answer is a claim, later entries include
        # abstention. Fresh workers must always start at that first entry.
        self.assertTrue(all(not row['abstained'] for row in metrics['per_world']))

    def test_caught_query_type_error_is_world_local_in_sandbox(self):
        task = ROOT / "benchmarks/Mathematics/EllipticCurveRecovery"
        ev = _load(task / "verification/evaluator.py", "ec_bad_query_boundary")
        world = ev._world(ev._BASE_DEVELOPMENT_SPECS[0])
        trigger = ev._legendre_count_cubic(97, world['a'], world['b'])
        source = (task / 'verification/reference_solver.py').read_text()
        source += """
_reference = recover_curve

def recover_curve(problem, count_points, budget_units):
    def wrapped(prime):
        report = count_points(prime)
        if prime == 97 and report['point_count'] == %d:
            try:
                count_points(11.0)
            except Exception:
                pass
        return report
    return _reference(problem, wrapped, budget_units)
""" % trigger
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / 'caught_query.py'
            candidate.write_text(source)
            returncode, stdout, metrics = self._run_entrypoint(str(candidate))
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout['valid'], 1)
        self.assertGreater(stdout['combined_score'], 0)
        self.assertGreater(metrics['feasibility_rate'], 0)
        self.assertLess(metrics['feasibility_rate'], 1)

    def test_baseline_exits_zero_with_a_written_metrics_file(self):
        returncode, stdout, metrics = self._run_entrypoint("solution.py")
        self.assertEqual(returncode, 0)
        self.assertEqual(stdout["valid"], 1.0)
        for key in self.SCORE_KEYS:
            self.assertIn(key, metrics)
        self.assertAlmostEqual(metrics["combined_score"], 0.0)



class ReviewContractRegressions(unittest.TestCase):
    def test_invalid_rows_are_not_discovery_attempts(self):
        ev = _load(ROOT / "benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py", "review_invalid")
        result = ev.evaluate(lambda *args: {})
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["development_discovery_attempt_count"], 0)
        self.assertEqual(result["development_discovery_coverage"], 0.0)
        self.assertEqual(result["heldout_discovery_attempt_count"], 0)
        self.assertEqual(result["heldout_discovery_coverage"], 0.0)
        self.assertGreater(result["heldout_unsupported_world_count"], 0)
        self.assertEqual(result["heldout_false_discovery_count"], 0)

    def test_runner_routes_through_trusted_harness_without_importing_candidate(self):
        import contextlib
        import io
        import tempfile
        import subprocess
        runner = _load(ROOT / "benchmarks/Mathematics/EllipticCurveRecovery/frontier_eval/run_eval.py", "review_runner")
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text("raise AssertionError('must never import here')\n")
            metrics = Path(tmp) / "metrics.json"
            completed = subprocess.CompletedProcess([], 0, '{"combined_score": 0.2, "valid": 1.0}', '')
            with patch.object(sys, "argv", ["run_eval.py", "--candidate", str(candidate), "--metrics-out", str(metrics)]), patch.object(runner.subprocess, "run", return_value=completed) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[1], str(ROOT / "sle/frontier_eval_entrypoint.py"))
            self.assertEqual(command[command.index("--task") + 1], "Mathematics/EllipticCurveRecovery")
            self.assertEqual(command[command.index("--candidate") + 1], str(candidate))
            self.assertNotIn("-m", command)


class ArithmeticScienceRegressions(unittest.TestCase):
    def setUp(self):
        self.ev = _load(ROOT / "benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py", "review_arithmetic")

    def test_quintic_counts_include_affine_roots_and_one_infinity(self):
        for coefficients in ([1, 0, 0, 0, 1, 0], [1, -2, 3, 0, 4, 1]):
            for prime in (11, 13, 17):
                direct = 1 + sum((y*y - sum(c * x**(5-i) for i, c in enumerate(coefficients))) % prime == 0 for x in range(prime) for y in range(prime))
                self.assertEqual(self.ev._legendre_count_quintic(prime, coefficients), direct)

    def test_refusal_worlds_are_smooth_genus_two_at_every_query_prime(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS:
            if spec[1] != "genus_two":
                continue
            world = self.ev._world(spec)
            coefficients = world["quintic"]
            self.assertEqual(len(coefficients), 6)
            self.assertEqual(coefficients[0], 1)
            for prime in self.ev.PRIME_LIST:
                self.assertTrue(self.ev._squarefree_mod_prime(coefficients, prime))
                count = self.ev._legendre_count_quintic(prime, coefficients)
                self.assertLessEqual(abs(count - prime - 1), 4 * prime**0.5)

    def test_fractional_coefficients_and_queries_do_not_truncate(self):
        for value in (11.1, "11", True):
            oracle = self.ev._ArithmeticOracle(self.ev._world((41011, "elliptic")))
            with self.assertRaises(ValueError):
                oracle.count_points(value)
            self.assertTrue(oracle.violated)
            self.assertEqual(oracle.used, 0)
        for value in (0.5, "0", False):
            with self.assertRaises(ValueError):
                self.ev._validate({"a": value, "b": 1, "abstain": False, "confidence": 0.5})
        self.ev._validate({"a": -3, "b": 2, "abstain": False, "confidence": 0.5})

    def test_confident_wrong_coefficients_do_not_get_perfect_calibration(self):
        row = self.ev._evaluate_world(lambda *args: {"a": 1200, "b": 1200, "abstain": False, "confidence": 1.0}, (41011, "elliptic"), "development", 0)
        self.assertTrue(row["valid"])
        self.assertLess(row["confidence_score"], 0.99)


if __name__ == "__main__":
    unittest.main()

class RevisionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = _load(ROOT / "benchmarks/Mathematics/EllipticCurveRecovery/verification/evaluator.py", "revision_ec")
        self.ref = _load(ROOT / "benchmarks/Mathematics/EllipticCurveRecovery/verification/reference_solver.py", "revision_ref")

    def test_literal_answers_and_one_prime_fingerprints_have_no_credit(self):
        specs = self.ev._BASE_DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS
        for n in (0, 1, 2):
            index = 0
            def memo(problem, count_points, budget):
                nonlocal index
                w = self.ev._world(specs[index]); index += 1
                for p in (97, 89)[:n]:
                    count_points(p)
                return {'a': w['a'] if w['kind'] == 'elliptic' else None,
                        'b': w['b'] if w['kind'] == 'elliptic' else None,
                        'abstain': w['kind'] != 'elliptic', 'confidence': 1.0}
            r = self.ev.evaluate(memo)
            self.assertEqual(r['valid'], 1)
            self.assertEqual(r['combined_score'], 0)
            self.assertEqual(r['robustness_score'], 0)

    def test_one_caught_bad_query_does_not_erase_other_worlds(self):
        calls = 0
        def partial(problem, count_points, budget):
            nonlocal calls
            calls += 1
            if calls == 1:
                try:
                    count_points(11.0)
                except ValueError:
                    pass
            return self.ref.recover_curve(problem, count_points, budget)
        r = self.ev.evaluate(partial)
        self.assertEqual(r['valid'], 1)
        self.assertGreater(r['combined_score'], 0)
        self.assertLess(r['feasibility_rate'], 1)

    def test_singular_claim_is_a_false_discovery_not_invalid(self):
        r = self.ev.evaluate(lambda *args: {'a': -3, 'b': 2, 'abstain': False, 'confidence': 1})
        self.assertEqual(r['valid'], 1)
        self.assertEqual(r['combined_score'], 0)
        self.assertEqual(r['development_false_discovery_rate'], 1)

    def test_singular_split_signatures_are_disjoint(self):
        signatures = []
        for specs in (self.ev._BASE_DEVELOPMENT_SPECS, self.ev.HELDOUT_SPECS):
            current = set()
            for spec in specs:
                if spec[1] != 'singular': continue
                w = self.ev._world(spec)
                current.add(tuple(self.ev._legendre_count_cubic(p,w['a'],w['b']) for p in self.ev.PRIME_LIST))
            signatures.append(current)
        self.assertFalse(signatures[0] & signatures[1])
        self.assertGreaterEqual(len(signatures[0]), 3)

    def test_q_isomorphic_worlds_have_indistinguishable_bounded_twins(self):
        for specs in (self.ev._BASE_DEVELOPMENT_SPECS, self.ev.HELDOUT_SPECS):
            for spec in specs:
                if spec[1] != 'isomorphic': continue
                w = self.ev._world(spec); a,b = w['a'], w['b']
                self.assertLessEqual(abs(16*a), self.ev.COEFFICIENT_BOUND)
                self.assertLessEqual(abs(64*b), self.ev.COEFFICIENT_BOUND)
                for p in self.ev.PRIME_LIST:
                    self.assertEqual(self.ev._legendre_count_cubic(p,a,b), self.ev._legendre_count_cubic(p,16*a,64*b))

    def test_trusted_compatibility_matches_independent_brute_force(self):
        bound = 12
        for truth in ((1,1),(-3,2),(4,-5)):
            transcript = [(p,self.ev._legendre_count_cubic(p,*truth)) for p in (11,13)]
            expected = {(a,b) for a in range(-bound,bound+1) for b in range(-bound,bound+1)
                        if all(self.ev._legendre_count_cubic(p,a,b)==n for p,n in transcript)}
            actual = self.ev._arithmetic.compatible_pairs(transcript,bound)
            self.assertEqual({tuple(row) for row in actual},expected)

    def test_spurious_empty_and_singular_only_worlds_are_distinct(self):
        for kind in ('singular','genus_two'):
            for spec in self.ev._BASE_DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS:
                if spec[1] != kind: continue
                w = self.ev._world(spec); oracle = self.ev._ArithmeticOracle(w)
                for p in (97,89,83,79,73): oracle.count_points(p)
                pairs = self.ev._arithmetic.compatible_pairs(oracle.transcript, self.ev.COEFFICIENT_BOUND)
                if kind == 'genus_two':
                    self.assertEqual(len(pairs), 0)
                else:
                    self.assertGreater(len(pairs), 0)
                    self.assertEqual(len(self.ev._arithmetic.nonsingular(pairs)), 0)
