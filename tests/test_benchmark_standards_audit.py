"""Pin the standards audit's rules, including the two it originally got wrong.

Both original defects pointed the same way — they made the inventory look more mature than it is:

  * `domain_reviewed` excluded the exact string "pending_external" but not
    "pending_external_photovoltaics", so 17 tasks that have never been reviewed were counted as
    reviewed and the audit reported 28% where the truth is 0%;
  * an earlier dependency scan matched package names as substrings, so every evaluator appeared to
    use ASE because the letters occur in "case", "base" and "database". This audit parses imports
    instead, and that has to stay true.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "audit_benchmark_standards.py"
    spec = importlib.util.spec_from_file_location("standards_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class ImportDetectionTests(unittest.TestCase):
    def test_a_package_name_appearing_inside_a_word_is_not_an_import(self):
        source = """
def f(case, base, database):
    return case + base + database
"""
        self.assertEqual(MODULE.imported_modules(source) & MODULE.COMMUNITY_PACKAGES, set())

    def test_plain_and_from_imports_are_both_found(self):
        source = "import stim\nfrom rdkit import Chem\n"
        found = MODULE.imported_modules(source)
        self.assertIn("stim", found)
        self.assertIn("rdkit", found)

    def test_a_deferred_import_inside_a_function_still_counts(self):
        """Every oracle here imports its toolkit lazily, so a top-level-only scan would see none."""
        source = "def _rna():\n    import RNA\n    return RNA\n"
        self.assertIn("RNA", MODULE.imported_modules(source))

    def test_dynamic_imports_are_found(self):
        source = 'import importlib\nm = importlib.import_module("pyscf")\n'
        self.assertIn("pyscf", MODULE.imported_modules(source))

    def test_a_relative_import_is_not_read_as_a_toolkit(self):
        source = "from . import rdkit_helpers\n"
        self.assertEqual(MODULE.imported_modules(source) & MODULE.COMMUNITY_PACKAGES, set())

    def test_unparseable_source_yields_nothing_rather_than_raising(self):
        self.assertEqual(MODULE.imported_modules("def broken(:\n"), set())


class DomainReviewTests(unittest.TestCase):
    def test_a_pending_value_with_a_field_appended_is_still_pending(self):
        with TemporaryDirectory() as tmp:
            result = MODULE.check(Path(tmp), {
                "review": {"domain": "pending_external_photovoltaics"}})
            self.assertFalse(result["domain_reviewed"])

    def test_bare_pending_is_pending(self):
        with TemporaryDirectory() as tmp:
            result = MODULE.check(Path(tmp), {"review": {"domain": "pending_external"}})
            self.assertFalse(result["domain_reviewed"])

    def test_an_empty_or_missing_value_is_not_review(self):
        with TemporaryDirectory() as tmp:
            self.assertFalse(MODULE.check(Path(tmp), {})["domain_reviewed"])
            self.assertFalse(
                MODULE.check(Path(tmp), {"review": {"domain": "  "}})["domain_reviewed"])

    def test_a_named_reviewer_counts(self):
        with TemporaryDirectory() as tmp:
            result = MODULE.check(Path(tmp), {
                "review": {"domain": "reviewed 2026-08 by an external RNA thermodynamics group"}})
            self.assertTrue(result["domain_reviewed"])


class InventoryTests(unittest.TestCase):
    """The audit's own claims about this repository, which are load-bearing in the README."""

    @classmethod
    def setUpClass(cls):
        import json
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "standards.json"
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):
                MODULE.main(["--output", str(target)])
            cls.report = json.loads(target.read_text(encoding="utf-8"))

    def test_nothing_is_externally_reviewed_yet(self):
        self.assertEqual(self.report["met_counts"]["domain_reviewed"], 0)

    def test_the_community_oracle_tasks_are_the_ones_claimed(self):
        """Named rather than counted: a task added without its toolkit on the list reads as an
        author reimplementation, which is how SpinSystemInference first appeared here."""
        community = {
            row["task"] for row in self.report["rows"]
            if row["standards"]["oracle_is_community"]
        }
        self.assertEqual(community, {
            "QuantumErrorCorrection/QuantumErrorDecoder",
            "MedicinalChemistry/MolecularLeadOptimization",
            "RNAEngineering/RNAEnsembleDesign",
            "Spectroscopy/SpinSystemInference",
            "Algorithm/GraphFromDistances",
            "Mathematics/SequenceLawRecovery",
            "QuantumDynamics/HamiltonianLearning",
            "WavePropagation/ActiveFullWaveformInversion",
            "Paleoclimate/ChronologyAssimilation",
            "Hydrology/GroundwaterRemediationDesign",
            "Cryosphere/IceObservationNetworkDesign",
        })

    def test_a_toolkit_used_only_by_a_reference_does_not_make_the_oracle_community(self):
        """The standard is about the oracle, and a reference is not the oracle.

        `RadialVelocityPlanets` ships a reference detector built on astropy's Lomb-Scargle while
        its evaluator implements the periodogram itself. Counting the directory's imports
        wholesale read that as a community oracle, which inverts what the standard measures: a
        reference is *encouraged* to use the community tool, precisely so the author's oracle can
        be checked against it.
        """
        rows = {row["task"]: row for row in self.report["rows"]}
        self.assertFalse(
            rows["Exoplanets/RadialVelocityPlanets"]["standards"]["oracle_is_community"])

    def test_every_uncapped_task_ships_a_reference_record(self):
        """An uncapped score above 1.0 is a claim about the state of the art."""
        missing = [
            row["task"] for row in self.report["rows"]
            if row["score_mode"] == "uncapped" and not row["standards"]["has_reference_record"]
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
