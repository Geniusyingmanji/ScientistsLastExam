from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_summary_module():
    path = Path(__file__).resolve().parents[1] / "scripts/summarize_science_calibrations.py"
    spec = importlib.util.spec_from_file_location("science_calibration_summary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScienceCalibrationSummaryTests(unittest.TestCase):
    def test_default_reports_cover_all_normal_science_calibrations(self):
        module = load_summary_module()
        self.assertEqual(len(module.DEFAULT_REPORTS), 75)
        self.assertTrue(any("truss_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any("antenna_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any("nmr_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any(
            "heat_exchanger_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "reaction_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "gravity_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "ocean_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "ocean_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "radiative_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "radiative_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "low_thrust_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "low_thrust_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "cavity_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "cavity_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "climate_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "climate_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "absorber_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "absorber_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "distillation_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "distillation_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "hartree_fock_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "hartree_fock_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "room_acoustics_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "room_acoustics_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "convection_diffusion_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "convection_diffusion_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "seismic_wave_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "seismic_wave_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rankine_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rankine_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "mosfet_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "mosfet_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rans_v2_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rans_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "gene_network_v1_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "gene_network_v1_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rna_inverse_v1_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "rna_inverse_v1_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "protein_stability_v1_b1" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "protein_stability_v1_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "electrolyte_conductivity_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "electrolyte_conductivity_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "demographic_sfs_v2_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "demographic_sfs_v2_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "calorimeter_v2_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "calorimeter_v2_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "prospective_meta_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "prospective_meta_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "photovoltaic_tandem_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "photovoltaic_tandem_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "catalyst_deactivation_lab_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "catalyst_deactivation_lab_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "qcm_raw_pipeline_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "qcm_raw_pipeline_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "force_field_hypothesis_v2_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "force_field_hypothesis_v2_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "alloy_hardness_v1_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "alloy_hardness_v1_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "diffraction_grating_v2_b1" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertTrue(any(
            "diffraction_grating_v2_b3" in path
            for path in module.DEFAULT_REPORTS
        ))
        self.assertFalse(any("blind" in path for path in module.DEFAULT_REPORTS))

        report = module.build_report([
            Path(__file__).resolve().parents[1] / path
            for path in module.DEFAULT_REPORTS
        ])
        self.assertEqual(report["normal_condition_count"], 75)
        self.assertEqual(report["task_count"], 38)

    def test_scalar_metric_filter_rejects_nonfinite_and_omits_nested(self):
        from sle.protocol import compact_scalar_metrics

        self.assertEqual(
            compact_scalar_metrics({
                "score": 0.5,
                "valid": True,
                "reason": None,
                "per_instance": [{"score": 1.0}],
            }),
            {"score": 0.5, "valid": True, "reason": None},
        )
        with self.assertRaises(ValueError):
            compact_scalar_metrics({"score": float("nan")})

    def test_compact_snapshot_binds_full_trajectory_without_nested_metrics(self):
        from sle.protocol import compact_trajectory_snapshot

        event = {
            "schema_version": 2,
            "step": 0,
            "oracle_calls": 1,
            "budget_units": 1,
            "score": 0.5,
            "best_score": 0.5,
            "valid": True,
            "accepted": True,
            "wall_seconds": 0.1,
            "cumulative_wall_seconds": 0.1,
            "candidate_sha256": "candidate",
            "parent_sha256": None,
            "metrics": {"robustness_score": 0.25, "per_instance": [{"x": 1}]},
            "algorithm_metadata": {
                "selection_policy": "offline_best_of_open_loop_batch",
                "nested": {"omit": True},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            snapshot = compact_trajectory_snapshot(path)
        self.assertEqual(len(snapshot["trajectory_sha256"]), 64)
        self.assertEqual(snapshot["events"][0]["metrics"], {"robustness_score": 0.25})
        self.assertEqual(
            snapshot["events"][0]["algorithm_metadata"],
            {"selection_policy": "offline_best_of_open_loop_batch"},
        )

    def test_portable_summary_content_is_pinned(self):
        module = load_summary_module()
        original = json.loads(module.PORTABLE_SUMMARY.read_text(encoding="utf-8"))
        mutations = (
            lambda document: document["records"][0].__setitem__(
                "source_revision", "tampered-revision"
            ),
            lambda document: document["records"][0]["trajectory"][0].__setitem__(
                "score", 12345.0
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                document = json.loads(json.dumps(original))
                mutate(document)
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "summary.json"
                    path.write_text(json.dumps(document), encoding="utf-8")
                    module._portable_records.cache_clear()
                    with patch.object(module, "PORTABLE_SUMMARY", path):
                        with self.assertRaisesRegex(ValueError, "hash"):
                            module._portable_records()
        module._portable_records.cache_clear()


if __name__ == "__main__":
    unittest.main()
