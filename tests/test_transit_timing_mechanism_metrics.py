import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "benchmarks/Physics/TransitTimingAttribution/verification/evaluator.py"
spec = importlib.util.spec_from_file_location("ttv_metrics", PATH)
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)
REF_PATH = ROOT / "benchmarks/Physics/TransitTimingAttribution/verification/reference_solver.py"
ref_spec = importlib.util.spec_from_file_location("ttv_reference", REF_PATH)
reference = importlib.util.module_from_spec(ref_spec)
ref_spec.loader.exec_module(reference)
CAL_PATH = ROOT / "benchmarks/Physics/TransitTimingAttribution/verification/calibrate.py"
cal_spec = importlib.util.spec_from_file_location("ttv_calibrate", CAL_PATH)
calibrate = importlib.util.module_from_spec(cal_spec)
cal_spec.loader.exec_module(calibrate)


def claim(kind="planet", ids=None):
    return {"mechanism": kind, "period": 5.2, "next_offset_days": 0.0,
            "confidence": 1.0, "evidence_query_ids": ids or ["a", "b"]}


class TransitMechanismMetricsTests(unittest.TestCase):
    def test_correct_wrong_and_abstained_claims_use_real_score(self):
        worlds = [{"kind": k, "query_ids": ["a", "b"], "budget": 4,
                   "period": 5.2, "amplitude": 0.006, "phase": 0.5, "noise": 0.002}
                  for k in ("planet", "activity", "clock", "planet", "activity", "unsupported")]
        claims = ["planet", "clock", None, "planet", None, None]
        iterator = iter(claims * 2)
        def candidate(*args):
            kind = next(iterator)
            return {"abstain": True} if kind is None else claim(kind)
        with patch.object(evaluator, "development_worlds", return_value=worlds), \
             patch.object(evaluator, "sealed_worlds", return_value=worlds), \
             patch.object(evaluator, "_observation", return_value={}):
            result = evaluator.evaluate(candidate)
        for split in ("development", "validation"):
            self.assertEqual(result[split + "_mechanism_correct_count"], 2)
            self.assertEqual(result[split + "_mechanism_total_count"], 5)
            self.assertEqual(result[split + "_mechanism_score"], 0.4)
            self.assertEqual(result[split + "_false_discovery_denominator"], 3)
        self.assertEqual(evaluator._score(worlds[1], evaluator._parse_submission(claim("clock"))), (0.0, True))

    def test_refusal_changes_headline_and_all_abstain_is_zero(self):
        def row(supported, score, abstain=False):
            return {"supported": supported, "score": score, "abstain": abstain,
                    "correct": supported and not abstain, "fd": not supported and not abstain}
        supported = [row(True, 0.8)] * 3
        good = evaluator._aggregate(supported + [row(False, 1, True)])
        bad = evaluator._aggregate(supported + [row(False, 0)])
        self.assertAlmostEqual(good["combined_score"], 0.8)
        self.assertEqual(bad["combined_score"], 0.0)
        result = evaluator.evaluate(lambda *a: {"abstain": True})
        self.assertEqual(result["combined_score"], 0)
        self.assertEqual(result["robustness_score"], 0)
        self.assertEqual(result["valid"], 1)

    def test_constant_claims_cannot_score(self):
        for kind in evaluator.MECHANISMS[:3]:
            def candidate(obs, measure, budget):
                ids = [measure(n)["query_id"] for n in (20, 30)]
                return claim(kind, ids)
            result = evaluator.evaluate(candidate)
            self.assertEqual(result["valid"], 1)
            self.assertEqual(result["combined_score"], 0)
            self.assertEqual(result["robustness_score"], 0)

    def test_worlds_are_deterministic_and_splits_differ(self):
        dev, val = evaluator.development_worlds(), evaluator.sealed_worlds()
        self.assertEqual(dev, evaluator.development_worlds())
        self.assertEqual(val, evaluator.sealed_worlds())
        self.assertNotEqual(len(dev), len(val))
        self.assertNotEqual([w["kind"] for w in dev], [w["kind"] for w in val][:len(dev)])
        self.assertNotEqual([w["kind"] for w in dev], sorted(w["kind"] for w in dev))
        self.assertEqual({w["kind"] for w in dev if w["kind"] not in evaluator.MECHANISMS},
                         {"unsupported_resonant", "unsupported_chirp"})
        self.assertEqual(len({w["seed"] for w in dev + val}), len(dev) + len(val))

    def test_followup_noise_is_world_and_coordinate_seeded(self):
        first = evaluator.development_worlds()[0]
        second = evaluator.development_worlds()[1]
        a = evaluator._experiment(first, 20)["timing_offset_days"] - evaluator._signal(first, 20)
        b = evaluator._experiment(second, 20)["timing_offset_days"] - evaluator._signal(second, 20)
        self.assertNotEqual(a, b)
        ordered = evaluator.development_worlds()[0]
        reordered = evaluator.development_worlds()[0]
        expected = evaluator._experiment(ordered, 20)["timing_offset_days"]
        evaluator._experiment(reordered, 21)
        actual = evaluator._experiment(reordered, 20)["timing_offset_days"]
        self.assertEqual(expected, actual)

    def test_sessions_reset_at_every_world_boundary(self):
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
        self.assertEqual(evaluator.evaluate(candidate)["valid"], 1)
        self.assertEqual(candidate.resets, len(evaluator.development_worlds()) + len(evaluator.sealed_worlds()))

    def test_malformed_candidates_and_caught_budget_errors_fail_closed(self):
        def raises(*args):
            raise RuntimeError("broken candidate")
        def overspend(obs, measure, budget):
            for _ in range(budget + 1):
                try:
                    measure(20)
                except RuntimeError:
                    pass
            return {"abstain": True}
        bad = [{}, "wrong", None, [], {"abstain": "yes"}, claim("wrong"),
               claim(ids=["fake", "invented"]), claim(ids=["a", "a"]),
               {**claim(), "period": float("nan")}, {**claim(), "period": -1},
               {**claim(), "next_offset_days": float("inf")}, {**claim(), "confidence": 2},
               {**claim(), "evidence_query_ids": [1, 2]}]
        good = evaluator.evaluate(lambda *a: {"abstain": True})
        for candidate in [raises, overspend] + [lambda *a, value=value: value for value in bad]:
            result = evaluator.evaluate(candidate)
            self.assertEqual(result["valid"], 0)
            self.assertEqual(result["combined_score"], 0)
            self.assertEqual(set(result), set(good))

    def test_reference_budget_and_shortcut_headroom(self):
        full = evaluator.evaluate(reference.attribute_ttv)
        half = evaluator.evaluate(lambda observation, measure, budget: reference._attribute_ttv(
            observation, measure, min(budget, 2), 1.0, 6.0, 0.8))
        shortcut = evaluator.evaluate(calibrate.fitted_policy(
            (13, 26, 43, 59), 1.2, 3.0, 0.8))
        self.assertGreater(full["combined_score"] - half["combined_score"], 0.30)
        self.assertGreater(full["robustness_score"] - half["robustness_score"], 0.15)
        self.assertGreater(full["combined_score"] - shortcut["combined_score"], 0.05)
        self.assertGreater(full["robustness_score"] - shortcut["robustness_score"], 0.10)
        self.assertEqual(full["development_correct_refusal_denominator"], 10)
        self.assertEqual(full["heldout_correct_refusal_denominator"], 10)


if __name__ == "__main__":
    unittest.main()
