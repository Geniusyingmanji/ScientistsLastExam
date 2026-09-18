"""Gates on the two metadata fields that used to assert something nothing checked.

`eval_time_seconds` is declared in every metadata.yaml and read by no code on the evaluation
path: the timeout that actually stops an evaluation is the hand-committed `EVAL_TIMEOUT_S` in
each task's `run_eval.py`. And `review.domain` accepted any nonempty string, so `'x'` was a
completed external domain review. Both are reconciled here rather than enforced in the runtime,
because changing the enforced timeout of 88 tasks would move evidence.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sle.certification import certification_status
from sle.registry import list_tasks
from scripts import audit_tasks
from scripts.audit_tasks import (
    EVAL_TIMEOUT_MAX,
    EVAL_TIMEOUT_MIN,
    LINEAGE_STATUSES,
    _domain_review_issues,
    _metadata_issues,
    _normalized_oracle,
    _task_card_issues,
    _timeout_issues,
    audit,
    domain_review_state,
)

# Tasks built inside this repository, whose builder model, scaffold and red-team history are
# recorded on the card rather than reconstructed after the fact. Everything else is inherited.
RECORDED_LINEAGE = {
    "Ecology/OccupancyDetectionDesign",
    "DataPrivacy/SparseVectorAudit",
    "Physics/CriticalPhenomenaLab",
    "SystemsBiology/EnzymeKineticsLaw",
    "ParticlePhysics/DiscrepantMeasurements",
    "ComputerArchitecture/CacheReplacementPolicyID",
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
    "Exoplanets/TransitTimingAttribution",
    "Mathematics/NarrowAdmissibleTuple",
    "Superconductivity/SuperconductorTcRecord",
    "Geophysics/UPbConcordiaInference",
    "Sensors/IMUBiasCalibration",
    "Microbiology/MetagenomeCompositionAssignment",
    "Hydrology/AquiferPumpingInference",
}


class TaskCardAuditTests(unittest.TestCase):
    def test_oracle_comparison_ignores_only_text_docstrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evaluator.py"
            body = "def evaluate(solver):\n    return solver()\n"
            path.write_text(body)
            bare = _normalized_oracle(path)
            path.write_text('"A different scientific description."\n' + body)
            self.assertEqual(_normalized_oracle(path), bare)
            for expression in ('b"bytes are not a docstring"', '42', 'True'):
                path.write_text(expression + "\n" + body)
                self.assertNotEqual(_normalized_oracle(path), bare)

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


class EvalTimeoutReconciliationTests(unittest.TestCase):
    """`eval_time_seconds` is decorative unless something checks it against the enforced value."""

    def _wrapper(self, directory: Path, timeout: str) -> Path:
        path = directory / "run_eval.py"
        # A comment naming a different number, which a substring scan would pick up first.
        path.write_text("# EVAL_TIMEOUT_S = 9999\nEVAL_TIMEOUT_S = %s\n" % timeout,
                        encoding="utf-8")
        return path

    def test_the_enforced_timeout_is_read_from_the_source_not_a_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "300")
            self.assertEqual(audit_tasks._module_literal(path, "EVAL_TIMEOUT_S"), 300)

    def test_a_declared_cost_wrong_by_orders_of_magnitude_is_caught(self):
        """The shape actually found in the tree: declared 1 s against an enforced 720 s."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "720")
            issues = _timeout_issues({"eval_time_seconds": 1}, path, "T/t")
        self.assertEqual(len(issues), 1)
        self.assertIn("exceeds the declared", issues[0])

    def test_a_timeout_that_does_not_cover_the_declared_cost_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "300")
            issues = _timeout_issues({"eval_time_seconds": 600}, path, "T/t")
        self.assertEqual(len(issues), 1)
        self.assertIn("does not cover the declared", issues[0])

    def test_the_generator_margin_and_a_conservative_one_both_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "300")
            for seconds in (100, 20, 4):
                with self.subTest(seconds=seconds):
                    self.assertEqual(_timeout_issues({"eval_time_seconds": seconds}, path, "T/t"), [])

    def test_the_check_surfaces_a_disagreement_whichever_side_is_wrong(self):
        """Two-sided on purpose: 600 s declared against a 600 s wrapper and 3600 s against the
        same wrapper both fail. It reports that the two disagree, not which one is wrong - the
        migration entry records both numbers so a human can tell."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "600")
            for declared in (600, 3600):
                with self.subTest(declared=declared):
                    self.assertTrue(_timeout_issues({"eval_time_seconds": declared}, path, "T/t"))

    def test_the_bounds_are_ordered_and_documented(self):
        self.assertLess(EVAL_TIMEOUT_MIN, EVAL_TIMEOUT_MAX)
        self.assertEqual(EVAL_TIMEOUT_MIN, 3.0)

    def test_a_non_numeric_declaration_fails_instead_of_escaping_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._wrapper(Path(tmp), "300")
            for declared in (None, "5", 0, True, -3):
                with self.subTest(declared=declared):
                    self.assertTrue(
                        _timeout_issues({"eval_time_seconds": declared}, path, "T/t"))

    def test_an_absent_key_is_left_to_the_required_metadata_check(self):
        """One root cause, one issue: `missing_metadata` already reports the absent key."""
        self.assertEqual(_timeout_issues({}, None, "T/t"), [])

    def test_a_wrapper_whose_timeout_is_not_a_literal_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_eval.py"
            path.write_text("import os\nEVAL_TIMEOUT_S = int(os.environ['T'])\n",
                            encoding="utf-8")
            self.assertTrue(_timeout_issues({"eval_time_seconds": 5}, path, "T/t"))

    def test_metadata_issues_still_reports_the_schema_fields_it_did_before(self):
        self.assertEqual(
            _metadata_issues({"difficulty": "hard", "tier": "T2", "score_mode": "clipped",
                              "eval_time_seconds": 5}, None, "T/t"), [])

    def test_every_registered_task_reconciles_its_two_numbers(self):
        """The whole-inventory check, so a new task cannot land with the two disagreeing."""
        offenders = {}
        for spec in list_tasks(None):
            issues = _timeout_issues(
                spec.metadata, spec.task_dir / "frontier_eval" / "run_eval.py", spec.task_id)
            if issues:
                offenders[spec.task_id] = issues
        # The two recorded at HEAD are named in schemas/eval_timeout_migration.json, whose entry
        # pins the pair it was written against - so this passes only while the numbers hold.
        self.assertEqual(offenders, {})

    def test_a_migration_entry_goes_stale_when_either_number_moves(self):
        """A recorded disagreement must not outlive the numbers it excuses."""
        spec = next(s for s in list_tasks(None)
                    if s.task_id in audit_tasks._migration_inventory())
        run_eval = spec.task_dir / "frontier_eval" / "run_eval.py"
        moved = dict(spec.metadata)
        moved["eval_time_seconds"] = spec.metadata["eval_time_seconds"] + 1
        self.assertTrue(_timeout_issues(moved, run_eval, spec.task_id))

    def test_a_clean_task_is_not_in_the_migration_inventory(self):
        """An entry for a task whose numbers already agree would excuse a future drift.

        The pinning check returns early on an entry that matches, so a needless entry reads as
        consistent purely because the ratio is never reached.
        """
        specs = {spec.task_id: spec for spec in list_tasks(None)}
        for task_id in audit_tasks._migration_inventory():
            with self.subTest(task=task_id):
                spec = specs[task_id]
                declared = spec.metadata["eval_time_seconds"]
                enforced = audit_tasks._module_literal(
                    spec.task_dir / "frontier_eval" / "run_eval.py", "EVAL_TIMEOUT_S")
                ratio = enforced / declared
                self.assertTrue(ratio < EVAL_TIMEOUT_MIN or ratio > EVAL_TIMEOUT_MAX)


class DomainReviewFieldTests(unittest.TestCase):
    """`review.domain` accepted any nonempty string, so `'x'` was a completed review."""

    def test_an_arbitrary_string_is_not_a_review(self):
        self.assertEqual(
            _domain_review_issues({"domain": "x"}),
            ["task card review domain is not a pending status or complete"])

    def test_the_inherited_pending_variants_still_validate(self):
        for value in ("pending_external", "pending_external_photovoltaics",
                      "pending_external_rna_thermodynamics_and_design", "pending"):
            with self.subTest(value=value):
                self.assertEqual(_domain_review_issues({"domain": value}), [])
                self.assertEqual(domain_review_state({"domain": value}), "pending")

    def test_complete_requires_a_reviewer_and_a_date(self):
        self.assertNotEqual(_domain_review_issues({"domain": "complete"}), [])
        self.assertEqual(domain_review_state({"domain": "complete"}), "unknown")
        self.assertEqual(_domain_review_issues({"domain": "complete"}), [
            "task card review domain is complete without reviewed_by",
            "task card review domain is complete without reviewed_at",
        ])
        signed = {"domain": "complete", "reviewed_by": "An external group",
                  "reviewed_at": "2026-09-17"}
        self.assertEqual(_domain_review_issues(signed), [])
        self.assertEqual(domain_review_state(signed), "complete")

    def test_pending_is_distinguishable_from_done_by_script(self):
        pending = {"domain": "pending_external_rna_design"}
        done = {"domain": "complete", "reviewed_by": "G", "reviewed_at": "2026-09-17"}
        self.assertNotEqual(domain_review_state(pending), domain_review_state(done))
        self.assertEqual(
            {domain_review_state(pending), domain_review_state(done)},
            {"pending", "complete"})

    def test_the_maturity_audit_uses_the_same_classifier(self):
        """It used to accept a bare "passed" - a sign-off with no reviewer and no date."""
        maturity = __import__("scripts.audit_task_maturity", fromlist=["domain_review_state"])
        unsigned = {"domain": "passed"}
        signed = {"domain": "complete", "reviewed_by": "G", "reviewed_at": "2026-09-17"}
        self.assertIs(maturity.domain_review_state, domain_review_state)
        self.assertNotEqual(domain_review_state(unsigned), "complete")
        self.assertEqual(domain_review_state(signed), "complete")

    def test_the_whole_inventory_reports_no_completed_domain_review(self):
        """Matches scripts/audit_task_maturity.py's frozen count of 0 of 88."""
        completed = [
            spec.task_id for spec in list_tasks(None)
            if domain_review_state(
                __import__("yaml").safe_load(
                    (spec.task_dir / "TASK_CARD.yaml").read_text(encoding="utf-8")
                ).get("review") or {}) == "complete"
        ]
        self.assertEqual(completed, [])

    def test_the_migration_inventory_is_scoped_to_the_two_recorded_tasks(self):
        self.assertEqual(
            set(audit_tasks._migration_inventory()),
            {"Microbiology/MetagenomeCompositionAssignment",
             "InformationTheory/ShannonCapacityCertificate"})
        for entry in audit_tasks._migration_inventory().values():
            self.assertEqual(entry["status"], "pending")
            self.assertTrue(entry["reason"])


class CardFieldValidationEndToEndTests(unittest.TestCase):
    """`'x'` must fail the real gate, not just the helper."""

    def _card_with_domain(self, value: str) -> dict:
        template = next(spec for spec in list_tasks(None)
                        if spec.task_dir.joinpath("TASK_CARD.yaml").is_file())
        card = __import__("yaml").safe_load(
            template.task_dir.joinpath("TASK_CARD.yaml").read_text(encoding="utf-8"))
        card["review"]["domain"] = value
        return card

    def test_a_card_declaring_x_fails_the_task_card_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text(json.dumps(self._card_with_domain("x")), encoding="utf-8")
            issues = _task_card_issues(path)
        self.assertIn("task card review domain is not a pending status or complete", issues)

    def test_a_pending_card_passes_the_task_card_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TASK_CARD.yaml"
            path.write_text(json.dumps(
                self._card_with_domain("pending_external_photovoltaics")), encoding="utf-8")
            self.assertEqual(_task_card_issues(path), [])


if __name__ == "__main__":
    unittest.main()
