from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_low_thrust_v2_calibrations.py"
BASELINE_HASH = "a" * 64


def _module():
    spec = importlib.util.spec_from_file_location("low_thrust_analysis_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, phase, heldout=1.0e-10):
    rows = []
    for index in range(6):
        split = "heldout" if index in {1, 4} else "development"
        rows.append({
            "name": "mission_%d" % index,
            "split": split,
            "valid": True,
            "nominal": {
                "mission_feasible": False,
                "maximum_scaled_terminal_error": 5.0 + index,
            },
            "shifted": [
                {"mission_feasible": False} for _ in range(3)
            ],
        })
    return {
        "combined_score": score,
        "valid": 1.0,
        "feasibility_rate": 0.0,
        "raw_score": score,
        "development_score": score,
        "robustness_score": score * 0.8,
        "development_validation_gap": score * 0.2,
        "heldout_policy_score": heldout,
        "heldout_robustness_score": heldout * 0.2,
        "heldout_artifact_valid_rate": 1.0,
        "development_mission_feasibility_rate": 0.0,
        "heldout_mission_feasibility_rate": 0.0,
        "development_shift_feasibility_rate": 0.0,
        "heldout_shift_feasibility_rate": 0.0,
        "mean_development_terminal_accuracy": score * 1.4,
        "mean_heldout_terminal_accuracy": heldout * 1.4,
        "mean_development_phase_score": phase,
        "mean_heldout_phase_score": phase / 2.0,
        "mean_development_delta_v_m_s": 800.0,
        "mean_heldout_delta_v_m_s": 1000.0,
        "per_instance": rows,
    }


def _event(step, parent, score, phase, accepted):
    metrics = _metrics(score, phase)
    return {
        "step": step,
        "score": score,
        "best_score": score,
        "accepted": accepted,
        "candidate_sha256": str(step + 1) * 64,
        "parent_sha256": parent,
        **{key: metrics[key] for key in metrics if key != "per_instance"},
        "mission_summary": {
            "instance_count": 6,
            "valid_instance_count": 6,
            "development_instance_count": 4,
            "heldout_instance_count": 2,
            "nominal_feasible_count": 0,
            "shifted_case_count": 18,
            "shifted_feasible_count": 0,
            "minimum_maximum_scaled_terminal_error": 5.0,
            "maximum_maximum_scaled_terminal_error": 10.0,
        },
    }


def _record(label, mode, budget, tokens, scores, phases, accepted):
    baseline = _event(0, None, 0.0, 0.1, True)
    baseline["candidate_sha256"] = BASELINE_HASH
    events = [baseline]
    incumbent = BASELINE_HASH
    for index, (score, phase, is_accepted) in enumerate(
        zip(scores, phases, accepted), 1
    ):
        parent = BASELINE_HASH if mode == "selection_blind" else incumbent
        event = _event(index, parent, score, phase, is_accepted)
        events.append(event)
        if mode != "selection_blind" and is_accepted:
            incumbent = event["candidate_sha256"]
    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: float(event["score"]),
    )
    return {
        "label": label,
        "source_revision": "f" * 40,
        "feedback_mode": mode,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "server_side_seed_control": False,
        "total_tokens": tokens,
        "best_score": float(selected["score"]),
        "selected_metrics": {
            key: selected[key]
            for key in _metrics(0.0, 0.0)
            if key != "per_instance"
        },
        "trajectory": events,
    }


def _fixtures():
    calibration = {
        "source_revision": "e" * 40,
        "integration_consistency": {
            "production_vs_refined_max_scaled_error": 0.042,
            "refined_vs_cartesian_max_scaled_error": 0.0028,
        },
        "public_gauss_newton_metrics": {
            **{
                key: value
                for key, value in _metrics(0.711, 1.0e-6, heldout=0.719).items()
                if key != "per_instance"
            },
            "robustness_score": 0.682,
            "heldout_robustness_score": 0.660,
            "development_mission_feasibility_rate": 1.0,
            "heldout_mission_feasibility_rate": 1.0,
        },
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", 1, 4598,
            [0.0077], [1.0e-8], [True],
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 18491,
            [0.0050, 0.0047, 2.0e-6], [0.24, 1.0e-4, 0.25],
            [True, False, False],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 13366,
            [0.0049, 0.0037, 0.0055], [1.0e-8, 0.36, 1.0e-4],
            [True, False, True],
        ),
    }
    return calibration, records


def _batch_document():
    raw_metrics = _metrics(0.0077, 1.0e-8)
    raw_events = [
        {
            "step": 0,
            "candidate_sha256": BASELINE_HASH,
            "parent_sha256": None,
            "metrics": _metrics(0.0, 0.1),
        },
        {
            "step": 1,
            "candidate_sha256": "b" * 64,
            "parent_sha256": BASELINE_HASH,
            "metrics": raw_metrics,
        },
    ]
    compact_events = [
        {
            "step": 0,
            "score": 0.0,
            "accepted": True,
            "candidate_sha256": BASELINE_HASH,
            "parent_sha256": None,
        },
        {
            "step": 1,
            "score": 0.0077,
            "accepted": True,
            "candidate_sha256": "b" * 64,
            "parent_sha256": BASELINE_HASH,
        },
    ]
    snapshot = {
        "schema_version": 1,
        "trajectory_sha256": "c" * 64,
        "events": compact_events,
    }
    document = {
        "trusted_evidence": True,
        "passed": True,
        "execution_passed": True,
        "source_provenance": {
            "source_tree_dirty": False,
            "git_revision": "d" * 40,
        },
        "config": {
            "budget": 1,
            "llm": {"model": "gpt-5.5", "server_side_seed_control": False},
        },
        "runs": [{
            "task": "Astrodynamics/LowThrustTransfer",
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
            "seed": 0,
            "best": 0.0077,
            "accepted": 1,
            "evaluated": 2,
            "error": None,
            "workdir": "/unused",
            "summary": {
                "oracle_calls": 2,
                "llm": {"total_tokens": 100},
                "feedback_scope": "synthetic test scope",
                "selection_policy": "online_incumbent",
            },
            "trajectory_snapshot": snapshot,
        }],
    }
    return document, snapshot, raw_events


class LowThrustCalibrationAnalysisTests(unittest.TestCase):
    def test_real_calibration_accepts_serialized_five_of_six_rate(self):
        module = _module()
        calibration = module._load_calibration(module.CALIBRATION)
        self.assertAlmostEqual(
            calibration["public_gauss_newton_metrics"][
                "heldout_shift_feasibility_rate"
            ],
            5.0 / 6.0,
        )

    def test_analysis_separates_axes_and_is_explicitly_noncausal(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertTrue(
            report["observed_model_proposal_pattern"]["all_terminal_infeasible"]
        )
        self.assertEqual(
            report["observed_model_proposal_pattern"][
                "nominal_terminal_feasible_proposal_count"
            ],
            0,
        )
        axes = report["science_axis_separation"]
        self.assertGreater(
            axes["public_gauss_newton"]["nominal_development_utility"], 0.70
        )
        self.assertEqual(
            axes["gpt55_normal_budget_three_selected"][
                "nominal_terminal_feasibility"
            ],
            0.0,
        )
        self.assertTrue(any("one run" in item for item in report["limitations"]))

    def test_source_lineage_or_terminal_feasibility_change_breaks_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(
            module._analyze_records(calibration, records, False)["execution_passed"]
        )
        calibration, records = _fixtures()
        records["blind_budget_three"]["trajectory"][2]["parent_sha256"] = "9" * 64
        self.assertFalse(
            module._analyze_records(calibration, records, True)["execution_passed"]
        )
        calibration, records = _fixtures()
        records["normal_budget_three"]["trajectory"][1][
            "development_mission_feasibility_rate"
        ] = 0.25
        self.assertFalse(
            module._analyze_records(calibration, records, True)["execution_passed"]
        )

    def test_loader_binds_report_and_raw_trajectory_hashes(self):
        module = _module()
        document, snapshot, raw_events = _batch_document()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            expected_report_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            with mock.patch.object(module, "ROOT", Path(temporary)), mock.patch.object(
                module, "compact_trajectory_snapshot", return_value=snapshot
            ), mock.patch.object(module, "load_trajectory", return_value=raw_events):
                record = module._load("budget_one", "report.json")
                self.assertEqual(record["report_sha256"], expected_report_hash)
                self.assertEqual(record["trajectory_sha256"], "c" * 64)

                changed = dict(snapshot)
                changed["trajectory_sha256"] = "0" * 64
                with mock.patch.object(
                    module, "compact_trajectory_snapshot", return_value=changed
                ):
                    with self.assertRaisesRegex(ValueError, "snapshot differs"):
                        module._load("budget_one", "report.json")


if __name__ == "__main__":
    unittest.main()
