from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/audit_alloy_hash_order_migration.py"
    spec = importlib.util.spec_from_file_location(
        "alloy_hash_order_migration_test", path,
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load alloy hash-order migration audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlloyHashOrderMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()

    def test_source_contract_is_exactly_the_three_sorting_edits(self):
        module = self.module
        revision = module.source_provenance(ROOT)["git_revision"]
        report = module.audit_source_contract(revision)
        self.assertTrue(report["passed"], report)
        self.assertEqual(
            report["task_runtime_source_changes"],
            list(module.ALLOWED_RUNTIME_CHANGES),
        )
        self.assertTrue(all(
            record["hash_contract_passed"]
            for record in report["source_hash_records"]
        ))

    def test_complete_finite_landscape_change_is_only_roundoff(self):
        report = self.module.audit_landscape()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["world_count"], 13)
        self.assertEqual(report["pair_count_per_seed"], 137)
        self.assertEqual(report["three_alloy_utility_count_per_seed"], 318)
        self.assertFalse(report["old_cross_seed_bit_exact"])
        self.assertTrue(report["new_cross_seed_bit_exact"])
        self.assertTrue(all(
            record["proxy_and_truth_optimal_rows_exactly_match"]
            and record["baseline_metrics_exactly_match"]
            and record["reference_metrics_exactly_match"]
            for record in report["records"]
        ))

    def test_retention_manifest_exposes_three_unreplayable_proposals(self):
        manifest = self.module._retained_manifest()
        self.assertEqual(len(manifest["proposal_hashes"]), 7)
        self.assertEqual(len(manifest["retained_proposal_hashes"]), 4)
        self.assertEqual(len(manifest["unretained_proposal_hashes"]), 3)
        self.assertEqual(len(manifest["artifacts"]), 6)

    def test_metric_difference_paths_are_stable_and_numeric(self):
        differences = self.module._metric_differences(
            {"per_world": [{"value": 1.0}, {"value": 2.0}]},
            {"per_world": [{"value": 1.0}, {"value": 2.0 + 1.0e-15}]},
        )
        self.assertEqual(len(differences), 1)
        self.assertEqual(differences[0]["path"], "/per_world/1/value")
        self.assertGreater(differences[0]["absolute_difference"], 0.0)


if __name__ == "__main__":
    unittest.main()
