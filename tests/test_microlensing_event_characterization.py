from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

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
CONSTANT = _load("test_microlensing_constant", TASK / "verification" / "shortcut_constant.py")
TEXTBOOK = _load("test_microlensing_textbook", TASK / "verification" / "shortcut_textbook.py")


class MicrolensingEventCharacterizationTests(unittest.TestCase):
    def test_reference_spends_full_budget_in_r_band(self):
        observer = EVALUATOR._Observer(EVALUATOR.DEVELOPMENT_WORLDS[0])
        REFERENCE.infer_microlensing(EVALUATOR.PUBLIC_PROBLEM, observer)
        self.assertEqual(observer.used, 24)
        self.assertTrue(all(band == "r" for _, band in observer.seen))

    def test_external_contract_keeps_solution_editable(self):
        readonly = (TASK / "frontier_eval/readonly_files.txt").read_text().splitlines()
        self.assertNotIn("solution.py", readonly)
        self.assertIn("verification", readonly)
        self.assertIn("frontier_eval", readonly)
        command = (TASK / "frontier_eval/eval_command.txt").read_text()
        self.assertEqual(command.strip(), "{python} frontier_eval/run_eval.py --candidate {candidate} --metrics-out {metrics}")

    def test_malformed_submission_matrix(self):
        changes = [{"model": "invalid"}, {"timescale_days": float("nan")},
                   {"timescale_days": 100}, {"timescale_days": -1},
                   {"amplitude": float("inf")}, {"amplitude": -1},
                   {"feature_time_days": float("nan")}, {"feature_time_days": 25},
                   {"confidence": float("nan")}, {"confidence": 2},
                   {"abstain": "yes"}, {"evidence_query_ids": []},
                   {"evidence_query_ids": ["invented"] * 6}]
        for update in changes:
            def bad(problem, observe):
                ids = [observe(float(t), "r")["query_id"] for t in problem["candidate_times"][:6]]
                return {"abstain": False, "confidence": 0.5, "evidence_query_ids": ids,
                        "model": "point_lens", "timescale_days": 8.0, "amplitude": 0.0,
                        "feature_time_days": 0.0} | update
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
        self.assertGreater(first["combined_score"], 0.85)
        self.assertEqual(first["development_correct_refusal_rate"], 1.0)

    def test_reference_recovers_variables_and_refuses_ambiguous_worlds(self):
        for worlds in (EVALUATOR.DEVELOPMENT_WORLDS, EVALUATOR.HELDOUT_WORLDS):
            for world in worlds:
                observer = EVALUATOR._Observer(world)
                claim = REFERENCE.infer_microlensing(EVALUATOR.PUBLIC_PROBLEM, observer)
                if world["kind"] == "variable":
                    self.assertFalse(claim["abstain"])
                    self.assertEqual(claim["model"], "variable_source")
                    self.assertLessEqual(abs(claim["timescale_days"] - world["period"]), 1.0)
                elif world["kind"] == "ambiguous":
                    self.assertTrue(claim["abstain"])

    def test_public_timescale_range_covers_supported_worlds(self):
        lower, upper = EVALUATOR.PUBLIC_PROBLEM["timescale_bounds_days"]
        for worlds in (EVALUATOR.DEVELOPMENT_WORLDS, EVALUATOR.HELDOUT_WORLDS):
            for world in worlds:
                if world["kind"] == "variable":
                    value = world["period"]
                elif world["kind"] in {"point", "binary"}:
                    value = EVALUATOR._point_duration(world["timescale"], world["u0"])
                else:
                    continue
                self.assertLessEqual(lower, value)
                self.assertLessEqual(value, upper)

    def test_sparse_cadence_loses_reference_capability(self):
        full = EVALUATOR.evaluate(REFERENCE.infer_microlensing)
        sparse = EVALUATOR.evaluate(
            lambda problem, observe: REFERENCE._infer(
                problem, observe, cadence_step=3))
        self.assertEqual(sparse["development_mean_budget_used"], 8.0)
        self.assertGreater(full["combined_score"] - sparse["combined_score"], 0.20)
        self.assertGreater(
            full["heldout_mechanism_score"], sparse["heldout_mechanism_score"])

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

    def test_one_invalid_world_zeroes_the_headline_and_sessions_reset(self):
        class PartiallyInvalid:
            def __init__(self):
                self.resets = 0

            def reset_session(self):
                self.resets += 1

            def __call__(self, problem, observe):
                ids = [observe(float(time), "r")["query_id"]
                       for time in problem["candidate_times"][:6]]
                if self.resets == 2:
                    return None
                return {"abstain": True, "confidence": 0.5,
                        "evidence_query_ids": ids}

        candidate = PartiallyInvalid()
        metrics = EVALUATOR.evaluate(candidate)
        self.assertEqual(candidate.resets, 24)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_world_families_are_present(self):
        self.assertEqual({w["kind"] for w in EVALUATOR.DEVELOPMENT_WORLDS},
                         {"point", "binary", "variable", "ambiguous"})

    def test_flux_ranges_overlap_across_families(self):
        intervals = []
        for kind in ("point", "binary", "variable", "ambiguous"):
            ranges = []
            for world in EVALUATOR.DEVELOPMENT_WORLDS:
                if world["kind"] == kind:
                    values = [EVALUATOR._flux(world, time, "r")
                              for time in EVALUATOR.TIMES[:-1]]
                    ranges.append(float(np.ptp(values)))
            intervals.append((min(ranges), max(ranges)))
        self.assertLessEqual(max(low for low, _ in intervals),
                             min(high for _, high in intervals))

    def test_declared_shortcuts_stay_below_reference_margin(self):
        reference = EVALUATOR.evaluate(REFERENCE.infer_microlensing)["combined_score"]
        for candidate in (CONSTANT.infer_microlensing, TEXTBOOK.infer_microlensing):
            metrics = EVALUATOR.evaluate(candidate)
            self.assertEqual(metrics["valid"], 1.0)
            self.assertLess(metrics["combined_score"], 0.8 * reference)


if __name__ == "__main__":
    unittest.main()
