"""The current fixed-schedule family must reach the declared guard unchanged."""
import importlib.util
from pathlib import Path
import unittest

import yaml

from scripts.shortcut_probe_contract import undeclared_candidates, validate_contract
from sle.registry import list_tasks


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Physics/TransitTimingAttribution"
VERIFICATION = TASK / "verification"


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransitTimingShortcutContractTests(unittest.TestCase):
    def test_contract_registers_reference_baseline_and_strongest_fixed_policy(self):
        card = yaml.safe_load((TASK / "TASK_CARD.yaml").read_text(encoding="utf-8"))
        contract = card["shortcut_probe"]
        self.assertEqual(
            contract["reference"],
            {
                "candidate": "verification/reference_solver.py",
                "expected_score": 0.594835,
            },
        )
        self.assertEqual(contract["relative_margin"], 0.2)
        self.assertEqual(contract["score_tolerance"], 0.000001)
        probes = {row["id"]: row for row in contract["probes"]}
        self.assertEqual(set(probes), {"legal_baseline", "strongest_fixed_schedule"})
        self.assertEqual(
            probes["strongest_fixed_schedule"],
            {
                "candidate": "verification/reference_no_active_design.py",
                "expected_score": 0.432153,
                "id": "strongest_fixed_schedule",
            },
        )
        validate_contract(contract, TASK)

    def test_every_in_tree_entrypoint_is_declared_or_excluded(self):
        card = yaml.safe_load((TASK / "TASK_CARD.yaml").read_text(encoding="utf-8"))
        spec = next(
            spec
            for spec in list_tasks(None)
            if spec.task_id == "Exoplanets/TransitTimingAttribution"
        )
        self.assertEqual(undeclared_candidates(card["shortcut_probe"], spec), [])

    def test_fixed_candidate_matches_the_grid_winner_parameters(self):
        fixed = load_source(
            VERIFICATION / "reference_no_active_design.py", "standalone_ttv_fixed"
        )
        source = (VERIFICATION / "reference_no_active_design.py").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "fractions=(0.00,0.20,0.45,0.70,1.00)",
            "1.3,6.0,0.5",
            "alternative_gap_limit=6.0",
        ):
            self.assertIn(fragment, source)
        self.assertTrue(callable(fixed.attribute_ttv))

    def test_replay_driver_uses_the_declared_fixed_candidate(self):
        replay = (VERIFICATION / "replay_probes.py").read_text(encoding="utf-8")
        self.assertIn('verification/reference_no_active_design.py', replay)
        self.assertNotIn("shortcut_family_a.py", replay)


if __name__ == "__main__":
    unittest.main()
