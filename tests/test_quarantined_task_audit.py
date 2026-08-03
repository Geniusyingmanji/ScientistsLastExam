from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "scripts/audit_quarantined_tasks.py"
    spec = importlib.util.spec_from_file_location(
        "quarantined_task_audit_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load quarantined task audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuarantinedTaskAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.report = cls.module.audit()
        cls.records = {
            row["task"]: row for row in cls.report["records"]
        }

    def test_every_manifest_quarantine_has_a_reproduced_check(self):
        self.assertTrue(self.report["execution_passed"], self.report)
        self.assertEqual(self.report["missing_checks"], [])
        self.assertEqual(self.report["stale_checks"], [])
        self.assertEqual(self.report["summary"], {
            "manifest_quarantined_count": 9,
            "audited_count": 9,
            "reproduced_defect_count": 9,
            "meets_internal_benchmark_standard_count": 0,
            "recommended_retain_quarantine_count": 9,
        })
        self.assertEqual(
            set(self.records), set(self.report["manifest_quarantined_tasks"])
        )

    def test_generic_physics_claims_share_one_nonphysical_oracle(self):
        group = self.report["generic_clone_group"]
        self.assertEqual(group["unique_normalized_oracle_count"], 1)
        self.assertEqual(set(group["tasks"]), set(self.module.GENERIC_CLONE_TASKS))
        fingerprints = {
            self.records[task]["normalized_oracle_sha256"]
            for task in group["tasks"]
        }
        self.assertEqual(fingerprints, {group["normalized_oracle_sha256"]})
        for task in group["tasks"]:
            row = self.records[task]
            self.assertEqual(row["defined_functions"], ["_forward_model", "evaluate"])
            self.assertEqual(
                row["unused_solver_imports"], ["minimize_scalar", "solve_ivp"]
            )
            self.assertFalse(row["has_instance_or_split_declarations"])
            self.assertFalse(row["task_card_present"])
            self.assertEqual(row["entrypoint"], row["contract_entrypoint"])
            self.assertEqual(row["declared_oracle_type"], "physical_sim")

    def test_generic_clones_are_fixed_answer_and_fail_open(self):
        for task in self.module.GENERIC_CLONE_TASKS:
            row = self.records[task]
            self.assertEqual(row["parameter_count"], 8)
            self.assertEqual(row["baseline_score"], 0.0)
            self.assertEqual(row["embedded_target_score"], 1.0)
            self.assertEqual(row["nonfinite_score"], 1.0)
            self.assertTrue(row["nonfinite_valid"])
            self.assertFalse(row["nonfinite_objective_is_finite"])
            self.assertEqual(
                set(row["failed_standard_axes"]),
                {
                    "scientific_semantics",
                    "oracle_fidelity",
                    "generalization",
                    "optimization_integrity",
                    "evidence_integrity",
                },
            )

    def test_previously_audited_quarantine_defects_still_reproduce(self):
        for task in self.module.REPRODUCED_WAVE4_CHECKS:
            row = self.records[task]
            self.assertTrue(row["defect_reproduced"], row)
            self.assertFalse(row["meets_internal_benchmark_standard"])
            self.assertTrue(row["failed_standard_axes"])
            self.assertEqual(
                row["recommendation"],
                "retain_quarantine_until_substantive_rebuild",
            )


if __name__ == "__main__":
    unittest.main()
