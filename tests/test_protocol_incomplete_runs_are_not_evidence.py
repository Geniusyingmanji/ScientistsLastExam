"""A run in which no proposal was ever valid is not evidence about the searcher.

Two things this repository hit in one day produced exactly such runs and reported them as a model
scoring zero. The Anthropic transport omitted the `thinking` field, so a model that reasons by
default spent every output token on a thinking block and returned no text: nine of nine
proposals read `no_code`. Then a public problem key that read numeric held a sentence, and the
model's `float()` raised inside every candidate before its first oracle call: nine of nine
proposals invalid. Neither run said anything about enzyme kinetics, and both would have entered
the admission report as a flat zero feedback arm - which the criterion reads as "the searcher
never moved", a statement about the model that was not true.

The search loop now marks such a run `protocol_incomplete = no_valid_proposal` in its summary,
the batch aggregator carries the mark, and the admission report's `collect` skips the run. This
pins the last of those, with a run that is otherwise indistinguishable from a real one.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _report():
    spec = importlib.util.spec_from_file_location(
        "report_admission_criterion_test", ROOT / "scripts/report_admission_criterion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(root: Path, name: str, mode: str, seed: int, *, incomplete: str | None) -> None:
    workdir = root / "cohort" / name
    workdir.mkdir(parents=True)
    (workdir / "run_manifest.json").write_text(json.dumps({
        "task_id": "Demo/Task", "feedback_mode": mode, "seed": seed,
        "llm_condition": {"model": "test-model"}, "llm_condition_sha256": "c" * 64,
        "task_package_sha256": "p" * 64, "runtime_source_sha256": "r" * 64,
    }), encoding="utf-8")
    rows = [{"step": 0, "score": 0.0, "valid": True}]
    for step in range(1, 4):
        rows.append({"step": step, "score": 0.0 if incomplete else 0.1 * step,
                     "valid": not incomplete, "error": "no_code" if incomplete else None})
    (workdir / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    summary = {"valid_proposal_count": 0 if incomplete else 3}
    if incomplete:
        summary["protocol_incomplete"] = incomplete
    (workdir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


class ProtocolIncompleteRunsTests(unittest.TestCase):
    def test_a_run_with_no_valid_proposal_is_excluded_from_curves(self):
        report = _report()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _run(root, "normal_s0", "normal", 0, incomplete=None)
            _run(root, "blind_s0", "selection_blind", 0, incomplete=None)
            _run(root, "normal_s1", "normal", 1, incomplete="no_valid_proposal")
            found = report.collect(root)
        self.assertEqual(len(found), 1, found)
        curves = next(iter(found.values()))
        self.assertEqual(sorted(curves["normal"]), [0], "the incomplete seed must not be a curve")
        self.assertEqual(sorted(curves["selection_blind"]), [0])
        self.assertEqual([round(x, 6) for x in curves["normal"][0]], [0.1, 0.2, 0.3])

    def test_a_complete_run_with_the_same_shape_is_kept(self):
        """The skip keys on the summary's own statement, not on a flat curve: a genuinely flat
        run that produced valid proposals is a measurement and stays."""
        report = _report()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _run(root, "normal_s0", "normal", 0, incomplete=None)
            flat = root / "cohort" / "normal_s0"
            rows = [json.loads(l) for l in (flat / "trajectory.jsonl").read_text().splitlines()]
            for row in rows:
                row["score"] = 0.0
            (flat / "trajectory.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            found = report.collect(root)
        self.assertEqual(len(found), 1)
        self.assertEqual(next(iter(found.values()))["normal"][0], [0.0, 0.0, 0.0])

    def test_the_helper_reads_the_reason_and_tolerates_absence(self):
        report = _report()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _run(root, "a", "normal", 0, incomplete="no_valid_proposal")
            _run(root, "b", "normal", 1, incomplete=None)
            self.assertEqual(report._protocol_incomplete(root / "cohort" / "a"), "no_valid_proposal")
            self.assertIsNone(report._protocol_incomplete(root / "cohort" / "b"))
            self.assertIsNone(report._protocol_incomplete(root / "cohort" / "missing"))


if __name__ == "__main__":
    unittest.main()
