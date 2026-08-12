"""Pin the theme-fit audit, in particular the check that first read four tasks wrongly.

`open_ended` asks one narrow question: does the task's own card describe its *anchor* as
something a correct implementation reaches. A first version matched the bare word "exact" and
flagged eighteen tasks, four of which it had no business flagging:

  * the decoder task, whose baseline sentence says "scores exactly 0 by construction" — that is
    about the baseline, which is supposed to be trivial;
  * an alloy task containing the compound "exact-recipe confirmation";
  * two discovery tasks describing "the exact hidden graph" and "exact simulator peak parameters"
    — the truth a discovery task exists to recover, which every discovery task has.

Over-flagging is as damaging as under-flagging here: it would have retired tasks that are the
benchmark's strongest.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_theme_fit.py"
    spec = importlib.util.spec_from_file_location("theme_fit_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class ClosedFormDetectionTests(unittest.TestCase):
    def test_a_manufactured_solution_is_closed_form(self):
        self.assertTrue(MODULE.CLOSED_FORM.search("near-exact manufactured sine-series solution"))

    def test_unit_fidelity_is_closed_form(self):
        self.assertTrue(MODULE.CLOSED_FORM.search("unit global-phase-invariant process fidelity"))

    def test_the_global_optimum_is_closed_form(self):
        self.assertTrue(MODULE.CLOSED_FORM.search("the global optimum of the relaxed problem"))

    def test_a_trivial_baseline_phrase_is_not_a_closed_form_anchor(self):
        self.assertIsNone(
            MODULE.CLOSED_FORM.search("decoder that never predicts a flip; scores exactly 0 "
                                      "by construction"))

    def test_a_hyphenated_compound_is_not_a_closed_form_anchor(self):
        self.assertIsNone(MODULE.CLOSED_FORM.search("sparse exact-recipe confirmation"))

    def test_a_hidden_truth_is_not_a_closed_form_anchor(self):
        """Every discovery task has a truth; that is not the same as a reachable reference."""
        self.assertIsNone(MODULE.CLOSED_FORM.search("exact hidden graph and structural coefficients"))
        self.assertIsNone(MODULE.CLOSED_FORM.search("exact simulator peak parameters"))


class ApplicabilityTests(unittest.TestCase):
    def test_the_discovery_axis_check_does_not_apply_to_optimization_tasks(self):
        class Spec:
            task_dir = Path("/nonexistent")
            metadata = {"scientific_role": "optimization", "score_mode": "uncapped"}

        self.assertIsNone(MODULE.check(Spec(), {})["discovery_axes"])

    def test_an_undeclared_role_fails_role_declared(self):
        class Spec:
            task_dir = Path("/nonexistent")
            metadata = {"scientific_role": "", "score_mode": "clipped"}

        self.assertFalse(MODULE.check(Spec(), {})["role_declared"])


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import contextlib
        import io
        import json
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "theme.json"
            with contextlib.redirect_stdout(io.StringIO()):
                MODULE.main(["--output", str(target)])
            cls.report = json.loads(target.read_text(encoding="utf-8"))

    def test_every_task_declares_one_of_the_two_forms(self):
        self.assertEqual(
            self.report["met_counts"]["role_declared"],
            self.report["applicable_counts"]["role_declared"],
        )

    def test_the_flagship_tasks_are_not_flagged_as_closed_form(self):
        closed = set(self.report["closed_form_reference"])
        for task in ("QuantumErrorCorrection/QuantumErrorDecoder",
                     "MedicinalChemistry/MolecularLeadOptimization",
                     "RNAEngineering/RNAEnsembleDesign",
                     "Spectroscopy/SpinSystemInference"):
            self.assertNotIn(task, closed)


if __name__ == "__main__":
    unittest.main()
