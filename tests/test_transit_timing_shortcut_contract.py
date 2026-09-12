"""Known fixed schedules must reach the real shortcut guard unchanged."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Physics/TransitTimingAttribution"
VERIFICATION = TASK / "verification"
FAMILIES = {
    "a": ((13, 26, 43, 59), 1.2, 3.0, 0.8),
    "b": ((16, 32, 48, 59), 1.0, 0.0, 0.35),
    "c": ((16, 32, 48, 59), 99.0, 6.0, 0.5),
}


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransitTimingShortcutContractTests(unittest.TestCase):
    def test_contract_registers_all_three_known_families(self):
        card = yaml.safe_load((TASK / "TASK_CARD.yaml").read_text())
        contract = card["shortcut_probe"]
        self.assertEqual(contract["reference"], {
            "candidate": "verification/reference_solver.py", "expected_score": 0.754681})
        self.assertEqual(contract["relative_margin"], 0.2)
        self.assertEqual(contract["score_tolerance"], 0.000001)
        probes = {row["id"]: row for row in contract["probes"]}
        self.assertEqual(set(probes), {"legal_baseline", *(
            "fixed_schedule_family_" + family for family in FAMILIES)})
        for family, expected in zip(FAMILIES, (0.574956, 0.543759, 0.515176)):
            row = probes["fixed_schedule_family_" + family]
            self.assertEqual(row["candidate"], "verification/shortcut_family_" + family + ".py")
            self.assertEqual(row["expected_score"], expected)
            self.assertTrue((TASK / row["candidate"]).is_file())

    def test_family_a_remains_frozen_and_is_replayed_directly(self):
        candidate=(VERIFICATION / "shortcut_family_a.py").read_bytes()
        self.assertEqual(hashlib.sha256(candidate).hexdigest(),
                         "534ed09d974ef9e9e2798eb9486dca8b81f6422a89336ce7a4ac406cf8c1ee99")
        replay=(VERIFICATION / "replay_probes.py").read_text()
        self.assertIn('verification/shortcut_family_a.py',replay)

    def test_standalone_candidates_preserve_budget_and_refusal_boundaries(self):
        # Extract the historical public-input policy without importing calibrate.py,
        # whose offline sweep loads the private evaluator at module import time.
        tree = ast.parse((VERIFICATION / "calibrate.py").read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "fitted_policy")
        reference = types.SimpleNamespace()
        namespace = {"reference": reference}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "original_fitted_policy", "exec"), namespace)
        for family, parameters in FAMILIES.items():
            path = VERIFICATION / ("shortcut_family_" + family + ".py")
            candidate_tree = ast.parse(path.read_text())
            imports = {alias.name.split(".")[0] for node in ast.walk(candidate_tree)
                       if isinstance(node, ast.Import) for alias in node.names}
            from_imports = {node.module for node in ast.walk(candidate_tree)
                            if isinstance(node, ast.ImportFrom)}
            self.assertEqual(imports, {"math", "numpy"})
            self.assertEqual(from_imports, {"__future__"})
            candidate = load_source(path, "standalone_ttv_" + family)
            original = namespace["fitted_policy"](*parameters)
            schedule, rms, gap, correlation = parameters
            cases = ((rms, gap, correlation), (rms + 0.01, gap, correlation),
                     (rms, gap - 0.01, correlation), (rms, gap, correlation + 0.01))
            for budget in (0, 1, 2, 4, 8):
                for diagnostic_values in cases:
                    with self.subTest(family=family, budget=budget, diagnostics=diagnostic_values):
                        observed_queries = []
                        original_queries = []
                        def measure(queries, number):
                            queries.append(number)
                            return {"query_id": "q" + str(number), "timing_offset_days": 0.01}
                        def diagnostics(observation, x, y):
                            relative_rms, model_gap, corr = diagnostic_values
                            return ("planet", 5.2, None), model_gap, relative_rms, corr
                        reference._diagnostics = diagnostics
                        reference._predict = lambda model, number: 0.125
                        observation = {"transit_numbers": [0, 1], "timing_offsets_days": [0.0, 0.01],
                                       "forecast_transit_number": 75}
                        with patch.object(candidate, "_diagnostics", side_effect=diagnostics), \
                             patch.object(candidate, "_predict", return_value=0.125):
                            actual = candidate.attribute_ttv(observation,
                                lambda number: measure(observed_queries, number), budget)
                            expected = original(observation,
                                lambda number: measure(original_queries, number), budget)
                        self.assertEqual(actual, expected)
                        self.assertEqual(observed_queries, list(schedule[:budget]))
                        self.assertEqual(observed_queries, original_queries)
                        self.assertEqual(actual["abstain"], budget < 2 or diagnostic_values != cases[0])


if __name__ == "__main__":
    unittest.main()
