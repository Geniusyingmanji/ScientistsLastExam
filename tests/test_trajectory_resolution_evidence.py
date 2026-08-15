"""The trajectory packager exists to bind a re-measurement, so it has to refuse a stale run.

Re-measuring evidence is the repair for an evaluator change that was not measurably inert. That
repair is worth nothing if a run made against the *old* task can be packaged and presented as
evidence about the new one - it would launder exactly the staleness it was meant to fix. These
tests pin that refusal, and pin that a packaged run carries the hashes it was bound to.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "trajectory_evidence", ROOT / "scripts" / "build_trajectory_resolution_evidence.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from sle.algorithms.common import task_contract_sha256, task_package_sha256  # noqa: E402
from sle.registry import find_task  # noqa: E402

TASK = "Optics/DiffractionGratingDesign"


def _run_directory(root: Path, manifest: dict, events: list[dict]) -> Path:
    run = root / "run"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "trajectory.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    return run


class TrajectoryResolutionEvidenceTests(unittest.TestCase):
    def setUp(self):
        spec = find_task(TASK, include_uncertified=True)
        self.current = {
            "task_id": TASK,
            "task_package_sha256": task_package_sha256(spec),
            "task_contract_sha256": task_contract_sha256(spec),
            "seed": 1,
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
        }
        self.events = [
            {"step": 0, "score": 0.10, "valid": True},
            {"step": 1, "score": 0.35, "valid": True},
            {"step": 2, "score": 0.35, "valid": True},
            {"step": 3, "score": 0.20, "valid": False},
        ]

    def test_a_run_against_a_different_package_is_refused(self):
        stale = dict(self.current, task_package_sha256="0" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, stale, self.events)
            output = root / "out.json"
            with self.assertRaises(SystemExit) as raised:
                builder.main(["--run", str(run), "--output", str(output)])
            # Refusing has to mean writing nothing: a half-written evidence file is worse than
            # none, because the next reader binds to it.
            self.assertFalse(output.exists())
        message = str(raised.exception)
        self.assertIn("different task", message)
        self.assertIn("task_package_sha256", message)

    def test_a_run_against_a_different_contract_is_refused(self):
        stale = dict(self.current, task_contract_sha256="1" * 64)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, stale, self.events)
            with self.assertRaises(SystemExit) as raised:
                builder.main(["--run", str(run), "--output", str(root / "out.json")])
        self.assertIn("task_contract_sha256", str(raised.exception))

    def test_a_current_run_is_packaged_with_the_hashes_it_is_bound_to(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, dict(self.current), self.events)
            output = root / "out.json"
            self.assertEqual(builder.main(["--run", str(run), "--output", str(output)]), 0)
            document = json.loads(output.read_text(encoding="utf-8"))
        row = document["runs"][0]
        self.assertEqual(row["task"], TASK)
        self.assertEqual(row["task_package_sha256"], self.current["task_package_sha256"])
        self.assertEqual(row["task_contract_sha256"], self.current["task_contract_sha256"])
        self.assertEqual(len(row["trajectory_snapshot"]["events"]), len(self.events))

    def test_only_valid_steps_set_the_resolved_gap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, dict(self.current), self.events)
            output = root / "out.json"
            builder.main(["--run", str(run), "--output", str(output)])
            document = json.loads(output.read_text(encoding="utf-8"))
        # 0.20 came from an invalid step and 0.35 repeats, so the only resolved gap is 0.10 -> 0.35.
        self.assertEqual(document["aggregate"]["distinct_valid_scores"], [0.10, 0.35])
        self.assertAlmostEqual(document["aggregate"]["minimum_nonzero_score_gap"], 0.25)

    def test_a_run_that_never_moved_is_recorded_untrusted_rather_than_silently_written(self):
        flat = [{"step": 0, "score": 0.5, "valid": True}, {"step": 1, "score": 0.5, "valid": True}]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, dict(self.current), flat)
            output = root / "out.json"
            builder.main(["--run", str(run), "--output", str(output)])
            document = json.loads(output.read_text(encoding="utf-8"))
        self.assertIsNone(document["aggregate"]["minimum_nonzero_score_gap"])
        self.assertIsNot(document.get("trusted_evidence"), True)

    def test_an_unfinished_run_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _run_directory(root, dict(self.current), self.events)
            (run / "run_manifest.json").unlink()
            with self.assertRaises(SystemExit) as raised:
                builder.main(["--run", str(run), "--output", str(root / "out.json")])
        self.assertIn("did not finish", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
