from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


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
    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_fast_preflight_executes_but_is_not_complete_calibration(self):
        report = _module().calibrate(recalibrate_references=False)
        self.assertTrue(report["preflight_passed"])
        self.assertFalse(report["execution_passed"])
        self.assertFalse(report["trusted_evidence"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["reference_recalibration"]["performed"])
        self.assertFalse(report["reference_recalibration"]["passed"])
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
