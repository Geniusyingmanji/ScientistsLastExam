from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts/analyze_maturity_gap_calibrations.py"
    spec = importlib.util.spec_from_file_location("maturity_gap_analysis", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MaturityGapAnalysisTests(unittest.TestCase):
    def test_frozen_reports_support_only_onramp_dispositions(self):
        module = load_module()
        report = module.build_report(module.DEFAULT_B1, module.DEFAULT_B3)
        self.assertTrue(report["execution_passed"])
        self.assertEqual(set(report["task_findings"]), module.EXPECTED_TASKS)
        self.assertEqual(
            report["task_findings"]["DynamicalSystems/LyapunovControl"]
            ["current_disposition"],
            "one_step_saturated_on_ramp",
        )
        self.assertEqual(
            report["task_findings"]["Geophysics/SeismicInversion"]
            ["current_disposition"],
            "one_step_saturated_on_ramp",
        )
        self.assertEqual(
            report["task_findings"]["NuclearEngineering/NeutronDiffusionCriticality"]
            ["current_disposition"],
            "fixed_single_regime_near_ceiling_on_ramp",
        )


if __name__ == "__main__":
    unittest.main()
