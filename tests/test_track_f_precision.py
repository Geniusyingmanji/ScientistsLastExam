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

    def test_frozen_pilot_yields_fixed_unpaired_primary_design(self):
        report = MODULE.plan(self.PILOT)
        self.assertEqual(report["fixed_balanced_blocks_per_condition"], 48)
        self.assertEqual(report["scheduled_search_cells"], 384)
        self.assertEqual(report["scheduled_model_proposals"], 1152)
        self.assertFalse(report["design"]["same_local_identifier_is_paired_seed"])
        self.assertEqual(report["design"]["provider_draw_assumption"], "independent_unpaired")
        self.assertEqual(report["design"]["primary_task"], "DynamicalSystems/ActiveLawDiscovery")
        self.assertEqual(report["design"]["primary_pilot_proxy_axis"], "robustness_score")
        self.assertEqual(report["design"]["secondary_stress_test_task"], "Optics/DiffractionGratingDesign")
        active = report["pilot_diagnostics"]["DynamicalSystems/ActiveLawDiscovery"]
        diffraction = report["pilot_diagnostics"]["Optics/DiffractionGratingDesign"]
        self.assertAlmostEqual(active["pilot_difference_sample_sd"], 0.023637872588285126)
        self.assertAlmostEqual(diffraction["pilot_difference_sample_sd"], 0.6154332715955124)
        self.assertEqual(
            [row["balanced_n_per_condition"] for row in report["design_sigma_scenarios"]],
            [32, 48, 64, 88],
        )
        self.assertGreater(report["power_at_fixed_n_under_design_sigma"], 0.80)
        self.assertFalse(report["fixed_sample_rule"]["sample_size_adaptation"])
        self.assertFalse(report["fixed_sample_rule"]["early_stopping_from_outcomes"])
        self.assertFalse(report["claims"]["feedback_effect_identified"])

    def test_exact_power_is_monotone_in_n_and_decreases_with_sigma(self):
        powers = [
            MODULE.exact_two_sample_power(
                n_per_condition=n, sigma=0.25, effect=0.15, alpha=0.05
            )
            for n in (16, 32, 64)
        ]
        self.assertLess(powers[0], powers[1])
        self.assertLess(powers[1], powers[2])
        self.assertGreater(
            MODULE.exact_two_sample_power(
                n_per_condition=48, sigma=0.25, effect=0.15, alpha=0.05
            ),
            MODULE.exact_two_sample_power(
                n_per_condition=48, sigma=0.35, effect=0.15, alpha=0.05
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
