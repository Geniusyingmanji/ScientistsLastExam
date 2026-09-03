from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sle.algorithms.common import (
    llm_condition_sha256,
    runtime_source_sha256,
    task_contract_sha256,
)
from sle.algorithms.evolve import greedy_rewrite
from sle.llm import LLMConfig
from sle.protocol import compact_trajectory_snapshot
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_track_f_confirmation.py"
SPEC = importlib.util.spec_from_file_location(
    "track_f_confirmation_runner_for_test", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


TASK = "Fixture/Task"
MODES = tuple(MODULE.EXPECTED_MODES)


def _event(step: int, score: float, best: float, source: str, tokens: int) -> dict:
    return {
        "schema_version": 2,
        "step": step,
        "oracle_calls": step + 1,
        "budget_units": step + 1,
        "score": score,
        "best_score": best,
        "valid": True,
        "accepted": step == 0 or score == best,
        "wall_seconds": 1.0,
        "cumulative_wall_seconds": float(step + 1),
        "candidate_sha256": MODULE.sha256_text(source),
        "parent_sha256": None if step == 0 else "parent",
        "metrics": {"combined_score": score, "valid": 1.0},
        "llm": {} if step == 0 else {
            "input_tokens": tokens // 2,
            "output_tokens": tokens - tokens // 2,
            "total_tokens": tokens,
        },
        "error": None,
        "algorithm_metadata": {},
    }


def _cell(mode: str, proposal_tokens: int, *, shared_source: bool = False) -> dict:
    prefix = "shared" if shared_source else mode
    sources = {
        0: "def solve(): return 'baseline'\n",
        1: "def solve(): return %r\n" % (prefix + "-one"),
        2: "def solve(): return %r\n" % (prefix + "-two"),
        3: "def solve(): return %r\n" % (prefix + "-three"),
    }
    scores = (0.0, 0.1, 0.2, 0.3)
    events = [
        _event(
            step,
            scores[step],
            scores[step],
            sources[step],
            0 if step == 0 else proposal_tokens,
        )
        for step in range(4)
    ]
    return {
        "task": TASK,
        "condition": mode,
        "replicate_id": 0,
        "events": events,
        "sources": sources,
        "total_tokens": proposal_tokens * 3,
    }


def _context() -> dict:
    return {
        "schema_version": 1,
        "purpose": "fresh_confirmation",
        "task_id": TASK,
        "generator": "fixture_v1",
        "panel_id": "fixture-r0",
        "master_seed": 123,
        "world_count": 1,
    }


class TrackFConfirmationRunnerTests(unittest.TestCase):
    class FakeLLM:
        def __init__(self, source: str):
            self.source = source
            self.last_usage = {}
            self.config = LLMConfig(
                wire="chat", base_url="https://example.invalid/v1",
                model="fixture", max_output_tokens=20, temperature=0.0,
                timeout_seconds=1,
            )

        def complete(self, _prompt, system=None):
            self.last_usage = {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "estimated_cost_usd": None,
            }
            return "```python\n%s\n```" % self.source

    def test_endpoint_plan_uses_common_completed_token_horizon_and_deduplicates(self):
        cells = [
            _cell("normal", 10),
            _cell("score_only", 8),
            _cell("delayed_replay", 6),
            _cell("selection_blind", 5),
        ]
        endpoints, evaluations, sources = MODULE._build_endpoint_plan(
            cells, {(TASK, 0): _context()}, budget=3,
            confirmation_replays=2, confirmation_randomization_seed=81237,
        )
        self.assertEqual(len(endpoints), 8)
        self.assertEqual({row["common_total_token_horizon"] for row in endpoints}, {15})
        by_endpoint = {
            (row["condition"], row["endpoint"]): row for row in endpoints
        }
        self.assertEqual(
            by_endpoint[("normal", "common_total_token_horizon")][
                "completed_through_step"
            ],
            1,
        )
        self.assertEqual(
            by_endpoint[("score_only", "common_total_token_horizon")][
                "completed_through_step"
            ],
            1,
        )
        self.assertEqual(
            by_endpoint[("delayed_replay", "common_total_token_horizon")][
                "completed_through_step"
            ],
            2,
        )
        self.assertEqual(
            by_endpoint[("selection_blind", "common_total_token_horizon")][
                "completed_through_step"
            ],
            3,
        )
        # Selection-blind full and token endpoints reuse one artifact. Seven
        # unique artifacts each receive two independent deterministic replays.
        self.assertEqual(len(sources), 7)
        self.assertEqual(len(evaluations), 14)
        counts = {}
        for row in evaluations:
            counts[row["artifact_id"]] = counts.get(row["artifact_id"], 0) + 1
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(
            {
                row["replay_index"] for row in evaluations
            },
            {0, 1},
        )
        midpoint = len(evaluations) // 2
        self.assertEqual(
            [row["artifact_id"] for row in evaluations[:midpoint]],
            [row["artifact_id"] for row in evaluations[midpoint:]],
        )
        self.assertEqual(
            {row["replay_index"] for row in evaluations[:midpoint]}, {0}
        )
        self.assertEqual(
            {row["replay_index"] for row in evaluations[midpoint:]}, {1}
        )

    def test_confirmation_reconstructs_randomized_williams_schedule(self):
        replicates = list(range(48))
        first = MODULE._reconstruct_condition_schedule(replicates, 834721)
        repeated = MODULE._reconstruct_condition_schedule(replicates, 834721)
        changed = MODULE._reconstruct_condition_schedule(replicates, 834722)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)
        self.assertEqual(
            [row["replicate_identifier"] for row in first], replicates
        )
        rows = [row["feedback_modes"] for row in first]
        for position in range(4):
            self.assertEqual(
                {mode: sum(row[position] == mode for row in rows) for mode in MODES},
                {mode: 12 for mode in MODES},
            )
        # Equality of a preregistration and search copy is insufficient: an
        # edited row must differ from the seed-derived schedule.
        tampered = json.loads(json.dumps(first))
        tampered[0]["feedback_modes"] = list(reversed(
            tampered[0]["feedback_modes"]
        ))
        self.assertNotEqual(tampered, first)
        with self.assertRaisesRegex(ValueError, "Williams"):
            MODULE._reconstruct_condition_schedule([0, 0], 1)

    def test_strict_observer_selection_keeps_first_tie_and_ignores_invalid(self):
        events = [
            _event(0, 0.0, 0.0, "b", 0),
            _event(1, 0.4, 0.4, "one", 4),
            _event(2, 0.4, 0.4, "two", 4),
            _event(3, 0.9, 0.4, "three", 4),
        ]
        events[3]["valid"] = False
        self.assertEqual(MODULE._observer_best_step(events, 3), 1)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_real_retained_run_reconstructs_prompt_lineage_and_selection(self):
        spec = find_task(
            "DynamicalSystems/ActiveLawDiscovery", include_uncertified=True
        )
        baseline = spec.initial_program_path.read_text(encoding="utf-8")
        llm = self.FakeLLM(baseline)
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary) / "runs" / spec.task_id.replace("/", "__")
            workdir = workdir / "greedy_rewrite" / "normal" / "seed_0"
            result = greedy_rewrite(
                spec,
                llm,
                budget=1,
                timeout_s=90,
                workdir=workdir,
                seed=0,
                feedback_mode="normal",
                log_fn=lambda _line: None,
            )
            run = {
                "task": spec.task_id,
                "algorithm": "greedy_rewrite",
                "feedback_mode": "normal",
                "seed": 0,
                "baseline": result.baseline_score,
                "best": result.best_score,
                "accepted": result.accepted,
                "evaluated": result.evaluated,
                "workdir": str(workdir),
                "summary": result.summary,
                "trajectory_snapshot": compact_trajectory_snapshot(
                    workdir / "trajectory.jsonl", schema_version=2
                ),
                "execution_block_index": 1,
                "within_block_position": 1,
            }
            config = {
                "work_root": str(Path(temporary) / "runs"),
                "llm_condition_sha256": llm_condition_sha256(llm),
            }
            source_binding = {
                "runtime_source_sha256": runtime_source_sha256(),
                "tasks": [{
                    "task": spec.task_id,
                    "task_contract_sha256": task_contract_sha256(spec),
                }],
            }
            loaded = MODULE._load_cell(run, config, source_binding, budget=1)
        self.assertEqual(loaded["total_tokens"], 15)
        self.assertEqual(loaded["treatment_lineage"]["selection_policy"], "online_incumbent")
        self.assertEqual(len(loaded["treatment_lineage"]["records"]), 1)
        self.assertEqual(MODULE._observer_best_step(loaded["events"], 1), 0)
        self.assertEqual(loaded["sources"][0], baseline)
        self.assertEqual(loaded["sources"][1].rstrip(), baseline.rstrip())
        self.assertNotEqual(
            MODULE.sha256_text(loaded["sources"][1]),
            MODULE.sha256_text(baseline),
        )

        tampered = json.loads(json.dumps(loaded["events"]))
        tampered[1]["algorithm_metadata"]["prompt_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "prompt/lineage"):
            MODULE._validate_treatment_lineage(
                tampered,
                loaded["sources"],
                spec,
                "normal",
                1,
            )

        pending_checkpoint = {
            "pending_proposal": {"schema_version": 1},
            "evaluated_candidates": [{
                "step": 0,
                "program": baseline,
                "sha256": MODULE.sha256_text(baseline),
                "score": loaded["events"][0]["score"],
                "valid": loaded["events"][0]["valid"],
                "metrics": MODULE.search_visible_metrics(
                    loaded["events"][0]["metrics"]
                ),
            }],
        }
        with self.assertRaisesRegex(ValueError, "pending proposal"):
            MODULE._source_rows(
                loaded["events"][:1], pending_checkpoint, baseline
            )

    def _context_artifact_fixture(self, root: Path):
        root_entropy = "31" * 32
        message = (
            "frontier-science-track-f-confirmation-v1\0%s\0%d" % (TASK, 0)
        ).encode("utf-8")
        master_seed = int.from_bytes(
            hmac.new(bytes.fromhex(root_entropy), message, hashlib.sha256).digest()[:8],
            "big",
        ) & ((1 << 63) - 1)
        context = {
            **_context(),
            "master_seed": master_seed,
        }
        context_payload = MODULE.canonical_trusted_context(context)
        context_sha = hashlib.sha256(context_payload).hexdigest()
        source_binding = {
            "git_revision": "a" * 40,
            "runtime_source_sha256": "b" * 64,
            "tasks": [{
                "task": TASK,
                "task_contract_sha256": "c" * 64,
                "generator": "fixture_v1",
                "world_count": 1,
            }],
        }
        private = {
            "schema_version": 1,
            "purpose": "track_f_private_fresh_confirmation_contexts",
            "cohort_id": "fixture",
            "root_entropy_hex": root_entropy,
            "source_binding": source_binding,
            "blocks": [{
                "task": TASK,
                "replicate_id": 0,
                "context_sha256": context_sha,
                "context": context,
            }],
        }
        private_path = root / "private.json"
        private_payload = (
            json.dumps(private, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        private_path.write_bytes(private_payload)
        private_path.chmod(0o600)
        public = {
            "schema_version": 1,
            "commitment_version": 1,
            "purpose": "track_f_fresh_confirmation_context_commitment",
            "cohort_id": "fixture",
            "source_binding": source_binding,
            "private_manifest_sha256": hashlib.sha256(private_payload).hexdigest(),
            "block_count": 1,
            "blocks": [{
                "task": TASK,
                "replicate_id": 0,
                "panel_id": context["panel_id"],
                "generator": context["generator"],
                "world_count": 1,
                "context_sha256": context_sha,
                "context_utf8_bytes": len(context_payload),
            }],
        }
        public_path = root / "public.json"
        public_path.write_text(json.dumps(public) + "\n", encoding="utf-8")
        preregistration = {
            "confirmation_commitment": {
                "sha256": hashlib.sha256(public_path.read_bytes()).hexdigest(),
                "private_manifest_sha256": hashlib.sha256(private_payload).hexdigest(),
                "block_count": 1,
            },
        }
        return private_path, public_path, preregistration, source_binding

    def test_private_public_context_bindings_and_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_path, public_path, prereg, source_binding = (
                self._context_artifact_fixture(root)
            )
            with patch.object(
                MODULE, "_source_equivalent", return_value=True
            ), patch.object(
                MODULE, "_load_oracle_auditor",
                return_value=lambda _context: {"passed": True},
            ):
                contexts, public, audits = MODULE._validate_context_artifacts(
                    private_path,
                    public_path,
                    prereg,
                    [TASK],
                    [0],
                    source_binding,
                )
                self.assertEqual(set(contexts), {(TASK, 0)})
                self.assertEqual(public["block_count"], 1)
                self.assertEqual(len(audits), 1)

                private_path.chmod(0o644)
                with self.assertRaisesRegex(ValueError, "permissions"):
                    MODULE._validate_context_artifacts(
                        private_path, public_path, prereg, [TASK], [0], source_binding
                    )
                private_path.chmod(0o600)

                changed = json.loads(public_path.read_text(encoding="utf-8"))
                changed["blocks"][0]["context_sha256"] = "0" * 64
                public_path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
                prereg["confirmation_commitment"]["sha256"] = hashlib.sha256(
                    public_path.read_bytes()
                ).hexdigest()
                with self.assertRaisesRegex(ValueError, "context binding"):
                    MODULE._validate_context_artifacts(
                        private_path, public_path, prereg, [TASK], [0], source_binding
                    )

    def test_duplicate_private_context_block_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_path, public_path, prereg, source_binding = (
                self._context_artifact_fixture(root)
            )
            private = json.loads(private_path.read_text(encoding="utf-8"))
            private["blocks"].append(json.loads(json.dumps(private["blocks"][0])))
            payload = (json.dumps(private, indent=2, sort_keys=True) + "\n").encode("utf-8")
            private_path.write_bytes(payload)
            private_path.chmod(0o600)
            public = json.loads(public_path.read_text(encoding="utf-8"))
            public["private_manifest_sha256"] = hashlib.sha256(payload).hexdigest()
            public_path.write_text(json.dumps(public) + "\n", encoding="utf-8")
            prereg["confirmation_commitment"].update({
                "sha256": hashlib.sha256(public_path.read_bytes()).hexdigest(),
                "private_manifest_sha256": hashlib.sha256(payload).hexdigest(),
            })
            with patch.object(
                MODULE, "_source_equivalent", return_value=True
            ), self.assertRaisesRegex(ValueError, "risk set"):
                MODULE._validate_context_artifacts(
                    private_path, public_path, prereg, [TASK], [0], source_binding
                )

    def test_presearch_prerequisites_require_exact_smoke_prereg_binding(self):
        revision = "a" * 40
        clean = {
            "git_available": True,
            "git_revision": revision,
            "source_tree_dirty": False,
            "source_changes": [],
        }
        seed = 71923
        smoke_replicates = [0, 1, 2, 3]
        schedule = MODULE._reconstruct_condition_schedule(
            smoke_replicates, seed
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prereg_path = root / "prereg.json"
            prereg_path.write_text('{"fixture":true}\n', encoding="utf-8")
            prerequisites = {}
            for name in (
                "full_test_suite", "security_audit", "certification_audit"
            ):
                report = {
                    "schema_version": 1,
                    "execution_passed": True,
                    "trusted_evidence": True,
                    "passed": True,
                    "source_provenance": clean,
                }
                if name == "full_test_suite":
                    report.update({"unittest_ok": True, "test_count": 100})
                elif name == "security_audit":
                    report["test_count"] = 20
                else:
                    report.update({
                        "inventory_count": 59,
                        "status_counts": {
                            "certified": 7,
                            "candidate": 43,
                            "quarantined": 9,
                        },
                    })
                path = root / (name + ".json")
                path.write_text(json.dumps(report) + "\n", encoding="utf-8")
                prerequisites[name] = {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": len(path.read_bytes()),
                }
            precision = {
                "schema_version": 1,
                "execution_passed": True,
                "trusted_evidence": True,
                "passed": True,
                "source_provenance": clean,
                "fixed_balanced_blocks_per_condition": 48,
                "scheduled_search_cells": 384,
                "scheduled_model_proposals": 1152,
            }
            precision_path = root / "precision.json"
            precision_path.write_text(
                json.dumps(precision) + "\n", encoding="utf-8"
            )
            smoke_runs = []
            for replicate in smoke_replicates:
                for mode in MODES:
                    smoke_runs.append({
                        "task": "Chemistry/LennardJonesCluster",
                        "algorithm": "greedy_rewrite",
                        "feedback_mode": mode,
                        "seed": replicate,
                        "execution_block_index": replicate + 1,
                        "within_block_position": (
                            schedule[replicate]["feedback_modes"].index(mode) + 1
                        ),
                    })
            smoke = {
                "schema_version": 1,
                "execution_passed": True,
                "trusted_evidence": True,
                "passed": True,
                "source_provenance": clean,
                "config": {
                    "tasks": ["Chemistry/LennardJonesCluster"],
                    "algorithms": ["greedy_rewrite"],
                    "feedback_modes": list(MODES),
                    "seeds": smoke_replicates,
                    "condition_order": "balanced_williams",
                    "condition_order_randomization_seed": seed,
                    "condition_order_schedule": schedule,
                    "block_workers": 2,
                    "block_parallelism": {
                        "maximum_concurrent_blocks": 2,
                        "within_block_conditions": (
                            "serial_in_condition_order_schedule"
                        ),
                    },
                    "budget": 0,
                    "trajectory_snapshot_schema_version": 2,
                    "llm_condition_sha256": "c" * 64,
                    "preregistration": {
                        "sha256": hashlib.sha256(
                            prereg_path.read_bytes()
                        ).hexdigest(),
                        "bytes": len(prereg_path.read_bytes()),
                    },
                },
                "aggregate": {"successful_runs": 16, "failed_runs": 0},
                "runs": smoke_runs,
            }
            smoke_path = root / "smoke.json"
            smoke_path.write_text(json.dumps(smoke) + "\n", encoding="utf-8")
            prerequisites["protocol_smoke"] = {
                "path": str(smoke_path),
                "task": "Chemistry/LennardJonesCluster",
                "budget": 0,
                "replicate_identifiers": smoke_replicates,
                "feedback_modes": list(MODES),
                "condition_order": "balanced_williams",
                "condition_order_randomization_seed": seed,
                "condition_order_schedule": schedule,
                "block_workers": 2,
                "scheduled_cell_count": 16,
            }
            prereg = {
                "prerequisites": prerequisites,
                "precision_plan": {
                    "path": str(precision_path),
                    "sha256": hashlib.sha256(
                        precision_path.read_bytes()
                    ).hexdigest(),
                    "bytes": len(precision_path.read_bytes()),
                },
                "design": {
                    "fixed_blocks_per_condition": 48,
                    "scheduled_cell_count": 384,
                    "scheduled_model_proposals": 1152,
                },
            }
            with patch.object(MODULE, "_source_equivalent", return_value=True):
                audits = MODULE._validate_presearch_prerequisites(
                    prereg, prereg_path, revision, "c" * 64
                )
                self.assertEqual(len(audits), 5)
                self.assertTrue(audits[-1]["exact_preregistration_binding"])

                smoke["config"]["preregistration"]["sha256"] = "0" * 64
                smoke_path.write_text(
                    json.dumps(smoke) + "\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "protocol smoke"):
                    MODULE._validate_presearch_prerequisites(
                        prereg, prereg_path, revision, "c" * 64
                    )

    def test_render_quarantines_stochastic_replays(self):
        context_sha = "a" * 64
        candidate_sha = "b" * 64
        artifact_id = "c" * 64
        evaluation_ids = ("d" * 64, "e" * 64)
        endpoint = {
            "endpoint_id": "endpoint",
            "artifact_id": artifact_id,
            "candidate_sha256": candidate_sha,
            "context_sha256": context_sha,
        }
        document = {
            "source_provenance": {
                "git_available": True,
                "git_revision": "f" * 40,
                "source_tree_dirty": False,
            },
            "planned_evaluations": [
                {
                    "evaluation_id": evaluation_ids[index],
                    "artifact_id": artifact_id,
                    "candidate_sha256": candidate_sha,
                    "context_sha256": context_sha,
                    "task": TASK,
                    "replicate_id": 0,
                }
                for index in range(2)
            ],
            "attempts": [
                {
                    "evaluation_id": evaluation_ids[index],
                    "status": "completed",
                    "metrics": {
                        "combined_score": 0.1 + 0.1 * index,
                        "valid": 1.0,
                        "trusted_context_sha256": context_sha,
                    },
                }
                for index in range(2)
            ],
        }
        MODULE._render_results(document, [endpoint])
        self.assertFalse(document["execution_passed"])
        self.assertEqual(document["completion"]["stochastic_artifacts"], 1)
        self.assertIsNone(document["endpoint_results"][0]["metrics"])
        self.assertTrue(document["endpoint_results"][0]["stochastic_artifact"])
        self.assertFalse(
            document["analysis_gate"]["eligible_for_separate_preregistered_analysis"]
        )
        self.assertFalse(
            document["claims"]["preregistered_primary_hypothesis_test_completed"]
        )
        self.assertFalse(document["claims"]["feedback_causal_effect_identified"])

    def test_attempt_ledger_rejects_tampering_and_post_terminal_retry(self):
        context_sha = "a" * 64
        evaluation = {
            "evaluation_id": "b" * 64,
            "artifact_id": "c" * 64,
            "replay_index": 0,
            "task": TASK,
            "replicate_id": 0,
            "candidate_sha256": "d" * 64,
            "context_sha256": context_sha,
        }
        attempt = {
            **evaluation,
            "attempt_index": 1,
            "confirmation_look_index": 1,
            "status": "completed",
            "started_at": "2026-07-26T00:00:00+00:00",
            "completed_at": "2026-07-26T00:00:01+00:00",
            "wall_seconds": 1.0,
            "metrics": {
                "combined_score": 0.5,
                "valid": 1.0,
                "trusted_context_sha256": context_sha,
            },
        }
        MODULE._validate_attempt_ledger({"attempts": [attempt]}, [evaluation])

        tampered = json.loads(json.dumps(attempt))
        tampered["candidate_sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "lineage"):
            MODULE._validate_attempt_ledger({"attempts": [tampered]}, [evaluation])

        retry = json.loads(json.dumps(attempt))
        retry["attempt_index"] = 2
        retry["confirmation_look_index"] = 2
        with self.assertRaisesRegex(ValueError, "follows a terminal"):
            MODULE._validate_attempt_ledger(
                {"attempts": [attempt, retry]}, [evaluation]
            )

        missing_context = json.loads(json.dumps(attempt))
        missing_context["metrics"].pop("trusted_context_sha256")
        with self.assertRaisesRegex(ValueError, "lacks context"):
            MODULE._validate_attempt_ledger(
                {"attempts": [missing_context]}, [evaluation]
            )

    def test_parallel_worker_results_do_not_define_look_order(self):
        context = _context()
        context_sha = hashlib.sha256(
            MODULE.canonical_trusted_context(context)
        ).hexdigest()
        source = "def solve(): return 1\n"
        source_sha = MODULE.sha256_text(source)
        evaluations = [
            {
                "evaluation_id": "evaluation-%d" % index,
                "artifact_id": "artifact-%d" % index,
                "replay_index": 0,
                "task": TASK,
                "replicate_id": index,
                "candidate_sha256": source_sha,
                "context_sha256": context_sha,
            }
            for index in range(3)
        ]
        attempts = [
            {
                **evaluation,
                "attempt_index": 1,
                "confirmation_look_index": index + 1,
                "status": "started",
                "started_at": "2026-07-26T00:00:0%d+00:00" % index,
                "completed_at": None,
                "wall_seconds": None,
                "metrics": None,
            }
            for index, evaluation in enumerate(evaluations)
        ]
        document = {"attempts": attempts}
        MODULE._validate_attempt_ledger(document, evaluations)
        # Simulate reverse completion order. Mutating outcome fields in place
        # must not reorder the write-ahead list or its look indices.
        for evaluation in reversed(evaluations):
            attempt = next(
                row for row in attempts
                if row["evaluation_id"] == evaluation["evaluation_id"]
            )
            attempt.update({
                "status": "completed",
                "completed_at": "2026-07-26T00:01:00+00:00",
                "wall_seconds": 1.0,
                "metrics": {
                    "combined_score": 0.5,
                    "valid": 1.0,
                    "trusted_context_sha256": context_sha,
                },
            })
        MODULE._validate_attempt_ledger(document, evaluations)
        self.assertEqual(
            [row["evaluation_id"] for row in attempts],
            [row["evaluation_id"] for row in evaluations],
        )
        self.assertEqual(
            [row["confirmation_look_index"] for row in attempts], [1, 2, 3]
        )

    def test_incomplete_search_fails_before_private_read_or_confirmation_call(self):
        with patch.object(
            MODULE,
            "_validate_preregistration_and_search",
            side_effect=ValueError("complete search risk set is not available"),
        ), patch.object(MODULE, "_validate_context_artifacts") as private_read, patch.object(
            MODULE, "evaluate_candidate"
        ) as evaluate:
            with self.assertRaisesRegex(ValueError, "complete search"):
                MODULE.run_confirmation(
                    preregistration_path=Path("prereg.json"),
                    search_report_path=Path("search.json"),
                    private_contexts_path=Path("private.json"),
                    public_commitment_path=Path("public.json"),
                    output_path=Path("result.json"),
                    resume=False,
                )
        private_read.assert_not_called()
        evaluate.assert_not_called()

    def test_closed_cohort_replays_unique_artifacts_and_resume_is_idempotent(self):
        cells = [
            _cell("normal", 10),
            _cell("score_only", 8),
            _cell("delayed_replay", 6),
            _cell("selection_blind", 5),
        ]
        context = _context()
        context_sha = hashlib.sha256(
            MODULE.canonical_trusted_context(context)
        ).hexdigest()
        design = {
            "tasks": [TASK],
            "replicates": [0],
            "budget": 3,
            "timeout": 10.0,
            "confirmation_replays": 2,
            "confirmation_randomization_seed": 12345,
            "source_binding": {},
            "prerequisite_audits": [],
        }
        clean = {
            "git_available": True,
            "git_revision": "a" * 40,
            "source_tree_dirty": False,
            "source_changes": [],
        }
        calls = []

        def evaluate(_spec, candidate, timeout_s, *, trusted_context):
            calls.append(candidate.read_text(encoding="utf-8"))
            return {
                "combined_score": 0.5,
                "valid": 1.0,
                "trusted_context_sha256": context_sha,
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = {}
            for name in ("preregistration", "search", "private", "public"):
                path = root / (name + ".json")
                path.write_text('{"fixture":true}\n', encoding="utf-8")
                inputs[name] = path
            output = root / "nested" / "confirmation.json"
            validators = (
                patch.object(
                    MODULE,
                    "_validate_preregistration_and_search",
                    return_value=(
                        {}, {"source_provenance": {"git_revision": "a" * 40}},
                        cells, design,
                    ),
                ),
                patch.object(
                    MODULE,
                    "_validate_context_artifacts",
                    return_value=(
                        {(TASK, 0): context}, {"block_count": 1},
                        [{"task": TASK, "replicate_id": 0, "audit": {"passed": True}}],
                    ),
                ),
                patch.object(MODULE, "source_provenance", return_value=clean),
                patch.object(MODULE, "find_task", return_value=object()),
                patch.object(MODULE, "evaluate_candidate", side_effect=evaluate),
            )
            with validators[0], validators[1], validators[2], validators[3], validators[4]:
                document = MODULE.run_confirmation(
                    preregistration_path=inputs["preregistration"],
                    search_report_path=inputs["search"],
                    private_contexts_path=inputs["private"],
                    public_commitment_path=inputs["public"],
                    output_path=output,
                    resume=False,
                    command=["test"],
                )
                first_call_count = len(calls)
                resumed = MODULE.run_confirmation(
                    preregistration_path=inputs["preregistration"],
                    search_report_path=inputs["search"],
                    private_contexts_path=inputs["private"],
                    public_commitment_path=inputs["public"],
                    output_path=output,
                    resume=True,
                    command=["test"],
                )
            self.assertEqual(first_call_count, 14)
            self.assertEqual(len(calls), first_call_count)
            self.assertTrue(document["execution_passed"])
            self.assertTrue(
                document["analysis_gate"][
                    "eligible_for_separate_preregistered_analysis"
                ]
            )
            self.assertFalse(
                document["claims"]["feedback_causal_effect_identified"]
            )
            self.assertEqual(document["completion"]["planned_unique_artifacts"], 7)
            self.assertEqual(document["completion"]["deterministic_artifacts"], 7)
            self.assertEqual(document["completion"]["stochastic_artifacts"], 0)
            self.assertEqual(document["completion"]["attempt_count"], 14)
            self.assertEqual(
                [row["confirmation_look_index"] for row in document["attempts"]],
                list(range(1, 15)),
            )
            self.assertEqual(resumed["attempts"], document["attempts"])

    def test_infrastructure_failure_is_retained_and_retried(self):
        cells = [_cell(mode, 5, shared_source=True) for mode in MODES]
        context = _context()
        context_sha = hashlib.sha256(
            MODULE.canonical_trusted_context(context)
        ).hexdigest()
        design = {
            "tasks": [TASK], "replicates": [0], "budget": 3,
            "timeout": 10.0, "confirmation_replays": 2, "source_binding": {},
            "confirmation_randomization_seed": 12345,
            "prerequisite_audits": [],
        }
        clean = {
            "git_available": True, "git_revision": "a" * 40,
            "source_tree_dirty": False, "source_changes": [],
        }
        call_index = 0

        def evaluate(_spec, _candidate, timeout_s, *, trusted_context):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                return {
                    "combined_score": -1.0e18,
                    "valid": 0.0,
                    "trusted_context_sha256": context_sha,
                    "infrastructure_failure": 1.0,
                }
            return {
                "combined_score": 0.4,
                "valid": 1.0,
                "trusted_context_sha256": context_sha,
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for name in ("prereg", "search", "private", "public"):
                path = root / (name + ".json")
                path.write_text('{}\n', encoding="utf-8")
                paths.append(path)
            output = root / "confirmation.json"
            common = (
                patch.object(
                    MODULE, "_validate_preregistration_and_search",
                    return_value=(
                        {}, {"source_provenance": {"git_revision": "a" * 40}},
                        cells, design,
                    ),
                ),
                patch.object(
                    MODULE, "_validate_context_artifacts",
                    return_value=(
                        {(TASK, 0): context}, {"block_count": 1},
                        [{"audit": {"passed": True}}],
                    ),
                ),
                patch.object(MODULE, "source_provenance", return_value=clean),
                patch.object(MODULE, "find_task", return_value=object()),
                patch.object(MODULE, "evaluate_candidate", side_effect=evaluate),
            )
            with common[0], common[1], common[2], common[3], common[4]:
                first = MODULE.run_confirmation(
                    preregistration_path=paths[0], search_report_path=paths[1],
                    private_contexts_path=paths[2], public_commitment_path=paths[3],
                    output_path=output, resume=False,
                )
                self.assertFalse(first["execution_passed"])
                second = MODULE.run_confirmation(
                    preregistration_path=paths[0], search_report_path=paths[1],
                    private_contexts_path=paths[2], public_commitment_path=paths[3],
                    output_path=output, resume=True,
                )
            # One unique shared artifact, two replays, and one retained retry.
            self.assertEqual(call_index, 3)
            self.assertTrue(second["execution_passed"])
            self.assertEqual(second["completion"]["attempt_count"], 3)
            first_eval = second["planned_evaluations"][0]["evaluation_id"]
            matching = [
                row for row in second["attempts"]
                if row["evaluation_id"] == first_eval
            ]
            self.assertEqual([row["attempt_index"] for row in matching], [1, 2])
            self.assertEqual(
                [row["confirmation_look_index"] for row in second["attempts"]],
                [1, 2, 3],
            )


if __name__ == "__main__":
    unittest.main()
