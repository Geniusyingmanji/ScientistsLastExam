"""Contract and normalization checks for the retained engineering candidate task."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "benchmarks" / "Engineering"
TASKS = (
    "WakeAwareFarmCoDesign",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EngineeringCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluators = {
            name: load(TASK_ROOT / name / "verification" / "evaluator.py", "eval_" + name)
            for name in TASKS
        }
        cls.solutions = {
            name: load(TASK_ROOT / name / "solution.py", "solution_" + name)
            for name in TASKS
        }
        cls.references = {
            name: load(TASK_ROOT / name / "verification" / "reference.py", "reference_" + name)
            for name in TASKS
        }

    def _baseline(self, name):
        entry = (TASK_ROOT / name / "frontier_eval" / "entrypoint.txt").read_text().strip()
        return getattr(self.solutions[name], entry)

    def _reference(self, name):
        entry = (TASK_ROOT / name / "frontier_eval" / "entrypoint.txt").read_text().strip()
        return getattr(self.references[name], entry)

    def test_shipped_baselines_are_valid_and_define_zero(self):
        for name in TASKS:
            with self.subTest(name=name):
                result = self.evaluators[name].evaluate(self._baseline(name))
                repeated = self.evaluators[name].evaluate(self._baseline(name))
                self.assertEqual(result["valid"], 1.0)
                self.assertAlmostEqual(result["combined_score"], 0.0, places=8)
                self.assertIn("heldout_policy_score", result)
                self.assertEqual(result, repeated)

    def test_truth_blind_references_leave_headroom_on_development(self):
        for name in TASKS:
            with self.subTest(name=name):
                result = self.evaluators[name].evaluate(self._reference(name))
                self.assertEqual(result["valid"], 1.0)
                self.assertGreater(result["combined_score"], 0.50)
                self.assertLess(result["combined_score"], 0.80)

    def test_malformed_candidates_fail_closed(self):
        def malformed(*_args, **_kwargs):
            return None
        for name in TASKS:
            with self.subTest(name=name):
                result = self.evaluators[name].evaluate(malformed)
                self.assertEqual(result["valid"], 0.0)
                self.assertEqual(result["combined_score"], 0.0)
                self.assertTrue(all(not row["valid"] for row in result["per_instance"]))

    def test_task_specific_hard_constraints_reject_bad_artifacts(self):
        wind = self.evaluators["WakeAwareFarmCoDesign"]
        problem = wind._problem(wind.INSTANCE_SPECS[0])
        n = problem["turbine_count"]
        with self.assertRaises(ValueError):
            wind._validate(problem, {"layout_xy_m": [[1.0, 1.0]] * n,
                                     "yaw_by_direction_deg": [[0.0] * n] * 12})


if __name__ == "__main__":
    unittest.main()
