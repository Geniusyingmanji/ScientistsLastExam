from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sle.certification import certification_status
from sle.registry import list_tasks
from scripts.audit_tasks import LINEAGE_STATUSES, _task_card_issues, audit

# Tasks built inside this repository, whose builder model, scaffold and red-team history are
# recorded on the card rather than reconstructed after the fact. Everything else is inherited.
RECORDED_LINEAGE = {
    'StructuralBiology/ProteinDistanceGeometry',
    "Ecology/OccupancyDetectionDesign",
    "Physics/CriticalPhenomenaLab",
    "SystemsBiology/EnzymeKineticsLaw",
    "ParticlePhysics/DiscrepantMeasurements",
    "MaterialsScience/PhaseDiagramDiscovery",
    "Physics/HiddenCouplingNetwork",
    "ClimateScience/ForcedSignalAttribution",
    "StructuralEngineering/ModalDamageAttribution",
    "Mathematics/BlackBoxGroupIdentification",
    "Spectroscopy/CrowdedSpectrumAssignment",
    "Mathematics/RamseyLowerBound",
    "Mathematics/KissingNumber",
    "Mathematics/ZarankiewiczMatrix",
    "Mathematics/DegreeDiameterGraph",
    "Mathematics/VanDerWaerdenColoring",
    "Mathematics/SchurPartition",
    "Mathematics/ErdosMinimumOverlap",
    "Mathematics/HeilbronnTrianglePacking",
    "Algorithm/TensorRank555",
    "Mathematics/Superpermutation",
    "AtmosphericChemistry/MethaneSourceAttribution",
    "Turbulence/WallClosureDiscovery",
    "Exoplanets/TransmissionSpectrumSpecies",
    "DiscreteGeometry/SpherePackingCertificate",
    "QuantumFoundations/BellBoundCertificate",
    "InformationTheory/ShannonCapacityCertificate",
    "QuantumControl/ActiveNoiseSpectroscopy",
    "Mathematics/NonlinearCodeRecords",
    "Mathematics/CapSetFrontier",
    "ParticlePhysics/LookElsewhereAnomaly",
    "CausalDiscovery/SurvivorshipConfoundedDesign",
    "Oceanography/AMOCTippingRefusal",
    "Gravitation/PTAHellingsDowns",
    "Physics/ComplexBoseLaw",
    "MaterialsScience/QuinaryConvexHull",
    "Mathematics/HeavyTailEvidence",
    "Mathematics/NarrowAdmissibleTuple",
    "Superconductivity/SuperconductorTcRecord",
    "Geophysics/UPbConcordiaInference",
}


class TaskCardAuditTests(unittest.TestCase):
    def test_every_nonquarantined_task_has_a_valid_card(self):
        checked = 0
        for spec in list_tasks(None):
            if certification_status(spec.task_id) == "quarantined":
                continue
            checked += 1
            self.assertEqual(
                _task_card_issues(spec.task_dir / "TASK_CARD.yaml"),
                [],
                spec.task_id,
            )
        # Every non-quarantined task, whatever the inventory currently holds. A literal count
        # here fails on any deliberate change to the inventory, which says nothing about whether
        # the cards are valid - the thing this test exists to check.
        expected = sum(1 for spec in list_tasks(None)
                       if certification_status(spec.task_id) != "quarantined")
        self.assertEqual(checked, expected)
        self.assertGreater(checked, 0)

    def test_bad_yaml_is_a_task_issue_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text("scientific_question: bad: scalar\n", encoding="utf-8")
            issues = _task_card_issues(path)
        self.assertEqual(len(issues), 1)
        self.assertIn("not valid YAML", issues[0])

    def test_schema_requires_scientific_and_evidence_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text("schema_version: 2\nscientific_question: test\n", encoding="utf-8")
            issues = _task_card_issues(path)
        self.assertIn("task card missing artifact", issues)
        self.assertIn("task card missing oracle", issues)
        self.assertIn("task card missing review", issues)
        self.assertIn("task card missing provenance", issues)
        self.assertIn("task card missing novelty_risk", issues)
        self.assertIn("task card missing lineage", issues)
        self.assertIn("task card missing construction_audit", issues)
        self.assertIn("task card missing long_horizon", issues)

    def test_schema_two_maturity_metadata_is_machine_readable(self):
        for spec in list_tasks(None):
            if certification_status(spec.task_id) == "quarantined":
                continue
            card = __import__("yaml").safe_load(
                (spec.task_dir / "TASK_CARD.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(card["schema_version"], 2, spec.task_id)
            self.assertIn(card["provenance"]["class"], {
                "known_answer", "procedural", "public_data_replay", "prospective",
            })
            # Enumerated, not pinned to one literal. This asserted `incomplete_legacy`
            # everywhere, which was true of an inventory that was entirely inherited - but the
            # field exists to separate a task whose lineage is recorded from one whose is not,
            # and a literal forces a newly built task to misreport itself to stay green.
            #
            # The allowlist keeps it a guard rather than a formality: an inherited task cannot
            # quietly start claiming a lineage nobody reconstructed.
            self.assertIn(card["lineage"]["status"], LINEAGE_STATUSES, spec.task_id)
            if spec.task_id not in RECORDED_LINEAGE:
                self.assertEqual(card["lineage"]["status"], "incomplete_legacy", spec.task_id)
                self.assertEqual(
                    card["construction_audit"]["status"], "incomplete_legacy", spec.task_id)
            self.assertFalse(card["lineage"]["frozen_before_eval"])
            self.assertIsNone(card["lineage"]["freeze_timestamp"])
            self.assertFalse(card["long_horizon"]["measurement_health_passed"])
            self.assertFalse(card["long_horizon"]["material_headroom_after_2h"])

    def test_inventory_audit_counts_all_required_cards(self):
        report = audit()
        expected = sum(1 for spec in list_tasks(None)
                       if certification_status(spec.task_id) != "quarantined")
        self.assertEqual(report["task_card_required_count"], expected)
        self.assertEqual(report["task_card_passed_count"], expected)
        self.assertGreater(expected, 0)
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
