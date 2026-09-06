from __future__ import annotations

import importlib.util
import copy
import tempfile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.repo_paths import run_workdir_is_present  # noqa: E402
SCRIPT = ROOT / "scripts/analyze_force_field_hypothesis_calibrations.py"
SPEC = importlib.util.spec_from_file_location("force_field_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _metrics():
    result = {field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS}
    result.update({
        "combined_score": 0.0,
        "raw_score": 0.0,
        "feasibility_rate": 1.0,
        "heldout_feasibility_rate": 1.0,
        "development_lineage_score": 1.0,
        "heldout_lineage_score": 1.0,
        "development_acquisition_score": 0.35,
        "heldout_acquisition_score": 0.34,
        "development_information_gain": 0.32,
        "heldout_information_gain": 0.30,
        "development_design_coverage": 0.39,
        "heldout_design_coverage": 0.39,
        "development_hypothesis_score": 0.37,
        "heldout_hypothesis_score": 0.52,
        "development_true_hypothesis_retention_rate": 5.0 / 7.0,
        "heldout_true_hypothesis_retention_rate": 0.8,
        "development_premature_elimination_rate": 4.0 / 7.0,
        "heldout_premature_elimination_rate": 0.4,
        "development_model_selection_score": 3.0 / 7.0,
        "heldout_model_selection_score": 0.6,
        "development_confidence_score": 4.0 / 7.0,
        "heldout_confidence_score": 0.4,
        "development_supported_claim_coverage": 0.0,
        "heldout_supported_claim_coverage": 0.0,
        "development_supported_correct_model_rate": 0.0,
        "heldout_supported_correct_model_rate": 0.0,
        "development_unsupported_refusal_rate": 1.0,
        "heldout_unsupported_refusal_rate": 1.0,
        "development_false_discovery_rate": 0.0,
        "heldout_false_discovery_rate": 0.0,
        "development_mean_query_calls": 1.0,
        "heldout_mean_query_calls": 1.0,
        "development_mean_query_budget_units": 1.0,
        "heldout_mean_query_budget_units": 1.0,
        "development_reference_policy_score": 0.98,
        "heldout_reference_policy_score": 0.98,
        "development_oracle_clean_score": 1.0,
        "heldout_oracle_clean_score": 1.0,
        "candidate_instance_call_count": 12.0,
        "candidate_instance_valid_rate": 1.0,
    })
    return result


def _baseline_event():
    return {
        "step": 0,
        "oracle_calls": 1,
        "budget_units": 1,
        "score": 0.0,
        "best_score": 0.0,
        "valid": True,
        "accepted": True,
        "candidate_sha256": ANALYSIS.BASELINE_SHA256,
        "parent_sha256": None,
        "failure_kind": None,
        "infrastructure_failure": False,
        "science_metrics": _metrics(),
        "world_metrics": [{}] * 12,
        "valid_world_count": 12,
        "invalid_world_count": 0,
        "llm": {},
        "algorithm_metadata": {},
    }


def _proposal(label, step, failure):
    full_world = failure == "invalid_submission"
    candidate = __import__("hashlib").sha256(
        (label + ":" + str(step)).encode("utf-8")
    ).hexdigest()
    return {
        "step": step,
        "oracle_calls": step + 1,
        "budget_units": step + 1,
        "score": 0.0 if full_world else -1.0e18,
        "best_score": 0.0,
        "valid": False,
        "accepted": False,
        "candidate_sha256": candidate,
        "parent_sha256": ANALYSIS.BASELINE_SHA256,
        "failure_kind": failure,
        "infrastructure_failure": False,
        "science_metrics": ({
            **{field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS},
            "candidate_instance_call_count": 12.0,
            "candidate_instance_valid_rate": 0.0,
        } if full_world else {
            field: None for field in ANALYSIS.SCIENCE_FIELDS
        }),
        "world_metrics": (
            [{"failure_kind": "invalid_submission"}] * 12
            if full_world else []
        ),
        "valid_world_count": 0,
        "invalid_world_count": 12 if full_world else 0,
        "llm": {},
        "algorithm_metadata": {},
    }


def _record(label, mode, failures, tokens, missing_imports=None):
    events = [_baseline_event()] + [
        _proposal(label, step, failure)
        for step, failure in enumerate(failures, 1)
    ]
    counts = {}
    for failure in failures:
        counts[failure] = counts.get(failure, 0) + 1
    terminal_hash = events[-1]["candidate_sha256"]
    scan = {
        "source_sha256": terminal_hash,
        "syntax_valid": True,
        "syntax_error": None,
        "fixed_world_literal_hits": [],
        "evaluator_source_term_hits": [],
        "dynamic_source_import_hits": [],
        "dynamic_source_call_hits": [],
        "known_missing_import_symbols": missing_imports or [],
        "shortcut_safe": True,
    }
    best_scan = dict(scan)
    best_scan["source_sha256"] = ANALYSIS.BASELINE_SHA256
    budget = len(failures)
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "a" * 64,
        "source_revision": ANALYSIS.INPUT_SOURCE_REVISION,
        "source_scope": ["sle", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "b" * 64,
        "model": "gpt-5.5",
        "server_side_seed_control": False,
        "feedback_mode": mode,
        "feedback_scope": "synthetic",
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": 0 if label == "budget_one" else 1,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "budget_units": budget + 1,
        "llm_calls": budget,
        "provider_usage_records": budget,
        "input_tokens": 2263 if budget == 1 else 6789,
        "output_tokens": tokens - (2263 if budget == 1 else 6789),
        "total_tokens": tokens,
        "wall_seconds": float(tokens / 100.0),
        "baseline_score": 0.0,
        "best_score": 0.0,
        "best_so_far_auc": 0.0,
        "accepted_proposals": 0,
        "trajectory_sha256": "c" * 64,
        "run_manifest_sha256": "d" * 64,
        "checkpoint_sha256": "e" * 64,
        "summary_sha256": "f" * 64,
        "task_contract_sha256": "1" * 64,
        "runtime_source_sha256": "2" * 64,
        "trusted_evaluator_runtime_sha256": "9" * 64,
        "baseline_candidate_sha256": ANALYSIS.BASELINE_SHA256,
        "best_program": "runs/example/best_program.py",
        "best_program_sha256": ANALYSIS.BASELINE_SHA256,
        "terminal_program": "runs/example/solution.py",
        "terminal_program_sha256": terminal_hash,
        "checkpoint_best_program_sha256": ANALYSIS.BASELINE_SHA256,
        "selected_step": 0,
        "selected_origin": "baseline",
        "selected_candidate_sha256": ANALYSIS.BASELINE_SHA256,
        "selected_metrics": events[0]["science_metrics"],
        "terminal_candidate_sha256": terminal_hash,
        "proposal_count": budget,
        "valid_proposal_count": 0,
        "invalid_proposal_count": budget,
        "failure_counts": counts,
        "infrastructure_failure_count": 0,
        "trajectory": events,
        "retained_artifact_scans": {
            "best_program": best_scan,
            "terminal_program": scan,
        },
        "artifact_retention_scope": "synthetic",
        "integrity_passed": True,
    }


def _records():
    return {
        "budget_one": _record(
            "budget_one", "normal", ["invalid_submission"], 7020
        ),
        "normal_budget_three": _record(
            "normal_budget_three",
            "normal",
            ["candidate_runtime_error"] * 3,
            21309,
        ),
        "blind_budget_three": _record(
            "blind_budget_three",
            "selection_blind",
            [
                "candidate_runtime_error",
                "candidate_runtime_error",
                "blocked_or_missing_import",
            ],
            21952,
            ["scipy.optimize.quad"],
        ),
    }


def _calibration():
    baseline = _metrics()
    reference = dict(baseline)
    reference.update({
        "combined_score": 0.96417825,
        "heldout_policy_score": 0.949851,
        "robustness_score": 0.96429,
        "heldout_robustness_score": 0.949894,
        "development_supported_claim_coverage": 1.0,
        "heldout_supported_claim_coverage": 1.0,
        "development_supported_correct_model_rate": 1.0,
        "heldout_supported_correct_model_rate": 1.0,
        "development_unsupported_refusal_rate": 1.0,
        "heldout_unsupported_refusal_rate": 1.0,
        "development_false_discovery_rate": 0.0,
        "heldout_false_discovery_rate": 0.0,
        "development_interval_coverage": 1.0,
        "heldout_interval_coverage": 1.0,
    })
    return {
        "source_revision": ANALYSIS.INPUT_SOURCE_REVISION,
        "weak_baseline": baseline,
        "truth_blind_reference": reference,
    }


class ForceFieldHypothesisAnalysisTests(unittest.TestCase):
    def report(self, **kwargs):
        return ANALYSIS._analyze_records(
            _calibration(),
            _records(),
            runtime_source_equivalent=kwargs.get(
                "runtime_source_equivalent", True
            ),
            runtime_source_changes=kwargs.get("runtime_source_changes", []),
        )

    def test_failure_hurdle_is_exact_and_not_infrastructure(self):
        report = self.report()
        self.assertTrue(report["input_trusted_evaluator_runtime_equivalent"])
        self.assertTrue(report["execution_passed"], report)
        hurdle = report["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 0)
        self.assertEqual(hurdle["invalid_proposal_count"], 7)
        self.assertEqual(hurdle["failure_counts"], {
            "blocked_or_missing_import": 1,
            "candidate_runtime_error": 5,
            "invalid_submission": 1,
        })
        self.assertEqual(hurdle["full_world_invalid_submission_count"], 1)
        self.assertEqual(hurdle["infrastructure_failure_count"], 0)

    def test_retained_and_unretained_proposal_scope(self):
        retained = self.report()["retained_artifact_summary"]
        self.assertEqual(retained["retained_proposal_source_count"], 3)
        self.assertEqual(retained["unretained_proposal_source_count"], 4)
        self.assertTrue(retained["all_retained_sources_parse"])
        self.assertTrue(retained["all_retained_shortcut_scans_passed"])
        self.assertEqual(
            retained["terminal_known_missing_import_symbols"][
                "blind_budget_three"
            ],
            ["scipy.optimize.quad"],
        )

    def test_lineage_distinguishes_online_and_frozen_parent(self):
        records = _records()
        self.assertTrue(ANALYSIS._lineage_is_valid(
            records["normal_budget_three"]
        ))
        self.assertTrue(ANALYSIS._lineage_is_valid(
            records["blind_budget_three"]
        ))
        records["blind_budget_three"]["trajectory"][2][
            "parent_sha256"
        ] = records["blind_budget_three"]["trajectory"][1][
            "candidate_sha256"
        ]
        self.assertFalse(ANALYSIS._lineage_is_valid(
            records["blind_budget_three"]
        ))

    def test_contrast_is_descriptive_not_causal(self):
        report = self.report()
        contrast = report[
            "normal_minus_blind_budget_three_descriptive_contrast"
        ]
        self.assertEqual(contrast["best_score"], 0.0)
        self.assertEqual(contrast["oracle_calls"], 0)
        self.assertEqual(contrast["input_tokens"], 0)
        self.assertEqual(contrast["total_tokens"], -643)
        findings = report["descriptive_findings"]
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertTrue(findings["normal_and_blind_are_input_token_matched"])
        self.assertFalse(findings["normal_and_blind_are_total_token_matched"])
        self.assertFalse(findings["feedback_effect_identified"])

    def test_source_scan_rejects_evaluator_access_and_detects_bad_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = Path(temporary) / "clean.py"
            clean.write_text(
                "def calibrate_forcefield(problem, query):\n    return {}\n",
                encoding="utf-8",
            )
            bad = Path(temporary) / "bad.py"
            bad.write_text(
                "from scipy.optimize import quad\n"
                "def calibrate_forcefield(problem, query):\n"
                "    return '52011', 'verification/evaluator.py'\n",
                encoding="utf-8",
            )
            self.assertTrue(ANALYSIS._source_scan(clean)["shortcut_safe"])
            scan = ANALYSIS._source_scan(bad)
            self.assertFalse(scan["shortcut_safe"])
            self.assertEqual(scan["fixed_world_literal_hits"], ["52011"])
            self.assertEqual(
                scan["known_missing_import_symbols"],
                ["scipy.optimize.quad"],
            )

    def test_runtime_source_change_fails_closed(self):
        report = self.report(
            runtime_source_equivalent=False,
            runtime_source_changes=["benchmarks/Chemistry/ForceFieldCalibration/x.py"],
        )
        self.assertFalse(report["execution_passed"])

    def test_trusted_evaluator_runtime_mismatch_fails_closed(self):
        records = copy.deepcopy(_records())
        records["blind_budget_three"][
            "trusted_evaluator_runtime_sha256"
        ] = "8" * 64
        report = ANALYSIS._analyze_records(_calibration(), records)
        self.assertFalse(report["execution_passed"])
        self.assertEqual(report["trust_decision"], "execution_failed")

    def test_full_analysis_when_raw_trajectories_exist(self):
        raw_paths = []
        for relative in ANALYSIS.REPORTS.values():
            if not (ROOT / relative).is_file():
                self.skipTest("force-field GPT-5.5 report not generated")
            document = __import__("json").loads(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            raw_paths.append(document["runs"][0]["workdir"])
        # Resolved the same way the analysis resolves it. Checking the recorded absolute path
        # instead made this guard and the analysis disagree: on the machine that produced the
        # runs the absolute path exists, so the guard passed, and the analysis - which places the
        # path in the repository being read - then raised in a worktree.
        if not all(run_workdir_is_present(path, ROOT) for path in raw_paths):
            self.skipTest("the runs this analysis reads are not in this checkout")
        report = ANALYSIS.analyze()
        self.assertTrue(report["execution_passed"], report)
        self.assertEqual(
            report["proposal_hurdle_summary"]["failure_counts"],
            {
                "blocked_or_missing_import": 1,
                "candidate_runtime_error": 5,
                "invalid_submission": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
