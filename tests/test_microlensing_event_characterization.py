from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Physics" / "MicrolensingEventCharacterization"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load("test_microlensing_evaluator", TASK / "verification" / "evaluator.py")
REFERENCE = _load("test_microlensing_reference", TASK / "verification" / "reference_solver.py")
BASELINE = _load("test_microlensing_baseline", TASK / "solution.py")


class MicrolensingEventCharacterizationTests(unittest.TestCase):
    def test_g_band_is_unused_and_reference_spends_only_r_budget(self):
        def run(collect_g, g_flux):
            calls = []
            def observe(time, band):
                calls.append((time, band))
                return {"query_id": "q%02d" % len(calls), "time": time, "band": band,
                        "flux": 1.0 + 0.5 * np.exp(-time * time / 20) if band == "r" else g_flux}
            def point_fit(times, flux):
                return (0.001, 8.0, np.ones(len(times)), np.array([1.0, 0.0]))
            with patch.object(REFERENCE, "_fit_point", side_effect=point_fit), \
                 patch.object(REFERENCE, "_sinusoid", return_value=(0.01, 15.0, 0.1)):
                result = REFERENCE._infer(EVALUATOR.PUBLIC_PROBLEM, observe, collect_g=collect_g)
            return result, calls
        r_only, r_calls = run(False, 0.0)
        legacy, old_calls = run(True, 1.0)
        corrupted, _ = run(True, float("nan"))
        self.assertEqual(legacy, corrupted)
        self.assertEqual(len(r_calls), 24)
        self.assertEqual(len(old_calls), 30)
        self.assertTrue(all(band == "r" for _, band in r_calls))
        for result in (r_only, legacy):
            result.pop("evidence_query_ids")
        self.assertEqual(r_only, legacy)

    def test_external_contract_keeps_solution_editable(self):
        readonly = (TASK / "frontier_eval/readonly_files.txt").read_text().splitlines()
        self.assertNotIn("solution.py", readonly)
        command = (TASK / "frontier_eval/eval_command.txt").read_text()
        self.assertEqual(command.strip(), "{python} frontier_eval/run_eval.py --candidate {candidate} --metrics-out {metrics}")

    def test_malformed_submission_matrix(self):
        changes = [{"model": "invalid"}, {"timescale_days": float("nan")},
                   {"timescale_days": 100}, {"timescale_days": -1},
                   {"amplitude": float("inf")}, {"amplitude": -1},
                   {"confidence": float("nan")}, {"confidence": 2},
                   {"abstain": "yes"}, {"evidence_query_ids": []},
                   {"evidence_query_ids": ["invented"] * 6}]
        for update in changes:
            def bad(problem, observe):
                ids = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
                return {"abstain": False, "confidence": 0.5, "evidence_query_ids": ids,
                        "model": "point_lens", "timescale_days": 8.0, "amplitude": 0.0} | update
            result = EVALUATOR.evaluate(bad)
            self.assertEqual(result["valid"], 0)
            self.assertEqual(result["combined_score"], 0)

    def test_baseline_is_valid_and_zero(self):
        metrics = EVALUATOR.evaluate(BASELINE.infer_microlensing)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_reference_is_key_deterministic(self):
        first = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
        second = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
        self.assertEqual(first, second)
        self.assertGreater(first["combined_score"], 0.45)
        self.assertEqual(first["development_correct_refusal_rate"], 1.0)

    def test_blanket_abstention_is_zero(self):
        def blanket(problem, observe):
            ids = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
            return {"abstain": True, "confidence": 0.5, "evidence_query_ids": ids}
        self.assertEqual(EVALUATOR.evaluate(blanket)["combined_score"], 0.0)

    def test_duplicate_query_fails_closed(self):
        def duplicate(problem, observe):
            observe(float(problem["candidate_times"][0]), "r")
            observe(float(problem["candidate_times"][0]), "r")
        metrics = EVALUATOR.evaluate(duplicate)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_world_families_are_present(self):
        self.assertEqual({w["kind"] for w in EVALUATOR.DEVELOPMENT_WORLDS},
                         {"point", "binary", "variable", "ambiguous"})


if __name__ == "__main__":
    unittest.main()
