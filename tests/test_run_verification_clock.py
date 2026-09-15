"""Synthetic clock contracts exercised through the real greedy producer/ledger."""
from __future__ import annotations

from contextlib import contextmanager
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sle.algorithms import evolve
from sle.evaluation_ledger import EvaluationLedger
from sle.protocol import load_trajectory, summarize_trajectory
from sle.registry import find_task
from sle.run_verification import verify_run
from test_protocol import FakeLLM
import test_run_verification as fixtures


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TimedLLM(FakeLLM):
    def __init__(self, clock, reply, attempt_delays):
        super().__init__([reply])
        self.clock = clock
        self.attempt_delays = attempt_delays

    def complete(self, prompt, system=None):
        # Mock transport attempts/backoff within one provider invocation. Their
        # elapsed time belongs to its prefix only when that invocation succeeds.
        for delay in self.attempt_delays:
            self.clock.advance(delay)
        return super().complete(prompt, system)


def evaluator(clock, rows):
    remaining = iter(rows)

    def evaluate(*args, **kwargs):
        duration, result = next(remaining)
        clock.advance(duration)
        if isinstance(result, Exception):
            raise result
        return result
    return evaluate


@contextmanager
def receipt_durations(*durations):
    remaining = iter(durations)
    original = EvaluationLedger.evaluate_once

    def fixed_duration(ledger, request, evaluate, **kwargs):
        samples = iter([0.0, next(remaining)])
        return original(ledger, request, evaluate, clock=lambda: next(samples))
    with patch.object(EvaluationLedger, "evaluate_once", fixed_duration):
        yield


def rewrite_trajectory_and_summary(root, events):
    (root / "trajectory.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    path = root / "summary.json"
    summary = json.loads(path.read_text())
    summary.update(summarize_trajectory(events, budget=summary["budget"] + 1))
    path.write_text(json.dumps(summary))


class RunVerificationClockTests(unittest.TestCase):
    def test_recomputed_summary_cannot_erase_baseline_receipt_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with receipt_durations(2.0):
                request_id = fixtures.RunVerificationTests()._run(root)
            receipt = EvaluationLedger(root).require_receipt_id(request_id)
            self.assertEqual(receipt["evaluation_wall_seconds"], 2.0)
            self.assertTrue(verify_run(root)["verified"])
            original = load_trajectory(root / "trajectory.jsonl")
            for wall, cumulative in ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0), (2.0 + 1e-15, 2.0 + 1e-15)):
                with self.subTest(wall=wall, cumulative=cumulative):
                    events = copy.deepcopy(original)
                    events[0].update(wall_seconds=wall, cumulative_wall_seconds=cumulative)
                    rewrite_trajectory_and_summary(root, events)
                    with self.assertRaisesRegex(ValueError, "active clock"):
                        verify_run(root)
                    self.assertEqual(EvaluationLedger(root).require_receipt_id(request_id), receipt)

    def test_proposal_publication_receipt_and_prefix_must_agree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = fixtures.RunVerificationTests()
            with receipt_durations(2.0, 2.0):
                fixture._run(root)
                fixture._proposal(root, score=0.5, accepted=True, provider_wall=3.0)
            self.assertTrue(verify_run(root)["verified"])
            original = load_trajectory(root / "trajectory.jsonl")
            self.assertEqual(original[1]["cumulative_wall_seconds"], 7.0)
            for wall, cumulative, published in (
                (0.0, 2.0, 2.0), (4.0, 6.0, 5.0), (4.0, 7.0, 5.0),
                (5.0, 7.0, 4.0), (5.0, 7.0, 1.0), (5.0, 7.0, 8.0),
                (5.0, 7.0, None), (5.0, 7.0, True), (5.0, 7.0, "5"),
                (5.0, 7.0, float("nan")), (5.0, 7.0, float("inf")),
                (5.0, 7.0, 10 ** 1000),
            ):
                with self.subTest(wall=wall, cumulative=cumulative, published=published):
                    events = copy.deepcopy(original)
                    events[1].update(wall_seconds=wall, cumulative_wall_seconds=cumulative)
                    events[1]["algorithm_metadata"]["proposal_published_wall_seconds"] = published
                    rewrite_trajectory_and_summary(root, events)
                    with self.assertRaisesRegex(ValueError, "active clock|publication time"):
                        verify_run(root)

    def test_clock_equality_allows_only_addition_rounding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = fixtures.RunVerificationTests()
            with receipt_durations(0.1, 0.3):
                fixture._run(root)
                fixture._proposal(root, score=0.5, accepted=True, provider_wall=0.2)
            self.assertNotEqual(0.1 + (0.2 + 0.3), (0.1 + 0.2) + 0.3)
            self.assertTrue(verify_run(root)["verified"])

    def test_provider_retries_count_the_successful_prefix_but_not_restart_downtime(self):
        clock = Clock()
        spec = find_task("LennardJonesCluster")
        reply = "```python\ndef optimize_cluster(n_atoms): return []\n```"
        with tempfile.TemporaryDirectory() as temporary, patch.object(evolve.time, "monotonic", clock), patch.object(
            evolve, "evaluate_candidate", side_effect=evaluator(clock, [
                (1.0, {"combined_score": 0.1, "valid": 1.0}),
                (2.0, {"combined_score": 0.2, "valid": 1.0}),
            ]),
        ):
            root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "provider request failed"):
                evolve.greedy_rewrite(spec, TimedLLM(clock, RuntimeError("offline"), [2, 3]),
                                      budget=1, timeout_s=20, workdir=root, log_fn=lambda _: None)
            self.assertEqual(len(load_trajectory(root / "trajectory.jsonl")), 1)
            clock.advance(1000)
            evolve.greedy_rewrite(spec, TimedLLM(clock, reply, [1, 2, 3]), budget=1,
                                  timeout_s=20, workdir=root, resume=True, log_fn=lambda _: None)
            events = load_trajectory(root / "trajectory.jsonl")
            self.assertEqual(events[1]["algorithm_metadata"]["proposal_published_wall_seconds"], 7.0)
            self.assertEqual(events[1]["cumulative_wall_seconds"], 9.0)
            self.assertTrue(verify_run(root)["verified"])

    def test_evaluator_retry_reuses_provider_prefix_and_counts_only_committed_receipt(self):
        spec = find_task("LennardJonesCluster")
        reply = "```python\ndef optimize_cluster(n_atoms): return []\n```"
        infrastructure = {"combined_score": -1e18, "valid": 0.0, "infrastructure_failure": 1.0}
        for failure in (infrastructure, RuntimeError("evaluator exception")):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as temporary:
                root, clock = Path(temporary), Clock()
                with patch.object(evolve.time, "monotonic", clock), patch.object(
                    evolve, "evaluate_candidate", side_effect=evaluator(clock, [
                        (1.0, {"combined_score": 0.1, "valid": 1.0}), (5.0, failure),
                        (2.0, {"combined_score": 0.2, "valid": 1.0}),
                    ]),
                ):
                    with self.assertRaises(RuntimeError):
                        evolve.greedy_rewrite(spec, TimedLLM(clock, reply, [3]), budget=1,
                                              timeout_s=20, workdir=root, log_fn=lambda _: None)
                    clock.advance(1000)
                    evolve.greedy_rewrite(spec, FakeLLM([]), budget=1, timeout_s=20,
                                          workdir=root, resume=True, log_fn=lambda _: None)
                events = load_trajectory(root / "trajectory.jsonl")
                self.assertEqual(events[1]["algorithm_metadata"]["proposal_published_wall_seconds"], 4.0)
                self.assertEqual(events[1]["cumulative_wall_seconds"], 6.0)
                self.assertEqual(EvaluationLedger(root).snapshot()["attempt_count"], 3)
                self.assertTrue(verify_run(root)["verified"])

    def test_receipt_reuse_keeps_original_time_after_crash_before_event(self):
        spec = find_task("LennardJonesCluster")
        reply = "```python\ndef optimize_cluster(n_atoms): return []\n```"
        for crash_step in (0, 1):
            with self.subTest(crash_step=crash_step), tempfile.TemporaryDirectory() as temporary:
                root, clock = Path(temporary), Clock()
                original_append = evolve.append_event

                def append(path, event):
                    if event.step == crash_step:
                        raise RuntimeError("crash after receipt")
                    return original_append(path, event)

                with patch.object(evolve.time, "monotonic", clock), patch.object(
                    evolve, "evaluate_candidate", side_effect=evaluator(clock, [
                        (2.0, {"combined_score": 0.1, "valid": 1.0}),
                        (4.0, {"combined_score": 0.2, "valid": 1.0}),
                    ]),
                ), patch.object(evolve, "append_event", side_effect=append):
                    with self.assertRaisesRegex(RuntimeError, "crash after receipt"):
                        evolve.greedy_rewrite(spec, TimedLLM(clock, reply, [3]), budget=crash_step,
                                              timeout_s=20, workdir=root, log_fn=lambda _: None)
                receipts = {path: path.read_bytes() for path in (root / "evaluation_ledger/receipts").glob("*.json")}
                clock.advance(1000)
                with patch.object(evolve.time, "monotonic", clock), patch.object(
                    evolve, "evaluate_candidate", side_effect=AssertionError("receipt must be reused"),
                ):
                    evolve.greedy_rewrite(spec, FakeLLM([]), budget=crash_step, timeout_s=20,
                                          workdir=root, resume=True, log_fn=lambda _: None)
                event = load_trajectory(root / "trajectory.jsonl")[-1]
                self.assertTrue(event["algorithm_metadata"]["evaluation_receipt_reused"])
                self.assertEqual(event["cumulative_wall_seconds"], 2.0 if crash_step == 0 else 9.0)
                self.assertEqual(receipts, {path: path.read_bytes() for path in receipts})
                self.assertTrue(verify_run(root)["verified"])

    def test_no_code_local_overhead_is_not_mistaken_for_an_evaluator_receipt(self):
        clock = Clock()
        spec = find_task("LennardJonesCluster")
        retain = evolve._retain_rejected

        def retain_with_cost(*args, **kwargs):
            result = retain(*args, **kwargs)
            clock.advance(2)
            return result

        with tempfile.TemporaryDirectory() as temporary, patch.object(evolve.time, "monotonic", clock), patch.object(
            evolve, "evaluate_candidate", side_effect=evaluator(clock, [
                (1.0, {"combined_score": 0.1, "valid": 1.0}),
            ]),
        ), patch.object(evolve, "_retain_rejected", side_effect=retain_with_cost):
            root = Path(temporary)
            evolve.greedy_rewrite(spec, TimedLLM(clock, "no code", [3]), budget=1,
                                  timeout_s=20, workdir=root, log_fn=lambda _: None)
            events = load_trajectory(root / "trajectory.jsonl")
            self.assertEqual(events[1]["algorithm_metadata"]["proposal_published_wall_seconds"], 4.0)
            self.assertEqual(events[1]["cumulative_wall_seconds"], 6.0)
            self.assertEqual(EvaluationLedger(root).snapshot()["receipt_count"], 1)
            self.assertTrue(verify_run(root)["verified"])
            events[1]["algorithm_metadata"]["proposal_published_wall_seconds"] = 7.0
            rewrite_trajectory_and_summary(root, events)
            with self.assertRaisesRegex(ValueError, "publication time"):
                verify_run(root)

    def test_receipt_time_survives_crash_before_attempt_completion(self):
        spec = find_task("LennardJonesCluster")
        root_clock = Clock()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(evolve.time, "monotonic", root_clock), patch.object(
                evolve, "evaluate_candidate", side_effect=evaluator(root_clock, [
                    (2.0, {"combined_score": 0.1, "valid": 1.0}),
                ]),
            ), patch.object(EvaluationLedger, "_finish_attempt", side_effect=RuntimeError("after receipt commit")):
                with self.assertRaisesRegex(RuntimeError, "after receipt commit"):
                    evolve.greedy_rewrite(spec, FakeLLM([]), budget=0, timeout_s=20,
                                          workdir=root, log_fn=lambda _: None)
            self.assertEqual(EvaluationLedger(root).snapshot()["incomplete_attempt_count"], 1)
            root_clock.advance(1000)
            with patch.object(evolve.time, "monotonic", root_clock), patch.object(
                evolve, "evaluate_candidate", side_effect=AssertionError("durable outcome already exists"),
            ):
                evolve.greedy_rewrite(spec, FakeLLM([]), budget=0, timeout_s=20,
                                      workdir=root, resume=True, log_fn=lambda _: None)
            self.assertEqual(load_trajectory(root / "trajectory.jsonl")[0]["cumulative_wall_seconds"], 2.0)
            self.assertEqual(EvaluationLedger(root).snapshot()["incomplete_attempt_count"], 1)
            self.assertTrue(verify_run(root)["verified"])

    def test_late_results_and_fixed_grid_sentinels_keep_the_same_clock(self):
        spec = find_task("LennardJonesCluster")
        reply = "```python\ndef optimize_cluster(n_atoms): return []\n```"
        for horizon, late in ((3.0, True), (10.0, False)):
            with self.subTest(horizon=horizon), tempfile.TemporaryDirectory() as temporary:
                root, clock = Path(temporary), Clock()
                with patch.object(evolve.time, "monotonic", clock), patch.object(
                    evolve, "evaluate_candidate", side_effect=evaluator(clock, [
                        (1.0, {"combined_score": 0.1, "valid": 1.0}),
                        (3.0, {"combined_score": 0.9, "valid": 1.0}),
                    ]),
                ):
                    result = evolve.greedy_rewrite(spec, TimedLLM(clock, reply, [1]), budget=1,
                        timeout_s=20, workdir=root, active_wall_horizon_s=horizon,
                        sentinel_interval_s=1.0, log_fn=lambda _: None)
                events = load_trajectory(root / "trajectory.jsonl")
                self.assertEqual(events[1]["cumulative_wall_seconds"], 5.0)
                self.assertEqual(events[1]["algorithm_metadata"]["completed_after_active_wall_horizon"], late)
                self.assertEqual(events[1]["accepted"], not late)
                self.assertGreater(result.summary["sentinel_snapshot"]["type_counts"].get("fixed_grid", 0), 0)
                self.assertTrue(verify_run(root)["verified"])
                if late:
                    events[1].update(wall_seconds=2.0, cumulative_wall_seconds=3.0, accepted=True, best_score=0.9)
                    events[1]["algorithm_metadata"]["completed_after_active_wall_horizon"] = False
                    rewrite_trajectory_and_summary(root, events)
                    with self.assertRaisesRegex(ValueError, "active clock"):
                        verify_run(root)
