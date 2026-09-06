from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sle.algorithms import common
from sle.evaluation_ledger import EvaluationLedger
from sle.frontier import (
    FrontierLedger,
    FrozenWave,
    load_frozen_wave,
    promote_frontier_receipt,
    validate_family_waves,
)
from sle.protocol import TrajectoryEvent, append_event, sha256_text, summarize_trajectory
from sle.runtime_identity import TrustedRuntime, current_runtime_descriptor


TRUSTED_RUNTIME = current_runtime_descriptor(())
TRUSTED_RUNTIME_SHA256 = TRUSTED_RUNTIME["fingerprint_sha256"]


def _wave(
    wave_id: str = "wave-1",
    *,
    predecessor: str | None = None,
) -> FrozenWave:
    def cell(**values):
        values["semantic_contract"] = {
            "canonicalizer_id": "example-canonicalizer-v1",
            "canonicalizer_path": "frontier_eval/contracts/canonicalizer.py",
            "canonicalizer_sha256": "4" * 64,
            "evidence_predicate_id": "example-evidence-v1",
            "evidence_predicate_path": "frontier_eval/contracts/predicate.py",
            "evidence_predicate_sha256": "5" * 64,
            "evaluation_panel_path": "frontier_eval/contracts/panel.json",
            "evaluation_panel_sha256": "6" * 64,
            "oracle_path": "verification/evaluator.py",
            "oracle_sha256": "7" * 64,
        }
        payload = json.dumps(
            values, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8") + b"\n"
        return {
            **values,
            "definition_sha256": hashlib.sha256(payload).hexdigest(),
        }

    cells = {
            "solver": cell(**{
                "id": "solver",
                "kind": "optimization",
                "weight": 2.0,
                "objective": "maximize",
                "reference_value": 10.0,
                "credit_scale": 5.0,
                "minimum_delta": 0.5,
            }),
            "claims": cell(**{
                "id": "claims",
                "kind": "discovery",
                "weight": 3.0,
                "credit_per_claim": 0.25,
                "novelty_namespace": "ScientificComputing/Example/claims-v1",
            }),
    }
    semantic = {
        "schema_version": 1,
        "task_family_id": "ScientificComputing/Example",
        "wave_id": wave_id,
        "predecessor_wave_sha256": predecessor,
        "cells": [cells[key] for key in sorted(cells)],
    }
    payload = json.dumps(
        semantic, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8") + b"\n"
    return FrozenWave(
        task_family_id="ScientificComputing/Example",
        wave_id=wave_id,
        manifest_sha256=hashlib.sha256(payload).hexdigest(),
        predecessor_wave_sha256=predecessor,
        cells=cells,
    )


def _record(
    ledger: FrontierLedger,
    evidence: EvaluationLedger,
    wave: FrozenWave,
    *,
    artifact: str,
    records: list[dict],
    valid: float = 1.0,
    contract_hash: str = "a" * 64,
    package_hash: str = "b" * 64,
    runtime_hash: str = "c" * 64,
    trusted_runtime_hash: str = TRUSTED_RUNTIME_SHA256,
):
    receipt = evidence.evaluate_once(
        {
            "kind": "proposal",
            "task_id": wave.task_family_id,
            **wave.binding(),
            "task_contract_sha256": contract_hash,
            "task_package_sha256": package_hash,
            "runtime_source_sha256": runtime_hash,
            "trusted_evaluator_runtime_sha256": trusted_runtime_hash,
            "candidate_sha256": artifact,
        },
        lambda: {
            "combined_score": 0.0,
            "valid": valid,
            "frontier_records": records,
        },
    )
    verified = {
        "verified": True,
        "verified_request_ids": [receipt["request_id"]],
        "verified_receipt_metrics_sha256": {
            receipt["request_id"]: receipt["metrics_sha256"]
        },
        "trusted_evaluator_runtime_sha256": trusted_runtime_hash,
    }
    return ledger._record_verified(
        wave,
        evaluation_ledger=evidence,
        request_id=receipt["request_id"],
        verified_run=verified,
    )


class FrozenWaveTests(unittest.TestCase):
    def _spec(self, root: Path):
        eval_dir = root / "frontier_eval"
        eval_dir.mkdir(parents=True)
        contract_dir = eval_dir / "contracts"
        contract_dir.mkdir()
        artifacts = {
            "canonicalizer.py": b"canonicalizer-v1\n",
            "predicate.py": b"predicate-v1\n",
            "panel.json": b"{}\n",
            "evaluator.py": b"oracle-v1\n",
        }
        hashes = {}
        for name, payload in artifacts.items():
            destination = (
                root / "verification" / name
                if name == "evaluator.py"
                else contract_dir / name
            )
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(payload)
            hashes[name] = hashlib.sha256(payload).hexdigest()
        (eval_dir / "wave.yaml").write_text(
            f"""schema_version: 1
task_family_id: ScientificComputing/Example
wave_id: wave-1
predecessor_wave_sha256: null
cells:
  - id: solver
    kind: optimization
    weight: 2
    objective: maximize
    reference_value: 10
    credit_scale: 5
    minimum_delta: 0.5
    semantic_contract:
      canonicalizer_id: example-canonicalizer-v1
      canonicalizer_path: frontier_eval/contracts/canonicalizer.py
      canonicalizer_sha256: "{hashes['canonicalizer.py']}"
      evidence_predicate_id: example-evidence-v1
      evidence_predicate_path: frontier_eval/contracts/predicate.py
      evidence_predicate_sha256: "{hashes['predicate.py']}"
      evaluation_panel_path: frontier_eval/contracts/panel.json
      evaluation_panel_sha256: "{hashes['panel.json']}"
      oracle_path: verification/evaluator.py
      oracle_sha256: "{hashes['evaluator.py']}"
""",
            encoding="utf-8",
        )
        return SimpleNamespace(
            task_id="ScientificComputing/Example",
            task_dir=root,
            eval_dir=eval_dir,
            metadata={
                "task_family_id": "ScientificComputing/Example",
                "wave_id": "wave-1",
                "scientific_role": "optimization",
            },
        )

    def test_manifest_is_loaded_and_content_hashed(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = self._spec(Path(temporary))
            wave = load_frozen_wave(spec)
            self.assertEqual(wave.task_family_id, spec.task_id)
            self.assertEqual(wave.wave_id, "wave-1")
            self.assertEqual(len(wave.manifest_sha256), 64)
            self.assertEqual(wave.cells["solver"]["reference_value"], 10.0)

    def test_opt_in_metadata_requires_a_matching_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = self._spec(Path(temporary))
            spec.metadata["wave_id"] = "wave-2"
            with self.assertRaisesRegex(ValueError, "wave_id"):
                load_frozen_wave(spec)

    def test_semantic_contract_hashes_bind_repository_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = self._spec(Path(temporary))
            (spec.task_dir / "frontier_eval/contracts/panel.json").write_text(
                '{"changed":true}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "artifact hash differs"):
                load_frozen_wave(spec)

    def test_semantic_contract_binds_declared_evaluator_entrypoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            spec = self._spec(Path(temporary))
            (spec.task_dir / "verification/evaluator.py").write_text(
                "changed-oracle\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "artifact hash differs"):
                load_frozen_wave(spec)

    def test_legacy_task_without_family_metadata_has_no_wave(self):
        spec = SimpleNamespace(
            task_id="Chemistry/Legacy",
            eval_dir=Path("/definitely/missing"),
            metadata={},
        )
        self.assertIsNone(load_frozen_wave(spec))

    def test_explicit_empty_family_metadata_is_rejected(self):
        spec = SimpleNamespace(
            task_id="Chemistry/Legacy",
            eval_dir=Path("/definitely/missing"),
            metadata={"task_family_id": ""},
        )
        with self.assertRaisesRegex(ValueError, "wave.yaml"):
            load_frozen_wave(spec)

    def test_family_registry_rejects_forks_and_missing_predecessors(self):
        first = _wave()
        child = _wave("wave-2", predecessor=first.manifest_sha256)
        fork = _wave("wave-3", predecessor=first.manifest_sha256)
        specs = [SimpleNamespace(task_id="a"), SimpleNamespace(task_id="b")]
        with patch("sle.frontier.load_frozen_wave", side_effect=[first, child]):
            self.assertEqual(validate_family_waves(specs), [])
        with patch("sle.frontier.load_frozen_wave", side_effect=[first, child, fork]):
            issues = validate_family_waves(specs + [SimpleNamespace(task_id="c")])
        self.assertTrue(any("fork" in issue for issue in issues))
        orphan = _wave("wave-2", predecessor="9" * 64)
        with patch("sle.frontier.load_frozen_wave", return_value=orphan):
            issues = validate_family_waves([SimpleNamespace(task_id="orphan")])
        self.assertTrue(any("missing predecessor" in issue for issue in issues))

    def test_run_manifest_binds_opted_in_family_and_wave(self):
        class Client:
            config = SimpleNamespace(
                wire="chat", base_url="https://example.invalid/v1", model="fixture",
                max_output_tokens=1, temperature=0, reasoning_effort=None,
                timeout_seconds=1, extra_headers={}, input_cost_per_million=None,
                output_cost_per_million=None,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self._spec(root / "task")
            workdir = root / "run"
            workdir.mkdir()
            with patch.object(common, "task_contract_sha256", return_value="b" * 64), \
                 patch.object(common, "task_package_sha256", return_value="c" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="d" * 64):
                manifest = common.ensure_run_manifest(
                    workdir, spec=spec, llm=Client(), algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=False,
                )
            self.assertEqual(manifest["task_family_id"], spec.task_id)
            self.assertEqual(manifest["wave_id"], "wave-1")
            self.assertEqual(len(manifest["wave_manifest_sha256"]), 64)
            unsupported = root / "unsupported"
            unsupported.mkdir()
            with patch.object(common, "task_contract_sha256", return_value="b" * 64), \
                 patch.object(common, "task_package_sha256", return_value="c" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="d" * 64), \
                 self.assertRaisesRegex(ValueError, "evaluation receipts"):
                common.ensure_run_manifest(
                    unsupported, spec=spec, llm=Client(), algorithm="abmcts",
                    seed=0, feedback_mode="normal", resume=False,
                )

    def test_promotion_rejects_receipt_outside_a_verified_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self._spec(root / "task")
            wave = load_frozen_wave(spec)
            run = root / "run"
            run.mkdir()
            frozen = {
                "schema_version": 1,
                "algorithm": "greedy_rewrite",
                "task_id": spec.task_id,
                "task_contract_sha256": "a" * 64,
                "task_package_sha256": "b" * 64,
                "runtime_source_sha256": "c" * 64,
                "trusted_evaluator_runtime": TRUSTED_RUNTIME,
                "seed": 0,
                "feedback_mode": "normal",
                "llm_condition_sha256": "d" * 64,
                "llm_condition": {"model": "test-model"},
                **wave.binding(),
            }
            (run / "run_manifest.json").write_text(
                json.dumps(frozen) + "\n", encoding="utf-8"
            )
            receipt = EvaluationLedger(run).evaluate_once(
                {
                    **frozen,
                    "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
                    "kind": "proposal",
                    "proposal_budget": 0,
                    "candidate_sha256": "d" * 64,
                },
                lambda: {"combined_score": 0.0, "valid": 1.0,
                         "frontier_records": []},
            )
            with patch.object(common, "task_contract_sha256", return_value="a" * 64), \
                 patch.object(common, "task_package_sha256", return_value="b" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="c" * 64), \
                 patch("sle.evaluate.resolve_trusted_runtime", return_value=TrustedRuntime("python", TRUSTED_RUNTIME)), \
                 self.assertRaisesRegex(ValueError, "run lacks a valid"):
                promote_frontier_receipt(
                    spec,
                    run_workdir=run,
                    ledger_root=root / "canonical",
                    request_id=receipt["request_id"],
                )

    def test_promotion_accepts_a_receipt_in_a_verified_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self._spec(root / "task")
            wave = load_frozen_wave(spec)
            run = root / "run"
            run.mkdir()
            program = "def solve():\n    return 1\n"
            candidate_hash = sha256_text(program)
            frozen = {
                "schema_version": 1,
                "algorithm": "greedy_rewrite",
                "task_id": spec.task_id,
                "task_contract_sha256": "a" * 64,
                "task_package_sha256": "b" * 64,
                "runtime_source_sha256": "c" * 64,
                "trusted_evaluator_runtime": TRUSTED_RUNTIME,
                "seed": 0,
                "feedback_mode": "normal",
                "llm_condition_sha256": "d" * 64,
                "llm_condition": {"model": "test-model"},
                **wave.binding(),
            }
            (run / "run_manifest.json").write_text(
                json.dumps(frozen) + "\n", encoding="utf-8"
            )
            receipt = EvaluationLedger(run).evaluate_once(
                {
                    **{key: frozen[key] for key in (
                        "algorithm", "task_id", "task_contract_sha256",
                        "task_package_sha256", "runtime_source_sha256", "seed",
                        "feedback_mode", "llm_condition_sha256", "llm_condition",
                        "task_family_id", "wave_id", "wave_manifest_sha256",
                    )},
                    "kind": "baseline",
                    "proposal_budget": 0,
                    "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
                    "step": 0,
                    "candidate_sha256": candidate_hash,
                },
                lambda: {"combined_score": 0.0, "valid": 1.0,
                         "frontier_records": []},
            )
            event = TrajectoryEvent(
                step=0, oracle_calls=1, score=0.0, best_score=0.0,
                valid=True, accepted=True,
                wall_seconds=receipt["evaluation_wall_seconds"],
                cumulative_wall_seconds=receipt["evaluation_wall_seconds"],
                candidate_sha256=candidate_hash, parent_sha256=None,
                budget_units=1, metrics=receipt["metrics"],
                algorithm_metadata={"evaluation_request_id": receipt["request_id"]},
            )
            append_event(run / "trajectory.jsonl", event)
            summary = summarize_trajectory([event.to_dict()], budget=1)
            summary.update({
                "algorithm": "greedy_rewrite", "task_id": spec.task_id,
                "seed": 0, "feedback_mode": "normal", "budget": 0,
                "selection_policy": "online_incumbent",
                "baseline_score": 0.0,
                "evaluation_ledger_snapshot": EvaluationLedger(run).snapshot(),
            })
            (run / "summary.json").write_text(
                json.dumps(summary) + "\n", encoding="utf-8"
            )
            (run / "best_program.py").write_text(program, encoding="utf-8")
            with patch.object(common, "task_contract_sha256", return_value="a" * 64), \
                 patch.object(common, "task_package_sha256", return_value="b" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="c" * 64), \
                 patch("sle.evaluate.resolve_trusted_runtime", return_value=TrustedRuntime("python", TRUSTED_RUNTIME)):
                decision = promote_frontier_receipt(
                    spec, run_workdir=run, ledger_root=root / "canonical",
                    request_id=receipt["request_id"],
                )
            self.assertEqual(decision["credit_delta"], 0.0)


class FrontierLedgerTests(unittest.TestCase):
    def test_public_record_cannot_bypass_run_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "unverified")
            with self.assertRaisesRegex(ValueError, "promote_frontier_receipt"):
                ledger.record(
                    _wave(), evaluation_ledger=evidence, request_id="d" * 64
                )

    def test_optimization_credits_only_verified_marginal_frontier_gain(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "verified")
            first = _record(
                ledger, evidence, _wave(), artifact="d" * 64,
                records=[{"cell_id": "solver", "canonical_id": "method-a", "value": 12.5}],
            )
            below_delta = _record(
                ledger, evidence, _wave(), artifact="e" * 64,
                records=[{"cell_id": "solver", "canonical_id": "method-b", "value": 12.9}],
            )
            second = _record(
                ledger, evidence, _wave(), artifact="f" * 64,
                records=[{"cell_id": "solver", "canonical_id": "method-c", "value": 15.0}],
            )
            snapshot = ledger.snapshot()

        self.assertAlmostEqual(first["credit_delta"], 1.0)
        self.assertEqual(below_delta["credit_delta"], 0.0)
        self.assertAlmostEqual(second["credit_delta"], 1.0)
        self.assertAlmostEqual(snapshot["lifetime_credit"], 2.0)
        self.assertEqual(snapshot["optimization_frontiers"]["ScientificComputing/Example|solver"], 15.0)

    def test_discovery_claims_are_canonicalized_and_never_double_counted(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "verified")
            first = _record(
                ledger, evidence, _wave(), artifact="d" * 64,
                records=[
                    {"cell_id": "claims", "canonical_id": "edge:A>B"},
                    {"cell_id": "claims", "canonical_id": "edge:B>C"},
                ],
            )
            duplicate = _record(
                ledger, evidence, _wave(), artifact="e" * 64,
                records=[{"cell_id": "claims", "canonical_id": "edge:A>B"}],
            )
            snapshot = ledger.snapshot()

        self.assertAlmostEqual(first["credit_delta"], 1.5)
        self.assertEqual(duplicate["credit_delta"], 0.0)
        self.assertEqual(snapshot["unique_discovery_count"], 2)

    def test_new_wave_must_extend_the_recorded_manifest_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "verified")
            first_wave = _wave()
            _record(
                ledger, evidence, first_wave, artifact="d" * 64, records=[]
            )
            bad = _wave("wave-2", predecessor="9" * 64)
            with self.assertRaisesRegex(ValueError, "predecessor"):
                _record(
                    ledger, evidence, bad, artifact="0" * 64, records=[]
                )
            good = _wave(
                "wave-2", predecessor=first_wave.manifest_sha256
            )
            _record(
                ledger, evidence, good, artifact="1" * 64, records=[]
            )
            self.assertEqual(ledger.snapshot()["wave_count"], 2)

    def test_same_wave_freezes_all_task_and_runtime_evidence_bindings(self):
        changes = {
            "task contract": {"contract_hash": "9" * 64},
            "task package": {"package_hash": "9" * 64},
            "runtime source": {"runtime_hash": "9" * 64},
            "trusted runtime": {"trusted_runtime_hash": "9" * 64},
        }
        for label, changed in changes.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                ledger = FrontierLedger(root)
                evidence = EvaluationLedger(root / "verified")
                _record(ledger, evidence, _wave(), artifact="d" * 64, records=[])
                with self.assertRaisesRegex(ValueError, "immutable wave evidence"):
                    _record(
                        ledger,
                        evidence,
                        _wave(),
                        artifact="e" * 64,
                        records=[],
                        **changed,
                    )

    def test_legacy_event_schema_is_read_only_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = FrontierLedger(root)
            evidence = EvaluationLedger(root / "verified")
            _record(ledger, evidence, _wave(), artifact="d" * 64, records=[])
            path = root / "frontier_ledger" / "events" / "00000000.json"
            event = json.loads(path.read_text(encoding="utf-8"))
            event["schema_version"] = 1
            payload = {key: value for key, value in event.items() if key != "event_sha256"}
            event["event_sha256"] = hashlib.sha256(
                (
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                ).encode("utf-8")
            ).hexdigest()
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "event schema"):
                ledger.snapshot()

    def test_tampered_append_only_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = FrontierLedger(root)
            evidence = EvaluationLedger(root / "verified")
            _record(
                ledger, evidence, _wave(), artifact="d" * 64, records=[]
            )
            path = root / "frontier_ledger" / "events" / "00000000.json"
            event = json.loads(path.read_text(encoding="utf-8"))
            event["credit_delta"] = 1000.0
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "event hash"):
                FrontierLedger(root).snapshot()

    def test_direct_wave_objects_cannot_lie_about_cell_semantics(self):
        wave = _wave()
        wave.cells["solver"]["weight"] = 200.0
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "verified")
            with self.assertRaisesRegex(ValueError, "definition_sha256"):
                _record(
                    ledger, evidence, wave, artifact="d" * 64, records=[]
                )

    def test_invalid_evaluation_receipt_cannot_mint_credit(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = FrontierLedger(Path(temporary))
            evidence = EvaluationLedger(Path(temporary) / "verified")
            with self.assertRaisesRegex(ValueError, "valid evaluator result"):
                _record(
                    ledger, evidence, _wave(), artifact="d" * 64,
                    records=[{"cell_id": "claims", "canonical_id": "fake"}],
                    valid=0.0,
                )
            self.assertEqual(ledger.snapshot()["event_count"], 0)

    def test_same_receipt_is_idempotent_and_conflicting_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = FrontierLedger(root)
            evidence = EvaluationLedger(root / "verified")
            wave = _wave()
            receipt = evidence.evaluate_once(
                {
                    "kind": "proposal",
                    "task_id": wave.task_family_id,
                    **wave.binding(),
                    "task_contract_sha256": "a" * 64,
                    "task_package_sha256": "b" * 64,
                    "runtime_source_sha256": "c" * 64,
                    "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
                    "candidate_sha256": "d" * 64,
                },
                lambda: {
                    "combined_score": 0.0,
                    "valid": 1.0,
                    "frontier_records": [
                        {"cell_id": "claims", "canonical_id": "edge:A>B"}
                    ],
                },
            )
            verified = {
                "verified": True,
                "verified_request_ids": [receipt["request_id"]],
                "verified_receipt_metrics_sha256": {
                    receipt["request_id"]: receipt["metrics_sha256"]
                },
                "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
            }
            first = ledger._record_verified(
                wave, evaluation_ledger=evidence, request_id=receipt["request_id"],
                verified_run=verified,
            )
            repeated = ledger._record_verified(
                wave, evaluation_ledger=evidence, request_id=receipt["request_id"],
                verified_run=verified,
            )
            self.assertFalse(first["receipt_reused"])
            self.assertTrue(repeated["receipt_reused"])
            self.assertEqual(ledger.snapshot()["event_count"], 1)

            conflicting = EvaluationLedger(root / "conflicting")
            conflicting.evaluate_once(
                {
                    "kind": "proposal",
                    "task_id": wave.task_family_id,
                    **wave.binding(),
                    "task_contract_sha256": "a" * 64,
                    "task_package_sha256": "b" * 64,
                    "runtime_source_sha256": "c" * 64,
                    "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
                    "candidate_sha256": "d" * 64,
                },
                lambda: {
                    "combined_score": 0.0,
                    "valid": 1.0,
                    "frontier_records": [
                        {"cell_id": "claims", "canonical_id": "edge:B>C"}
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "differs from verified run"):
                ledger._record_verified(
                    wave,
                    evaluation_ledger=conflicting,
                    request_id=receipt["request_id"],
                    verified_run=verified,
                )

    def test_same_artifact_cannot_change_its_canonical_record_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = FrontierLedger(root)
            wave = _wave()
            first = EvaluationLedger(root / "first")
            second = EvaluationLedger(root / "second")
            _record(
                ledger, first, wave, artifact="d" * 64,
                records=[{"cell_id": "claims", "canonical_id": "edge:A>B"}],
            )
            receipt = second.evaluate_once(
                {
                    "kind": "proposal",
                    "task_id": wave.task_family_id,
                    **wave.binding(),
                    "task_contract_sha256": "a" * 64,
                    "task_package_sha256": "b" * 64,
                    "runtime_source_sha256": "c" * 64,
                    "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
                    "candidate_sha256": "d" * 64,
                    "step": 2,
                },
                lambda: {
                    "combined_score": 0.0,
                    "valid": 1.0,
                    "frontier_records": [
                        {"cell_id": "claims", "canonical_id": "edge:B>C"}
                    ],
                },
            )
            verified = {
                "verified": True,
                "verified_request_ids": [receipt["request_id"]],
                "verified_receipt_metrics_sha256": {
                    receipt["request_id"]: receipt["metrics_sha256"]
                },
                "trusted_evaluator_runtime_sha256": TRUSTED_RUNTIME_SHA256,
            }
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                ledger._record_verified(
                    wave, evaluation_ledger=second, request_id=receipt["request_id"],
                    verified_run=verified,
                )


if __name__ == "__main__":
    unittest.main()
