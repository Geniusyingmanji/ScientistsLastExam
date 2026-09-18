"""Tests for the degenerate-policy probe.

The probe's whole claim is that its policies are *well-formed* submissions - the reference's
own answer with one flag moved - rather than malformed candidates that any oracle rejects.
These tests pin that: the rewrite reaches a claim committed through a callback, an abstention
withdraws the assertions that would contradict it, and no verdict is reported for an axis
whose input the probe never touched.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "audit_discovery_discrimination", ROOT / "scripts/audit_discovery_discrimination.py")
MODULE = importlib.util.module_from_spec(_spec)
_argv = sys.argv
sys.argv = ["audit_discovery_discrimination"]
try:
    _spec.loader.exec_module(MODULE)
finally:
    sys.argv = _argv


class SetAbstainTests(unittest.TestCase):
    def test_rewrites_a_top_level_flag(self):
        payload = {"abstain": False, "value": 3}
        self.assertEqual(MODULE._set_abstain(payload, True), 1)
        self.assertIs(payload["abstain"], True)

    def test_rewrites_a_nested_flag(self):
        payload = {"preconfirmation": {"abstain": False}, "post": {"abstain": False}}
        self.assertEqual(MODULE._set_abstain(payload, True), 2)
        self.assertIs(payload["preconfirmation"]["abstain"], True)
        self.assertIs(payload["post"]["abstain"], True)

    def test_depth_is_bounded(self):
        deep = {"abstain": False}
        for _ in range(MODULE.MAX_REWRITE_DEPTH + 2):
            deep = {"nest": deep}
        self.assertEqual(MODULE._set_abstain(deep, True), 0)

    def test_abstaining_withdraws_a_contradicting_claim(self):
        # ProspectiveMetaAnalysis raises `an abstaining model cannot claim benefit`, so a probe
        # that only flips `abstain` scores a crash rather than a refusal.
        payload = {"abstain": False, "claim_beneficial": True}
        MODULE._set_abstain(payload, True)
        self.assertIs(payload["claim_beneficial"], False)

    def test_claiming_leaves_the_claim_fields_alone(self):
        payload = {"abstain": True, "claim_beneficial": False}
        MODULE._set_abstain(payload, False)
        self.assertIs(payload["claim_beneficial"], False)

    def test_a_submission_with_no_flag_reports_nothing_moved(self):
        self.assertEqual(MODULE._set_abstain({"parameters": [1, 2]}, True), 0)


class FakeProxy:
    """Stands in for the sandboxed candidate: records its calls, answers from a script."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.resets = 0

    def reset_session(self):
        self.resets += 1

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return copy.deepcopy(self.answers[len(self.calls) - 1])


class PolicyTests(unittest.TestCase):
    def test_reference_policy_passes_the_answer_through(self):
        proxy = FakeProxy([{"abstain": False, "x": 1}])
        policy = MODULE.Policy(proxy)
        self.assertEqual(policy({}), {"abstain": False, "x": 1})
        self.assertEqual(policy.calls, 1)

    def test_reset_session_is_forwarded(self):
        proxy = FakeProxy([{"abstain": False}])
        MODULE.Policy(proxy).reset_session()
        self.assertEqual(proxy.resets, 1)

    def test_claim_all_rewrites_the_returned_answer(self):
        proxy = FakeProxy([{"abstain": True}])
        policy = MODULE.ClaimAll(proxy)
        self.assertEqual(policy({}), {"abstain": False})
        self.assertEqual(policy.rewrites, 1)
        self.assertEqual(policy.callback_rewrites, 0)

    def test_the_rewrite_reaches_a_claim_committed_through_a_callback(self):
        committed = []

        def confirm(artifact):
            committed.append(artifact)
            return {"result": 1}

        proxy = FakeProxy([{"abstain": True}])
        policy = MODULE.ClaimAll(proxy)
        policy({}, confirm)
        # The oracle handed the candidate a tool; the probe must rewrite what goes into it,
        # because that artifact is what the false-discovery axis reads.
        wrapped = proxy.calls[0][0][1]
        wrapped({"abstain": True, "claim_beneficial": False})
        self.assertEqual(committed, [{"abstain": False, "claim_beneficial": False}])
        self.assertEqual(policy.callback_rewrites, 1)

    def test_a_task_with_no_flag_anywhere_is_not_applicable(self):
        proxy = FakeProxy([{"parameters": [1.0]}])
        with self.assertRaises(MODULE.NotApplicable):
            MODULE.AbstainAll(proxy)({})

    def test_constant_answer_replays_the_first_world(self):
        proxy = FakeProxy([{"abstain": False, "x": 1}, {"abstain": False, "x": 2}])
        policy = MODULE.ConstantAnswer(proxy)
        first = policy({})
        second = policy({})
        self.assertEqual(second, {"abstain": False, "x": 1})
        # A deep copy each time, so an oracle that consumes the submission cannot change what
        # the next world receives.
        first["x"] = 99
        self.assertEqual(policy({})["x"], 1)
        self.assertEqual(len(proxy.calls), 1)


class SaturationTests(unittest.TestCase):
    def test_an_axis_at_its_best_value_is_saturated(self):
        metrics = {"heldout_correct_refusal_rate": 1.0,
                   "development_false_discovery_rate": 0.0,
                   "development_mechanism_score": 0.5}
        self.assertEqual(MODULE.saturated_axes(metrics),
                         ["development_false_discovery_rate", "heldout_correct_refusal_rate"])

    def test_booleans_and_text_are_not_axes(self):
        self.assertEqual(MODULE.saturated_axes({"valid_flag_coverage": True, "note": "x"}), [])


class OutcomeTests(unittest.TestCase):
    def test_a_policy_that_moved_no_flag_is_not_applicable(self):
        # CacheReplacementPolicyID and SparseVectorAudit absorb the resulting candidate error
        # into invalid worlds, so the run reports a clean 0.0 that reads like a defended task.
        run = {"abstain_flags_rewritten": 0,
               "metrics": {"combined_score": 0.0, "valid": 0.0}}
        self.assertEqual(MODULE._outcome(run), "not_applicable")

    def test_a_refused_submission_is_rejected_not_a_low_score(self):
        run = {"abstain_flags_rewritten": 11,
               "metrics": {"combined_score": 0.0, "valid": 0.0}}
        self.assertEqual(MODULE._outcome(run), "rejected")

    def test_an_accepted_submission_is_scored(self):
        run = {"abstain_flags_rewritten": 11,
               "metrics": {"combined_score": 0.0, "valid": 1.0}}
        self.assertEqual(MODULE._outcome(run), "scored")

    def test_the_control_has_no_rewrite_counter_and_is_still_scored(self):
        self.assertEqual(MODULE._outcome({"metrics": {"combined_score": 0.7, "valid": 1.0}}),
                         "scored")


class CalibrationBlindAxisTests(unittest.TestCase):
    def _runs(self, reference, abstain, claim, outcome="scored"):
        return {
            "reference": {"metrics": reference, "outcome": "scored"},
            "abstain_all": {"metrics": abstain, "outcome": outcome},
            "claim_all": {"metrics": claim, "outcome": outcome},
        }

    def test_an_axis_identical_under_opposite_policies_is_reported(self):
        runs = self._runs({"false_discovery_rate": 0.0, "mechanism_score": 0.9},
                          {"false_discovery_rate": 0.0, "mechanism_score": 0.0},
                          {"false_discovery_rate": 0.0, "mechanism_score": 0.4})
        self.assertEqual(MODULE.calibration_blind_axes(runs), ["false_discovery_rate"])

    def test_structural_and_probe_bound_metrics_are_excluded(self):
        constant = {"development_world_count": 16.0, "correct_refusal_denominator": 8.0,
                    "mean_experiment_calls": 3.0, "raw_quality": 0.5}
        self.assertEqual(MODULE.calibration_blind_axes(self._runs(constant, constant, constant)),
                         ["raw_quality"])

    def test_nothing_is_claimed_when_the_probe_moved_no_flag(self):
        # Silence about an axis the probe never reached is the honest answer; saying the axis
        # is insensitive would be a claim about the probe.
        constant = {"false_discovery_rate": 0.0}
        self.assertEqual(
            MODULE.calibration_blind_axes(self._runs(constant, constant, constant, "not_applicable")), [])

    def test_nothing_is_claimed_when_a_submission_was_refused(self):
        constant = {"false_discovery_rate": 0.0}
        self.assertEqual(
            MODULE.calibration_blind_axes(self._runs(constant, constant, constant, "rejected")), [])

    def test_nothing_is_claimed_when_a_policy_did_not_run(self):
        runs = {"reference": {"metrics": {"false_discovery_rate": 0.0}, "outcome": "scored"},
                "claim_all": {"metrics": {"false_discovery_rate": 0.0}, "outcome": "scored"},
                "abstain_all": {"status": "error"}}
        self.assertEqual(MODULE.calibration_blind_axes(runs), [])


class ReferenceProgramTests(unittest.TestCase):
    class Spec:
        def __init__(self, task_dir, entrypoint):
            self.task_dir = task_dir
            self.entrypoint = entrypoint

    def _package(self, tmp, files):
        for name, body in files.items():
            path = Path(tmp) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    def test_the_baseline_and_the_harness_are_not_references(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self._package(tmp, {
                "solution.py": "def solve(x):\n    return x\n",
                "frontier_eval/run_eval.py": "def solve(x):\n    return x\n",
                "verification/reference_solver.py": "def solve(x):\n    return x\n",
            })
            found = MODULE.reference_program(self.Spec(Path(tmp), "solve"))
            self.assertEqual(found.name, "reference_solver.py")

    def test_a_package_with_only_a_baseline_has_no_reference(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self._package(tmp, {"solution.py": "def solve(x):\n    return x\n"})
            self.assertIsNone(MODULE.reference_program(self.Spec(Path(tmp), "solve")))


if __name__ == "__main__":
    unittest.main()


class RowRenderingTests(unittest.TestCase):
    """The table must survive every outcome; a KeyError here once discarded finished work."""

    def _row(self, runs):
        return {"task": "A/B", "status": "measured", "reference_score": 0.8,
                "reference_saturated_axes": [], "runs": runs}

    def test_a_rejected_policy_prints_its_outcome_not_a_zero(self):
        row = self._row({"reference": {"metrics": {"combined_score": 0.8}},
                         "claim_all": {"outcome": "rejected",
                                       "metrics": {"combined_score": 0.0, "valid": 0.0}}})
        import io
        import contextlib
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            MODULE._print_row(row)
        printed = buffer.getvalue()
        self.assertIn("claim_all=rejected", printed)
        self.assertNotIn("0.0000", printed)

    def test_a_scored_policy_still_prints_its_ratio(self):
        row = self._row({"reference": {"metrics": {"combined_score": 0.8}},
                         "claim_all": {"outcome": "scored", "ratio_to_reference": 0.5,
                                       "reaches_threshold": False,
                                       "metrics": {"combined_score": 0.4, "valid": 1.0}}})
        import io
        import contextlib
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            MODULE._print_row(row)
        self.assertIn("claim_all=0.4000(50%)", buffer.getvalue())
