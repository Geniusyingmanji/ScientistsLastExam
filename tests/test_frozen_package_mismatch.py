"""Classifying why a frozen task package no longer matches its binding.

The frozen cohort went from seven passes to zero and the report could only say "expected X, got
Y". The two causes call for opposite responses - a rewritten evaluator needs the evidence
re-measured, a declarative annotation needs only the binding refreshed - so the difference is
worth naming. Both bugs this logic has already had are pinned here: it read the revision from the
wrong place, and it compared by path across a directory move and declared that every file in
every task had changed.
"""
from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preflight", ROOT / "scripts/run_measurement_health_preflight.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Spec:
    def __init__(self, task_id: str):
        self.task_id = task_id


class FrozenPackageMismatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self._saved_root = MODULE.ROOT
        MODULE.ROOT = self.repo
        self.addCleanup(setattr, MODULE, "ROOT", self._saved_root)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, text=True)

    def write(self, relative, body):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def seed(self, domain="Old"):
        self.write("benchmarks/%s/T/Task.md" % domain, "ask")
        self.write("benchmarks/%s/T/verification/evaluator.py" % domain, "score = 1")
        self.write("benchmarks/%s/T/frontier_eval/metadata.yaml" % domain, "name: T\n")
        return self.commit("seed")

    def classify(self, revision):
        return MODULE._package_mismatch_explanation(Spec("Domain/T"), revision)

    def test_a_declarative_annotation_is_named_as_such(self):
        revision = self.seed()
        self.write("benchmarks/Old/T/frontier_eval/metadata.yaml",
                   "name: T\nscientific_role: optimization\n")
        self.commit("annotate")
        result = self.classify(revision)
        self.assertTrue(result["classified"])
        self.assertTrue(result["declarative_change_only"])
        self.assertEqual(result["behavioural_files_changed"], [])

    def test_moving_the_task_is_not_reported_as_rewriting_it(self):
        """Comparing by path made a directory move look like every file being replaced."""
        revision = self.seed(domain="Old")
        (self.repo / "benchmarks" / "New").mkdir(parents=True, exist_ok=True)
        self.git("mv", "benchmarks/Old/T", "benchmarks/New/T")
        self.commit("move")
        result = self.classify(revision)
        self.assertTrue(result["classified"])
        self.assertTrue(result["declarative_change_only"])
        self.assertEqual(result["behavioural_files_changed"], [])

    def test_an_edited_evaluator_is_reported_as_behavioural(self):
        revision = self.seed()
        self.write("benchmarks/Old/T/verification/evaluator.py", "score = 2")
        self.commit("edit")
        result = self.classify(revision)
        self.assertFalse(result["declarative_change_only"])
        self.assertEqual(result["behavioural_files_changed"], ["verification/evaluator.py"])

    def test_a_non_declarative_card_key_is_behavioural(self):
        """The card is not automatically harmless; only the listed keys are."""
        revision = self.seed()
        self.write("benchmarks/Old/T/frontier_eval/metadata.yaml",
                   "name: T\nevaluation_timeout_seconds: 900\n")
        self.commit("retime")
        self.assertFalse(self.classify(revision)["declarative_change_only"])

    def test_a_reference_the_evaluator_never_names_is_not_behavioural(self):
        """Documenting a task's anchor must not invalidate the evidence the anchor explains."""
        revision = self.seed()
        self.write("benchmarks/Old/T/verification/reference_thing.py", "def solve(): return 1")
        self.commit("add a reference")
        result = self.classify(revision)
        self.assertTrue(result["classified"])
        self.assertTrue(result["declarative_change_only"])
        self.assertEqual(result["behavioural_files_changed"], [])

    def test_a_reference_the_evaluator_does_import_is_behavioural(self):
        revision = self.seed()
        self.write("benchmarks/Old/T/verification/reference_thing.py", "def solve(): return 1")
        self.write("benchmarks/Old/T/verification/evaluator.py",
                   "import reference_thing\nscore = 1")
        self.commit("add a reference the evaluator uses")
        result = self.classify(revision)
        self.assertFalse(result["declarative_change_only"])

    def test_a_missing_revision_is_reported_not_guessed(self):
        self.seed()
        self.assertFalse(self.classify(None)["classified"])
        self.assertFalse(self.classify("")["classified"])


if __name__ == "__main__":
    unittest.main()
