from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path

from frontier_science.runtime_migration import (
    compare_json_values,
    filter_runtime_source_changes,
    runtime_source_changes,
)


ROOT = Path(__file__).resolve().parents[1]


def _audit_module():
    path = ROOT / "scripts/audit_trusted_context_runtime_migration.py"
    spec = importlib.util.spec_from_file_location("runtime_migration_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load runtime migration audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeMigrationTests(unittest.TestCase):
    def test_task_card_metadata_is_the_only_filtered_task_path(self):
        changes = [
            "benchmarks/Engineering/ExampleTask/TASK_CARD.yaml",
            "benchmarks/Engineering/ExampleTask/Task.md",
            "benchmarks/Engineering/ExampleTask/solution.py",
            "benchmarks/Engineering/ExampleTask/verification/evaluator.py",
            "benchmarks/Engineering/ExampleTask/verification/data.json",
            "benchmarks/Engineering/ExampleTask/frontier_eval/__init__.py",
            "frontier_science/evaluate.py",
            "frontier_science/TASK_CARD.yaml",
            "benchmarks/Engineering/ExampleTask/verification/TASK_CARD.yaml",
        ]

        self.assertEqual(
            filter_runtime_source_changes(changes),
            changes[1:],
        )

    def test_numeric_comparison_never_hides_structure_or_categories(self):
        accepted = compare_json_values(
            {"valid": 1.0, "rows": [{"score": 0.5}]},
            {"valid": 1, "rows": [{"score": 0.5 + 1.0e-12}]},
            numeric_tolerance=1.0e-10,
        )
        self.assertTrue(accepted["equivalent"], accepted)
        self.assertEqual(accepted["non_numeric_difference_count"], 0)
        self.assertEqual(accepted["numeric_difference_count"], 1)

        for current in (
            {"valid": True, "rows": [{"score": 0.5}]},
            {"valid": 1.0, "rows": []},
            {"valid": 1.0, "rows": [{"score": 0.5}], "extra": 0.0},
            {"valid": 1.0, "rows": [{"score": "0.5"}]},
        ):
            rejected = compare_json_values(
                {"valid": 1.0, "rows": [{"score": 0.5}]}, current,
                numeric_tolerance=1.0e-10,
            )
            self.assertFalse(rejected["equivalent"], rejected)

    def test_source_and_none_path_contracts_are_exact(self):
        module = _audit_module()
        revision = module.source_provenance(ROOT)["git_revision"]
        source = module.audit_source_contract(revision)
        semantics = module.audit_legacy_path_semantics()
        self.assertTrue(source["passed"], source)
        self.assertTrue(semantics["passed"], semantics)

    def test_runtime_diff_normalizes_legacy_and_discipline_task_paths(self):
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        for scope in (
            ["benchmarks/Optics/DiffractionGratingDesign"],
            ["benchmarks/Physics/DiffractionGratingDesign"],
        ):
            self.assertEqual(
                runtime_source_changes(revision, revision, scope, root=ROOT),
                [],
            )


if __name__ == "__main__":
    unittest.main()
