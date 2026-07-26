from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/plan_track_f_precision.py"
SPEC = importlib.util.spec_from_file_location("track_f_precision_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrackFPrecisionTests(unittest.TestCase):
    PILOT = ROOT / "experiments/feedback_measurement_pilot_analysis_2026-07-26_v1.json"

    def test_frozen_pilot_yields_balanced_stage1_and_variance_cap(self):
        report = MODULE.plan(self.PILOT)
        self.assertEqual(report["most_variable_task"], "Optics/DiffractionGratingDesign")
        self.assertEqual(report["stage1_balanced_blocks_per_condition"], 32)
        self.assertEqual(
            report["maximum_blinded_variance_reassessment_blocks_per_condition"],
            68,
        )
        diffraction = report["task_plans"]["Optics/DiffractionGratingDesign"]
        self.assertAlmostEqual(diffraction["pilot_sample_sd"], 0.25867132689266675)
        self.assertEqual(
            [row["balanced_n"] for row in diffraction["scenarios"]],
            [32, 48, 68],
        )
        self.assertGreater(diffraction["scenarios"][0]["power_at_balanced_n"], 0.80)
        self.assertTrue(report["blinded_reassessment_rule"]["variance_only"])
        self.assertFalse(report["claims"]["feedback_effect_identified"])

    def test_exact_power_is_monotone_in_n_and_decreases_with_sigma(self):
        powers = [
            MODULE.exact_two_sided_power(
                n=n, sigma=0.25, effect=0.15, alpha=0.025
            )
            for n in (16, 32, 64)
        ]
        self.assertLess(powers[0], powers[1])
        self.assertLess(powers[1], powers[2])
        self.assertGreater(
            MODULE.exact_two_sided_power(
                n=32, sigma=0.25, effect=0.15, alpha=0.025
            ),
            MODULE.exact_two_sided_power(
                n=32, sigma=0.35, effect=0.15, alpha=0.025
            ),
        )

    def test_untrusted_or_incomplete_pilot_fails_closed(self):
        pilot = json.loads(self.PILOT.read_text(encoding="utf-8"))
        for mutation in ("passed", "trusted_evidence", "execution_passed"):
            changed = json.loads(json.dumps(pilot))
            changed[mutation] = False
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "pilot.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    MODULE.plan(path)


if __name__ == "__main__":
    unittest.main()
