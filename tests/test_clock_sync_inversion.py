"""Discovery-contract pins for ClockSyncInversion.

The public score is mechanism, normalised so that declining every world is exactly zero and so is
claiming intervals everywhere. A world whose exchanges no affine clocks and constant delays can
explain is the unsupported case: declining it is correct, declining everything is not; in a
supported world the answer is an interval for every clock offset, scored against the width that
unlimited data could not shrink.

Four of these tests pin what the construction found the hard way: that the exchanges obey the
published model, that every unsupported world is detectable and every supported one is not, that
the empty-queue rows are what catch the faults, and that an interval that misses costs a world.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/ComputerScience/ClockSyncInversion"

# identifiable widths summed over the clocks (microseconds) and kappa* of the unsupported worlds
WIDTH_SUMS = {"dev-01": 20.67, "dev-02": 88.43, "dev-03": 115.57, "dev-04": 123.44, "dev-05": 85.02,
              "dev-06": 52.25, "dev-07": 113.28, "held-01": 61.72, "held-02": 71.16, "held-03": 75.89,
              "held-04": 67.80}
KAPPA = {"dev-08": 19.1, "dev-09": 19.1, "dev-10": 23.2, "dev-11": 13.0, "dev-12": 17.1,
         "held-05": 15.9, "held-06": 22.5}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClockSyncInversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "clock_sync_oracle")
        cls.baseline = _load(TASK / "solution.py", "clock_sync_baseline")
        cls.reference = _load(TASK / "verification/reference_envelope_lp.py", "clock_sync_reference")
        cls.specs = cls.evaluator.DEVELOPMENT_WORLDS + cls.evaluator.HELDOUT_WORLDS
        cls.full = cls.evaluator.evaluate(cls.reference.identify)

    def _variant(self, **cfg):
        return lambda p, e, w: self.reference.identify(p, e, w, cfg)

    def test_blanket_refusal_in_both_forms_and_a_blind_claim_score_zero(self):
        for submission in ({"verdict": "no_model", "confidence": 1.0}, {"abstain": True}):
            metrics = self.evaluator.evaluate(lambda _p, _e, _w, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)
            self.assertEqual(metrics["development_correct_refusal_rate"], 1.0, submission)
            self.assertEqual(metrics["development_raw_mechanism"], 5.0 / 12.0, submission)

        def blind(problem, _e, _w):
            # a second either side of zero covers every offset and claims every world
            return {"verdict": "offsets", "confidence": 0.9,
                    "intervals": {str(j): [[-1.0, 1.0], [-1.0, 1.0]] for j in range(1, problem["nodes"])}}
        metrics = self.evaluator.evaluate(blind)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 0.0)

    def test_the_worlds_are_the_recorded_ones(self):
        ev = self.evaluator
        kinds = [ev._world(s)["kind"] for s in ev.DEVELOPMENT_WORLDS]
        self.assertEqual(kinds.count("supported"), 7)
        self.assertEqual([ev._world(s)["kind"] for s in ev.HELDOUT_WORLDS].count("supported"), 4)
        for spec in self.specs:
            world = ev._world(spec)
            if world["kind"] == "supported":
                self.assertAlmostEqual(float(world["widths"][1:].sum() * 1e6), WIDTH_SUMS[spec["name"]], places=2, msg=spec["name"])
            else:
                self.assertIsNone(world["widths"], spec["name"])

    def test_one_way_propagations_are_positive_and_within_the_public_model(self):
        for spec in self.specs:
            world = self.evaluator._world(spec)
            for direction, propagation in world["p"].items():
                self.assertGreaterEqual(propagation, 50e-6, (spec["name"], direction))
                self.assertLessEqual(propagation, 2e-3, (spec["name"], direction))
                self.assertGreater(world["lower"][direction], 0.0)

    def test_fdr_counts_claims_and_preserves_the_distinct_world_rate(self):
        ev = self.evaluator
        common = {"sharpness": 0.0, "mechanism_score": 0.0,
                  "confidence_calibration_score": 0.0, "probes_used": 0, "valid": True}
        records = [
            dict(common, kind="supported", abstained=False, false_discovery=True, correct_refusal=False),
            dict(common, kind="supported", abstained=False, false_discovery=False, correct_refusal=False),
            dict(common, kind="supported", abstained=True, false_discovery=False, correct_refusal=False),
            dict(common, kind="unsupported", abstained=True, false_discovery=False, correct_refusal=True),
        ]
        result = ev._split_summary(records)
        self.assertEqual(result["false_discovery_count"], 1)
        self.assertEqual(result["claim_count"], 2)
        self.assertEqual(result["false_discovery_rate"], 0.5)
        self.assertEqual(result["false_claim_world_rate"], 0.25)
        self.assertEqual(result["correct_refusal_count"], 1)
        self.assertEqual(result["unsupported_count"], 1)
        self.assertEqual(result["supported_claim_count"], 2)
        self.assertEqual(result["supported_count"], 3)
        self.assertEqual(result["discovery_coverage"], 2 / 3)

    def test_zero_claim_denominator_is_unavailable_to_discovery_reporting(self):
        import yaml
        from scripts.report_discovery_triple import extract

        metrics = self.evaluator.evaluate(lambda *_: {"abstain": True})
        contract = yaml.safe_load((TASK / "TASK_CARD.yaml").read_text())["metric_contract"]
        for split in ("development", "heldout"):
            self.assertEqual(metrics[split + "_claim_count"], 0)
            self.assertEqual(extract(metrics, split, contract)["fdr"]["status"], "zero_denominator")

    def test_every_unsupported_world_is_detectable_and_no_supported_one_is(self):
        """kappa* is the smallest relaxation, in pair-jitter units, that lets affine clocks and
        constant delays within the published bounds reproduce every true floor trajectory."""
        ev = self.evaluator
        for spec in self.specs:
            world = ev._world(spec)
            kappa = ev.detectability(world)
            if world["kind"] == "supported":
                self.assertLess(kappa, 1e-6, spec["name"])
            else:
                self.assertGreaterEqual(kappa, 12.0, spec["name"])
                self.assertAlmostEqual(kappa, KAPPA[spec["name"]], places=1, msg=spec["name"])

    def test_the_exchanges_follow_the_published_model(self):
        """Every one-way delay is at least its propagation, up to jitter, and at least the
        published floor of probes find the queue empty."""
        ev = self.evaluator
        spec = next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-02")
        world = ev._world(spec)
        exchange, _wait = ev._Bench(world, 7).oracle()
        for (i, j) in world["links"]:
            X = exchange(i, j, 400)
            t = (X[:, 0] - world["theta"][i]) / (1 + world["skew"][i])
            for (a, b), y in (((i, j), X[:, 1] - X[:, 0]), ((j, i), X[:, 3] - X[:, 2])):
                resid = y - (ev.offset(world, b, t) - ev.offset(world, a, t)) - world["p"][(a, b)]
                sp = math.hypot(world["sigma"][a], world["sigma"][b])
                self.assertGreater(resid.min(), -6.5 * sp, (a, b))
                self.assertGreaterEqual(np.mean(np.abs(resid) < 3 * sp), 0.8 * ev.PI_MIN, (a, b))
        for d in world["p"]:
            self.assertGreaterEqual(world["p"][d], world["lower"][d])
        for (i, j) in world["calibrated"]:
            self.assertLessEqual(abs(world["p"][(i, j)] - world["p"][(j, i)]), ev.ALPHA)

    def test_the_reference_and_the_baseline(self):
        ev, full = self.evaluator, self.full
        baseline = ev.evaluate(self.baseline.identify)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(baseline["development_false_discovery_rate"], 0.8)
        self.assertEqual(full["valid"], 1.0)
        self.assertGreater(full["combined_score"], 0.45)
        self.assertLess(full["combined_score"], 0.8)
        self.assertEqual(full["development_false_discovery_rate"], 0.0)
        self.assertEqual(full["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(full["development_correct_refusal_rate"], 1.0)
        self.assertEqual(full["heldout_correct_refusal_rate"], 1.0)
        self.assertEqual(full["development_discovery_coverage"], 1.0)
        # the intervals are well above the identifiable width, which is the axis being measured
        self.assertLess(full["development_interval_sharpness"], 0.8)
        for row in full["per_instance"]:
            self.assertTrue(row["valid"], row)
            self.assertLessEqual(row["probes_used"], ev.PROBE_BUDGET, row)

    def test_the_empty_queue_rows_are_what_catch_the_faults(self):
        """Without them the LP absorbs a rate step or a miscalibrated link into queueing."""
        metrics = self.evaluator.evaluate(self._variant(atoms=False))
        claimed = [r for r in metrics["per_instance"] if r["kind"] == "unsupported" and not r["abstained"]]
        self.assertGreaterEqual(len(claimed), 4)
        self.assertLess(metrics["combined_score"], self.full["combined_score"] - 0.3)
        # used only as a test, they still catch every fault but leave the intervals wider
        test_only = self.evaluator.evaluate(self._variant(detect_only=True))
        self.assertEqual(test_only["development_correct_refusal_rate"], 1.0)
        self.assertLess(test_only["combined_score"], self.full["combined_score"] - 0.1)

    def test_a_missed_interval_costs_a_world_wherever_it_is_made(self):
        ev = self.evaluator
        supported = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-01"))
        unsupported = ev._world(next(s for s in ev.DEVELOPMENT_WORLDS if s["name"] == "dev-10"))
        N, H = supported["N"], ev.HORIZON

        def around(world, shift, scale):
            out = {}
            for j in range(1, world["N"]):
                half = scale * (world["widths"][j] if world["widths"] is not None else 1e-6) / 2
                out[j] = [(float(ev.offset(world, j, e)) + shift - half, float(ev.offset(world, j, e)) + shift + half)
                          for e in (0.0, H)]
            return out
        exact = ev._metrics(supported, around(supported, 0.0, 1.0))
        self.assertTrue(exact["covered"])
        self.assertAlmostEqual(exact["mechanism_score"], 1.0)
        wide = ev._metrics(supported, around(supported, 0.0, 4.0))
        self.assertAlmostEqual(wide["mechanism_score"], 0.25)
        missed = ev._metrics(supported, around(supported, 1e-3, 1.0))
        self.assertTrue(missed["false_discovery"])
        self.assertEqual(missed["mechanism_score"], -1.0)
        self.assertEqual(ev._metrics(supported, None)["mechanism_score"], 0.0)
        claimed = ev._metrics(unsupported, around(unsupported, 0.0, 1.0))
        self.assertTrue(claimed["false_discovery"])
        self.assertEqual(claimed["mechanism_score"], 0.0)
        self.assertEqual(ev._metrics(unsupported, None)["mechanism_score"], 1.0)
        self.assertEqual(N, 5)

    def test_two_evaluations_are_identical(self):
        second = self.evaluator.evaluate(self.reference.identify)
        self.assertEqual(json.dumps(self.full, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_malformed_candidates_score_zero_without_raising(self):
        ev = self.evaluator

        def raises(_p, _e, _w):
            raise RuntimeError("boom")

        def overspend(problem, exchange, _w):
            while True:
                exchange(0, problem["links"][0][1] if problem["links"][0][0] == 0 else problem["links"][0][0], 5000)

        def overspend_caught(problem, exchange, wait):
            try:
                overspend(problem, exchange, wait)
            except RuntimeError:
                pass
            return {"verdict": "no_model"}

        def overwait(problem, _e, wait):
            wait(problem["horizon_s"] + 1.0)

        def overwait_caught(problem, exchange, wait):
            try:
                overwait(problem, exchange, wait)
            except RuntimeError:
                pass
            return {"verdict": "no_model"}

        def patched_budget(problem, exchange, wait):
            exchange.budget = 10 ** 9  # a function attribute: the ledger is not reachable
            return overspend(problem, exchange, wait)

        def claim(**override):
            def f(problem, _e, _w):
                intervals = {str(j): [[-1.0, 1.0], [-1.0, 1.0]] for j in range(1, problem["nodes"])}
                answer = {"verdict": "offsets", "intervals": intervals, "confidence": 0.5}
                for key, value in override.items():
                    if key == "patch":
                        value(intervals, problem)
                    else:
                        answer[key] = value
                return answer
            return f

        def link(problem):
            return problem["links"][0]

        shapes = {
            "raises": raises,
            "none": lambda _p, _e, _w: None,
            "empty": lambda _p, _e, _w: {},
            "string": lambda _p, _e, _w: "offsets",
            "verdict_bad": lambda _p, _e, _w: {"verdict": "maybe"},
            "intervals_missing": lambda _p, _e, _w: {"verdict": "offsets"},
            "intervals_list": claim(intervals=[[-1.0, 1.0]]),
            "node_missing": claim(patch=lambda iv, p: iv.pop("1")),
            "node_zero": claim(patch=lambda iv, p: iv.__setitem__("0", [[0.0, 0.0], [0.0, 0.0]])),
            "node_out_of_range": claim(patch=lambda iv, p: iv.__setitem__(str(p["nodes"]), [[0.0, 0.0], [0.0, 0.0]])),
            "node_twice": claim(patch=lambda iv, p: iv.__setitem__(1, [[-1.0, 1.0], [-1.0, 1.0]])),
            "one_epoch": claim(patch=lambda iv, p: iv.__setitem__("1", [[-1.0, 1.0]])),
            "interval_reversed": claim(patch=lambda iv, p: iv.__setitem__("1", [[1.0, -1.0], [-1.0, 1.0]])),
            "interval_nan": claim(patch=lambda iv, p: iv.__setitem__("1", [[float("nan"), 1.0], [-1.0, 1.0]])),
            "interval_inf": claim(patch=lambda iv, p: iv.__setitem__("1", [[-float("inf"), 1.0], [-1.0, 1.0]])),
            "interval_str": claim(patch=lambda iv, p: iv.__setitem__("1", [["-1", "1"], [-1.0, 1.0]])),
            "interval_bool": claim(patch=lambda iv, p: iv.__setitem__("1", [[False, True], [-1.0, 1.0]])),
            "interval_three": claim(patch=lambda iv, p: iv.__setitem__("1", [[-1.0, 0.0, 1.0], [-1.0, 1.0]])),
            "confidence_nan": claim(confidence=float("nan")),
            "confidence_str": claim(confidence="high"),
            "overspend": overspend,
            "overspend_caught": overspend_caught,
            "overwait": overwait,
            "overwait_caught": overwait_caught,
            "patched_budget": patched_budget,
            "no_such_link": lambda p, e, _w: e(0, 0, 1),
            "node_float": lambda p, e, _w: e(float(link(p)[0]), link(p)[1], 1),
            "node_bool": lambda p, e, _w: e(False, True, 1),
            "probes_zero": lambda p, e, _w: e(link(p)[0], link(p)[1], 0),
            "probes_float": lambda p, e, _w: e(link(p)[0], link(p)[1], 2.0),
            "wait_negative": lambda _p, _e, w: w(-1.0),
            "wait_nan": lambda _p, _e, w: w(float("nan")),
            "wait_str": lambda _p, _e, w: w("10"),
        }
        self.assertGreaterEqual(len(shapes), 12)
        for name, candidate in shapes.items():
            metrics = ev.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0, name)
            self.assertEqual(metrics["combined_score"], 0.0, name)
            self.assertEqual(metrics["feasibility_rate"], 0.0, name)

    def test_probes_are_charged_and_the_budget_and_the_horizon_fail_closed(self):
        ev = self.evaluator
        world = ev._world(self.specs[0])
        i, j = world["links"][0]
        bench = ev._Bench(world, 3)
        exchange, wait = bench.oracle()
        X = exchange(i, j, 10)
        self.assertEqual(X.shape, (10, 4))
        self.assertEqual(bench.used, 10)
        self.assertAlmostEqual(bench.now, 10 * ev.SPACING)
        exchange(j, i, 10)                 # either end may start an exchange
        wait(100.0)
        self.assertAlmostEqual(bench.now, 20 * ev.SPACING + 100.0)
        with self.assertRaises(RuntimeError):
            exchange(i, j, ev.PROBE_BUDGET)
        self.assertTrue(bench.violated)
        self.assertEqual(bench.used, 20)
        late = ev._Bench(world, 3)
        exchange, wait = late.oracle()
        wait(ev.HORIZON - 1.0)
        with self.assertRaises(RuntimeError):
            exchange(i, j, 10)             # the tenth probe would start past the horizon
        self.assertTrue(late.violated)

    def test_hidden_axes_stay_out_of_the_search_view(self):
        from sle.metric_visibility import SEARCH_VISIBLE_KEYS

        for key in SEARCH_VISIBLE_KEYS:
            self.assertNotIn("heldout", key)
            self.assertNotIn("mechanism", key)
            self.assertNotIn("sharpness", key)


if __name__ == "__main__":
    unittest.main()
