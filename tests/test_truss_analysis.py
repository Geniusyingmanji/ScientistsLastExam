from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_truss_v2_calibrations.py"
BASELINE_HASH = "a" * 64


def _load_script():
    spec = importlib.util.spec_from_file_location("truss_analysis_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(step, score, heldout_robustness, parent, candidate, accepted=True):
    metrics = {
        "combined_score": score,
        "valid": 1.0,
        "robustness_score": score / 2.0,
        "heldout_policy_score": score / 3.0,
        "heldout_robustness_score": heldout_robustness,
        "mean_shifted_case_feasibility_rate": 0.75,
        "mean_shifted_constraint_feasibility_rate": 0.98,
    }
    return {
        "step": step,
        "oracle_calls": step + 1,
        "budget_units": step + 1,
        "score": score,
        "best_score": score,
        "valid": True,
        "accepted": accepted,
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "metrics": metrics,
        "algorithm_metadata": {},
        "error": None,
    }


def _document(mode="selection_blind", changed_parent=False):
    second_parent = "0" * 64 if changed_parent else BASELINE_HASH
    events = [
        _event(0, 0.0, 0.0, None, BASELINE_HASH),
        _event(1, 0.1, 0.4, second_parent, "b" * 64),
        _event(2, 0.2, 0.3, BASELINE_HASH, "c" * 64),
        _event(3, 0.3, 0.2, BASELINE_HASH, "d" * 64),
    ]
    snapshot = {"schema_version": 1, "trajectory_sha256": "e" * 64, "events": events}
    return {
        "trusted_evidence": True,
        "passed": True,
        "source_provenance": {
            "source_tree_dirty": False,
            "git_revision": "f" * 40,
        },
        "config": {
            "budget": 3,
            "llm": {"server_side_seed_control": False},
        },
        "runs": [{
            "task": "StructuralEngineering/TrussWeightMinimization",
            "algorithm": "greedy_rewrite",
            "feedback_mode": mode,
            "seed": 1,
            "best": 0.3,
            "accepted": 3,
            "evaluated": 4,
            "workdir": "/unused",
            "summary": {
                "oracle_calls": 4,
                "llm": {"total_tokens": 100},
                "feedback_scope": "synthetic test scope",
                "selection_policy": (
                    "offline_best_of_open_loop_batch"
                    if mode == "selection_blind" else "online_incumbent"
                ),
            },
            "trajectory_snapshot": snapshot,
        }],
    }, snapshot


def _record(label, best, heldout_robustness, budget, tokens, mode):
    prior_heldout = heldout_robustness + (0.1 if label == "normal_budget_three" else 0.0)
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "1" * 64,
        "trajectory_sha256": "2" * 64,
        "source_revision": "3" * 40,
        "feedback_mode": mode,
        "feedback_scope": "synthetic test scope",
        "seed": 1,
        "proposal_budget": budget,
        "server_side_seed_control": False,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "best_score": best,
        "selected_step": budget,
        "selected_candidate_sha256": "4" * 64,
        "selected_metrics": {
            "combined_score": best,
            "robustness_score": best / 2.0,
            "heldout_policy_score": best / 3.0,
            "heldout_robustness_score": heldout_robustness,
            "mean_shifted_case_feasibility_rate": 0.75,
            "mean_shifted_constraint_feasibility_rate": 0.98,
        },
        "trajectory": [
            {
                "step": budget - 1,
                "combined_score": best - 0.1,
                "heldout_policy_score": best / 3.0 - 0.1,
                "heldout_robustness_score": prior_heldout,
            },
            {
                "step": budget,
                "combined_score": best,
                "heldout_policy_score": best / 3.0,
                "heldout_robustness_score": heldout_robustness,
            },
        ],
    }


class TrussCalibrationAnalysisTests(unittest.TestCase):
    def test_record_analysis_is_noncausal_and_detects_divergence(self):
        module = _load_script()
        records = {
            "budget_one": _record("budget_one", 0.0, 0.0, 1, 40, "normal"),
            "normal_budget_three": _record(
                "normal_budget_three", 0.6, 0.1, 3, 200, "normal"
            ),
            "blind_budget_three": _record(
                "blind_budget_three", 0.1, 0.4, 3, 120, "selection_blind"
            ),
        }
        report = module._analyze_records(records)
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["evidence_scope"],
            "TRUSS_HEADROOM_DIAGNOSTIC_NOT_CAUSAL_OR_POPULATION_EVIDENCE",
        )
        self.assertGreater(
            report["normal_minus_blind_selected_contrast"]["combined_score"], 0.0
        )
        self.assertLess(
            report["within_normal_final_accepted_change"][
                "heldout_robustness_score"
            ],
            0.0,
        )

    def test_blind_parent_change_is_rejected(self):
        module = _load_script()
        document, snapshot = _document(changed_parent=True)
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / "report.json"
            fake.write_text(json.dumps(document), encoding="utf-8")
            with mock.patch.object(module, "ROOT", Path(temporary)), mock.patch.object(
                module, "compact_trajectory_snapshot", return_value=snapshot
            ):
                with self.assertRaisesRegex(ValueError, "changed parent"):
                    module._load("blind_budget_three", "report.json")


if __name__ == "__main__":
    unittest.main()
