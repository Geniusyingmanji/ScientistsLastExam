from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Electrochemistry/ElectrolyteConductivityDesign"
DATA = TASK / "verification/electrolyte_conductivity_v1.json"
DATA_SHA256 = "0c6899d6eb1a17b9565fb55963d1f46b52ba270cf10a5ec05177a01771593f29"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "electrolyte_test_oracle")
BUILDER = _load(
    ROOT / "scripts/build_electrolyte_conductivity_data.py",
    "electrolyte_builder_test",
)
CALIBRATION = _load(
    ROOT / "scripts/calibrate_electrolyte_conductivity_design.py",
    "electrolyte_calibration_test",
)


class ElectrolyteConductivityDesignTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "Electrochemistry/ElectrolyteConductivityDesign",
            include_uncertified=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_data_hash_provenance_lineage_and_contract(self):
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), DATA_SHA256)
        document = json.loads(DATA.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(
            document["builder_version"], "electrolyte-conductivity-design-v1"
        )
        source = document["source"]
        self.assertEqual(source["article"]["doi"], "10.1038/s41597-023-01936-3")
        self.assertEqual(source["article"]["license"], "CC-BY-4.0")
        self.assertEqual(source["dataset"]["doi"], "10.5281/zenodo.7244939")
        self.assertEqual(source["dataset"]["license"], "CC-BY-4.0")
        self.assertEqual(source["dataset"]["size_bytes"], BUILDER.SOURCE_SIZE)
        self.assertEqual(source["dataset"]["md5"], BUILDER.SOURCE_MD5)
        self.assertEqual(source["dataset"]["sha256"], BUILDER.SOURCE_SHA256)
        self.assertEqual(
            source["upstream_analysis_repository"]["commit"],
            "74ca52a0673cd33a313cfcfaad6bc271baa8ad0d",
        )
        contract = document["contract"]
        self.assertEqual(contract["source_complete_experiment_count"], 358)
        self.assertEqual(contract["source_formulation_count"], 85)
        self.assertEqual(contract["candidate_complete_experiment_count"], 141)
        self.assertEqual(contract["candidate_formulation_count"], 23)
        self.assertEqual(contract["batch_size"], 3)
        self.assertEqual(contract["assay_budget"], 8)
        self.assertEqual(len(document["source_formulations"]), 85)
        self.assertEqual(len(document["candidates"]), 23)

        source_ids = {
            experiment_id
            for row in document["source_formulations"]
            for experiment_id in row["experiment_ids"]
        }
        target_ids = set()
        for row in document["candidates"]:
            self.assertEqual(len(row["discovery_replicates"]), 2)
            self.assertEqual(len(row["confirmation_replicates"]), 2)
            for field in (
                "discovery_replicates", "confirmation_replicates", "audit_replicates"
            ):
                for repeat in row[field]:
                    target_ids.add(repeat["experiment_id"])
                    self.assertEqual(len(repeat["conductivity_s_cm"]), 10)
        self.assertEqual(len(source_ids), 358)
        self.assertEqual(len(target_ids), 141)
        self.assertFalse(source_ids & target_ids)

        source_compositions = {
            tuple(row["composition_g"][key] for key in BUILDER.COMPONENTS)
            for row in document["source_formulations"]
        }
        target_compositions = {
            tuple(row["composition_g"][key] for key in BUILDER.COMPONENTS)
            for row in document["candidates"]
        }
        self.assertFalse(source_compositions & target_compositions)

    def test_builder_reconstructs_exact_data_from_fixed_source_when_available(self):
        source = Path(
            "/tmp/frontier_science_electrolyte/Conductivtiy_experiment.csv"
        )
        if not source.is_file():
            self.skipTest("fixed upstream Zenodo CSV is not present")
        rebuilt = BUILDER.build(source)
        rendered = json.dumps(
            rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
        ) + "\n"
        self.assertEqual(rendered.encode("utf-8"), DATA.read_bytes())

    def test_physical_identity_and_independent_arrhenius_recalculation(self):
        document = ORACLE.DATA_DOCUMENT
        experiment_ids = set()
        for candidate in document["candidates"]:
            for field in (
                "discovery_replicates", "confirmation_replicates", "audit_replicates"
            ):
                for repeat in candidate[field]:
                    experiment_ids.add(repeat["experiment_id"])
                    conductivity = np.asarray(repeat["conductivity_s_cm"])
                    cell = np.asarray(repeat["cell_constant_cm_inv"])
                    resistance = np.asarray(repeat["resistance_ohm"])
                    np.testing.assert_allclose(
                        conductivity, cell / resistance, rtol=0.0, atol=2e-15
                    )
        self.assertEqual(len(experiment_ids), 141)
        checks = CALIBRATION._independent_arrhenius_checks(document)
        self.assertEqual(checks["experiment_count"], 141)
        self.assertEqual(checks["unique_experiment_count"], 141)
        self.assertLess(checks["maximum_absolute_r2_error"], 1e-12)
        self.assertLess(checks["maximum_absolute_mse_error"], 1e-12)
        self.assertLess(
            checks["maximum_absolute_activation_energy_error"], 1e-10
        )

    def test_worlds_references_headroom_and_confirmation_are_separate(self):
        self.assertEqual(len(ORACLE.DEVELOPMENT_WORLDS), 5)
        self.assertEqual(len(ORACLE.HELDOUT_WORLDS), 3)
        for world in ORACLE.WORLDS:
            with self.subTest(world=world["name"]):
                anchor = ORACLE._anchors()[world["name"]]
                self.assertGreater(
                    anchor["reference_utility"], anchor["baseline_utility"] + 0.04
                )
                self.assertGreater(
                    anchor["robust_reference_utility"],
                    anchor["baseline_lower_utility"] + 0.03,
                )
                self.assertNotEqual(
                    anchor["reference_ids"], anchor["robust_reference_ids"]
                )

        baseline = ORACLE.evaluate(ORACLE._baseline_policy)
        reference = ORACLE.evaluate(ORACLE._reference_policy)
        robust_reference = ORACLE.evaluate(ORACLE._robust_reference_policy)
        for key in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "confirmation_score",
            "heldout_confirmation_score",
        ):
            self.assertEqual(baseline[key], 0.0)
        self.assertEqual(reference["combined_score"], 1.0)
        self.assertEqual(reference["heldout_policy_score"], 1.0)
        self.assertEqual(robust_reference["robustness_score"], 1.0)
        self.assertEqual(robust_reference["heldout_robustness_score"], 1.0)
        # The optimization reference is not independently confirmed; this is the
        # central Goodhart/repeatability counterexample rather than an assertion bug.
        self.assertLess(reference["confirmation_score"], 0.10)
        self.assertLess(reference["heldout_confirmation_score"], 0.15)

    def test_truth_blind_policy_improves_visible_assays_but_not_confirmation(self):
        result = ORACLE.evaluate(CALIBRATION.truth_blind_assay_policy)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["development_mean_assay_calls"], 8.0)
        self.assertEqual(result["heldout_mean_assay_calls"], 8.0)
        self.assertEqual(result["development_assay_unique_rate"], 1.0)
        self.assertEqual(result["heldout_assay_unique_rate"], 1.0)
        self.assertGreater(result["combined_score"], 0.25)
        self.assertGreater(result["heldout_policy_score"], 0.25)
        self.assertLess(result["confirmation_score"], 0.10)
        self.assertEqual(result["heldout_confirmation_score"], 0.0)

    def test_public_problem_hides_identity_split_and_all_measurements(self):
        hidden = {
            "name", "split", "campaign", "experiment_id", "source_line_numbers",
            "discovery_replicates", "confirmation_replicates", "audit_replicates",
            "confirmation_quality", "eis_rmse", "arrhenius_r2",
        }
        for world in ORACLE.WORLDS:
            problem = ORACLE._problem(world)
            rendered = json.dumps(problem, sort_keys=True)
            for key in hidden:
                self.assertNotIn('"%s"' % key, rendered)
            self.assertEqual(len(problem["candidate_formulations"]), 23)
            self.assertEqual(len(problem["temperatures_c"]), 10)
            self.assertAlmostEqual(sum(problem["application_weights"]), 1.0)
            self.assertEqual(problem["batch_size"], 3)
            self.assertEqual(problem["assay_budget"], 8)

    def test_secure_baseline_is_zero_and_science_metrics_are_sealed(self):
        spec = find_task(
            "Electrochemistry/ElectrolyteConductivityDesign",
            include_uncertified=True,
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_world_call_count"], 8)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        direct = ORACLE.evaluate(ORACLE._baseline_policy)
        self.assertEqual(
            metrics["per_world"],
            json.loads(json.dumps(direct["per_world"], allow_nan=False)),
        )
        visible = search_visible_metrics(metrics)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )
        for key in (
            "robustness_score", "confirmation_score", "heldout_policy_score",
            "development_proxy_false_promotion_rate", "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_heldout_invalidity_does_not_change_development_selection(self):
        heldout_weights = {
            tuple(float(value) for value in world["weights"])
            for world in ORACLE.HELDOUT_WORLDS
        }

        def policy(problem, assay):
            if tuple(problem["application_weights"]) in heldout_weights:
                return {"formulation_ids": []}
            return ORACLE._baseline_policy(problem, assay)

        result = ORACLE.evaluate(policy)
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["heldout_feasibility_rate"], 0.0)
        self.assertEqual(result["candidate_world_valid_rate"], 5.0 / 8.0)
        self.assertNotIn("error_message", result)

    def test_all_worlds_get_fresh_process_imports_and_tmpfs(self):
        result = self.evaluate_source(
            """
            from pathlib import Path
            CALLS = 0
            def design_electrolyte_batch(problem, assay):
                global CALLS
                CALLS += 1
                marker = Path('/tmp/electrolyte_seen')
                if CALLS != 1 or marker.exists():
                    return {'formulation_ids': []}
                marker.write_text('seen')
                return {'formulation_ids': [
                    row['id'] for row in problem['candidate_formulations'][:3]
                ]}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_world_call_count"], 8)
        self.assertEqual(result["candidate_world_valid_rate"], 1.0)

    def test_budget_repeat_and_invalid_assay_fail_closed_even_when_caught(self):
        bodies = (
            "for _ in range(9): assay(problem['candidate_formulations'][0]['id'])",
            "assay('not-a-formulation')",
        )
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(
                    """
                    def design_electrolyte_batch(problem, assay):
                        try:
                            %s
                        except Exception:
                            pass
                        return {'formulation_ids': [
                            row['id'] for row in problem['candidate_formulations'][:3]
                        ]}
                    """ % body
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0)

    def test_malformed_submissions_fail_closed(self):
        sources = (
            "return {'formulation_ids': []}",
            "return {'formulation_ids': ['F00', 'F00', 'F01']}",
            "return {'formulation_ids': ['F00', 'F01', 'missing']}",
            "return ['F00', 'F01', 'F02']",
        )
        for body in sources:
            with self.subTest(body=body):
                result = self.evaluate_source(
                    """
                    def design_electrolyte_batch(problem, assay):
                        %s
                    """ % body
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
