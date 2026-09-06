from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sle.runtime_identity import current_runtime_descriptor


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "analyze_candidate_calibration.py"
)
SPEC = importlib.util.spec_from_file_location(
    "candidate_calibration_analysis_for_test", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _events(scores: list[float]) -> list[dict]:
    return [
        {
            "step": step,
            "best_score": score,
            "valid": True,
            "accepted": step == 0 or score > max(scores[:step]),
            "metrics": {
                "accuracy": score,
                "promotion_ready": score > 1.0,
            },
        }
        for step, score in enumerate(scores)
    ]


class CandidateCalibrationAnalysisTests(unittest.TestCase):
    def _analyze(self, report_path: Path, prereg_path: Path) -> dict:
        with patch.object(
            MODULE, "_verify_successful_run",
            side_effect=lambda run, *_args, **_kwargs: run[
                "trajectory_snapshot"
            ],
        ), patch.object(MODULE, "_validate_cohort_semantics"), patch.object(
            MODULE, "_validate_preregistered_command"
        ), patch.object(
            MODULE, "_validate_source_lineage"
        ):
            return MODULE.analyze(report_path, prereg_path)

    def _write_inputs(self, root: Path) -> tuple[Path, Path]:
        runtime = current_runtime_descriptor(())
        binding = {
            "task_contract_sha256": "1" * 64,
            "task_package_sha256": "2" * 64,
            "task_card_sha256": "3" * 64,
            "runtime_source_sha256": "4" * 64,
            "task_family_id": "D/T",
            "wave_id": "wave-v1",
            "wave_manifest_sha256": "5" * 64,
            "trusted_evaluator_runtime": runtime,
            "trusted_evaluator_runtime_sha256": runtime[
                "fingerprint_sha256"
            ],
        }
        cohort_path = (
            Path(__file__).resolve().parents[1] / ".research"
            / "exploratory_2h_cohort_manifest_2026-09-03_v7.json"
        )
        cohort_hash = hashlib.sha256(cohort_path.read_bytes()).hexdigest()
        preregistration = {
            "preregistration_id": "fixture-v1",
            "claim_limit": MODULE.CANDIDATE_CALIBRATION_CLAIM_LIMIT,
            "frozen_source": {
                "parent_revision": "f" * 40,
                "runtime_source_sha256": "4" * 64,
            },
            "source_cohort": {
                "path": cohort_path.relative_to(
                    Path(__file__).resolve().parents[1]
                ).as_posix(),
                "sha256": cohort_hash,
                "analysis_role": "candidate_calibration",
                "claim_limit": MODULE.CANDIDATE_CALIBRATION_CLAIM_LIMIT,
            },
            "model_condition": {
                "llm_condition_sha256": "a" * 64,
                "model": "hy3",
                "server_side_seed_control": False,
                "required_readable_fields": sorted(
                    MODULE.REQUIRED_READABLE_MODEL_FIELDS
                ),
            },
            "design": {
                "tasks": [{
                    "task": "D/T",
                    **binding,
                    "maturity_contract_sha256": "6" * 64,
                    "science_metric_estimands": [
                        {
                            "metric": "accuracy",
                            "value_type": "numeric",
                            "direction": "higher_is_better",
                        },
                        {
                            "metric": "promotion_ready",
                            "value_type": "boolean",
                            "direction": "higher_is_better",
                        },
                    ],
                }],
                "analysis_role": "candidate_calibration",
                "resume_permitted": True,
                "feedback_modes": ["normal", "selection_blind"],
                "local_replicate_identifiers": [0, 1],
                "budget_estimands": [1, 2, 3],
                "proposal_budget_upper_bound": 3,
                "condition_order_design": "reverse_parity",
                "condition_order_schedule": [
                    {
                        "replicate_identifier": 0,
                        "feedback_modes": ["normal", "selection_blind"],
                    },
                    {
                        "replicate_identifier": 1,
                        "feedback_modes": ["selection_blind", "normal"],
                    },
                ],
            },
        }
        prereg_path = root / "prereg.json"
        prereg_path.write_text(json.dumps(preregistration), encoding="utf-8")
        prereg_hash = hashlib.sha256(prereg_path.read_bytes()).hexdigest()

        def run(mode: str, seed: int, scores: list[float]) -> dict:
            return {
                "task": "D/T",
                "algorithm": "greedy_rewrite",
                "feedback_mode": mode,
                "seed": seed,
                "budget": 3,
                "workdir": str(
                    (root / "runs" / "D__T" / "greedy_rewrite" / mode
                     / ("seed_%d" % seed)).resolve()
                ),
                "workdir_scope": "local_only_not_portable_evidence_identity",
                "trusted_evaluator_runtime": binding[
                    "trusted_evaluator_runtime"
                ],
                "trusted_evaluator_runtime_sha256": binding[
                    "trusted_evaluator_runtime_sha256"
                ],
                "baseline": scores[0],
                "best": scores[-1],
                "trajectory_snapshot": {"events": _events(scores)},
            }

        failed = {
            "task": "D/T",
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
            "seed": 0,
            "budget": 3,
            "workdir": str(
                (root / "runs" / "D__T" / "greedy_rewrite" / "normal"
                 / "seed_0").resolve()
            ),
            "workdir_scope": "local_only_not_portable_evidence_identity",
            "trusted_evaluator_runtime": binding[
                "trusted_evaluator_runtime"
            ],
            "trusted_evaluator_runtime_sha256": binding[
                "trusted_evaluator_runtime_sha256"
            ],
            "error": "offline",
            "trajectory_snapshot": {"events": _events([0.0, 0.2])},
        }
        report = {
            "trust_status": "TRUSTED_SECURE_EVAL",
            "evidence_scope": "MODEL_CALIBRATION_NOT_POPULATION_PERFORMANCE",
            "source_provenance": {
                "git_available": True,
                "git_revision": "abc123",
                "source_tree_dirty": False,
                "source_changes": [],
            },
            "final_integrity": {"passed": True},
            "execution_passed": True,
            "trusted_evidence": True,
            "passed": True,
            "trust_decision": "trusted_clean_revision",
            "aggregate": {
                "successful_runs": 4,
                "failed_runs": 0,
                "intent_to_evaluate": {
                    "scheduled_runs": 4,
                    "successful_runs": 4,
                    "terminal_failed_runs": 0,
                    "missing_run_rows": 0,
                },
            },
            "config": {
                "tasks": ["D/T"],
                "algorithms": ["greedy_rewrite"],
                "feedback_modes": ["normal", "selection_blind"],
                "seeds": [0, 1],
                "budget": 3,
                "scheduled_run_count": 4,
                "condition_order": "reverse_parity",
                "condition_order_schedule": preregistration["design"][
                    "condition_order_schedule"
                ],
                "work_root": str((root / "runs").resolve()),
                "work_root_scope": "local_only_not_portable_evidence_identity",
                "frozen_task_bindings": {"D/T": binding},
                "run_role": "calibration",
                "llm_condition_sha256": "a" * 64,
                "llm": {"model": "hy3", "server_side_seed_control": False},
                "preregistration": {
                    "sha256": prereg_hash,
                    "execution_contract_validated": True,
                    "resume_suffix_permitted": True,
                },
                "cohort_manifest": {
                    "path": preregistration["source_cohort"]["path"],
                    "sha256": cohort_hash,
                },
            },
            "runs": [
                failed,
                run("selection_blind", 0, [0.0, 0.1, 0.2, 0.3]),
                run("normal", 1, [0.0, 0.4, 0.9, 1.1]),
                run("selection_blind", 1, [0.0, 0.3, 0.5, 0.8]),
                run("normal", 0, [0.0, 0.5, 0.7, 0.9]),
            ],
        }
        report_path = root / "report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return report_path, prereg_path

    def test_first_attempt_and_latest_prefix_summaries_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_path, prereg_path = self._write_inputs(Path(temporary))
            result = self._analyze(report_path, prereg_path)

        first = result["analyses"]["first_attempt"]
        latest = result["analyses"]["latest_attempt_after_transparent_resume"]
        first_normal_b3 = first["by_task_condition"]["D/T|normal"]["B3"]
        latest_normal_b3 = latest["by_task_condition"]["D/T|normal"]["B3"]
        self.assertEqual(first_normal_b3["scheduled_n"], 2)
        self.assertEqual(first_normal_b3["observed_n"], 1)
        self.assertEqual(first_normal_b3["missing_n"], 1)
        self.assertEqual(first_normal_b3["exceeds_reference_n"], 1)
        self.assertEqual(latest_normal_b3["observed_n"], 2)
        self.assertAlmostEqual(latest_normal_b3["mean_best_score"], 1.0)
        self.assertEqual(
            latest_normal_b3["valid_proposals_through_prefix_n"], 6
        )
        self.assertEqual(
            latest_normal_b3["proposal_errors_through_prefix_n"], 0
        )
        self.assertEqual(
            first["normal_minus_selection_blind"]["D/T"]["B3"], None
        )
        self.assertEqual(
            first_normal_b3["valid_proposals_through_prefix_n"], 4
        )
        self.assertAlmostEqual(
            latest["normal_minus_selection_blind"]["D/T"]["B3"], 0.45
        )

    def test_science_metric_summaries_preserve_missingness_and_contrasts(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_path, prereg_path = self._write_inputs(Path(temporary))
            result = self._analyze(report_path, prereg_path)

        first = result["analyses"]["first_attempt"]
        latest = result["analyses"][
            "latest_attempt_after_transparent_resume"
        ]
        first_normal = first["by_task_condition"]["D/T|normal"]["B3"]
        latest_normal = latest["by_task_condition"]["D/T|normal"]["B3"]
        accuracy = latest_normal["science_metrics"]["accuracy"]
        promotion = latest_normal["science_metrics"]["promotion_ready"]

        self.assertEqual(
            first_normal["science_metrics"]["accuracy"],
            {
                "value_type": "numeric",
                "direction": "higher_is_better",
                "scheduled_n": 2,
                "observed_n": 1,
                "missing_n": 1,
                "mean_over_observed": 1.1,
            },
        )
        self.assertEqual(accuracy["scheduled_n"], 2)
        self.assertEqual(accuracy["observed_n"], 2)
        self.assertEqual(accuracy["missing_n"], 0)
        self.assertAlmostEqual(accuracy["mean_over_observed"], 1.0)
        self.assertEqual(promotion["value_type"], "boolean")
        self.assertEqual(promotion["direction"], "higher_is_better")
        self.assertAlmostEqual(promotion["true_fraction_of_observed"], 0.5)
        self.assertEqual(
            first["science_metric_normal_minus_selection_blind"]["D/T"][
                "B3"
            ],
            None,
        )
        science_contrast = latest[
            "science_metric_normal_minus_selection_blind"
        ]["D/T"]["B3"]
        self.assertAlmostEqual(science_contrast["accuracy"], 0.45)
        self.assertAlmostEqual(science_contrast["promotion_ready"], 0.5)
        self.assertEqual(
            latest_normal["best_artifact_science_metrics_by_replicate"][0],
            {
                "replicate_identifier": 0,
                "observed": True,
                "status": "completed",
                "best_artifact_source_step": 3,
                "metrics": {
                    "accuracy": 0.9,
                    "promotion_ready": False,
                },
            },
        )
        self.assertEqual(
            first_normal["best_artifact_science_metrics_by_replicate"][0],
            {
                "replicate_identifier": 0,
                "observed": False,
                "status": "error",
                "best_artifact_source_step": None,
                "metrics": None,
            },
        )

    def test_report_must_match_preregistered_model_condition(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["config"]["llm_condition_sha256"] = "x" * 64
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model condition"):
                self._analyze(report_path, prereg_path)

            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["config"]["condition_order_schedule"] = []
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "condition schedule"):
                self._analyze(report_path, prereg_path)

    def test_report_must_match_task_binding_and_run_cell_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["config"]["frozen_task_bindings"]["D/T"][
                "wave_manifest_sha256"
            ] = "x" * 64
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen task binding"):
                self._analyze(report_path, prereg_path)

            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["config"]["frozen_task_bindings"]["D/T"] = {}
            for run in report["runs"]:
                run.pop("trusted_evaluator_runtime", None)
                run.pop("trusted_evaluator_runtime_sha256", None)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen task binding"):
                self._analyze(report_path, prereg_path)

            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["runs"][0]["algorithm"] = "other"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "run cell identity"):
                self._analyze(report_path, prereg_path)

            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["runs"][0]["seed"] = True
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "run cell identity"):
                self._analyze(report_path, prereg_path)

    def test_untrusted_parent_report_cannot_be_upgraded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["execution_passed"] = False
            report["trusted_evidence"] = False
            report["passed"] = False
            report["trust_decision"] = "execution_failed"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = self._analyze(report_path, prereg_path)
        self.assertFalse(result["execution_passed"])
        self.assertFalse(result["trusted_evidence"])
        self.assertFalse(result["passed"])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path, prereg_path = self._write_inputs(root)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["trust_decision"] = "execution_failed"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = self._analyze(report_path, prereg_path)
        self.assertFalse(result["trusted_evidence"])

    def test_design_axes_and_budget_are_strict_nonempty_unique_integers(self):
        mutations = (
            (
                lambda prereg, report: (
                    prereg["design"].update({"feedback_modes": []}),
                    report["config"].update({
                        "feedback_modes": [], "scheduled_run_count": 0,
                    }),
                ),
                "feedback modes",
            ),
            (
                lambda prereg, report: (
                    prereg["design"].update({
                        "local_replicate_identifiers": [0, True],
                    }),
                    report["config"].update({"seeds": [0, True]}),
                ),
                "replicate identifiers",
            ),
            (
                lambda prereg, report: (
                    prereg["design"].update({
                        "proposal_budget_upper_bound": True,
                        "budget_estimands": [1],
                    }),
                    report["config"].update({"budget": True}),
                ),
                "proposal budget",
            ),
            (
                lambda prereg, _report: prereg["design"].update({
                    "budget_estimands": [1, 4],
                }),
                "budget estimands",
            ),
        )
        for mutate, message in mutations:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report_path, prereg_path = self._write_inputs(root)
                prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                mutate(prereg, report)
                prereg_path.write_text(json.dumps(prereg), encoding="utf-8")
                report["config"]["preregistration"]["sha256"] = hashlib.sha256(
                    prereg_path.read_bytes()
                ).hexdigest()
                report_path.write_text(json.dumps(report), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    self._analyze(report_path, prereg_path)

    def test_science_metric_estimands_are_strict_and_unique(self):
        mutations = (
            lambda specs: specs.clear(),
            lambda specs: specs.append(dict(specs[0])),
            lambda specs: specs[0].update({"metric": " "}),
            lambda specs: specs[0].update({"value_type": "ratio"}),
            lambda specs: specs[0].update({"direction": "maximize"}),
            lambda specs: specs[0].update({"direction": ["higher_is_better"]}),
            lambda specs: specs[0].update({"unfrozen_field": "surprise"}),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report_path, prereg_path = self._write_inputs(root)
                prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
                mutate(
                    prereg["design"]["tasks"][0][
                        "science_metric_estimands"
                    ]
                )
                prereg_path.write_text(json.dumps(prereg), encoding="utf-8")
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["config"]["preregistration"]["sha256"] = (
                    hashlib.sha256(prereg_path.read_bytes()).hexdigest()
                )
                report_path.write_text(json.dumps(report), encoding="utf-8")

                with self.assertRaisesRegex(
                    ValueError, "science metric estimands"
                ):
                    self._analyze(report_path, prereg_path)

    def test_accepted_incumbent_science_metric_values_are_strict(self):
        metric_specs = [
            {
                "metric": "accuracy",
                "value_type": "numeric",
                "direction": "higher_is_better",
            },
            {
                "metric": "promotion_ready",
                "value_type": "boolean",
                "direction": "higher_is_better",
            },
        ]
        invalid_values = (
            ({"accuracy": True, "promotion_ready": False}, "numeric"),
            ({"accuracy": float("nan"), "promotion_ready": False}, "numeric"),
            ({"accuracy": 0.5, "promotion_ready": 1}, "boolean"),
            ({"accuracy": 0.5}, "boolean"),
        )
        for metrics, message in invalid_values:
            with self.subTest(metrics=metrics):
                events = _events([0.0, 0.5])
                events[1]["metrics"] = metrics
                with self.assertRaisesRegex(ValueError, message):
                    MODULE._prefix_row(
                        {
                            "baseline": 0.0,
                            "trajectory_snapshot": {"events": events},
                        },
                        1,
                        metric_specs,
                    )

    def test_successful_run_artifacts_must_reverify(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_path, prereg_path = self._write_inputs(Path(temporary))
            with patch.object(
                MODULE, "_verify_successful_run",
                side_effect=ValueError("unverifiable run artifacts"),
            ), patch.object(
                MODULE, "_validate_cohort_semantics"
            ), patch.object(
                MODULE, "_validate_preregistered_command"
            ), patch.object(MODULE, "_validate_source_lineage"):
                with self.assertRaisesRegex(ValueError, "unverifiable"):
                    MODULE.analyze(report_path, prereg_path)

    def test_cohort_semantics_bind_task_order_hashes_and_reuse_policy(self):
        task_row = {
            "task": "D/T",
            "task_contract_sha256": "1" * 64,
            "task_card_sha256": "2" * 64,
            "maturity_contract_sha256": "3" * 64,
        }
        source = {
            "analysis_role": "candidate_calibration",
            "claim_limit": MODULE.CANDIDATE_CALIBRATION_CLAIM_LIMIT,
        }
        cohort = {
            "schema_version": 1,
            "analysis_role": "candidate_calibration",
            "claim_limit": MODULE.CANDIDATE_CALIBRATION_CLAIM_LIMIT,
            "selection": {"confirmatory_reuse_permitted": False},
            "tasks": [{
                "task": "D/T",
                "runtime_contract_sha256": "1" * 64,
                "task_card_sha256": "2" * 64,
                "maturity_contract_sha256": "3" * 64,
            }],
        }
        MODULE._validate_cohort_semantics(
            cohort, source, [task_row], "candidate_calibration"
        )
        cohort["selection"]["confirmatory_reuse_permitted"] = True
        with self.assertRaisesRegex(ValueError, "confirmatory reuse"):
            MODULE._validate_cohort_semantics(
                cohort, source, [task_row], "candidate_calibration"
            )
        cohort["selection"]["confirmatory_reuse_permitted"] = False
        cohort["claim_limit"] = "hardness_certification_and_model_ranking"
        source["claim_limit"] = cohort["claim_limit"]
        with self.assertRaisesRegex(ValueError, "claim limit"):
            MODULE._validate_cohort_semantics(
                cohort, source, [task_row], "candidate_calibration"
            )

    def test_reported_baseline_and_best_must_match_verified_trajectory(self):
        events = _events([0.0, 0.5, 0.9, 1.1])
        MODULE._validate_run_scores(
            {"baseline": 0.0, "best": 1.1}, events
        )
        with self.assertRaisesRegex(ValueError, "baseline or best"):
            MODULE._validate_run_scores(
                {"baseline": 99.0, "best": 1.1}, events
            )

    def test_incomplete_prefix_retains_all_observed_failure_burden(self):
        events = _events([0.0, -1.0])
        events[1].update({
            "valid": False,
            "error": "TimeoutError: provider timeout",
            "algorithm_metadata": {"signed_decision_action": "abstain"},
        })
        row = MODULE._prefix_row(
            {
                "error": "TimeoutError: provider timeout",
                "baseline": 0.0,
                "trajectory_snapshot": {"events": events},
            },
            3,
        )
        self.assertFalse(row["observed"])
        self.assertEqual(row["invalid_proposals_through_prefix"], 1)
        self.assertEqual(row["proposal_errors_through_prefix"], 1)
        self.assertEqual(row["proposal_timeouts_through_prefix"], 1)
        self.assertEqual(row["signed_abstentions_through_prefix"], 1)

    def test_prefix_science_metrics_follow_latest_accepted_incumbent(self):
        metric_specs = [
            {
                "metric": "accuracy",
                "value_type": "numeric",
                "direction": "higher_is_better",
            },
            {
                "metric": "promotion_ready",
                "value_type": "boolean",
                "direction": "higher_is_better",
            },
        ]
        events = [
            {
                "step": 0,
                "best_score": 0.0,
                "valid": True,
                "accepted": True,
                "metrics": {"accuracy": 0.1, "promotion_ready": False},
            },
            {
                "step": 1,
                "best_score": 0.8,
                "valid": True,
                "accepted": True,
                "metrics": {"accuracy": 0.7, "promotion_ready": True},
            },
            {
                "step": 2,
                "best_score": 0.8,
                "valid": True,
                "accepted": False,
                "metrics": {"accuracy": 0.99, "promotion_ready": False},
            },
        ]

        row = MODULE._prefix_row(
            {
                "baseline": 0.0,
                "trajectory_snapshot": {"events": events},
            },
            2,
            metric_specs,
        )

        self.assertEqual(row["best_artifact_source_step"], 1)
        self.assertEqual(
            row["best_artifact_science_metrics"],
            {"accuracy": 0.7, "promotion_ready": True},
        )

        events[1]["accepted"] = False
        row = MODULE._prefix_row(
            {
                "baseline": 0.0,
                "trajectory_snapshot": {"events": events},
            },
            2,
            metric_specs,
        )
        self.assertEqual(row["best_artifact_source_step"], 0)
        self.assertEqual(
            row["best_artifact_science_metrics"],
            {"accuracy": 0.1, "promotion_ready": False},
        )

    def test_verified_readable_model_condition_must_match_preregistration(self):
        descriptor = {
            "wire": "chat",
            "endpoint_sha256": "e" * 64,
            "model": "hy3",
            "max_output_tokens": 32768,
            "temperature": 0.7,
            "reasoning_effort": None,
            "timeout_seconds": 600.0,
            "stream": True,
            "chat_max_tokens_field": "max_tokens",
            "chat_reasoning_fallback": False,
            "server_side_seed_control": False,
        }
        model = {
            "wire": "chat",
            "endpoint_sha256": "e" * 64,
            "model": "hy3",
            "max_output_tokens": 32768,
            "temperature": 0.7,
            "reasoning_effort": None,
            "provider_request_timeout_seconds": 600.0,
            "stream": True,
            "chat_max_tokens_field": "max_tokens",
            "chat_reasoning_fallback": False,
            "server_side_seed_control": False,
        }
        MODULE._validate_verified_model_condition(
            {"llm_condition": descriptor}, model
        )
        descriptor["model"] = "other-model"
        with self.assertRaisesRegex(ValueError, "model condition differs"):
            MODULE._validate_verified_model_condition(
                {"llm_condition": descriptor}, model
            )
        descriptor["model"] = "hy3"
        descriptor["endpoint_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "model condition differs"):
            MODULE._validate_verified_model_condition(
                {"llm_condition": descriptor}, model
            )
        model.pop("reasoning_effort")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            MODULE._validate_verified_model_condition(
                {"llm_condition": descriptor}, model
            )

    def test_resume_or_duplicate_attempts_cannot_be_trusted(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_path, prereg_path = self._write_inputs(Path(temporary))
            result = self._analyze(report_path, prereg_path)
        self.assertFalse(result["trusted_evidence"])
        self.assertFalse(result["execution_passed"])

    def test_source_lineage_accepts_same_revision_and_rejects_unknown_parent(self):
        revision = MODULE.subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(MODULE.ROOT),
            text=True,
        ).strip()
        MODULE._validate_source_lineage(revision, revision)
        with self.assertRaisesRegex(ValueError, "not an ancestor"):
            MODULE._validate_source_lineage("0" * 40, revision)


if __name__ == "__main__":
    unittest.main()
