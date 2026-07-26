from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from frontier_science.runtime_migration import compare_json_values


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


if __name__ == "__main__":
    unittest.main()
