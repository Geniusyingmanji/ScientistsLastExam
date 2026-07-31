from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Engineering/QuartzCrystalMicrobalanceLab"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "qcm_raw_oracle")
BASELINE = _load(TASK / "solution.py", "qcm_raw_baseline")


def _independent_peak_and_q(frequencies, values):
    conductance = np.real(values)
    peak_index = int(np.argmax(conductance))
    peak_frequency = float(frequencies[peak_index])
    half = float(conductance[peak_index]) / 2.0

    def crossing(indices):
        for left, right in indices:
            y0 = float(conductance[left] - half)
            y1 = float(conductance[right] - half)
            if y0 == 0.0:
                return float(frequencies[left])
            if y0 * y1 <= 0.0:
                weight = -y0 / (y1 - y0)
                return float(
                    frequencies[left]
                    + weight * (frequencies[right] - frequencies[left])
                )
        raise AssertionError("half-power crossing not bracketed")

    lower = crossing((i, i + 1) for i in range(peak_index - 1, -1, -1))
    upper = crossing((i, i + 1) for i in range(peak_index, len(frequencies) - 1))
    return peak_frequency, peak_frequency / (upper - lower)


class QCMRawPipelineTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "Sensors/QuartzCrystalMicrobalanceLab", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_bvd_fit_agrees_with_independent_peak_bandwidth(self):
        for harmonic in ORACLE.HARMONICS:
            resonance = harmonic * ORACLE.NOMINAL_FUNDAMENTAL_HZ - 31.5
            quality = {1: 31000.0, 3: 26000.0, 5: 20500.0}[harmonic]
            frequencies = np.linspace(
                resonance - 7.0 * resonance / quality,
                resonance + 7.0 * resonance / quality,
                4001,
            )
            values = ORACLE._bvd_admittance(
                frequencies,
                resonance,
                quality,
                {1: 31e-15, 3: 9.5e-15, 5: 5.8e-15}[harmonic],
            )
            problem = {
                "motional_capacitance_initial_f_by_harmonic": {
                    "1": 30e-15, "3": 10e-15, "5": 6e-15,
                },
                "shunt_capacitance_f": ORACLE.SHUNT_CAPACITANCE_F,
            }
            fitted_frequency, fitted_q, rms = ORACLE._fit_bvd(
                frequencies, values, harmonic, problem
            )
            independent_frequency, independent_q = _independent_peak_and_q(
                frequencies, values
            )
            self.assertLess(abs(fitted_frequency - resonance), 1e-4)
            self.assertLess(abs(fitted_q / quality - 1.0), 2e-6)
            self.assertLess(abs(independent_frequency - resonance), 0.1)
            self.assertLess(abs(independent_q / quality - 1.0), 0.002)
            self.assertLess(rms, 1e-8)

    def test_complex_affine_calibration_recovers_chain(self):
        for spec_value in (
            ORACLE.DEVELOPMENT_SPECS[0], ORACLE.HELDOUT_SPECS[0]
        ):
            world = ORACLE._make_world(spec_value)
            problem = ORACLE._public_problem(world)
            start = ORACLE._fit_affine(problem["calibration_blocks"][0])
            end = ORACLE._fit_affine(problem["calibration_blocks"][1])
            self.assertLess(abs(start[0] - world["start_offset"]), 7.0)
            self.assertLess(abs(end[0] - world["end_offset"]), 7.0)
            self.assertLess(
                abs(start[1] - world["start_gain"]) / abs(world["start_gain"]),
                3.0e-4,
            )
            self.assertLess(
                abs(end[1] - world["end_gain"]) / abs(world["end_gain"]),
                2.5e-4,
            )

    def test_reference_pipeline_separates_supported_physical_and_instrument_worlds(self):
        result = ORACLE.evaluate(ORACLE._reference_agent)
        self.assertGreater(result["combined_score"], 0.98)
        self.assertGreater(result["heldout_policy_score"], 0.98)
        self.assertGreater(result["robustness_score"], 0.85)
        self.assertEqual(result["development_supported_claim_coverage"], 1.0)
        self.assertEqual(result["heldout_supported_claim_coverage"], 1.0)
        self.assertEqual(result["development_unsupported_refusal_rate"], 1.0)
        self.assertEqual(result["heldout_unsupported_refusal_rate"], 1.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_fault_diagnosis_accuracy"], 1.0)
        self.assertEqual(result["heldout_fault_diagnosis_accuracy"], 1.0)
        expected = {
            "rigid_linear": "supported",
            "rigid_missing": "supported",
            "viscoelastic": "physical_anomaly",
            "rate_change": "physical_anomaly",
            "iq_conjugated": "instrument_fault",
            "clipped": "instrument_fault",
        }
        for split, specs in (
            ("development", ORACLE.DEVELOPMENT_SPECS),
            ("heldout", ORACLE.HELDOUT_SPECS),
        ):
            for index, spec_value in enumerate(specs):
                world = ORACLE._make_world(spec_value)
                problem = ORACLE._public_problem(world)
                submission = ORACLE._reference_pipeline(problem)
                self.assertEqual(submission["diagnosis"], expected[world["kind"]])
                self.assertEqual(
                    submission["abstain"], world["kind"] not in ORACLE.SUPPORTED_KINDS
                )
                truth = ORACLE._evaluate_truth_world(spec_value, split, index)
                self.assertEqual(truth["joint_quality"], 1.0)

    def test_sealed_robustness_uses_rate_and_sauerbrey_shifts(self):
        world = ORACLE._make_world(ORACLE.DEVELOPMENT_SPECS[0])
        horizon = ORACLE.PREDICTION_TIME_S
        shifted = ORACLE._robust_mass_at(world, horizon)
        nominal = ORACLE._mass_at(world, horizon)
        rate_only = (
            ORACLE._mass_at(world, ORACLE.DEPOSITION_TIMES_S[-1])
            + world["rate"] * world["sealed_rate_scale"]
            * (horizon - ORACLE.DEPOSITION_TIMES_S[-1])
        )
        sensitivity_only = nominal / world["sealed_sauerbrey_scale"]
        self.assertNotAlmostEqual(shifted, nominal, places=8)
        self.assertNotAlmostEqual(shifted, rate_only, places=8)
        self.assertNotAlmostEqual(shifted, sensitivity_only, places=8)

    def test_baseline_is_valid_zero_and_science_metrics_are_sealed(self):
        direct = ORACLE.evaluate(BASELINE.analyze_qcm)
        self.assertEqual(direct["valid"], 1.0)
        self.assertEqual(direct["combined_score"], 0.0)
        self.assertEqual(direct["robustness_score"], 0.0)
        self.assertEqual(direct["development_supported_claim_coverage"], 0.0)
        visible = search_visible_metrics(direct)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate"}
        )
        self.assertNotIn("per_world", visible)
        self.assertNotIn("development_calibration_score", visible)
        self.assertNotIn("development_fault_diagnosis_accuracy", visible)

    def test_secure_baseline_matches_direct_evaluation(self):
        spec = find_task(
            "Sensors/QuartzCrystalMicrobalanceLab", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        direct = ORACLE.evaluate(BASELINE.analyze_qcm)
        direct["raw_score"] = direct["combined_score"]
        self.assertEqual(secure, direct)

    def test_fabricated_evidence_and_incomplete_sweep_map_fail_closed(self):
        for mode in ("evidence", "missing_map"):
            with self.subTest(mode=mode):
                result = self.evaluate_source(
                    """
                    def analyze_qcm(problem):
                        nominal = problem['nominal_frequency_hz_by_harmonic']
                        sweeps = problem['sweeps']
                        value = {
                            'calibration': {
                                'start_offset_counts': [0.0, 0.0],
                                'end_offset_counts': [0.0, 0.0],
                                'start_complex_gain_counts_per_siemens': [
                                    700000.0, 0.0],
                                'end_complex_gain_counts_per_siemens': [
                                    700000.0, 0.0]},
                            'resonance_frequency_hz_by_sweep': {
                                row['sweep_id']: nominal[str(row['harmonic'])]
                                for row in sweeps},
                            'quality_factor_by_sweep': {
                                row['sweep_id']: 20000.0 for row in sweeps},
                            'mass_loading_ug_cm2': 0.0,
                            'deposition_rate_ug_cm2_s': 0.0,
                            'predicted_mass_ug_cm2': 0.0,
                            'additional_deposition_time_s': 0.0,
                            'diagnosis': 'undetermined',
                            'confidence': 0.0,
                            'abstain': True,
                            'evidence_ids': [
                                block['calibration_id']
                                for block in problem['calibration_blocks']
                            ] + [row['sweep_id'] for row in sweeps]}
                        if %r == 'evidence':
                            value['evidence_ids'] = ['fabricated']
                        else:
                            value['resonance_frequency_hz_by_sweep'].pop(
                                next(iter(value['resonance_frequency_hz_by_sweep']))
                            )
                        return value
                    """ % mode
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0, result)
                self.assertTrue(all(
                    row["failure_kind"] == "invalid_submission"
                    for row in result["per_world"][:6]
                ))

    def test_nonfinite_and_extra_fields_fail_closed(self):
        result = self.evaluate_source(
            """
            def analyze_qcm(problem):
                sweeps = problem['sweeps']
                value = {
                    'calibration': {
                        'start_offset_counts':[0.0,0.0],
                        'end_offset_counts':[0.0,0.0],
                        'start_complex_gain_counts_per_siemens':[700000.0,0.0],
                        'end_complex_gain_counts_per_siemens':[700000.0,0.0]},
                    'resonance_frequency_hz_by_sweep': {
                        row['sweep_id']: float('nan') for row in sweeps},
                    'quality_factor_by_sweep': {
                        row['sweep_id']: 20000.0 for row in sweeps},
                    'mass_loading_ug_cm2':0.0,
                    'deposition_rate_ug_cm2_s':0.0,
                    'predicted_mass_ug_cm2':0.0,
                    'additional_deposition_time_s':0.0,
                    'diagnosis':'undetermined','confidence':0.0,
                    'abstain':True,
                    'evidence_ids':[row['sweep_id'] for row in sweeps],
                    'extra':'not allowed'}
                return value
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertLessEqual(result["combined_score"], 0.0, result)

    def test_candidate_worlds_use_fresh_processes(self):
        result = self.evaluate_source(
            """
            calls = 0
            def analyze_qcm(problem):
                global calls
                calls += 1
                if calls != 1:
                    raise RuntimeError('session leaked')
                sweeps = problem['sweeps']
                return {
                    'calibration': {
                        'start_offset_counts':[0.0,0.0],
                        'end_offset_counts':[0.0,0.0],
                        'start_complex_gain_counts_per_siemens':[700000.0,0.0],
                        'end_complex_gain_counts_per_siemens':[700000.0,0.0]},
                    'resonance_frequency_hz_by_sweep': {
                        row['sweep_id']: problem['nominal_frequency_hz_by_harmonic'][str(row['harmonic'])]
                        for row in sweeps},
                    'quality_factor_by_sweep': {
                        row['sweep_id']: 20000.0 for row in sweeps},
                    'mass_loading_ug_cm2':0.0,
                    'deposition_rate_ug_cm2_s':0.0,
                    'predicted_mass_ug_cm2':0.0,
                    'additional_deposition_time_s':0.0,
                    'diagnosis':'undetermined','confidence':0.0,
                    'abstain':True,
                    'evidence_ids':[
                        block['calibration_id'] for block in problem['calibration_blocks']
                    ] + [row['sweep_id'] for row in sweeps]}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_instance_call_count"], 10)
        self.assertEqual(result["candidate_instance_valid_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
