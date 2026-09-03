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

    def test_the_migration_starting_point_is_still_exactly_what_was_recorded(self):
        """The old side of the contract is the part that can still be checked.

        This audit records one historical change - sorting the composition keys before summing
        differences - by pinning the hash of each touched file before and after. The *before*
        hashes are a fact about a revision and stay true. The *after* hashes assert that nothing
        has touched those files since, which stopped being true the moment the evaluator was
        uncapped, and would stop being true again on any later edit.

        So the enduring claim is checked here and the "nothing has moved since" claim is checked
        as a refusal below, the same way a preregistered replay is handled: a historical record
        that can no longer be re-derived should say so, not be loosened until it passes.
        """
        module = self.module
        revision = module.source_provenance(ROOT)["git_revision"]
        report = module.audit_source_contract(revision)
        self.assertTrue(all(
            record["old_sha256"] == record["expected_old_sha256"]
            for record in report["source_hash_records"]
        ), report["source_hash_records"])
        self.assertEqual(
            report["shared_runtime_source_changes"],
            list(module.RUNTIME_PATHS),
        )

    def test_the_audit_refuses_once_the_files_it_pinned_have_moved_on(self):
        module = self.module
        revision = module.source_provenance(ROOT)["git_revision"]
        report = module.audit_source_contract(revision)
        moved = [record["path"] for record in report["source_hash_records"]
                 if record["new_sha256"] != record["expected_new_sha256"]]
        if not moved:
            # Nothing has been edited since the migration, so the original claim holds whole.
            self.assertTrue(report["passed"], report)
            self.assertTrue(report["shared_runtime_migration"]["accepted"])
            return
        self.assertFalse(
            report["passed"],
            "files pinned by this migration have changed (%s) and the audit still reports "
            "passed - the pin is not being checked" % ", ".join(moved))

    def test_complete_finite_landscape_change_is_only_roundoff(self):
        report = self.module.audit_landscape()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["world_count"], 13)
        self.assertEqual(report["pair_count_per_seed"], 137)
        self.assertEqual(report["three_alloy_utility_count_per_seed"], 318)
        self.assertTrue(report["new_cross_seed_bit_exact"])
        self.assertTrue(all(
            record["maximum_pair_distance_absolute_difference"]
            <= self.module.MAX_EXPECTED_ROUNDOFF
            and record["maximum_three_alloy_utility_absolute_difference"]
            <= self.module.MAX_EXPECTED_ROUNDOFF
            and record["proxy_and_truth_optimal_rows_exactly_match"]
            and record["baseline_metrics_exactly_match"]
            and record["reference_metrics_exactly_match"]
            for record in report["records"]
        ))

    def test_retention_manifest_exposes_three_unreplayable_proposals(self):
        try:
            manifest = self.module._retained_manifest()
        except FileNotFoundError as missing:
            # Run directories are not committed; a checkout without them is missing data.
            self.skipTest("the runs this manifest reads are not in this checkout: %s" % missing)
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
