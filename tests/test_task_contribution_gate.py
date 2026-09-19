"""The contribution gate must catch a missing package before an LLM run does.

It wraps checks CONTRIBUTING.md already names. This file pins that PhaseDiagramDiscovery
passes the structural half, so the hy3 debug path is exercising eval and the model, not a
missing Task.md.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.check_task_contribution as gate  # noqa: E402
from scripts.check_task_contribution import check_task  # noqa: E402


class TaskContributionGateTests(unittest.TestCase):
    def test_an_unknown_task_raises(self):
        with self.assertRaises(Exception):
            check_task("NoSuchDomain/NoSuchTask", skip_eval=True)

    def _assert_structural_gate(self, task_id):
        report = check_task(task_id, skip_eval=True)
        failed = [row["check"] for row in report["checks"] if row["ok"] is False]
        self.assertEqual(failed, [], report)
        self.assertEqual(report["phases"]["structural"], "passed")
        self.assertEqual(report["phases"]["runtime"], "incomplete")
        self.assertEqual(report["phases"]["difficulty"], "unassessed")
        self.assertFalse(report["passed"])
        self.assertEqual(report["status"], "incomplete")
        names = {row["check"] for row in report["checks"]}
        for required in (
            "listed_in_all",
            "certification_status",
            "not_self_certified",
            "required_files",
            "task_card",
            "metadata",
            "frontier_wave",
            "discovery_contract_lint_documented",
            "numeric_keys",
            "documented_keys",
        ):
            self.assertIn(required, names)
        status = next(row["detail"] for row in report["checks"]
                      if row["check"] == "certification_status")
        self.assertEqual(status, "candidate")

    def test_phase_diagram_passes_the_structural_gate(self):
        self._assert_structural_gate("MaterialsScience/PhaseDiagramDiscovery")

    def test_crowded_spectrum_passes_the_structural_gate(self):
        self._assert_structural_gate("Spectroscopy/CrowdedSpectrumAssignment")

    def test_wave2_discovery_packages_pass_the_structural_gate(self):
        for task_id in (
            "Physics/ComplexBoseLaw",
            "MaterialsScience/QuinaryConvexHull",
            "Mathematics/HeavyTailEvidence",
        ):
            self._assert_structural_gate(task_id)
        held = check_task("Gravitation/PTAHellingsDowns", skip_eval=True)
        checks = {row["check"]: row for row in held["checks"]}
        self.assertFalse(checks["certification_status"]["ok"])
        self.assertEqual(checks["certification_status"]["detail"], "quarantined")
        self.assertEqual(held["phases"]["structural"], "failed")

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_runtime_gate_rejects_a_high_scoring_baseline_and_valid_bad_candidates(
        self, evaluate_candidate
    ):
        evaluate_candidate.return_value = {"combined_score": 1.0, "valid": 1.0}
        report = check_task("MaterialsScience/PhaseDiagramDiscovery")
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["baseline_eval"]["ok"])
        self.assertFalse(checks["bad_candidates_score_zero"]["ok"])

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_runtime_gate_rejects_an_invalid_candidate_with_a_positive_score(
        self, evaluate_candidate
    ):
        baseline = {
            "combined_score": 0.0,
            "valid": 1.0,
            "development_mechanism_score": 0.0,
            "development_false_discovery_rate": 1.0,
            "development_correct_refusal_rate": 0.0,
            "development_discovery_coverage": 1.0,
        }
        malformed = {"combined_score": 0.25, "valid": 0.0}
        evaluate_candidate.side_effect = [baseline, dict(baseline), malformed, malformed, malformed]
        report = check_task("ParticlePhysics/LookElsewhereAnomaly")
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["bad_candidates_score_zero"]["ok"])

    @mock.patch("scripts.check_task_contribution.load_frozen_wave")
    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_zero_release_score_cannot_hide_degenerate_frontier_records(self, evaluate, wave):
        wave.return_value = mock.Mock(task_family_id="fixture", wave_id="wave-1")
        baseline = {"combined_score": 0.0, "valid": 1.0, "frontier_records": []}
        abstention = {**baseline, "frontier_records": [{"cell_id": "claim", "canonical_id": "empty"}]}
        malformed = {"combined_score": 0.0, "valid": 0.0}
        evaluate.side_effect = [baseline, dict(baseline), abstention, abstention,
                                malformed, malformed, malformed]
        report = check_task("MaterialsScience/PhaseDiagramDiscovery")
        checks = {r["check"]: r for r in report["checks"]}
        self.assertFalse(checks["frontier_degenerate_credit_zero"]["ok"])
        self.assertIn("blanket_abstention", checks["frontier_degenerate_credit_zero"]["detail"])

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_repeated_infrastructure_failure_is_not_deterministic_science(self, evaluate):
        evaluate.return_value = {"combined_score": -1e18, "valid": 0.0, "infrastructure_failure": 1.0}
        report = check_task("MaterialsScience/PhaseDiagramDiscovery")
        checks = {r["check"]: r for r in report["checks"]}
        self.assertFalse(checks["deterministic_baseline"]["ok"])

    @mock.patch("scripts.check_task_contribution.load_certification")
    def test_structural_gate_requires_an_explicit_certification_record(self, load_certification):
        load_certification.return_value = {"schema_version": 1, "tasks": {}}
        report = check_task("MaterialsScience/PhaseDiagramDiscovery", skip_eval=True)
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["registered_in_certification"]["ok"])

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_identical_infrastructure_failures_never_prove_determinism(self, evaluate):
        evaluate.return_value = {"combined_score": -1e18, "valid": 0.0,
                                 "infrastructure_failure": True}
        report = check_task("MaterialsScience/PhaseDiagramDiscovery")
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["deterministic_baseline"]["ok"])


def test_missing_initial_solution_produces_failed_structural_report(tmp_path):
    import shutil
    from dataclasses import replace
    from scripts import check_task_contribution as gate

    original = gate.find_task("MaterialsScience/PhaseDiagramDiscovery", include_uncertified=True)
    task_dir = tmp_path / original.task_dir.name
    shutil.copytree(original.task_dir, task_dir)
    spec = replace(original, task_dir=task_dir, eval_dir=task_dir / "frontier_eval")
    spec.initial_program_path.unlink()
    with mock.patch.object(gate, "find_task", return_value=spec), mock.patch.object(gate, "ROOT", tmp_path):
        report = gate.check_task(spec.task_id, skip_eval=True)
    checks = {row["check"]: row for row in report["checks"]}
    assert checks["required_files"]["ok"] is False
    assert "solution.py" in checks["required_files"]["detail"]
    assert report["phases"]["structural"] == "failed"
    assert report["passed"] is False


class DiscoveryAxisDenominatorTests(unittest.TestCase):
    """A published rate without its count cannot be read, so the gate now asks for both.

    `correct_refusal_rate = 1.0` is one world out of one or thirty out of thirty, and the
    difference is the whole resolution of the axis: a three-world denominator lets a candidate
    that guesses hit a perfect axis once in twenty-seven tries. Thirty-seven of the forty-six
    discovery tasks publish rates with no counts; they are listed as pending rather than failed,
    the same way the shortcut contract was migrated.
    """

    @staticmethod
    def _split():
        import yaml as _yaml
        from sle.registry import list_tasks
        tax = _yaml.safe_load((ROOT / "sle" / "conf" / "exam_taxonomy.yaml").read_text(
            encoding="utf-8"))["tasks"]
        fdr = re.compile(r"false_discovery_(denominator|count)")
        refusal = re.compile(r"correct_refusal_(denominator|count)")
        compliant, missing = [], []
        for spec in list_tasks(None):
            if tax[spec.task_id]["form"] != "discovery":
                continue
            source = "".join(path.read_text(encoding="utf-8", errors="replace")
                             for path in sorted((spec.task_dir / "verification").glob("*.py")))
            (compliant if fdr.search(source) and refusal.search(source)
             else missing).append(spec.task_id)
        return compliant, missing

    def test_the_pending_inventory_is_exactly_the_non_compliant_discovery_tasks(self):
        pending = json.loads(gate.DISCOVERY_AXIS_MIGRATION.read_text(encoding="utf-8"))["tasks"]
        compliant, missing = self._split()
        self.assertEqual(sorted(pending), sorted(missing))
        self.assertTrue(compliant, "at least one discovery task must already comply")
        for task_id, entry in pending.items():
            with self.subTest(task=task_id):
                self.assertEqual(entry.get("status"), "pending")
                self.assertTrue(str(entry.get("reason") or "").strip())

    def test_the_policy_says_listing_is_not_a_pass(self):
        document = json.loads(gate.DISCOVERY_AXIS_MIGRATION.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertIn("never a pass", document["policy"])
        self.assertTrue(document["inventory_revision"])

    def test_counts_are_recognised_by_suffix_under_any_prefix(self):
        for key in ("development_correct_refusal_denominator", "heldout_correct_refusal_count",
                    "correct_refusal_denominator"):
            with self.subTest(key=key):
                self.assertTrue(gate._has_count({key: 3}, gate.DISCOVERY_REFUSAL_COUNTS))
        self.assertFalse(gate._has_count({"development_correct_refusal_rate": 1.0},
                                         gate.DISCOVERY_REFUSAL_COUNTS))


class ReportRowTests(unittest.TestCase):
    """A row that only states an observation must not decide a phase."""

    def test_a_report_row_leaves_the_verdict_alone(self):
        task_id = "DataPrivacy/SparseVectorAudit"
        axes = {"development_false_discovery_rate": 0.0,
                "development_correct_refusal_rate": 1.0,
                "development_discovery_coverage": 1.0,
                "development_mechanism_score": 0.8}
        probe = {"status": "passed", "passed": True, "detail": "declared guard held",
                 "observations": [], "reference_axes": axes, "reference_axes_saturated": True}
        with mock.patch.object(gate, "inspect_probe", return_value=probe):
            report = check_task(task_id, skip_eval=True)
        note = [row for row in report["checks"] if row["check"] == "discovery_axes_at_reference"]
        self.assertEqual(len(note), 1, report["checks"])
        self.assertTrue(note[0]["report"])
        self.assertIsNone(note[0]["ok"])
        self.assertEqual(note[0]["status"], "saturated")
        self.assertEqual(report["phases"]["structural"], "passed")
        self.assertNotIn("failed", report["phases"].values())

    def test_a_report_row_is_excluded_from_the_phase_verdict(self):
        note = {"check": "note", "ok": None, "report": True, "detail": ""}
        passing = {"check": "a", "ok": True, "detail": ""}
        self.assertEqual(gate._phase([passing]), "passed")
        self.assertEqual(gate._phase([passing, note]), "passed",
                         "a report row must not downgrade a passing phase")
        self.assertEqual(gate._phase([note]), "incomplete",
                         "a phase made only of report rows has established nothing")
        self.assertEqual(gate._phase([{"check": "b", "ok": False, "detail": ""}, note]), "failed")


if __name__ == "__main__":
    unittest.main()
