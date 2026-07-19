from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_science.algorithms import ALGORITHMS, get_algorithm
from frontier_science.algorithms.evolve import greedy_rewrite
from frontier_science.algorithms.abmcts_backend import abmcts
from frontier_science.algorithms.shinkaevolve_backend import _evaluation_rows
from frontier_science.algorithms.common import restore_committed_trajectory
from frontier_science.algorithms.common import require_evaluation_budget
from frontier_science.algorithms.common import llm_condition_sha256
from frontier_science.llm import LLMClient, LLMConfig
from frontier_science.protocol import (TrajectoryEvent, append_event, best_so_far_auc,
                                       load_trajectory, mean_confidence_interval,
                                       summarize_trajectory)
from frontier_science.registry import find_task
from frontier_science import upstream_evaluator
from frontier_science.upstream_evaluator import write_configured_wrapper


class FakeLLM:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.last_usage = {}
        self.config = LLMConfig(
            wire="chat", base_url="https://example.invalid/v1", model="fixture",
            max_output_tokens=20, temperature=0.0, timeout_seconds=1,
        )

    def complete(self, prompt, system=None):
        self.last_usage = {"input_tokens": 10, "output_tokens": 5,
                           "total_tokens": 15, "estimated_cost_usd": 0.001}
        value = next(self.replies)
        if isinstance(value, Exception):
            raise value
        return value


class ProtocolMetricTests(unittest.TestCase):
    def events(self):
        return [
            {
                "schema_version": 2, "step": 0, "budget_units": 1,
                "oracle_calls": 1, "score": 0.0, "best_score": 0.0,
                "valid": True, "accepted": True, "wall_seconds": 0.1,
                "cumulative_wall_seconds": 0.1, "candidate_sha256": "a",
                "parent_sha256": None,
            },
            {
                "schema_version": 2, "step": 1, "budget_units": 2,
                "oracle_calls": 2, "score": 0.5, "best_score": 0.5,
                "valid": True, "accepted": True, "wall_seconds": 0.1,
                "cumulative_wall_seconds": 0.2, "candidate_sha256": "b",
                "parent_sha256": "a",
            },
            {
                "schema_version": 2, "step": 2, "budget_units": 3,
                "oracle_calls": 3, "score": -1.0, "best_score": 0.5,
                "valid": False, "accepted": False, "wall_seconds": 0.1,
                "cumulative_wall_seconds": 0.3, "candidate_sha256": "c",
                "parent_sha256": "b",
            },
        ]

    def test_best_so_far_auc_has_explicit_horizon(self):
        self.assertAlmostEqual(best_so_far_auc(self.events(), budget=4), 0.375)

    def test_confidence_interval(self):
        got = mean_confidence_interval([1, 2, 3])
        self.assertEqual(got["n"], 3)
        self.assertAlmostEqual(got["mean"], 2.0)
        self.assertLess(got["ci95_low"], got["mean"])
        self.assertAlmostEqual(got["ci95_low"], -0.484, places=3)

    def test_jsonl_roundtrip_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            for step, score in enumerate((0.0, 0.5)):
                append_event(path, TrajectoryEvent(
                    step=step, oracle_calls=step + 1, score=score, best_score=score,
                    valid=True, accepted=True, wall_seconds=1,
                    cumulative_wall_seconds=step + 1, candidate_sha256=str(step),
                    parent_sha256=None,
                ))
            events = load_trajectory(path)
            summary = summarize_trajectory(events, budget=2)
            self.assertEqual(summary["best_score"], 0.5)
            self.assertAlmostEqual(summary["best_so_far_auc"], 0.25)
            self.assertIsNone(summary["llm"]["estimated_cost_usd"])

    def test_unknown_pricing_is_null_not_zero(self):
        client = LLMClient(LLMConfig())
        client._record_usage({"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})
        self.assertEqual(client.last_usage["total_tokens"], 120)
        self.assertIsNone(client.last_usage["estimated_cost_usd"])
        priced = LLMClient(LLMConfig(
            input_cost_per_million=2.0, output_cost_per_million=4.0
        ))
        priced._record_usage({"prompt_tokens": 100, "completion_tokens": 20})
        self.assertAlmostEqual(priced.last_usage["estimated_cost_usd"], 0.00028)

    def test_resume_discards_uncommitted_and_partial_trajectory_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            for step in range(3):
                append_event(path, TrajectoryEvent(
                    step=step, oracle_calls=step + 1, score=float(step),
                    best_score=float(step), valid=True, accepted=True,
                    wall_seconds=1, cumulative_wall_seconds=step + 1,
                    candidate_sha256=str(step), parent_sha256=None,
                    budget_units=step + 1,
                ))
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"schema_version":2,"step":3')
            restored = restore_committed_trajectory(path, next_step=2)
            self.assertEqual([event["step"] for event in restored], [0, 1])
            self.assertEqual([event["step"] for event in load_trajectory(path)], [0, 1])

    def test_resume_rejects_corrupt_committed_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            path.write_text('{"schema_version":2,"step":0\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checkpoint-owned prefix"):
                restore_committed_trajectory(path, next_step=1)

    def test_loader_rejects_accounting_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            append_event(path, TrajectoryEvent(
                step=0, oracle_calls=1, budget_units=1, score=0.1, best_score=0.1,
                valid=True, accepted=True, wall_seconds=1, cumulative_wall_seconds=1,
                candidate_sha256="a", parent_sha256=None,
            ))
            append_event(path, TrajectoryEvent(
                step=1, oracle_calls=3, budget_units=2, score=0.2, best_score=0.2,
                valid=True, accepted=True, wall_seconds=1, cumulative_wall_seconds=2,
                candidate_sha256="b", parent_sha256="a",
            ))
            with self.assertRaisesRegex(ValueError, "oracle_calls"):
                load_trajectory(path)

    def test_auc_rejects_non_schema_events(self):
        events = self.events()
        events[0]["schema_version"] = 1
        with self.assertRaisesRegex(ValueError, "unsupported trajectory schema"):
            best_so_far_auc(events)

    def test_upstream_wrapper_binds_task_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_configured_wrapper(Path(tmp) / "evaluator.py", "D/T", 12.5)
            source = path.read_text(encoding="utf-8")
            self.assertIn("configure('D/T', 12.5)", source)
            self.assertIn("sys.path.insert", source)
            self.assertNotIn("API_KEY", source)

    def test_llm_condition_hash_does_not_serialize_secret_headers(self):
        client = LLMClient(LLMConfig(extra_headers={"Authorization": "secret-value"}))
        condition = llm_condition_sha256(client)
        self.assertEqual(len(condition), 64)
        self.assertNotIn("secret-value", condition)

    def test_upstream_evaluation_scrubs_and_restores_credentials(self):
        seen = {}

        def fake_evaluate(*args, **kwargs):
            seen["credential"] = os.environ.get("OPENAI_API_KEY")
            seen["timeout_s"] = kwargs.get("timeout_s")
            return {"combined_score": 0.1}

        with patch.object(upstream_evaluator, "find_task", return_value=object()), patch.object(
            upstream_evaluator, "evaluate_candidate", side_effect=fake_evaluate
        ):
            upstream_evaluator.configure("D/T", 12.5)
            with patch.dict(os.environ, {"OPENAI_API_KEY": "secret"}, clear=False):
                self.assertEqual(
                    upstream_evaluator.evaluate("candidate.py"), {"combined_score": 0.1}
                )
                self.assertEqual(os.environ["OPENAI_API_KEY"], "secret")
            self.assertIsNone(seen["credential"])
            self.assertEqual(seen["timeout_s"], 12.5)


class GreedyRewriteTests(unittest.TestCase):
    def test_trace_cost_and_resume(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n" + baseline + "\n```"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            result = greedy_rewrite(spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                                    workdir=work, seed=17, log_fn=lambda _: None)
            self.assertEqual(result.algorithm, "greedy_rewrite")
            events = load_trajectory(work / "trajectory.jsonl")
            self.assertEqual([e["step"] for e in events], [0, 1])
            self.assertEqual(events[1]["llm"]["total_tokens"], 15)
            self.assertIn("selection still uses true oracle scores", result.summary["feedback_scope"])
            checkpoint = json.loads((work / "checkpoint.json").read_text())
            self.assertEqual(checkpoint["next_iter"], 2)
            manifest = json.loads((work / "run_manifest.json").read_text())
            self.assertEqual(manifest["task_id"], spec.task_id)
            self.assertEqual(manifest["seed"], 17)
            self.assertEqual(len(manifest["runtime_source_sha256"]), 64)

            with self.assertRaises(FileExistsError):
                greedy_rewrite(spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                               workdir=work, seed=17, log_fn=lambda _: None)

            resumed = greedy_rewrite(spec, FakeLLM([fenced]), budget=2, timeout_s=20,
                                     workdir=work, seed=17, resume=True,
                                     log_fn=lambda _: None)
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 3)
            self.assertEqual(resumed.evaluated, 3)

            with self.assertRaisesRegex(ValueError, "manifest"):
                greedy_rewrite(spec, FakeLLM([fenced]), budget=3, timeout_s=20,
                               workdir=work, seed=18, resume=True,
                               log_fn=lambda _: None)

            with self.assertRaisesRegex(ValueError, "smaller than the committed checkpoint"):
                greedy_rewrite(spec, FakeLLM([]), budget=1, timeout_s=20,
                               workdir=work, seed=17, resume=True,
                               log_fn=lambda _: None)

    def test_llm_failure_is_recorded_without_unbound_reply(self):
        spec = find_task("LennardJonesCluster")
        with tempfile.TemporaryDirectory() as tmp:
            result = greedy_rewrite(spec, FakeLLM([RuntimeError("offline")]), budget=1,
                                    timeout_s=20, workdir=Path(tmp), log_fn=lambda _: None)
            self.assertEqual(result.evaluated, 1)
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")
            self.assertEqual(events[-1]["error"], "LLM error: offline")


class AlgorithmAdapterTests(unittest.TestCase):
    def test_named_algorithms_do_not_alias_greedy(self):
        self.assertEqual(set(ALGORITHMS), {"greedy_rewrite", "openevolve", "abmcts", "shinkaevolve"})
        for name in ("openevolve", "abmcts", "shinkaevolve"):
            self.assertIsNot(get_algorithm(name), greedy_rewrite)

    def test_optional_dependency_failure_is_explicit(self):
        spec = find_task("LennardJonesCluster")
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.abmcts_backend._load_treequest",
            side_effect=RuntimeError("official TreeQuest unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "official TreeQuest"):
                abmcts(spec, FakeLLM([]), budget=0, timeout_s=20, workdir=Path(tmp))

    def test_feedback_modes_fail_instead_of_silent_degradation(self):
        spec = find_task("LennardJonesCluster")
        backend = get_algorithm("openevolve")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unsupported"):
                backend(spec, FakeLLM([]), budget=0, timeout_s=20,
                        workdir=Path(tmp), feedback_mode="shuffled")

    def test_shinka_island_copies_do_not_consume_oracle_budget(self):
        rows = [
            {"id": "original", "metadata": {}},
            {"id": "copy", "metadata": {"_is_island_copy": True}},
        ]
        self.assertEqual([row["id"] for row in _evaluation_rows(rows)], ["original"])

    def test_upstream_evaluation_overspend_fails_closed(self):
        require_evaluation_budget("fixture", count=3, budget=2)
        with self.assertRaisesRegex(RuntimeError, "3 real evaluation rows.*2-call budget"):
            require_evaluation_budget("fixture", count=3, budget=1)


if __name__ == "__main__":
    unittest.main()
