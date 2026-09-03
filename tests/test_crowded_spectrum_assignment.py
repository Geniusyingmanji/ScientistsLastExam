"""Discovery-contract pins for CrowdedSpectrumAssignment.

The public score is mechanism, normalised so that declining every world is exactly zero.
Blank and contaminant worlds are the unsupported cases. The species set is gated, so a
baseline that over-claims the alias scores zero on those worlds even if it names the
right pair among extras.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Chemistry/CrowdedSpectrumAssignment"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CrowdedSpectrumAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "crowded_spectrum_oracle")
        cls.baseline = _load(TASK / "solution.py", "crowded_spectrum_baseline")
        cls.reference = _load(
            TASK / "verification/reference_assignment.py", "crowded_spectrum_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _scan, _zoom: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_mechanism_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_nearest_library_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.assign_species)
        reference = self.evaluator.evaluate(self.reference.assign_species)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertGreater(reference["combined_score"], 0.0)
        self.assertIn("development_false_discovery_rate", baseline)
        self.assertIn("development_correct_refusal_rate", baseline)

    def test_an_alias_world_is_not_solved_by_the_default_scan_alone(self):
        """The planted alias is the experiment-design content: without zooms the
        nearest-library baseline cannot name the unique subset."""
        baseline = self.evaluator.evaluate(self.baseline.assign_species)
        alias = [row for row in baseline["per_instance"]
                 if row["kind"] == "alias" and row["split"] == "development"]
        self.assertTrue(alias)
        self.assertFalse(any(row["species_set_correct"] for row in alias))

    def test_alias_worlds_include_both_sides_of_the_ambiguous_default_peak(self):
        truths = []
        for spec in self.evaluator.DEVELOPMENT_WORLDS + self.evaluator.HELDOUT_WORLDS:
            if spec["kind"] == "alias":
                truths.append({name for name, _fraction in self.evaluator._world(spec)["components"]})
        self.assertIn({"gamma", "delta"}, truths)
        self.assertIn({"epsilon"}, truths)

        for specs in (
            self.evaluator.DEVELOPMENT_WORLDS,
            self.evaluator.HELDOUT_WORLDS,
        ):
            aliases = [spec for spec in specs if spec["kind"] == "alias"]
            scans = [
                self.evaluator._Instrument(
                    self.evaluator._world(spec), self.evaluator.ZOOM_BUDGET
                ).scan()
                for spec in aliases
            ]
            self.assertEqual(scans[0], scans[1])

        def fixed_blend_claim(_problem, scan, zoom):
            del zoom
            scan()
            return {
                "species": [
                    {"name": "gamma", "fraction": 0.5},
                    {"name": "delta", "fraction": 0.5},
                ],
                "confidence": 1.0,
                "abstain": False,
            }

        metrics = self.evaluator.evaluate(fixed_blend_claim)
        aliases = [row for row in metrics["per_instance"] if row["kind"] == "alias"]
        self.assertTrue(any(row["species_set_correct"] for row in aliases))
        self.assertTrue(any(not row["species_set_correct"] for row in aliases))

    def test_zero_zoom_peak_height_attack_cannot_solve_both_alias_truths(self):
        def threshold_attack(_problem, scan, zoom):
            del zoom
            peaks = scan()
            mean_height = sum(float(row["intensity"]) for row in peaks) / len(peaks)
            names = ["epsilon"] if mean_height > 0.97 else ["gamma", "delta"]
            return {
                "species": [
                    {"name": name, "fraction": 1.0 / len(names)} for name in names
                ],
                "confidence": 1.0,
                "abstain": False,
            }

        metrics = self.evaluator.evaluate(threshold_attack)
        aliases = [row for row in metrics["per_instance"] if row["kind"] == "alias"]
        self.assertTrue(all(row["zoom_calls"] == 0 for row in aliases))
        self.assertLess(sum(row["species_set_correct"] for row in aliases), len(aliases))

    def test_zoom_reference_distinguishes_both_sides_of_every_alias_pair(self):
        metrics = self.evaluator.evaluate(self.reference.assign_species)
        aliases = [row for row in metrics["per_instance"] if row["kind"] == "alias"]
        self.assertEqual(len(aliases), 4)
        self.assertTrue(all(row["zoom_calls"] > 0 for row in aliases))
        self.assertTrue(all(row["species_set_correct"] for row in aliases))


if __name__ == "__main__":
    unittest.main()
