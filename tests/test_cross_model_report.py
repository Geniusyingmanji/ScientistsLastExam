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


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "report_cross_model.py"
    spec = importlib.util.spec_from_file_location("cross_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def write_run(root, cohort, name, task, model, mode, seed, scores, usage=(0, 0),
              contract="c" * 64):
    workdir = root / cohort / name
    workdir.mkdir(parents=True)
    (workdir / "run_manifest.json").write_text(json.dumps({
        "task_id": task, "feedback_mode": mode, "seed": seed,
        "llm_condition": {"model": model}, "task_package_sha256": contract,
    }), encoding="utf-8")
    lines = []
    for index, score in enumerate(scores, start=1):
        lines.append(json.dumps({"step": index, "valid": True, "score": score,
                                 "llm": {"input_tokens": usage[0], "output_tokens": usage[1]}}))
    (workdir / "trajectory.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
            with contextlib.redirect_stdout(buffer):
                MODULE.main(argv)
            return json.loads(target.read_text(encoding="utf-8")), buffer.getvalue()

    def test_one_model_is_reported_as_not_a_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "a", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.1, 0.4])
            report, text = self.run_report(root)
            self.assertEqual(report["models"], ["gpt-5.5"])
            self.assertIn("needs two", text)

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
            self.assertIn("different versions of the task", text)

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
                {"task": "T/X", "model": "gpt-5.5", "verdict": "measures_iteration"},
                {"task": "T/X", "model": "unrecorded", "verdict": "thin_screen"},
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertEqual(set(report["verdicts"]["T/X"]), {"gpt-5.5"})
            self.assertIn("disagree: 0", text)

    def test_verdict_disagreement_is_surfaced_not_summarised_away(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "g", "w", "T/X", "gpt-5.5", "selection_blind", 0, [0.5])
            admission = Path(tmp) / "adm.json"
            admission.write_text(json.dumps({"rows": [
                {"task": "T/X", "model": "gpt-5.5", "verdict": "measures_iteration"},
                {"task": "T/X", "model": "claude-opus-4-8", "verdict": "feedback_harmful"},
            ]}), encoding="utf-8")
            report, text = self.run_report(root, admission=admission)
            self.assertEqual(set(report["verdicts"]["T/X"]), {"gpt-5.5", "claude-opus-4-8"})
            self.assertIn("disagree: 1", text)


if __name__ == "__main__":
    unittest.main()
