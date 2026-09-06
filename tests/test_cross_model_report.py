"""Pin the cross-model comparison, especially the rank statistic and the two-model guard.

A single-model repository cannot claim discrimination, and the first thing this report has to do
is say so plainly rather than print an empty table that reads like agreement.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "report_cross_model.py"
    spec = importlib.util.spec_from_file_location("cross_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def write_run(root, cohort, name, task, model, mode, seed, scores, usage=(0, 0),
              contract="c" * 64, condition=None, runtime="r" * 64,
              trusted_runtime="t" * 64, algorithm="greedy_rewrite", budget=None,
              manifest_budget=None):
    workdir = root / cohort / name
    workdir.mkdir(parents=True)
    (workdir / "run_manifest.json").write_text(json.dumps({
        "task_id": task, "feedback_mode": mode, "seed": seed,
        "llm_condition": {"model": model},
        "llm_condition_sha256": condition or ("condition:" + model),
        "task_package_sha256": contract,
        "runtime_source_sha256": runtime,
        "trusted_evaluator_runtime": {"fingerprint_sha256": trusted_runtime},
        "algorithm": algorithm,
        "config": {"budget": manifest_budget if manifest_budget is not None
                   else (budget or len(scores))},
    }), encoding="utf-8")
    lines = []
    for index, score in enumerate(scores, start=1):
        lines.append(json.dumps({"step": index, "valid": True, "score": score,
                                 "llm": {"input_tokens": usage[0], "output_tokens": usage[1]}}))
    (workdir / "trajectory.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def admission_row(model, verdict, contract="c" * 64, budget_signature=(1, 3)):
    return {
        "task": "T/X",
        "model": model,
        "llm_condition_sha256": "condition:" + model,
        "task_version": MODULE.version_class("T/X", contract)[:14],
        "runtime_source_sha256": "r" * 64,
        "trusted_evaluator_runtime_sha256": "t" * 64,
        "algorithm": "greedy_rewrite",
        "trusted_evidence": True,
        "paired_budget_signature": list(budget_signature),
        "verdict": verdict,
    }


class SpearmanTests(unittest.TestCase):
    def test_identical_orderings_correlate_perfectly(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)

    def test_reversed_orderings_correlate_negatively(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_ties_use_average_ranks_rather_than_arbitrary_order(self):
        self.assertAlmostEqual(MODULE.spearman([1, 1, 2, 3], [1, 1, 2, 3]), 1.0)

    def test_a_constant_column_has_no_correlation_rather_than_a_crash(self):
        self.assertIsNone(MODULE.spearman([1, 1, 1, 1], [1, 2, 3, 4]))

    def test_fewer_than_three_points_is_not_computable(self):
        self.assertIsNone(MODULE.spearman([1, 2], [2, 1]))


class ReportTests(unittest.TestCase):
    @staticmethod
    def run_report(root, admission=None):
        with TemporaryDirectory() as out:
            target = Path(out) / "cross.json"
            argv = ["--runs", str(root), "--output", str(target)]
            if admission:
                argv += ["--admission", str(admission)]
            buffer = io.StringIO()
            def verified(path, **_kwargs):
                manifest = json.loads((Path(path) / "run_manifest.json").read_text())
                steps = [
                    json.loads(line)["step"]
                    for line in (Path(path) / "trajectory.jsonl").read_text().splitlines()
                    if line.strip()
                ]
                return {
                    "verified": True,
                    "budget": max(steps),
                    "trusted_evaluator_runtime_sha256": manifest[
                        "trusted_evaluator_runtime"
                    ]["fingerprint_sha256"],
                }
            with patch.object(MODULE, "verify_run", side_effect=verified), \
                    contextlib.redirect_stdout(buffer):
                MODULE.main(argv)
            return json.loads(target.read_text(encoding="utf-8")), buffer.getvalue()

    def test_one_model_is_reported_as_not_a_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "a", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.1, 0.4])
            report, text = self.run_report(root)
            self.assertEqual(report["models"], ["gpt-5.5"])
            self.assertIn("needs two", text)

    def test_unverified_run_is_excluded_from_scientific_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "a", "w", "T/X", "gpt-5.5", "selection_blind", 0,
                      [0.1, 0.4])
            with patch.object(MODULE, "verify_run", side_effect=ValueError("unbound")):
                rows = MODULE.read_runs(root)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["trusted_evidence"])

    def test_two_models_on_shared_tasks_are_ranked_side_by_side(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, task in enumerate(["T/A", "T/B", "T/C"]):
                write_run(root, "g", "g%d" % index, task, "gpt-5.5", "selection_blind", 0,
                          [0.1 * (index + 1)])
                write_run(root, "c", "c%d" % index, task, "claude-opus-4-8", "selection_blind", 0,
                          [0.2 * (index + 1)])
            report, text = self.run_report(root)
            self.assertEqual(report["models"], ["claude-opus-4-8", "gpt-5.5"])
            self.assertEqual(len(report["shared_tasks"]), 3)
            self.assertIn("rank correlation", text)

    def test_models_that_ran_different_task_versions_are_excluded(self):
        """Comparing across a task edit reports the edit as a model difference."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, task in enumerate(["T/A", "T/B", "T/C"]):
                write_run(root, "g", "g%d" % index, task, "gpt-5.5", "selection_blind", 0,
                          [0.1 * (index + 1)], contract="old" + "0" * 61)
                write_run(root, "c", "c%d" % index, task, "claude-opus-4-8", "selection_blind", 0,
                          [0.2 * (index + 1)], contract="new" + "0" * 61)
            report, text = self.run_report(root)
            self.assertEqual(report["shared_tasks"], [])
            self.assertIn("no task where both ran the same version", text)
            pair = report["pairwise"][0]
            self.assertEqual(len(pair["excluded_for_contract_mismatch"]), 3)
            self.assertIsNone(pair["rho"])

    def test_models_on_different_evaluator_runtimes_are_not_compared(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "g", "T/X", "gpt-5.5", "selection_blind", 0,
                      [0.1], trusted_runtime="a" * 64)
            write_run(root, "c", "c", "T/X", "claude-opus-4-8",
                      "selection_blind", 0, [0.2], trusted_runtime="b" * 64)
            report, text = self.run_report(root)
            self.assertEqual(report["pairwise"], [])
            self.assertEqual(len(report["incomparable_condition_pairs"]), 1)
            self.assertIn("runtime/statistical-arm identity differs", text)

    def test_the_same_contract_is_compared(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, task in enumerate(["T/A", "T/B", "T/C"]):
                write_run(root, "g", "g%d" % index, task, "gpt-5.5", "selection_blind", 0,
                          [0.1 * (index + 1)])
                write_run(root, "c", "c%d" % index, task, "claude-opus-4-8", "selection_blind", 0,
                          [0.2 * (index + 1)])
            report, _ = self.run_report(root)
            self.assertEqual(len(report["shared_tasks"]), 3)
            self.assertEqual(report["pairwise"][0]["rho"], 1.0)

    def test_conditions_algorithms_and_runtimes_are_not_averaged_before_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, task in enumerate(["T/A", "T/B", "T/C"]):
                write_run(root, "g", "g%d" % index, task, "gpt-5.5",
                          "selection_blind", 0, [0.1], condition="g-condition-a")
                write_run(root, "g", "g-alt%d" % index, task, "gpt-5.5",
                          "selection_blind", 1, [0.9], condition="g-condition-b")
                write_run(root, "c", "c%d" % index, task, "claude-opus-4-8",
                          "selection_blind", 0, [0.2], condition="c-condition")
            report, _ = self.run_report(root)
            pairs = [row for row in report["pairwise"] if row["tasks"]]
            self.assertEqual(len(pairs), 2)
            self.assertEqual(
                {row["conditions"][0]["llm_condition_sha256"] for row in pairs
                 if row["conditions"][0]["model"] == "gpt-5.5"}
                | {row["conditions"][1]["llm_condition_sha256"] for row in pairs
                   if row["conditions"][1]["model"] == "gpt-5.5"},
                {"g-condition-a", "g-condition-b"},
            )

    def test_modes_and_budgets_are_not_averaged_before_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, task in enumerate(["T/A", "T/B", "T/C"]):
                write_run(root, "g", "g%d" % index, task, "gpt-5.5",
                          "selection_blind", 0, [0.1], budget=1)
                write_run(root, "g", "g-alt%d" % index, task, "gpt-5.5",
                          "blind", 1, [0.9, 0.9, 0.9], budget=3)
                write_run(root, "c", "c%d" % index, task, "claude-opus-4-8",
                          "selection_blind", 0, [0.2], budget=1)
            report, _ = self.run_report(root)
            pairs = [row for row in report["pairwise"] if row["tasks"]]
            self.assertEqual(len(pairs), 1)
            self.assertEqual(
                [condition["feedback_mode"] for condition in pairs[0]["conditions"]],
                ["selection_blind", "selection_blind"],
            )
            self.assertEqual(
                [condition["proposal_budget"] for condition in pairs[0]["conditions"]],
                [1, 1],
            )

    def test_budget_comes_from_verified_summary_not_manifest_config(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "g", "T/X", "gpt-5.5", "selection_blind", 0,
                      [0.1], budget=1, manifest_budget=99)
            write_run(root, "c", "c", "T/X", "claude-opus-4-8",
                      "selection_blind", 0, [0.2], budget=1, manifest_budget=99)
            report, _ = self.run_report(root)
            self.assertEqual(
                [condition["proposal_budget"] for condition in report["pairwise"][0]["conditions"]],
                [1, 1],
            )

    def test_proposal_validity_is_stratified_by_verified_budget(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "b1", "T/X", "gpt-5.5", "selection_blind", 0,
                      [0.1], budget=1)
            write_run(root, "g", "b3", "T/X", "gpt-5.5", "selection_blind", 1,
                      [0.1, 0.2, 0.3], budget=3)
            report, _ = self.run_report(root)
            self.assertEqual(
                {row["proposal_budget"] for row in report["proposal_validity"]},
                {1, 3},
            )

    def test_cost_is_blank_rather_than_guessed_for_an_unpriced_model(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.5],
                      usage=(1000, 2000))
            report, text = self.run_report(root)
            row = next(r for r in report["cost"] if r["model"] == "gpt-5.5")
            self.assertIsNone(row["estimated_usd"])
            self.assertIn("no published price", text)

    def test_a_priced_model_reports_dollars(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "selection_blind", 0, [0.5],
                      usage=(1_000_000, 1_000_000))
            report, _ = self.run_report(root)
            row = next(r for r in report["cost"] if r["model"] == "claude-opus-4-8")
            self.assertAlmostEqual(row["estimated_usd"], 30.0)

    def test_an_unrecorded_model_is_not_treated_as_a_third_model(self):
        """"We do not know which model" cannot agree or disagree with anything."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.5])
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration"),
                admission_row("unrecorded", "thin_screen"),
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertEqual(len(report["verdicts"]["T/X"]), 1)
            self.assertTrue(next(iter(report["verdicts"]["T/X"])).startswith("gpt-5.5@"))
            self.assertIn("disagree: 0", text)

    def test_verdict_disagreement_is_surfaced_not_summarised_away(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.5])
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "normal", 0, [0.5])
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration"),
                admission_row("claude-opus-4-8", "feedback_harmful"),
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertEqual(len(report["verdicts"]["T/X"]), 2)
            self.assertIn("disagree: 1", text)

    def test_verdicts_reached_against_different_task_versions_do_not_disagree(self):
        """Two verdicts about two different versions of a task disagree about nothing."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.5],
                      contract="old" + "0" * 61)
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "normal", 0, [0.5],
                      contract="new" + "0" * 61)
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration", "old" + "0" * 61),
                admission_row("claude-opus-4-8", "feedback_harmful", "new" + "0" * 61),
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertIn("disagree: 0", text)
            self.assertIn("more than one version", text)
            self.assertEqual(report["verdicts_same_version"], {})

    def test_verdicts_with_different_paired_budget_signatures_do_not_agree(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "normal", 0, [0.5])
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "normal", 0, [0.5])
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration", budget_signature=(1, 3)),
                admission_row("claude-opus-4-8", "measures_iteration",
                              budget_signature=(1, 3, 5)),
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertEqual(report["verdicts_same_version"], {})
            self.assertIn("agree: 0", text)

    def test_a_third_model_on_another_version_does_not_hide_a_valid_pair(self):
        """Requiring every model to agree on a version discarded real comparisons."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "normal", 0, [0.5])
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "normal", 0, [0.5])
            write_run(root, "o", "w", "T/X", "gpt-5.6-sol", "normal", 0, [0.5],
                      contract="other" + "0" * 59)
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration"),
                admission_row("claude-opus-4-8", "feedback_harmful"),
                admission_row("gpt-5.6-sol", "thin_screen", "other" + "0" * 59),
            ]}), encoding="utf-8")
            _, text = self.run_report(root, admission=admission)
            # The two that share a version are still compared, and they disagree.
            self.assertIn("disagree: 1", text)

    def test_a_verdict_from_a_normal_only_model_still_compares(self):
        """The verdict check spans both arms, so it must not key off the open-loop arm alone."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "normal", 0, [0.5])
            write_run(root, "c", "w", "T/X", "claude-opus-4-8", "normal", 0, [0.5])
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                admission_row("gpt-5.5", "measures_iteration"),
                admission_row("claude-opus-4-8", "measures_iteration"),
            ]}), encoding="utf-8")
            _, text = self.run_report(root, admission=admission)
            self.assertIn("agree: 1", text)


if __name__ == "__main__":
    unittest.main()
