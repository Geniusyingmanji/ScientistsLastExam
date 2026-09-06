"""Discovery-contract pins for GridTopologyRecovery."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Engineering/GridTopologyRecovery"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GridTopologyRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "grid_oracle")
        cls.baseline = _load(TASK / "solution.py", "grid_baseline")
        cls.reference = _load(
            TASK / "verification/reference_topology.py", "grid_reference"
        )

    def test_graph_3_and_graph_4_match_on_the_frozen_injections(self):
        for injection in self.evaluator.INJECTIONS:
            left = self.evaluator._angles(self.evaluator.CATALOG["graph_3"], injection)
            right = self.evaluator._angles(self.evaluator.CATALOG["graph_4"], injection)
            self.assertLess(np.max(np.abs(left - right)), 1e-12)
        unique = self.evaluator._angles(
            self.evaluator.CATALOG["graph_0"], self.evaluator.INJECTIONS[0]
        )
        other = self.evaluator._angles(
            self.evaluator.CATALOG["graph_1"], self.evaluator.INJECTIONS[0]
        )
        self.assertGreater(np.max(np.abs(unique - other)), 0.05)

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _measure: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_star_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.recover_topology)
        reference = self.evaluator.evaluate(self.reference.recover_topology)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertGreater(reference["development_signal_recovery_rate"], 0.99)
        self.assertGreater(reference["development_correct_refusal_rate"], 0.99)

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: {})
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_modal_damage_or_a_hidden_coupling_network(self):
        from sle.registry import find_task
        spec = find_task("PowerSystems/GridTopologyRecovery", include_uncertified=True)
        modal = find_task("StructuralEngineering/ModalDamageAttribution", include_uncertified=True)
        hidden = find_task("Physics/HiddenCouplingNetwork", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "recover_topology")
        self.assertNotEqual(spec.task_dir, modal.task_dir)
        self.assertNotEqual(spec.task_dir, hidden.task_dir)


if __name__ == "__main__":
    unittest.main()
