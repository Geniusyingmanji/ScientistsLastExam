"""A rebinding records what it measured; it must never erase what an earlier one measured.

The overlays that rebind the frozen cohort stack: each writes per-task records and the next one
merges on top. A rebinding that measures nothing writes `None` for the fields it did not measure,
and a naive merge lets that `None` overwrite a real measurement underneath.

That is not a hypothetical. Rebinding the manifest's maturity hash - a change that touched no
evidence at all - dropped six tasks' recorded evaluator-inertness measurements, and the preflight
fell from 7 of 7 to 1 of 7. Nothing about the evidence had changed. Only the record that it had
been checked was gone, and the checks then correctly refused evidence they could no longer excuse.

The failure mode is quiet: the rebinding tool reports success, the spec looks well formed, and the
loss only shows up as unrelated-looking check failures one layer down.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

MEASURED_FIELDS = (
    "evaluator_change_measured_inert",
    "evidence_remeasured_on_current_runtime",
)


def _preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight_for_rebinding_tests",
        ROOT / "scripts" / "run_measurement_health_preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rebinder():
    spec = importlib.util.spec_from_file_location(
        "rebinder_for_rebinding_tests",
        ROOT / "scripts" / "rebind_measurement_health_spec.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RebindingPreservesMeasurementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preflight = _preflight()
        cls.spec_path = Path(cls.preflight.DEFAULT_SPEC)
        cls.spec = json.loads(cls.spec_path.read_text(encoding="utf-8"))

    def _chain(self):
        """Every spec in the supersession chain, newest first."""
        documents, path = [], self.spec_path
        seen = set()
        while path is not None and path not in seen:
            seen.add(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            documents.append((path.name, document))
            candidate = (document.get("supersedes") or {}).get("path")
            path = (ROOT / candidate) if candidate and (ROOT / candidate).is_file() else None
        return documents

    def test_no_measurement_recorded_by_an_earlier_overlay_was_dropped(self):
        chain = self._chain()
        self.assertGreater(len(chain), 1, "expected a supersession chain to check")
        current = {row["task"]: row for row in self.spec.get("task_overrides") or []}
        for name, document in chain[1:]:
            for row in document.get("task_overrides") or []:
                for field in MEASURED_FIELDS:
                    if not row.get(field):
                        continue
                    self.assertTrue(
                        current.get(row["task"], {}).get(field),
                        "%s recorded %s for %s and the current spec no longer has it - a later "
                        "rebinding erased a measurement instead of carrying it forward"
                        % (name, field, row["task"]),
                    )

    def test_every_rebound_task_carries_something_that_justifies_its_binding(self):
        """Either the evaluator change was measured inert, or the evidence was re-measured.

        The count is not the point; having any at all is. A task with neither has had its hashes
        moved forward on no stated grounds, which is the re-signing this whole mechanism exists to
        refuse.
        """
        rows = self.spec.get("task_overrides") or []
        self.assertTrue(rows)
        unexplained = [row["task"] for row in rows
                       if not any(row.get(field) for field in MEASURED_FIELDS)]
        self.assertEqual(
            unexplained, [],
            "these tasks carry neither a measurement nor a re-measurement, so nothing justifies "
            "their binding: %s" % unexplained)

    def test_a_measurement_names_what_it_compared(self):
        """A record saying only "inert" is an assertion. It has to carry the count behind it."""
        for row in self.spec.get("task_overrides") or []:
            measured = row.get("evaluator_change_measured_inert")
            if not measured:
                continue
            self.assertGreater(
                measured.get("metrics_compared", 0), 0,
                "%s claims a measured-inert evaluator change with no metrics behind it"
                % row["task"])
            self.assertTrue(measured.get("files_changed"), row["task"])

    def test_explicit_shared_remeasurement_is_not_ignored_when_hashes_match(self):
        evidence = self.spec["shared_task_overrides"]["exactly_once_recovery"]["evidence"]
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "rebind_measurement_health_spec.py"),
                "--output", str(ROOT / ".research" / "unused_spec.json"),
                "--manifest-output", str(ROOT / ".research" / "unused_manifest.json"),
                "--artifacts-output", str(ROOT / ".research" / "unused_artifacts.json"),
                "--rebind-evidence",
                "exactly_once_recovery=%s" % evidence["path"],
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("%d task(s) rebound" % len(self.spec["task_overrides"]), result.stdout)
        self.assertNotIn("nothing to write", result.stdout)

    def test_dirty_tree_cannot_write_a_successor(self):
        module = _rebinder()
        evidence = self.spec["shared_task_overrides"]["exactly_once_recovery"]["evidence"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = [root / name for name in ("spec.json", "manifest.json", "artifacts.json")]
            with patch.object(module, "tree_is_clean", return_value=False):
                result = module.main([
                    "--output", str(outputs[0]),
                    "--manifest-output", str(outputs[1]),
                    "--artifacts-output", str(outputs[2]),
                    "--rebind-evidence", "exactly_once_recovery=%s" % evidence["path"],
                ])
            self.assertEqual(result, 1)
            self.assertFalse(any(path.exists() for path in outputs))


if __name__ == "__main__":
    unittest.main()
