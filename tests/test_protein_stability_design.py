from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Biology/ProteinStabilityDesign"
DATA = TASK / "verification/protein_stability_landscapes_v1.json"
DATA_SHA256 = "7983438c683ea5b3a43bdd212b524413ecdbf1ece63cad79ab37b1149da1ba4a"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "protein_stability_test_oracle")
CALIBRATION = _load(
    ROOT / "scripts/calibrate_protein_stability_design.py",
    "protein_stability_calibration_test",
)
BUILDER = _load(
    ROOT / "scripts/build_protein_stability_data.py",
    "protein_stability_builder_test",
)


class ProteinStabilityDesignTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "ProteinEngineering/ProteinStabilityDesign", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_data_hash_provenance_worlds_and_reliable_protease_filters(self):
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), DATA_SHA256)
        document = json.loads(DATA.read_text(encoding="utf-8"))
        source = document["source"]
        self.assertEqual(source["article"]["doi"], "10.1038/s41586-023-06328-6")
        self.assertEqual(source["article"]["license"], "CC-BY-4.0")
        self.assertEqual(
            source["proteingym"]["dataset_doi"], "10.5281/zenodo.15293562"
        )
        self.assertEqual(source["proteingym"]["version"], "1.3")
        self.assertEqual(
            source["proteingym"]["repository_commit"], BUILDER.PROTEINGYM_COMMIT
        )
        self.assertEqual(
            source["supplementary_methods_sha256"],
            "7f8cea1118862735235984f477cd23ad900e0034aa5894dddbf11c0ade5aeb26",
        )
        self.assertEqual(len(ORACLE.DEVELOPMENT_WORLDS), 5)
        self.assertEqual(len(ORACLE.HELDOUT_WORLDS), 3)
        self.assertEqual(len({world["id"] for world in ORACLE.WORLDS}), 8)
        for world in ORACLE.WORLDS:
            with self.subTest(world=world["id"]):
                self.assertGreaterEqual(len(world["candidates"]), 300)
                self.assertEqual(world["candidate_count"], len(world["candidates"]))
                self.assertEqual(
                    len({row["sequence"] for row in world["candidates"]}),
                    len(world["candidates"]),
                )
                for row in world["candidates"]:
                    self.assertLess(
                        abs(row["trypsin_delta_g"]), BUILDER.DUMMY_DELTA_G_ABS_BOUND
                    )
                    self.assertLess(
                        abs(row["chymotrypsin_delta_g"]),
                        BUILDER.DUMMY_DELTA_G_ABS_BOUND,
                    )
                    for field in (
                        "combined_delta_g_95ci",
                        "trypsin_delta_g_95ci",
                        "chymotrypsin_delta_g_95ci",
                    ):
                        self.assertLessEqual(
                            row[field], BUILDER.MAX_RELIABLE_DELTA_G_95CI
                        )

    def test_builder_reconstructs_exact_data_from_fixed_sources_when_available(self):
        reference = Path(
            "/tmp/proteingym.JlV3Jy/reference_files/DMS_substitutions.csv"
        )
        processed = Path("/tmp/protein_data/DMS_ProteinGym_substitutions_v1.3.zip")
        raw = Path("/tmp/protein_data/substitutions_raw_DMS_v1.3.zip")
        if not all(path.is_file() for path in (reference, processed, raw)):
            self.skipTest("fixed upstream ProteinGym source files are not present")
        rebuilt = BUILDER.build(reference, processed, raw)
        rendered = json.dumps(
            rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
        ) + "\n"
        self.assertEqual(rendered.encode("utf-8"), DATA.read_bytes())

    def test_frozen_reference_exactly_matches_search_and_has_headroom(self):
        for world in ORACLE.WORLDS:
            with self.subTest(world=world["id"]):
                frozen = ORACLE._reference_rows(world)
                rebuilt = ORACLE._search_reference_rows(world)
                self.assertEqual(
                    [row["mutation"] for row in frozen],
                    [row["mutation"] for row in rebuilt],
                )
                anchors = ORACLE._anchors()[world["id"]]
                self.assertGreater(
                    anchors["reference"]["utility"],
                    anchors["baseline"]["utility"] + 0.10,
                )
                for field in ("trypsin_quality", "chymotrypsin_quality"):
                    self.assertGreater(
                        anchors["reference"][field], anchors["baseline"][field]
                    )

        baseline = ORACLE.evaluate(ORACLE._baseline_policy)
        reference = ORACLE.evaluate(ORACLE._reference_policy)
        for key in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score",
        ):
            self.assertEqual(baseline[key], 0.0)
            self.assertEqual(reference[key], 1.0)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertGreater(
            baseline["development_proxy_false_promotion_rate"], 0.25
        )
        self.assertGreater(
            baseline["heldout_proxy_false_promotion_rate"], 0.50
        )
        self.assertGreaterEqual(
            max(row["proxy_false_promotion_rate"] for row in baseline["per_world"]),
            0.75,
        )

    def test_truth_blind_twelve_assay_policy_has_transfer_headroom(self):
        result = ORACLE.evaluate(CALIBRATION.truth_blind_assay_policy)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["development_mean_assay_calls"], 12.0)
        self.assertEqual(result["heldout_mean_assay_calls"], 12.0)
        self.assertGreater(result["combined_score"], 0.35)
        self.assertGreater(result["heldout_policy_score"], 0.25)

    def test_public_problem_hides_identity_split_labels_and_measurements(self):
        hidden = {
            "id", "name", "split", "candidates", "stability_ddg",
            "trypsin_delta_g", "chymotrypsin_delta_g", "reference",
        }
        for world in ORACLE.WORLDS:
            problem = ORACLE._problem(world)
            rendered = json.dumps(problem, sort_keys=True)
            for key in hidden:
                self.assertNotIn('"%s"' % key, rendered)
            self.assertEqual(len(problem["candidate_residue_pairs"]), len(world["candidates"]))
            self.assertEqual(len(set(problem["candidate_residue_pairs"])), len(world["candidates"]))
            self.assertEqual(problem["batch_size"], 8)
            self.assertEqual(problem["assay_budget"], 12)

    def test_secure_baseline_is_zero_and_science_metrics_are_sealed(self):
        spec = find_task(
            "ProteinEngineering/ProteinStabilityDesign", include_uncertified=True
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_world_call_count"], 8)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        visible = search_visible_metrics(metrics)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )
        for key in (
            "development_mean_stability_ddg",
            "development_top_decile_hit_rate",
            "development_proxy_false_promotion_rate",
            "robustness_score",
            "heldout_policy_score",
            "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_heldout_invalidity_does_not_change_public_development_selection(self):
        heldout_sequences = {
            world["wild_type_sequence"] for world in ORACLE.HELDOUT_WORLDS
        }

        def policy(problem, assay):
            del assay
            if problem["wild_type_sequence"] in heldout_sequences:
                return {"sequences": []}
            return ORACLE._baseline_policy(problem, None)

        result = ORACLE.evaluate(policy)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["feasibility_rate"], 1.0)
        self.assertEqual(result["heldout_feasibility_rate"], 0.0)
        self.assertEqual(result["candidate_world_valid_rate"], 5.0 / 8.0)
        self.assertNotIn("error_message", result)

    def test_trusted_scoring_failure_is_not_classified_as_candidate_failure(self):
        original = ORACLE._batch_metrics
        try:
            def broken_scoring(*_args, **_kwargs):
                raise RuntimeError("trusted scoring deliberately broken")

            ORACLE._batch_metrics = broken_scoring
            with self.assertRaisesRegex(RuntimeError, "trusted scoring deliberately broken"):
                ORACLE._evaluate_world(
                    ORACLE._baseline_policy, ORACLE.DEVELOPMENT_WORLDS[0], 0
                )
        finally:
            ORACLE._batch_metrics = original

    def test_all_worlds_get_fresh_process_imports_and_tmpfs(self):
        result = self.evaluate_source(
            """
            from pathlib import Path
            CALLS = 0
            def design_stable_batch(problem, assay):
                global CALLS
                CALLS += 1
                marker = Path('/tmp/protein_seen')
                if CALLS != 1 or marker.exists():
                    return {'sequences': []}
                marker.write_text('seen')
                wild = problem['wild_type_sequence']
                i, j = problem['mutable_positions']
                output = []
                for pair in problem['candidate_residue_pairs'][:8]:
                    sequence = list(wild)
                    sequence[i], sequence[j] = pair
                    output.append(''.join(sequence))
                return {'sequences': output}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_world_call_count"], 8)
        self.assertEqual(result["candidate_world_valid_rate"], 1.0)

    def test_budget_repeat_and_invalid_assay_fail_closed_even_when_caught(self):
        bodies = (
            "for _ in range(13): assay(make(problem['candidate_residue_pairs'][0]))",
            "assay('X' * len(problem['wild_type_sequence']))",
        )
        template = """
            def design_stable_batch(problem, assay):
                def make(pair):
                    sequence = list(problem['wild_type_sequence'])
                    i, j = problem['mutable_positions']
                    sequence[i], sequence[j] = pair
                    return ''.join(sequence)
                try:
                    BODY
                except Exception:
                    pass
                return {'sequences': [make(pair) for pair in problem['candidate_residue_pairs'][:8]]}
        """
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(template.replace("BODY", body))
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0)
                expected = "budget_exceeded" if "range(13)" in body else "invalid_assay"
                self.assertTrue(all(
                    row["failure_kind"] == expected for row in result["per_world"]
                ))

    def test_malformed_duplicate_wrong_length_and_unmeasured_pair_fail_closed(self):
        bodies = (
            "return {}",
            "return {'sequences': []}",
            "return {'sequences': [make(problem['candidate_residue_pairs'][0])] * 8}",
            "return {'sequences': [make(pair) for pair in problem['candidate_residue_pairs'][:7]]}",
            "return {'sequences': ['X' * len(problem['wild_type_sequence'])] * 8}",
            "return {'sequences': tuple(make(pair) for pair in problem['candidate_residue_pairs'][:8]) + (1,)}",
        )
        template = """
            def design_stable_batch(problem, assay):
                def make(pair):
                    sequence = list(problem['wild_type_sequence'])
                    i, j = problem['mutable_positions']
                    sequence[i], sequence[j] = pair
                    return ''.join(sequence)
                BODY
        """
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(template.replace("BODY", body))
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
