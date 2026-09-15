"""Tests for the report that measures how much of a task's difficulty is its contract.

Its claim is a rank correlation, and a correlation computed over the wrong rows is worse than no
correlation at all: it looks like evidence. These pin the parts that decide which rows exist.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "contract_burden", ROOT / "scripts/report_contract_burden.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SpearmanTests(unittest.TestCase):
    def test_a_perfect_inverse_relationship_is_minus_one(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_a_perfect_relationship_is_one(self):
        self.assertAlmostEqual(MODULE.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)

    def test_ties_do_not_crash_and_use_average_ranks(self):
        self.assertIsNotNone(MODULE.spearman([1, 1, 2, 3], [1, 2, 2, 3]))

    def test_a_constant_column_has_no_correlation_rather_than_a_wrong_one(self):
        self.assertIsNone(MODULE.spearman([1, 1, 1, 1], [1, 2, 3, 4]))

    def test_too_few_points_is_reported_as_not_computable(self):
        self.assertIsNone(MODULE.spearman([1, 2], [2, 1]))


class RowSelectionTests(unittest.TestCase):
    """A task with a handful of proposals cannot support a validity rate."""

    def run_report(self, runs: Path, tmp: Path):
        output = tmp / "burden.json"
        MODULE.main(["--runs", str(runs), "--output", str(output)])
        return json.loads(output.read_text(encoding="utf-8"))

    def test_the_minimum_proposal_count_is_a_real_threshold(self):
        self.assertGreaterEqual(MODULE.MIN_PROPOSALS, 10)

    def test_an_empty_tree_yields_no_rows_and_no_correlation(self):
        with TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runs.mkdir()
            report = self.run_report(runs, Path(tmp))
            self.assertEqual(report["rows"], [])
            self.assertIsNone(report["rank_correlation_lines_vs_validity"])

    def test_full_measurement_identity_is_declared_for_stratification(self):
        self.assertEqual(
            set(MODULE.IDENTITY_FIELDS),
            {
                "task", "task_version", "runtime_source_sha256",
                "trusted_evaluator_runtime_sha256", "algorithm", "model",
                "llm_condition_sha256", "feedback_mode", "proposal_budget",
                "seed",
            },
        )

    def test_unverified_run_is_diagnostic_and_never_measured(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            (task_dir / "verification").mkdir(parents=True)
            (task_dir / "verification/evaluator.py").write_text(
                "# evaluator\n", encoding="utf-8"
            )
            initial = task_dir / "initial.py"
            initial.write_text("# initial\n", encoding="utf-8")
            workdir = root / "runs/run"
            workdir.mkdir(parents=True)
            (workdir / "run_manifest.json").write_text(json.dumps({
                "task_id": "T/X",
                "feedback_mode": "normal",
                "seed": 0,
                "task_package_sha256": "p" * 64,
                "runtime_source_sha256": "r" * 64,
                "trusted_evaluator_runtime": {
                    "fingerprint_sha256": "t" * 64,
                },
                "algorithm": "greedy_rewrite",
                "llm_condition": {"model": "hy3"},
                "llm_condition_sha256": "c" * 64,
                "config": {"budget": MODULE.MIN_PROPOSALS},
            }), encoding="utf-8")
            (workdir / "trajectory.jsonl").write_text(
                "".join(json.dumps({
                    "step": step, "valid": True, "metrics": {},
                }) + "\n" for step in range(1, MODULE.MIN_PROPOSALS + 1)),
                encoding="utf-8",
            )
            spec = SimpleNamespace(
                task_id="T/X", task_dir=task_dir, initial_program_path=initial,
            )
            with patch.object(MODULE, "list_tasks", return_value=[spec]), \
                    patch.object(MODULE, "task_package_sha256", return_value="p" * 64), \
                    patch.object(MODULE, "verify_run", side_effect=ValueError("unbound")):
                report = self.run_report(root / "runs", root)
            self.assertEqual(report["trusted_input_run_count"], 0)
            self.assertEqual(report["unattributable_input_run_count"], 1)
            self.assertEqual(report["rows"], [])
            self.assertEqual(
                report["inputs"][0]["evidence_status"],
                "run_verification_failed",
            )

    def test_seed_zero_and_verified_budget_are_valid_identity_values(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            (task_dir / "verification").mkdir(parents=True)
            (task_dir / "verification/evaluator.py").write_text(
                "# evaluator\n", encoding="utf-8"
            )
            initial = task_dir / "initial.py"
            initial.write_text("# initial\n", encoding="utf-8")
            workdir = root / "runs/run"
            workdir.mkdir(parents=True)
            package = "p" * 64
            (workdir / "run_manifest.json").write_text(json.dumps({
                "task_id": "T/X", "feedback_mode": "normal", "seed": 0,
                "task_package_sha256": package,
                "runtime_source_sha256": "r" * 64,
                "trusted_evaluator_runtime": {"fingerprint_sha256": "t" * 64},
                "algorithm": "greedy_rewrite",
                "llm_condition": {"model": "hy3"},
                "llm_condition_sha256": "c" * 64,
                "config": {"budget": 999},
            }), encoding="utf-8")
            (workdir / "trajectory.jsonl").write_text("".join(
                json.dumps({"step": step, "valid": True, "metrics": {}}) + "\n"
                for step in range(1, MODULE.MIN_PROPOSALS + 1)
            ), encoding="utf-8")
            spec = SimpleNamespace(
                task_id="T/X", task_dir=task_dir, initial_program_path=initial,
            )
            with patch.object(MODULE, "list_tasks", return_value=[spec]), \
                    patch.object(MODULE, "task_package_sha256", return_value=package,
                                 create=True), \
                    patch.object(MODULE, "verify_run", return_value={
                        "verified": True,
                        "budget": MODULE.MIN_PROPOSALS,
                        "trusted_evaluator_runtime_sha256": "t" * 64,
                    }):
                report = self.run_report(root / "runs", root)
            self.assertEqual(report["trusted_input_run_count"], 1)
            self.assertEqual(report["rows"][0]["seed"], 0)
            self.assertEqual(
                report["rows"][0]["proposal_budget"], MODULE.MIN_PROPOSALS
            )

    def test_historical_task_package_is_diagnostic_not_measured_with_current_lines(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            (task_dir / "verification").mkdir(parents=True)
            (task_dir / "verification/evaluator.py").write_text(
                "# current evaluator\n", encoding="utf-8"
            )
            initial = task_dir / "initial.py"
            initial.write_text("# initial\n", encoding="utf-8")
            workdir = root / "runs/old"
            workdir.mkdir(parents=True)
            (workdir / "run_manifest.json").write_text(json.dumps({
                "task_id": "T/X", "feedback_mode": "normal", "seed": 0,
                "task_package_sha256": "o" * 64,
                "runtime_source_sha256": "r" * 64,
                "trusted_evaluator_runtime": {"fingerprint_sha256": "t" * 64},
                "algorithm": "greedy_rewrite", "llm_condition": {"model": "hy3"},
                "llm_condition_sha256": "c" * 64,
            }), encoding="utf-8")
            (workdir / "trajectory.jsonl").write_text("".join(
                json.dumps({"step": step, "valid": True, "metrics": {}}) + "\n"
                for step in range(1, MODULE.MIN_PROPOSALS + 1)
            ), encoding="utf-8")
            spec = SimpleNamespace(
                task_id="T/X", task_dir=task_dir, initial_program_path=initial,
            )
            with patch.object(MODULE, "list_tasks", return_value=[spec]), \
                    patch.object(MODULE, "task_package_sha256", return_value="n" * 64,
                                 create=True), \
                    patch.object(MODULE, "verify_run", return_value={
                        "verified": True, "budget": MODULE.MIN_PROPOSALS,
                        "trusted_evaluator_runtime_sha256": "t" * 64,
                    }):
                report = self.run_report(root / "runs", root)
            self.assertEqual(report["trusted_input_run_count"], 0)
            self.assertEqual(report["unattributable_input_run_count"], 1)
            self.assertEqual(report["rows"], [])
            self.assertEqual(
                report["inputs"][0]["evidence_status"],
                "historical_or_incomplete_identity",
            )


if __name__ == "__main__":
    unittest.main()
