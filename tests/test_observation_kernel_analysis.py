from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze_observation_kernels.py"
SPEC = importlib.util.spec_from_file_location("observation_kernel_analysis", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _event(step: int, time_seconds: float, score: float, valid: bool = True):
    return {
        "schema_version": 2,
        "step": step,
        "oracle_calls": step + 1,
        "budget_units": step + 1,
        "score": score,
        "best_score": score,
        "valid": valid,
        "accepted": valid,
        "wall_seconds": time_seconds,
        "cumulative_wall_seconds": time_seconds,
        "candidate_sha256": str(step),
        "parent_sha256": None if step == 0 else str(step - 1),
    }


class ObservationKernelAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            _event(0, 0.0, 0.0),
            _event(1, 10.0, 0.2),
            _event(2, 20.0, 0.8),
            _event(3, 90.0, 1.0),
        ]

    def test_periodic_kernel_retains_interval_censoring_and_missed_state(self):
        result = MODULE.replay_kernel(
            self.events, interval_seconds=60.0, horizon_seconds=120.0
        )
        self.assertEqual(result["missed_material_transition_count"], 1)
        rows = {row["event_step"]: row for row in result["material_event_intervals"]}
        self.assertEqual(rows[1]["left_open_seconds"], 0.0)
        self.assertEqual(rows[1]["right_closed_seconds"], 60.0)
        self.assertEqual(rows[1]["detection_delay_seconds"], 50.0)
        self.assertFalse(rows[1]["observed_as_distinct_state"])
        self.assertTrue(rows[2]["observed_as_distinct_state"])

    def test_dense_event_auc_exceeds_delayed_periodic_auc(self):
        dense = MODULE.replay_kernel(
            self.events, interval_seconds=None, horizon_seconds=120.0
        )
        periodic = MODULE.replay_kernel(
            self.events, interval_seconds=60.0, horizon_seconds=120.0
        )
        self.assertAlmostEqual(dense["wall_time_auc"], 88.0 / 120.0)
        self.assertAlmostEqual(periodic["wall_time_auc"], 0.4)
        self.assertLess(periodic["wall_time_auc"], dense["wall_time_auc"])
        self.assertEqual(dense["wall_time_ever_valid_auc"], 1.0)
        self.assertEqual(dense["wall_time_current_validity_auc"], 1.0)

    def test_phase_changes_detection_delay_without_changing_events(self):
        zero = MODULE.replay_kernel(
            self.events, interval_seconds=60.0, phase_seconds=0.0,
            horizon_seconds=120.0,
        )
        half = MODULE.replay_kernel(
            self.events, interval_seconds=60.0, phase_seconds=30.0,
            horizon_seconds=120.0,
        )
        self.assertEqual(
            zero["material_state_count_including_baseline"],
            half["material_state_count_including_baseline"],
        )
        self.assertNotEqual(
            zero["mean_detection_delay_seconds"],
            half["mean_detection_delay_seconds"],
        )

    def test_analyze_binds_input_and_marks_live_state_out_of_scope(self):
        with tempfile.TemporaryDirectory(dir=MODULE.ROOT) as tmp:
            path = Path(tmp) / "trajectory.jsonl"
            path.write_text(
                "\n".join(json.dumps(row) for row in self.events) + "\n",
                encoding="utf-8",
            )
            clean = {
                "git_available": True,
                "git_revision": "fixture",
                "source_tree_dirty": False,
                "source_changes": [],
                "source_scope": [],
                "command": [],
            }
            with patch.object(MODULE, "source_provenance", return_value=clean):
                report = MODULE.analyze(
                    [path], intervals=[60.0], horizon_seconds=120.0
                )
            self.assertTrue(report["trusted_evidence"])
            self.assertFalse(report["design"]["live_state_in_scope"])
            self.assertEqual(len(report["trajectories"][0]["kernels"]), 3)
            self.assertEqual(len(report["trajectories"][0]["trajectory_sha256"]), 64)
            self.assertEqual(
                report["trajectories"][0]["analysis_horizon_seconds"], 120.0
            )
            self.assertIsNone(report["rank_analysis"])

    def test_invalid_phase_and_short_horizon_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "phase"):
            MODULE.replay_kernel(
                self.events, interval_seconds=60.0, phase_seconds=60.0
            )
        with self.assertRaisesRegex(ValueError, "precede"):
            MODULE.replay_kernel(
                self.events, interval_seconds=60.0, horizon_seconds=80.0
            )
        shifted = [dict(row) for row in self.events]
        shifted[0]["cumulative_wall_seconds"] = 1.0
        with self.assertRaisesRegex(ValueError, "t=0"):
            MODULE.replay_kernel(shifted, interval_seconds=60.0)

    def test_invalid_baseline_retains_first_valid_interval(self):
        events = [
            _event(0, 0.0, 0.0, valid=False),
            _event(1, 20.0, 0.4),
            _event(2, 80.0, 0.7),
        ]
        result = MODULE.replay_kernel(
            events, interval_seconds=60.0, horizon_seconds=120.0
        )
        first = result["first_valid_event"]
        self.assertEqual(first["event_kind"], "first_valid")
        self.assertEqual(first["left_open_seconds"], 0.0)
        self.assertEqual(first["right_closed_seconds"], 60.0)
        self.assertEqual(result["post_first_valid_improvement_count"], 1)
        self.assertAlmostEqual(result["wall_time_ever_valid_auc"], 0.5)

    def test_fixed_grid_reports_missed_transient_invalid_state(self):
        events = [
            _event(0, 0.0, 0.0),
            _event(1, 20.0, 0.4),
            _event(2, 40.0, 0.4, valid=False),
            _event(3, 50.0, 0.7),
        ]
        # A best-so-far score is retained across the invalid proposal.
        events[2]["best_score"] = 0.4
        events[2]["accepted"] = False
        dense = MODULE.replay_kernel(
            events, interval_seconds=None, horizon_seconds=120.0
        )
        periodic = MODULE.replay_kernel(
            events, interval_seconds=60.0, horizon_seconds=120.0
        )
        self.assertEqual(dense["missed_current_event_state_count"], 0)
        self.assertIn(2, periodic["missed_current_event_steps"])
        self.assertLess(
            dense["wall_time_current_validity_auc"],
            dense["wall_time_ever_valid_auc"],
        )
        self.assertEqual(periodic["wall_time_current_validity_auc"], 1.0)

    def test_seeded_phase_is_reproducible_and_strictly_interior(self):
        first = MODULE._seeded_phase(60.0, 7)
        second = MODULE._seeded_phase(60.0, 7)
        other = MODULE._seeded_phase(60.0, 8)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertGreater(first, 0.0)
        self.assertLess(first, 60.0)

    def test_rank_analysis_is_explicit_and_detects_reversal(self):
        trajectories = [
            {
                "trajectory": "a",
                "kernels": [
                    {"kernel": "dense_event", "interval_seconds": None,
                     "phase_seconds": 0.0, "wall_time_auc": 0.8},
                    {"kernel": "fixed", "interval_seconds": 60.0,
                     "phase_seconds": 0.0, "wall_time_auc": 0.2},
                ],
            },
            {
                "trajectory": "b",
                "kernels": [
                    {"kernel": "dense_event", "interval_seconds": None,
                     "phase_seconds": 0.0, "wall_time_auc": 0.7},
                    {"kernel": "fixed", "interval_seconds": 60.0,
                     "phase_seconds": 0.0, "wall_time_auc": 0.5},
                ],
            },
        ]
        result = MODULE._ranking_analysis(trajectories)
        fixed = next(
            row for row in result["kernels"]
            if row["kernel_key"].startswith("fixed")
        )
        self.assertEqual(fixed["pairwise_rank_reversal_count_vs_dense"], 1)

    def test_rank_comparison_requires_common_explicit_horizon(self):
        with self.assertRaisesRegex(ValueError, "common horizon"):
            MODULE.analyze(
                [Path("does-not-matter"), Path("also-does-not-matter")],
                intervals=[60.0], compare_ranks=True,
            )

    def test_trusted_input_binding_checks_snapshot_hash(self):
        with tempfile.TemporaryDirectory(dir=MODULE.ROOT) as tmp:
            root = Path(tmp)
            workdir = root / "run"
            workdir.mkdir()
            trajectory = workdir / "trajectory.jsonl"
            trajectory.write_text(
                "\n".join(json.dumps(row) for row in self.events) + "\n",
                encoding="utf-8",
            )
            digest = MODULE._sha256(trajectory)
            report = root / "report.json"
            document = {
                "execution_passed": True,
                "trusted_evidence": True,
                "passed": True,
                "source_provenance": {
                    "source_tree_dirty": False,
                    "source_changes": [],
                    "git_revision": "fixture",
                },
                "runs": [{
                    "workdir": str(workdir),
                    "task": "D/T",
                    "algorithm": "fixture",
                    "feedback_mode": "normal",
                    "seed": 0,
                    "trajectory_snapshot": {
                        "trajectory_sha256": digest,
                        "events": [{}, {}, {}, {}],
                    },
                }],
            }
            report.write_text(json.dumps(document), encoding="utf-8")
            binding = MODULE._load_bound_trajectory(
                trajectory.resolve(), [report], True
            )
            self.assertEqual(binding["snapshot_trajectory_sha256"], digest)
            document["runs"][0]["trajectory_snapshot"]["trajectory_sha256"] = "bad"
            report.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs"):
                MODULE._load_bound_trajectory(
                    trajectory.resolve(), [report], True
                )

    def test_trusted_input_mode_requires_report(self):
        with self.assertRaisesRegex(ValueError, "binding report"):
            MODULE.analyze(
                [Path("does-not-matter")], require_trusted_inputs=True
            )


if __name__ == "__main__":
    unittest.main()
