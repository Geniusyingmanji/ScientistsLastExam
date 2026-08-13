from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/analyze_calorimeter_v2_calibrations.py"


def _analysis():
    spec = importlib.util.spec_from_file_location(
        "calorimeter_analysis_test", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load calorimeter analysis")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _calibration(module):
    return {
        "source_revision": module.EXPECTED_MODEL_SOURCE_REVISION,
        "weak_baseline": {"combined_score": 0.0},
        "nominal_reference_policy": {
            "combined_score": 1.0,
            "robustness_score": 0.0,
        },
        "robust_reference_policy": {
            "combined_score": 0.7977894682304659,
            "robustness_score": 1.0,
            "heldout_policy_score": 0.7541269490241698,
        },
    }


def _record(module, label, budget, seed, mode, reason_key, tokens):
    baseline = "a" * 64
    trajectory = [{
        "step": 0,
        "oracle_calls": 1,
        "budget_units": 1,
        "score": 0.0,
        "best_score": 0.0,
        "valid": True,
        "accepted": True,
        "candidate_sha256": baseline,
        "parent_sha256": None,
        "candidate_failure_kind": None,
        "infrastructure_failure": False,
        "science_metrics": {"combined_score": 0.0},
        "llm": {},
        "algorithm_metadata": {},
    }]
    for step in range(1, budget + 1):
        trajectory.append({
            "step": step,
            "oracle_calls": step + 1,
            "budget_units": step + 1,
            "score": -1.0e18,
            "best_score": 0.0,
            "valid": False,
            "accepted": False,
            "candidate_sha256": str(step) * 64,
            "parent_sha256": baseline,
            "candidate_failure_kind": "candidate_runtime_error",
            "infrastructure_failure": False,
            "science_metrics": {},
            "llm": {},
            "algorithm_metadata": {},
        })
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "b" * 64,
        "source_revision": module.EXPECTED_MODEL_SOURCE_REVISION,
        "source_scope": ["sle", "scripts", "tests", "benchmarks"],
        "llm_condition_sha256": "c" * 64,
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
        "input_tokens": 2226 * budget,
        "output_tokens": tokens - 2226 * budget,
        "total_tokens": tokens,
        "wall_seconds": float(30 * budget),
        "baseline_score": 0.0,
        "best_score": 0.0,
        "best_so_far_auc": 0.0,
        "accepted_proposals": 0,
        "proposal_count": budget,
        "valid_proposal_count": 0,
        "invalid_proposal_count": budget,
        "failure_counts": {"candidate_runtime_error": budget},
        "infrastructure_failure_count": 0,
        "trajectory_sha256": "d" * 64,
        "run_manifest_sha256": "e" * 64,
        "task_contract_sha256": "f" * 64,
        "runtime_source_sha256": "0" * 64,
        "baseline_candidate_sha256": baseline,
        "best_program": "runs/example/best_program.py",
        "best_program_sha256": baseline,
        "terminal_program": "runs/example/solution.py",
        "terminal_program_sha256": trajectory[-1]["candidate_sha256"],
        "terminal_source_diagnosis": {
            "path": "runs/example/solution.py",
            "sha256": trajectory[-1]["candidate_sha256"],
            "compiles_and_imports": True,
            "direct_oracle_valid": 0.0,
            "direct_oracle_score": 0.0,
            "candidate_instance_valid_rate": 0.0,
            "per_instance_reasons": [reason_key] * 6,
            "normalized_reason_counts": {reason_key: 6},
        },
        "artifact_retention_scope": "synthetic",
        "trajectory": trajectory,
        "integrity_passed": True,
    }


def _records(module):
    return {
        "budget_one": _record(
            module,
            "budget_one",
            1,
            0,
            "normal",
            "missing_public_key:radiation_length_scint_mm",
            5944,
        ),
        "normal_budget_three": _record(
            module,
            "normal_budget_three",
            3,
            1,
            "normal",
            "missing_public_key:radiation_length_scint_mm",
            18091,
        ),
        "blind_budget_three": _record(
            module,
            "blind_budget_three",
            3,
            1,
            "selection_blind",
            "missing_public_key:light_yield_per_gev",
            18329,
        ),
    }


class CalorimeterAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = _analysis()

    def report(self, **kwargs):
        return self.analysis._analyze_records(
            _calibration(self.analysis),
            _records(self.analysis),
            runtime_source_equivalent=kwargs.get(
                "runtime_source_equivalent", True
            ),
            runtime_source_changes=kwargs.get("runtime_source_changes", []),
        )

    def test_integrity_and_single_run_scope(self):
        report = self.report()
        self.assertTrue(report["execution_passed"])
        self.assertIsInstance(report["trusted_evidence"], bool)
        self.assertTrue(report["input_task_runtime_source_equivalent"])
        self.assertTrue(report["input_source_scope_equivalent"])
        self.assertTrue(report["input_llm_condition_equivalent"])
        self.assertTrue(report["input_task_contract_equivalent"])
        self.assertTrue(report["input_runtime_manifest_equivalent"])
        self.assertTrue(all(
            row["integrity_passed"]
            for row in report["records"].values()
        ))
        self.assertIn("SINGLE_RUN", report["evidence_scope"])
        self.assertIn("NOT_FEEDBACK_CAUSAL", report["evidence_scope"])

    def test_all_proposals_are_runtime_invalid_not_infrastructure_failures(self):
        hurdle = self.report()["proposal_hurdle_summary"]
        self.assertEqual(hurdle["proposal_count"], 7)
        self.assertEqual(hurdle["valid_proposal_count"], 0)
        self.assertEqual(hurdle["invalid_proposal_count"], 7)
        self.assertEqual(hurdle["candidate_runtime_error_count"], 7)
        self.assertEqual(hurdle["infrastructure_failure_count"], 0)
        self.assertEqual(hurdle["retained_terminal_source_count"], 3)
        self.assertEqual(hurdle["unretained_intermediate_source_count"], 4)

    def test_retained_terminal_diagnosis_and_lineage(self):
        expected = {
            "budget_one": {
                "missing_public_key:radiation_length_scint_mm": 6
            },
            "normal_budget_three": {
                "missing_public_key:radiation_length_scint_mm": 6
            },
            "blind_budget_three": {
                "missing_public_key:light_yield_per_gev": 6
            },
        }
        records = self.report()["records"]
        baseline_hashes = set()
        for label, record in records.items():
            diagnosis = record["terminal_source_diagnosis"]
            self.assertEqual(
                diagnosis["normalized_reason_counts"], expected[label]
            )
            self.assertEqual(diagnosis["direct_oracle_valid"], 0.0)
            self.assertEqual(
                diagnosis["candidate_instance_valid_rate"], 0.0
            )
            self.assertEqual(len(diagnosis["per_instance_reasons"]), 6)
            baseline_hashes.add(record["baseline_candidate_sha256"])
        self.assertEqual(len(baseline_hashes), 1)
        normal = records["normal_budget_three"]
        blind = records["blind_budget_three"]
        baseline = normal["baseline_candidate_sha256"]
        self.assertTrue(all(
            row["parent_sha256"] == baseline
            for row in normal["trajectory"][1:]
        ))
        self.assertTrue(all(
            row["parent_sha256"] == baseline
            for row in blind["trajectory"][1:]
        ))

    def test_budget_three_contrast_is_oracle_not_token_matched(self):
        report = self.report()
        contrast = report[
            "normal_minus_blind_budget_three_descriptive_contrast"
        ]
        self.assertEqual(contrast["best_score"], 0.0)
        self.assertEqual(contrast["valid_proposal_count"], 0)
        self.assertEqual(contrast["oracle_calls"], 0)
        self.assertEqual(contrast["input_tokens"], 0)
        self.assertNotEqual(contrast["output_tokens"], 0)
        self.assertNotEqual(contrast["total_tokens"], 0)
        findings = report["descriptive_findings"]
        self.assertTrue(findings["normal_and_blind_are_oracle_call_matched"])
        self.assertFalse(findings["normal_and_blind_are_token_matched"])
        self.assertFalse(findings["feedback_effect_identified"])

    def test_reference_tradeoff_exists_but_model_does_not_reach_it(self):
        report = self.report()
        context = report["reference_tradeoff_context"]
        self.assertEqual(context["weak_baseline_development_score"], 0.0)
        self.assertEqual(context["nominal_reference_development_score"], 1.0)
        self.assertEqual(
            context["nominal_reference_development_robustness"], 0.0
        )
        self.assertGreater(
            context["robust_reference_development_score"], 0.70
        )
        self.assertEqual(
            context["robust_reference_development_robustness"], 1.0
        )
        self.assertFalse(
            report["descriptive_findings"][
                "model_reaches_nominal_robust_tradeoff_curve"
            ]
        )

    def test_runtime_source_change_gate_rejects_mismatch(self):
        report = self.report(
            runtime_source_equivalent=False,
            runtime_source_changes=["sle/example.py"],
        )
        self.assertFalse(report["execution_passed"])
        self.assertEqual(report["trust_decision"], "execution_failed")
        self.assertFalse(report["trusted_evidence"])

    def test_runtime_scope_tracks_trusted_evaluator_not_search_or_narrative(self):
        scope = self.analysis.TASK_RUNTIME_SCOPE
        for path in (
            "sle/evaluate.py",
            "sle/trusted_driver.py",
            "sle/secure_eval.py",
            "sle/candidate_worker.py",
            "sle/rpc_codec.py",
        ):
            self.assertIn(path, scope)
        for path in (
            "sle/algorithms/evolve.py",
            "sle/protocol.py",
            "sle/certification.yaml",
        ):
            self.assertNotIn(path, scope)

    def test_full_analysis_when_raw_trajectories_exist(self):
        raw_paths = []
        for relative in self.analysis.REPORTS.values():
            if not (ROOT / relative).is_file():
                self.skipTest("calorimeter GPT-5.5 report not generated")
            document = __import__("json").loads(
                (ROOT / relative).read_text(encoding="utf-8")
            )
            raw_paths.append(
                Path(document["runs"][0]["workdir"]) / "trajectory.jsonl"
            )
        if not all(path.is_file() for path in raw_paths):
            self.skipTest("ignored raw trajectories are unavailable")
        report = self.analysis.analyze()
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["proposal_hurdle_summary"]["proposal_count"], 7
        )


if __name__ == "__main__":
    unittest.main()
