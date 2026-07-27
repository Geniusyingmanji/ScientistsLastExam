from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_science.algorithms import ALGORITHMS, get_algorithm
from frontier_science.algorithms.evolve import (extract_signed_decision,
                                                extract_signed_submission,
                                                greedy_rewrite)
from frontier_science.algorithms.abmcts_backend import abmcts
from frontier_science.algorithms.shinkaevolve_backend import _evaluation_rows
from frontier_science.algorithms.common import restore_committed_trajectory
from frontier_science.algorithms.common import require_evaluation_budget
from frontier_science.algorithms.common import llm_condition_sha256
from frontier_science.llm import LLMClient, LLMConfig
from frontier_science.metric_visibility import (load_full_metrics, search_visible_metrics,
                                                score_only_metrics, source_sha256,
                                                store_full_metrics)
from frontier_science.protocol import (TrajectoryEvent, append_event, best_so_far_auc,
                                       compact_trajectory_snapshot, load_trajectory,
                                       mean_confidence_interval,
                                       realized_token_curve, sha256_text,
                                       summarize_at_token_horizon, summarize_trajectory)
from frontier_science.registry import find_task
from frontier_science import upstream_evaluator
from frontier_science.upstream_evaluator import write_configured_wrapper


class FakeLLM:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.prompts = []
        self.last_usage = {}
        self.config = LLMConfig(
            wire="chat", base_url="https://example.invalid/v1", model="fixture",
            max_output_tokens=20, temperature=0.0, timeout_seconds=1,
        )

    def complete(self, prompt, system=None):
        self.prompts.append(prompt)
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

    def test_snapshot_v1_is_frozen_and_v2_adds_portable_token_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            append_event(path, TrajectoryEvent(
                step=0, oracle_calls=1, budget_units=1, score=0.0, best_score=0.0,
                valid=True, accepted=True, wall_seconds=0.1,
                cumulative_wall_seconds=0.1, candidate_sha256="a", parent_sha256=None,
            ))
            append_event(path, TrajectoryEvent(
                step=1, oracle_calls=2, budget_units=2, score=0.5, best_score=0.5,
                valid=True, accepted=True, wall_seconds=0.2,
                cumulative_wall_seconds=0.3, candidate_sha256="b", parent_sha256="a",
                llm={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
            ))
            v1 = compact_trajectory_snapshot(path)
            v2 = compact_trajectory_snapshot(path, schema_version=2)
        self.assertEqual(v1["schema_version"], 1)
        self.assertNotIn("schema_version", v1["events"][0])
        self.assertNotIn("llm", v1["events"][1])
        self.assertNotIn("wall_seconds", v1["events"][1])
        self.assertEqual(v2["schema_version"], 2)
        self.assertEqual(v2["events"][1]["llm"]["total_tokens"], 10)
        self.assertEqual(v2["events"][1]["cumulative_wall_seconds"], 0.3)

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

    def test_realized_token_curve_and_common_horizon_exclude_unfinished_calls(self):
        events = self.events()
        events[1]["llm"] = {
            "input_tokens": 7, "output_tokens": 3, "total_tokens": 10,
        }
        events[2]["llm"] = {
            "input_tokens": 12, "output_tokens": 8, "total_tokens": 20,
        }
        curve = realized_token_curve(events)
        self.assertEqual(
            [point["cumulative_tokens"] for point in curve], [0, 10, 30]
        )
        at_25 = summarize_at_token_horizon(events, 25)
        self.assertEqual(at_25["selected_step"], 1)
        self.assertEqual(at_25["tokens_spent_by_selected_step"], 10)
        self.assertEqual(at_25["best_score"], 0.5)
        self.assertAlmostEqual(at_25["best_so_far_token_auc"], 0.3)
        at_30 = summarize_at_token_horizon(events, 30)
        self.assertEqual(at_30["selected_step"], 2)
        self.assertAlmostEqual(at_30["best_so_far_token_auc"], 1 / 3)

    def test_realized_token_curve_fails_closed_on_missing_or_inconsistent_usage(self):
        events = self.events()
        with self.assertRaisesRegex(ValueError, "lacks.*total_tokens"):
            realized_token_curve(events)
        events[1]["llm"] = {
            "input_tokens": 7, "output_tokens": 3, "total_tokens": 11,
        }
        events[2]["llm"] = {
            "input_tokens": 12, "output_tokens": 8, "total_tokens": 20,
        }
        with self.assertRaisesRegex(ValueError, "disagrees"):
            realized_token_curve(events)

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
            self.assertIn("configure('D/T', 12.5, '')", source)
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

    def test_science_metrics_are_sealed_by_default(self):
        full = {
            "combined_score": 0.7,
            "valid": 1.0,
            "feasibility_rate": 1.0,
            "raw_score": 4.2,
            "robustness_score": 0.1,
            "mechanism_score": 0.2,
            "holdout_prediction_score": 0.3,
            "per_scenario": [{"secret": 1}],
            "unexpected_future_science_metric": 0.4,
        }
        visible = search_visible_metrics(full)
        self.assertEqual(set(visible), {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        })
        for key in (
            "robustness_score", "mechanism_score", "holdout_prediction_score",
            "per_scenario", "unexpected_future_science_metric",
        ):
            self.assertNotIn(key, visible)

    def test_score_only_view_is_scalar_and_still_seals_unknown_metrics(self):
        full = {
            "combined_score": 0.7,
            "valid": 1.0,
            "feasibility_rate": 0.8,
            "raw_score": 4.2,
            "robustness_score": 0.1,
            "unexpected_future_science_metric": 0.4,
        }
        self.assertEqual(score_only_metrics(full), {"combined_score": 0.7})

    def test_trusted_metric_sidecar_roundtrip_and_public_consistency(self):
        source = "def solve():\n    return 1\n"
        full = {
            "combined_score": 0.7, "valid": 1.0,
            "robustness_score": 0.2, "per_scenario": [{"utility": 0.2}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            digest = store_full_metrics(root / "sealed", candidate, full)
            self.assertEqual(digest, source_sha256(source))
            loaded = load_full_metrics(
                root / "sealed", source,
                {"combined_score": 0.7, "valid": 1.0},
            )
            self.assertEqual(loaded, full)
            with self.assertRaisesRegex(ValueError, "mismatch"):
                load_full_metrics(
                    root / "sealed", source,
                    {"combined_score": 0.8, "valid": 1.0},
                )
            with self.assertRaisesRegex(RuntimeError, "nondeterministic"):
                store_full_metrics(
                    root / "sealed", candidate,
                    {**full, "robustness_score": 0.9},
                )

    def test_upstream_evaluator_returns_public_and_stores_full_metrics(self):
        full = {
            "combined_score": 0.4, "valid": 1.0,
            "robustness_score": 0.9, "mechanism_score": 0.8,
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            upstream_evaluator, "find_task", return_value=object()
        ), patch.object(
            upstream_evaluator, "evaluate_candidate", return_value=full
        ):
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text("x = 1\n", encoding="utf-8")
            sidecar = Path(tmp) / "sealed"
            upstream_evaluator.configure("D/T", 12.5, str(sidecar))
            visible = upstream_evaluator.evaluate(str(candidate))
            self.assertEqual(visible, {"combined_score": 0.4, "valid": 1.0})
            self.assertEqual(load_full_metrics(sidecar, "x = 1\n"), full)


class GreedyRewriteTests(unittest.TestCase):
    def test_signed_decision_parser_is_strict(self):
        self.assertEqual(
            extract_signed_decision(
                '```decision\n{"action":"commit","rationale":"stable result"}\n```'
            ),
            {"action": "commit", "rationale": "stable result"},
        )
        self.assertIsNone(extract_signed_decision("commit"))
        self.assertIsNone(extract_signed_decision(
            '```decision\n{"action":"stop","rationale":"x"}\n```'
        ))
        self.assertIsNone(extract_signed_decision(
            '```decision\n{"action":"commit","rationale":"x","score":1}\n```'
        ))
        valid = (
            "```python\nx = 1\n```\n"
            '```decision\n{"action":"continue","rationale":"test"}\n```'
        )
        self.assertIsNotNone(extract_signed_submission(valid))
        self.assertIsNone(extract_signed_submission("prose\n" + valid))
        self.assertIsNone(extract_signed_submission(valid + "\nprose"))
        self.assertIsNone(extract_signed_submission(valid.replace(
            "```python\n", "```python\nx = 0\n```\n```python\n", 1
        )))

    def test_invalid_signed_contract_is_candidate_failure(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        invalid = "```python\n%s\n```\nmissing decision" % baseline
        with tempfile.TemporaryDirectory() as tmp:
            result = greedy_rewrite(
                spec,
                FakeLLM([invalid]),
                budget=1,
                timeout_s=20,
                workdir=Path(tmp),
                active_wall_horizon_s=60,
                signed_decisions=True,
                log_fn=lambda _: None,
            )
            trajectory = load_trajectory(Path(tmp) / "trajectory.jsonl")
        self.assertEqual(trajectory[1]["error"], "signed_decision_contract_invalid")
        self.assertFalse(trajectory[1]["valid"])
        self.assertEqual(result.evaluated, 1)
        submission = next(
            row for row in result.summary["sentinel_snapshot"]["events"]
            if row["sentinel_type"] == "submission"
        )
        self.assertEqual(submission["evaluation"]["status"], "not_applicable")

    def test_signed_commit_is_bound_and_honor_stop_ends_proposals(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        response = (
            "```python\n%s\n```\n"
            "```decision\n"
            '{"action":"commit","rationale":"I would defend this artifact now."}\n'
            "```" % baseline
        )
        llm = FakeLLM([response])
        with tempfile.TemporaryDirectory() as tmp:
            result = greedy_rewrite(
                spec,
                llm,
                budget=3,
                timeout_s=20,
                workdir=Path(tmp),
                active_wall_horizon_s=60,
                sentinel_interval_s=30,
                signed_decisions=True,
                signed_decision_policy="honor_stop",
                log_fn=lambda _: None,
            )
            trajectory = load_trajectory(Path(tmp) / "trajectory.jsonl")

        self.assertEqual(len(trajectory), 2)
        self.assertEqual(
            trajectory[1]["algorithm_metadata"]["signed_decision_action"],
            "commit",
        )
        self.assertEqual(result.summary["latest_signed_endpoint_action"], "commit")
        self.assertEqual(result.summary["honored_signed_stop_action"], "commit")
        self.assertEqual(
            result.summary["sentinel_snapshot"]["events"][-1]["reason"],
            "signed_commit_honored_before_horizon",
        )
        sentinels = result.summary["sentinel_snapshot"]["events"]
        commit = next(row for row in sentinels if row["sentinel_type"] == "commit")
        submission = next(
            row for row in sentinels if row["sentinel_type"] == "submission"
        )
        self.assertEqual(commit["artifact_sha256"], submission["artifact_sha256"])
        self.assertEqual(commit["metadata"]["decision_policy"], "honor_stop")
        self.assertEqual(
            commit["metadata"]["response_sha256"],
            submission["metadata"]["response_sha256"],
        )
        self.assertIn("```decision``` JSON object", llm.prompts[0])

    def test_signed_abstain_can_be_recorded_without_stopping(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        responses = [
            (
                "```python\n%s\n```\n```decision\n"
                '{"action":"abstain","rationale":"insufficient evidence"}\n```'
            ) % baseline,
            (
                "```python\n%s\n```\n```decision\n"
                '{"action":"continue","rationale":"continue search"}\n```'
            ) % baseline,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = greedy_rewrite(
                spec,
                FakeLLM(responses),
                budget=2,
                timeout_s=20,
                workdir=Path(tmp),
                active_wall_horizon_s=60,
                signed_decisions=True,
                signed_decision_policy="record_only",
                log_fn=lambda _: None,
            )
        self.assertEqual(len(result.history), 2)
        self.assertEqual(result.summary["latest_signed_endpoint_action"], "abstain")
        self.assertIsNone(result.summary["honored_signed_stop_action"])
        abstain = next(
            row for row in result.summary["sentinel_snapshot"]["events"]
            if row["sentinel_type"] == "abstain"
        )
        self.assertIsNone(abstain["artifact_sha256"])
        self.assertEqual(abstain["evaluation"]["status"], "not_applicable")

    def test_fixed_duration_sentinels_capture_boundary_artifacts(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n" + baseline + "\n```"
        llm = FakeLLM([fenced])
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            result = greedy_rewrite(
                spec,
                llm,
                budget=1,
                timeout_s=20,
                workdir=work,
                active_wall_horizon_s=10.0,
                sentinel_interval_s=2.0,
                log_fn=lambda _: None,
            )
            snapshot = result.summary["sentinel_snapshot"]
            events = snapshot["events"]

        self.assertFalse(result.summary["horizon_reached"])
        self.assertEqual(events[0]["sentinel_type"], "t0")
        self.assertEqual(events[-1]["sentinel_type"], "terminal")
        self.assertEqual(events[-1]["reason"], "proposal_budget_exhausted_before_active_wall_horizon")
        self.assertEqual(snapshot["type_counts"]["submission"], 1)
        self.assertEqual(snapshot["type_counts"]["terminal"], 1)
        submission = next(
            row for row in events if row["sentinel_type"] == "submission"
        )
        self.assertEqual(submission["evaluation"]["status"], "not_evaluated")
        self.assertIsNone(submission["evaluation"]["sha256"])
        self.assertIn("Preregistered active-time horizon", llm.prompts[0])
        self.assertIn("10.000 active wall seconds", llm.prompts[0])
        self.assertIn("proposal 1 in a fixed-duration run", llm.prompts[0])
        self.assertIn("operational safety bound", llm.prompts[0])
        self.assertNotIn("proposal 1 of 1", llm.prompts[0])

    def test_late_result_is_retained_but_cannot_update_incumbent(self):
        spec = find_task("LennardJonesCluster")
        improved = "def optimize_cluster(n_atoms):\n    return []\n"
        llm = FakeLLM(["```python\n%s\n```" % improved])
        metrics = [
            {"combined_score": 0.1, "valid": 1.0},
            {"combined_score": 0.9, "valid": 1.0},
        ]
        clock = iter([0.0, 0.1, 0.1, 0.2, 0.2, 0.3, 2.0])
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=metrics,
        ), patch(
            "frontier_science.algorithms.evolve.time.monotonic",
            side_effect=lambda: next(clock),
        ):
            result = greedy_rewrite(
                spec,
                llm,
                budget=1,
                timeout_s=20,
                workdir=Path(tmp),
                active_wall_horizon_s=1.0,
                sentinel_interval_s=0.5,
                log_fn=lambda _: None,
            )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")

        self.assertEqual(result.best_score, 0.1)
        self.assertEqual(result.best_program, spec.initial_program_path.read_text(encoding="utf-8"))
        self.assertFalse(events[1]["accepted"])
        self.assertTrue(
            events[1]["algorithm_metadata"]["completed_after_active_wall_horizon"]
        )
        terminal = result.summary["sentinel_snapshot"]["events"][-1]
        self.assertEqual(terminal["source_step"], 1)
        self.assertEqual(
            terminal["selection_policy"], "terminal_workspace_artifact"
        )
        self.assertEqual(
            terminal["evaluation"]["status"], "completed_after_schedule"
        )
        self.assertFalse(terminal["feedback_visible"])
        self.assertTrue(result.summary["horizon_reached"])

    def test_baseline_crossing_horizon_is_explicit_protocol_failure(self):
        spec = find_task("LennardJonesCluster")
        clock = iter([0.0, 2.0])
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            return_value={"combined_score": 0.1, "valid": 1.0},
        ), patch(
            "frontier_science.algorithms.evolve.time.monotonic",
            side_effect=lambda: next(clock),
        ):
            result = greedy_rewrite(
                spec,
                FakeLLM([]),
                budget=0,
                timeout_s=20,
                workdir=Path(tmp),
                active_wall_horizon_s=1.0,
                sentinel_interval_s=0.5,
                log_fn=lambda _: None,
            )

        self.assertTrue(result.summary["horizon_reached"])
        self.assertTrue(result.summary["baseline_crossed_horizon"])
        sentinel_events = result.summary["sentinel_snapshot"]["events"]
        self.assertEqual(sentinel_events[0]["evaluation"]["status"], "completed_after_schedule")
        self.assertFalse(sentinel_events[0]["feedback_visible"])
        self.assertEqual(
            sentinel_events[-1]["reason"],
            "baseline_evaluation_completed_after_active_wall_horizon",
        )

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
            self.assertIn("search selection uses combined_score", result.summary["feedback_scope"])
            self.assertIn("evaluator-only validation", result.summary["feedback_scope"])
            checkpoint = json.loads((work / "checkpoint.json").read_text())
            self.assertEqual(checkpoint["next_iter"], 2)
            self.assertEqual(checkpoint["best_source_step"], 0)
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

    def test_llm_transport_failure_does_not_consume_proposal_slot(self):
        spec = find_task("LennardJonesCluster")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with self.assertRaisesRegex(
                RuntimeError, "provider request failed"
            ):
                greedy_rewrite(
                    spec, FakeLLM([RuntimeError("offline")]), budget=1,
                    timeout_s=20, workdir=work, log_fn=lambda _: None,
                )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")
            self.assertEqual(len(events), 1)
            checkpoint = json.loads(
                (work / "checkpoint.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checkpoint["next_iter"], 1)
            self.assertIsNone(checkpoint["pending_proposal"])
            fenced = "```python\n" + spec.initial_program_path.read_text(
                encoding="utf-8"
            ) + "\n```"
            resumed = greedy_rewrite(
                spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                workdir=work, resume=True, log_fn=lambda _: None,
            )
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 2)
            self.assertEqual(resumed.evaluated, 2)

    def test_evaluator_infrastructure_failure_does_not_consume_proposal_slot(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n" + baseline + "\n```"
        baseline_metrics = {
            "combined_score": 0.1, "valid": 1.0,
        }
        infrastructure = {
            "combined_score": -1.0e18,
            "valid": 0.0,
            "infrastructure_failure": 1.0,
            "error_message": "trusted evaluator process failure",
        }
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=[baseline_metrics, infrastructure],
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "candidate trusted evaluator"
                ):
                    greedy_rewrite(
                        spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                        workdir=work, log_fn=lambda _: None,
                    )
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 1)
            checkpoint = json.loads(
                (work / "checkpoint.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checkpoint["next_iter"], 1)
            pending = checkpoint["pending_proposal"]
            self.assertEqual(pending["parse_status"], "parsed_code")
            self.assertEqual(pending["program"].rstrip(), baseline.rstrip())
            self.assertEqual(
                pending["candidate_sha256"], sha256_text(pending["program"])
            )
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                return_value={"combined_score": 0.2, "valid": 1.0},
            ):
                resumed = greedy_rewrite(
                    spec, FakeLLM([]), budget=1, timeout_s=20,
                    workdir=work, resume=True, log_fn=lambda _: None,
                )
            self.assertEqual(resumed.evaluated, 2)
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 2)
            completed = json.loads(
                (work / "checkpoint.json").read_text(encoding="utf-8")
            )
            self.assertIsNone(completed["pending_proposal"])

    def test_baseline_receipt_survives_crash_before_trajectory_commit(self):
        spec = find_task("LennardJonesCluster")
        calls = {"count": 0}

        def evaluate(_spec, _candidate, timeout_s):
            calls["count"] += 1
            return {"combined_score": 0.1, "valid": 1.0}

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=evaluate,
            ), patch(
                "frontier_science.algorithms.evolve.append_event",
                side_effect=RuntimeError("crash after baseline receipt"),
            ):
                with self.assertRaisesRegex(RuntimeError, "baseline receipt"):
                    greedy_rewrite(
                        spec, FakeLLM([]), budget=0, timeout_s=20,
                        workdir=work, log_fn=lambda _: None,
                    )
            self.assertEqual(calls["count"], 1)
            self.assertFalse((work / "trajectory.jsonl").exists())
            self.assertFalse((work / "checkpoint.json").exists())
            self.assertEqual(
                len(list((work / "evaluation_ledger/receipts").glob("*.json"))),
                1,
            )

            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=AssertionError("baseline evaluator called twice"),
            ):
                result = greedy_rewrite(
                    spec, FakeLLM([]), budget=0, timeout_s=20,
                    workdir=work, resume=True, log_fn=lambda _: None,
                )

            events = load_trajectory(work / "trajectory.jsonl")
            self.assertEqual(calls["count"], 1)
            self.assertEqual(len(events), 1)
            self.assertTrue(
                events[0]["algorithm_metadata"]["evaluation_receipt_reused"]
            )
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["request_count"], 1
            )
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["receipt_count"], 1
            )

    def test_committed_baseline_trajectory_recovers_before_checkpoint(self):
        spec = find_task("LennardJonesCluster")
        calls = {"count": 0}

        def evaluate(_spec, _candidate, timeout_s):
            calls["count"] += 1
            return {"combined_score": 0.1, "valid": 1.0}

        real_append = __import__(
            "frontier_science.algorithms.evolve", fromlist=["append_event"]
        ).append_event

        def append_then_crash(path, event):
            real_append(path, event)
            raise RuntimeError("crash after baseline trajectory")

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=evaluate,
            ), patch(
                "frontier_science.algorithms.evolve.append_event",
                side_effect=append_then_crash,
            ):
                with self.assertRaisesRegex(RuntimeError, "baseline trajectory"):
                    greedy_rewrite(
                        spec, FakeLLM([]), budget=0, timeout_s=20,
                        workdir=work, log_fn=lambda _: None,
                    )
            self.assertEqual(calls["count"], 1)
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 1)
            self.assertFalse((work / "checkpoint.json").exists())

            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=AssertionError("baseline evaluator called twice"),
            ):
                result = greedy_rewrite(
                    spec, FakeLLM([]), budget=0, timeout_s=20,
                    workdir=work, resume=True, log_fn=lambda _: None,
                )

            self.assertEqual(calls["count"], 1)
            self.assertTrue((work / "checkpoint.json").is_file())
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 1)
            self.assertEqual(result.evaluated, 1)
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["receipt_count"], 1
            )

    def test_proposal_receipt_survives_crash_before_trajectory_commit(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n" + baseline + "\n```"
        calls = {"count": 0}

        def evaluate(_spec, _candidate, timeout_s):
            calls["count"] += 1
            return {
                "combined_score": 0.1 if calls["count"] == 1 else 0.2,
                "valid": 1.0,
            }

        from frontier_science.algorithms import evolve as evolve_module
        real_append = evolve_module.append_event
        appends = {"count": 0}

        def crash_on_proposal(path, event):
            appends["count"] += 1
            if appends["count"] == 2:
                raise RuntimeError("crash after proposal receipt")
            return real_append(path, event)

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=evaluate,
            ), patch(
                "frontier_science.algorithms.evolve.append_event",
                side_effect=crash_on_proposal,
            ):
                with self.assertRaisesRegex(RuntimeError, "proposal receipt"):
                    greedy_rewrite(
                        spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                        workdir=work, log_fn=lambda _: None,
                    )
            self.assertEqual(calls["count"], 2)
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 1)
            checkpoint = json.loads(
                (work / "checkpoint.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checkpoint["next_iter"], 1)
            self.assertIsNotNone(checkpoint["pending_proposal"])
            self.assertEqual(
                len(list((work / "evaluation_ledger/receipts").glob("*.json"))),
                2,
            )

            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=AssertionError("proposal evaluator called twice"),
            ):
                result = greedy_rewrite(
                    spec, FakeLLM([]), budget=1, timeout_s=20,
                    workdir=work, resume=True, log_fn=lambda _: None,
                )

            events = load_trajectory(work / "trajectory.jsonl")
            self.assertEqual(calls["count"], 2)
            self.assertEqual(len(events), 2)
            self.assertTrue(
                events[1]["algorithm_metadata"]["evaluation_receipt_reused"]
            )
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["request_count"], 2
            )
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["receipt_count"], 2
            )

    def test_committed_proposal_trajectory_recovers_before_checkpoint(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        proposal = baseline + "\n# recovery-proposal\n"
        fenced = "```python\n" + proposal + "\n```"
        calls = {"count": 0}

        def evaluate(_spec, _candidate, timeout_s):
            calls["count"] += 1
            return {
                "combined_score": 0.1 if calls["count"] == 1 else 0.2,
                "valid": 1.0,
            }

        evolve_module = __import__(
            "frontier_science.algorithms.evolve", fromlist=["append_event"]
        )
        real_append = evolve_module.append_event
        appends = {"count": 0}

        def append_then_crash(path, event):
            appends["count"] += 1
            real_append(path, event)
            if appends["count"] == 2:
                raise RuntimeError("crash after proposal trajectory")

        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=evaluate,
            ), patch(
                "frontier_science.algorithms.evolve.append_event",
                side_effect=append_then_crash,
            ):
                with self.assertRaisesRegex(RuntimeError, "proposal trajectory"):
                    greedy_rewrite(
                        spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                        workdir=work, log_fn=lambda _: None,
                    )
            self.assertEqual(calls["count"], 2)
            self.assertEqual(len(load_trajectory(work / "trajectory.jsonl")), 2)
            checkpoint = json.loads(
                (work / "checkpoint.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checkpoint["next_iter"], 1)

            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=AssertionError("proposal evaluator called twice"),
            ):
                result = greedy_rewrite(
                    spec, FakeLLM([]), budget=1, timeout_s=20,
                    workdir=work, resume=True, log_fn=lambda _: None,
                )

            events = load_trajectory(work / "trajectory.jsonl")
            self.assertEqual(calls["count"], 2)
            self.assertEqual([row["step"] for row in events], [0, 1])
            self.assertEqual(
                events[1]["candidate_sha256"], sha256_text(proposal.strip())
            )
            self.assertEqual(events[1]["score"], 0.2)
            self.assertTrue(
                events[1]["algorithm_metadata"]["evaluation_receipt_reused"]
            )
            self.assertEqual(result.evaluated, 2)
            self.assertEqual(
                result.summary["evaluation_ledger_snapshot"]["request_count"], 2
            )

    def test_checkpoint_search_state_does_not_store_sealed_metrics(self):
        spec = find_task("ControlTheory/InvertedPendulumSwingUp", include_uncertified=True)
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n" + baseline + "\n```"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            greedy_rewrite(
                spec, FakeLLM([fenced]), budget=1, timeout_s=20,
                workdir=work, seed=9, log_fn=lambda _: None,
            )
            checkpoint = json.loads((work / "checkpoint.json").read_text(encoding="utf-8"))
            self.assertNotIn("robustness_score", checkpoint["best_metrics"])
            self.assertNotIn("per_scenario", checkpoint["best_metrics"])
            events = load_trajectory(work / "trajectory.jsonl")
            self.assertIn("robustness_score", events[0]["metrics"])
            self.assertIn("per_scenario", events[0]["metrics"])

    def test_selection_blind_freezes_parent_and_metrics_but_retains_offline_best(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        proposal_one = "# OPEN_LOOP_PROPOSAL_ONE\ndef optimize_cluster(n_atoms):\n    return []\n"
        proposal_two = "# OPEN_LOOP_PROPOSAL_TWO\ndef optimize_cluster(n_atoms):\n    return []\n"
        llm = FakeLLM([
            "```python\n%s\n```" % proposal_one,
            "```python\n%s\n```" % proposal_two,
        ])
        metrics = [
            {"combined_score": 0.0, "valid": 1.0, "feasibility_rate": 1.0},
            {"combined_score": 0.8, "valid": 1.0, "feasibility_rate": 1.0},
            {"combined_score": 0.7, "valid": 1.0, "feasibility_rate": 1.0},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=metrics,
        ):
            result = greedy_rewrite(
                spec,
                llm,
                budget=2,
                timeout_s=20,
                workdir=Path(tmp),
                feedback_mode="selection_blind",
                log_fn=lambda _: None,
            )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")

        self.assertEqual(result.best_score, 0.8)
        self.assertEqual(result.best_program.strip(), proposal_one.strip())
        self.assertEqual(result.summary["selection_policy"], "offline_best_of_open_loop_batch")
        self.assertEqual(events[1]["parent_sha256"], sha256_text(baseline))
        self.assertEqual(events[2]["parent_sha256"], sha256_text(baseline))
        self.assertEqual(
            events[2]["algorithm_metadata"]["accepted_semantics"],
            "offline_best_update",
        )
        self.assertIn(baseline, llm.prompts[0])
        self.assertIn(baseline, llm.prompts[1])
        self.assertNotIn("OPEN_LOOP_PROPOSAL_ONE", llm.prompts[1])
        self.assertIn('"combined_score": 0.0', llm.prompts[0])
        self.assertIn('"combined_score": 0.0', llm.prompts[1])
        self.assertIn("proposal 1 of 2", llm.prompts[0])
        self.assertIn("proposal 2 of 2", llm.prompts[1])

    def test_score_only_hides_other_metrics_but_keeps_online_parent_selection(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        proposal_one = "# SCORE_ONLY_ONE\ndef optimize_cluster(n_atoms):\n    return []\n"
        proposal_two = "# SCORE_ONLY_TWO\ndef optimize_cluster(n_atoms):\n    return []\n"
        llm = FakeLLM([
            "```python\n%s\n```" % proposal_one,
            "```python\n%s\n```" % proposal_two,
        ])
        metrics = [
            {
                "combined_score": 0.0, "valid": 1.0,
                "feasibility_rate": 0.5, "raw_score": 2.0,
                "robustness_score": 0.9,
            },
            {
                "combined_score": 0.8, "valid": 1.0,
                "feasibility_rate": 1.0, "raw_score": 3.0,
                "robustness_score": 0.1,
            },
            {"combined_score": 0.7, "valid": 1.0},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=metrics,
        ):
            result = greedy_rewrite(
                spec, llm, budget=2, timeout_s=20, workdir=Path(tmp),
                feedback_mode="score_only", log_fn=lambda _: None,
            )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")

        self.assertEqual(result.best_score, 0.8)
        self.assertIn(baseline, llm.prompts[0])
        self.assertIn(proposal_one.strip(), llm.prompts[1])
        self.assertIn('"combined_score": 0.0', llm.prompts[0])
        self.assertIn('"combined_score": 0.8', llm.prompts[1])
        for hidden in ("valid", "feasibility_rate", "raw_score", "robustness_score"):
            self.assertNotIn('"%s"' % hidden, llm.prompts[0])
            self.assertNotIn('"%s"' % hidden, llm.prompts[1])
        self.assertEqual(events[2]["parent_sha256"], sha256_text(proposal_one.strip()))
        self.assertEqual(
            events[2]["algorithm_metadata"]["prompt_metric_keys"],
            "combined_score",
        )
        self.assertEqual(result.summary["selection_policy"], "online_incumbent")
        self.assertIn("not a no-feedback control", result.summary["feedback_scope"])

    def test_repeated_source_hash_does_not_reassign_parent_lineage(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        improved = "# UNIQUE_BEST\ndef optimize_cluster(n_atoms):\n    return []\n"
        llm = FakeLLM([
            "```python\n%s\n```" % improved,
            "```python\n%s\n```" % baseline,
            "```python\n%s\n```" % improved,
        ])
        metrics = [
            {"combined_score": 0.0, "valid": 1.0},
            {"combined_score": 0.8, "valid": 1.0},
            {"combined_score": 0.1, "valid": 1.0},
            {"combined_score": 0.8, "valid": 1.0},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=metrics,
        ):
            greedy_rewrite(
                spec, llm, budget=3, timeout_s=20, workdir=Path(tmp),
                feedback_mode="normal", log_fn=lambda _: None,
            )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")
        self.assertEqual(events[2]["algorithm_metadata"]["prompt_source_step"], 1)
        self.assertEqual(events[3]["algorithm_metadata"]["prompt_source_step"], 1)
        self.assertEqual(events[3]["parent_sha256"], sha256_text(improved.strip()))

    def test_delayed_replay_releases_parent_on_fixed_one_proposal_lag(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        proposals = [
            "# DELAYED_ONE\ndef optimize_cluster(n_atoms):\n    return []\n",
            "# DELAYED_TWO\ndef optimize_cluster(n_atoms):\n    return []\n",
            "# DELAYED_THREE\ndef optimize_cluster(n_atoms):\n    return []\n",
        ]
        llm = FakeLLM(["```python\n%s\n```" % proposal for proposal in proposals])
        metrics = [
            {"combined_score": 0.0, "valid": 1.0, "raw_score": 0.0},
            {"combined_score": 0.8, "valid": 1.0, "raw_score": 8.0},
            {"combined_score": 0.7, "valid": 1.0, "raw_score": 7.0},
            {"combined_score": 0.6, "valid": 1.0, "raw_score": 6.0},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=metrics,
        ):
            result = greedy_rewrite(
                spec, llm, budget=3, timeout_s=20, workdir=Path(tmp),
                feedback_mode="delayed_replay", log_fn=lambda _: None,
            )
            events = load_trajectory(Path(tmp) / "trajectory.jsonl")

        self.assertIn(baseline, llm.prompts[0])
        self.assertIn(baseline, llm.prompts[1])
        self.assertNotIn("DELAYED_ONE", llm.prompts[1])
        self.assertIn(proposals[0].strip(), llm.prompts[2])
        self.assertEqual(
            [event["parent_sha256"] for event in events[1:]],
            [
                sha256_text(baseline),
                sha256_text(baseline),
                sha256_text(proposals[0].strip()),
            ],
        )
        self.assertEqual(
            [event["algorithm_metadata"]["prompt_source_step"] for event in events[1:]],
            [0, 0, 1],
        )
        self.assertEqual(
            [
                event["algorithm_metadata"]["feedback_released_through_step"]
                for event in events[1:]
            ],
            [0, 0, 1],
        )
        self.assertEqual(result.best_score, 0.8)
        self.assertEqual(
            result.summary["selection_policy"],
            "delayed_online_parent_offline_final_best",
        )

    def test_delayed_replay_resume_restores_unreleased_candidate_state(self):
        spec = find_task("LennardJonesCluster")
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        proposal_one = "# RESUME_DELAYED_ONE\ndef optimize_cluster(n_atoms):\n    return []\n"
        proposal_two = "# RESUME_DELAYED_TWO\ndef optimize_cluster(n_atoms):\n    return []\n"
        proposal_three = "# RESUME_DELAYED_THREE\ndef optimize_cluster(n_atoms):\n    return []\n"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                side_effect=[
                    {"combined_score": 0.0, "valid": 1.0},
                    {"combined_score": 0.8, "valid": 1.0},
                    {"combined_score": 0.7, "valid": 1.0},
                ],
            ):
                greedy_rewrite(
                    spec,
                    FakeLLM([
                        "```python\n%s\n```" % proposal_one,
                        "```python\n%s\n```" % proposal_two,
                    ]),
                    budget=2,
                    timeout_s=20,
                    workdir=work,
                    feedback_mode="delayed_replay",
                    log_fn=lambda _: None,
                )
            resumed_llm = FakeLLM(["```python\n%s\n```" % proposal_three])
            with patch(
                "frontier_science.algorithms.evolve.evaluate_candidate",
                return_value={"combined_score": 0.6, "valid": 1.0},
            ):
                resumed = greedy_rewrite(
                    spec, resumed_llm, budget=3, timeout_s=20, workdir=work,
                    feedback_mode="delayed_replay", resume=True,
                    log_fn=lambda _: None,
                )
            events = load_trajectory(work / "trajectory.jsonl")

        self.assertIn(proposal_one.strip(), resumed_llm.prompts[0])
        self.assertEqual(events[3]["parent_sha256"], sha256_text(proposal_one.strip()))
        self.assertEqual(resumed.best_score, 0.8)


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
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unsupported"):
                backend(spec, FakeLLM([]), budget=0, timeout_s=20,
                        workdir=Path(tmp), feedback_mode="selection_blind")

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
