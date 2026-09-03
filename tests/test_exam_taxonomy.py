"""The exam-surface map must cover the inventory and stay aligned with metadata."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_exam_taxonomy import issues, load_taxonomy, summary  # noqa: E402
from sle.registry import list_tasks  # noqa: E402


class ExamTaxonomyTests(unittest.TestCase):
    def test_every_listed_task_has_exactly_one_cell(self):
        self.assertEqual(issues(), [])
        report = summary()
        self.assertEqual(report["task_count"], len(list_tasks(None)))
        self.assertEqual(
            report["forms"]["optimization"] + report["forms"]["discovery"],
            report["task_count"],
        )

    def test_discovery_kinds_are_not_collapsed_into_one_bin(self):
        kinds = summary()["discovery_kinds"]
        for name in ("formula", "structure", "evidence", "substance", "parameter_inversion"):
            self.assertGreater(kinds.get(name, 0), 0, name)

    def test_declared_taxonomy_values_are_the_values_tasks_actually_use(self):
        tax = load_taxonomy()
        optimization = {
            row["analogue"] for row in tax["tasks"].values()
            if row.get("form") == "optimization"
        }
        discovery = {
            row["kind"] for row in tax["tasks"].values()
            if row.get("form") == "discovery"
        }
        self.assertEqual(optimization, set(tax["optimization_analogue"]))
        self.assertEqual(discovery, set(tax["discovery_kind"]))

    def test_on_ramps_are_named_rather_than_paired(self):
        tax = load_taxonomy()
        self.assertEqual(
            tax["tasks"]["SystemsBiology/EnzymeKineticsLaw"].get("note"),
            "on_ramp_do_not_pair",
        )
        self.assertEqual(
            tax["tasks"]["ParticlePhysics/DiscrepantMeasurements"].get("note"),
            "on_ramp_do_not_pair",
        )

if __name__ == "__main__":
    unittest.main()
