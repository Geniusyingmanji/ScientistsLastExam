from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_measurement_health_preflight.py"
SPEC = importlib.util.spec_from_file_location("measurement_health_preflight", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def stable_evaluator(_spec, _candidate, _timeout):
    return {"combined_score": 0.5, "valid": 1.0}


class MeasurementHealthPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = MODULE.build_report(evaluator=stable_evaluator)
        cls.tasks = {row["task"]: row for row in cls.report["tasks"]}

    def test_frozen_cohort_is_covered_and_all_bound_evidence_passes(self):
        self.assertEqual(self.report["task_count"], 7)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])
        self.assertEqual(self.report["preflight_passed_count"], 7)
        self.assertEqual(self.report["long_horizon_run_permitted_count"], 7)
        for row in self.report["tasks"]:
            self.assertTrue(row["long_horizon_run_permitted"])
            self.assertEqual(row["not_permitted_reasons"], [])
            materiality = row["checks"]["scientific_materiality"]
            self.assertEqual(materiality["status"], "pass")
            self.assertTrue(materiality["criteria_complete"])
            self.assertTrue(materiality["axes_covered"])
            self.assertTrue(materiality["same_witness_enforced"])
            self.assertIn("not agent improvement", materiality["claim"])
            self.assertEqual(row["checks"]["exactly_once_recovery"]["status"], "pass")
            self.assertTrue(
                row["checks"]["exactly_once_recovery"]["oracle_deterministic"]
            )
            self.assertIn(
                "not physical exactly-once",
                row["checks"]["exactly_once_recovery"]["claim"],
            )

    def test_fixed_artifact_noise_is_actually_remeasured(self):
        for row in self.report["tasks"]:
            check = row["checks"]["fixed_artifact_noise"]
            self.assertEqual(check["status"], "pass")
            self.assertEqual(check["repetitions"], 3)
            self.assertEqual(check["scores"], [0.5, 0.5, 0.5])
            self.assertEqual(check["noise_span"], 0.0)
            self.assertTrue(check["exact_payload_match"])

    def test_current_contract_and_artifact_bindings_are_exact(self):
        for row in self.report["tasks"]:
            self.assertEqual(row["checks"]["frozen_runtime_contract"]["status"], "pass")
            self.assertEqual(row["checks"]["frozen_task_package"]["status"], "pass")
            self.assertEqual(row["checks"]["fixed_artifact_binding"]["status"], "pass")
            artifact = row["checks"]["fixed_artifact_binding"]
            self.assertIn("measurement_health_preflight_artifacts", artifact["path"])
            self.assertNotIn("runs/", artifact["path"])
            self.assertEqual(
                artifact["portable_artifact"]["candidate_sha256"],
                artifact["actual_sha256"],
            )

    def test_diffraction_uses_current_contract_calibration(self):
        diffraction = self.tasks["Optics/DiffractionGratingDesign"]
        check = diffraction["checks"]["baseline_reference_separation"]
        self.assertEqual(check["status"], "pass")
        self.assertTrue(check["contract_compatibility"]["runtime_files_unchanged"])
        # The property is that the calibration was measured against the evaluator that ships
        # now - not that it carries a particular date. Pinning the filename made this test fail
        # the moment the evidence was legitimately re-measured, which is backwards: a re-measured
        # calibration is the thing this test wants, so it asserts the hash instead.
        calibration = json.loads(
            (ROOT / check["evidence"]["path"]).read_text(encoding="utf-8"))
        recorded = calibration["task_source_sha256"]
        evaluator = next(path for path in recorded if path.endswith("verification/evaluator.py"))
        self.assertEqual(
            recorded[evaluator],
            hashlib.sha256((ROOT / evaluator).read_bytes()).hexdigest(),
            "the bound calibration was measured against a different evaluator than the one "
            "on disk, so it is not evidence about the current runtime",
        )
        for task in (
            "Electrochemistry/ElectrolyteConductivityDesign",
            "RNAEngineering/RNAInverseDesign",
            "Semiconductor/MOSFETDoping",
            "StructuralEngineering/TrussWeightMinimization",
            "Thermodynamics/HeatExchangerDesign",
            "Turbulence/RANSCalibration",
        ):
            self.assertEqual(
                self.tasks[task]["checks"]["baseline_reference_separation"]["status"],
                "pass",
            )

    def test_numerical_resolution_and_materiality_remain_separate(self):
        for row in self.report["tasks"]:
            resolution = row["checks"]["evaluator_numerical_resolution"]
            self.assertEqual(resolution["status"], "pass")
            self.assertGreater(resolution["minimum_nonzero_score_gap"], 0.0)
            materiality = row["checks"]["scientific_materiality"]
            self.assertEqual(materiality["status"], "pass")
            self.assertNotIn("minimum_nonzero_score_gap", materiality)
            self.assertNotEqual(
                materiality["evidence"]["path"], resolution["evidence"]["path"]
            )

    def test_noisy_or_invalid_replay_fails_the_noise_gate(self):
        calls = {"count": 0}

        def noisy(_spec, _candidate, _timeout):
            calls["count"] += 1
            return {
                "combined_score": 0.5 + (calls["count"] % 2) * 1e-4,
                "valid": 1.0,
            }

        report = MODULE.build_report(evaluator=noisy)
        self.assertEqual(report["task_count"], 7)
        self.assertTrue(all(
            row["checks"]["fixed_artifact_noise"]["status"] == "fail"
            for row in report["tasks"]
        ))
        self.assertTrue(all(
            row["checks"]["evaluator_numerical_resolution"]["status"] == "missing"
            for row in report["tasks"]
        ))

    def test_hidden_metric_drift_fails_even_when_combined_score_is_constant(self):
        calls = {"count": 0}

        def hidden_drift(_spec, _candidate, _timeout):
            calls["count"] += 1
            return {
                "combined_score": 0.5,
                "valid": 1.0,
                "heldout_policy_score": calls["count"] * 1e-4,
            }

        report = MODULE.build_report(evaluator=hidden_drift)
        for row in report["tasks"]:
            check = row["checks"]["fixed_artifact_noise"]
            self.assertEqual(check["noise_span"], 0.0)
            self.assertFalse(check["exact_payload_match"])
            self.assertEqual(check["status"], "fail")

    def test_tampered_spec_binding_prevents_execution(self):
        document = json.loads(MODULE.DEFAULT_SPEC.read_text(encoding="utf-8"))
        document["top_level_overrides"]["cohort_manifest_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spec.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            report = MODULE.build_report(spec_path=path, evaluator=stable_evaluator)
        self.assertEqual(report["task_count"], 0)
        self.assertFalse(report["execution_passed"])
        self.assertIn(
            "preflight spec does not bind the current cohort manifest",
            report["issues"],
        )

    def test_portable_artifact_pack_hash_is_fail_closed(self):
        document = json.loads(MODULE.LEGACY_SPEC.read_text(encoding="utf-8"))
        document["tasks"][0]["portable_artifact"]["evidence"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spec.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            report = MODULE.build_report(spec_path=path,
                                         manifest_path=MODULE.LEGACY_MANIFEST,
                                         evaluator=stable_evaluator)
        first = report["tasks"][0]
        self.assertEqual(first["checks"]["fixed_artifact_binding"]["status"], "fail")
        self.assertEqual(first["checks"]["fixed_artifact_noise"]["status"], "missing")

    def test_v2_overlay_base_hash_is_fail_closed_before_evaluation(self):
        document = json.loads(MODULE.DEFAULT_SPEC.read_text(encoding="utf-8"))
        document["base_spec"]["sha256"] = "0" * 64
        calls = {"count": 0}

        def evaluator(*_args):
            calls["count"] += 1
            return stable_evaluator(*_args)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spec.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            report = MODULE.build_report(spec_path=path, evaluator=evaluator)
        self.assertEqual(calls["count"], 0)
        self.assertFalse(report["execution_passed"])
        self.assertIn("v2 preflight base-spec hash differs", report["issues"])

    def test_recovery_requires_a_deterministic_task_card(self):
        config = self.report["tasks"][0]["checks"]["exactly_once_recovery"]
        self.assertEqual(config["status"], "pass")
        spec = MODULE.load_task_spec(
            MODULE.ROOT / "benchmarks/Chemistry/ElectrolyteConductivityDesign"
        )
        original = MODULE._task_card
        try:
            MODULE._task_card = lambda _spec: ({"oracle": {"deterministic": False}}, None)
            resolved, _inputs, issues = MODULE._resolve_preflight_spec(MODULE.DEFAULT_SPEC)
            self.assertEqual(issues, [])
            failed = MODULE._recovery_check(
                resolved["tasks"][0]["exactly_once_recovery"], spec
            )
        finally:
            MODULE._task_card = original
        self.assertEqual(failed["status"], "fail")
        self.assertIn("not declared deterministic", failed["reason"])

    def test_materiality_task_identity_mismatch_fails_closed(self):
        resolved, _inputs, issues = MODULE._resolve_preflight_spec(MODULE.DEFAULT_SPEC)
        self.assertEqual(issues, [])
        spec = MODULE.load_task_spec(
            MODULE.ROOT / "benchmarks/Chemistry/ElectrolyteConductivityDesign"
        )
        config = dict(resolved["tasks"][0]["scientific_materiality"])
        config["task_pointer"] = "/tasks/1"
        check = MODULE._scientific_materiality_check(
            config, "Electrochemistry/ElectrolyteConductivityDesign", spec
        )
        self.assertEqual(check["status"], "fail")
        self.assertFalse(check["task_identity_matches"])

    def test_materiality_runtime_drift_fails_closed(self):
        resolved, _inputs, issues = MODULE._resolve_preflight_spec(MODULE.DEFAULT_SPEC)
        self.assertEqual(issues, [])
        spec = MODULE.load_task_spec(
            MODULE.ROOT / "benchmarks/Chemistry/ElectrolyteConductivityDesign"
        )
        original = MODULE._contract_compatibility
        try:
            MODULE._contract_compatibility = lambda *_args: {
                "runtime_files_unchanged": False,
                "changed_paths": ["verification/evaluator.py"],
            }
            check = MODULE._scientific_materiality_check(
                resolved["tasks"][0]["scientific_materiality"],
                "Electrochemistry/ElectrolyteConductivityDesign",
                spec,
            )
        finally:
            MODULE._contract_compatibility = original
        self.assertEqual(check["status"], "fail")


if __name__ == "__main__":
    unittest.main()
