from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_distillation_v2_calibrations.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "distillation_analysis_test", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split(score, robustness, shift_rate, count):
    return {
        "instance_count": count,
        "nominal_visible_score": score,
        "sealed_robustness_score": robustness,
        "nominal_feasibility_rate": 1.0,
        "sealed_shift_feasibility_rate": shift_rate,
        "mean_nominal_annualized_cost": 1.0,
        "minimum_nominal_constraint_margin": 0.001,
        "designs": [],
        "shift_diagnostics": {
            name: {"feasibility_rate": 1.0 if name == "richer_feed" else 0.0}
            for name in (
                "lower_relative_volatility", "richer_feed",
                "leaner_feed_quality_shift", "reflux_derating",
                "combined_operating_shift",
            )
        },
    }


def _record(label, budget, seed, mode, score, heldout, valid_count,
            timeout_count, tokens, selected_step):
    baseline = "a" * 64
    events = [{
        "step": 0, "accepted": True, "valid": True,
        "candidate_sha256": baseline, "parent_sha256": None,
        "candidate_failure_kind": None,
    }]
    parent = baseline
    for step in range(1, budget + 1):
        valid = step == selected_step and selected_step > 0
        accepted = valid
        candidate = (str(step % 10) * 64)
        events.append({
            "step": step,
            "accepted": accepted,
            "valid": valid,
            "candidate_sha256": candidate,
            "parent_sha256": baseline if mode == "selection_blind" else parent,
            "candidate_failure_kind": (
                None if valid else "candidate_timeout"
            ),
        })
        if accepted and mode != "selection_blind":
            parent = candidate
    return {
        "label": label,
        "source_revision": "b" * 40,
        "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "c" * 64,
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
        "best_score": score,
        "selected_step": selected_step,
        "proposal_valid_count": valid_count,
        "proposal_failure_counts": {"candidate_timeout": timeout_count},
        "selected_axes": {
            "development": _split(
                score, 0.0, 0.2 if selected_step else 1.0, 4
            ),
            "heldout": _split(
                heldout, 0.0, 0.2 if selected_step else 1.0, 2
            ),
        },
        "trajectory": events,
    }


def _cost_probe():
    return {
        "candidate_design_identical_across_cost_regimes": True,
        "candidate_reference_cost_ranking_reverses": True,
        "all_candidate_and_reference_designs_feasible": True,
        "source_mentions_public_tray_cost_field": False,
        "source_mentions_public_vapour_cost_field": False,
    }


class DistillationAnalysisTests(unittest.TestCase):
    def test_analysis_separates_nominal_robustness_and_cost_mechanism(self):
        module = _module()
        records = {
            "budget_one": _record(
                "budget_one", 1, 0, "normal", 0.0, 0.0, 0, 1, 6000, 0
            ),
            "normal_budget_three": _record(
                "normal_budget_three", 3, 1, "normal", 0.613, 0.541,
                1, 2, 21738, 2,
            ),
            "blind_budget_three": _record(
                "blind_budget_three", 3, 1, "selection_blind", 0.0,
                0.0, 0, 3, 17926, 0,
            ),
        }
        report = module._analyze_records(
            {"source_revision": "d" * 40}, records, _cost_probe(), True
        )
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["observed_proposal_pattern"]["valid_proposal_count"], 1
        )
        self.assertEqual(
            report["science_axis_separation"]["sealed_operating_robustness"][
                "development_score"
            ],
            0.0,
        )
        self.assertTrue(
            report["descriptive_findings"][
                "selected_program_is_not_cost_responsive_in_post_hoc_probe"
            ]
        )
        self.assertNotEqual(
            report["normal_minus_blind_diagnostic"]["total_tokens"], 0
        )

    def test_changed_blind_parent_breaks_lineage(self):
        module = _module()
        record = _record(
            "blind_budget_three", 3, 1, "selection_blind", 0.0,
            0.0, 0, 3, 100, 0,
        )
        record["trajectory"][2]["parent_sha256"] = "f" * 64
        self.assertFalse(module._lineage_is_valid(record))

    def test_cost_responsiveness_change_breaks_observed_gate(self):
        module = _module()
        records = {
            "budget_one": _record(
                "budget_one", 1, 0, "normal", 0.0, 0.0, 0, 1, 6000, 0
            ),
            "normal_budget_three": _record(
                "normal_budget_three", 3, 1, "normal", 0.613, 0.541,
                1, 2, 21738, 2,
            ),
            "blind_budget_three": _record(
                "blind_budget_three", 3, 1, "selection_blind", 0.0,
                0.0, 0, 3, 17926, 0,
            ),
        }
        probe = _cost_probe()
        probe["candidate_design_identical_across_cost_regimes"] = False
        report = module._analyze_records(
            {"source_revision": "d" * 40}, records, probe, True
        )
        self.assertFalse(report["execution_passed"])


if __name__ == "__main__":
    unittest.main()
