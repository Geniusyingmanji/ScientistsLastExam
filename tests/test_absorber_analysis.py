from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_absorber_v2_calibrations.py"
BASELINE_HASH = "a" * 64


def _module():
    spec = importlib.util.spec_from_file_location("absorber_analysis_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _axes(score, heldout, robustness, heldout_robustness, manufacturing):
    def split(nominal, robust):
        return {
            "instance_count": 4,
            "nominal_visible_score": nominal,
            "sealed_robustness_score": robust,
            "robustness_retention_ratio": robust / nominal if nominal else None,
            "exact_distributed_model_utility": nominal / 2.0,
            "public_proxy_utility": nominal / 10.0,
            "proxy_minus_distributed_utility": -0.4 * nominal,
            "mean_absorption": nominal / 2.0,
            "twentieth_percentile_absorption": nominal / 3.0,
            "coverage_above_half": nominal / 2.0,
            "artifact_feasibility_rate": 1.0,
            "mean_worst_shift_utility": robust / 2.0,
            "mean_all_shift_geometry_feasibility_rate": manufacturing,
            "manufacturing_shift_geometry_feasibility_rate": manufacturing,
            "manufacturing_geometry_failures": (
                [] if manufacturing == 1.0
                else [{"instance": "synthetic", "shift": "manufacturing_pattern_a"}]
            ),
        }

    development = split(score, robustness)
    held = split(heldout, heldout_robustness)
    held["instance_count"] = 2
    return {
        "development": development,
        "heldout": held,
        "development_nominal_minus_robustness_score": score - robustness,
    }


def _record(label, budget, seed, mode, score, heldout, robustness,
            heldout_robustness, manufacturing, tokens, step):
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "1" * 64,
        "trajectory_sha256": "2" * 64,
        "source_revision": "3e4333a0ec9eab13d644f368886749bc3ca2fe7f",
        "source_scope": ["sle", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "3" * 64,
        "model": "gpt-5.5",
        "server_side_seed_control": False,
        "feedback_mode": mode,
        "feedback_scope": "synthetic sealed scope",
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": seed,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "best_score": score,
        "selected_step": step,
        "selected_candidate_sha256": "4" * 64,
        "selected_artifact_valid": True,
        "selected_axes": _axes(
            score, heldout, robustness, heldout_robustness, manufacturing
        ),
        "proposal_valid_count": 1 if budget == 3 else 0,
        "proposal_valid_rate": 1.0 / 3.0 if budget == 3 else 0.0,
        "proposal_failure_counts": {"candidate_timeout": budget - 1},
        "trajectory": [],
    }


def _event(step, candidate, parent, accepted=True):
    return {
        "step": step,
        "oracle_calls": step + 1,
        "budget_units": step + 1,
        "score": float(step),
        "best_score": float(step),
        "valid": True,
        "accepted": accepted,
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "metrics": {"valid": 1.0},
        "llm": {},
        "algorithm_metadata": {},
        "error": None,
    }


class AbsorberCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_separates_visible_score_from_sealed_robustness(self):
        module = _module()
        records = {
            "budget_one": _record(
                "budget_one", 1, 0, "normal", 0.0, 0.0, 0.0, 0.0,
                1.0, 50, 0,
            ),
            "normal_budget_three": _record(
                "normal_budget_three", 3, 1, "normal", 0.915, 0.86,
                0.912, 0.858, 1.0, 240, 1,
            ),
            "blind_budget_three": _record(
                "blind_budget_three", 3, 1, "selection_blind", 0.917, 0.96,
                0.452, 0.449, 0.75, 150, 2,
            ),
        }
        report = module._analyze_records(records)
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["evidence_scope"],
            "ABSORBER_SINGLE_RUN_CALIBRATION_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        )
        contrast = report["normal_minus_blind_selected_contrast"]
        self.assertLess(contrast["development_nominal_visible_score"], 0.0)
        self.assertGreater(contrast["development_sealed_robustness_score"], 0.4)
        self.assertGreater(
            contrast["development_manufacturing_geometry_feasibility_rate"],
            0.0,
        )
        self.assertEqual(contrast["oracle_calls"], 0)
        self.assertTrue(
            report["descriptive_findings"]["near_equal_visible_development_scores"]
        )

    def test_blind_parent_change_is_rejected(self):
        module = _module()
        baseline_bytes = b"baseline"
        baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()
        proposal_hash = "b" * 64
        events = [
            _event(0, baseline_hash, None),
            _event(1, proposal_hash, "0" * 64, accepted=False),
        ]
        snapshot = {
            "schema_version": 1,
            "trajectory_sha256": "c" * 64,
            "events": events,
        }
        document = {
            "trusted_evidence": True,
            "passed": True,
            "source_provenance": {
                "source_tree_dirty": False,
                "source_changes": [],
                "git_revision": "3e4333a0ec9eab13d644f368886749bc3ca2fe7f",
                "source_scope": ["sle", "scripts", "tests", "benchmarks"],
            },
            "config": {
                "budget": 1,
                "llm_condition_sha256": "d" * 64,
                "llm": {"model": "gpt-5.5", "server_side_seed_control": False},
            },
            "runs": [{
                "task": "AcousticMetamaterials/BroadbandAbsorber",
                "algorithm": "greedy_rewrite",
                "feedback_mode": "selection_blind",
                "seed": 1,
                "best": 0.0,
                "evaluated": 2,
                "workdir": "/unused",
                "summary": {
                    "oracle_calls": 2,
                    "selection_policy": "offline_best_of_open_loop_batch",
                    "feedback_scope": "synthetic",
                    "llm": {"total_tokens": 1},
                },
                "trajectory_snapshot": snapshot,
            }],
        }
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            report = temporary_path / "report.json"
            report.write_text(json.dumps(document), encoding="utf-8")
            with mock.patch.object(module, "ROOT", temporary_path), mock.patch.object(
                module, "load_trajectory", return_value=events
            ), mock.patch.object(
                module, "compact_trajectory_snapshot", return_value=snapshot
            ):
                with self.assertRaisesRegex(ValueError, "changed frozen parent"):
                    module._load("blind_budget_three", "report.json")


if __name__ == "__main__":
    unittest.main()
