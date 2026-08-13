from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sle.sentinels import SentinelLedger, load_sentinel_events


class SentinelLedgerTests(unittest.TestCase):
    def test_boundary_ledger_is_content_addressed_and_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            ledger = SentinelLedger(workdir)
            baseline = "def solve():\n    return 0\n"
            candidate = "def solve():\n    return 1\n"
            first = ledger.capture(
                "t0",
                source=baseline,
                source_step=0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=0.2,
                selection_policy="baseline",
                evaluation={"combined_score": 0.0, "valid": 1.0},
                evaluation_status="completed",
                evaluation_completed_elapsed_seconds=0.2,
                feedback_visible=True,
            )
            ledger.capture(
                "submission",
                source=candidate,
                source_step=1,
                artifact_published_elapsed_seconds=1.0,
                recorded_elapsed_seconds=1.0,
                selection_policy="agent_submission",
                idempotency_key="submission:1",
                metadata={"decision": "continue"},
            )
            duplicate = ledger.capture(
                "submission",
                source=candidate,
                source_step=1,
                artifact_published_elapsed_seconds=1.0,
                recorded_elapsed_seconds=1.1,
                selection_policy="agent_submission",
                idempotency_key="submission:1",
                metadata={"decision": "continue"},
            )
            self.assertEqual(duplicate["sequence"], 1)
            ledger.capture(
                "first_valid",
                source=candidate,
                source_step=1,
                artifact_published_elapsed_seconds=1.0,
                recorded_elapsed_seconds=1.4,
                selection_policy="first_valid",
                evaluation={"combined_score": 0.7, "valid": 1.0},
                evaluation_status="completed",
                evaluation_completed_elapsed_seconds=1.4,
                feedback_visible=True,
            )
            ledger.capture(
                "terminal",
                source=candidate,
                source_step=1,
                scheduled_elapsed_seconds=2.0,
                artifact_published_elapsed_seconds=1.0,
                recorded_elapsed_seconds=2.1,
                selection_policy="terminal_workspace_artifact",
                evaluation={"combined_score": 0.7, "valid": 1.0},
                evaluation_status="reused_deterministic",
                evaluation_completed_elapsed_seconds=1.4,
                feedback_visible=False,
            )
            snapshot = ledger.snapshot()

            self.assertEqual(snapshot["event_count"], 4)
            self.assertTrue(snapshot["has_terminal"])
            self.assertEqual(snapshot["type_counts"]["submission"], 1)
            self.assertEqual(first["artifact_utf8_bytes"], len(baseline.encode()))
            self.assertEqual(len(first["artifact_sha256"]), 64)
            self.assertEqual(
                len(list((workdir / "sentinels/artifacts").glob("*/candidate.py"))),
                2,
            )
            self.assertEqual(
                load_sentinel_events(
                    workdir / "sentinels/sentinel_events.jsonl",
                    workdir=workdir,
                ),
                ledger.events,
            )

    def test_terminal_artifact_must_have_been_published_by_cutoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = SentinelLedger(Path(temporary))
            ledger.capture(
                "t0", source="x", source_step=0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=0.0,
                selection_policy="baseline",
            )
            with self.assertRaisesRegex(ValueError, "published after"):
                ledger.capture(
                    "terminal", source="late", source_step=1,
                    scheduled_elapsed_seconds=2.0,
                    artifact_published_elapsed_seconds=2.2,
                    recorded_elapsed_seconds=2.2,
                    selection_policy="terminal_workspace_artifact",
                )

    def test_resume_validates_hashes_and_terminal_is_final(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            ledger = SentinelLedger(workdir)
            event = ledger.capture(
                "t0", source="baseline", source_step=0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=0.0,
                selection_policy="baseline",
                idempotency_key="t0",
            )
            resumed = SentinelLedger(workdir, resume=True)
            self.assertEqual(resumed.events, ledger.events)
            resumed.capture(
                "terminal", source="baseline", source_step=0,
                scheduled_elapsed_seconds=1.0,
                artifact_published_elapsed_seconds=0.0,
                recorded_elapsed_seconds=1.0,
                selection_policy="terminal_workspace_artifact",
            )
            with self.assertRaisesRegex(ValueError, "already has a terminal"):
                resumed.capture(
                    "terminal", source="baseline", source_step=0,
                    scheduled_elapsed_seconds=1.0,
                    artifact_published_elapsed_seconds=0.0,
                    recorded_elapsed_seconds=1.0,
                    selection_policy="terminal_workspace_artifact",
                )

            with self.assertRaisesRegex(ValueError, "different content"):
                ledger.capture(
                    "submission", source="different", source_step=1,
                    artifact_published_elapsed_seconds=0.5,
                    recorded_elapsed_seconds=1.0,
                    selection_policy="agent_submission",
                    idempotency_key="t0",
                )

            artifact = workdir / str(event["artifact_path"])
            artifact.write_text("corrupt", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact hash differs"):
                SentinelLedger(workdir, resume=True)


if __name__ == "__main__":
    unittest.main()
