from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/EvidenceSynthesis/ProspectiveMetaAnalysis"
CALIBRATION = ROOT / "scripts/calibrate_prospective_meta_analysis.py"
ADMISSION = ROOT / "scripts/audit_candidate_wave5.py"


def load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("prospective_meta_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_calibration():
    spec = importlib.util.spec_from_file_location(
        "prospective_meta_calibration_test", CALIBRATION
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_admission():
    spec = importlib.util.spec_from_file_location(
        "prospective_meta_admission_test", ADMISSION
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProspectiveMetaAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = load_oracle()

    def test_worlds_are_procedural_and_records_are_lineage_linked(self):
        oracle = self.oracle
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(oracle.HELDOUT_SPECS), 4)
        hashes = set()
        for spec in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
            world = oracle._make_world(spec)
            self.assertEqual(len(world["eligible_trials"]), 14)
            expected = oracle._expected_screening(world)
            self.assertEqual(len(expected["included_registration_ids"]), 14)
            self.assertEqual(len(expected["primary_record_ids"]), 14)
            self.assertGreaterEqual(len(expected["duplicate_groups"]), 10)
            self.assertGreater(len(expected["selective_report_ids"]), 0)
            ids = tuple(sorted(record["record_id"] for record in world["records"]))
            self.assertNotIn(ids, hashes)
            hashes.add(ids)

    def test_registry_primary_is_invariant_to_publication_duplication_and_highlighting(self):
        oracle = self.oracle
        world = oracle._make_world(oracle.DEVELOPMENT_SPECS[0])
        problem = oracle._public_problem(world)
        fit = oracle._fit_meta_regression(problem["records"])
        publications = [
            copy.deepcopy(record) for record in problem["records"]
            if record["record_type"] == "publication"
        ]
        for record in publications:
            record["record_id"] += "-adversarial-copy"
            record["highlighted_outcome"] = "biomarker_response"
        augmented = list(problem["records"]) + publications
        repeated = oracle._fit_meta_regression(augmented)
        self.assertTrue(np.allclose(fit["beta"], repeated["beta"], atol=0.0))
        self.assertEqual(fit["tau"], repeated["tau"])

    def test_public_problem_and_confirmation_hide_world_identity_and_truth(self):
        oracle = self.oracle
        hidden = {
            "seed", "kind", "truth", "eligible", "true_mean",
            "study_deviation", "confirmation_noise_seed", "split",
        }
        for spec in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
            world = oracle._make_world(spec)
            problem = oracle._public_problem(world)
            rendered = json.dumps(problem, sort_keys=True)
            for key in hidden:
                self.assertNotIn('"%s"' % key, rendered)
            laboratory = oracle._ProspectiveLaboratory(world, problem)
            oracle.reference_policy(problem, laboratory.confirm)
            result = laboratory.result
            self.assertEqual(
                set(result),
                {
                    "registration_id", "site_id", "moderator_value",
                    "sample_size", "primary_endpoint", "effect",
                    "standard_error",
                },
            )

    def test_truth_blind_reference_has_headroom_and_refuses_nonlinear_worlds(self):
        oracle = self.oracle
        weak = oracle.evaluate(oracle.weak_baseline)
        reference = oracle.evaluate(oracle.reference_policy)
        truth = oracle.evaluate(oracle.oracle_reference_policy)
        self.assertEqual(weak["combined_score"], 0.0)
        self.assertEqual(weak["valid"], 1.0)
        self.assertGreater(reference["combined_score"], 0.75)
        self.assertLess(reference["combined_score"], 0.99)
        self.assertGreater(reference["heldout_policy_score"], 0.70)
        self.assertEqual(reference["development_unsupported_refusal_rate"], 1.0)
        self.assertEqual(reference["heldout_unsupported_refusal_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(truth["combined_score"], 1.0)
        self.assertEqual(truth["robustness_score"], 1.0)
        self.assertEqual(truth["heldout_policy_score"], 1.0)
        self.assertEqual(truth["heldout_robustness_score"], 1.0)

    def test_reference_screening_matches_lineage_and_selective_report_truth(self):
        oracle = self.oracle
        for spec in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
            world = oracle._make_world(spec)
            problem = oracle._public_problem(world)
            observed = oracle._reference_screening(problem)
            expected = oracle._expected_screening(world)
            self.assertEqual(
                set(observed["included_registration_ids"]),
                expected["included_registration_ids"],
            )
            self.assertEqual(
                set(observed["primary_record_ids"]), expected["primary_record_ids"]
            )
            self.assertEqual(
                oracle._pairs(observed["duplicate_groups"]),
                oracle._pairs(expected["duplicate_groups"]),
            )
            self.assertEqual(
                set(observed["selective_report_ids"]),
                expected["selective_report_ids"],
            )

    def test_confirmation_is_deterministic_charged_and_commit_bound(self):
        oracle = self.oracle
        world = oracle._make_world(oracle.DEVELOPMENT_SPECS[1])
        problem = oracle._public_problem(world)
        commit = oracle.reference_policy.__globals__["_reference_screening"](problem)
        pre = oracle._reference_pre_model(problem)
        site = problem["candidate_sites"][2]
        sample_size = 200
        predicted = pre["intercept"] + pre["moderator_slope"] * site["moderator_value"]
        payload = {
            "screening": commit,
            "preconfirmation": pre,
            "site_id": site["site_id"],
            "sample_size": sample_size,
            "forecast": {
                "predicted_effect": predicted,
                "prediction_interval": [predicted - 0.5, predicted + 0.5],
            },
        }
        first = oracle._ProspectiveLaboratory(world, problem)
        second = oracle._ProspectiveLaboratory(world, problem)
        one = first.confirm(payload)
        two = second.confirm(copy.deepcopy(payload))
        self.assertEqual(one, two)
        with self.assertRaises(ValueError):
            first.confirm(payload)

        altered = copy.deepcopy(payload)
        altered["sample_size"] += 20
        row = oracle._score_world(
            world,
            {"confirmation_commit": altered, "postconfirmation": pre},
            second,
        )
        self.assertFalse(row["valid"])
        self.assertIn("differs", row["reason"])

    def test_malformed_nonfinite_unknown_ids_and_inconsistent_forecast_fail_closed(self):
        oracle = self.oracle
        world = oracle._make_world(oracle.DEVELOPMENT_SPECS[0])
        problem = oracle._public_problem(world)
        laboratory = oracle._ProspectiveLaboratory(world, problem)
        screening = oracle._reference_screening(problem)
        pre = oracle._reference_pre_model(problem)
        common = {
            "screening": screening,
            "preconfirmation": pre,
            "site_id": "site_c",
            "sample_size": 200,
            "forecast": {
                "predicted_effect": pre["intercept"],
                "prediction_interval": [pre["intercept"] - 0.5, pre["intercept"] + 0.5],
            },
        }
        variants = []
        nonfinite = copy.deepcopy(common)
        nonfinite["preconfirmation"]["tau"] = np.nan
        variants.append(nonfinite)
        unknown = copy.deepcopy(common)
        unknown["screening"]["primary_record_ids"].append("REC-unknown")
        variants.append(unknown)
        inconsistent = copy.deepcopy(common)
        inconsistent["forecast"]["predicted_effect"] += 0.2
        variants.append(inconsistent)
        overbudget = copy.deepcopy(common)
        overbudget["site_id"] = "site_a"
        overbudget["sample_size"] = 300
        variants.append(overbudget)
        for value in variants:
            with self.assertRaises(ValueError):
                oracle._validate_commit(value, problem)
        self.assertFalse(laboratory.called)

    def test_non_abstaining_claim_without_commit_or_confirmation_fails_closed(self):
        oracle = self.oracle
        world = oracle._make_world(oracle.DEVELOPMENT_SPECS[0])
        problem = oracle._public_problem(world)
        laboratory = oracle._ProspectiveLaboratory(world, problem)
        model = {
            "intercept": 0.2,
            "moderator_slope": 0.0,
            "tau": 0.1,
            "confidence": 0.8,
            "abstain": False,
            "claim_beneficial": True,
        }
        row = oracle._score_world(
            world,
            {"confirmation_commit": None, "postconfirmation": model},
            laboratory,
        )
        self.assertFalse(row["valid"])
        self.assertIn("requires", row["reason"])

    def test_heldout_invalidity_does_not_change_development_selection(self):
        oracle = self.oracle
        heldout_record_ids = {
            record["record_id"]
            for spec in oracle.HELDOUT_SPECS
            for record in oracle._make_world(spec)["records"]
        }

        def policy(problem, confirm):
            if any(
                record["record_id"] in heldout_record_ids
                for record in problem["records"]
            ):
                return {"malformed": True}
            return oracle.reference_policy(problem, confirm)

        reference = oracle.evaluate(oracle.reference_policy)
        result = oracle.evaluate(policy)
        self.assertEqual(result["valid"], 1.0)
        self.assertAlmostEqual(
            result["combined_score"], reference["combined_score"], places=12
        )
        self.assertEqual(result["heldout_feasibility_rate"], 0.0)
        self.assertEqual(result["heldout_policy_score"], 0.0)

    def test_secure_baseline_equivalence_fresh_sessions_and_metric_sealing(self):
        oracle = self.oracle
        direct = oracle.evaluate(oracle.weak_baseline)
        spec = find_task(
            "EvidenceSynthesis/ProspectiveMetaAnalysis", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        for key in (
            "combined_score", "valid", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "feasibility_rate",
        ):
            self.assertEqual(secure[key], direct[key])
        shown = search_visible_metrics(secure)
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_evidence_integrity_score",
            "development_false_discovery_rate", "per_world",
        ):
            self.assertNotIn(key, shown)

        source = """
import os
import numpy as np
def synthesize_evidence(problem, confirm):
    seen = os.path.exists('/tmp/prospective-meta-state')
    with open('/tmp/prospective-meta-state', 'w') as handle:
        handle.write('x')
    count = getattr(np, '_prospective_meta_counter', 0)
    np._prospective_meta_counter = count + 1
    if seen or count:
        raise RuntimeError('state crossed corpus boundary')
    return {'confirmation_commit': None, 'postconfirmation': {
        'intercept': 0.0, 'moderator_slope': 0.0, 'tau': 0.0,
        'confidence': 1.0, 'abstain': True, 'claim_beneficial': False}}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            isolated = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(isolated["valid"], 1.0)
        self.assertEqual(isolated["combined_score"], 0.0)

    def test_duplicate_confirmation_call_fails_closed_even_when_caught(self):
        spec = find_task(
            "EvidenceSynthesis/ProspectiveMetaAnalysis", include_uncertified=True
        )
        source = """
def synthesize_evidence(problem, confirm):
    records = problem['records']
    registries = [r for r in records if r['record_type'] == 'registry_result']
    eligible = [r for r in registries if r['randomized'] and
                r['population'] == 'target_condition' and
                r['comparator'] == 'standard_care' and
                r['preregistered_primary'] == 'response_12w']
    groups = {}
    for r in records: groups.setdefault(r['registration_id'], []).append(r['record_id'])
    screen = {'included_registration_ids': [r['registration_id'] for r in eligible],
              'primary_record_ids': [r['record_id'] for r in eligible],
              'duplicate_groups': [v for v in groups.values() if len(v) > 1],
              'selective_report_ids': [r['record_id'] for r in records
                if r['record_type'] == 'publication' and
                r['highlighted_outcome'] != r['preregistered_primary']]}
    pre = {'intercept': 0.0, 'moderator_slope': 0.0, 'tau': 0.1,
           'confidence': 0.0, 'abstain': False, 'claim_beneficial': False}
    commit = {'screening': screen, 'preconfirmation': pre, 'site_id': 'site_c',
              'sample_size': 200, 'forecast': {'predicted_effect': 0.0,
              'prediction_interval': [-0.5, 0.5]}}
    confirm(commit)
    try: confirm(commit)
    except Exception: pass
    return {'confirmation_commit': commit, 'postconfirmation': pre}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_calibration_gate_executes(self):
        report = load_calibration().calibrate()
        self.assertTrue(report["execution_passed"], report)
        self.assertTrue(report["world_checks"]["passed"])
        self.assertTrue(report["invalid_artifact_checks"]["passed"])
        self.assertTrue(report["difficulty_gate"]["passed"])
        self.assertTrue(report["secure_baseline_exactly_matches_direct"])

    def test_wave5_admission_gate_executes(self):
        report = load_admission().audit()
        self.assertTrue(report["execution_passed"], report)
        self.assertEqual(report["summary"]["recommended_candidate_count"], 1)
        self.assertTrue(report["records"][0]["passed"])

    def test_frontier_eval_entrypoint_accepts_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(TASK / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()
