"""Pinned invariants for the 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""


from __future__ import annotations


import importlib.util


import json


import sys


import unittest


from pathlib import Path
from _sandbox_tools import skip_unless_sandbox
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


TASKS = {'Algorithm/ScalingLawIdentification': ('benchmarks/ComputerScience/ScalingLawIdentification',
                                        'identify_scaling_law')}


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


class ScalingLawPins(unittest.TestCase):
    def setUp(self):
        task = ROOT / "benchmarks/ComputerScience/ScalingLawIdentification"
        self.ev = _load(task / "verification/evaluator.py", "scale_ev")
        self.ref = _load(task / "verification/reference_solver.py", "scale_ref")

    def test_design_is_public_and_within_budget_on_each_domain(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS:
            world = self.ev._world(spec)
            problem = self.ev.problem_statement(world)
            sizes = self.ref.design(problem, self.ev.BUDGET_UNITS)
            self.assertTrue(all(world["bounds"][0] <= n <= world["bounds"][1] for n in sizes))
            self.assertLessEqual(sum(self.ev._call_cost(n) for n in sizes), self.ev.BUDGET_UNITS)

    def test_ambiguity_has_a_policy_independent_information_bound(self):
        for spec in self.ev._BASE_DEVELOPMENT_SPECS + self.ev.HELDOUT_SPECS:
            if spec[1] != "ambiguous":
                continue
            world = self.ev._world(spec)
            kl, accuracy = self.ev.ambiguity_information_bound(world)
            self.assertLess(kl, .13)
            self.assertLess(accuracy, .63)
            self.assertGreater(accuracy, .5)

    def test_two_refusal_checks_have_different_jobs(self):
        full = self.ev.evaluate(self.ref.identify_scaling_law)
        for key in ("adequacy", "separation"):
            reduced = self.ev.evaluate(lambda *a: self.ref.solve(*a, **{key: False}))
            self.assertEqual(reduced["valid"], 1.)
            self.assertGreater(reduced["development_false_discovery_rate"],
                               full["development_false_discovery_rate"])
        # A narrow domain alone is not a refusal label.
        world = self.ev._world((30053, "supported_narrow", "exponential"))
        lab = self.ev._Profiler(world)
        answer = self.ref.identify_scaling_law(self.ev.problem_statement(world), lab.time_run, self.ev.BUDGET_UNITS)
        self.assertFalse(answer["abstain"])

    def test_narrow_control_cannot_be_identified_from_public_metadata(self):
        ambiguous = self.ev._world((30047, "ambiguous", "linear"))
        supported = self.ev._world((30053, "supported_narrow", "exponential"))
        self.assertEqual(self.ev.problem_statement(ambiguous), self.ev.problem_statement(supported))

    def test_integer_valued_floats_preserve_reference_results(self):
        import numpy as np
        expected = self.ev.evaluate(self.ref.identify_scaling_law)
        for cast in (float, np.float64, np.int64):
            actual = self.ev.evaluate(lambda p, lab, b: self.ref.identify_scaling_law(p, lambda n: lab(cast(n)), b))
            self.assertEqual(expected, actual)

    def test_one_invalid_world_does_not_erase_valid_worlds(self):
        calls = 0
        def candidate(*args):
            nonlocal calls
            calls += 1
            return {} if calls == 1 else self.ref.identify_scaling_law(*args)
        result = self.ev.evaluate(candidate)
        self.assertEqual(result["valid"], 1.)
        self.assertGreater(result["combined_score"], 0.)
        self.assertLess(result["feasibility_rate"], 1.)


@skip_unless_sandbox("bwrap")
class ScalingLawRunnerIntegration(unittest.TestCase):
    """Launch frontier_eval/run_eval.py exactly as eval_command.txt does.

    The shipped runner was once an unrendered template: it wrote the metrics file
    and then died on a doubled-brace set literal, so every entrypoint run exited
    nonzero. This test executes the real command line so that class of defect
    cannot come back unnoticed.
    """

    def test_runner_executes_reference_end_to_end(self):
        import subprocess
        import tempfile

        task = ROOT / "benchmarks/ComputerScience/ScalingLawIdentification"
        command = [
            sys.executable, "frontier_eval/run_eval.py",
            "--candidate", str((task / "verification" / "reference_solver.py").resolve()),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / "public"
            public.mkdir()
            private = Path(tmp) / "trusted"
            metrics_path = public / "metrics.json"
            command += ["--metrics-out", str(metrics_path),
                        "--full-metrics-dir", str(private)]
            completed = subprocess.run(command, cwd=str(task), capture_output=True,
                                       text=True, timeout=300)
            self.assertEqual(completed.returncode, 0, completed.stderr[-500:])
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(set(metrics), {"combined_score", "valid", "raw_score",
                                            "feasibility_rate"})
            sidecars = list(private.glob("*.json"))
            self.assertEqual(len(sidecars), 1)
            full = json.loads(sidecars[0].read_text())
            for key in ("robustness_score", "mechanism_score", "per_world"):
                self.assertIn(key, full)
                self.assertNotIn(key, metrics)
            self.assertEqual(metrics["valid"], 1.0)
            self.assertNotIn("error_message", metrics)
            reported = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertEqual(reported["combined_score"], metrics["combined_score"])



class ReviewContractRegressions(unittest.TestCase):
    def test_invalid_rows_are_not_discovery_attempts(self):
        ev = _load(ROOT / "benchmarks/ComputerScience/ScalingLawIdentification/verification/evaluator.py", "review_invalid")
        result = ev.evaluate(lambda *args: {})
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["development_discovery_attempt_count"], 0)
        self.assertEqual(result["development_discovery_coverage"], 0.0)
        self.assertEqual(result["heldout_discovery_attempt_count"], 0)
        self.assertEqual(result["heldout_discovery_coverage"], 0.0)
        self.assertGreater(result["heldout_unsupported_world_count"], 0)
        self.assertEqual(result["heldout_false_discovery_count"], 0)

    def test_runner_discards_stale_score_after_trusted_entrypoint_failure(self):
        import contextlib
        import io
        import tempfile
        import subprocess
        runner = _load(ROOT / "benchmarks/ComputerScience/ScalingLawIdentification/frontier_eval/run_eval.py", "review_runner")
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text("raise AssertionError('must never import here')\n")
            metrics = Path(tmp) / "metrics.json"
            metrics.write_text('{"combined_score": 1, "valid": 1}')
            completed = subprocess.CompletedProcess([], 2, '', 'trusted infrastructure failure')
            stdout = io.StringIO()
            with patch.object(runner.subprocess, "run", return_value=completed), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                result = runner.main(["--candidate", str(candidate), "--metrics-out", str(metrics)])
            self.assertEqual(result, 2)
            self.assertFalse(metrics.exists())
            self.assertEqual(stdout.getvalue(), "")


class ProfilingContractRegressions(unittest.TestCase):
    def setUp(self):
        self.ev = _load(ROOT / "benchmarks/ComputerScience/ScalingLawIdentification/verification/evaluator.py", "review_profiling")

    def test_fractional_sizes_fail_closed_even_if_candidate_catches(self):
        for value in (16.5, "16", True):
            profiler = self.ev._Profiler(self.ev._world((30011, "supported", "constant")))
            with self.assertRaises(ValueError):
                profiler.time_run(value)
            self.assertTrue(profiler.violated)
            self.assertEqual(profiler.used, 0)

    def test_probability_values_must_be_scalars_with_exact_vector_shape(self):
        probabilities = {name: [1.0 / len(self.ev.CLASSES)] for name in self.ev.CLASSES}
        with self.assertRaises(ValueError):
            self.ev._validate({"class_probabilities": probabilities, "scale": 1.0, "abstain": False, "confidence": 0.5})

    def test_wrong_law_is_not_awarded_perfect_confidence(self):
        def wrong(*args):
            return {"class_probabilities": {name: float(name == "exponential") for name in self.ev.CLASSES}, "scale": 1.0, "abstain": False, "confidence": 1.0}
        row = self.ev._evaluate_world(wrong, (30011, "supported", "constant"), "development", 0)
        self.assertTrue(row["valid"])
        self.assertLess(row["confidence_score"], 0.01)


if __name__ == "__main__":
    unittest.main()


def test_information_bound_matches_explicit_paired_likelihoods():
    import math
    task = ROOT / 'benchmarks/ComputerScience/ScalingLawIdentification'
    ev = _load(task / 'verification/evaluator.py', 'paired_likelihood_test')
    world = ev._world((30047, 'ambiguous', 'linear'))
    lo, hi = world['bounds']
    midpoint = math.sqrt(math.log2(lo)*math.log2(hi))
    counterpart = dict(world, family='linearithmic', scale=world['scale']/midpoint)
    per_cost = []
    for size in range(lo, hi+1):
        gap = math.log(ev._true_runtime(world, size)/ev._true_runtime(counterpart, size))
        per_cost.append(gap*gap/(2*world['noise']**2*ev._call_cost(size)))
    assert abs(ev.ambiguity_information_bound(world)[0] - ev.BUDGET_UNITS*max(per_cost)) < 1e-12


def test_extrapolation_uses_probability_mass_instead_of_argmax():
    task = ROOT / 'benchmarks/ComputerScience/ScalingLawIdentification'
    ev = _load(task / 'verification/evaluator.py', 'weighted_extrapolation_test')
    spec = (30011, 'supported', 'constant')
    world = ev._world(spec)
    def candidate(*args):
        return {'class_probabilities': {name: .5 if name in ('constant', 'exponential') else 0.
                                         for name in ev.CLASSES},
                'scale': world['scale'], 'abstain': False, 'confidence': .8}
    row = ev._evaluate_world(candidate, spec, 'development', 0)
    assert row['valid']
    assert abs(row['extrapolation_score']-.5) < 1e-12
