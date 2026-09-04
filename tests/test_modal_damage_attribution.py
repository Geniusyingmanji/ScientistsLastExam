"""Discovery-contract pins for ModalDamageAttribution.

The public score is mechanism, normalised so that declining every structure is exactly zero and so
is never claiming damage. A changed support is the unsupported case: declining it is correct,
declining everything is not; a healthy structure is determinable and "no damage" is its answer.

Two of these tests pin properties the construction checkpoints found the hard way: that the
measurement budget is not free, and that the temperature confound cannot be dodged by choosing
which days to measure on.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Engineering/ModalDamageAttribution"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModalDamageAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "modal_damage_oracle")
        cls.baseline = _load(TASK / "solution.py", "modal_damage_baseline")
        cls.reference = _load(TASK / "verification/reference_modal_ratios.py", "modal_damage_reference")

    def test_blanket_refusal_and_blanket_denial_both_score_zero(self):
        for submission in ({"abstain": True}, {"damaged": False, "abstain": False}):
            metrics = self.evaluator.evaluate(lambda _p, _m, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)

    def test_temperature_cancels_from_the_ratios_and_not_from_the_frequencies(self):
        """The one identity the task is built on. If it ever stops holding, the task is a different
        task: the confound would no longer be removable and only modelling it would work."""
        ev = self.evaluator
        world = ev._world({"kind": "healthy", "seed": 41100307, "budget": 9})
        warm = ev._frequencies(world["healthy"], 20.0)
        cold = ev._frequencies(world["healthy"], -10.0)
        np.testing.assert_allclose(cold / cold[0], warm / warm[0], rtol=1e-9)
        self.assertGreater(float(np.max(np.abs(cold / warm - 1.0))), 0.03)

    def test_a_support_change_is_not_explainable_by_any_single_element(self):
        """Every refusal world must be decidable: no member of the declared family reproduces it."""
        ev = self.evaluator
        for spec in ev.DEVELOPMENT_WORLDS + ev.HELDOUT_WORLDS:
            world = ev._world(spec)
            if world["kind"] not in ("support_change", "damaged"):
                continue
            healthy = ev._frequencies(world["healthy"], ev.REFERENCE_TEMPERATURE)
            healthy_ratios = healthy / healthy[0]
            actual = ev._frequencies(world, ev.REFERENCE_TEMPERATURE)
            target = (actual / actual[0]) / healthy_ratios - 1.0
            best = min(
                float(np.linalg.norm(
                    (lambda f: (f / f[0]) / healthy_ratios - 1.0)(
                        ev._frequencies({"masses": world["masses"],
                                         "springs": self._with_loss(world, element, severity)},
                                        ev.REFERENCE_TEMPERATURE)) - target)
                    / max(1e-12, np.linalg.norm(target)))
                for element in range(1, ev.MASS_COUNT)
                for severity in np.arange(0.05, 0.96, 0.05))
            if world["kind"] == "support_change":
                self.assertGreater(best, 0.30, "support change looks like single-element damage")
            else:
                self.assertLess(best, 0.20, "damaged world is not explained by its own family")

    @staticmethod
    def _with_loss(world, element, severity):
        springs = world["healthy"]["springs"].copy()
        springs[element] *= 1.0 - float(severity)
        return springs

    def test_the_measurement_budget_is_not_free(self):
        """One day must be materially worse than the whole budget, or the task is not budgeted."""
        source = (TASK / "verification/reference_modal_ratios.py").read_text(encoding="utf-8")
        one_day = source.replace("for day in order[:budget]:", "for day in order[:1]:")
        self.assertNotEqual(one_day, source)
        namespace = {}
        exec(compile(one_day, "one_day_reference", "exec"), namespace)  # noqa: S102
        full = self.evaluator.evaluate(self.reference.attribute_damage)["combined_score"]
        single = self.evaluator.evaluate(namespace["attribute_damage"])["combined_score"]
        self.assertLess(single, full - 0.2, "measuring once scores as well as measuring nine times")

    def test_the_extrapolation_baseline_is_valid_and_scores_zero(self):
        baseline = self.evaluator.evaluate(self.baseline.attribute_damage)
        reference = self.evaluator.evaluate(self.reference.attribute_damage)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_healthy_false_alarm_rate"], 1.0)
        self.assertGreater(reference["combined_score"], 0.5)
        self.assertLess(reference["combined_score"], 1.0)
        # The reference answers every determinable structure and refuses every support change, so
        # what it leaves on the table is precision, not coverage: its severity score is under a
        # half against a four per cent tolerance. If that ever reaches the ceiling the task has
        # stopped measuring the axis it was built around.
        self.assertEqual(reference["development_discovery_coverage"], 1.0)
        self.assertEqual(reference["development_correct_refusal_rate"], 1.0)
        self.assertLess(reference["development_severity_score"], 0.7)


if __name__ == "__main__":
    unittest.main()
