from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from sle import episode_panel as panel
from sle.scientific_episode import digest


def cell(policy, world, metrics=None, status="completed", spent=1):
    return {"policy": policy, "world_index": world, "metrics": metrics,
            "status": status, "resources": {"experiment_units": spent}}


class PanelEnvironment:
    task_id = "Test/Panel"
    budget_units = 3

    def __init__(self, seed):
        self.seed = seed

    def public_problem(self):
        return {"budget_units": self.budget_units}

    def action_cost(self, tool, arguments):
        return 1

    def experiment(self, tool, arguments):
        return {"value": 0.5}

    def validate_claim(self, claim):
        if set(claim) != {"estimate"}:
            raise ValueError("invalid claim")

    def confirm(self, claim):
        return {"measurement": 0.5}

    def evaluate(self, claim, confirmation):
        return {"error": abs(claim["estimate"] - 0.5),
                "coverage": {"numerator": 1, "denominator": 1, "value": 1}}


def observed(problem, execute):
    for _ in range(problem["budget_units"]):
        result = execute("measure", {})
    return {"estimate": result["value"]}


def constant(problem, execute):
    return {"estimate": 0}


class EpisodePanelTests(unittest.TestCase):
    def test_ratios_are_pooled_with_denominators_and_failures_never_become_zero(self):
        cells = [cell("a", 0, {"error": 2, "fdr": {"numerator": 1, "denominator": 2}}),
                 cell("a", 1, {"error": 4, "fdr": {"numerator": 0, "denominator": 100}}),
                 cell("a", 2, status="invalid_candidate")]
        result = panel.summarize_cells(cells, ["a"])["policies"]["a"]
        self.assertEqual(result["scalar_metrics"]["error"], {"n": 2, "mean": 3, "min": 2, "max": 4})
        self.assertEqual(result["pooled_ratios"]["fdr"]["value"], 1 / 102)
        self.assertEqual(result["status_counts"], {"completed": 2, "invalid_candidate": 1})

    def test_flat_rate_axes_are_not_averaged_again_and_zero_denominator_stays_null(self):
        metrics = {"false_discovery_numerator": 0, "false_discovery_denominator": 0,
                   "false_discovery_rate": None, "estimate": 0.3}
        result = panel.summarize_cells([cell("a", 0, metrics)], ["a"])["policies"]["a"]
        self.assertEqual(set(result["scalar_metrics"]), {"estimate"})
        self.assertIsNone(result["pooled_ratios"]["false_discovery"]["value"])

    def test_invalid_ratio_fails_closed(self):
        for numerator, denominator in ((2, 1), (1, 0), (float("nan"), 1), (True, 1)):
            with self.subTest(numerator=numerator), self.assertRaises(ValueError):
                panel.summarize_cells([cell("a", 0, {"rate": {
                    "numerator": numerator, "denominator": denominator}})], ["a"])

    def test_conflicting_ratio_representations_fail_in_either_order(self):
        pairs = [("fdr", {"numerator": 1, "denominator": 2}),
                 ("fdr_numerator", 0), ("fdr_denominator", 2)]
        for entries in (pairs, list(reversed(pairs))):
            with self.assertRaisesRegex(ValueError, "conflicting metric ratio"):
                panel._axes(dict(entries))

    def test_explicit_invalid_metrics_are_excluded_from_science_and_pairs(self):
        rows = [cell("a", 0, {"valid": False, "error": 0}),
                cell("b", 0, {"valid": True, "error": 1})]
        summary = panel.summarize_cells(rows, ["a", "b"], "error")
        self.assertEqual(summary["policies"]["a"]["completed_worlds"], 1)
        self.assertEqual(summary["policies"]["a"]["scientifically_valid_worlds"], 0)
        self.assertEqual(summary["policies"]["a"]["scalar_metrics"], {})
        self.assertEqual(summary["paired_comparisons"][0]["difference_left_minus_right"]["n"], 0)

    def test_paired_summary_records_valid_intersection_and_actual_cost_difference(self):
        cells = [cell("a", 0, {"error": 0.1}, spent=2), cell("b", 0, {"error": 0.4}),
                 cell("a", 1, {"error": 0.2}), cell("b", 1, status="budget_exhausted")]
        result = panel.summarize_cells(cells, ["a", "b"], "error")["paired_comparisons"][0]
        self.assertEqual(result["difference_left_minus_right"]["n"], 1)
        self.assertAlmostEqual(result["difference_left_minus_right"]["mean"], -0.3)
        self.assertEqual(result["equal_actual_spend_pairs"], 0)

    def _patches(self, directory, bindings=None):
        return (
            patch.object(panel, "_task_directory", return_value=("Test/Panel", directory)),
            patch.object(panel, "_load_module", return_value=SimpleNamespace(POLICIES={"observed": observed, "constant": constant})),
            patch.object(panel, "create_environment", side_effect=lambda task, seed: PanelEnvironment(seed)),
            patch.object(panel, "source_binding", side_effect=bindings or (lambda task: {"task_id": "Test/Panel"})),
        )

    def test_full_panel_binds_private_cells_and_applies_same_cap(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            a, b, c, d = self._patches(directory)
            with a, b, c as created, d:
                report, path = panel.run_panel("Test/Panel", ["observed", "constant"], directory / "private",
                                                world_count=2, seed_start=99, budget_units=2, primary_metric="error")
            self.assertEqual(created.call_count, 4)
            self.assertEqual([call.args[1] for call in created.call_args_list], [99, 99, 100, 100])
            self.assertFalse(report["frontier_eligible"])
            self.assertEqual(report["frontier_model_draws"], 0)
            for row in report["cells"]:
                episode = json.loads((path.parent / row["episode_path"]).read_text())
                self.assertEqual(episode["resources"]["budget_units"], 2)
                self.assertEqual(episode["sha256"], row["episode_sha256"])
                self.assertEqual((path.parent / row["episode_path"]).stat().st_mode & 0o777, 0o600)
            self.assertEqual(report["sha256"], digest({key: value for key, value in report.items() if key != "sha256"}))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_source_change_during_panel_cannot_produce_aggregate(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            a, b, c, d = self._patches(directory, [{"task_id": "Test/Panel", "source": 1},
                                                 {"task_id": "Test/Panel", "source": 2}])
            with a, b, c, d, self.assertRaisesRegex(ValueError, "changed during panel"):
                panel.run_panel("Test/Panel", ["constant"], directory / "private", world_count=1)
            self.assertFalse((directory / "private" / "panel.json").exists())

    def test_initialization_failure_preserves_cell_and_continues(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            a, b, c, d = self._patches(directory)
            with a, b, c as created, d:
                created.side_effect = [RuntimeError("oracle initialization failed"), PanelEnvironment(1)]
                report, path = panel.run_panel("Test/Panel", ["constant"], directory / "private", world_count=2)
            self.assertEqual([row["status"] for row in report["cells"]], ["infrastructure_error", "completed"])
            failed = report["cells"][0]
            self.assertIsNone(failed["metrics"])
            self.assertNotIn("episode_path", failed)
            failure_path = path.parent / failed["failure_path"]
            failure = json.loads(failure_path.read_text())
            self.assertEqual(failure["sha256"], failed["failure_sha256"])
            self.assertEqual(failure_path.stat().st_mode & 0o777, 0o600)
            summary = report["summary"]["policies"]["constant"]
            self.assertEqual(summary["scalar_metrics"]["error"]["n"], 1)

    def test_unknown_policy_and_nonempty_output_rejected(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            a, b, c, d = self._patches(directory)
            with a, b, c, d:
                with self.assertRaisesRegex(ValueError, "unknown policy"):
                    panel.run_panel("Test/Panel", ["bad"], directory / "private")
                private = directory / "private"
                private.mkdir(mode=0o700)
                (private / "old-result").write_text("preserve")
                with self.assertRaisesRegex(ValueError, "empty"):
                    panel.run_panel("Test/Panel", ["constant"], private, world_count=1)
                self.assertEqual((private / "old-result").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
