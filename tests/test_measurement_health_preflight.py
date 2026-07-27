from __future__ import annotations

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

    def test_frozen_cohort_is_covered_and_missing_evidence_fails_closed(self):
        self.assertEqual(self.report["task_count"], 7)
        self.assertEqual(self.report["issues"], [])
        self.assertTrue(self.report["execution_passed"])
        self.assertEqual(self.report["preflight_passed_count"], 0)
        self.assertEqual(self.report["long_horizon_run_permitted_count"], 0)
        for row in self.report["tasks"]:
            self.assertFalse(row["long_horizon_run_permitted"])
            self.assertEqual(row["checks"]["scientific_materiality"]["status"], "missing")
            self.assertEqual(row["checks"]["exactly_once_recovery"]["status"], "missing")

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

    def test_calibration_contract_drift_is_not_silently_accepted(self):
        diffraction = self.tasks["Optics/DiffractionGratingDesign"]
        check = diffraction["checks"]["baseline_reference_separation"]
        self.assertEqual(check["status"], "missing")
        self.assertIn(
            "verification/evaluator.py",
            " ".join(check["contract_compatibility"]["changed_paths"]),
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

    def test_numerical_resolution_is_not_relabelled_as_materiality(self):
        for row in self.report["tasks"]:
            resolution = row["checks"]["evaluator_numerical_resolution"]
            self.assertEqual(resolution["status"], "pass")
            self.assertGreater(resolution["minimum_nonzero_score_gap"], 0.0)
            self.assertEqual(row["checks"]["scientific_materiality"]["status"], "missing")

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
        document["cohort_manifest_sha256"] = "0" * 64
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
        document = json.loads(MODULE.DEFAULT_SPEC.read_text(encoding="utf-8"))
        document["tasks"][0]["portable_artifact"]["evidence"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spec.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            report = MODULE.build_report(spec_path=path, evaluator=stable_evaluator)
        first = report["tasks"][0]
        self.assertEqual(first["checks"]["fixed_artifact_binding"]["status"], "fail")
        self.assertEqual(first["checks"]["fixed_artifact_noise"]["status"], "missing")


if __name__ == "__main__":
    unittest.main()
