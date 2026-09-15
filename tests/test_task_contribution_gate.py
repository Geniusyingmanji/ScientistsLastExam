"""The contribution gate must catch a missing package before an LLM run does.

It wraps checks CONTRIBUTING.md already names. This file pins that PhaseDiagramDiscovery
passes the structural half, so the hy3 debug path is exercising eval and the model, not a
missing Task.md.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
            "Gravitation/PTAHellingsDowns",
            "Physics/ComplexBoseLaw",
            "MaterialsScience/QuinaryConvexHull",
            "Mathematics/HeavyTailEvidence",
        ):
            self._assert_structural_gate(task_id)

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_runtime_gate_rejects_a_high_scoring_baseline_and_valid_bad_candidates(
        self, evaluate_candidate
    ):
        evaluate_candidate.return_value = {"combined_score": 1.0, "valid": 1.0}
        report = check_task("Mathematics/RamseyLowerBound")
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
        report = check_task("Mathematics/RamseyLowerBound")
        checks = {r["check"]: r for r in report["checks"]}
        self.assertFalse(checks["deterministic_baseline"]["ok"])

    @mock.patch("scripts.check_task_contribution.load_certification")
    def test_structural_gate_requires_an_explicit_certification_record(self, load_certification):
        load_certification.return_value = {"schema_version": 1, "tasks": {}}
        report = check_task("Mathematics/RamseyLowerBound", skip_eval=True)
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["registered_in_certification"]["ok"])

    @mock.patch("scripts.check_task_contribution.evaluate_candidate")
    def test_identical_infrastructure_failures_never_prove_determinism(self, evaluate):
        evaluate.return_value = {"combined_score": -1e18, "valid": 0.0,
                                 "infrastructure_failure": True}
        report = check_task("Mathematics/RamseyLowerBound")
        checks = {row["check"]: row for row in report["checks"]}
        self.assertFalse(checks["deterministic_baseline"]["ok"])


def test_missing_initial_solution_produces_failed_structural_report(tmp_path):
    import shutil
    from dataclasses import replace
    from scripts import check_task_contribution as gate

    original = gate.find_task("Mathematics/RamseyLowerBound", include_uncertified=True)
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


if __name__ == "__main__":
    unittest.main()
