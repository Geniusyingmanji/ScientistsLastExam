from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from sle.runtime_migration import (
    LAYOUT_RUNTIME_BLOBS,
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
            "sle/evaluate.py",
            "sle/TASK_CARD.yaml",
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

    def test_runtime_diff_normalizes_the_committed_cross_revision_layout_move(self):
        legacy_revision = "3e031373cd54f4d9542076fbe42ceaee855fe825"
        current_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        shared_scope = [
            "sle/registry.py",
            "sle/spec.py",
        ]
        for task_scope in (
            "benchmarks/Turbulence/RANSCalibration",
            "benchmarks/Engineering/RANSCalibration",
        ):
            self.assertEqual(
                runtime_source_changes(
                    legacy_revision,
                    current_revision,
                    [*shared_scope, task_scope],
                    root=ROOT,
                ),
                [],
            )

    def test_layout_normalization_requires_the_exact_atomic_loader_blobs(self):
        def tree_output(revision: str) -> str:
            index = 0 if revision == "legacy" else 1
            rows = []
            for path, hashes in LAYOUT_RUNTIME_BLOBS.items():
                blob = hashes[index]
                if blob is None:
                    continue
                if revision == "changed" and path.endswith("registry.py"):
                    blob = "f" * 40
                rows.append("100644 blob %s\t%s" % (blob, path))
            return "\n".join(rows) + "\n"

        def ls_tree(command, **_kwargs):
            return tree_output(command[3])

        with patch(
            "sle.runtime_migration.subprocess.check_output",
            side_effect=ls_tree,
        ):
            with patch(
                "sle.runtime_migration._is_ancestor",
                side_effect=lambda _left, right, _root: right != "legacy",
            ):
                changes = runtime_source_changes(
                    "legacy",
                    "changed",
                    ["sle/registry.py"],
                    root=ROOT,
                )

        self.assertIn("sle/registry.py", changes)

    def test_layout_runtime_unit_is_unchanged_at_current_revision(self):
        legacy_revision = "3e031373cd54f4d9542076fbe42ceaee855fe825"
        current_revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        self.assertEqual(
            runtime_source_changes(
                legacy_revision,
                current_revision,
                [
                    "sle/benchmark_layout.py",
                    "sle/registry.py",
                    "sle/spec.py",
                ],
                root=ROOT,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
