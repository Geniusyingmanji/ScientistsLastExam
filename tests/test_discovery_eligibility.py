"""Retirement is enforceable independently of execution and certification flags."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

from sle.certification import certification_status
from sle.discovery_eligibility import (
    QUALIFICATION_CHECKS, discovery_eligibility, load_discovery_eligibility,
    require_discovery_frontier_eligibility,
)
from sle.frontier import promote_frontier_receipt
from sle.registry import find_task


class DiscoveryEligibilityTests(unittest.TestCase):
    def test_all_six_holds_are_quarantined_but_explicitly_addressable(self):
        records = load_discovery_eligibility()["tasks"]
        self.assertEqual(len(records), 6)
        for task_id, record in records.items():
            with self.subTest(task_id=task_id):
                self.assertEqual(certification_status(task_id), "quarantined")
                with self.assertRaises(KeyError):
                    find_task(task_id)
                spec = find_task(task_id, include_uncertified=True)
                verdict = discovery_eligibility(spec)
                self.assertEqual(verdict["status"], record["status"])
                self.assertTrue(verdict["historical_evaluation_allowed"])
                self.assertTrue(verdict["reviewed_package_matches"])
                self.assertFalse(verdict["frontier_eligible"])

    def test_hold_survives_package_and_role_edits(self):
        spec = find_task("PTAHellingsDowns", include_uncertified=True)
        spec.metadata = {**spec.metadata, "scientific_role": "optimization"}
        with patch("sle.algorithms.common.task_package_sha256", return_value="f" * 64):
            verdict = discovery_eligibility(spec)
        self.assertEqual(verdict["status"], "quarantined_shortcut")
        self.assertFalse(verdict["reviewed_package_matches"])
        self.assertFalse(verdict["frontier_eligible"])

    def test_new_v2_requires_calibration(self):
        spec = find_task("PTAHellingsDowns", include_uncertified=True)
        spec.task_id = "Gravitation/PTAHellingsDownsV2"
        verdict = discovery_eligibility(spec)
        self.assertEqual(verdict["status"], "calibration_required")
        self.assertFalse(verdict["frontier_eligible"])

    def test_optimization_is_not_qualified_by_discovery_policy(self):
        verdict = discovery_eligibility(SimpleNamespace(task_id="Fixture/Optimization",
                                                       metadata={"scientific_role": "optimization"}))
        self.assertEqual(verdict["status"], "not_applicable")
        self.assertIsNone(verdict["frontier_eligible"])

    def test_promotion_blocks_hold_before_reading_or_creating_ledger(self):
        spec = find_task("AMOCTippingRefusal", include_uncertified=True)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("sle.frontier.load_frozen_wave") as load_wave:
                with self.assertRaisesRegex(ValueError, "quarantined_shortcut"):
                    promote_frontier_receipt(
                        spec, run_workdir=root / "missing", ledger_root=root / "ledger",
                        request_id="a" * 64,
                    )
                load_wave.assert_not_called()
            self.assertFalse((root / "ledger").exists())

    def test_cli_allow_uncertified_does_not_bypass_promotion(self):
        from sle.cli import main
        with self.assertRaisesRegex(ValueError, "discovery frontier promotion blocked"):
            main(["frontier-promote", "--task", "BlackBoxGroupIdentification",
                  "--allow-uncertified", "--run-workdir", "/nonexistent/run",
                  "--ledger-root", "/nonexistent/ledger", "--request-id", "a" * 64])

    def test_discovery_wave_cannot_hide_under_optimization_role(self):
        from _branch_fixtures import find_task as fixture_task
        spec = fixture_task("LennardJonesCluster")
        spec.metadata = {**spec.metadata, "scientific_role": "optimization"}
        wave = SimpleNamespace(cells={"cell": {"kind": "discovery"}})
        with patch("sle.frontier.load_frozen_wave", return_value=wave):
            with self.assertRaisesRegex(ValueError, "calibration_required"):
                promote_frontier_receipt(
                    spec, run_workdir=Path("/nonexistent/run"),
                    ledger_root=Path("/nonexistent/ledger"), request_id="a" * 64,
                )

    def _qualification_fixture(self, root):
        spec = SimpleNamespace(task_id="Test/DiscoveryV2", task_dir=root / "task",
                               metadata={"scientific_role": "discovery"})
        spec.task_dir.mkdir()
        (spec.task_dir / "oracle.py").write_text("original")
        from sle.algorithms.common import task_package_sha256
        package = task_package_sha256(spec)
        evidence = {"schema_version": 1, "task_id": spec.task_id,
                    "task_package_sha256": package,
                    "qualification_checks": dict.fromkeys(QUALIFICATION_CHECKS, True),
                    "evidence_refs": ["reviewed-calibration-run-receipt"]}
        artifact = root / "calibration.json"
        artifact.write_text(json.dumps(evidence))
        review = {"reviewer": "domain reviewer", "reviewed_at": "2026-09-18",
                  "evidence_path": "calibration.json",
                  "evidence_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
        record = {"status": "qualified", "reason": "reviewed evidence",
                  "task_package_sha256": package, "qualification": review}
        policy = root / "policy.yaml"
        policy.write_text(yaml.safe_dump({"schema_version": 1,
                          "default_discovery_status": "calibration_required",
                          "tasks": {spec.task_id: record}}))
        return spec, policy, artifact, record, evidence

    def test_qualification_requires_matching_package_and_reviewed_evidence(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, policy, artifact, _record, _evidence = self._qualification_fixture(root)
            with patch("sle.discovery_eligibility.ROOT", root):
                self.assertTrue(discovery_eligibility(spec, policy_path=policy)["frontier_eligible"])
                (spec.task_dir / "oracle.py").write_text("changed")
                changed = discovery_eligibility(spec, policy_path=policy)
                self.assertEqual(changed["status"], "calibration_required")
                self.assertFalse(changed["frontier_eligible"])
                (spec.task_dir / "oracle.py").write_text("original")
                artifact.write_text("changed evidence")
                self.assertFalse(discovery_eligibility(spec, policy_path=policy)["frontier_eligible"])

    def test_qualified_label_alone_or_incomplete_checks_cannot_qualify(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, policy, artifact, record, evidence = self._qualification_fixture(root)
            for missing in ("qualification", "independent_confirmation_worlds"):
                with self.subTest(missing=missing):
                    changed = dict(record)
                    if missing == "qualification":
                        changed.pop("qualification")
                    else:
                        evidence["qualification_checks"][missing] = False
                        artifact.write_text(json.dumps(evidence))
                        changed["qualification"]["evidence_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
                    policy.write_text(yaml.safe_dump({"schema_version": 1,
                                      "default_discovery_status": "calibration_required",
                                      "tasks": {spec.task_id: changed}}))
                    with patch("sle.discovery_eligibility.ROOT", root):
                        self.assertFalse(discovery_eligibility(spec, policy_path=policy)["frontier_eligible"])

    def test_malformed_policy_fails_closed(self):
        spec = find_task("PTAHellingsDowns", include_uncertified=True)
        with TemporaryDirectory() as temporary:
            policy = Path(temporary) / "policy.yaml"
            policy.write_text("schema_version: 1\ndefault_discovery_status: qualified\ntasks: {}\n")
            with self.assertRaises(ValueError):
                discovery_eligibility(spec, policy_path=policy)

    def test_reviewed_artifact_cannot_escape_repository(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, policy, artifact, record, _evidence = self._qualification_fixture(root)
            for path in (str(artifact.resolve()), "../calibration.json"):
                with self.subTest(path=path):
                    record["qualification"]["evidence_path"] = path
                    policy.write_text(yaml.safe_dump({"schema_version": 1,
                                      "default_discovery_status": "calibration_required",
                                      "tasks": {spec.task_id: record}}))
                    with patch("sle.discovery_eligibility.ROOT", root):
                        verdict = discovery_eligibility(spec, policy_path=policy)
                    self.assertFalse(verdict["frontier_eligible"])
                    self.assertIn("repository-relative", verdict["reason"])

    def test_admission_keeps_scientific_axes_but_blocks_frontier_claim(self):
        path = Path(__file__).resolve().parents[1] / "scripts/report_discovery_admission.py"
        module_spec = importlib.util.spec_from_file_location("eligibility_admission", path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "in.json", root / "out.json"
            source.write_text(json.dumps({"rows": [{
                "task": "Mathematics/BlackBoxGroupIdentification",
                "verdict": "measures_iteration", "task_version": "old-version",
            }]}))
            module.main(["--admission", str(source), "--output", str(output)])
            row = json.loads(output.read_text())["rows"][0]
        self.assertEqual(row["verdict"], "discovery_public_score_only")
        self.assertFalse(row["frontier_claim_eligible"])
        self.assertEqual(row["current_task_eligibility"]["status"], "quarantined_provisional")


if __name__ == "__main__":
    unittest.main()
