"""Pinned invariants for the 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""


from __future__ import annotations


import io
import importlib.util


import json


import sys
import tempfile
import unittest


from pathlib import Path
from unittest import mock


from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]


TASKS = {'Electrochemistry/ChronoamperometryLawID': ('benchmarks/Chemistry/ChronoamperometryLawID',
                                             'identify_current_law'),
 'Electrophysiology/HodgkinHuxleyCurrentID': ('benchmarks/Biology/HodgkinHuxleyCurrentID',
                                              'recover_channel_parameters')}

RUNNERS = {
    "Electrophysiology/HodgkinHuxleyCurrentID":
        "benchmarks/Biology/HodgkinHuxleyCurrentID",
    "Electrochemistry/ChronoamperometryLawID":
        "benchmarks/Chemistry/ChronoamperometryLawID",
    "Spectroscopy/MassFragmentationTree":
        "benchmarks/Chemistry/MassFragmentationTree",
    "ChemicalProcess/ThermochemicalCycleAudit":
        "benchmarks/Chemistry/ThermochemicalCycleAudit",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BlackBoxRunnerTests(unittest.TestCase):
    def test_runners_delegate_to_sandbox_and_emit_valid_json(self):
        expected = {"combined_score": 0.25, "valid": 1.0}
        completed = mock.Mock(returncode=0, stdout=json.dumps(expected), stderr="")

        for index, (task_id, directory) in enumerate(RUNNERS.items()):
            runner_path = ROOT / directory / "frontier_eval/run_eval.py"
            source = runner_path.read_text(encoding="utf-8")
            self.assertNotIn("spec_from_file_location", source, task_id)
            self.assertNotIn("import evaluator", source, task_id)
            runner = _load(runner_path, "r4_runner_%d" % index)

            with tempfile.TemporaryDirectory() as tmp:
                metrics_path = Path(tmp) / "metrics.json"
                argv = [str(runner_path), "--candidate", str(ROOT / directory / "solution.py"),
                        "--metrics-out", str(metrics_path)]
                output = io.StringIO()
                with mock.patch.object(sys, "argv", argv), \
                     mock.patch.object(runner.subprocess, "run", return_value=completed) as run, \
                     redirect_stdout(output):
                    self.assertEqual(runner.main(), 0, task_id)

                command = run.call_args.args[0]
                self.assertEqual(Path(command[1]), ROOT / "sle/frontier_eval_entrypoint.py",
                                 task_id)
                self.assertEqual(command[command.index("--task") + 1], task_id)
                self.assertEqual(command[command.index("--metrics-out") + 1],
                                 str(metrics_path))
                self.assertEqual(json.loads(output.getvalue()), expected)


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
            self.assertEqual(first["combined_score"], 0.0, task_id)
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


class ChronoamperometryPins(unittest.TestCase):
    def test_reference_is_accurate_without_saturating_the_score(self):
        task = ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
        ev = _load(task / "verification/evaluator.py", "r4_chrono_calibration")
        ref = _load(task / "verification/reference_solver.py", "r4_chrono_reference")
        result = ev.evaluate(ref.identify_current_law)
        self.assertEqual(result["valid"], 1.0)
        self.assertGreater(result["combined_score"], 0.60)
        self.assertLessEqual(result["combined_score"], 0.80)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)

    def test_refusal_gates_have_distinct_development_worlds(self):
        task = ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
        ev = _load(task / "verification/evaluator.py", "r4_chrono_gate_eval")
        ref = _load(task / "verification/reference_solver.py", "r4_chrono_gate_ref")
        full = ev.evaluate(ref.identify_current_law)
        with mock.patch.object(ref, "CHI_SQUARE_PER_DOF_GATE", 1e9):
            no_shape_gate = ev.evaluate(ref.identify_current_law)
        with mock.patch.object(ref, "DRIFT_Z_GATE", 1e9):
            no_drift_gate = ev.evaluate(ref.identify_current_law)
        self.assertEqual(full["development_correct_refusal_rate"], 1.0)
        self.assertEqual(no_shape_gate["development_correct_refusal_rate"], 0.5)
        self.assertEqual(no_drift_gate["development_correct_refusal_rate"], 0.5)

    def test_one_step_probe_stays_below_reference(self):
        task = ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
        ev = _load(task / "verification/evaluator.py", "r4_chrono_probe_eval")
        ref = _load(task / "verification/reference_solver.py", "r4_chrono_probe_ref")
        probe = _load(task / "verification/probe_one_step.py", "r4_chrono_probe")
        reference = ev.evaluate(ref.identify_current_law)
        shortcut = ev.evaluate(probe.identify_current_law)
        self.assertEqual(shortcut["valid"], 1.0)
        self.assertLess(shortcut["combined_score"], 0.9 * reference["combined_score"])

    def test_padding_slots_are_free_but_active_slots_bounded(self):
        ev = _load(ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
                   "/verification/evaluator.py", "r4_chrono")
        # Two-parameter family (catalytic) with padded zeros must validate.
        submission = {"family_probabilities": {name: 1 / 6 for name in ev.FAMILIES},
                      "parameters": [1.0, 0.5, 0.0], "abstain": False,
                      "confidence": 0.5}
        probs, params, confidence, abstain = ev._validate(submission)
        self.assertFalse(abstain)
        self.assertEqual(ev._active_count("catalytic"), 2)

    def test_drift_is_shared_linear_across_potentials(self):
        ev = _load(ROOT / "benchmarks/Chemistry/ChronoamperometryLawID"
                   "/verification/evaluator.py", "r4_chrono")
        world = ev._world((12047, "drift", "catalytic"))
        lo, hi = 0.15, 0.85
        clean_lo = ev._true_current(world, lo)
        clean_hi = ev._true_current(world, hi)
        ratio = ev.amplitude_factor(lo) / ev.amplitude_factor(hi)
        # The family part scales with phi(E); the shared linear drift does not, so
        # the scaled difference grows linearly in time.
        residual = clean_hi - clean_lo / ratio
        self.assertLess(abs(residual[0]), 1e-3)
        self.assertGreater(abs(residual[-1]), 0.5)


class HodgkinHuxleyPins(unittest.TestCase):
    def test_reference_uses_the_complete_public_budget(self):
        ev = _load(ROOT / "benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh_budget_eval")
        ref = _load(ROOT / "benchmarks/Biology/HodgkinHuxleyCurrentID/verification/reference_solver.py",
                    "r4_hh_budget_ref")
        result = ev.evaluate(ref.recover_channel_parameters)
        self.assertEqual(ev.BUDGET_UNITS, len(ref.PROTOCOLS))
        self.assertTrue(all(row["budget_used"] == ev.BUDGET_UNITS
                            for row in result["per_world"]))

    def test_two_protocol_probe_stays_below_reference(self):
        task = ROOT / "benchmarks/Biology/HodgkinHuxleyCurrentID"
        ev = _load(task / "verification/evaluator.py", "r4_hh_probe_eval")
        ref = _load(task / "verification/reference_solver.py", "r4_hh_probe_ref")
        probe = _load(task / "verification/probe_two_protocols.py", "r4_hh_probe")
        reference = ev.evaluate(ref.recover_channel_parameters)
        shortcut = ev.evaluate(probe.recover_channel_parameters)
        self.assertEqual(shortcut["valid"], 1.0)
        self.assertLess(shortcut["combined_score"], 0.9 * reference["combined_score"])

    def test_a_type_current_has_a_transient_from_holding_inactivation(self):
        ev = _load(ROOT / "benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh_a_type")
        parameters = [120.0, 36.0, 0.3, 50.0, -77.0, -54.4, 0.0, 0.0]
        time, gates = ev._gating_traces(30.0, 30.0)
        extra = (ev.ionic_current(parameters, 30.0, gates, "a_type")
                 - ev.ionic_current(parameters, 30.0, gates))
        # A depolarizing clamp releases holding-state availability, then the
        # extra current inactivates on the stated fast 20 ms time scale.
        self.assertGreater(float(extra.max()), 500.0)
        self.assertGreater(float(extra.max()), 2.0 * float(extra[-1]))

    def test_absolute_voltage_matches_classic_resting_gate_values(self):
        ev = _load(ROOT / "benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh_voltage_convention")
        with mock.patch.object(ev, "HOLDING", -65.0):
            _, gates = ev._gating_traces(-65.0, 5.0)
        # Independent published HH equilibrium values at absolute V = -65 mV.
        expected = (0.0529324853, 0.5961207535, 0.3176769141)
        for column, value in enumerate(expected):
            self.assertAlmostEqual(float(gates[0, column]), value, places=8)
            self.assertAlmostEqual(float(gates[-1, column]), value, places=8)

    def test_rate_forms_are_stable_at_singular_points(self):
        ev = _load("benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh")
        self.assertAlmostEqual(ev.alpha_m(25.0), 1.0, places=6)
        self.assertAlmostEqual(ev.alpha_n(10.0), 0.1, places=6)

    def test_gating_relaxes_from_holding(self):
        ev = _load("benchmarks/Biology/HodgkinHuxleyCurrentID/verification/evaluator.py",
                   "r4_hh")
        time, gating = ev._gating_traces(30.0, 20.0)
        # m activates and h inactivates from the -80 mV holding steady state.
        self.assertGreater(gating[-1, 0], gating[0, 0])
        self.assertLess(gating[-1, 1], gating[0, 1])


if __name__ == "__main__":
    unittest.main()
