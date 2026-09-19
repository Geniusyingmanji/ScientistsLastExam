"""Fixed-plan operator workflows: no model calls and no invented completed cells."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import task_campaign as campaign


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binding = {"task_id": "Fixture/Task", "task_package_sha256": "p" * 64,
                        "task_contract_sha256": "t" * 64, "runtime_source_sha256": "r" * 64,
                        "llm_condition_sha256": "l" * 64, "model": "fixture-model",
                        "orchestration_sha256": "o" * 64}

    def plan(self, kind="delta_ladder", **kwargs):
        with patch.object(campaign, "bindings", return_value=self.binding):
            return campaign.make_plan(kind, task="Fixture/Task", config=self.root / "config.yaml",
                                      workdir=self.root / "runs", seeds=[0, 1, 2],
                                      budgets=kwargs.pop("budgets", [1, 3]), **kwargs)

    def populate(self, plan, selected_cells=None):
        selected_cells = plan["cells"] if selected_cells is None else selected_cells
        for cohort in plan["cohorts"]:
            config = {"tasks": [plan["bindings"]["task_id"]], "algorithms": [plan["algorithm"]],
                      "seeds": plan["seeds"], "feedback_modes": plan["feedback_modes"],
                      "budget": cohort["proposal_budget"], "timeout_s": plan["timeout_s"],
                      "active_wall_horizon_s": cohort["active_wall_horizon_s"],
                      "llm_condition_sha256": plan["bindings"]["llm_condition_sha256"]}
            entries = []
            for cell in selected_cells:
                if cell["cohort"] != cohort["id"]:
                    continue
                directory = Path(cell["workdir"])
                directory.mkdir(parents=True, exist_ok=True)
                manifest = {key: plan["bindings"][key] for key in (
                    "task_id", "task_package_sha256", "task_contract_sha256",
                    "runtime_source_sha256", "llm_condition_sha256")}
                manifest.update(seed=cell["seed"], feedback_mode=cell["feedback_mode"],
                                algorithm=plan["algorithm"], protocol={
                                    "evaluator_timeout_seconds": plan["timeout_s"],
                                    "active_wall_horizon_s": cohort["active_wall_horizon_s"]})
                (directory / "run_manifest.json").write_text(json.dumps(manifest))
                endpoint = 0.4 if cell["feedback_mode"] == "normal" else 0.2
                events = []
                for step in range(cohort["proposal_budget"] + 1):
                    score = 0.1 if step == 0 else endpoint if step == 1 else 0.01
                    events.append({"schema_version": 2, "step": step, "oracle_calls": step + 1,
                                   "budget_units": step + 1, "score": score,
                                   "best_score": 0.1 if step == 0 else endpoint,
                                   "accepted": step <= 1, "valid": True,
                                   "wall_seconds": 1.0, "cumulative_wall_seconds": step + 1.0,
                                   "candidate_sha256": str(step) * 64, "parent_sha256": "0" * 64,
                                   "metrics": {"combined_score": score, "valid": 1},
                                   "llm": {"total_tokens": 3}, "algorithm_metadata": {}})
                if cohort["active_wall_horizon_s"] is not None:
                    events[-1]["cumulative_wall_seconds"] = cohort["active_wall_horizon_s"] + 1
                    events[-1]["wall_seconds"] = events[-1]["cumulative_wall_seconds"] - events[-2]["cumulative_wall_seconds"]
                payload = "\n".join(json.dumps(event) for event in events) + "\n"
                (directory / "trajectory.jsonl").write_text(payload)
                entries.append({"task": plan["bindings"]["task_id"], "algorithm": plan["algorithm"],
                                "seed": cell["seed"], "feedback_mode": cell["feedback_mode"],
                                "workdir": str(directory), "summary": {"horizon_reached": True},
                                "trajectory_snapshot": {"trajectory_sha256": hashlib.sha256(payload.encode()).hexdigest()}})
            path = Path(cohort["batch_output"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"config": config, "runs": entries}))

    def test_budget_grid_contains_both_arms_and_stays_fixed(self):
        plan = self.plan()
        self.assertEqual(len(plan["cells"]), 12)
        self.assertEqual(plan["feedback_modes"], ["normal", "selection_blind"])
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan))
        self.assertEqual(campaign.read_plan(path), plan)
        plan["budgets"][0] = 500
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "hash"):
            campaign.read_plan(path)

    def test_calibration_is_one_open_loop_draw_per_seed_by_cli_default(self):
        with patch.object(campaign, "bindings", return_value=self.binding), \
             patch.object(campaign, "source_provenance", return_value={"git_available": True, "git_revision": "fixture", "source_tree_dirty": False}), \
             patch.object(campaign.subprocess, "run") as run:
            rc = campaign.main("calibration", ["--plan", str(self.root / "plan.json"),
                "--output", str(self.root / "report.json"), "--task", "Fixture/Task",
                "--llm-config", str(self.root / "config.yaml"), "--workdir", str(self.root / "runs")])
        self.assertEqual(rc, 0)
        run.assert_not_called()
        plan = campaign.read_plan(self.root / "plan.json")
        self.assertEqual(plan["budgets"], [1])
        self.assertEqual(plan["feedback_modes"], ["selection_blind"])
        self.assertEqual(len(plan["cells"]), 3)
        self.assertEqual(json.loads((self.root / "report.json").read_text())["status"], "planned")

    def test_missing_and_partial_pairs_keep_the_full_denominator(self):
        plan = self.plan()
        with patch.object(campaign, "load_llm_client") as client:
            report = campaign.replay(plan)
        client.assert_not_called()
        self.assertEqual(report["scheduled_cells"], 12)
        self.assertEqual(report["cell_status_counts"], {"missing": 12})
        self.populate(plan, plan["cells"][:2])
        report = campaign.replay(plan)
        self.assertEqual(report["complete_cells"], 2, report)
        self.assertAlmostEqual(report["completion_rate"], 2 / 12)
        self.assertIsNone(report["ladder"][0]["mean_delta"])
        self.assertAlmostEqual(report["paired"][0]["delta"], 0.2)

    def test_complete_replay_retains_rejected_proposal_incumbent(self):
        plan = self.plan()
        self.populate(plan)
        with patch.object(campaign.subprocess, "run") as run:
            report = campaign.replay(plan)
        run.assert_not_called()
        self.assertEqual(report["status"], "complete", report)
        self.assertAlmostEqual(report["ladder"][1]["mean_delta"], 0.2)
        self.assertEqual(report["cells"][-2]["endpoint"], 0.4)
        self.assertEqual(report["scientific_admission"], "not_assessed")
        self.assertFalse(report["trusted_evidence"])

    def test_wrong_model_manifest_and_bad_snapshot_are_explicit(self):
        plan = self.plan(budgets=[1])
        self.populate(plan)
        path = Path(plan["cells"][0]["workdir"]) / "run_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["llm_condition_sha256"] = "different"
        path.write_text(json.dumps(manifest))
        report = campaign.replay(plan)
        self.assertEqual(report["cells"][0]["status"], "invalid_evidence")
        trajectory = Path(plan["cells"][1]["workdir"]) / "trajectory.jsonl"
        trajectory.write_text(trajectory.read_text() + "\n")
        report = campaign.replay(plan)
        self.assertIn("snapshot", report["cells"][1]["detail"])

    def test_wrong_budget_config_and_damaged_batch_never_look_complete(self):
        plan = self.plan()
        self.populate(plan)
        path = Path(plan["cohorts"][0]["batch_output"])
        batch = json.loads(path.read_text())
        batch["config"]["budget"] = 99
        path.write_text(json.dumps(batch))
        self.assertEqual(campaign.replay(plan)["cells"][0]["status"], "invalid_evidence")
        path.write_text("{bad json")
        self.assertEqual(campaign.replay(plan)["cells"][0]["status"], "invalid_evidence")

    def test_repeated_failed_attempt_does_not_disappear(self):
        plan = self.plan(budgets=[1])
        self.populate(plan)
        path = Path(plan["cohorts"][0]["batch_output"])
        batch = json.loads(path.read_text())
        failed = copy.deepcopy(batch["runs"][0])
        failed["error"] = "transport_failure"
        batch["runs"].append(failed)
        path.write_text(json.dumps(batch))
        cell = campaign.replay(plan)["cells"][0]
        self.assertEqual(cell["status"], "failed")
        self.assertEqual(cell["attempt_count"], 2)

    def test_active_wall_requires_cap_and_does_not_call_proposal_reporter(self):
        with self.assertRaisesRegex(ValueError, "proposal-cap"):
            self.plan(budget_mode="active_wall", budgets=[10])
        plan = self.plan(budget_mode="active_wall", budgets=[10], proposal_cap=2)
        self.assertIn("--active-wall-horizon", campaign.batch_command(plan, plan["cohorts"][0]))
        self.populate(plan)
        report = campaign.replay(plan)
        self.assertEqual(report["status"], "complete", report)
        self.assertEqual(campaign.build_reports(plan, report, self.root / "reports")["status"], "unavailable")

    def test_execution_refuses_changed_bindings_before_subprocess(self):
        plan = self.plan()
        with patch.object(campaign.platform, "system", return_value="Linux"), \
             patch.object(campaign, "source_provenance", return_value={"git_available": True, "source_tree_dirty": False}), \
             patch.object(campaign, "bindings", return_value={}), patch.object(campaign.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "changed after planning"):
                campaign.execute(plan)
        run.assert_not_called()

    def test_active_wall_flag_without_measured_horizon_is_incomplete(self):
        plan = self.plan(budget_mode="active_wall", budgets=[10], proposal_cap=2)
        self.populate(plan)
        cell = plan["cells"][0]
        trajectory = Path(cell["workdir"]) / "trajectory.jsonl"
        events = [json.loads(line) for line in trajectory.read_text().splitlines()]
        events[-1]["cumulative_wall_seconds"] = 3.0
        events[-1]["wall_seconds"] = 1.0
        payload = "\n".join(map(json.dumps, events)) + "\n"
        trajectory.write_text(payload)
        path = Path(plan["cohorts"][0]["batch_output"])
        batch = json.loads(path.read_text())
        batch["runs"][0]["trajectory_snapshot"]["trajectory_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
        path.write_text(json.dumps(batch))
        replayed = campaign.replay(plan)
        self.assertEqual(replayed["cells"][0]["status"], "incomplete")
        self.assertIn("before the active-wall horizon", replayed["cells"][0]["detail"])

    def test_failed_execution_cannot_pass_by_replaying_previous_complete_results(self):
        plan = self.plan()
        self.populate(plan)
        path = self.root / "plan.json"
        output = self.root / "output.json"
        path.write_text(json.dumps(plan))
        with patch.object(campaign, "execute", return_value=[{"cohort": "budget_00", "returncode": 2}]):
            rc = campaign.main("delta_ladder", ["--plan", str(path), "--output", str(output), "--execute"])
        report = json.loads(output.read_text())
        self.assertEqual(rc, 2)
        self.assertEqual(report["status"], "execution_failed")
        self.assertEqual(report["replay_status"], "complete")

    def test_invalid_budgets_and_rewriting_an_existing_plan_are_rejected(self):
        for budgets in ([0], [2, 1], [1, 1], [float("inf")], [1.5]):
            with self.assertRaises(ValueError):
                self.plan(budgets=budgets)
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan()))
        with self.assertRaises(SystemExit):
            campaign.main("delta_ladder", ["--plan", str(path), "--output", str(self.root / "out.json"), "--budgets", "20"])

    def test_auxiliary_report_commands_resolve_to_current_optimization_tools(self):
        commands = campaign.report_commands(self.plan(), self.root / "reports")
        self.assertEqual([Path(command[1]).name for command in commands],
                         ["report_admission_criterion.py"])
        self.assertTrue(all(Path(command[1]).is_file() for command in commands))
        self.assertTrue(all((campaign.ROOT / path).is_file()
                            for path in campaign.ORCHESTRATION_FILES))

    def test_auxiliary_reporters_refuse_unplanned_input_runs(self):
        plan = self.plan()
        self.populate(plan)
        alien = Path(plan["workdir"]) / "unplanned"
        alien.mkdir()
        (alien / "run_manifest.json").write_text("{}")
        result = campaign.build_reports(plan, campaign.replay(plan), self.root / "reports")
        self.assertEqual(result["status"], "blocked_unscheduled_runs")


if __name__ == "__main__":
    unittest.main()
