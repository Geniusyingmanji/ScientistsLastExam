from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/calibrate_room_acoustics_v2.py"
    spec = importlib.util.spec_from_file_location(
        "room_acoustics_calibration_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load room-acoustics calibration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoomAcousticsCalibrationTests(unittest.TestCase):
    def test_calibration_executes_and_trust_follows_source_provenance(self):
        report = _module().calibrate()
        self.assertTrue(report["execution_passed"])
        expected_trust = bool(
            report["source_provenance"]["git_available"]
            and not report["source_provenance"]["source_tree_dirty"]
        )
        self.assertEqual(report["trusted_evidence"], expected_trust)
        self.assertEqual(report["passed"], expected_trust)
        self.assertEqual(
            len(report["independent_equation_and_reference_checks"]), 6
        )
        self.assertTrue(all(
            row["passed"]
            for row in report["independent_equation_and_reference_checks"]
        ))
        self.assertTrue(report["difficulty_gate"]["passed"])
        self.assertTrue(report["determinism_check"]["passed"])
        self.assertTrue(all(
            row["valid"] == 0.0 and row["combined_score"] == 0.0
            for row in report["invalid_artifact_checks"].values()
        ))


if __name__ == "__main__":
    unittest.main()
