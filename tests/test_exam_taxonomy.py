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

    def test_wave0_siblings_are_named_as_disjoint_instance_sets(self):
        """CapSetFrontier and TensorRank555 share an oracle family with a certified
        package. The taxonomy note is the ledger that they are new instance sets,
        not silent extensions of those certified cells."""
        tax = load_taxonomy()
        self.assertEqual(
            tax["tasks"]["Mathematics/CapSetFrontier"].get("note"),
            "open_dims_not_extension_of_certified_capset",
        )
        self.assertEqual(
            tax["tasks"]["Algorithm/TensorRank555"].get("note"),
            "new_sizes_not_extension_of_certified_matmul",
        )
        self.assertEqual(
            tax["tasks"]["ParticlePhysics/LookElsewhereAnomaly"].get("note"),
            "trials_factor_not_clone_of_discrepant_measurements",
        )
        self.assertEqual(
            tax["tasks"]["CausalDiscovery/SurvivorshipConfoundedDesign"].get("note"),
            "selection_not_clone_of_interventional_scm",
        )
        self.assertEqual(
            tax["tasks"]["Oceanography/AMOCTippingRefusal"].get("note"),
            "fold_refusal_not_ebm_parameter_fit",
        )
        self.assertEqual(
            tax["tasks"]["Gravitation/PTAHellingsDowns"].get("note"),
            "hd_orf_not_lookelsewhere_bump",
        )
        self.assertEqual(
            tax["tasks"]["Physics/ComplexBoseLaw"].get("note"),
            "bose_exponents_not_activelaw_ode",
        )
        self.assertEqual(
            tax["tasks"]["MaterialsScience/QuinaryConvexHull"].get("note"),
            "quinary_hull_not_binary_xrd",
        )
        self.assertEqual(
            tax["tasks"]["Mathematics/HeavyTailEvidence"].get("note"),
            "clauset_tails_not_lookelsewhere",
        )
        self.assertEqual(
            tax["tasks"]["Glaciology/GlenFlowLawDiscovery"].get("note"),
            "glen_exponent_not_amoc_fold_or_wall_closure",
        )


if __name__ == "__main__":
    unittest.main()
