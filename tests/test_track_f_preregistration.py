from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_track_f_preregistration.py"
SPEC = importlib.util.spec_from_file_location("track_f_prereg_for_test", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrackFPreregistrationTests(unittest.TestCase):
    def test_williams_schedule_is_seeded_reproducible_and_balanced(self):
        replicates = list(range(48))
        first = MODULE.condition_schedule(replicates, 71390421)
        repeated = MODULE.condition_schedule(replicates, 71390421)
        changed = MODULE.condition_schedule(replicates, 71390422)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)
        self.assertEqual(
            [row["replicate_identifier"] for row in first], replicates
        )
        rows = [row["feedback_modes"] for row in first]
        for position in range(4):
            self.assertEqual(
                {
                    mode: sum(row[position] == mode for row in rows)
                    for mode in MODULE.MODES
                },
                {mode: 12 for mode in MODULE.MODES},
            )
        carryovers = [
            (row[position], row[position + 1])
            for row in rows
            for position in range(3)
        ]
        expected_pairs = {
            (left, right)
            for left in MODULE.MODES
            for right in MODULE.MODES
            if left != right
        }
        self.assertEqual(set(carryovers), expected_pairs)
        self.assertEqual(
            {
                pair: sum(value == pair for value in carryovers)
                for pair in expected_pairs
            },
            {pair: 12 for pair in expected_pairs},
        )

    def test_schedule_rejects_duplicate_replicates_and_boolean_seed(self):
        with self.assertRaisesRegex(ValueError, "Williams"):
            MODULE.condition_schedule([0, 0], 1)
        with self.assertRaisesRegex(ValueError, "Williams"):
            MODULE.condition_schedule([0, 1], True)

    def test_main_refuses_to_overwrite_preregistration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "prereg.json"
            output.write_text("occupied\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "overwrite"):
                MODULE.main([
                    "--precision", str(root / "precision.json"),
                    "--commitment", str(root / "commitment.json"),
                    "--full-suite", str(root / "full.json"),
                    "--security", str(root / "security.json"),
                    "--certification", str(root / "certification.json"),
                    "--smoke", str(root / "smoke.json"),
                    "--search-report", str(root / "search.json"),
                    "--search-work-root", str(root / "runs"),
                    "--condition-order-randomization-seed", "1",
                    "--confirmation-randomization-seed", "2",
                    "--search-block-workers", "2",
                    "--confirmation-workers", "2",
                    "--output", str(output),
                ])

    def test_builder_binds_clean_evidence_commitment_and_analyzer(self):
        revision = "a" * 40
        clean = {
            "git_available": True,
            "git_revision": revision,
            "source_tree_dirty": False,
            "source_changes": [],
            "source_scope": ["frontier_science", "scripts", "tests", "benchmarks"],
        }
        task_bindings = []
        for task in MODULE.TASKS:
            spec = MODULE.find_task(task, include_uncertified=True)
            task_bindings.append({
                "task": task,
                "task_contract_sha256": MODULE.task_contract_sha256(spec),
                "generator": (
                    "active_law_fresh_v1"
                    if task == MODULE.TASKS[0]
                    else "diffraction_grating_fresh_v1"
                ),
                "world_count": 7 if task == MODULE.TASKS[0] else 3,
            })
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def write(name, document):
                path = root / (name + ".json")
                path.write_text(json.dumps(document) + "\n", encoding="utf-8")
                return path

            common = {
                "schema_version": 1,
                "execution_passed": True,
                "trusted_evidence": True,
                "passed": True,
                "source_provenance": clean,
            }
            precision = write("precision", {
                **common,
                "fixed_balanced_blocks_per_condition": 48,
                "scheduled_search_cells": 384,
                "scheduled_model_proposals": 1152,
                "design": {
                    "primary_task": MODULE.TASKS[0],
                    "primary_contrast": "normal_minus_selection_blind",
                    "primary_horizon": "common_total_token_horizon",
                    "primary_fresh_confirmation_axis": (
                        "confirmation_normalized_mechanism_score"
                    ),
                    "secondary_stress_test_task": MODULE.TASKS[1],
                    "secondary_fresh_confirmation_axis": (
                        "confirmation_robustness_score"
                    ),
                    "provider_draw_assumption": "independent_unpaired",
                    "same_local_identifier_is_paired_seed": False,
                    "confirmatory_primary_hypothesis_count": 1,
                    "two_sided_alpha": 0.05,
                    "minimum_important_difference": 0.15,
                },
            })
            full = write("full", {
                **common, "unittest_ok": True, "test_count": 600,
            })
            security = write("security", {**common, "test_count": 23})
            certification = write("certification", {
                **common,
                "inventory_count": 59,
                "status_counts": {
                    "certified": 7, "candidate": 43, "quarantined": 9,
                },
            })
            commitment = write("commitment", {
                "schema_version": 1,
                "commitment_version": 1,
                "purpose": "track_f_fresh_confirmation_context_commitment",
                "source_provenance": clean,
                "source_binding": {
                    "git_revision": revision,
                    "runtime_source_sha256": MODULE.runtime_source_sha256(),
                    "tasks": task_bindings,
                },
                "private_manifest_sha256": "b" * 64,
                "private_manifest_utf8_bytes": 1234,
                "block_count": 96,
                "blocks": [
                    {
                        "task": task,
                        "replicate_id": replicate,
                        "panel_id": "fixture-%d" % replicate,
                        "generator": (
                            "active_law_fresh_v1"
                            if task == MODULE.TASKS[0]
                            else "diffraction_grating_fresh_v1"
                        ),
                        "world_count": 7 if task == MODULE.TASKS[0] else 3,
                        "context_sha256": hashlib.sha256(
                            (task + str(replicate)).encode("utf-8")
                        ).hexdigest(),
                        "context_utf8_bytes": 100,
                    }
                    for task in MODULE.TASKS for replicate in range(48)
                ],
            })
            smoke = root / "future_smoke.json"
            client = type("Client", (), {
                "config": type("Config", (), {
                    "wire": "responses",
                    "base_url": "https://example.invalid/v1",
                    "model": "gpt-5.5",
                    "max_output_tokens": 16000,
                    "temperature": None,
                    "reasoning_effort": "low",
                    "timeout_seconds": 900,
                    "extra_headers": {},
                    "input_cost_per_million": None,
                    "output_cost_per_million": None,
                })(),
            })()
            with patch.object(
                MODULE, "source_provenance", return_value=clean
            ), patch.object(MODULE, "load_llm_client", return_value=client):
                document = MODULE.build(
                    precision_path=precision,
                    commitment_path=commitment,
                    full_suite_path=full,
                    security_path=security,
                    certification_path=certification,
                    smoke_path=smoke,
                    search_report_path=root / "future_search.json",
                    search_work_root=root / "future_runs",
                    condition_order_randomization_seed=71923,
                    confirmation_randomization_seed=89123,
                    search_block_workers=8,
                    confirmation_workers=8,
                    llm_config=None,
                )
        self.assertEqual(document["frozen_source"]["revision"], revision)
        self.assertEqual(document["design"]["fixed_blocks_per_condition"], 48)
        self.assertEqual(document["design"]["scheduled_cell_count"], 384)
        self.assertEqual(document["confirmation_commitment"]["block_count"], 96)
        self.assertEqual(document["design"]["search_block_workers"], 8)
        self.assertEqual(document["design"]["confirmation_workers"], 8)
        self.assertEqual(
            document["analysis_implementation"]["sha256"],
            hashlib.sha256(MODULE.ANALYZER.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            document["analysis"]["statistical_test"],
            "two_sided_independent_welch_t",
        )
        self.assertFalse(
            document["claims_before_outcomes"]["feedback_effect_identified"]
        )


if __name__ == "__main__":
    unittest.main()
