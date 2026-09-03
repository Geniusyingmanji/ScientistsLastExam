from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Chemistry/AlloyHardnessOptimization"
DATA = TASK / "verification/alloy_hardness_v1.json"
DATA_SHA256 = "a55effd2a4077b63a19a45a91729698e07b1bd9e89a72da79b87f2528a09d003"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "alloy_hardness_test_oracle")
BUILDER = _load(
    ROOT / "scripts/build_alloy_hardness_data.py", "alloy_hardness_builder_test"
)
CALIBRATION = _load(
    ROOT / "scripts/calibrate_alloy_hardness_optimization.py",
    "alloy_hardness_calibration_test",
)
ADMISSION = _load(
    ROOT / "scripts/audit_candidate_wave10.py", "alloy_hardness_admission_test"
)


class AlloyHardnessOptimizationTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "MaterialsScience/AlloyHardnessOptimization", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_data_hash_provenance_counts_and_doi_partition(self):
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), DATA_SHA256)
        document = json.loads(DATA.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(
            document["builder_version"], "alloy-hardness-optimization-v1"
        )
        source = document["source"]
        self.assertEqual(source["article"]["doi"], "10.1038/s41597-020-00768-9")
        self.assertEqual(source["article"]["license"], "CC-BY-4.0")
        self.assertEqual(
            source["dataset"]["doi"], "10.6084/m9.figshare.12642953.v9"
        )
        self.assertEqual(source["dataset"]["size_bytes"], BUILDER.SOURCE_SIZE)
        self.assertEqual(source["dataset"]["md5"], BUILDER.SOURCE_MD5)
        self.assertEqual(source["dataset"]["sha256"], BUILDER.SOURCE_SHA256)
        self.assertEqual(
            source["upstream_repository"]["commit"], BUILDER.UPSTREAM_COMMIT
        )
        contract = document["contract"]
        self.assertEqual(contract["total_csv_row_count"], 1545)
        self.assertEqual(contract["eligible_raw_row_count"], 358)
        self.assertEqual(contract["historical_pool_recipe_count"], 205)
        self.assertEqual(contract["historical_proxy_recipe_count"], 197)
        self.assertEqual(contract["historical_study_count"], 44)
        self.assertEqual(contract["reserved_confirmation_recipe_count"], 9)
        self.assertEqual(contract["reserved_confirmation_study_count"], 8)
        self.assertEqual(contract["target_world_count"], 13)
        self.assertEqual(contract["target_recipe_count"], 65)
        self.assertEqual(len(ORACLE.DEVELOPMENT_WORLDS), 8)
        self.assertEqual(len(ORACLE.HELDOUT_WORLDS), 5)
        proxy = contract["proxy"]
        self.assertEqual(proxy["alpha"], 100.0)
        self.assertEqual(proxy["alpha_grid"], [0.1, 1.0, 10.0, 100.0, 1000.0])
        self.assertEqual(len(proxy["historical_leave_one_doi_out"]), 5)
        self.assertTrue(all(
            row["heldout_study_count"] == 44
            for row in proxy["historical_leave_one_doi_out"]
        ))
        self.assertEqual(
            min(
                proxy["historical_leave_one_doi_out"],
                key=lambda row: (
                    row["equal_study_weight_rmse_hv"], row["alpha"]
                ),
            )["alpha"],
            proxy["alpha"],
        )

        source_dois = {
            row["doi"] for row in document["historical_source_recipes"]
        }
        target_dois = {world["source_doi"] for world in document["worlds"]}
        self.assertFalse(source_dois & target_dois)
        self.assertEqual(len(target_dois), 13)
        self.assertEqual(
            len({row["id"] for world in document["worlds"]
                 for row in world["candidates"]}),
            65,
        )
        ranked = sorted(
            target_dois,
            key=lambda doi: hashlib.sha256(
                ("doi:" + doi).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            {
                world["source_doi"] for world in document["worlds"]
                if world["split"] == "development"
            },
            set(ranked[:8]),
        )

    def test_builder_reconstructs_exact_data_from_fixed_source_when_available(self):
        source = Path("/tmp/MPEA_dataset.csv")
        if not source.is_file():
            self.skipTest("fixed upstream MPEA CSV is not present")
        rebuilt = BUILDER.build(source)
        rendered = json.dumps(
            rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
        ) + "\n"
        self.assertEqual(rendered.encode("utf-8"), DATA.read_bytes())

    def test_builder_rejects_same_size_source_content_change(self):
        source = Path("/tmp/MPEA_dataset.csv")
        if not source.is_file():
            self.skipTest("fixed upstream MPEA CSV is not present")
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "MPEA_dataset.csv"
            payload = bytearray(source.read_bytes())
            payload[-2] ^= 1
            changed.write_bytes(payload)
            self.assertEqual(changed.stat().st_size, BUILDER.SOURCE_SIZE)
            with self.assertRaisesRegex(ValueError, "MD5"):
                BUILDER.build(changed)

    def test_formula_parser_is_order_and_whitespace_invariant(self):
        first = BUILDER._parse_formula("Al1 Co0.5 Cr0.5 Fe1")
        second = BUILDER._parse_formula("Fe1Cr0.5Co0.5Al1")
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(first.values()), 1.0)
        with self.assertRaises(ValueError):
            BUILDER._parse_formula("Al1(CoCr)1")

    def test_proxy_target_and_confirmation_evidence_lines_are_disjoint(self):
        document = ORACLE.DATA_DOCUMENT
        key = lambda row: (
            tuple(row["composition"].items()), row["processing_method"]
        )
        source_keys = {key(row) for row in document["historical_source_recipes"]}
        confirmation_keys = {
            key(row) for row in document["reserved_confirmation_recipes"]
        }
        target_keys = {
            key(row) for world in document["worlds"]
            for row in world["candidates"]
        }
        self.assertFalse(source_keys & target_keys)
        self.assertFalse(source_keys & confirmation_keys)
        self.assertTrue(confirmation_keys <= target_keys)

        source_lines = {
            line for row in document["historical_source_recipes"]
            for line in row["source_line_numbers"]
        }
        confirmation_lines = {
            line for row in document["reserved_confirmation_recipes"]
            for line in row["source_line_numbers"]
        }
        target_lines = {
            line for world in document["worlds"] for row in world["candidates"]
            for line in row["source_line_numbers"]
        }
        self.assertFalse(source_lines & confirmation_lines)
        self.assertFalse(source_lines & target_lines)
        self.assertFalse(confirmation_lines & target_lines)

        confirmation_records = [
            record for world in document["worlds"]
            for candidate in world["candidates"]
            for record in candidate["independent_exact_recipe_confirmations"]
        ]
        self.assertEqual(len(confirmation_records), 9)
        target_dois = {world["source_doi"] for world in document["worlds"]}
        self.assertTrue(all(
            record["doi"] not in target_dois for record in confirmation_records
        ))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_split_anchors_baseline_reference_and_truth_blind_headroom(self):
        anchors = ORACLE._anchors()
        for split in ("development", "heldout"):
            anchor = anchors["split_" + split]
            self.assertGreater(
                anchor["reference_utility"], anchor["baseline_utility"] + 0.05
            )
        baseline = ORACLE.evaluate(ORACLE._baseline_policy)
        reference = ORACLE.evaluate(ORACLE._reference_policy)
        spec = find_task(
            "MaterialsScience/AlloyHardnessOptimization", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(reference["combined_score"], 1.0)
        self.assertEqual(reference["heldout_policy_score"], 1.0)
        direct = json.loads(json.dumps(baseline, allow_nan=False))
        direct["raw_score"] = direct["combined_score"]
        self.assertEqual(secure, direct)
        result = ORACLE.evaluate(CALIBRATION.truth_blind_assay_policy)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertGreater(result["combined_score"], 0.30)
        self.assertGreater(result["heldout_policy_score"], 0.30)
        self.assertEqual(result["development_mean_assay_calls"], 2.0)
        self.assertEqual(result["heldout_mean_assay_calls"], 2.0)
        self.assertEqual(result["development_assay_unique_rate"], 1.0)
        self.assertEqual(result["heldout_assay_unique_rate"], 1.0)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_baseline_is_bit_exact_across_hash_seeds_and_secure_path(self):
        script = (
            "import importlib.util,json,pathlib;"
            "p=pathlib.Path(%r);"
            "s=importlib.util.spec_from_file_location('alloy_seed_oracle',p);"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "print(json.dumps(m.evaluate(m._baseline_policy),sort_keys=True,"
            "separators=(',',':'),allow_nan=False))"
        ) % str(TASK / "verification/evaluator.py")
        rendered = []
        for seed in ("0", "1", "2", "17", "123456"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            rendered.append(subprocess.check_output(
                [sys.executable, "-c", script], cwd=ROOT, env=env, text=True,
            ).strip())
        self.assertEqual(len(set(rendered)), 1)

        direct = json.loads(rendered[0])
        direct["raw_score"] = direct["combined_score"]
        spec = find_task(
            "MaterialsScience/AlloyHardnessOptimization", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(secure, direct)

    def test_calibration_and_candidate_admission_gates(self):
        source = Path("/tmp/MPEA_dataset.csv")
        if not source.is_file():
            self.skipTest("fixed upstream MPEA CSV is not present")
        calibration = CALIBRATION.calibrate(source)
        self.assertTrue(
            calibration["execution_passed"],
            {
                "failed_checks": [
                    key for key, value in calibration["checks"].items()
                    if not value
                ],
                "isolation": calibration["secure_isolation_and_failure_checks"],
                "secure_baseline_equal": calibration[
                    "secure_baseline_exactly_matches_direct"
                ],
            },
        )
        self.assertTrue(calibration["data_rebuild"]["exact_match"])
        self.assertTrue(all(calibration["checks"].values()))
        self.assertEqual(
            calibration["trusted_evidence"],
            calibration["source_provenance"]["source_tree_dirty"] is False,
        )
        self.assertEqual(calibration["passed"], calibration["trusted_evidence"])
        admission = ADMISSION.audit(source)
        self.assertTrue(admission["execution_passed"])
        self.assertEqual(admission["summary"]["recommended_candidate_count"], 1)
        self.assertEqual(admission["summary"]["recommended_quarantine_count"], 0)

    def test_public_problem_hides_identity_split_measurements_and_confirmation(self):
        hidden = {
            "source_doi", "source_year", "source_title", "split",
            "study_hardness_hv", "within_study_min_hv", "within_study_max_hv",
            "source_line_numbers", "reported_microstructures",
            "independent_exact_recipe_confirmations",
        }
        for world in ORACLE.WORLDS:
            problem = ORACLE._problem(world)
            rendered = json.dumps(problem, sort_keys=True)
            for field in hidden:
                self.assertNotIn('"%s"' % field, rendered)
            self.assertEqual(len(problem["candidates"]), len(world["candidates"]))
            self.assertEqual(problem["batch_size"], 3)
            self.assertEqual(problem["assay_budget"], 2)
            self.assertEqual(problem["required_prediction_confidence"], 0.90)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_secure_baseline_is_zero_and_science_metrics_are_sealed(self):
        spec = find_task(
            "MaterialsScience/AlloyHardnessOptimization", include_uncertified=True
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_world_call_count"], 13)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        visible = search_visible_metrics(metrics)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )
        for key in (
            "heldout_policy_score", "development_prediction_score",
            "development_proxy_false_promotion_rate",
            "development_independent_confirmation_mae_hv", "per_world",
        ):
            self.assertNotIn(key, visible)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_trusted_scoring_failure_is_not_candidate_invalidity(self):
        original = ORACLE._batch_utility
        try:
            def broken(*_args, **_kwargs):
                raise RuntimeError("trusted alloy scoring deliberately broken")

            ORACLE._batch_utility = broken
            with self.assertRaisesRegex(RuntimeError, "trusted alloy scoring"):
                ORACLE._evaluate_world(
                    ORACLE._baseline_policy, ORACLE.DEVELOPMENT_WORLDS[0], 0
                )
        finally:
            ORACLE._batch_utility = original

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_all_worlds_get_fresh_process_imports_and_tmpfs(self):
        result = self.evaluate_source(
            """
            from pathlib import Path
            CALLS = 0
            def design_alloy_batch(problem, assay):
                global CALLS
                CALLS += 1
                marker = Path('/tmp/alloy_seen')
                if CALLS != 1 or marker.exists():
                    return {'alloy_ids': [], 'predictions': {}}
                marker.write_text('seen')
                rows = problem['candidates'][:3]
                return {
                    'alloy_ids': [row['id'] for row in rows],
                    'predictions': {
                        row['id']: {
                            'predicted_hardness_hv': row['proxy_hardness_hv'],
                            'interval_hv': [0.0, 2000.0],
                        } for row in rows
                    },
                }
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_world_call_count"], 13)
        self.assertEqual(result["candidate_world_valid_rate"], 1.0)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_budget_repeat_and_invalid_assay_fail_closed_when_caught(self):
        bodies = (
            "for _ in range(3): assay(problem['candidates'][0]['id'])",
            "assay('unknown-alloy')",
        )
        template = """
            def design_alloy_batch(problem, assay):
                try:
                    BODY
                except Exception:
                    pass
                rows = problem['candidates'][:3]
                return {
                    'alloy_ids': [row['id'] for row in rows],
                    'predictions': {
                        row['id']: {
                            'predicted_hardness_hv': row['proxy_hardness_hv'],
                            'interval_hv': [0.0, 2000.0],
                        } for row in rows
                    },
                }
        """
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(template.replace("BODY", body))
                self.assertEqual(result["valid"], 0.0, result)
                expected = "budget_exceeded" if "range(3)" in body else "invalid_assay"
                self.assertTrue(all(
                    row["failure_kind"] == expected for row in result["per_world"]
                ))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_malformed_ids_prediction_keys_intervals_and_nonfinite_fail_closed(self):
        bodies = (
            "return {}",
            "return {'alloy_ids': [], 'predictions': {}}",
            "return make([rows[0], rows[0], rows[1]])",
            "return make(rows[:2])",
            "return {'alloy_ids': ['unknown', rows[0]['id'], rows[1]['id']], 'predictions': {}}",
            "value = make(rows[:3]); value['predictions'].pop(rows[0]['id']); return value",
            "value = make(rows[:3]); value['predictions'][rows[0]['id']]['interval_hv'] = [700.0, 300.0]; return value",
            "value = make(rows[:3]); value['predictions'][rows[0]['id']]['predicted_hardness_hv'] = float('nan'); return value",
        )
        template = """
            def design_alloy_batch(problem, assay):
                rows = problem['candidates']
                def make(selected):
                    return {
                        'alloy_ids': [row['id'] for row in selected],
                        'predictions': {
                            row['id']: {
                                'predicted_hardness_hv': row['proxy_hardness_hv'],
                                'interval_hv': [0.0, 2000.0],
                            } for row in selected
                        },
                    }
                BODY
        """
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(template.replace("BODY", body))
                self.assertEqual(result["valid"], 0.0, result)
                if "float('nan')" in body:
                    self.assertEqual(result["combined_score"], -1e18)
                    self.assertEqual(
                        result["candidate_failure_kind"],
                        "non_finite_candidate_value",
                    )
                else:
                    self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
