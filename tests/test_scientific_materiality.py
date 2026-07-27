from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_scientific_materiality.py"
SPEC = importlib.util.spec_from_file_location("scientific_materiality", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScientificMaterialityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.build_report()
        cls.tasks = {row["task"]: row for row in cls.report["tasks"]}

    def _modified_report(self, mutate):
        document = json.loads(MODULE.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        mutate(document)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            return MODULE.build_report(path)

    def test_frozen_cohort_has_seven_same_witness_raw_materiality_contracts(self):
        self.assertEqual(self.report["task_count"], 7)
        self.assertEqual(self.report["materiality_contract_passed_count"], 7)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])
        for row in self.report["tasks"]:
            self.assertTrue(row["materiality_contract_passed"], row)
            self.assertTrue(row["same_witness_enforced"])
            self.assertEqual(row["issues"], [])
            self.assertEqual(row["criterion_count"], row["criteria_passed_count"])
            self.assertTrue(set(row["required_axes"]) <= set(row["covered_axes"]))
            self.assertNotEqual(row["baseline_pointer"], row["material_witness_pointer"])
            self.assertTrue(row["evidence"]["hash_matches"])
            self.assertTrue(row["evidence"]["trusted_evidence"])
            self.assertTrue(row["contract_compatibility"]["runtime_files_unchanged"])
            self.assertIsNone(row["citation"]["reason"])

    def test_materiality_uses_raw_scientific_values_not_combined_score(self):
        forbidden = MODULE.FORBIDDEN_PRIMARY_TOKENS
        for task in json.loads(
            MODULE.DEFAULT_CONTRACT.read_text(encoding="utf-8")
        )["tasks"]:
            for criterion in task["criteria"]:
                if criterion["kind"] not in {"paired_scalar", "paired_records"}:
                    continue
                pointer = criterion.get("value_pointer", criterion["witness_pointer"])
                token = pointer.rstrip("/").rsplit("/", 1)[-1]
                self.assertNotIn(token, forbidden)
                self.assertFalse(token.startswith("normalized_"))
                self.assertTrue(
                    "minimum_absolute_change" in criterion
                    or "minimum_relative_change" in criterion
                )

    def test_electrolyte_requires_untouched_confirmation_not_discovery_score(self):
        row = self.tasks["Electrochemistry/ElectrolyteConductivityDesign"]
        self.assertEqual(
            row["material_witness_pointer"],
            "/direct_confirmation_robust_reference",
        )
        criteria = {criterion["id"]: criterion for criterion in row["criteria"]}
        self.assertGreaterEqual(
            criteria["development_confirmation_minimum_conductivity"][
                "signed_relative_change"
            ],
            0.05,
        )
        self.assertGreaterEqual(
            criteria["heldout_confirmation_minimum_conductivity"][
                "signed_relative_change"
            ],
            0.05,
        )

    def test_collection_contracts_cover_every_record_and_required_split(self):
        expectations = {
            "Optics/DiffractionGratingDesign": 6,
            "Semiconductor/MOSFETDoping": 6,
            "StructuralEngineering/TrussWeightMinimization": 6,
            "Thermodynamics/HeatExchangerDesign": 6,
        }
        for task, record_count in expectations.items():
            paired = [
                criterion for criterion in self.tasks[task]["criteria"]
                if criterion["kind"] == "paired_records"
            ]
            self.assertTrue(paired, task)
            for criterion in paired:
                self.assertEqual(criterion["record_count"], record_count)
                self.assertTrue(criterion["split_coverage_passed"])
                self.assertEqual(
                    set(criterion["observed_splits"]), {"development", "heldout"}
                )

    def test_tampered_evidence_hash_fails_closed(self):
        report = self._modified_report(
            lambda document: document["tasks"][0]["evidence"].update(
                {"sha256": "0" * 64}
            )
        )
        first = report["tasks"][0]
        self.assertFalse(first["materiality_contract_passed"])
        self.assertIn("calibration evidence binding failed", first["issues"])
        self.assertEqual(first["criterion_count"], 0)

    def test_combined_score_cannot_be_relabelled_materiality(self):
        def mutate(document):
            task = document["tasks"][2]
            criterion = task["criteria"][0]
            criterion["baseline_pointer"] = "/direct_baseline/combined_score"
            criterion["witness_pointer"] = "/reference/combined_score"

        report = self._modified_report(mutate)
        row = report["tasks"][2]
        self.assertFalse(row["materiality_contract_passed"])
        self.assertTrue(any(
            "normalized or combined score" in issue for issue in row["issues"]
        ))

    def test_mixing_a_second_witness_fails_same_witness_rule(self):
        def mutate(document):
            document["tasks"][0]["criteria"][0]["witness_pointer"] = (
                "/direct_confirmation_reference/"
                "development_confirmation_minimum_weighted_conductivity_s_cm"
            )

        report = self._modified_report(mutate)
        row = report["tasks"][0]
        self.assertFalse(row["materiality_contract_passed"])
        self.assertTrue(any(
            "outside the declared material witness" in issue for issue in row["issues"]
        ))

    def test_missing_heldout_axis_fails_coverage(self):
        def mutate(document):
            task = document["tasks"][6]
            task["criteria"] = [
                criterion for criterion in task["criteria"]
                if "heldout" not in criterion["axes"]
            ]

        report = self._modified_report(mutate)
        row = report["tasks"][6]
        self.assertFalse(row["materiality_contract_passed"])
        self.assertIn(
            "criteria do not cover every required scientific axis", row["issues"]
        )

    def test_unreachable_threshold_is_a_scientific_failure_not_execution_error(self):
        def mutate(document):
            document["tasks"][4]["criteria"][0]["minimum_relative_change"] = 0.99

        report = self._modified_report(mutate)
        row = report["tasks"][4]
        self.assertTrue(report["execution_passed"])
        self.assertFalse(row["materiality_contract_passed"])
        self.assertEqual(row["issues"], [])
        self.assertFalse(row["criteria"][0]["passed"])

    def test_citation_title_must_match_verified_metadata_and_task_card(self):
        def mutate(document):
            document["tasks"][1]["citation"]["verified_title"] = "Wrong title"

        report = self._modified_report(mutate)
        row = report["tasks"][1]
        self.assertFalse(row["materiality_contract_passed"])
        self.assertIn("citation binding failed", row["issues"])

    def test_runtime_drift_quarantines_bound_calibration(self):
        original = MODULE._contract_compatibility
        try:
            MODULE._contract_compatibility = lambda *_args: {
                "runtime_files_unchanged": False,
                "changed_paths": ["verification/evaluator.py"],
                "reason": "fixture drift",
            }
            report = MODULE.build_report()
        finally:
            MODULE._contract_compatibility = original
        self.assertEqual(report["materiality_contract_passed_count"], 0)
        for row in report["tasks"]:
            self.assertIn(
                "calibration evidence is not bound to the current task runtime",
                row["issues"],
            )


if __name__ == "__main__":
    unittest.main()
