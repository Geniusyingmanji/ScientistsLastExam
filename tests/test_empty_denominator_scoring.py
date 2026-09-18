"""An empty denominator is not measured, never a perfect score.

The maintainer's discovery-discrimination criterion D-b (docs/discovery_discrimination.md)
states the rule: a ratio axis whose denominator is empty is ``not_measured``, not ``1.0``.
Two evaluators violated it in the same direction - an empty truth set read as *perfect
recovery*, so a candidate that did no science collected mechanism credit from a world with
nothing to recover:

- ``Physics/RadialVelocityPlanets``: one development world (``s0_p0``) has zero injected
  planets; ``recovery = hits/len(truth) if truth else 1.0`` made an empty-claim candidate
  score exactly 0.25 combined (the single 1.0 averaged over four scored worlds), while the
  task card's own invariant says "a system with no injected planet has no recoverable
  mechanism, and every claim on it is a false discovery".
- ``Chemistry/SpinSystemInference``: ``coupling_score = hits/real if real else 1.0`` gave a
  candidate that claimed only zeros half of the mechanism axis from a world whose couplings
  are all true zeros.

These tests pin the fixed semantics at the scoring-function level, which needs no oracle
dependencies (astropy is absent on a plain dev host; nmrsim likewise). The end-to-end path
is exercised by the repository's own suite on hosts that have the packages.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RadialVelocityEmptyDenominatorTests(unittest.TestCase):
    def _evaluator(self):
        return _load(
            "benchmarks/Physics/RadialVelocityPlanets/verification/evaluator.py",
            "rv_evaluator_under_test")

    def test_a_world_with_no_injected_planet_has_no_mechanism(self):
        ev = self._evaluator()
        world = {"planets": [], "key": "t_zero"}
        row = ev._score_world(world, {"periods": []})
        self.assertIsNone(row["mechanism"])
        self.assertEqual(row["mechanism_denominator"], 0)
        # The card's invariant: every claim on it is a false discovery. An empty claim list
        # reports an undefined FDR (None), never a zero that would read as "clean".
        self.assertIsNone(row["false_discovery_rate"])

    def test_claiming_nothing_on_a_zero_planet_world_scores_no_combined_credit(self):
        """The regression this fix closes: 0.25 combined from one empty world.

        Before the fix, an empty-claim candidate averaged a 1.0 from s0_p0 into the
        mechanism mean. End-to-end the candidate needs astropy (the observation builder), so
        the pin here is the aggregation: rows with mechanism None never enter the mean.
        """
        ev = self._evaluator()
        rows = [
            {"key": "s0_p0", "valid": True, "abstained": False, "determined": True,
             "mechanism": None, "false_discovery_rate": None},
            {"key": "s1_p2", "valid": True, "abstained": False, "determined": True,
             "mechanism": 1.0, "false_discovery_rate": 0.0},
            {"key": "s2_p1", "valid": True, "abstained": False, "determined": True,
             "mechanism": 0.0, "false_discovery_rate": 0.0},
            {"key": "s3_p0", "valid": True, "abstained": False, "determined": True,
             "mechanism": 0.0, "false_discovery_rate": 0.0},
        ]
        scored = [r for r in rows
                  if not r.get("abstained") and r.get("mechanism") is not None]
        # The pre-fix code averaged all four (including the None-as-1.0), giving 0.25.
        self.assertEqual(len(scored), 3)
        mean = sum(r["mechanism"] for r in scored) / len(scored)
        self.assertAlmostEqual(mean, 1.0 / 3.0)

    def test_a_populated_world_scores_unchanged(self):
        ev = self._evaluator()
        world = {"planets": [{"period": 5.0}, {"period": 12.0}], "key": "t_two"}
        row = ev._score_world(world, {"periods": [5.0, 12.0]})
        self.assertEqual(row["mechanism"], 1.0)
        self.assertEqual(row["mechanism_denominator"], 2)
        self.assertEqual(row["false_discovery_rate"], 0.0)


class SpinSystemEmptyDenominatorTests(unittest.TestCase):
    def _evaluator(self):
        return _load(
            "benchmarks/Chemistry/SpinSystemInference/verification/evaluator.py",
            "spin_evaluator_under_test")

    def test_a_world_with_only_true_zero_couplings_has_an_unmeasured_coupling_axis(self):
        sp = self._evaluator()
        world = {"shifts": [100.0, 200.0], "couplings": [[0, 0], [0, 0]],
                 "degenerate": False}
        parsed = {"shifts": [100.0, 200.0], "couplings": [[0, 0], [0, 0]]}
        row = sp._mechanism(world, parsed)
        self.assertIsNone(row["coupling_recovery"])
        self.assertEqual(row["coupling_denominator"], 0)
        # The mechanism of that world is the shift axis alone: it still measures real
        # recovery, and half of it no longer comes from a denominator that does not exist.
        self.assertEqual(row["mechanism"], 1.0)

    def test_claiming_a_coupling_above_the_resolvable_floor_on_a_zero_world_is_a_false_discovery(self):
        sp = self._evaluator()
        J = sp.RESOLVABLE_J
        world = {"shifts": [100.0, 200.0], "couplings": [[0, 0], [0, 0]],
                 "degenerate": False}
        parsed = {"shifts": [100.0, 200.0], "couplings": [[0, 3 * J], [3 * J, 0]]}
        row = sp._mechanism(world, parsed)
        # The claim is counted where the card says it belongs: the false-discovery axis.
        self.assertEqual(row["false_discovery_rate"], 1.0)
        self.assertIsNone(row["coupling_recovery"])

    def test_a_world_with_resolvable_couplings_scores_unchanged(self):
        sp = self._evaluator()
        J = sp.RESOLVABLE_J
        world = {"shifts": [100.0, 200.0],
                 "couplings": [[0, 3 * J], [3 * J, 0]], "degenerate": False}
        parsed = {"shifts": [100.0, 200.0], "couplings": [[0, 3 * J], [3 * J, 0]]}
        row = sp._mechanism(world, parsed)
        self.assertEqual(row["coupling_recovery"], 1.0)
        self.assertEqual(row["coupling_denominator"], 1)
        self.assertAlmostEqual(row["mechanism"], 1.0)


if __name__ == "__main__":
    unittest.main()
