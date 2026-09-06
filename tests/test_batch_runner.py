from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sle.llm import LLMConfig
from sle.runtime_identity import current_runtime_descriptor
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "batch_evolve.py"
SPEC = importlib.util.spec_from_file_location("batch_evolve_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _current_cohort_manifest() -> Path:
    """The cohort manifest the preflight is bound to, whichever rebinding wrote it last."""
    spec = importlib.util.spec_from_file_location(
        "preflight_for_cohort_manifest",
        Path(__file__).resolve().parents[1] / "scripts" / "run_measurement_health_preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DEFAULT_MANIFEST


class BatchAggregationTests(unittest.TestCase):
    RUNTIME_DESCRIPTOR = current_runtime_descriptor(())
    RUNTIME_SHA256 = RUNTIME_DESCRIPTOR["fingerprint_sha256"]

    def runtime_fields(self):
        return {
            "trusted_evaluator_runtime": self.RUNTIME_DESCRIPTOR,
            "trusted_evaluator_runtime_sha256": self.RUNTIME_SHA256,
        }

    class Config:
        wire = "chat"; base_url = "https://example.invalid/v1"; model = "fixture"
        max_output_tokens = 10; temperature = 0; reasoning_effort = None
        timeout_seconds = 1; extra_headers = {}
        input_cost_per_million = None; output_cost_per_million = None

    def test_condition_aggregation_reports_auc_cost_and_ci(self):
        def run(seed, best, auc):
            return {
                "task": "T/X", "algorithm": "greedy_rewrite", "feedback_mode": "normal",
                "seed": seed, "best": best,
                **self.runtime_fields(),
                "summary": {"best_so_far_auc": auc, "budget_units": 4,
                            "oracle_calls": 3 + seed, "wall_seconds": 2 + seed,
                            "llm": {"total_tokens": 10 + seed, "estimated_cost_usd": 0.1}},
            }
        got = MODULE.aggregate_runs([run(0, 0.2, 0.1), run(1, 0.4, 0.3)])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 2)
        self.assertAlmostEqual(condition["best_score"]["mean"], 0.3)
        self.assertAlmostEqual(condition["best_so_far_auc"]["mean"], 0.2)
        self.assertEqual(condition["budget_units"]["mean"], 4)
        self.assertAlmostEqual(condition["oracle_calls"]["mean"], 3.5)
        self.assertIn("estimated_cost_usd", condition)

    def test_aggregation_rejects_mixed_trusted_runtimes_for_one_task(self):
        first = current_runtime_descriptor(())
        second = current_runtime_descriptor(("missing-runtime-fixture",))

        def run(seed: int, descriptor: dict):
            return {
                "task": "T/X", "algorithm": "greedy_rewrite",
                "feedback_mode": "normal", "seed": seed, "best": 0.2,
                "trusted_evaluator_runtime": descriptor,
                "trusted_evaluator_runtime_sha256": descriptor[
                    "fingerprint_sha256"
                ],
                "summary": {
                    "best_so_far_auc": 0.1, "budget_units": 1,
                    "oracle_calls": 1, "wall_seconds": 1,
                    "llm": {"total_tokens": 0, "estimated_cost_usd": None},
                },
            }

        with self.assertRaisesRegex(ValueError, "mixed trusted evaluator runtimes"):
            MODULE.aggregate_runs([
                run(0, first),
                run(1, second),
            ])

    def test_aggregation_rejects_runs_without_trusted_runtime_identity(self):
        run = {
            "task": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 0, "error": "offline",
        }
        with self.assertRaisesRegex(ValueError, "lacks trusted evaluator runtime"):
            MODULE.aggregate_runs([run])

    def test_feedback_condition_order_is_counterbalanced_by_seed(self):
        modes = ["normal", "selection_blind"]
        self.assertEqual(MODULE._condition_order(modes, 0), modes)
        self.assertEqual(MODULE._condition_order(modes, 1), list(reversed(modes)))
        self.assertEqual(MODULE._condition_order(modes, 2), modes)

    def test_four_condition_williams_order_balances_position_and_carryover(self):
        modes = ["normal", "score_only", "delayed_replay", "selection_blind"]
        rows = [
            MODULE._condition_order(
                modes, seed=100 + index, design="balanced_williams",
                schedule_index=index,
            )
            for index in range(4)
        ]
        for position in range(4):
            self.assertEqual({row[position] for row in rows}, set(modes))
        carryovers = [
            (row[index], row[index + 1])
            for row in rows for index in range(3)
        ]
        self.assertEqual(len(carryovers), 12)
        self.assertEqual(len(set(carryovers)), 12)
        self.assertTrue(all(left != right for left, right in carryovers))

        repeated = [
            MODULE._condition_order(
                modes, seed=index, design="balanced_williams",
                schedule_index=index,
            )
            for index in range(12)
        ]
        for position in range(4):
            counts = {
                mode: sum(row[position] == mode for row in repeated)
                for mode in modes
            }
        self.assertEqual(set(counts.values()), {3})

        schedule = MODULE._condition_schedule(
            modes,
            list(range(24)),
            "balanced_williams",
            randomization_seed=834721,
        )
        self.assertEqual(
            schedule,
            MODULE._condition_schedule(
                modes,
                list(range(24)),
                "balanced_williams",
                randomization_seed=834721,
            ),
        )
        self.assertNotEqual(
            schedule,
            MODULE._condition_schedule(
                modes,
                list(range(24)),
                "balanced_williams",
                randomization_seed=834722,
            ),
        )
        for position in range(4):
            counts = {
                mode: sum(row[position] == mode for row in schedule)
                for mode in modes
            }
            self.assertEqual(set(counts.values()), {6})

    def test_williams_order_rejects_non_four_mode_design(self):
        with self.assertRaisesRegex(ValueError, "exactly four"):
            MODULE._condition_order(
                ["normal", "selection_blind"], 0, "balanced_williams"
            )
        with self.assertRaisesRegex(ValueError, "requires"):
            MODULE._condition_schedule(
                ["normal", "score_only", "delayed_replay", "selection_blind"],
                list(range(4)),
                "balanced_williams",
                randomization_seed=None,
            )
        with self.assertRaisesRegex(ValueError, "requires balanced_williams"):
            MODULE._condition_schedule(
                ["normal"], [0], "reverse_parity", randomization_seed=1
            )

    def test_main_rejects_empty_or_duplicate_schedule_axes(self):
        invalid_arguments = (
            ["--feedback-modes", ","],
            ["--feedback-modes", "normal,normal"],
            ["--algorithms", "greedy_rewrite,greedy_rewrite"],
            ["--seeds", "0,0"],
            ["--tasks", "LennardJonesCluster,LennardJonesCluster"],
        )
        with patch.object(
            MODULE, "_frozen_task_bindings",
            side_effect=AssertionError("must reject before runtime freeze"),
        ):
            for arguments in invalid_arguments:
                with self.subTest(arguments=arguments):
                    with self.assertRaises(SystemExit):
                        MODULE.main(arguments)

    def test_execution_blocks_keep_conditions_serial_with_fixed_indices(self):
        modes = ["normal", "score_only", "delayed_replay", "selection_blind"]
        seeds = [3, 7, 11, 15]
        schedule = MODULE._condition_schedule(
            modes, seeds, "balanced_williams", randomization_seed=834721
        )
        blocks = MODULE._execution_blocks(
            ["T/A", "T/B"], ["greedy_rewrite"], seeds, schedule
        )
        self.assertEqual(len(blocks), 8)
        self.assertEqual(
            [row["block_index"] for row in blocks], list(range(1, 9))
        )
        self.assertEqual(
            [(row["task"], row["seed"]) for row in blocks[:4]],
            [("T/A", seed) for seed in seeds],
        )
        for block in blocks:
            self.assertEqual(
                block["feedback_modes"], schedule[seeds.index(block["seed"])]
            )
            self.assertEqual(set(block["feedback_modes"]), set(modes))

    def test_worker_rejects_runtime_change_before_constructing_llm_client(self):
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        current = dict(frozen)
        current["trusted_evaluator_runtime_sha256"] = "2" * 64
        payload = {
            "block_index": 1,
            "task": spec.task_id,
            "algorithm": "greedy_rewrite",
            "seed": 0,
            "feedback_modes": ["normal"],
            "llm_config": self.Config(),
            "work_root": "/does/not/matter",
            "budget": 1,
            "timeout_s": 1.0,
            "resume": False,
            "skip_keys": [],
            "frozen_task_binding": frozen,
        }
        with patch.object(
            MODULE, "_frozen_task_bindings", return_value={spec.task_id: current},
        ), patch.object(MODULE, "LLMClient") as llm_client:
            with self.assertRaisesRegex(RuntimeError, "task binding changed"):
                MODULE._execute_block(payload)
        llm_client.assert_not_called()

    def test_worker_rejects_symlinked_cell_before_client_or_backend(self):
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root = root / "runs"
            outside = root / "outside"
            cell = (
                work_root / "Chemistry__LennardJonesCluster"
                / "greedy_rewrite" / "normal" / "seed_0"
            )
            cell.parent.mkdir(parents=True)
            outside.mkdir()
            cell.symlink_to(outside, target_is_directory=True)
            payload = {
                "block_index": 1,
                "task": spec.task_id,
                "algorithm": "greedy_rewrite",
                "seed": 0,
                "feedback_modes": ["normal"],
                "llm_config": self.Config(),
                "work_root": str(work_root.resolve()),
                "budget": 1,
                "timeout_s": 1.0,
                "resume": False,
                "skip_keys": [],
                "frozen_task_binding": frozen,
            }
            escaped_write = outside / "backend-wrote-here"

            def algorithm(**kwargs):
                (kwargs["workdir"] / escaped_write.name).write_text(
                    "escaped", encoding="utf-8"
                )
                raise RuntimeError("stop after escaped write")

            client = Mock()
            backend = Mock(return_value=algorithm)
            rejected = None
            with patch.object(
                MODULE, "_assert_task_binding", return_value=None,
            ), patch.object(
                MODULE, "LLMClient", client,
            ), patch.object(
                MODULE, "get_algorithm", backend,
            ):
                try:
                    MODULE._execute_block(payload)
                except RuntimeError as exc:
                    rejected = exc
            self.assertFalse(
                escaped_write.exists(), "backend wrote through the cell symlink"
            )
            self.assertIsNotNone(rejected)
            self.assertRegex(str(rejected), "unsafe batch cell path")
            client.assert_not_called()
            backend.assert_not_called()
            self.assertEqual(cell.resolve(), outside.resolve())

    def test_worker_rejects_traversal_and_task_alias_before_factories(self):
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        with tempfile.TemporaryDirectory() as temporary:
            for task_id, feedback_modes in (
                (spec.task_id, ["../outside"]),
                ("LennardJonesCluster", ["normal"]),
            ):
                with self.subTest(task=task_id, feedback_modes=feedback_modes):
                    payload = {
                        "block_index": 1,
                        "task": task_id,
                        "algorithm": "greedy_rewrite",
                        "seed": 0,
                        "feedback_modes": feedback_modes,
                        "llm_config": self.Config(),
                        "work_root": temporary,
                        "budget": 1,
                        "timeout_s": 1.0,
                        "resume": False,
                        "skip_keys": [],
                        "frozen_task_binding": frozen,
                    }
                    client = Mock()
                    backend = Mock()
                    with patch.object(
                        MODULE, "_assert_task_binding", return_value=None,
                    ), patch.object(
                        MODULE, "LLMClient", client,
                    ), patch.object(
                        MODULE, "get_algorithm", backend,
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, "unsafe batch cell path"
                        ):
                            MODULE._execute_block(payload)
                    client.assert_not_called()
                    backend.assert_not_called()

    def test_worker_rechecks_cell_alias_before_backend_execution(self):
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            cell = (
                root / "Chemistry__LennardJonesCluster" / "greedy_rewrite"
                / "normal" / "seed_0"
            )
            cell.parent.mkdir(parents=True)
            payload = {
                "block_index": 1,
                "task": spec.task_id,
                "algorithm": "greedy_rewrite",
                "seed": 0,
                "feedback_modes": ["normal"],
                "llm_config": self.Config(),
                "work_root": temporary,
                "budget": 1,
                "timeout_s": 1.0,
                "resume": False,
                "skip_keys": [],
                "frozen_task_binding": frozen,
            }
            checks = 0

            def binding_check(*_args):
                nonlocal checks
                checks += 1
                if checks == 2:
                    cell.symlink_to(outside, target_is_directory=True)

            backend = Mock()
            with patch.object(
                MODULE, "_assert_task_binding", side_effect=binding_check,
            ), patch.object(
                MODULE, "LLMClient", return_value=Mock(),
            ), patch.object(
                MODULE, "get_algorithm", return_value=backend,
            ):
                with self.assertRaisesRegex(RuntimeError, "unsafe batch cell path"):
                    MODULE._execute_block(payload)
            backend.assert_not_called()
            self.assertEqual(cell.resolve(), outside.resolve())

    def test_worker_rechecks_full_binding_before_backend_execution(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        changed = dict(frozen)
        changed["task_package_sha256"] = "0" * 64
        payload = {
            "block_index": 1,
            "task": spec.task_id,
            "algorithm": "greedy_rewrite",
            "seed": 0,
            "feedback_modes": ["normal"],
            "llm_config": self.Config(),
            "work_root": temporary.name,
            "budget": 1,
            "timeout_s": 1.0,
            "resume": False,
            "skip_keys": [],
            "frozen_task_binding": frozen,
        }
        backend = Mock()
        with patch.object(
            MODULE, "_frozen_task_bindings",
            side_effect=[{spec.task_id: frozen}, {spec.task_id: changed}],
        ), patch.object(MODULE, "LLMClient") as llm_client, patch.object(
            MODULE, "get_algorithm", return_value=backend,
        ):
            with self.assertRaisesRegex(RuntimeError, "task binding changed"):
                MODULE._execute_block(payload)
        llm_client.assert_called_once()
        backend.assert_not_called()

    def test_worker_rechecks_binding_immediately_before_model_call(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        changed = dict(frozen)
        changed["runtime_source_sha256"] = "0" * 64
        payload = {
            "block_index": 1,
            "task": spec.task_id,
            "algorithm": "greedy_rewrite",
            "seed": 0,
            "feedback_modes": ["normal"],
            "llm_config": self.Config(),
            "work_root": temporary.name,
            "budget": 1,
            "timeout_s": 1.0,
            "resume": False,
            "skip_keys": [],
            "frozen_task_binding": frozen,
        }
        raw_client = type("Client", (), {
            "config": self.Config(),
            "complete": Mock(return_value="must not be returned"),
        })()

        def backend(**kwargs):
            kwargs["llm"].complete("proposal")
            raise AssertionError("model call was not guarded")

        with patch.object(
            MODULE, "_frozen_task_bindings", side_effect=[
                {spec.task_id: frozen},
                {spec.task_id: frozen},
                {spec.task_id: changed},
                {spec.task_id: changed},
            ],
        ), patch.object(MODULE, "LLMClient", return_value=raw_client), patch.object(
            MODULE, "get_algorithm", return_value=backend,
        ):
            result = MODULE._execute_block(payload)
        self.assertIn("frozen task binding changed", result["entries"][0]["error"])
        raw_client.complete.assert_not_called()

    def test_worker_postchecks_binding_after_backend_exception(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        changed = dict(frozen)
        changed["task_contract_sha256"] = "0" * 64
        payload = {
            "block_index": 1,
            "task": spec.task_id,
            "algorithm": "greedy_rewrite",
            "seed": 0,
            "feedback_modes": ["normal"],
            "llm_config": self.Config(),
            "work_root": temporary.name,
            "budget": 1,
            "timeout_s": 1.0,
            "resume": False,
            "skip_keys": [],
            "frozen_task_binding": frozen,
        }

        def backend(**_kwargs):
            raise ValueError("backend failed")

        with patch.object(
            MODULE, "_frozen_task_bindings", side_effect=[
                {spec.task_id: frozen},
                {spec.task_id: frozen},
                {spec.task_id: changed},
            ],
        ), patch.object(MODULE, "LLMClient"), patch.object(
            MODULE, "get_algorithm", return_value=backend,
        ):
            result = MODULE._execute_block(payload)
        self.assertIn(
            "frozen task binding changed after backend execution",
            result["entries"][0]["error"],
        )

    def test_task_runtime_records_are_path_free_and_resolved_once(self):
        specs = [
            MODULE.find_task("Chemistry/LennardJonesCluster", include_uncertified=True),
            MODULE.find_task("Optics/DiffractionGratingDesign", include_uncertified=True),
        ]
        descriptor = current_runtime_descriptor(())
        runtime = type("Runtime", (), {
            "descriptor": descriptor,
            "fingerprint_sha256": descriptor["fingerprint_sha256"],
            "executable": "/private/oracle/python",
        })()
        with patch.object(
            MODULE, "resolve_trusted_runtime", return_value=runtime,
        ) as resolve:
            records = MODULE._trusted_runtime_records(specs)
        self.assertEqual(resolve.call_count, 2)
        self.assertNotIn("/private/oracle/python", json.dumps(records))
        self.assertEqual(
            set(records), {"Chemistry/LennardJonesCluster", "Optics/DiffractionGratingDesign"}
        )

    def test_parent_freezes_complete_task_bindings_with_one_runtime_probe_each(self):
        specs = [
            MODULE.find_task("Chemistry/LennardJonesCluster", include_uncertified=True),
            MODULE.find_task("Optics/DiffractionGratingDesign", include_uncertified=True),
        ]
        descriptor = current_runtime_descriptor(())
        runtime = type("Runtime", (), {
            "descriptor": descriptor,
            "fingerprint_sha256": descriptor["fingerprint_sha256"],
        })()
        with patch.object(
            MODULE, "resolve_trusted_runtime", return_value=runtime,
        ) as resolve:
            bindings = MODULE._frozen_task_bindings(specs)
        self.assertEqual(resolve.call_count, len(specs))
        for spec in specs:
            binding = bindings[spec.task_id]
            self.assertEqual(
                binding["task_contract_sha256"], MODULE.task_contract_sha256(spec)
            )
            self.assertEqual(
                binding["task_package_sha256"], MODULE.task_package_sha256(spec)
            )
            self.assertEqual(
                binding["task_card_sha256"], MODULE.hashlib.sha256(
                    (spec.task_dir / "TASK_CARD.yaml").read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                binding["runtime_source_sha256"], MODULE.runtime_source_sha256()
            )
            self.assertEqual(binding["trusted_evaluator_runtime"], descriptor)

    def test_completed_report_entry_requires_verified_underlying_run(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        work_root = Path(temporary.name)
        run_path = (
            work_root / "T__X" / "greedy_rewrite" / "normal" / "seed_0"
        )
        descriptor = current_runtime_descriptor(())
        bindings = {"T/X": {
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }}
        entry = {
            "task": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 0, "budget": 3,
            "workdir": str(run_path),
            "workdir_scope": "local_only_not_portable_evidence_identity",
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }
        with patch.object(
            MODULE, "verify_run", side_effect=ValueError("missing ledger"),
        ) as verify:
            with self.assertRaisesRegex(SystemExit, "completed cell is unverifiable"):
                MODULE._verified_completed_keys(
                    [entry], bindings, expected_budget=3,
                    expected_work_root=work_root,
                )
        verify.assert_called_once_with(
            run_path, expected_budget=3,
            expected_trusted_runtime_sha256=descriptor["fingerprint_sha256"],
        )

    def test_completed_report_entry_cannot_claim_a_different_seed(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        work_root = Path(temporary.name)
        descriptor = current_runtime_descriptor(())
        bindings = {"T/X": {
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }}
        entry = {
            "task": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 999, "budget": 3,
            "workdir": str(
                work_root / "T__X" / "greedy_rewrite" / "normal" / "seed_999"
            ),
            "workdir_scope": "local_only_not_portable_evidence_identity",
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }
        verified = {
            "verified": True,
            "task_id": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 0, "budget": 3,
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }
        with patch.object(MODULE, "verify_run", return_value=verified):
            with self.assertRaisesRegex(SystemExit, "identity differs"):
                MODULE._verified_completed_keys(
                    [entry], bindings, expected_budget=3,
                    expected_work_root=work_root,
                )

    def test_completed_report_cannot_reuse_run_from_another_work_root(self):
        descriptor = current_runtime_descriptor(())
        bindings = {"T/X": {
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }}
        verified = {
            "verified": True,
            "task_id": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 0, "budget": 3,
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor["fingerprint_sha256"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work_root = root / "current-runs"
            other_root = root / "other-runs"
            work_root.mkdir()
            other_root.mkdir()
            external_run = (
                other_root / "T__X" / "greedy_rewrite" / "normal" / "seed_0"
            )
            entry = {
                "task": "T/X", "algorithm": "greedy_rewrite",
                "feedback_mode": "normal", "seed": 0, "budget": 3,
                "workdir": str(external_run),
                "workdir_scope": "local_only_not_portable_evidence_identity",
                "trusted_evaluator_runtime": descriptor,
                "trusted_evaluator_runtime_sha256": descriptor[
                    "fingerprint_sha256"
                ],
            }
            with patch.object(MODULE, "verify_run", return_value=verified) as verify:
                with self.assertRaisesRegex(SystemExit, "frozen work root"):
                    MODULE._verified_completed_keys(
                        [entry], bindings, expected_budget=3,
                        expected_work_root=work_root,
                    )
            verify.assert_not_called()

    def test_parent_freezes_task_runtimes_before_loading_model_client(self):
        order = []
        descriptor = current_runtime_descriptor(())

        def freeze(specs):
            order.append("runtime")
            return {spec.task_id: {
                "descriptor": descriptor,
                "fingerprint_sha256": descriptor["fingerprint_sha256"],
            } for spec in specs}

        def load(_path):
            order.append("llm")
            raise RuntimeError("stop after ordering check")

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "_frozen_task_bindings", side_effect=freeze,
        ), patch.object(MODULE, "load_llm_client", side_effect=load):
            with self.assertRaisesRegex(RuntimeError, "ordering check"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster", "--budget", "0",
                    "--output", str(Path(tmp) / "report.json"),
                    "--workdir", str(Path(tmp) / "runs"),
                ])
        self.assertEqual(order, ["runtime", "llm"])

    def test_final_integrity_recheck_detects_task_and_source_changes(self):
        spec = MODULE.find_task(
            "Chemistry/LennardJonesCluster", include_uncertified=True
        )
        frozen = MODULE._frozen_task_bindings([spec])[spec.task_id]
        changed = dict(frozen)
        changed["task_contract_sha256"] = "0" * 64
        initial = {
            "git_available": True,
            "git_revision": "abc",
            "source_tree_dirty": False,
            "source_changes": [],
        }
        final = dict(initial, source_tree_dirty=True, source_changes=[" M sle/x.py"])
        with patch.object(
            MODULE, "_frozen_task_bindings", return_value={spec.task_id: changed},
        ), patch.object(MODULE, "source_provenance", return_value=final):
            errors = MODULE._final_integrity_errors(
                [spec], {spec.task_id: frozen}, initial
            )
        self.assertEqual(errors, ["task_binding_changed", "source_provenance_changed"])

    @skip_unless_sandbox("bwrap")  # runs the baseline through the real harness
    def test_block_resume_retries_started_cell_then_runs_unstarted_cells(self):
        task = "Chemistry/LennardJonesCluster"
        modes = ["normal", "score_only"]
        source = MODULE.find_task(
            task, include_uncertified=True
        ).initial_program_path.read_text(encoding="utf-8")
        task_spec = MODULE.find_task(task, include_uncertified=True)
        frozen_binding = MODULE._frozen_task_bindings([task_spec])[task]
        fenced = "```python\n%s\n```" % source
        config = LLMConfig(
            wire="chat", base_url="https://example.invalid/v1",
            model="fixture", max_output_tokens=20, temperature=0.0,
            timeout_seconds=1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "block_index": 1,
                "task": task,
                "algorithm": "greedy_rewrite",
                "seed": 0,
                "feedback_modes": modes,
                "llm_config": config,
                "work_root": str(root),
                "budget": 1,
                "timeout_s": 20.0,
                "resume": False,
                "skip_keys": [],
                "frozen_task_binding": frozen_binding,
            }
            failing = type("Failing", (), {
                "config": config,
                "last_usage": {},
                "complete": lambda self, prompt, system=None: (
                    (_ for _ in ()).throw(RuntimeError("offline"))
                ),
            })()
            with patch.object(MODULE, "LLMClient", return_value=failing):
                first = MODULE._execute_block(payload)
            self.assertEqual(len(first["entries"]), 2)
            self.assertIn("LLMInfrastructureError", first["entries"][0]["error"])
            self.assertTrue(first["entries"][0]["attempt_started"])
            self.assertEqual(
                first["entries"][1]["error"],
                "BlockedByPriorConditionError: earlier condition failed before "
                "this scheduled condition could start",
            )
            self.assertEqual(
                first["entries"][1]["blocked_by_run_key"],
                "Chemistry/LennardJonesCluster|greedy_rewrite|normal|0",
            )
            self.assertFalse(first["entries"][1]["attempt_started"])
            normal_dir = (
                root / "Chemistry__LennardJonesCluster" / "greedy_rewrite"
                / "normal" / "seed_0"
            )
            self.assertTrue((normal_dir / "checkpoint.json").is_file())
            self.assertEqual(
                len((normal_dir / "trajectory.jsonl").read_text().splitlines()), 1
            )
            self.assertEqual(
                len(first["entries"][0]["trajectory_snapshot"]["events"]), 1
            )

            replies = iter([fenced, fenced])
            recovered = type("Recovered", (), {
                "config": config,
                "last_usage": {},
                "complete": lambda self, prompt, system=None: next(replies),
            })()
            payload["resume"] = True
            with patch.object(MODULE, "LLMClient", return_value=recovered):
                second = MODULE._execute_block(payload)
            self.assertEqual(len(second["entries"]), 2)
            self.assertFalse(any(row.get("error") for row in second["entries"]))
            self.assertEqual(
                [row["within_block_position"] for row in second["entries"]],
                [1, 2],
            )
            self.assertEqual(
                len((normal_dir / "trajectory.jsonl").read_text().splitlines()), 2
            )

    def test_aggregation_uses_latest_attempt_without_dropping_history(self):
        failed = {"task": "T/X", "algorithm": "greedy_rewrite",
                  "feedback_mode": "normal", "seed": 0, "error": "offline",
                  **self.runtime_fields()}
        successful = {
            "task": "T/X", "algorithm": "greedy_rewrite", "feedback_mode": "normal",
            "seed": 0, "best": 0.3,
            **self.runtime_fields(),
            "summary": {"best_so_far_auc": 0.2, "budget_units": 2, "oracle_calls": 2,
                        "wall_seconds": 1, "llm": {"total_tokens": None,
                                                   "estimated_cost_usd": None}},
        }
        got = MODULE.aggregate_runs([failed, successful])
        self.assertEqual(got["attempt_count"], 2)
        self.assertEqual(got["superseded_attempts"], 1)
        self.assertEqual(got["failed_attempts"], 1)
        self.assertEqual(got["attempt_failure_rate"], 0.5)
        self.assertEqual(got["recovered_runs"], 1)
        self.assertEqual(got["successful_runs"], 1)
        self.assertEqual(got["failed_runs"], 0)
        self.assertEqual(got["intent_to_evaluate"], {
            "scheduled_runs": 1,
            "successful_runs": 1,
            "terminal_failed_runs": 0,
            "completion_rate": 1.0,
            "observed_run_rows": 1,
            "missing_run_rows": 0,
            "run_cells_with_any_failed_attempt": 1,
            "run_cells_with_protocol_incomplete_attempt": 0,
            "recovered_runs": 1,
        })
        self.assertEqual(got["first_attempt_intent_to_evaluate"], {
            "scheduled_runs": 1,
            "observed_run_rows": 1,
            "missing_run_rows": 0,
            "successful_runs": 0,
            "failed_runs": 1,
            "completion_rate": 0.0,
        })
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["attempt_count"], 2)
        self.assertEqual(condition["failed_attempts"], 1)
        self.assertEqual(condition["recovered_runs"], 1)

    def test_aggregation_uses_frozen_schedule_for_missing_run_rows(self):
        successful = {
            "task": "T/X", "algorithm": "greedy_rewrite",
            "feedback_mode": "normal", "seed": 0, "best": 0.3,
            **self.runtime_fields(),
            "summary": {
                "best_so_far_auc": 0.2, "budget_units": 2,
                "oracle_calls": 2, "wall_seconds": 1,
                "llm": {"total_tokens": None, "estimated_cost_usd": None},
            },
        }
        scheduled = {
            "T/X|greedy_rewrite|normal|0",
            "T/X|greedy_rewrite|normal|1",
        }
        got = MODULE.aggregate_runs(
            [successful], scheduled_run_keys=scheduled
        )
        self.assertEqual(got["intent_to_evaluate"]["scheduled_runs"], 2)
        self.assertEqual(got["intent_to_evaluate"]["terminal_failed_runs"], 1)
        self.assertEqual(got["intent_to_evaluate"]["completion_rate"], 0.5)
        self.assertEqual(got["first_attempt_intent_to_evaluate"], {
            "scheduled_runs": 2,
            "observed_run_rows": 1,
            "missing_run_rows": 1,
            "successful_runs": 1,
            "failed_runs": 1,
            "completion_rate": 0.5,
        })

    def test_failed_condition_stays_visible_without_valid_quality_rows(self):
        failed = {"task": "T/X", "algorithm": "greedy_rewrite",
                  "feedback_mode": "normal", "seed": 0, "error": "offline",
                  **self.runtime_fields()}
        got = MODULE.aggregate_runs([failed])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 0)
        self.assertEqual(condition["scheduled_n"], 1)
        self.assertEqual(condition["terminal_failed_runs"], 1)
        self.assertEqual(condition["completion_rate"], 0.0)
        self.assertEqual(condition["best_score"]["n"], 0)
        self.assertEqual(got["failed_attempts"], 1)
        self.assertEqual(got["intent_to_evaluate"]["completion_rate"], 0.0)
        self.assertEqual(got["overall_valid_only"], {})

    def test_fixed_duration_budget_exhaustion_is_protocol_incomplete(self):
        incomplete = {
            "task": "T/X",
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
            "seed": 0,
            "best": 0.8,
            **self.runtime_fields(),
            "protocol_incomplete": (
                "proposal_budget_exhausted_before_active_wall_horizon"
            ),
            "summary": {
                "best_so_far_auc": 0.7,
                "budget_units": 4,
                "oracle_calls": 4,
                "wall_seconds": 20,
                "llm": {"total_tokens": 100, "estimated_cost_usd": None},
            },
        }
        got = MODULE.aggregate_runs([incomplete])
        condition = got["by_condition"]["T/X|greedy_rewrite|normal"]
        self.assertEqual(condition["n"], 0)
        self.assertEqual(condition["protocol_incomplete_attempts"], 1)
        self.assertEqual(got["successful_runs"], 0)
        self.assertEqual(got["failed_runs"], 1)
        self.assertEqual(got["protocol_incomplete_attempts"], 1)
        self.assertEqual(
            got["intent_to_evaluate"][
                "run_cells_with_protocol_incomplete_attempt"
            ],
            1,
        )

    @skip_unless_sandbox("bwrap")  # runs the baseline through the real harness
    def test_complete_smoke_writes_passed_status(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {"git_available": True, "git_revision": "abc",
                 "source_tree_dirty": False, "source_changes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            output = Path(tmp) / "report.json"
            workdir = Path(tmp) / "runs"
            result = MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertTrue(report["passed"])
            self.assertTrue(report["execution_passed"])
            self.assertTrue(report["trusted_evidence"])
            self.assertEqual(report["final_integrity"], {"passed": True, "errors": []})
            snapshot = report["runs"][0]["trajectory_snapshot"]
            self.assertEqual(report["config"]["trajectory_snapshot_schema_version"], 2)
            self.assertEqual(snapshot["schema_version"], 2)
            self.assertEqual(len(snapshot["trajectory_sha256"]), 64)
            self.assertEqual(len(snapshot["events"]), 1)
            self.assertEqual(snapshot["events"][0]["schema_version"], 2)
            self.assertIn("wall_seconds", snapshot["events"][0])
            self.assertIn("cumulative_wall_seconds", snapshot["events"][0])
            task_id = "Chemistry/LennardJonesCluster"
            runtime = report["config"]["frozen_task_bindings"][task_id]
            self.assertEqual(
                report["runs"][0]["trusted_evaluator_runtime"],
                runtime["trusted_evaluator_runtime"],
            )
            self.assertEqual(
                report["runs"][0]["trusted_evaluator_runtime_sha256"],
                runtime["trusted_evaluator_runtime_sha256"],
            )
            self.assertEqual(
                report["aggregate"][
                    "trusted_evaluator_runtime_sha256_by_task"
                ],
                {task_id: runtime["trusted_evaluator_runtime_sha256"]},
            )
            self.assertEqual(
                report["config"]["work_root_scope"],
                "local_only_not_portable_evidence_identity",
            )
            self.assertEqual(
                report["runs"][0]["workdir_scope"],
                "local_only_not_portable_evidence_identity",
            )

    def test_nonzero_protocol_smoke_cannot_be_labelled_model_performance(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {"git_available": True, "git_revision": "abc",
                 "source_tree_dirty": False, "source_changes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            root = Path(tmp)
            output = root / "report.json"
            # Budget zero keeps this fixture offline, while run-role exercises
            # the same evidence-scope branch used by a nonzero protocol smoke.
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--budget", "0",
                "--seeds", "0",
                "--run-role", "protocol_smoke",
                "--workdir", str(root / "runs"),
                "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            report["evidence_scope"],
            "PROTOCOL_SMOKE_ONLY_NOT_MODEL_PERFORMANCE",
        )
        self.assertEqual(report["config"]["run_role"], "protocol_smoke")
        self.assertIn("do not treat", report["warning"])

    @skip_unless_sandbox("bwrap")  # runs the baseline through the real harness
    def test_preregistration_is_hash_bound_into_config(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {"git_available": True, "git_revision": "abc",
                 "source_tree_dirty": False, "source_changes": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            root = Path(tmp)
            preregistration = root / "prereg.json"
            preregistration.write_text('{"version":3}\n', encoding="utf-8")
            output = root / "report.json"
            self.assertEqual(MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(root / "runs"),
                "--output", str(output), "--preregistration", str(preregistration),
            ]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            bound = report["config"]["preregistration"]
            self.assertEqual(bound["path"], str(preregistration.resolve()))
            self.assertEqual(bound["bytes"], len(preregistration.read_bytes()))
            self.assertEqual(len(bound["sha256"]), 64)

            preregistration.write_text('{"version":4}\n', encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "config does not match"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                    "--timeout", "20", "--workdir", str(root / "runs"),
                    "--output", str(output), "--preregistration", str(preregistration),
                    "--resume",
                ])

    def test_execution_preregistration_enforces_command_model_and_task_package(self):
        spec = MODULE.find_task("LennardJonesCluster", include_uncertified=True)
        client = type("Client", (), {"config": self.Config()})()
        descriptor = current_runtime_descriptor(())
        binding = {
            "task_contract_sha256": MODULE.task_contract_sha256(spec),
            "task_package_sha256": MODULE.task_package_sha256(spec),
            "task_card_sha256": MODULE.hashlib.sha256(
                (spec.task_dir / "TASK_CARD.yaml").read_bytes()
            ).hexdigest(),
            "runtime_source_sha256": MODULE.runtime_source_sha256(),
            **MODULE.frontier_binding(spec),
            "trusted_evaluator_runtime": descriptor,
            "trusted_evaluator_runtime_sha256": descriptor[
                "fingerprint_sha256"
            ],
        }
        bindings = {spec.task_id: binding}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "_execution_preregistration_is_committed", return_value=True
        ):
            path = Path(tmp) / "execution_prereg.json"
            cohort = _current_cohort_manifest()
            document = {
                "schema_version": 1,
                "preregistration_id": "test_execution_contract",
                "source_cohort": {
                    "path": str(cohort.relative_to(MODULE.ROOT)),
                    "sha256": MODULE.hashlib.sha256(cohort.read_bytes()).hexdigest(),
                },
                "model_condition": {
                    "llm_condition_sha256": MODULE.llm_condition_sha256(client),
                },
                "design": {
                    "primary_command": [
                        "python3", "scripts/batch_evolve.py",
                        "--tasks", "LennardJonesCluster",
                    ],
                    "tasks": [{"task": spec.task_id, **binding}],
                },
                "prerequisites": [],
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            record = MODULE._preregistration_record(
                path,
                raw_argv=["--tasks", "LennardJonesCluster"],
                specs=[spec],
                llm=client,
                task_bindings=bindings,
            )
            self.assertTrue(record["execution_contract_validated"])
            self.assertTrue(record["command_contract_matches"])
            self.assertFalse(record["readable_model_condition_matches"])
            self.assertEqual(
                record["readable_model_condition_status"], "not_declared"
            )
            resumed = MODULE._preregistration_record(
                path,
                raw_argv=["--tasks", "LennardJonesCluster", "--resume"],
                specs=[spec],
                llm=client,
                task_bindings=bindings,
            )
            self.assertEqual(record, resumed)

            document["design"]["resume_permitted"] = False
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "does not permit resume"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster", "--resume"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )
            document["design"].pop("resume_permitted")

            document["model_condition"]["required_readable_fields"] = [
                "model", "wire"
            ]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "missing readable model"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )
            document["model_condition"].update({
                "model": client.config.model,
                "wire": client.config.wire,
            })
            path.write_text(json.dumps(document), encoding="utf-8")
            readable = MODULE._preregistration_record(
                path,
                raw_argv=["--tasks", "LennardJonesCluster"],
                specs=[spec],
                llm=client,
                task_bindings=bindings,
            )
            self.assertTrue(readable["readable_model_condition_matches"])
            self.assertEqual(
                readable["readable_model_condition_status"], "matched"
            )
            for field in ("required_readable_fields", "model", "wire"):
                document["model_condition"].pop(field)

            document["model_condition"]["model"] = "different-model"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "readable model condition"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )
            document["model_condition"].pop("model")

            with self.assertRaisesRegex(SystemExit, "runtime command differs"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster", "--budget", "1"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )

            document["source_cohort"]["sha256"] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "source_cohort hash differs"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )
            document["source_cohort"]["sha256"] = MODULE.hashlib.sha256(
                cohort.read_bytes()
            ).hexdigest()
            document["design"]["tasks"][0]["task_package_sha256"] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "task_package_sha256 differs"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )

            document["design"]["tasks"][0]["task_package_sha256"] = (
                MODULE.task_package_sha256(spec)
            )
            document["design"]["tasks"][0][
                "trusted_evaluator_runtime_sha256"
            ] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(
                SystemExit, "trusted evaluator runtime differs"
            ):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                    task_bindings=bindings,
                )

    def test_execution_preregistration_rejects_uncommitted_file(self):
        spec = MODULE.find_task("LennardJonesCluster", include_uncertified=True)
        client = type("Client", (), {"config": self.Config()})()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution_prereg.json"
            path.write_text(json.dumps({
                "design": {
                    "primary_command": [
                        "python3", "scripts/batch_evolve.py",
                        "--tasks", "LennardJonesCluster",
                    ],
                },
            }), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "tracked and match HEAD"):
                MODULE._preregistration_record(
                    path,
                    raw_argv=["--tasks", "LennardJonesCluster"],
                    specs=[spec],
                    llm=client,
                )

    def test_cohort_manifest_binds_order_contract_and_task_card(self):
        tasks = [
            "Electrochemistry/ElectrolyteConductivityDesign",
            "Optics/DiffractionGratingDesign",
        ]
        specs = [
            MODULE.find_task(task, include_uncertified=True) for task in tasks
        ]
        rows = []
        for spec in specs:
            rows.append({
                "task": spec.task_id,
                "maturity_contract_sha256": MODULE._maturity_contract_sha256(spec),
                "runtime_contract_sha256": MODULE.task_contract_sha256(spec),
                "task_card_sha256": MODULE.hashlib.sha256(
                    (spec.task_dir / "TASK_CARD.yaml").read_bytes()
                ).hexdigest(),
            })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohort.json"
            document = {
                "schema_version": 1,
                "manifest_id": "fixture",
                "analysis_role": "exploratory",
                "claim_limit": "not_confirmatory",
                "selection": {"confirmatory_reuse_permitted": False},
                "tasks": rows,
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            record = MODULE._cohort_manifest_record(
                path, specs, include_uncertified=True
            )
            self.assertEqual(record["task_count"], 2)
            self.assertFalse(record["confirmatory_reuse_permitted"])
            self.assertEqual(record["manifest_id"], "fixture")

            with self.assertRaisesRegex(SystemExit, "task order"):
                MODULE._cohort_manifest_record(
                    path, list(reversed(specs)), include_uncertified=True
                )
            document["tasks"][0]["runtime_contract_sha256"] = "0" * 64
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "runtime contract"):
                MODULE._cohort_manifest_record(
                    path, specs, include_uncertified=True
                )
            document["tasks"][0]["maturity_contract_sha256"] = "0" * 64
            document["tasks"][0]["runtime_contract_sha256"] = (
                MODULE.task_contract_sha256(specs[0])
            )
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "maturity contract"):
                MODULE._cohort_manifest_record(
                    path, specs, include_uncertified=True
                )

    def test_frozen_exploratory_manifest_matches_current_contracts(self):
        """The *current* manifest, not the one frozen first.

        Naming the original by filename meant this test kept checking a manifest that rebinding
        had superseded, so it went on failing after the rebinding that was supposed to fix it -
        and it failed on `maturity contract differs`, which was true of the old file and not of
        the live one. Reading the preflight's manifest makes the test follow a rebinding, which is
        the behaviour it is asking about.
        """
        path = _current_cohort_manifest()
        document = json.loads(path.read_text(encoding="utf-8"))
        specs = [
            MODULE.find_task(row["task"], include_uncertified=True)
            for row in document["tasks"]
        ]
        record = MODULE._cohort_manifest_record(
            path, specs, include_uncertified=True
        )
        self.assertEqual(record["task_count"], 7)
        self.assertEqual(
            record["analysis_role"],
            "result_selected_exploratory_measurement_screen",
        )
        self.assertFalse(record["confirmatory_reuse_permitted"])

    @skip_unless_sandbox("bwrap")  # runs the baseline through the real harness
    def test_resume_rejects_changed_experiment_config(self):
        client = type("Client", (), {"config": self.Config()})()

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value={
            "git_available": True, "git_revision": "abc",
            "source_tree_dirty": False, "source_changes": [],
        }):
            output = Path(tmp) / "report.json"
            workdir = Path(tmp) / "runs"
            self.assertEqual(MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
            ]), 0)
            with self.assertRaisesRegex(SystemExit, "config does not match"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster", "--budget", "1", "--seeds", "0",
                    "--timeout", "20", "--workdir", str(workdir), "--output", str(output),
                    "--resume",
                ])

    @skip_unless_sandbox("bwrap")
    def test_resume_skips_only_the_verified_matching_run_cell(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {
            "git_available": True, "git_revision": "abc",
            "source_tree_dirty": False, "source_changes": [],
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client,
        ), patch.object(MODULE, "source_provenance", return_value=clean):
            output = Path(tmp) / "report.json"
            workdir = Path(tmp) / "runs"
            arguments = [
                "--tasks", "LennardJonesCluster", "--budget", "0",
                "--seeds", "0", "--timeout", "20",
                "--workdir", str(workdir), "--output", str(output),
            ]
            self.assertEqual(MODULE.main(arguments), 0)
            with patch.object(
                MODULE, "_execute_block",
                side_effect=AssertionError("verified cell was rerun"),
            ) as execute:
                self.assertEqual(MODULE.main([*arguments, "--resume"]), 0)
            execute.assert_not_called()
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(report["runs"]), 1)

    @skip_unless_sandbox("bwrap")  # runs the baseline through the real harness
    def test_dirty_smoke_executes_but_is_not_trusted_evidence(self):
        client = type("Client", (), {"config": self.Config()})()
        dirty = {"git_available": True, "git_revision": "abc", "source_tree_dirty": True,
                 "source_changes": [" M sle/x.py"]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client
        ), patch.object(MODULE, "source_provenance", return_value=dirty):
            output = Path(tmp) / "report.json"
            result = MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0", "--seeds", "0",
                "--timeout", "20", "--workdir", str(Path(tmp) / "runs"),
                "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertTrue(report["execution_passed"])
            self.assertFalse(report["trusted_evidence"])
            self.assertFalse(report["passed"])

    @skip_unless_sandbox("bwrap")
    def test_final_binding_failure_prevents_trusted_completion(self):
        client = type("Client", (), {"config": self.Config()})()
        clean = {
            "git_available": True, "git_revision": "abc",
            "source_tree_dirty": False, "source_changes": [],
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            MODULE, "load_llm_client", return_value=client,
        ), patch.object(
            MODULE, "source_provenance", return_value=clean,
        ), patch.object(
            MODULE, "_final_integrity_errors",
            return_value=["task_binding_changed"],
        ):
            output = Path(tmp) / "report.json"
            result = MODULE.main([
                "--tasks", "LennardJonesCluster", "--budget", "0",
                "--seeds", "0", "--timeout", "20",
                "--workdir", str(Path(tmp) / "runs"),
                "--output", str(output),
            ])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertEqual(report["final_integrity"], {
            "passed": False, "errors": ["task_binding_changed"],
        })
        self.assertFalse(report["execution_passed"])
        self.assertFalse(report["trusted_evidence"])

    def test_greedy_only_controls_reject_unsupported_backend_mix(self):
        for mode in ("score_only", "delayed_replay", "selection_blind"):
            with self.subTest(mode=mode), self.assertRaisesRegex(
                SystemExit, "only for greedy_rewrite"
            ):
                MODULE.main([
                    "--tasks", "LennardJonesCluster",
                    "--algorithms", "greedy_rewrite,openevolve",
                    "--feedback-modes", mode,
                    "--budget", "0",
                ])

    def test_non_greedy_backend_is_rejected_before_client_or_backend_creation(self):
        with patch.object(MODULE, "_trusted_runtime_records") as runtimes, patch.object(
            MODULE, "load_llm_client"
        ) as client, patch.object(MODULE, "get_algorithm") as backend:
            with self.assertRaisesRegex(SystemExit, "durable receipt verification"):
                MODULE.main([
                    "--tasks", "LennardJonesCluster",
                    "--algorithms", "abmcts",
                    "--budget", "0",
                ])
        runtimes.assert_not_called()
        client.assert_not_called()
        backend.assert_not_called()

    def test_active_wall_horizon_is_greedy_only_and_interval_requires_horizon(self):
        with self.assertRaisesRegex(SystemExit, "requires --active-wall-horizon"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--sentinel-interval", "30",
                "--budget", "0",
            ])
        with self.assertRaisesRegex(SystemExit, "requires --active-wall-horizon"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--signed-decisions",
                "--budget", "0",
            ])
        with self.assertRaisesRegex(SystemExit, "requires --signed-decisions"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--active-wall-horizon", "120",
                "--signed-decision-policy", "honor_stop",
                "--budget", "0",
            ])
        with self.assertRaisesRegex(SystemExit, "only for greedy_rewrite"):
            MODULE.main([
                "--tasks", "LennardJonesCluster",
                "--algorithms", "abmcts",
                "--active-wall-horizon", "120",
                "--budget", "0",
            ])


if __name__ == "__main__":
    unittest.main()
