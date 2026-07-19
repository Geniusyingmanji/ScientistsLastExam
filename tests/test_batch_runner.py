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
        self.assertEqual(got["successful_runs"], 1)
        self.assertEqual(got["failed_runs"], 0)

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


if __name__ == "__main__":
    unittest.main()
