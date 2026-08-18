"""A saturation verdict retires a task, so it has to say what it is a verdict about.

The only score a searcher receives is `combined_score`. Robustness, mechanism recovery and every
per-instance metric are evaluator-only by the visibility contract, and the classifier that decides
saturation never sees them - it works from the one number the searcher was steering by.

`CalorimeterDesign` makes the gap concrete: 1.0121 at a single proposal, past its reference
witness, and `robustness_score` of exactly 0.0 - its worst-shift utility sits at the shipped
baseline. The searcher beat the witness on the visible axis and gained nothing on the hidden one.
Read as plain "saturated", that evidence would retire a task half of which is untouched.

The classifier cannot be taught to see the hidden axes - the visibility filter strips them before
anything is written, deliberately. What it can do is not claim more than it measured.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.metric_visibility import SEARCH_VISIBLE_KEYS  # noqa: E402


def _module(name: str):
    spec = importlib.util.spec_from_file_location(
        "scope_%s" % name, ROOT / "scripts" / ("%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SaturationScopeTests(unittest.TestCase):
    def test_a_saturation_verdict_names_the_metric_it_is_about(self):
        module = _module("audit_measurement_health")
        report = module.build_report()
        saturated = [row for row in report["tasks"]
                     if row["classification"] == module.SATURATED_ON_RAMP]
        self.assertTrue(saturated, "expected some saturated tasks to check")
        for row in saturated:
            reasons = " ".join(row["classification_reasons"])
            self.assertIn(
                "combined_score", reasons,
                "%s is called saturated without saying which metric that is true of" % row["task"])

    def test_robustness_is_not_a_metric_the_classifier_could_have_seen(self):
        """If this ever becomes visible, the verdict can be strengthened rather than qualified."""
        self.assertNotIn("robustness_score", SEARCH_VISIBLE_KEYS)
        self.assertIn("combined_score", SEARCH_VISIBLE_KEYS)

    def test_the_hidden_axis_reporter_distinguishes_a_rate_from_a_score(self):
        """Zero is the best value on a false-discovery rate and no gain on a normalised score.

        Conflating them marked `GravityInversion` as half-done on the strength of its best result.
        """
        source = (ROOT / "scripts" / "report_saturation_hidden_axes.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("_score", source)
        # The call-out is gated on the key being a normalised score, not on the value alone.
        gated = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and getattr(node.func, "attr", None) == "endswith"
                 and node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == "_score"]
        self.assertTrue(
            gated,
            "the reporter no longer restricts its no-gain call-out to normalised scores, so a "
            "rate at zero - its best possible value - will be reported as an untouched axis")


if __name__ == "__main__":
    unittest.main()
