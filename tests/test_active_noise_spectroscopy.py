"""Load-bearing invariants for QuantumControl/ActiveNoiseSpectroscopy."""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "ActiveNoiseSpectroscopy"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("active_noise_evaluator", TASK / "verification" / "evaluator.py")
REFERENCE = _load(
    "active_noise_reference", TASK / "verification" / "reference_spectroscopist.py"
)
BASELINE = _load("active_noise_baseline", TASK / "solution.py")


def _phase_only(problem, measure):
    result = measure("ramsey_3p5", 6000)
    shots = result["shots_per_quadrature"]
    phase_signal = 2.0 * result["y_plus_counts"] / shots - 1.0
    if phase_signal < 0.03:
        return {"abstain": True, "confidence": 0.7}
    return {
        "abstain": False,
        "noise_model": "single_telegraph",
        "switching_rate_per_us": 1.35,
        "noise_variance_rad2_per_us2": 0.251,
        "high_state_probability": 0.30,
        "confidence": 0.75,
    }


class PhysicsTests(unittest.TestCase):
    def test_filter_function_has_the_documented_zero_frequency_limit(self):
        ramsey = {"duration_us": 2.0, "pulse_times_us": ()}
        echo = {"duration_us": 2.0, "pulse_times_us": (1.0,)}
        self.assertAlmostEqual(EVALUATOR.filter_function(ramsey, 0.0).real, 2.0)
        self.assertAlmostEqual(EVALUATOR.filter_function(echo, 0.0).real, 0.0)

    def test_gaussian_piecewise_solution_matches_direct_covariance_quadrature(self):
        control = {"duration_us": 2.4, "pulse_times_us": (0.4, 1.3)}
        rate = 0.9
        variance = 0.23
        exact = EVALUATOR.gaussian_coherence(control, rate, variance).real
        count = 900
        dt = control["duration_us"] / count
        times = (np.arange(count) + 0.5) * dt
        signs = np.ones(count)
        for pulse in control["pulse_times_us"]:
            signs[times >= pulse] *= -1.0
        covariance = variance * np.exp(
            -rate * np.abs(times[:, None] - times[None, :])
        )
        chi = 0.5 * float(signs.dot(covariance).dot(signs)) * dt * dt
        self.assertAlmostEqual(exact, math.exp(-chi), delta=8e-4)

    def test_symmetric_telegraph_has_zero_phase_but_not_gaussian_coherence(self):
        control = {"duration_us": 3.5, "pulse_times_us": ()}
        telegraph = EVALUATOR.telegraph_coherence(control, 0.4, 0.45, 0.5)
        gaussian = EVALUATOR.gaussian_coherence(control, 0.4, 0.45)
        self.assertAlmostEqual(telegraph.imag, 0.0, places=12)
        self.assertAlmostEqual(gaussian.imag, 0.0, places=12)
        self.assertGreater(abs(telegraph.real - gaussian.real), 0.30)

    def test_asymmetric_telegraph_exposes_a_non_gaussian_phase(self):
        control = {"duration_us": 3.5, "pulse_times_us": ()}
        coherence = EVALUATOR.telegraph_coherence(control, 1.0, 0.22, 0.22)
        self.assertGreater(coherence.imag, 0.10)

    def test_family_separation_and_parameter_rank_are_independent_gates(self):
        for world in EVALUATOR.DEVELOPMENT_WORLDS:
            if world["kind"] == "single":
                rank, condition = EVALUATOR._parameter_jacobian_rank(world)
                self.assertEqual(rank, 3)
                self.assertTrue(math.isfinite(condition))
                self.assertGreaterEqual(EVALUATOR._family_separation_kl(world), 4.5)
            elif world["kind"] == "ambiguous_single":
                rank, condition = EVALUATOR._parameter_jacobian_rank(world)
                self.assertEqual(rank, 3)
                self.assertGreater(condition, 100.0)
                self.assertLess(EVALUATOR._family_separation_kl(world), 0.01)


class ShotProtocolTests(unittest.TestCase):
    def test_splitting_an_allocation_consumes_the_same_absolute_shot_stream(self):
        world = EVALUATOR.DEVELOPMENT_WORLDS[0]
        whole = EVALUATOR._ShotLab(world)
        whole_result = whole.measure("ramsey_2p0", 600)

        split = EVALUATOR._ShotLab(world)
        pieces = [split.measure("ramsey_2p0", 200) for _ in range(3)]
        self.assertEqual(
            whole_result["x_plus_counts"],
            sum(piece["x_plus_counts"] for piece in pieces),
        )
        self.assertEqual(
            whole_result["y_plus_counts"],
            sum(piece["y_plus_counts"] for piece in pieces),
        )
        self.assertEqual(whole.used, split.used)

    def test_caught_callback_protocol_error_still_invalidates_evaluation(self):
        def catches(problem, measure):
            del problem
            try:
                measure("not_a_control", 100)
            except ValueError:
                pass
            return {"abstain": True, "confidence": 0.5}

        result = EVALUATOR.evaluate(catches)
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)


class ScoringAndContractTests(unittest.TestCase):
    def test_baseline_is_valid_but_false_claim_penalty_clips_it_to_zero(self):
        result = EVALUATOR.evaluate(BASELINE.discover_noise)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["development_false_claim_count"], 4)
        self.assertEqual(result["development_claimed_mechanism_count"], 8)
        self.assertEqual(result["development_false_discovery_rate"], 0.5)
        self.assertEqual(
            result["development_unsupported_false_positive_rate"], 1.0
        )

    def test_always_abstain_is_exactly_zero_without_false_discoveries(self):
        result = EVALUATOR.evaluate(
            lambda problem, measure: {"abstain": True, "confidence": 0.7}
        )
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)
        self.assertEqual(result["development_unwarranted_refusal_rate"], 1.0)

    def test_phase_only_probe_misses_the_symmetric_supported_world(self):
        result = EVALUATOR.evaluate(_phase_only)
        self.assertLess(result["combined_score"], 0.5)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)
        self.assertEqual(result["development_unwarranted_refusal_rate"], 0.25)

    def test_truth_blind_reference_recovers_and_predicts_both_splits(self):
        result = EVALUATOR.evaluate(REFERENCE.discover_noise)
        self.assertGreater(result["combined_score"], 0.85)
        self.assertGreater(result["heldout_mechanism_score"], 0.80)
        self.assertGreater(result["development_heldout_prediction_score"], 0.80)
        self.assertGreater(result["heldout_prediction_score"], 0.80)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_correct_refusal_rate"], 1.0)
        self.assertEqual(result["development_unwarranted_refusal_rate"], 0.0)

    def test_malformed_submissions_fail_closed(self):
        cases = (
            lambda problem, measure: None,
            lambda problem, measure: {},
            lambda problem, measure: {"abstain": "yes"},
            lambda problem, measure: {
                "abstain": False,
                "noise_model": "single_telegraph",
                "switching_rate_per_us": float("nan"),
                "noise_variance_rad2_per_us2": 0.2,
                "high_state_probability": 0.2,
                "confidence": 0.5,
            },
            lambda problem, measure: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                result = EVALUATOR.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
