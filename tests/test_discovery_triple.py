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
    def write_run(directory: Path, condition: str) -> None:
        directory.mkdir(parents=True)
        (directory / "run_manifest.json").write_text(json.dumps({
            "task_id": "Mathematics/SequenceLawRecovery",
            "feedback_mode": "normal",
            "seed": 0,
            "llm_condition": {"model": "hy3-ioa"},
            "llm_condition_sha256": condition,
            "task_package_sha256": "task-package",
            "runtime_source_sha256": "runtime-source",
        }), encoding="utf-8")
        (directory / "trajectory.jsonl").write_text(json.dumps({
            "step": 1,
            "valid": True,
            "score": 0.5,
            "metrics": {
                "combined_score": 0.5,
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
            with contextlib.redirect_stdout(io.StringIO()):
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
