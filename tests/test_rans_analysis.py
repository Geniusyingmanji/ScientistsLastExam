from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_rans_v2_calibrations.py"


def _module():
    spec = importlib.util.spec_from_file_location("rans_analysis_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load RANS analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, heldout, robustness, heldout_robustness, loss):
    return {
        "combined_score": score,
        "valid": 1.0,
        "feasibility_rate": 1.0,
        "raw_score": score,
        "robustness_score": robustness,
        "heldout_policy_score": heldout,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": 1.0,
        "development_raw_loss": loss,
        "heldout_raw_loss": loss * 0.9,
        "development_worst_shift_loss": loss * 1.1,
        "heldout_worst_shift_loss": loss,
        "development_velocity_rmse_plus": 0.2,
        "heldout_velocity_rmse_plus": 0.2,
        "development_reynolds_shear_rmse_plus": 0.01,
        "heldout_reynolds_shear_rmse_plus": 0.01,
        "candidate_parameter_count": 4,
        "physics_gate_passed": True,
        "candidate_failure_kind": None,
    }


def _record(label, mode, budget, scores, tokens=1000):
    module = _module()
    baseline_hash = "a" * 64
    baseline_metrics = _metrics(0.0, 0.0, 0.0, 0.0, 1.0)
    events = [{
        "step": 0, "accepted": True, "valid": True,
        "score": 0.0, "best_score": 0.0,
        "candidate_sha256": baseline_hash, "parent_sha256": None,
        "candidate_parameter_vector": [0.41, 26.0, 0.0, 0.0],
        **baseline_metrics,
    }]
    best = 0.0
    incumbent = baseline_hash
    for index, score in enumerate(scores, 1):
        candidate = chr(ord("a") + index) * 64
        accepted = score > best
        parent = baseline_hash if mode == "selection_blind" else incumbent
        metrics = _metrics(
            score, score * 1.1, score * 0.4, score * 0.6,
            max(0.2, 1.0 - score),
        )
        if accepted:
            best = score
            if mode != "selection_blind":
                incumbent = candidate
        events.append({
            "step": index, "accepted": accepted, "valid": True,
            "score": score, "best_score": best,
            "candidate_sha256": candidate, "parent_sha256": parent,
            "candidate_parameter_vector": [0.41 + index / 100, 26.0, 0.0, 0.0],
            **metrics,
        })
    selected = min(
        (event for event in events if event["accepted"] and event["score"] == best),
        key=lambda event: event["step"],
    )
    return {
        "label": label,
        "source_revision": "4" * 40,
        "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "5" * 64,
        "model": "gpt-5.5",
        "server_side_seed_control": False,
        "feedback_mode": mode,
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": 1,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "budget_units": budget + 1,
        "llm_calls": budget,
        "provider_usage_records": budget,
        "total_tokens": tokens,
        "wall_seconds": float(budget),
        "best_score": best,
        "selected_step": selected["step"],
        "selected_candidate_sha256": selected["candidate_sha256"],
        "selected_metrics": {
            field: selected.get(field) for field in module.SCALAR_FIELDS
        },
        "selected_parameters": selected["candidate_parameter_vector"],
        "terminal_proposal_sha256": events[-1]["candidate_sha256"],
        "terminal_proposal_score": events[-1]["score"],
        "terminal_differs_from_selected": (
            events[-1]["candidate_sha256"] != selected["candidate_sha256"]
        ),
        "trajectory": events,
        "integrity_passed": True,
    }


def _records(low=False):
    if low:
        one = [0.0]
        normal = blind = [0.0, 0.0, 0.0]
    else:
        one = [0.0]
        normal = [0.0, 0.35, 0.0]
        blind = [0.0, 0.0, 0.0]
    return {
        "budget_one": _record("budget_one", "normal", 1, one, 500),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, normal, 900
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, blind, 1000
        ),
    }


class RANSAnalysisTests(unittest.TestCase):
    def test_runtime_scope_excludes_task_card_bibliography(self):
        module = _module()
        self.assertNotIn(
            "benchmarks/Turbulence/RANSCalibration/TASK_CARD.yaml",
            module.TASK_RUNTIME_SCOPE,
        )
        changed = subprocess.check_output(
            [
                "git", "diff", "--name-only",
                module.EXPECTED_MODEL_SOURCE_REVISION, "HEAD", "--",
                *module.TASK_RUNTIME_SCOPE,
            ],
            cwd=ROOT,
            text=True,
        ).splitlines()
        self.assertEqual(
            changed,
            ["frontier_science/evaluate.py", "frontier_science/secure_eval.py"],
        )

    def test_integrity_gate_does_not_require_desired_model_outcome(self):
        module = _module()
        report = module._analyze_records(
            {"source_revision": "0" * 40}, _records(low=True),
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

    def test_analysis_retains_transfer_robustness_and_rollback(self):
        module = _module()
        report = module._analyze_records(
            {"source_revision": "0" * 40}, _records(),
            runtime_source_equivalent=True,
            expected_model_source_revision="4" * 40,
        )
        self.assertTrue(report["execution_passed"])
        findings = report["descriptive_findings"]
        self.assertTrue(findings["normal_selected_transfers_above_development_score"])
        self.assertTrue(findings["normal_selected_robustness_below_nominal_on_both_splits"])
        self.assertTrue(findings["normal_has_rejected_regression_after_improvement"])
        self.assertTrue(findings["normal_rollback_preserves_selected_incumbent"])

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

    def test_real_reports_are_bound_and_source_equivalent(self):
        module = _module()
        if not all((ROOT / path).is_file() for path in module.REPORTS.values()):
            self.skipTest("RANS GPT-5.5 reports have not been generated")
        report = module.analyze()
        self.assertTrue(report["execution_passed"])
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertEqual(
            report["input_task_runtime_source_changes"],
            ["frontier_science/evaluate.py", "frontier_science/secure_eval.py"],
        )
        self.assertTrue(
            report["input_task_runtime_source_migration"]["accepted"]
        )
        self.assertTrue(all(
            record["integrity_passed"]
            for record in report["records"].values()
        ))


if __name__ == "__main__":
    unittest.main()
