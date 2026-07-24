from __future__ import annotations

import importlib.util
import math
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
TASK = ROOT / "benchmarks/WavePropagation/SeismicWaveInversion"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    return _load(
        TASK / "verification/evaluator.py", "seismic_wave_v2_test_oracle"
    )


def _calibration():
    return _load(
        ROOT / "scripts/calibrate_seismic_wave_v2.py",
        "seismic_wave_v2_test_calibration",
    )


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.index = 0

    def __call__(self, *_args):
        acquire = _args[-2]
        for midpoints, offsets, frequency in self.oracle.REFERENCE_EXPERIMENTS:
            acquire(midpoints, offsets, frequency)
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(
            self.oracle.HELDOUT_SPECS
        )
        world = self.oracle._world(specs[self.index])
        self.index += 1
        return self.oracle._reference_submission(world)


class SeismicWaveV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()
        cls.calibration = _calibration()

    def test_baseline_reference_and_metric_sealing(self):
        oracle = self.oracle

        def baseline(midpoint_bounds, offset_bounds, *_args):
            acquire = _args[-2]
            acquire(
                np.full(4, 0.5 * sum(midpoint_bounds)),
                np.linspace(offset_bounds[0], min(600.0, offset_bounds[1]), 4),
                12.0,
            )
            return {
                "parameters": np.zeros(9),
                "confidence": 0.0,
                "abstain": True,
            }

        weak = oracle.evaluate(baseline)
        reference = oracle.evaluate(_ReferencePolicy(oracle))
        self.assertTrue(oracle.SEISMIC_WAVE_INVERSION_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(oracle.HELDOUT_SPECS), 5)
        self.assertEqual(len(oracle.PARAMETER_NAMES), 9)
        self.assertEqual(weak["valid"], 1.0)
        self.assertEqual(weak["combined_score"], 0.0)
        self.assertEqual(weak["robustness_score"], 0.0)
        self.assertEqual(reference["valid"], 1.0)
        for key in (
            "combined_score", "mechanism_score", "robustness_score",
            "heldout_policy_score", "heldout_mechanism_score",
            "heldout_robustness_score",
        ):
            self.assertAlmostEqual(reference[key], 1.0)
        self.assertEqual(
            set(search_visible_metrics(reference)),
            {"combined_score", "valid", "feasibility_rate", "raw_score"},
        )

    def test_independent_public_forward_matches_oracle(self):
        oracle = self.oracle
        calibration = self.calibration
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        midpoints = np.asarray((500.0, 3500.0, 5000.0, 8200.0))
        offsets = np.asarray((0.0, 400.0, 1100.0, 2500.0))
        production = oracle.synthesize_public(
            world["parameters"], midpoints, offsets, 17.0
        )
        independent = calibration._public_synthesize(
            world["parameters"], midpoints, offsets, 17.0
        )
        self.assertLess(
            float(np.max(np.abs(production - independent))), 2.0e-12
        )

        # At zero offset, the exact Snell solution reduces to the public vertical-time sum.
        local = oracle.local_thicknesses(world["parameters"], [5000.0])[0]
        for interface in (1, 2):
            observed = oracle._reflection_travel_time(
                world["parameters"][:interface], local[:interface], [0.0]
            )[0]
            expected = 2.0 * float(np.sum(
                local[:interface] / world["parameters"][:interface]
            ))
            self.assertAlmostEqual(observed, expected, places=13)

    def test_reference_design_is_full_rank_and_center_design_is_not(self):
        oracle = self.oracle
        for spec in list(oracle.DEVELOPMENT_SPECS[:4]) + list(
            oracle.HELDOUT_SPECS[:3]
        ):
            world = oracle._world(spec)
            reference_records = [
                {
                    "midpoints_m": midpoints,
                    "offsets_m": offsets,
                    "peak_frequency_hz": frequency,
                }
                for midpoints, offsets, frequency in oracle.REFERENCE_EXPERIMENTS
            ]
            reference = oracle._experiment_information(
                world, reference_records
            )
            narrow = oracle._experiment_information(world, [{
                "midpoints_m": np.full(4, 5000.0),
                "offsets_m": np.linspace(0.0, 600.0, 4),
                "peak_frequency_hz": 12.0,
            }])
            self.assertEqual(reference["jacobian_rank"], 9)
            self.assertIsNotNone(reference["condition_number"])
            self.assertLess(reference["condition_number"], 350.0)
            self.assertAlmostEqual(reference["information_score"], 1.0)
            self.assertEqual(narrow["jacobian_rank"], 5)
            self.assertEqual(narrow["information_score"], 0.0)

    def test_truth_blind_policy_fits_supported_and_refuses_unsupported(self):
        oracle = self.oracle
        calibration = self.calibration
        supported = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        laboratory = oracle._SeismicLaboratory(supported)
        result = calibration.truth_blind_discover(
            oracle.MIDPOINT_BOUNDS_M, oracle.OFFSET_BOUNDS_M,
            oracle.FREQUENCY_BOUNDS_HZ, oracle.PARAMETER_NAMES,
            oracle.PARAMETER_BOUNDS.copy(), laboratory.acquire,
            oracle.ACQUISITION_BUDGET_UNITS,
        )
        self.assertFalse(result["abstain"])
        self.assertEqual(laboratory.used, 12)
        self.assertGreater(
            oracle._mechanism_quality(
                result["parameters"], supported["parameters"]
            ),
            0.99,
        )

        for spec in (
            oracle.DEVELOPMENT_SPECS[-2], oracle.DEVELOPMENT_SPECS[-1]
        ):
            world = oracle._world(spec)
            laboratory = oracle._SeismicLaboratory(world)
            result = calibration.truth_blind_discover(
                oracle.MIDPOINT_BOUNDS_M, oracle.OFFSET_BOUNDS_M,
                oracle.FREQUENCY_BOUNDS_HZ, oracle.PARAMETER_NAMES,
                oracle.PARAMETER_BOUNDS.copy(), laboratory.acquire,
                oracle.ACQUISITION_BUDGET_UNITS,
            )
            self.assertTrue(result["abstain"])
            self.assertTrue(np.array_equal(result["parameters"], np.zeros(9)))

    def test_acquisition_is_deterministic_charged_and_resets(self):
        oracle = self.oracle
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        midpoints, offsets, frequency = oracle.REFERENCE_EXPERIMENTS[0]
        first = oracle._SeismicLaboratory(world)
        second = oracle._SeismicLaboratory(world)
        one = first.acquire(midpoints, offsets, frequency)
        repeated = second.acquire(midpoints, offsets, frequency)
        self.assertEqual(one["budget_cost"], 6)
        self.assertTrue(np.array_equal(one["traces"], repeated["traces"]))
        first.acquire(*oracle.REFERENCE_EXPERIMENTS[1])
        self.assertEqual(first.used, 12)
        with self.assertRaises(RuntimeError):
            first.acquire(midpoints, offsets, frequency)
        self.assertTrue(first.violated)

    def test_malformed_artifacts_fail_closed(self):
        oracle = self.oracle
        candidates = (
            None,
            {"parameters": np.zeros(5), "confidence": 0.0, "abstain": True},
            {"parameters": np.full(9, np.nan), "confidence": 0.5,
             "abstain": False},
            {"parameters": np.asarray((1800, 1700, 3000, 300, 0, 0,
                                        500, 0, 0)),
             "confidence": 0.5, "abstain": False},
            {"parameters": np.asarray((1800, 2400, 3300, 180, -160, -100,
                                        300, -220, -150)),
             "confidence": 0.5, "abstain": False},
            {"parameters": np.ones(9), "confidence": 0.0, "abstain": True},
        )
        for result in candidates:
            metrics = oracle.evaluate(
                lambda *_args, result=result: result
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)

    def test_quadratic_thickness_validation_checks_interior_vertex(self):
        oracle = self.oracle
        # This first-layer profile is above 120 m on the former five-point
        # validation grid but dips below it at its interior vertex q=0.775.
        parameters = np.asarray((
            1800.0, 2500.0, 3500.0,
            180.0, -155.0, 100.0,
            550.0, 0.0, 0.0,
        ))
        sampled = oracle.local_thicknesses(
            parameters, np.asarray((0.0, 2500.0, 5000.0, 7500.0, 10000.0))
        )[:, 0]
        self.assertGreaterEqual(float(np.min(sampled)), 120.0)
        with self.assertRaisesRegex(ValueError, "physical range"):
            oracle._validate_submission({
                "parameters": parameters,
                "confidence": 0.5,
                "abstain": False,
            })

        valid = parameters.copy()
        valid[3] = 181.0
        returned, confidence, abstain = oracle._validate_submission({
            "parameters": valid,
            "confidence": 0.5,
            "abstain": False,
        })
        self.assertTrue(np.array_equal(returned, valid))
        self.assertEqual(confidence, 0.5)
        self.assertFalse(abstain)

    def test_caught_overbudget_secure_evaluation_fails_closed(self):
        spec = find_task(
            "WavePropagation/SeismicWaveInversion", include_uncertified=True
        )
        source = textwrap.dedent("""
            import numpy as np

            def discover_layered_velocity(
                midpoint_bounds, offset_bounds, frequency_bounds,
                parameter_names, parameter_bounds, acquire, budget_units,
            ):
                del midpoint_bounds, offset_bounds, frequency_bounds
                del parameter_names, parameter_bounds, budget_units
                midpoints = np.full(8, 5000.0)
                offsets = np.linspace(0.0, 3000.0, 8)
                try:
                    acquire(midpoints, offsets, 12.0)
                    acquire(midpoints, offsets, 16.0)
                    acquire(midpoints, offsets, 20.0)
                except Exception:
                    pass
                return {
                    'parameters': np.zeros(9),
                    'confidence': 0.0,
                    'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=180)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(
            metrics["error_message"],
            "candidate invalid: invalid_acquisition_request",
        )
        self.assertEqual(metrics["candidate_world_call_count"], 11)

    def test_all_worlds_get_fresh_candidate_process_and_tmpfs(self):
        spec = find_task(
            "WavePropagation/SeismicWaveInversion", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def discover_layered_velocity(
                midpoint_bounds, offset_bounds, frequency_bounds,
                parameter_names, parameter_bounds, acquire, budget_units,
            ):
                global module_counter
                del offset_bounds, frequency_bounds, parameter_names
                del parameter_bounds, budget_units
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/seismic-wave-world-state')
                with open('/tmp/seismic-wave-world-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_seismic_wave_world_counter', 0)
                np._seismic_wave_world_counter = imported_counter + 1
                acquire(
                    np.linspace(midpoint_bounds[0], midpoint_bounds[1], 4),
                    np.linspace(0.0, 600.0, 4),
                    12.0,
                )
                confidence = (
                    0.1 * module_counter + 0.2 * int(tmp_seen)
                    + 0.3 * imported_counter
                )
                return {
                    'parameters': np.zeros(9),
                    'confidence': confidence,
                    'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=180)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        self.assertTrue(all(
            math.isclose(row["confidence"], 0.1)
            for row in metrics["per_world"]
        ))

    def test_legacy_driver_uses_v2_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable, str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(TASK / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT), capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(metrics_path.is_file())
            metrics = __import__("json").loads(
                metrics_path.read_text(encoding="utf-8")
            )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["candidate_world_call_count"], 11)


if __name__ == "__main__":
    unittest.main()
