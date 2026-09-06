"""Pinned invariants for the 2026-09-05 round-four candidate tasks.

Each class pins the construction errors recorded in the task's known_best.md and
the repo-wide baseline/reference/bad-candidate contract. Tests load evaluators
directly; sandbox-dependent behaviour is out of scope here.
"""


from __future__ import annotations


import importlib.util


import json


import unittest


from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


TASKS = {'WaterDistribution/DistributionNetworkTopology': ('benchmarks/Engineering/DistributionNetworkTopology',
                                                   'recover_network')}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RoundFourPackageTests(unittest.TestCase):
    def test_baselines_valid_zero_and_deterministic(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_" + entrypoint)
            baseline = _load(ROOT / directory / "solution.py",
                             "r4_baseline_" + entrypoint)
            first = evaluator.evaluate(getattr(baseline, entrypoint))
            second = evaluator.evaluate(getattr(baseline, entrypoint))
            self.assertEqual(first["valid"], 1.0, task_id)
            self.assertLessEqual(abs(first["combined_score"]), 0.01, task_id)
            self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                             json.dumps(second, sort_keys=True, default=str), task_id)

    def test_references_valid_and_above_floor(self):
        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_ref_" + entrypoint)
            reference = _load(ROOT / directory / "verification" / "reference_solver.py",
                              "r4_reference_" + entrypoint)
            result = evaluator.evaluate(getattr(reference, entrypoint))
            self.assertEqual(result["valid"], 1.0, task_id)
            self.assertGreater(result["combined_score"], 0.05, task_id)

    def test_bad_candidates_score_invalid_without_crashing(self):
        def raises(*args, **kwargs):
            raise RuntimeError("candidate failure")

        for task_id, (directory, entrypoint) in TASKS.items():
            evaluator = _load(ROOT / directory / "verification" / "evaluator.py",
                              "r4_evaluator_bad_" + entrypoint)
            for candidate in (raises, lambda *a, **k: {}, lambda *a, **k: "junk"):
                result = evaluator.evaluate(candidate)
                self.assertEqual(result["valid"], 0.0, task_id)
                self.assertEqual(result["combined_score"], 0.0, task_id)


class DistributionNetworkPins(unittest.TestCase):
    def test_default_level_carries_two_break_ambiguity(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        self.assertEqual(ev.DIFFICULTY, 2)
        self.assertEqual(ev._difficulty_profile()["max_broken"], 2)

    def test_twin_pipes_share_route_signatures(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        incidence = {}
        for route_id, pipes in zip(ev.ROUTE_IDS, ev.ROUTES):
            for pipe in pipes:
                incidence.setdefault(pipe, set()).add(route_id)
        self.assertEqual(incidence["s11"], incidence["s21"])
        covered = set(incidence)
        self.assertEqual(covered, set(ev.PIPE_IDS))

    def test_supported_break_sets_are_signature_unique(self):
        ev = _load("benchmarks/Engineering/DistributionNetworkTopology"
                   "/verification/evaluator.py", "r4_water")
        for spec in ev._BASE_DEVELOPMENT_SPECS + ev.HELDOUT_SPECS:
            world = ev._world(spec)
            if world["kind"] == "supported":
                self.assertTrue(ev._identifiable(world["broken"], 3), spec)


if __name__ == "__main__":
    unittest.main()
