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

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    return _load_module(
        "climate_v2_test_oracle",
        ROOT / "benchmarks/EarthScience/EnergyBalanceModel/verification/evaluator.py",
    )


def _calibration():
    return _load_module(
        "climate_v2_test_calibration",
        ROOT / "scripts/calibrate_climate_v2.py",
    )


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.call_index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(
            self.oracle.HELDOUT_SPECS
        )
        world = self.oracle._world(specs[self.call_index])
        self.call_index += 1
        return self.oracle._reference_submission(world)


class EnergyBalanceModelV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()
        cls.calibration = _calibration()

    def test_baseline_reference_and_metric_sealing(self):
        oracle = self.oracle

        def always_abstain(parameter_names, *_args):
            return {
                "parameters": np.zeros(len(parameter_names)),
                "confidence": 0.0,
                "abstain": True,
            }

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["heldout_policy_score"], 0.0)
        self.assertEqual(baseline["heldout_robustness_score"], 0.0)
        self.assertEqual(baseline["candidate_world_call_count"], 11)
        self.assertEqual(baseline["candidate_world_valid_rate"], 1.0)

        reference = oracle.evaluate(_ReferencePolicy(oracle))
        for key in (
            "combined_score", "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_prediction_score",
            "heldout_prediction_score", "development_confidence_score",
            "heldout_confidence_score",
        ):
            self.assertAlmostEqual(reference[key], 1.0)
        self.assertTrue(all(row["valid"] for row in reference["per_world"]))

        visible = search_visible_metrics(reference)
        for key in (
            "robustness_score", "heldout_policy_score",
            "development_prediction_score", "heldout_prediction_score",
            "development_false_discovery_rate", "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_public_recurrence_matches_independent_rk4(self):
        oracle = self.oracle
        calibration = self.calibration
        parameters = np.asarray((1.37, 9.4, 126.0, 0.73, 1.08))
        forcing = np.concatenate((
            np.full(35, 5.0), np.full(20, -0.8),
            np.linspace(0.0, 7.5, 45), np.zeros(20),
        ))
        recurrence = oracle.simulate_public(parameters, forcing)
        independent = calibration._public_simulate(parameters, forcing)
        rk4 = calibration._rk4_public(parameters, forcing, substeps=100)
        for evaluator_values, independent_values, rk4_values in zip(
            recurrence, independent, rk4
        ):
            self.assertTrue(np.array_equal(
                evaluator_values, independent_values
            ))
            self.assertLess(
                float(np.max(np.abs(evaluator_values - rk4_values))), 1e-10
            )

    def test_laboratory_is_deterministic_charged_and_resets_state(self):
        oracle = self.oracle
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        forcing = np.concatenate((np.full(48, 4.0), np.zeros(32)))
        first = oracle._ClimateLaboratory(world)
        second = oracle._ClimateLaboratory(world)
        one = first.observe(forcing)
        fresh = second.observe(forcing)
        repeated = first.observe(forcing)
        self.assertEqual(one["budget_cost"], 4)
        self.assertEqual(first.used, oracle.EXPERIMENT_BUDGET_UNITS)
        self.assertTrue(np.array_equal(
            one["surface_temperature_anomaly_k"],
            fresh["surface_temperature_anomaly_k"],
        ))
        self.assertTrue(np.array_equal(
            one["toa_imbalance_w_m2"], fresh["toa_imbalance_w_m2"]
        ))
        self.assertFalse(np.array_equal(
            one["surface_temperature_anomaly_k"],
            repeated["surface_temperature_anomaly_k"],
        ))
        self.assertFalse(np.array_equal(
            one["toa_imbalance_w_m2"], repeated["toa_imbalance_w_m2"]
        ))
        # Each callback begins at the public zero anomaly state: its clean signal
        # is independent of previous calls and therefore agrees with a direct run.
        clean_surface, _deep, clean_imbalance = oracle._clean_response(
            world, forcing
        )
        direct_surface, _direct_deep, direct_imbalance = (
            oracle.simulate_public(world["parameters"], forcing)
        )
        self.assertTrue(np.array_equal(clean_surface, direct_surface))
        self.assertTrue(np.array_equal(clean_imbalance, direct_imbalance))

    def test_malformed_artifacts_fail_closed(self):
        oracle = self.oracle
        valid = {
            "parameters": np.zeros(len(oracle.PARAMETER_NAMES)),
            "confidence": 0.0,
            "abstain": True,
        }
        candidates = [None]
        for update in (
            {"parameters": np.zeros(4)},
            {"parameters": np.full(5, np.nan)},
            {"confidence": np.inf},
            {"abstain": 1},
            {"parameters": oracle.PARAMETER_BOUNDS[:, 1] + 0.1,
             "abstain": False},
            {"parameters": np.full(5, 1.0e6 + 1.0)},
        ):
            artifact = dict(valid)
            artifact.update(update)
            candidates.append(artifact)

        for artifact in candidates:
            metrics = oracle.evaluate(
                lambda *_args, artifact=artifact: artifact
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)
            self.assertEqual(
                metrics["error_message"],
                "candidate invalid: invalid_return_artifact",
            )
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_world"]
            ))
            self.assertTrue(all(
                row["failure_kind"] == "invalid_return_artifact"
                for row in metrics["per_world"]
            ))

    def test_calibration_invariants_and_experiment_design_gap(self):
        report = self.calibration.calibrate()
        self.assertTrue(report["execution_passed"])
        self.assertIsInstance(report["trusted_evidence"], bool)
        classical = report["truth_blind_long_multiscale_fit"]
        short = report["underinformative_short_fit"]
        self.assertGreater(classical["combined_score"], 0.70)
        self.assertGreater(classical["heldout_policy_score"], 0.80)
        self.assertLess(short["combined_score"], 0.10)
        self.assertLess(short["heldout_policy_score"], 0.10)
        self.assertGreater(
            classical["combined_score"] - short["combined_score"], 0.65
        )
        for key in (
            "exact_parameter_or_refusal_checks",
            "forcing_identifiability_checks",
            "misspecified_resolvability_checks",
            "noise_label_blind_checks",
        ):
            self.assertTrue(all(row["passed"] for row in report[key]))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_caught_budget_violation_fails_closed_in_secure_evaluation(self):
        spec = find_task(
            "ClimateScience/EnergyBalanceModel", include_uncertified=True
        )
        source = textwrap.dedent("""
            import numpy as np

            def identify_climate_response(
                parameter_names, parameter_bounds, experiment, budget_units
            ):
                del parameter_bounds, budget_units
                try:
                    experiment(np.zeros(160))
                    experiment(np.zeros(12))
                except Exception:
                    pass
                return {
                    'parameters': np.zeros(len(parameter_names)),
                    'confidence': 0.0,
                    'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertEqual(
            metrics["error_message"],
            "candidate invalid: invalid_experiment_request",
        )
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        self.assertTrue(all(
            row["failure_kind"] == "invalid_experiment_request"
            for row in metrics["per_world"]
        ))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_legacy_frontier_eval_driver_uses_v2_entrypoint(self):
        task = ROOT / "benchmarks/EarthScience/EnergyBalanceModel"
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(task / "frontier_eval/run_eval.py"),
                    "--candidate", str(task / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT), check=False, capture_output=True, text=True,
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_all_worlds_get_fresh_candidate_process_and_tmpfs(self):
        spec = find_task(
            "ClimateScience/EnergyBalanceModel", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def identify_climate_response(
                parameter_names, parameter_bounds, experiment, budget_units
            ):
                global module_counter
                del parameter_bounds, budget_units
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/climate-world-state')
                with open('/tmp/climate-world-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_climate_world_counter', 0)
                np._climate_world_counter = imported_counter + 1
                experiment(np.zeros(12))
                confidence = (
                    0.1 * module_counter + 0.2 * int(tmp_seen)
                    + 0.3 * imported_counter
                )
                return {
                    'parameters': np.zeros(len(parameter_names)),
                    'confidence': confidence,
                    'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        self.assertTrue(all(
            row["confidence"] == 0.1 for row in metrics["per_world"]
        ))
        self.assertTrue(all(
            row["experiment_calls"] == 1 for row in metrics["per_world"]
        ))


if __name__ == "__main__":
    unittest.main()
