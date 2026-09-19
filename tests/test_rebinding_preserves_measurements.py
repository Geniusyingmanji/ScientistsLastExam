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
import contextlib
import io
from types import SimpleNamespace
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

    @contextlib.contextmanager
    def _isolated_current_binding(self):
        """Exercise the writer against one unchanged test binding, not a live cohort."""
        module = _rebinder()
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            root = Path(temporary)
            spec_path = root / "spec.json"
            manifest_path = root / "manifest.json"
            spec_path.write_text("{}")
            row = {"task": "Fixture/Task", "task_package_sha256": "a" * 64}
            manifest_path.write_text(json.dumps({"tasks": [{
                "task": "Fixture/Task", "runtime_contract_sha256": "b" * 64,
                "maturity_contract_sha256": "c" * 64,
            }]}))
            stack.enter_context(patch.object(module._module, "_resolve_preflight_spec",
                                            return_value=({"tasks": [row]}, [], [])))
            stack.enter_context(patch.object(module, "find_task", return_value=SimpleNamespace()))
            stack.enter_context(patch.object(module, "task_package_sha256", return_value="a" * 64))
            stack.enter_context(patch.object(module, "task_contract_sha256", return_value="b" * 64))
            stack.enter_context(patch.object(module, "_maturity_contract_sha256", return_value="c" * 64))
            outputs = [root / name for name in ("successor.json", "next_manifest.json", "artifacts.json")]
            argv = ["--spec", str(spec_path), "--manifest", str(manifest_path),
                    "--output", str(outputs[0]), "--manifest-output", str(outputs[1]),
                    "--artifacts-output", str(outputs[2]),
                    "--rebind-evidence", "exactly_once_recovery=fixture-evidence.json"]
            yield module, argv, outputs

    def test_explicit_shared_remeasurement_is_not_ignored_when_hashes_match(self):
        with self._isolated_current_binding() as (module, argv, outputs):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = module.main(argv + ["--dry-run"])
            self.assertEqual(result, 0)
            self.assertIn("1 task(s) rebound", output.getvalue())
            self.assertNotIn("nothing to write", output.getvalue())
            self.assertFalse(any(path.exists() for path in outputs))

    def test_dirty_tree_cannot_write_a_successor(self):
        with self._isolated_current_binding() as (module, argv, outputs):
            with patch.object(module, "tree_is_clean", return_value=False):
                result = module.main(argv)
            self.assertEqual(result, 1)
            self.assertFalse(any(path.exists() for path in outputs))


if __name__ == "__main__":
    unittest.main()
