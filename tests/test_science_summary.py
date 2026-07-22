from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_summary_module():
    path = Path(__file__).resolve().parents[1] / "scripts/summarize_science_calibrations.py"
    spec = importlib.util.spec_from_file_location("science_calibration_summary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScienceCalibrationSummaryTests(unittest.TestCase):
    def test_default_reports_cover_all_normal_science_calibrations(self):
        module = load_summary_module()
        self.assertEqual(len(module.DEFAULT_REPORTS), 17)
        self.assertTrue(any("truss_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any("antenna_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any("nmr_v2_b3" in path for path in module.DEFAULT_REPORTS))
        self.assertTrue(any(
            "heat_exchanger_v2_b3" in path for path in module.DEFAULT_REPORTS
        ))
        self.assertFalse(any("blind" in path for path in module.DEFAULT_REPORTS))

    def test_scalar_metric_filter_rejects_nonfinite_and_omits_nested(self):
        from frontier_science.protocol import compact_scalar_metrics

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
        from frontier_science.protocol import compact_trajectory_snapshot

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


if __name__ == "__main__":
    unittest.main()
