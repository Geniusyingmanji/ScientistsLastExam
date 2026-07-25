from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    return _load_module(
        "demographic_sfs_v2_test_oracle",
        ROOT / "benchmarks/PopulationGenetics/DemographicSFS/verification/evaluator.py",
    )


def _calibration():
    return _load_module(
        "demographic_sfs_v2_test_calibration",
        ROOT / "scripts/calibrate_demographic_sfs_v2.py",
    )


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.call_index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(self.oracle.HELDOUT_SPECS)
        world = self.oracle._world(specs[self.call_index])
        self.call_index += 1
        return self.oracle._reference_submission(world)


class DemographicSFSV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()
        cls.calibration = _calibration()

    def test_constant_size_identity_and_independent_ode(self):
        oracle = self.oracle
        for n_sample in (3, 12, 32, 64):
            expected = oracle.expected_sfs_piecewise(n_sample, (1.0,), ())
            self.assertLess(
                float(np.max(np.abs(
                    expected - 1.0 / np.arange(1, n_sample)
                ))), 2.0e-14,
            )
        evaluator = oracle.expected_sfs_piecewise(
            32, (0.45, 2.2, 0.38, 1.0), (0.04, 0.12, 0.41)
        )
        independent = self.calibration._independent_ode_sfs(
            oracle, 32, (0.45, 2.2, 0.38, 1.0), (0.04, 0.12, 0.41)
        )
        self.assertLess(float(np.max(np.abs(evaluator - independent))), 2.0e-10)

    def test_baseline_reference_and_metric_sealing(self):
        oracle = self.oracle
        baseline = oracle.evaluate(lambda names, *_args: {
            "parameters": np.zeros(len(names)),
            "confidence": 0.0,
            "abstain": True,
        })
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["candidate_world_call_count"], 11)

        reference = oracle.evaluate(_ReferencePolicy(oracle))
        for key in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_prediction_score",
            "heldout_prediction_score", "development_confidence_score",
            "heldout_confidence_score",
        ):
            self.assertAlmostEqual(reference[key], 1.0)
        visible = search_visible_metrics(reference)
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_mechanism_score", "development_prediction_score",
            "heldout_prediction_score", "development_false_discovery_rate",
            "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_calibration_invariants_and_prediction_mechanism_gap(self):
        report = self.calibration.calibrate()
        self.assertTrue(report["execution_passed"])
        for relative_path, digest in report["task_source_sha256"].items():
            self.assertEqual(
                self.calibration._file_sha256(ROOT / relative_path), digest
            )
        classical = report["truth_blind_multisample_fit"]
        underinformative = report["underinformative_single_spectrum_fit"]
        equal_budget = report["equal_budget_repeated_small_sample_fit"]
        self.assertGreater(classical["combined_score"], 0.70)
        self.assertGreater(classical["heldout_policy_score"], 0.45)
        self.assertGreater(classical["development_prediction_score"], 0.95)
        self.assertGreater(classical["heldout_prediction_score"], 0.95)
        self.assertGreater(
            classical["heldout_prediction_score"]
            - classical["heldout_mechanism_score"], 0.40,
        )
        self.assertGreater(classical["combined_score"], underinformative["combined_score"])
        self.assertEqual(equal_budget["development_mean_budget_used"], 8.0)
        self.assertEqual(equal_budget["heldout_mean_budget_used"], 8.0)
        self.assertGreater(
            classical["combined_score"] - equal_budget["combined_score"], 0.15
        )
        self.assertGreater(
            classical["heldout_policy_score"]
            - equal_budget["heldout_policy_score"], 0.08
        )
        self.assertEqual(classical["development_unsupported_refusal_rate"], 1.0)
        self.assertEqual(classical["heldout_unsupported_refusal_rate"], 1.0)
        self.assertEqual(classical["development_false_discovery_rate"], 0.0)
        self.assertEqual(classical["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(
            classical["combined_score"],
            classical["development_mechanism_score"],
        )
        self.assertNotEqual(
            classical["combined_score"],
            classical["development_scientific_joint_score"],
        )
        for key in (
            "exact_parameter_or_refusal_checks", "identifiability_checks",
            "misspecified_resolvability_checks",
        ):
            self.assertTrue(all(row["passed"] for row in report[key]))
        self.assertTrue(all(
            row["indistinguishable_under_registered_threshold"]
            for row in report["finite_sfs_near_equivalence_limits"]
        ))

    def test_laboratory_is_deterministic_charged_and_independent(self):
        oracle = self.oracle
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        first, second = oracle._SFSLaboratory(world), oracle._SFSLaboratory(world)
        one = first.observe(20, 4)
        fresh = second.observe(20, 4)
        repeated = first.observe(20, 4)
        self.assertEqual(one["budget_cost"], 2)
        self.assertEqual(first.used, 4)
        self.assertTrue(np.array_equal(
            one["unfolded_sfs_counts"], fresh["unfolded_sfs_counts"]
        ))
        self.assertFalse(np.array_equal(
            one["unfolded_sfs_counts"], repeated["unfolded_sfs_counts"]
        ))

    def test_malformed_artifacts_fail_closed(self):
        oracle = self.oracle
        valid = {
            "parameters": np.zeros(len(oracle.PARAMETER_NAMES)),
            "confidence": 0.0,
            "abstain": True,
        }
        artifacts = [None]
        for update in (
            {"parameters": np.zeros(3)},
            {"parameters": np.full(4, np.nan)},
            {"confidence": np.inf},
            {"abstain": 1},
            {"parameters": np.asarray((0.4, 2.0, 0.4, 0.2)), "abstain": False},
        ):
            artifact = dict(valid)
            artifact.update(update)
            artifacts.append(artifact)
        for artifact in artifacts:
            metrics = oracle.evaluate(lambda *_args, artifact=artifact: artifact)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(
                metrics["error_message"],
                "candidate invalid: invalid_return_artifact",
            )

    def test_caught_budget_violation_fails_closed_in_secure_evaluation(self):
        spec = find_task(
            "PopulationGenetics/DemographicSFS", include_uncertified=True
        )
        source = textwrap.dedent("""
            import numpy as np
            def infer_demography(names, bounds, sizes, sequence, budget):
                del bounds, sizes, budget
                try:
                    sequence(64, 4)
                    sequence(64, 4)
                except Exception:
                    pass
                return {'parameters': np.zeros(len(names)),
                        'confidence': 0.0, 'abstain': True}
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(
            metrics["error_message"],
            "candidate invalid: invalid_experiment_request",
        )
        self.assertTrue(all(
            row["failure_kind"] == "invalid_experiment_request"
            for row in metrics["per_world"]
        ))

    def test_all_worlds_get_fresh_candidate_process_and_tmpfs(self):
        spec = find_task(
            "PopulationGenetics/DemographicSFS", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np
            module_counter = 0
            def infer_demography(names, bounds, sizes, sequence, budget):
                global module_counter
                del bounds, sizes, budget
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/demographic-world-state')
                with open('/tmp/demographic-world-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_demographic_world_counter', 0)
                np._demographic_world_counter = imported_counter + 1
                sequence(12, 1)
                confidence = (0.1 * module_counter + 0.2 * int(tmp_seen)
                              + 0.3 * imported_counter)
                return {'parameters': np.zeros(len(names)),
                        'confidence': confidence, 'abstain': True}
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        self.assertTrue(all(
            row["confidence"] == 0.1 for row in metrics["per_world"]
        ))
        self.assertTrue(all(
            row["experiment_calls"] == 1 for row in metrics["per_world"]
        ))

    def test_legacy_frontier_eval_driver_uses_v2_entrypoint(self):
        task = ROOT / "benchmarks/PopulationGenetics/DemographicSFS"
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [sys.executable, str(task / "frontier_eval/run_eval.py"),
                 "--candidate", str(task / "solution.py"),
                 "--metrics-out", str(metrics_path)],
                cwd=str(ROOT), check=False, capture_output=True, text=True,
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
