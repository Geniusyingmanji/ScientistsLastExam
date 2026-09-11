from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Biology" / "FRAPBindingInference"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FRAPBindingInferenceTests(unittest.TestCase):
    def test_reference_is_deterministic_capable_and_baseline_is_zero(self):
        evaluator = _load("frap_evaluator", TASK / "verification" / "evaluator.py")
        sys.path.insert(0, str(TASK / "verification"))
        try:
            reference = _load("frap_reference", TASK / "verification" / "reference_solver.py")
        finally:
            sys.path.pop(0)
        first = evaluator.evaluate(reference.infer_frap_binding)
        second = evaluator.evaluate(reference.infer_frap_binding)
        self.assertEqual(first, second)
        self.assertEqual(first["valid"], 1.0)
        self.assertGreater(first["development_combined_score"], 0.90)
        self.assertGreater(first["heldout_combined_score"], 0.85)
        self.assertEqual(first["development_correct_refusal_rate"], 1.0)
        self.assertEqual(first["heldout_correct_refusal_rate"], 1.0)
        self.assertEqual(first["development_false_discovery_rate"], 0.0)
        self.assertEqual(first["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(first["development_discovery_coverage"], 1.0)
        self.assertEqual(first["heldout_discovery_coverage"], 1.0)

        baseline = _load("frap_baseline", TASK / "solution.py")
        result = evaluator.evaluate(baseline.infer_frap_binding)
        self.assertEqual(result["development_combined_score"], 0.0)
        self.assertEqual(result["heldout_combined_score"], 0.0)
        self.assertEqual(result["valid"], 1.0)

    def test_supported_recovery_has_physical_bounds_and_radius_scaling(self):
        evaluator = _load("frap_physics", TASK / "verification" / "evaluator.py")
        times = np.asarray(evaluator.TIMES)
        small = evaluator.supported_recovery(0.7, 0.82, 0.35, 0.12, 0.8, times)
        large = evaluator.supported_recovery(0.7, 0.82, 0.35, 0.12, 2.6, times)
        self.assertTrue(np.all(small >= 0.0))
        self.assertTrue(np.all(small <= 0.82))
        self.assertTrue(np.all(np.diff(small) >= -1e-12))
        self.assertTrue(np.all(np.diff(large) >= -1e-12))
        self.assertGreater(small[3], large[3])
        late = evaluator.supported_recovery(0.7, 0.82, 0.35, 0.12, 1.2, 1e5)
        self.assertAlmostEqual(float(late), 0.82, places=8)

    def test_malformed_and_over_budget_candidates_fail_closed(self):
        evaluator = _load("frap_invalid", TASK / "verification" / "evaluator.py")
        malformed = evaluator.evaluate(lambda problem, measure: {})
        self.assertEqual(malformed["valid"], 0.0)
        self.assertEqual(malformed["combined_score"], 0.0)

        def overspend(problem, measure):
            for _ in range(problem["measurement_budget_units"] + 1):
                try:
                    measure(problem["bleach_radii_um"][0], problem["sample_times_s"][0])
                except RuntimeError:
                    pass
            return {}

        result = evaluator.evaluate(overspend)
        self.assertEqual(result["valid"], 0.0)
        self.assertEqual(result["combined_score"], 0.0)

    def test_submission_fault_matrix_fails_closed(self):
        evaluator = _load("frap_fault_matrix", TASK / "verification" / "evaluator.py")

        def valid_claim(problem, measure):
            rows = [
                measure(problem["bleach_radii_um"][0], time)
                for time in problem["sample_times_s"][:8]
            ]
            return {
                "diagnosis": "supported",
                "diffusion_coefficient_um2_s": 0.5,
                "mobile_fraction": 0.8,
                "binding_on_rate_s": 0.2,
                "binding_off_rate_s": 0.1,
                "predicted_recovery": [0.5 for _ in problem["prediction_contexts"]],
                "confidence": 0.5,
                "abstain": False,
                "evidence_measurement_ids": [row["measurement_id"] for row in rows],
            }

        def mutated(change):
            def candidate(problem, measure):
                claim = valid_claim(problem, measure)
                change(claim)
                return claim
            return candidate

        bad_candidates = (
            lambda problem, measure: None,
            lambda problem, measure: "not a mapping",
            mutated(lambda claim: claim.pop("confidence")),
            mutated(lambda claim: claim.update(extra=1)),
            mutated(lambda claim: claim.update(diagnosis="unknown")),
            mutated(lambda claim: claim.update(abstain=True)),
            mutated(lambda claim: claim.update(diffusion_coefficient_um2_s=float("nan"))),
            mutated(lambda claim: claim.update(mobile_fraction=2.0)),
            mutated(lambda claim: claim.update(predicted_recovery=[0.5])),
            mutated(lambda claim: claim.update(confidence=-1.0)),
            mutated(lambda claim: claim.update(evidence_measurement_ids=["fabricated"] * 8)),
        )
        for candidate in bad_candidates:
            with self.subTest(candidate=candidate):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)

    def test_ablation_ladder_retains_material_headroom(self):
        evaluator = _load("frap_ablation_eval", TASK / "verification" / "evaluator.py")
        sys.path.insert(0, str(TASK / "verification"))
        try:
            reference = _load("frap_ablation_ref", TASK / "verification" / "reference_solver.py")
            ablations = _load("frap_ablations", TASK / "verification" / "ablation_solvers.py")
        finally:
            sys.path.pop(0)
        full = evaluator.evaluate(reference.infer_frap_binding)
        two_radii = evaluator.evaluate(ablations.two_radii_only)
        fixed_rates = evaluator.evaluate(ablations.fixed_binding_rates)
        never_refuse = evaluator.evaluate(ablations.never_refuse)
        for split in ("development", "heldout"):
            self.assertGreater(full[split]["combined_score"], two_radii[split]["combined_score"])
            self.assertGreater(two_radii[split]["combined_score"], fixed_rates[split]["combined_score"])
            self.assertGreater(fixed_rates[split]["combined_score"], never_refuse[split]["combined_score"])


if __name__ == "__main__":
    unittest.main()
