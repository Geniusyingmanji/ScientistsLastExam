from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_photovoltaic_tandem_calibrations.py"
SPEC = importlib.util.spec_from_file_location("photovoltaic_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _metrics(score, robust, heldout, heldout_robust, cost=0.999):
    result = {field: 1.0 for field in ANALYSIS.SCIENCE_FIELDS}
    result.update({
        "combined_score": score,
        "raw_score": score,
        "robustness_score": robust,
        "heldout_policy_score": heldout,
        "heldout_robustness_score": heldout_robust,
        "development_mean_cost_utilization": cost,
        "heldout_mean_cost_utilization": cost,
    })
    return result


def _event(step, score, metrics, valid=True, failure=None):
    return {
        "step": step,
        "score": score,
        "best_score": max(0.0, score),
        "valid": valid,
        "accepted": valid and score > 0.0,
        "candidate_sha256": str(step),
        "parent_sha256": None if step == 0 else "0",
        "failure_kind": failure,
        "infrastructure_failure": False,
        "science_metrics": metrics,
    }


def _record(label, mode, budget, selected, proposals, tokens):
    return {
        "label": label,
        "source_revision": "input",
        "source_scope": ["sle", "benchmarks"],
        "llm_condition_sha256": "condition",
        "task_contract_sha256": "contract",
        "runtime_source_sha256": "runtime",
        "feedback_mode": mode,
        "seed": 0 if label == "budget_one" else 1,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "best_score": selected["science_metrics"]["combined_score"],
        "best_so_far_auc": 0.5,
        "selected_metrics": selected["science_metrics"],
        "valid_proposal_count": sum(event["valid"] for event in proposals),
        "integrity_passed": True,
        "trajectory": [
            _event(0, 0.0, _metrics(0.0, 0.0, 0.0, 0.0))
        ] + proposals,
    }


class PhotovoltaicTandemAnalysisTests(unittest.TestCase):
    def test_analysis_separates_nominal_saturation_from_robustness(self):
        one_event = _event(1, 0.995, _metrics(0.995, 0.86, 0.994, 0.81))
        normal_event = _event(3, 0.994, _metrics(0.994, 0.83, 0.989, 0.81))
        blind_event = _event(1, 0.9999, _metrics(0.9999, 0.898, 0.9998, 0.825))
        records = {
            "budget_one": _record(
                "budget_one", "normal", 1, one_event, [one_event], 6000
            ),
            "normal_budget_three": _record(
                "normal_budget_three", "normal", 3, normal_event,
                [
                    _event(1, -1e18, _metrics(0.0, 0.0, 0.0, 0.0),
                           valid=False, failure="candidate_runtime_error"),
                    _event(2, 0.97, _metrics(0.97, 0.78, 0.97, 0.77)),
                    normal_event,
                ],
                20000,
            ),
            "blind_budget_three": _record(
                "blind_budget_three", "selection_blind", 3, blind_event,
                [
                    blind_event,
                    _event(2, -1e18, _metrics(0.0, 0.0, 0.0, 0.0),
                           valid=False, failure="candidate_runtime_error"),
                    _event(3, 0.94, _metrics(0.94, 0.12, 0.99, 0.81)),
                ],
                16000,
            ),
        }
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"}, records,
            runtime_source_equivalent=True,
            calibration_source_revision="calibration",
            model_source_revision="input",
        )
        self.assertTrue(report["execution_passed"], report)
        hurdle = report["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 5)
        self.assertEqual(hurdle["candidate_runtime_error_count"], 2)
        findings = report["descriptive_findings"]
        self.assertTrue(findings[
            "all_selected_artifacts_near_saturate_nominal_development"
        ])
        self.assertTrue(findings[
            "all_selected_artifacts_leave_sealed_robustness_headroom"
        ])
        self.assertFalse(findings["feedback_effect_identified"])

    def test_shortcut_scan_rejects_world_ids_and_evaluator_terms(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = Path(temporary) / "clean.py"
            clean.write_text(
                "def design_tandem(problem):\n    return problem['designs']\n",
                encoding="utf-8",
            )
            bad = Path(temporary) / "bad.py"
            bad.write_text(
                "def design_tandem(problem):\n"
                "    return '5101' if problem else 'verification'\n",
                encoding="utf-8",
            )
            self.assertTrue(ANALYSIS._shortcut_scan(clean)["passed"])
            scan = ANALYSIS._shortcut_scan(bad)
            self.assertFalse(scan["passed"])
            self.assertEqual(scan["fixed_world_literal_hits"], ["5101"])
            self.assertEqual(scan["evaluator_source_term_hits"], ["verification"])

    def test_runtime_source_change_fails_closed(self):
        one_event = _event(1, 0.995, _metrics(0.995, 0.86, 0.994, 0.81))
        records = {
            label: _record(label, "selection_blind" if label.startswith("blind")
                           else "normal", 1 if label == "budget_one" else 3,
                           one_event, [one_event] * (1 if label == "budget_one" else 3),
                           100)
            for label in (
                "budget_one", "normal_budget_three", "blind_budget_three"
            )
        }
        report = ANALYSIS._analyze_records(
            {"source_revision": "calibration"}, records,
            runtime_source_equivalent=False,
            runtime_source_changes=["benchmarks/Chemistry/PhotovoltaicTandemDesign/x.py"],
            calibration_source_revision="calibration",
            model_source_revision="input",
        )
        self.assertFalse(report["execution_passed"])


if __name__ == "__main__":
    unittest.main()
