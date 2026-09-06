from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sle.algorithms.common import atomic_write_text
from sle.evaluation_ledger import EvaluationLedger
from sle.protocol import (
    TrajectoryEvent,
    append_event,
    load_trajectory,
    sha256_text,
    summarize_trajectory,
)
from sle.run_verification import verify_run
from sle.runtime_identity import current_runtime_descriptor


def _selection_policy(feedback_mode: str) -> str:
    if feedback_mode == "selection_blind":
        return "offline_best_of_open_loop_batch"
    if feedback_mode == "delayed_replay":
        return "delayed_online_parent_offline_final_best"
    return "online_incumbent"


def _accepted_semantics(feedback_mode: str) -> str:
    if feedback_mode == "selection_blind":
        return "offline_best_update"
    if feedback_mode == "delayed_replay":
        return "observer_best_update_not_immediate_parent_release"
    return "online_incumbent_update"


class RunVerificationTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        frontier: dict[str, str] | None = None,
        extra_request_frontier: dict[str, str] | None = None,
        proposal_budget: int = 0,
        feedback_mode: str = "normal",
    ) -> str:
        program = "def solve():\n    return 1\n"
        candidate_hash = sha256_text(program)
        manifest = {
            "schema_version": 1,
            "algorithm": "greedy_rewrite",
            "task_id": "ScientificComputing/Example",
            "task_contract_sha256": "a" * 64,
            "task_package_sha256": "b" * 64,
            "runtime_source_sha256": "c" * 64,
            "trusted_evaluator_runtime": current_runtime_descriptor(()),
            "seed": 0,
            "feedback_mode": feedback_mode,
            "llm_condition_sha256": "d" * 64,
            "llm_condition": {"model": "test-model"},
            **(frontier or {}),
        }
        atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
        receipt = EvaluationLedger(root).evaluate_once(
            {
                "kind": "baseline",
                **{key: manifest[key] for key in (
                    "algorithm", "task_id", "task_contract_sha256",
                    "task_package_sha256", "runtime_source_sha256", "seed",
                    "feedback_mode", "llm_condition_sha256", "llm_condition",
                )},
                "proposal_budget": proposal_budget,
                **(frontier or {}),
                **(extra_request_frontier or {}),
                "trusted_evaluator_runtime_sha256": manifest[
                    "trusted_evaluator_runtime"
                ]["fingerprint_sha256"],
                "step": 0,
                "candidate_sha256": candidate_hash,
            },
            lambda: {"combined_score": 0.25, "valid": 1.0},
        )
        event = TrajectoryEvent(
            step=0,
            oracle_calls=1,
            score=0.25,
            best_score=0.25,
            valid=True,
            accepted=True,
            wall_seconds=receipt["evaluation_wall_seconds"],
            cumulative_wall_seconds=receipt["evaluation_wall_seconds"],
            candidate_sha256=candidate_hash,
            parent_sha256=None,
            budget_units=1,
            metrics=receipt["metrics"],
            algorithm_metadata={"evaluation_request_id": receipt["request_id"]},
        )
        append_event(root / "trajectory.jsonl", event)
        summary = summarize_trajectory([event.to_dict()], budget=1)
        summary.update({
            "algorithm": "greedy_rewrite",
            "task_id": manifest["task_id"],
            "seed": 0,
            "feedback_mode": feedback_mode,
            "selection_policy": _selection_policy(feedback_mode),
            "budget": 0,
            "baseline_score": 0.25,
            "evaluation_ledger_snapshot": EvaluationLedger(root).snapshot(),
        })
        atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
        atomic_write_text(root / "best_program.py", program)
        return str(receipt["request_id"])

    def _proposal(
        self,
        root: Path,
        *,
        score: float,
        accepted: bool,
        recorded_feedback_mode: str | None = None,
    ) -> str:
        parent = (root / "best_program.py").read_text(encoding="utf-8")
        program = "def solve():\n    return 2\n"
        candidate_hash = sha256_text(program)
        prompt_hash = "f" * 64
        manifest = json.loads(
            (root / "run_manifest.json").read_text(encoding="utf-8")
        )
        feedback_mode = manifest["feedback_mode"]
        recorded_mode = recorded_feedback_mode or feedback_mode
        prompt_metrics = {"combined_score": 0.25, "valid": 1.0}
        if recorded_mode == "none":
            prompt_metrics = {}
        elif recorded_mode == "score_only":
            prompt_metrics = {"combined_score": 0.25}
        prompt_metrics_rendered = json.dumps(prompt_metrics, indent=2)
        receipt = EvaluationLedger(root).evaluate_once(
            {
                "kind": "proposal",
                "task_id": "ScientificComputing/Example",
                "task_contract_sha256": "a" * 64,
                "task_package_sha256": "b" * 64,
                "runtime_source_sha256": "c" * 64,
                "algorithm": "greedy_rewrite",
                "feedback_mode": feedback_mode,
                "seed": 0,
                "proposal_budget": 1,
                "llm_condition_sha256": "d" * 64,
                "llm_condition": {"model": "test-model"},
                "trusted_evaluator_runtime_sha256": manifest[
                    "trusted_evaluator_runtime"
                ]["fingerprint_sha256"],
                "step": 1,
                "candidate_sha256": candidate_hash,
                "parent_sha256": sha256_text(parent),
                "prompt_sha256": prompt_hash,
            },
            lambda: {"combined_score": score, "valid": 1.0},
        )
        best_score = score if accepted else 0.25
        prior_cumulative = float(
            load_trajectory(root / "trajectory.jsonl")[-1]["cumulative_wall_seconds"]
        )
        append_event(
            root / "trajectory.jsonl",
            TrajectoryEvent(
                step=1,
                oracle_calls=2,
                score=score,
                best_score=best_score,
                valid=True,
                accepted=accepted,
                wall_seconds=receipt["evaluation_wall_seconds"],
                cumulative_wall_seconds=(
                    prior_cumulative + receipt["evaluation_wall_seconds"]
                ),
                candidate_sha256=candidate_hash,
                parent_sha256=sha256_text(parent),
                budget_units=2,
                metrics=receipt["metrics"],
                algorithm_metadata={
                    "evaluation_request_id": receipt["request_id"],
                    "selection_policy": _selection_policy(recorded_mode),
                    "accepted_semantics": _accepted_semantics(recorded_mode),
                    "proposal_slot": 1,
                    "prompt_source_step": 0,
                    "feedback_released_through_step": 0,
                    "prompt_sha256": prompt_hash,
                    "prompt_metrics_sha256": sha256_text(
                        prompt_metrics_rendered
                    ),
                    "prompt_metrics_utf8_bytes": len(
                        prompt_metrics_rendered.encode("utf-8")
                    ),
                    "prompt_metric_keys": ",".join(sorted(prompt_metrics)),
                    "completed_after_active_wall_horizon": False,
                },
            ),
        )
        events = load_trajectory(root / "trajectory.jsonl")
        summary = summarize_trajectory(events, budget=2)
        prior = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        prior.update(summary)
        prior["budget"] = 1
        prior["evaluation_ledger_snapshot"] = EvaluationLedger(root).snapshot()
        atomic_write_text(root / "summary.json", json.dumps(prior) + "\n")
        if accepted:
            atomic_write_text(root / "best_program.py", program)
        return program

    def test_verifies_complete_content_bound_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            verified = verify_run(root)
            self.assertTrue(verified["verified"])
            self.assertEqual(
                verified["trusted_evaluator_runtime_sha256"],
                verified["trusted_evaluator_runtime"]["fingerprint_sha256"],
            )
            self.assertEqual(
                {
                    key: verified[key] for key in (
                        "task_id",
                        "algorithm",
                        "feedback_mode",
                        "seed",
                        "budget",
                        "task_contract_sha256",
                        "task_package_sha256",
                        "runtime_source_sha256",
                        "task_family_id",
                        "wave_id",
                        "wave_manifest_sha256",
                    )
                },
                {
                    "task_id": "ScientificComputing/Example",
                    "algorithm": "greedy_rewrite",
                    "feedback_mode": "normal",
                    "seed": 0,
                    "budget": 0,
                    "task_contract_sha256": "a" * 64,
                    "task_package_sha256": "b" * 64,
                    "runtime_source_sha256": "c" * 64,
                    "task_family_id": None,
                    "wave_id": None,
                    "wave_manifest_sha256": None,
                },
            )

    def test_returns_complete_frontier_cell_identity(self):
        frontier = {
            "task_family_id": "ScientificComputing/Example",
            "wave_id": "wave-1",
            "wave_manifest_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, frontier=frontier)
            verified = verify_run(root)
            self.assertEqual(
                {key: verified[key] for key in frontier}, frontier
            )

    def test_rejects_wrong_manifest_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            manifest = json.loads((root / "run_manifest.json").read_text())
            manifest["schema_version"] = 2
            atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
            with self.assertRaisesRegex(ValueError, "manifest schema"):
                verify_run(root)

    def test_rejects_relabelled_model_mode_or_seed_cell(self):
        cases = (
            ({"llm_condition_sha256": "e" * 64,
              "llm_condition": {"model": "other-model"}}, {}),
            ({"feedback_mode": "selection_blind"},
             {"feedback_mode": "selection_blind"}),
            ({"seed": 19}, {"seed": 19}),
        )
        for manifest_update, summary_update in cases:
            with self.subTest(manifest_update=manifest_update), \
                 tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._run(root)
                manifest = json.loads((root / "run_manifest.json").read_text())
                manifest.update(manifest_update)
                atomic_write_text(
                    root / "run_manifest.json", json.dumps(manifest) + "\n"
                )
                summary = json.loads((root / "summary.json").read_text())
                summary.update(summary_update)
                atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
                with self.assertRaisesRegex(
                    ValueError, "evaluation receipt .* manifest"
                ):
                    verify_run(root)

    def test_rejects_receipt_without_proposal_budget_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_id = self._run(root)
            request_path = (
                root / "evaluation_ledger" / "requests" / (request_id + ".json")
            )
            document = json.loads(request_path.read_text(encoding="utf-8"))
            document["request"].pop("proposal_budget")
            atomic_write_text(request_path, json.dumps(document) + "\n")
            with self.assertRaisesRegex(
                ValueError, "request content binding|proposal_budget"
            ):
                verify_run(root)

    def test_blind_and_delayed_modes_reject_online_feedback_metadata(self):
        for feedback_mode in ("selection_blind", "delayed_replay"):
            with self.subTest(feedback_mode=feedback_mode), \
                 tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._run(
                    root, proposal_budget=1, feedback_mode=feedback_mode
                )
                self._proposal(
                    root, score=0.5, accepted=True,
                    recorded_feedback_mode="normal",
                )
                summary = json.loads((root / "summary.json").read_text())
                summary["selection_policy"] = _selection_policy(feedback_mode)
                atomic_write_text(
                    root / "summary.json", json.dumps(summary) + "\n"
                )
                with self.assertRaisesRegex(ValueError, "feedback mode semantics"):
                    verify_run(root)

    def test_verifies_prompt_metric_visibility_for_each_feedback_mode(self):
        for feedback_mode in (
            "normal", "none", "score_only", "shuffled",
            "selection_blind", "delayed_replay",
        ):
            with self.subTest(feedback_mode=feedback_mode), \
                 tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._run(
                    root, proposal_budget=1, feedback_mode=feedback_mode
                )
                self._proposal(root, score=0.5, accepted=True)
                self.assertTrue(verify_run(root)["verified"])

    def test_rejects_prompt_metric_payload_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, proposal_budget=1, feedback_mode="none")
            self._proposal(root, score=0.5, accepted=True)
            events = load_trajectory(root / "trajectory.jsonl")
            events[1]["algorithm_metadata"]["prompt_metrics_sha256"] = "e" * 64
            atomic_write_text(
                root / "trajectory.jsonl",
                "\n".join(json.dumps(event) for event in events) + "\n",
            )
            with self.assertRaisesRegex(ValueError, "feedback mode semantics"):
                verify_run(root)

    def test_rejects_missing_required_manifest_hashes(self):
        for key in (
            "task_contract_sha256",
            "task_package_sha256",
            "runtime_source_sha256",
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._run(root)
                manifest = json.loads((root / "run_manifest.json").read_text())
                manifest.pop(key)
                atomic_write_text(
                    root / "run_manifest.json", json.dumps(manifest) + "\n"
                )
                with self.assertRaisesRegex(ValueError, key):
                    verify_run(root)

    def test_rejects_partial_frontier_manifest_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            manifest = json.loads((root / "run_manifest.json").read_text())
            manifest["task_family_id"] = "ScientificComputing/Example"
            atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
            with self.assertRaisesRegex(ValueError, "frontier binding"):
                verify_run(root)

    def test_rejects_unexpected_request_frontier_binding(self):
        frontier = {
            "task_family_id": "ScientificComputing/Example",
            "wave_id": "wave-1",
            "wave_manifest_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, extra_request_frontier=frontier)
            with self.assertRaisesRegex(ValueError, "frontier binding"):
                verify_run(root)

    def test_rejects_invalid_manifest_identity_values(self):
        cases = {
            "task_id": ("not canonical", "task_id"),
            "seed": (True, "seed"),
            "feedback_mode": ("unknown", "feedback_mode"),
        }
        for key, (value, message) in cases.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._run(root)
                manifest = json.loads((root / "run_manifest.json").read_text())
                manifest[key] = value
                atomic_write_text(
                    root / "run_manifest.json", json.dumps(manifest) + "\n"
                )
                with self.assertRaisesRegex(ValueError, message):
                    verify_run(root)

    def test_rejects_legacy_run_without_trusted_runtime_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            manifest = json.loads((root / "run_manifest.json").read_text())
            manifest.pop("trusted_evaluator_runtime")
            atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
            with self.assertRaisesRegex(ValueError, "trusted runtime descriptor"):
                verify_run(root)

    def test_rejects_request_with_different_trusted_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_id = self._run(root)
            request_path = root / "evaluation_ledger" / "requests" / (request_id + ".json")
            document = json.loads(request_path.read_text(encoding="utf-8"))
            document["request"]["trusted_evaluator_runtime_sha256"] = "d" * 64
            atomic_write_text(request_path, json.dumps(document) + "\n")
            with self.assertRaisesRegex(ValueError, "request content binding|trusted runtime"):
                verify_run(root)

    def test_rejects_runtime_fingerprint_inside_science_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request_id = self._run(root)
            receipt_path = root / "evaluation_ledger" / "receipts" / (request_id + ".json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["metrics"]["trusted_evaluator_runtime_sha256"] = "d" * 64
            receipt["metrics_sha256"] = hashlib.sha256(
                (
                    json.dumps(
                        receipt["metrics"],
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                ).encode("utf-8")
            ).hexdigest()
            atomic_write_text(receipt_path, json.dumps(receipt) + "\n")
            events = load_trajectory(root / "trajectory.jsonl")
            events[0]["metrics"] = receipt["metrics"]
            atomic_write_text(
                root / "trajectory.jsonl",
                "\n".join(json.dumps(event) for event in events) + "\n",
            )
            summary = json.loads((root / "summary.json").read_text())
            summary.update(summarize_trajectory(events, budget=1))
            atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
            with self.assertRaisesRegex(ValueError, "science metrics"):
                verify_run(root)

    def test_expected_trusted_runtime_must_match_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            with self.assertRaisesRegex(ValueError, "externally expected trusted runtime"):
                verify_run(root, expected_trusted_runtime_sha256="d" * 64)

    def test_non_greedy_run_cannot_be_trusted_without_durable_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            manifest = json.loads((root / "run_manifest.json").read_text())
            manifest["algorithm"] = "abmcts"
            atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
            summary = json.loads((root / "summary.json").read_text())
            summary["algorithm"] = "abmcts"
            atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
            with self.assertRaisesRegex(ValueError, "durable per-evaluation receipts"):
                verify_run(root)

    def test_rejects_hand_edited_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary["best_score"] = 99.0
            (root / "summary.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "summary accounting"):
                verify_run(root)

    def test_rejects_receipt_not_referenced_by_the_trajectory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            EvaluationLedger(root).evaluate_once(
                {
                    "kind": "proposal",
                    "task_id": "ScientificComputing/Example",
                    "task_contract_sha256": "a" * 64,
                    "task_package_sha256": "b" * 64,
                    "runtime_source_sha256": "c" * 64,
                    "step": 1,
                    "candidate_sha256": "d" * 64,
                    "parent_sha256": "e" * 64,
                    "prompt_sha256": "f" * 64,
                },
                lambda: {"combined_score": 0.5, "valid": 1.0},
            )
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary["evaluation_ledger_snapshot"] = EvaluationLedger(root).snapshot()
            (root / "summary.json").write_text(
                json.dumps(summary) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "outside the trajectory"):
                verify_run(root)

    def test_rejects_event_score_that_differs_from_receipt_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            event = json.loads(
                (root / "trajectory.jsonl").read_text(encoding="utf-8").strip()
            )
            event["score"] = 0.75
            event["best_score"] = 0.75
            (root / "trajectory.jsonl").write_text(
                json.dumps(event) + "\n", encoding="utf-8"
            )
            rebuilt = summarize_trajectory([event], budget=1)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary.update(rebuilt)
            (root / "summary.json").write_text(
                json.dumps(summary) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "evaluation receipts"):
                verify_run(root)

    def test_rejects_improving_receipt_marked_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, proposal_budget=1)
            self._proposal(root, score=0.5, accepted=False)
            with self.assertRaisesRegex(ValueError, "incumbent state"):
                verify_run(root)

    def test_rejects_oracle_counter_smaller_than_receipt_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, proposal_budget=1)
            self._proposal(root, score=0.5, accepted=True)
            events = load_trajectory(root / "trajectory.jsonl")
            events[1]["oracle_calls"] = 1
            (root / "trajectory.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary.update(summarize_trajectory(events, budget=2))
            (root / "summary.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "accounting differs"):
                verify_run(root)

    def test_equal_score_candidate_cannot_replace_incumbent_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, proposal_budget=1)
            proposal = self._proposal(root, score=0.25, accepted=False)
            atomic_write_text(root / "best_program.py", proposal)
            with self.assertRaisesRegex(ValueError, "replayed incumbent"):
                verify_run(root)

    def test_summary_cannot_redefine_the_frozen_proposal_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root, proposal_budget=1)
            self._proposal(root, score=0.5, accepted=True)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary["budget"] = 0
            (root / "summary.json").write_text(
                json.dumps(summary) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "smaller than its trajectory"):
                verify_run(root)

    def test_summary_cannot_inflate_a_completed_run_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            summary["budget"] = 10
            atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
            with self.assertRaisesRegex(ValueError, "early termination|completed budget"):
                verify_run(root)

    def test_release_verification_binds_external_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._run(root)
            with self.assertRaisesRegex(ValueError, "externally expected budget"):
                verify_run(root, expected_budget=1)


if __name__ == "__main__":
    unittest.main()
