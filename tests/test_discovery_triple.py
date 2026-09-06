"""Discovery-axis reports must find both supported run directory layouts."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts/report_discovery_triple.py"
    spec = importlib.util.spec_from_file_location("discovery_triple", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoveryTripleLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    @staticmethod
    def write_run(directory: Path, condition: str, *, mode: str = "normal",
                  seed: int = 0, budget: int = 1, score: float = 0.5) -> None:
        directory.mkdir(parents=True)
        (directory / "run_manifest.json").write_text(json.dumps({
            "task_id": "Mathematics/SequenceLawRecovery",
            "feedback_mode": mode,
            "seed": seed,
            "llm_condition": {"model": "hy3-ioa"},
            "llm_condition_sha256": condition,
            "task_package_sha256": "task-package",
            "runtime_source_sha256": "runtime-source",
            "trusted_evaluator_runtime": {"fingerprint_sha256": "trusted-runtime"},
            "algorithm": "greedy_rewrite",
        }), encoding="utf-8")
        (directory / "trajectory.jsonl").write_text(json.dumps({
            "step": budget,
            "valid": True,
            "score": score,
            "candidate_sha256": ("a" if mode == "normal" else "b") * 64,
            "metrics": {
                "combined_score": score,
                "heldout_mechanism_score": 0.4,
                "heldout_false_discovery_rate": 0.1,
                "heldout_unsupported_refusal_rate": 0.8,
                "heldout_discovery_coverage": 0.7,
            },
        }) + "\n", encoding="utf-8")

    def test_shallow_cohort_and_nested_batch_layouts_are_both_discovered(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            self.write_run(root / "cohort/cell", "condition-shallow")
            self.write_run(
                root / "batch/Mathematics__SequenceLawRecovery/greedy_rewrite/normal/seed_0",
                "condition-nested",
            )
            output = Path(tmp) / "triple.json"
            with patch.object(self.module, "verify_run", return_value={
                "verified": True,
                "budget": 1,
                "trusted_evaluator_runtime_sha256": "trusted-runtime",
            }), contextlib.redirect_stdout(io.StringIO()):
                self.module.main(["--runs", str(root), "--output", str(output)])
            rows = [
                row for row in json.loads(output.read_text(encoding="utf-8"))["rows"]
                if row.get("status") == "ok"
                and row.get("task") == "Mathematics/SequenceLawRecovery"
            ]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["llm_condition_sha256"] for row in rows},
            {"condition-shallow", "condition-nested"},
        )

    def test_legacy_manifest_model_is_recovered_from_the_condition_registry(self):
        document = {
            "task_id": "Mathematics/SequenceLawRecovery",
            "llm_condition_sha256": "legacy-condition",
            "task_package_sha256": "task-package",
            "runtime_source_sha256": "runtime-source",
        }
        with patch.object(
            self.module, "known_conditions", return_value={"legacy-condition": "hy3-ioa"}
        ):
            identity = self.module.run_identity(document)
        self.assertIsNotNone(identity)
        self.assertEqual(identity[1], "hy3-ioa")

    def test_identity_includes_algorithm_and_trusted_evaluator_runtime(self):
        document = {
            "task_id": "Mathematics/SequenceLawRecovery",
            "llm_condition": {"model": "hy3"},
            "llm_condition_sha256": "condition",
            "task_package_sha256": "package",
            "runtime_source_sha256": "runtime",
            "trusted_evaluator_runtime": {"fingerprint_sha256": "trusted"},
            "algorithm": "greedy_rewrite",
        }
        identity = self.module.run_identity(document)
        self.assertEqual(identity[-2:], ("trusted", "greedy_rewrite"))

    def test_unverified_run_is_only_unattributable_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            self.write_run(root / "cohort/cell", "condition")
            output = Path(tmp) / "triple.json"
            with patch.object(
                self.module, "discovery_task_names",
                return_value={"SequenceLawRecovery"},
            ), patch.object(
                self.module, "verify_run", side_effect=ValueError("unbound")
            ), contextlib.redirect_stdout(io.StringIO()):
                self.module.main(["--runs", str(root), "--output", str(output)])
            rows = json.loads(output.read_text(encoding="utf-8"))["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "unattributable_evidence")
        self.assertFalse(rows[0]["trusted_evidence"])

    def test_modes_budgets_and_seeds_are_separate_run_rows(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"
            self.write_run(
                root / "normal", "condition", mode="normal", seed=0,
                budget=1, score=0.4,
            )
            self.write_run(
                root / "blind", "condition", mode="selection_blind", seed=1,
                budget=3, score=0.9,
            )
            output = Path(tmp) / "triple.json"

            def verified(path, **_kwargs):
                return {
                    "verified": True,
                    "budget": 1 if Path(path).name == "normal" else 3,
                    "trusted_evaluator_runtime_sha256": "trusted-runtime",
                }

            with patch.object(
                self.module, "discovery_task_names",
                return_value={"SequenceLawRecovery"},
            ), patch.object(
                self.module, "verify_run", side_effect=verified,
            ), contextlib.redirect_stdout(io.StringIO()):
                self.module.main(["--runs", str(root), "--output", str(output)])
            rows = json.loads(output.read_text(encoding="utf-8"))["rows"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {(row["feedback_mode"], row["proposal_budget"], row["seed"])
             for row in rows},
            {("normal", 1, 0), ("selection_blind", 3, 1)},
        )
        self.assertTrue(all(row["run_manifest_sha256"] for row in rows))

    def test_equal_score_candidate_selection_has_a_hash_tie_break(self):
        with TemporaryDirectory() as tmp:
            run = Path(tmp)
            events = [
                {"step": 1, "valid": True, "score": 0.5,
                 "candidate_sha256": "b" * 64, "metrics": {"combined_score": 0.5}},
                {"step": 2, "valid": True, "score": 0.5,
                 "candidate_sha256": "a" * 64, "metrics": {"combined_score": 0.5}},
            ]
            (run / "trajectory.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            selected = self.module.best_proposal(run)
        self.assertEqual(selected["candidate_sha256"], "a" * 64)
