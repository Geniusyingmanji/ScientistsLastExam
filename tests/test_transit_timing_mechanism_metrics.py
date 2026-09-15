import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from sle.metric_visibility import search_visible_metrics


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Physics/TransitTimingAttribution"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = load("ttv_metrics", TASK / "verification/evaluator.py")
reference = load("ttv_reference", TASK / "verification/reference_solver.py")
fixed = load("ttv_fixed", TASK / "verification/reference_no_active_design.py")
calibrate = load("ttv_calibrate", TASK / "verification/calibrate.py")
baseline = load("ttv_baseline", TASK / "solution.py")


def claim(kind="planet", ids=None):
    return {
        "mechanism": kind,
        "period": 5.2,
        "next_offset_days": 0.0,
        "confidence": 1.0,
        "evidence_query_ids": ids or ["a", "b"],
    }


class TransitMechanismMetricsTests(unittest.TestCase):
    def test_correct_wrong_and_abstained_claims_have_explicit_denominators(self):
        worlds = [
            {
                "kind": kind,
                "query_ids": ["a", "b"],
                "budget": 5,
                "period": 5.2,
                "amplitude": 0.006,
                "phase": 0.5,
                "secondary_amplitude": 0.003,
                "secondary_period": 2.1,
                "secondary_phase": 0.4,
                "clock_linear": 0.0002,
                "clock_quadratic": 0.000006,
                "forecast_transit": 75,
                "noise": 0.002,
            }
            for kind in (
                "planet",
                "activity",
                "clock",
                "planet",
                "activity",
                "unsupported_resonant",
            )
        ]
        claims = ["planet", "clock", None, "planet", None, None]
        iterator = iter(claims * 2)

        def candidate(*args):
            kind = next(iterator)
            return {"abstain": True} if kind is None else claim(kind)

        with patch.object(evaluator, "development_worlds", return_value=worlds), patch.object(
            evaluator, "sealed_worlds", return_value=worlds
        ), patch.object(evaluator, "_observation", return_value={}), patch.object(
            evaluator, "_design_score", return_value=0.0
        ):
            result = evaluator.evaluate(candidate)
        for split in ("development", "validation"):
            self.assertEqual(result[split + "_mechanism_correct_count"], 2)
            self.assertEqual(result[split + "_mechanism_total_count"], 5)
            self.assertEqual(result[split + "_mechanism_score"], 0.4)
            self.assertEqual(result[split + "_false_discovery_denominator"], 3)
        self.assertEqual(result["combined_score"], result["development_score"])

    def test_world_panels_are_deterministic_disjoint_and_variable(self):
        development = evaluator.development_worlds()
        heldout = evaluator.sealed_worlds()
        self.assertEqual(development, evaluator.development_worlds())
        self.assertEqual(heldout, evaluator.sealed_worlds())
        self.assertEqual((len(development), len(heldout)), (69, 60))
        self.assertEqual(len({w["panel_seed"] for w in development}), 3)
        self.assertEqual(len({w["panel_seed"] for w in heldout}), 3)
        self.assertTrue(
            {w["panel_seed"] for w in development}.isdisjoint(
                {w["panel_seed"] for w in heldout}
            )
        )
        self.assertEqual(
            {w["kind"] for w in development if w["kind"] not in evaluator.MECHANISMS},
            {"unsupported_resonant", "unsupported_chirp"},
        )
        self.assertGreater(len({len(w["times"]) for w in development}), 1)
        self.assertGreater(len({w["noise"] for w in development}), 50)
        self.assertGreater(len({w["maximum_followup"] for w in development}), 10)
        self.assertGreater(len({w["forecast_transit"] for w in development}), 10)
        self.assertEqual(len({w["seed"] for w in development + heldout}), 129)

    def test_every_observation_publishes_dynamic_followup_bounds_and_budget(self):
        for world in evaluator.development_worlds() + evaluator.sealed_worlds():
            observation = evaluator._observation(world)
            self.assertEqual(observation["budget_transits"], 5)
            self.assertEqual(
                observation["maximum_followup_transit_number"], world["maximum_followup"]
            )
            self.assertEqual(observation["forecast_transit_number"], world["forecast_transit"])
            self.assertGreater(
                observation["forecast_transit_number"],
                observation["maximum_followup_transit_number"],
            )

    def test_design_score_normalizes_feasible_distinct_measurements(self):
        world = {
            "kind": "clock",
            "times": list(map(float, range(10))),
            "maximum_followup": 14,
            "budget": 2,
            "query_ids": ["q10", "q10-repeat", "q14"],
            "query_numbers": [10, 10, 14],
        }
        repeated = {"abstain": False, "ids": ["q10", "q10-repeat"]}
        single = {"abstain": False, "ids": ["q10"]}
        spread = {"abstain": False, "ids": ["q10", "q14"]}
        optimum = {"abstain": False, "ids": ["q13", "q14"]}
        self.assertEqual(
            evaluator._design_score(world, repeated), evaluator._design_score(world, single)
        )
        self.assertGreater(
            evaluator._design_score(world, spread), evaluator._design_score(world, repeated)
        )
        world["query_ids"].append("q13")
        world["query_numbers"].append(13)
        self.assertEqual(evaluator._design_score(world, optimum), 1.0)

    def test_refusal_and_precision_change_headline(self):
        def row(supported, score, abstain=False, false=False):
            return {
                "supported": supported,
                "score": score,
                "abstain": abstain,
                "correct": supported and not abstain and not false,
                "fd": false,
                "design": 0.0,
            }

        supported = [row(True, 0.8)] * 3
        good = evaluator._aggregate(supported + [row(False, 1.0, abstain=True)])
        never_refuse = evaluator._aggregate(supported + [row(False, 0.0, false=True)])
        imprecise = evaluator._aggregate(
            supported + [row(False, 1.0, abstain=True), row(False, 0.0, false=True)]
        )
        self.assertAlmostEqual(good["combined_score"], 0.8)
        self.assertEqual(never_refuse["combined_score"], 0.0)
        raw = (3 * 0.8 + 1.0 - 2.0) / 3.0
        self.assertAlmostEqual(
            imprecise["combined_score"], raw * 0.5 * (3.0 / 4.0) ** 3
        )
        all_abstain = evaluator.evaluate(lambda *args: {"abstain": True})
        self.assertEqual(all_abstain["combined_score"], 0.0)
        self.assertEqual(all_abstain["valid"], 1.0)

    def test_constant_claims_and_confident_baseline_score_zero(self):
        baseline_result = evaluator.evaluate(baseline.attribute_ttv)
        self.assertEqual(baseline_result["valid"], 1.0)
        self.assertEqual(baseline_result["combined_score"], 0.0)
        for kind in evaluator.MECHANISMS:
            def candidate(observation, measure, budget, kind=kind):
                start = max(map(int, observation["transit_numbers"])) + 1
                ids = [measure(start + offset)["query_id"] for offset in (0, 1)]
                return claim(kind, ids)

            result = evaluator.evaluate(candidate)
            self.assertEqual(result["valid"], 1.0)
            self.assertEqual(result["combined_score"], 0.0)

    def test_sessions_reset_and_followup_noise_is_coordinate_seeded(self):
        class Counter:
            resets = 0
            calls = 0

            def reset_session(self):
                self.resets += 1
                self.calls = 0

            def __call__(self, *args):
                self.calls += 1
                if self.calls != 1:
                    raise RuntimeError("state leaked")
                return {"abstain": True}

        candidate = Counter()
        self.assertEqual(evaluator.evaluate(candidate)["valid"], 1.0)
        self.assertEqual(candidate.resets, 129)
        first, second = evaluator.development_worlds()[:2]
        number = max(len(first["times"]), len(second["times"]))
        first_noise = evaluator._experiment(first, number)["timing_offset_days"] - evaluator._signal(
            first, number
        )
        second_noise = evaluator._experiment(second, number)["timing_offset_days"] - evaluator._signal(
            second, number
        )
        self.assertNotEqual(first_noise, second_noise)

    def test_malformed_candidates_and_caught_budget_errors_fail_closed(self):
        def raises(*args):
            raise RuntimeError("broken candidate")

        def overspend(observation, measure, budget):
            start = max(map(int, observation["transit_numbers"])) + 1
            for _ in range(budget + 1):
                try:
                    measure(start)
                except RuntimeError:
                    pass
            return {"abstain": True}

        bad = [
            {},
            "wrong",
            None,
            [],
            {"abstain": "yes"},
            claim("wrong"),
            claim(ids=["fake", "invented"]),
            claim(ids=["a", "a"]),
            {**claim(), "period": float("nan")},
            {**claim(), "period": -1},
            {**claim(), "next_offset_days": float("inf")},
            {**claim(), "confidence": 2},
            {**claim(), "evidence_query_ids": [1, 2]},
        ]
        key_shape = set(evaluator.evaluate(lambda *args: {"abstain": True}))
        for candidate in [raises, overspend] + [
            lambda *args, value=value: value for value in bad
        ]:
            result = evaluator.evaluate(candidate)
            self.assertEqual(result["valid"], 0.0)
            self.assertEqual(result["combined_score"], 0.0)
            self.assertEqual(set(result), key_shape)

    def test_public_metrics_hide_sealed_diagnostics(self):
        result = evaluator.evaluate(reference.attribute_ttv)
        public = search_visible_metrics(result)
        self.assertEqual(public["combined_score"], result["development_score"])
        self.assertNotIn("robustness_score", public)
        self.assertFalse(any(key.startswith(("heldout_", "validation_")) for key in public))

    def test_current_reference_fixed_guard_and_ablations(self):
        reference_result = evaluator.evaluate(reference.attribute_ttv)
        repeat = evaluator.evaluate(reference.attribute_ttv)
        fixed_result = evaluator.evaluate(fixed.attribute_ttv)
        self.assertEqual(reference_result, repeat)
        self.assertEqual(reference_result["valid"], 1.0)
        self.assertEqual(fixed_result["valid"], 1.0)
        self.assertAlmostEqual(reference_result["combined_score"], 0.5948352385872625)
        self.assertAlmostEqual(fixed_result["combined_score"], 0.4321528299414905)
        self.assertLess(
            fixed_result["combined_score"], 0.8 * reference_result["combined_score"]
        )
        self.assertEqual(reference_result["development_mechanism_total_count"], 51)
        self.assertEqual(reference_result["heldout_mechanism_total_count"], 42)
        self.assertEqual(reference_result["development_correct_refusal_denominator"], 18)
        self.assertEqual(reference_result["heldout_correct_refusal_denominator"], 18)
        expected = {
            "three_followups": 0.23887283843685286,
            "no_activity_model": 0.25275618612364864,
            "constant_forecast": 0.526720866558509,
            "no_out_of_family_evidence": 0.05270056318895445,
        }
        for name, score in expected.items():
            result = evaluator.evaluate(calibrate.reference_ablation(name))
            self.assertEqual(result["valid"], 1.0)
            self.assertAlmostEqual(result["combined_score"], score)

    def test_fixed_scan_declares_full_development_only_grid(self):
        count = (
            len(calibrate.FRACTION_SCHEDULES)
            * len(calibrate.RMS_LIMITS)
            * len(calibrate.GAP_LIMITS)
            * len(calibrate.CORRELATION_LIMITS)
            * len(calibrate.ALTERNATIVE_GAP_LIMITS)
        )
        self.assertEqual(count, 3840)
        self.assertEqual(
            calibrate.FRACTION_SCHEDULES[1], (0.00, 0.20, 0.45, 0.70, 1.00)
        )


if __name__ == "__main__":
    unittest.main()
