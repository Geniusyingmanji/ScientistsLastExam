from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_science.benchmark_layout import (
    DISCIPLINE_DOMAINS,
    discipline_for_domain,
    task_path,
)
from frontier_science import registry
from frontier_science.registry import discover_task_dirs, list_tasks
from scripts.gen_task import create_task


class BenchmarkLayoutTests(unittest.TestCase):
    def test_inventory_uses_only_declared_discipline_roots(self):
        roots = {path.parent.name for path in discover_task_dirs()}
        self.assertEqual(roots, set(DISCIPLINE_DOMAINS))
        self.assertEqual(len(list_tasks(None)), 59)

    def test_logical_domain_is_independent_of_physical_discipline(self):
        specs = {spec.task_id: spec for spec in list_tasks(None)}
        chemistry = specs["Chemistry/LennardJonesCluster"]
        self.assertEqual(chemistry.discipline, "Chemistry")
        self.assertEqual(chemistry.domain, "Chemistry")
        self.assertEqual(
            task_path(Path("benchmarks"), "Chemistry", "LennardJonesCluster"),
            Path("benchmarks/Chemistry/LennardJonesCluster"),
        )

    def test_every_inventory_domain_has_one_declared_discipline(self):
        for spec in list_tasks(None):
            self.assertEqual(discipline_for_domain(spec.domain), spec.discipline)

    def test_generator_places_new_task_under_declared_discipline(self):
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = create_task({
                "domain": "Chemistry",
                "task": "GeneratedLayoutSmoke",
                "difficulty": "hard",
                "oracle_type": "analytical",
                "score_mode": "clipped",
                "eval_time_seconds": 1,
                "science_metric": "smoke",
                "reference_baseline": "none",
                "reference_sota": "none",
                "citation": "none",
                "entrypoint": "solve",
                "task_md": "# Smoke\n",
                "baseline_code": "def solve(): return 0\n",
                "evaluator_code": "def evaluate(candidate): return {'combined_score': 0.0, 'valid': 1.0}\n",
            }, repo=Path(temporary))
        self.assertEqual(
            task_dir.relative_to(temporary),
            Path("benchmarks/Chemistry/GeneratedLayoutSmoke"),
        )

    def test_unknown_domain_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown benchmark domain"):
            discipline_for_domain("UnassignedResearchArea")

    def test_generator_rejects_mismatched_discipline_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "belongs to discipline"):
                create_task({
                    "domain": "Chemistry",
                    "discipline": "Physics",
                    "task": "MisplacedSmoke",
                    "difficulty": "hard",
                }, repo=Path(temporary))

    def test_registry_rejects_undeclared_top_level_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            benchmarks = Path(temporary)
            (benchmarks / "AdHocDomain").mkdir()
            with patch.object(registry, "BENCHMARKS", benchmarks):
                with self.assertRaisesRegex(ValueError, "Unexpected top-level"):
                    registry.discover_task_dirs()


if __name__ == "__main__":
    unittest.main()
