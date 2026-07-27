from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_science.llm import LLMConfig


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

        schedule = MODULE._condition_schedule(
            modes,
            list(range(24)),
            "balanced_williams",
            randomization_seed=834721,
        )
        self.assertEqual(
            schedule,
            MODULE._condition_schedule(
                modes,
                list(range(24)),
                "balanced_williams",
                randomization_seed=834721,
            ),
        )
        self.assertNotEqual(
            schedule,
            MODULE._condition_schedule(
                modes,
                list(range(24)),
                "balanced_williams",
                randomization_seed=834722,
            ),
        )
        for position in range(4):
            counts = {
                mode: sum(row[position] == mode for row in schedule)
                for mode in modes
            }
            self.assertEqual(set(counts.values()), {6})

    def test_williams_order_rejects_non_four_mode_design(self):
        with self.assertRaisesRegex(ValueError, "exactly four"):
            MODULE._condition_order(
                ["normal", "selection_blind"], 0, "balanced_williams"
            )
        with self.assertRaisesRegex(ValueError, "requires"):
            MODULE._condition_schedule(
                ["normal", "score_only", "delayed_replay", "selection_blind"],
                list(range(4)),
                "balanced_williams",
                randomization_seed=None,
            )
        with self.assertRaisesRegex(ValueError, "requires balanced_williams"):
            MODULE._condition_schedule(
                ["normal"], [0], "reverse_parity", randomization_seed=1
            )

    def test_execution_blocks_keep_conditions_serial_with_fixed_indices(self):
        modes = ["normal", "score_only", "delayed_replay", "selection_blind"]
        seeds = [3, 7, 11, 15]
        schedule = MODULE._condition_schedule(
            modes, seeds, "balanced_williams", randomization_seed=834721
        )
        blocks = MODULE._execution_blocks(
            ["T/A", "T/B"], ["greedy_rewrite"], seeds, schedule
        )
        self.assertEqual(len(blocks), 8)
        self.assertEqual(
            [row["block_index"] for row in blocks], list(range(1, 9))
        )
        self.assertEqual(
            [(row["task"], row["seed"]) for row in blocks[:4]],
            [("T/A", seed) for seed in seeds],
        )
        for block in blocks:
            self.assertEqual(
                block["feedback_modes"], schedule[seeds.index(block["seed"])]
            )
            self.assertEqual(set(block["feedback_modes"]), set(modes))

    def test_block_resume_retries_started_cell_then_runs_unstarted_cells(self):
        task = "Chemistry/LennardJonesCluster"
        modes = ["normal", "score_only"]
        source = MODULE.find_task(
            task, include_uncertified=True
        ).initial_program_path.read_text(encoding="utf-8")
        fenced = "```python\n%s\n```" % source
        config = LLMConfig(
            wire="chat", base_url="https://example.invalid/v1",
            model="fixture", max_output_tokens=20, temperature=0.0,
            timeout_seconds=1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "block_index": 1,
                "task": task,
                "algorithm": "greedy_rewrite",
                "seed": 0,
                "feedback_modes": modes,
                "llm_config": config,
                "work_root": str(root),
                "budget": 1,
                "timeout_s": 20.0,
                "resume": False,
                "skip_keys": [],
            }
            failing = type("Failing", (), {
                "config": config,
                "last_usage": {},
                "complete": lambda self, prompt, system=None: (
                    (_ for _ in ()).throw(RuntimeError("offline"))
                ),
            })()
            with patch.object(MODULE, "LLMClient", return_value=failing):
                first = MODULE._execute_block(payload)
            self.assertEqual(len(first["entries"]), 1)
            self.assertIn("LLMInfrastructureError", first["entries"][0]["error"])
            normal_dir = (
                root / "Chemistry__LennardJonesCluster" / "greedy_rewrite"
                / "normal" / "seed_0"
            )
            self.assertTrue((normal_dir / "checkpoint.json").is_file())
            self.assertEqual(
                len((normal_dir / "trajectory.jsonl").read_text().splitlines()), 1
            )

            replies = iter([fenced, fenced])
            recovered = type("Recovered", (), {
                "config": config,
                "last_usage": {},
                "complete": lambda self, prompt, system=None: next(replies),
            })()
            payload["resume"] = True
            with patch.object(MODULE, "LLMClient", return_value=recovered):
                second = MODULE._execute_block(payload)
            self.assertEqual(len(second["entries"]), 2)
            self.assertFalse(any(row.get("error") for row in second["entries"]))
            self.assertEqual(
                [row["within_block_position"] for row in second["entries"]],
                [1, 2],
            )
            self.assertEqual(
                len((normal_dir / "trajectory.jsonl").read_text().splitlines()), 2
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
            "run_cells_with_protocol_incomplete_attempt": 0,
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

    def test_fixed_duration_budget_exhaustion_is_protocol_incomplete(self):
        incomplete = {
            "task": "T/X",
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
            "seed": 0,
            "best": 0.8,
            "protocol_incomplete": (
                "proposal_budget_exhausted_before_active_wall_horizon"
            ),
            "summary": {
                "best_so_far_auc": 0.7,
                "budget_units": 4,
                "oracle_calls": 4,
                "wall_seconds": 20,
                "llm": {"total_tokens": 100, "estimated_cost_usd": None},
            },
        }
        got = MODULE.aggregate_runs([incomplete])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 0)
        self.assertEqual(condition["protocol_incomplete_attempts"], 1)
        self.assertEqual(got["successful_runs"], 0)
        self.assertEqual(got["failed_runs"], 1)
        self.assertEqual(got["protocol_incomplete_attempts"], 1)
        self.assertEqual(
            got["intent_to_evaluate"][
                "run_cells_with_protocol_incomplete_attempt"
            ],
            1,
        )

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

    def test_cohort_manifest_binds_order_contract_and_task_card(self):
        tasks = [
            "Electrochemistry/ElectrolyteConductivityDesign",
            "Optics/DiffractionGratingDesign",
        ]
        specs = [
            MODULE.find_task(task, include_uncertified=True) for task in tasks
        ]
        rows = []
        for spec in specs:
            rows.append({
                "task": spec.task_id,
                "maturity_contract_sha256": MODULE._maturity_contract_sha256(spec),
                "runtime_contract_sha256": MODULE.task_contract_sha256(spec),
                "task_card_sha256": MODULE.hashlib.sha256(
                    (spec.task_dir / "TASK_CARD.yaml").read_bytes()
                ).hexdigest(),
            })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohort.json"
            document = {
                "schema_version": 1,
                "manifest_id": "fixture",
                "analysis_role": "exploratory",
                "claim_limit": "not_confirmatory",
                "selection": {"confirmatory_reuse_permitted": False},
                "tasks": rows,
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            record = MODULE._cohort_manifest_record(
                path, specs, include_uncertified=True
            )
            self.assertEqual(record["task_count"], 2)
            self.assertFalse(record["confirmatory_reuse_permitted"])
            self.assertEqual(record["manifest_id"], "fixture")

            with self.assertRaisesRegex(SystemExit, "task order"):
                MODULE._cohort_manifest_record(
                    path, list(reversed(specs)), include_uncertified=True
                )
            document["tasks"][0]["runtime_contract_sha256"] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "runtime contract"):
                MODULE._cohort_manifest_record(
                    path, specs, include_uncertified=True
                )
            document["tasks"][0]["maturity_contract_sha256"] = "0" * 64
            document["tasks"][0]["runtime_contract_sha256"] = (
                MODULE.task_contract_sha256(specs[0])
            )
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "maturity contract"):
                MODULE._cohort_manifest_record(
                    path, specs, include_uncertified=True
                )

    def test_frozen_exploratory_manifest_matches_current_contracts(self):
        path = (
            Path(__file__).resolve().parents[1]
            / ".research/exploratory_2h_cohort_manifest_2026-07-27_v1.json"
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        specs = [
            MODULE.find_task(row["task"], include_uncertified=True)
            for row in document["tasks"]
        ]
        record = MODULE._cohort_manifest_record(
            path, specs, include_uncertified=True
        )
        self.assertEqual(record["task_count"], 7)
        self.assertEqual(
            record["analysis_role"],
            "result_selected_exploratory_measurement_screen",
        )
        self.assertFalse(record["confirmatory_reuse_permitted"])

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

    def test_active_wall_horizon_is_greedy_only_and_interval_requires_horizon(self):
        with self.assertRaisesRegex(SystemExit, "requires --active-wall-horizon"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--sentinel-interval", "30",
                "--budget", "0",
            ])
        with self.assertRaisesRegex(SystemExit, "only for greedy_rewrite"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--algorithms", "abmcts",
                "--active-wall-horizon", "120",
                "--budget", "0",
            ])


if __name__ == "__main__":
    unittest.main()
