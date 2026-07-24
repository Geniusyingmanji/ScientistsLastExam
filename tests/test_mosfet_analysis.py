from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_mosfet_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("mosfet_analysis_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load MOSFET analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, heldout, robustness, heldout_robustness):
    return {
        "combined_score": score,
        "valid": 1.0,
        "feasibility_rate": 1.0,
        "raw_score": score,
        "robustness_score": robustness,
        "heldout_policy_score": heldout,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": 1.0,
        "development_shift_feasibility_rate": 0.8,
        "heldout_shift_feasibility_rate": 0.75,
        "development_mean_nominal_feasible_rate": 0.9,
        "heldout_mean_nominal_feasible_rate": 0.85,
        "candidate_instance_call_count": 6,
        "candidate_instance_valid_rate": 1.0,
        "infrastructure_failure": False,
        "candidate_failure_kind": None,
    }


def _record(label, budget, mode, seed, scores, robustness):
    module = _module()
    baseline_metrics = _metrics(0.0, 0.0, 0.0, 0.0)
    events = [{
        "step": 0,
        "accepted": True,
        "valid": True,
        "score": 0.0,
        "best_score": 0.0,
        "candidate_sha256": "a" * 64,
        "parent_sha256": None,
        **baseline_metrics,
    }]
    best = 0.0
    incumbent = "a" * 64
    for index, score in enumerate(scores, 1):
        accepted = score > best
        candidate = chr(ord("a") + index) * 64
        parent = "a" * 64 if mode == "selection_blind" else incumbent
        metrics = _metrics(
            score, score * 0.9, robustness[index - 1],
            robustness[index - 1] * 0.9,
        )
        if accepted:
            best = score
            incumbent = candidate
        events.append({
            "step": index,
            "accepted": accepted,
            "valid": True,
            "score": score,
            "best_score": best,
            "candidate_sha256": candidate,
            "parent_sha256": parent,
            **metrics,
        })
    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: event["step"],
    )
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "1" * 64,
        "trajectory_sha256": "2" * 64,
        "run_manifest_sha256": "3" * 64,
        "source_revision": "4" * 40,
        "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "5" * 64,
        "model": "gpt-5.5",
        "server_side_seed_control": False,
        "feedback_mode": mode,
        "feedback_scope": "synthetic",
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": seed,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "budget_units": budget + 1,
        "llm_calls": budget,
        "provider_usage_records": budget,
        "total_tokens": budget * 100,
        "wall_seconds": float(budget * 10),
        "valid_rate": 1.0,
        "best_score": best,
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": {
            field: selected.get(field) for field in module.SCALAR_FIELDS
        },
        "selected_instance_axes": [],
        "best_program": "runs/example/best_program.py",
        "proposal_valid_count": budget,
        "proposal_failure_counts": {},
        "infrastructure_failure_count": 0,
        "valid_proposal_axes": [],
        "trajectory": events,
        "integrity_passed": True,
    }


def _records(low_outcome=False):
    if low_outcome:
        one_scores = [0.0]
        normal_scores = [0.0, 0.0, 0.0]
        blind_scores = [0.0, 0.0, 0.0]
        one_robustness = [0.0]
        three_robustness = [0.0, 0.0, 0.0]
    else:
        one_scores = [0.4]
        normal_scores = [0.3, 0.5, 0.7]
        blind_scores = [0.2, 0.6, 0.65]
        one_robustness = [0.2]
        three_robustness = [0.25, 0.20, 0.10]
    return {
        "budget_one": _record(
            "budget_one", 1, "normal", 0, one_scores, one_robustness,
        ),
        "normal_budget_three": _record(
            "normal_budget_three", 3, "normal", 1,
            normal_scores, three_robustness,
        ),
        "blind_budget_three": _record(
            "blind_budget_three", 3, "selection_blind", 1,
            blind_scores, three_robustness,
        ),
    }


class MOSFETAnalysisTests(unittest.TestCase):
    def test_integrity_gate_does_not_require_a_desired_model_result(self):
        module = _module()
        report = module._analyze_records(
            {"source_revision": "0" * 40},
            _records(low_outcome=True),
            runtime_source_equivalent=True,
            expected_model_source_revision="4" * 40,
        )
        self.assertTrue(report["execution_passed"])
        self.assertFalse(
            report["descriptive_findings"][
                "normal_budget_three_improves_visible_baseline"
            ]
        )
        self.assertFalse(
            report["descriptive_findings"]["feedback_necessity_identified"]
        )
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])

    def test_nominal_gain_with_robustness_loss_is_retained(self):
        module = _module()
        report = module._analyze_records(
            {"source_revision": "0" * 40},
            _records(),
            runtime_source_equivalent=True,
            expected_model_source_revision="4" * 40,
        )
        self.assertTrue(report["execution_passed"])
        transitions = report["accepted_transition_audit"][
            "normal_budget_three"
        ]
        self.assertTrue(any(
            row["nominal_improvement_with_development_robustness_regression"]
            for row in transitions
        ))

    def test_integrity_or_revision_failure_fails_closed(self):
        module = _module()
        records = _records()
        records["normal_budget_three"]["integrity_passed"] = False
        report = module._analyze_records(
            {"source_revision": "0" * 40}, records,
            runtime_source_equivalent=True,
            expected_model_source_revision="4" * 40,
        )
        self.assertFalse(report["execution_passed"])
        report = module._analyze_records(
            {"source_revision": "0" * 40}, _records(),
            runtime_source_equivalent=True,
            expected_model_source_revision="9" * 40,
        )
        self.assertFalse(report["execution_passed"])

    def test_full_analysis_when_preregistered_reports_exist(self):
        module = _module()
        if not all((ROOT / relative).is_file() for relative in module.REPORTS.values()):
            self.skipTest("preregistered MOSFET GPT-5.5 reports not generated")
        report = module.analyze()
        self.assertTrue(report["execution_passed"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertEqual(report["input_task_runtime_source_changes"], [])
        self.assertEqual(
            set(report["records"]),
            {"budget_one", "normal_budget_three", "blind_budget_three"},
        )
        self.assertTrue(all(
            record["integrity_passed"]
            for record in report["records"].values()
        ))
        self.assertTrue(all(
            len(record["selected_instance_axes"]) == 6
            for record in report["records"].values()
        ))


if __name__ == "__main__":
    unittest.main()
