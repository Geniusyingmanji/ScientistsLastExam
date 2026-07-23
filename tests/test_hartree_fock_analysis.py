from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_hartree_fock_v2_calibrations.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "hartree_fock_analysis_test", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(step, score, robustness, heldout_robustness, parent, accepted=True):
    candidate = (str((step + 1) % 10) * 64)
    return {
        "step": step,
        "accepted": accepted,
        "valid": True,
        "score": score,
        "best_score": score,
        "candidate_sha256": candidate,
        "parent_sha256": parent,
        "combined_score": score,
        "raw_score": 1.0,
        "heldout_policy_score": 1.0,
        "robustness_score": robustness,
        "heldout_robustness_score": heldout_robustness,
        "development_shifted_score": 1.0,
        "heldout_shifted_score": 1.0,
        "development_representation_invariance_score": robustness,
        "heldout_representation_invariance_score": heldout_robustness,
        "development_stability_rate": 1.0,
        "heldout_stability_rate": 1.0,
    }


def _record(label, mode, budget, seed, events, tokens=100):
    return {
        "label": label,
        "source_revision": (
            "746dff077a58e4c9a4afea821b5a3015d70cc378"
        ),
        "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "a" * 64,
        "model": "gpt-5.5",
        "server_side_seed_control": False,
        "feedback_mode": mode,
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": seed,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "valid_rate": 1.0,
        "best_score": events[-1]["score"],
        "selected_step": events[-1]["step"],
        "selected_metrics": {
            key: events[-1][key]
            for key in (
                "combined_score", "raw_score", "heldout_policy_score",
                "robustness_score", "heldout_robustness_score",
                "development_shifted_score", "heldout_shifted_score",
                "development_representation_invariance_score",
                "heldout_representation_invariance_score",
                "development_stability_rate", "heldout_stability_rate",
            )
        },
        "proposal_valid_count": budget,
        "infrastructure_failure_count": 0,
        "trajectory": events,
    }


def _calibration():
    return {
        "secure_vs_authoritative_direct_axis_comparison": {"passed": True}
    }


class HartreeFockCalibrationAnalysisTests(unittest.TestCase):
    def test_epsilon_audit_keeps_materially_different_predecessor(self):
        module = _module()
        baseline = _event(0, 0.0, 0.0, 2.0 / 3.0, None)
        step_two = _event(
            2, 0.9999999999998133, 0.9999999999998224,
            0.9023689270601761, baseline["candidate_sha256"],
        )
        step_three = _event(
            3, 0.9999999999998224, 0.7071067811863951,
            0.999999999999475, step_two["candidate_sha256"],
        )
        record = _record(
            "normal_budget_three", "normal", 3, 1,
            [baseline, _event(1, -1e18, 0.0, 0.0, baseline["candidate_sha256"], False),
             step_two, step_three],
        )
        record["trajectory"][1]["valid"] = False
        audit = module._material_acceptance_audit(record)
        self.assertTrue(audit["epsilon_changes_selected_artifact"])
        self.assertEqual(audit["epsilon_selected_step"], 2)
        self.assertLess(
            audit["strict_minus_epsilon_science_axes"]["robustness_score"],
            -0.25,
        )
        self.assertGreater(
            audit["strict_minus_epsilon_science_axes"][
                "heldout_robustness_score"
            ],
            0.05,
        )
        self.assertTrue(audit["scientifically_material_tradeoff"])

    def test_selection_blind_changed_parent_breaks_lineage(self):
        module = _module()
        baseline = _event(0, 0.0, 0.0, 2.0 / 3.0, None)
        proposal = _event(1, 1.0, 1.0, 1.0, "f" * 64)
        record = _record(
            "blind_budget_three", "selection_blind", 1, 1,
            [baseline, proposal],
        )
        self.assertFalse(module._lineage_is_valid(record))

    def test_full_descriptive_gate_rejects_causal_interpretation(self):
        module = _module()
        baseline = _event(0, 0.0, 0.0, 2.0 / 3.0, None)
        one = _record(
            "budget_one", "normal", 1, 0,
            [baseline, _event(1, 0.9999999999991, 0.9999999999998,
                              0.999999999998, baseline["candidate_sha256"])],
            50,
        )
        step_one = _event(1, -1e18, 0.0, 0.0, baseline["candidate_sha256"], False)
        step_one["valid"] = False
        step_two = _event(2, 0.9999999999998133, 0.9999999999998224,
                          0.9023689270601761, baseline["candidate_sha256"])
        step_three = _event(3, 0.9999999999998224, 0.7071067811863951,
                            0.999999999999475, step_two["candidate_sha256"])
        normal = _record(
            "normal_budget_three", "normal", 3, 1,
            [baseline, step_one, step_two, step_three], 200,
        )
        normal["proposal_valid_count"] = 2
        normal["infrastructure_failure_count"] = 1
        blind_events = [baseline]
        for step, score, robust, held in (
            (1, 0.9999999984, 0.707, 0.902),
            (2, 0.99999999995, 0.707, 0.902),
            (3, 0.9999999, 1.0, 2.0 / 3.0),
        ):
            blind_events.append(_event(
                step, score, robust, held, baseline["candidate_sha256"],
                accepted=step < 3,
            ))
        blind = _record(
            "blind_budget_three", "selection_blind", 3, 1,
            blind_events[:3], 170,
        )
        blind["proposal_valid_count"] = 3
        blind["oracle_calls"] = 4
        blind["proposal_budget"] = 3
        report = module._analyze_records(
            _calibration(), {
                "budget_one": one,
                "normal_budget_three": normal,
                "blind_budget_three": blind,
            }, True,
        )
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertTrue(
            report["descriptive_findings"][
                "feedback_not_shown_necessary_by_open_loop_calibration"
            ]
        )


if __name__ == "__main__":
    unittest.main()
