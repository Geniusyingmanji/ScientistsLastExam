"""Discovery-contract pins for QuinaryConvexHull.

The public score is mechanism, normalised so that declining every world is exactly zero.
Glass worlds are unsupported. An E_f<0 baseline therefore scores zero even when it happens
to name the vertices on one hull, because near-hull junk and glass are published as stables.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Chemistry/QuinaryConvexHull"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuinaryConvexHullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "hull_oracle")
        cls.baseline = _load(TASK / "solution.py", "hull_baseline")
        cls.reference = _load(
            TASK / "verification/reference_hull.py", "hull_reference"
        )

    def test_the_catalog_is_the_35_compositions_of_three_into_five(self):
        self.assertEqual(len(self.evaluator.CATALOG_NAMES), 35)
        self.assertEqual(len(self.evaluator.UNARY_NAMES), 5)
        self.assertEqual(self.evaluator.N_ATOMS, 3)
        self.assertEqual(self.evaluator.N_ELEM, 5)

    def test_ef_negative_is_not_the_vertex_set_on_a_hull_world(self):
        spec = next(item for item in self.evaluator.DEVELOPMENT_WORLDS
                    if item["kind"] in ("hull", "near_hull"))
        true = set(self.evaluator._truth(spec))
        energies = self.evaluator._frozen_energies(spec)
        negative = {
            self.evaluator.CATALOG_NAMES[i]
            for i, energy in enumerate(energies)
            if energy < 0.0 and self.evaluator.CATALOG_NAMES[i] not in self.evaluator.UNARY_NAMES
        }
        self.assertTrue(true)
        self.assertTrue(negative - true)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _relax: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_ef_cut_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.recover_hull)
        reference = self.evaluator.evaluate(self.reference.recover_hull)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["development_signal_recovery_rate"], 1.0)

    def test_the_reference_runs_through_the_same_secure_path_as_submissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            subprocess.run(
                [
                    sys.executable,
                    str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate",
                    str(TASK / "verification/reference_hull.py"),
                    "--metrics-out",
                    str(metrics_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 1.0)

    def test_this_is_not_a_binary_xrd_phase_diagram_or_stick_library(self):
        from sle.registry import find_task
        spec = find_task("MaterialsScience/QuinaryConvexHull", include_uncertified=True)
        phase = find_task("MaterialsScience/PhaseDiagramDiscovery", include_uncertified=True)
        spectrum = find_task("Spectroscopy/CrowdedSpectrumAssignment", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "recover_hull")
        self.assertNotEqual(spec.entrypoint, phase.entrypoint)
        self.assertNotEqual(spec.entrypoint, spectrum.entrypoint)
        self.assertNotEqual(spec.task_dir, phase.task_dir)
        source = (spec.task_dir / "verification/evaluator.py").read_text(encoding="utf-8")
        self.assertNotIn("pymatgen", source.lower())
        self.assertNotIn("mace", source.lower())


if __name__ == "__main__":
    unittest.main()
