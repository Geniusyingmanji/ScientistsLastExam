from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "batch_evolve.py"
SPEC = importlib.util.spec_from_file_location("batch_evolve_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BatchAggregationTests(unittest.TestCase):
    class Config:
        wire = "chat"; base_url = "https://example.invalid/v1"; model = "fixture"
        max_output_tokens = 10; temperature = 0; reasoning_effort = None
        timeout_seconds = 1; extra_headers = {}
        input_cost_per_million = None; output_cost_per_million = None

    def test_condition_aggregation_reports_auc_cost_and_ci(self):
        def run(seed, best, auc):
            return {
                "task": "T/X", "algorithm": "greedy_rewrite", "feedback_mode": "normal",
                "seed": seed, "best": best,
                "summary": {"best_so_far_auc": auc, "budget_units": 4,
                            "oracle_calls": 3 + seed, "wall_seconds": 2 + seed,
                            "llm": {"total_tokens": 10 + seed, "estimated_cost_usd": 0.1}},
            }
        got = MODULE.aggregate_runs([run(0, 0.2, 0.1), run(1, 0.4, 0.3)])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 2)
        self.assertAlmostEqual(condition["best_score"]["mean"], 0.3)
        self.assertAlmostEqual(condition["best_so_far_auc"]["mean"], 0.2)
        self.assertEqual(condition["budget_units"]["mean"], 4)
        self.assertAlmostEqual(condition["oracle_calls"]["mean"], 3.5)
        self.assertIn("estimated_cost_usd", condition)

    def test_feedback_condition_order_is_counterbalanced_by_seed(self):
        modes = ["normal", "selection_blind"]
        self.assertEqual(MODULE._condition_order(modes, 0), modes)
        self.assertEqual(MODULE._condition_order(modes, 1), list(reversed(modes)))
        self.assertEqual(MODULE._condition_order(modes, 2), modes)

    def test_four_condition_williams_order_balances_position_and_carryover(self):
        modes = ["normal", "score_only", "delayed_replay", "selection_blind"]
        rows = [
            MODULE._condition_order(
                modes, seed=100 + index, design="balanced_williams",
                schedule_index=index,
            )
            for index in range(4)
        ]
        for position in range(4):
            self.assertEqual({row[position] for row in rows}, set(modes))
        carryovers = [
            (row[index], row[index + 1])
            for row in rows for index in range(3)
        ]
        self.assertEqual(len(carryovers), 12)
        self.assertEqual(len(set(carryovers)), 12)
        self.assertTrue(all(left != right for left, right in carryovers))

        repeated = [
            MODULE._condition_order(
                modes, seed=index, design="balanced_williams",
                schedule_index=index,
            )
            for index in range(12)
        ]
        for position in range(4):
            counts = {
                mode: sum(row[position] == mode for row in repeated)
                for mode in modes
            }
            self.assertEqual(set(counts.values()), {3})

    def test_williams_order_rejects_non_four_mode_design(self):
        with self.assertRaisesRegex(ValueError, "exactly four"):
            MODULE._condition_order(
                ["normal", "selection_blind"], 0, "balanced_williams"
            )

    def test_aggregation_uses_latest_attempt_without_dropping_history(self):
        failed = {"task": "T/X", "algorithm": "greedy_rewrite",
                  "feedback_mode": "normal", "seed": 0, "error": "offline"}
        successful = {
            "task": "T/X", "algorithm": "greedy_rewrite", "feedback_mode": "normal",
            "seed": 0, "best": 0.3,
            "summary": {"best_so_far_auc": 0.2, "budget_units": 2, "oracle_calls": 2,
                        "wall_seconds": 1, "llm": {"total_tokens": None,
                                                   "estimated_cost_usd": None}},
        }
        got = MODULE.aggregate_runs([failed, successful])
        self.assertEqual(got["attempt_count"], 2)
        self.assertEqual(got["superseded_attempts"], 1)
        self.assertEqual(got["failed_attempts"], 1)
        self.assertEqual(got["attempt_failure_rate"], 0.5)
        self.assertEqual(got["recovered_runs"], 1)
        self.assertEqual(got["successful_runs"], 1)
        self.assertEqual(got["failed_runs"], 0)
        self.assertEqual(got["intent_to_evaluate"], {
            "scheduled_runs": 1,
            "successful_runs": 1,
            "terminal_failed_runs": 0,
            "completion_rate": 1.0,
            "run_cells_with_any_failed_attempt": 1,
            "recovered_runs": 1,
        })
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["attempt_count"], 2)
        self.assertEqual(condition["failed_attempts"], 1)
        self.assertEqual(condition["recovered_runs"], 1)

    def test_failed_condition_stays_visible_without_valid_quality_rows(self):
        failed = {"task": "T/X", "algorithm": "greedy_rewrite",
                  "feedback_mode": "normal", "seed": 0, "error": "offline"}
        got = MODULE.aggregate_runs([failed])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 0)
        self.assertEqual(condition["scheduled_n"], 1)
        self.assertEqual(condition["terminal_failed_runs"], 1)
        self.assertEqual(condition["completion_rate"], 0.0)
        self.assertEqual(condition["best_score"]["n"], 0)
        self.assertEqual(got["failed_attempts"], 1)
        self.assertEqual(got["intent_to_evaluate"]["completion_rate"], 0.0)
        self.assertEqual(got["overall_valid_only"], {})

    def test_complete_smoke_writes_passed_status(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {"git_available": True, "git_revision": "abc",
                 "source_tree_dirty": False, "source_changes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            output = Path(tmp) / "report.json"
            workdir = Path(tmp) / "runs"
            result = MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertTrue(report["passed"])
            self.assertTrue(report["execution_passed"])
            self.assertTrue(report["trusted_evidence"])
            snapshot = report["runs"][0]["trajectory_snapshot"]
            self.assertEqual(report["config"]["trajectory_snapshot_schema_version"], 2)
            self.assertEqual(snapshot["schema_version"], 2)
            self.assertEqual(len(snapshot["trajectory_sha256"]), 64)
            self.assertEqual(len(snapshot["events"]), 1)
            self.assertEqual(snapshot["events"][0]["schema_version"], 2)
            self.assertIn("wall_seconds", snapshot["events"][0])
            self.assertIn("cumulative_wall_seconds", snapshot["events"][0])

    def test_preregistration_is_hash_bound_into_config(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {"git_available": True, "git_revision": "abc",
                 "source_tree_dirty": False, "source_changes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            root = Path(tmp)
            preregistration = root / "prereg.json"
            preregistration.write_text('{"version":3}\n', encoding="utf-8")
            output = root / "report.json"
            self.assertEqual(MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(root / "runs"),
                "--output", str(output), "--preregistration", str(preregistration),
            ]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            bound = report["config"]["preregistration"]
            self.assertEqual(bound["path"], str(preregistration.resolve()))
            self.assertEqual(bound["bytes"], len(preregistration.read_bytes()))
            self.assertEqual(len(bound["sha256"]), 64)

            preregistration.write_text('{"version":4}\n', encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "config does not match"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                    "--timeout", "20", "--workdir", str(root / "runs"),
                    "--output", str(output), "--preregistration", str(preregistration),
                    "--resume",
                ])

    def test_resume_rejects_changed_experiment_config(self):
        client = type("Client", (), {"config": self.Config()})()

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value={
            "git_available": True, "git_revision": "abc",
            "source_tree_dirty": False, "source_changes": [],
        }):
            output = Path(tmp) / "report.json"
            workdir = Path(tmp) / "runs"
            self.assertEqual(MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
            ]), 0)
            with self.assertRaisesRegex(SystemExit, "config does not match"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster", "--budget", "1", "--seeds", "0",
                    "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
                    "--resume",
                ])

    def test_dirty_smoke_executes_but_is_not_trusted_evidence(self):
        client = type("Client", (), {"config": self.Config()})()
        dirty = {"git_available": True, "git_revision": "abc", "source_tree_dirty": True,
                 "source_changes": [" M frontier_science/x.py"]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=dirty):
            output = Path(tmp) / "report.json"
            result = MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(Path(tmp) / "runs"),
                "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertTrue(report["execution_passed"])
            self.assertFalse(report["trusted_evidence"])
            self.assertFalse(report["passed"])

    def test_greedy_only_controls_reject_unsupported_backend_mix(self):
        for mode in ("score_only", "delayed_replay", "selection_blind"):
            with self.subTest(mode=mode), self.assertRaisesRegex(
                SystemExit, "only for greedy_rewrite"
            ):
                MODULE.main([
                    "--tasks", "LennardJonesCluster",
                    "--algorithms", "greedy_rewrite,openevolve",
                    "--feedback-modes", mode,
                    "--budget", "0",
                ])


if __name__ == "__main__":
    unittest.main()
