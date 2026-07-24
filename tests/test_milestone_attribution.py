from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_milestone_attribution.py"
    spec = importlib.util.spec_from_file_location("ma1_analysis_test", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load MA1 analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash(label):
    import hashlib
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


OUTCOMES = [
    {"name": "development_score", "direction": "maximize", "material_epsilon": 0.05},
    {"name": "sealed_score", "direction": "maximize", "material_epsilon": 0.05},
    {"name": "mechanism_score", "direction": "maximize", "material_epsilon": 0.05},
    {"name": "false_discovery_rate", "direction": "minimize", "material_epsilon": 0.0},
    {"name": "validity", "direction": "maximize", "material_epsilon": 0.0},
]
GATES = [
    {"metric": "validity", "operator": ">=", "threshold": 1.0},
    {"metric": "false_discovery_rate", "operator": "<=", "threshold": 0.1},
]


def _row(label, parent, common, dev, sealed, mechanism, fdr=0.0, valid=1.0):
    return {
        "artifact_sha256": _hash(label),
        "built_from_parent_sha256": parent,
        "executable": True,
        **common,
        "metrics": {
            "development_score": dev,
            "sealed_score": sealed,
            "mechanism_score": mechanism,
            "false_discovery_rate": fdr,
            "validity": valid,
        },
    }


def _manifest(*, proxy=False, harmful=False, nonseparable=False):
    parent_hash = _hash("parent")
    child_hash = _hash("full")
    common = {
        "evidence_access_sha256": _hash("evidence"),
        "evaluator_manifest_sha256": _hash("evaluator"),
        "world_panel_sha256": _hash("worlds"),
        "environment_sha256": _hash("environment"),
    }
    parent = _row("parent", parent_hash, common, 0.2, 0.2, 0.2)
    parent.pop("built_from_parent_sha256")
    full = _row(
        "full", parent_hash, common, 0.7,
        0.22 if proxy else 0.7,
        0.22 if proxy else 0.7,
        0.5 if harmful else 0.0,
    )
    component = _row("component", parent_hash, common, 0.5, 0.5, 0.5)
    leave_out = _row("leaveout", parent_hash, common, 0.35, 0.35, 0.35)
    rollback = _row("rollback", parent_hash, common, 0.3, 0.3, 0.3)
    treatments = {
        "parent": parent,
        "full_child": full,
        "component_only:D": component,
        "leave_one_out:D": leave_out,
        "rollback:D": rollback,
    }
    if nonseparable:
        treatments["component_only:D"] = {
            "artifact_sha256": _hash("nonseparable"),
            "built_from_parent_sha256": parent_hash,
            "executable": False,
            "non_separable": True,
            "reason": "component requires another dependency",
        }
    return {
        "schema_version": 1,
        "cohort_id": "synthetic",
        "evidence_class": "synthetic_test",
        "outcomes": OUTCOMES,
        "hard_gates": GATES,
        "milestones": [{
            "milestone_id": "m1",
            "task": "Synthetic/Mechanism",
            "parent_sha256": parent_hash,
            "child_sha256": child_hash,
            "eligible": True,
            "sampled": True,
            "factors": ["D"],
            "visible_outcome": "development_score",
            "sealed_outcomes": ["sealed_score", "mechanism_score"],
            "attribution_outcomes": ["sealed_score", "mechanism_score"],
            "data_changed": True,
            "method_changed": False,
            "common_replay": common,
            "factorials": [],
            "treatments": treatments,
        }],
    }


class MilestoneAttributionTests(unittest.TestCase):
    def test_component_effect_and_reliability_decisions(self):
        module = _module()
        report = module.analyze_manifest(_manifest())
        row = report["milestones"][0]
        self.assertEqual(row["decision"], "bounded_component_attribution")
        self.assertEqual(row["attributed_factors"], ["D"])
        self.assertAlmostEqual(
            row["estimands"]["full_child"]["sealed_score"]["favorable_effect"],
            0.5,
        )

        proxy = module.analyze_manifest(_manifest(proxy=True))["milestones"][0]
        self.assertEqual(proxy["decision"], "development_only_proxy_improvement")

        harmful = module.analyze_manifest(_manifest(harmful=True))["milestones"][0]
        self.assertEqual(harmful["decision"], "reliability_or_validity_gate_failed")

    def test_nonseparable_is_reported_not_scored_zero(self):
        module = _module()
        row = module.analyze_manifest(
            _manifest(nonseparable=True)
        )["milestones"][0]
        self.assertIn("component_only:D", row["non_separable_treatments"])
        self.assertNotIn("D", row["estimands"]["component_only"])
        self.assertEqual(row["decision"], "bounded_component_attribution")

    def test_interaction_and_data_method_factorials(self):
        module = _module()
        manifest = _manifest()
        milestone = manifest["milestones"][0]
        milestone["factors"] = ["D", "M"]
        milestone["factorials"] = [["D", "M"]]
        milestone["data_changed"] = True
        milestone["method_changed"] = True
        common = milestone["common_replay"]
        parent = milestone["parent_sha256"]
        for prefix in ("factorial:D:M:", "data_method:"):
            for suffix, score in (("00", 0.2), ("10", 0.35), ("01", 0.3), ("11", 0.8)):
                milestone["treatments"][prefix + suffix] = _row(
                    prefix + suffix, parent, common, score, score, score,
                )
        row = module.analyze_manifest(manifest)["milestones"][0]
        self.assertAlmostEqual(
            row["estimands"]["factor_interactions"]["D:M"]["sealed_score"][
                "raw_interaction"
            ],
            0.35,
        )
        self.assertEqual(row["attributed_interactions"], ["D:M"])
        self.assertEqual(row["attributed_factors"], ["D", "M"])
        self.assertAlmostEqual(
            row["estimands"]["data_method_interaction"]["mechanism_score"][
                "raw_interaction"
            ],
            0.35,
        )

    def test_hash_or_evidence_mismatch_fails_closed(self):
        module = _module()
        manifest = _manifest()
        manifest["milestones"][0]["treatments"]["full_child"][
            "evidence_access_sha256"
        ] = _hash("wrong")
        with self.assertRaisesRegex(ValueError, "evidence_access"):
            module.analyze_manifest(manifest)

        manifest = _manifest()
        manifest["milestones"][0]["treatments"]["full_child"][
            "built_from_parent_sha256"
        ] = _hash("wrong-parent")
        with self.assertRaisesRegex(ValueError, "frozen parent"):
            module.analyze_manifest(manifest)

    def test_real_task_positive_controls_and_empty_agent_frame(self):
        module = _module()
        report = module.analyze_positive_controls()
        self.assertTrue(report["execution_passed"])
        sampling = report["input_provenance"]["agent_milestone_sampling_frame"]
        self.assertEqual(sampling["eligible_agent_milestone_count"], 0)
        self.assertTrue(sampling["reaction_blind_selected_excluded"])
        rows = {
            row["milestone_id"]: row
            for row in report["analysis"]["milestones"]
        }
        self.assertEqual(
            rows["reaction_classical_bundle_control"]["decision"],
            "reliability_or_validity_gate_failed",
        )
        self.assertEqual(
            rows["convection_off_axis_evidence_control"]["decision"],
            "bounded_component_attribution",
        )
        self.assertIn(
            "not an agent scientific insight",
            rows["convection_off_axis_evidence_control"]["allowed_wording"],
        )


if __name__ == "__main__":
    unittest.main()
