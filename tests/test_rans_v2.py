from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/RANSCalibration"
VERIFICATION = TASK / "verification"
CALIBRATION = ROOT / "scripts/calibrate_rans_v2.py"
DATA = VERIFICATION / "channel_dns_profiles_v1.json"
DATA_SHA256 = "0f70ce507fa65175f044538b41a266d42347cdf9c1bf2e7fafd8f630f47ed9bf"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    sys.path.insert(0, str(VERIFICATION))
    try:
        return _load(VERIFICATION / "evaluator.py", "rans_v2_test_oracle")
    finally:
        sys.path.pop(0)


class RANSV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()

    def test_dns_provenance_license_hash_and_splits(self):
        document = json.loads(DATA.read_text(encoding="utf-8"))
        source = document["source"]
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), DATA_SHA256)
        self.assertEqual(source["doi"], "10.5281/zenodo.5749302")
        self.assertEqual(source["concept_doi"], "10.5281/zenodo.4916024")
        self.assertEqual(source["license"], "CC-BY-4.0")
        self.assertEqual(len(source["authors"]), 4)
        self.assertEqual(set(source["source_file_sha256"]), {"180", "395", "590", "950"})
        self.assertEqual(tuple(self.oracle.DEVELOPMENT_RE_TAU), (180, 395))
        self.assertEqual(tuple(self.oracle.HELDOUT_RE_TAU), (590, 950))
        for key, row in document["profiles"].items():
            self.assertGreaterEqual(len(row["y_plus"]), 180)
            self.assertEqual(len(row["y_plus"]), len(row["mean_u_plus"]))
            self.assertEqual(len(row["y_plus"]), len(row["uv_plus"]))
            self.assertLess(row["y_plus"][-1], int(key))

    def test_baseline_nominal_robust_and_metric_sealing(self):
        oracle = self.oracle
        baseline = oracle.evaluate(oracle.standard_closure)
        nominal = oracle.evaluate(oracle.reference_closure)
        robust = oracle.evaluate(oracle.robust_reference_closure)
        self.assertTrue(oracle.RANS_CALIBRATION_V2)
        for key in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score",
        ):
            self.assertEqual(baseline[key], 0.0)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(nominal["combined_score"], 1.0)
        self.assertGreater(nominal["robustness_score"], 0.80)
        self.assertLess(nominal["heldout_policy_score"], 0.70)
        self.assertLess(nominal["heldout_robustness_score"], 0.60)
        self.assertAlmostEqual(robust["robustness_score"], 1.0)
        self.assertGreater(robust["combined_score"], 0.90)
        self.assertLess(robust["heldout_policy_score"], nominal["heldout_policy_score"])
        self.assertEqual(robust["heldout_robustness_score"], 0.0)
        self.assertEqual(
            set(search_visible_metrics(nominal)),
            {"combined_score", "valid", "feasibility_rate", "raw_score"},
        )

    def test_total_shear_positivity_and_shift_grid_are_physical(self):
        oracle = self.oracle
        for parameters in (
            oracle.STANDARD_PARAMETERS,
            oracle.NOMINAL_REFERENCE_PARAMETERS,
            oracle.ROBUST_REFERENCE_PARAMETERS,
        ):
            for re_tau in oracle.DEVELOPMENT_RE_TAU + oracle.HELDOUT_RE_TAU:
                row = oracle.DNS_PROFILES[re_tau]
                for factor in (1.0, 0.975, 1.025):
                    y_plus = row["y_plus"] * factor
                    mean_u, mean_shear, reynolds_shear = oracle.closure_profiles(
                        parameters, re_tau * factor, y_plus
                    )
                    total = mean_shear + reynolds_shear
                    expected = 1.0 - y_plus / (re_tau * factor)
                    self.assertLess(float(np.max(np.abs(total - expected))), 3e-15)
                    self.assertTrue(np.all(mean_shear >= 0.0))
                    self.assertTrue(np.all(reynolds_shear >= 0.0))
                    self.assertTrue(np.all(np.diff(mean_u) >= 0.0))
                    self.assertLess(y_plus[-1], re_tau * factor)

    def test_four_parameter_development_sensitivity_is_full_rank(self):
        calibration = _load(CALIBRATION, "rans_v2_calibration_test")
        record = calibration._sensitivity_record(self.oracle)
        self.assertEqual(record["parameter_count"], 4)
        self.assertEqual(record["jacobian_rank"], 4)
        self.assertLess(record["parameter_scaled_condition_number"], 100.0)
        self.assertTrue(record["passed"])

    def test_calibration_rebuild_and_committed_literals(self):
        calibration = _load(CALIBRATION, "rans_v2_calibration_rebuild_test")
        report = calibration.build_report(rebuild=True)
        self.assertTrue(report["execution_passed"])
        self.assertTrue(report["data_provenance_checks"]["passed"])
        self.assertTrue(report["identifiability"]["passed"])
        self.assertTrue(report["invalid_artifact_checks_passed"])
        self.assertTrue(report["physics_checks_passed"])
        self.assertTrue(report["witness_checks_passed"])
        self.assertTrue(report["optimizer_rebuild_checks_passed"])
        self.assertEqual(len(report["optimizer_rebuild_checks"]), 4)

    def test_malformed_nonfinite_boolean_complex_and_bounds_fail_closed(self):
        factories = (
            lambda: None,
            lambda: np.zeros(3),
            lambda: np.full(4, np.nan),
            lambda: np.full(4, np.inf),
            lambda: [True, 26.0, 0.0, 0.0],
            lambda: np.ones(4) + 1j,
            lambda: [0.19, 26.0, 0.0, 0.0],
            lambda: {"kappa": 0.41, "A_plus": 26.0,
                     "outer_linear": 0.0, "wrong": 0.0},
        )
        for factory in factories:
            metrics = self.oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)

    def test_secure_sandbox_blocks_oracle_read_and_network(self):
        spec = find_task("RANSCalibration", include_uncertified=True)
        source = textwrap.dedent("""
            import os
            import socket

            def calibrate_rans():
                try:
                    open('/workspace/benchmarks/Engineering/RANSCalibration/verification/evaluator.py').read()
                    return [0.48663474137035673, 35.262103882288415, 0.63124557167500384, -1.2612246455851348]
                except Exception:
                    pass
                socket.create_connection(('1.1.1.1', 53), timeout=0.1)
                return [0.41, 26.0, 0.0, 0.0]
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=20)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertIn(metrics.get("candidate_failure_kind"), {
            "blocked_or_missing_file", "blocked_operation", "candidate_runtime_error"
        })

    def test_legacy_driver_uses_v2_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable, str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(TASK / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT), check=False, capture_output=True, text=True,
                timeout=30,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()
