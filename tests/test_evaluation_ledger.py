from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from frontier_science.evaluation_ledger import EvaluationLedger, RunLease


class EvaluationLedgerTests(unittest.TestCase):
    def test_completed_receipt_is_reused_without_another_evaluator_call(self):
        calls = {"count": 0}

        def evaluator():
            calls["count"] += 1
            return {"combined_score": 0.7, "valid": 1.0, "sealed": 0.4}

        request = {
            "kind": "proposal", "task_id": "T/X", "step": 1,
            "candidate_sha256": "a" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            ledger = EvaluationLedger(Path(temporary))
            first = ledger.evaluate_once(request, evaluator)
            second = EvaluationLedger(Path(temporary)).evaluate_once(
                request,
                lambda: (_ for _ in ()).throw(AssertionError("called twice")),
            )
            snapshot = ledger.snapshot()

        self.assertEqual(calls["count"], 1)
        self.assertFalse(first["receipt_reused"])
        self.assertTrue(second["receipt_reused"])
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertEqual(snapshot["request_count"], 1)
        self.assertEqual(snapshot["receipt_count"], 1)
        self.assertEqual(snapshot["attempt_count"], 1)
        self.assertEqual(snapshot["open_request_ids"], [])

    def test_infrastructure_failure_has_no_receipt_and_same_request_can_retry(self):
        request = {
            "kind": "proposal", "task_id": "T/X", "step": 1,
            "candidate_sha256": "b" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            ledger = EvaluationLedger(Path(temporary))
            failed = ledger.evaluate_once(
                request,
                lambda: {
                    "combined_score": -1e18, "valid": 0.0,
                    "infrastructure_failure": 1.0,
                },
            )
            recovered = ledger.evaluate_once(
                request, lambda: {"combined_score": 0.8, "valid": 1.0}
            )
            snapshot = ledger.snapshot()

        self.assertFalse(failed["receipt_committed"])
        self.assertTrue(recovered["receipt_committed"])
        self.assertEqual(snapshot["request_count"], 1)
        self.assertEqual(snapshot["receipt_count"], 1)
        self.assertEqual(snapshot["attempt_count"], 2)
        self.assertEqual(snapshot["infrastructure_failure_attempt_count"], 1)

    def test_interrupted_attempt_is_retained_and_logical_request_stays_unique(self):
        request = {
            "kind": "proposal", "task_id": "T/X", "step": 1,
            "candidate_sha256": "c" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            ledger = EvaluationLedger(Path(temporary))
            prepared = ledger.prepare(request)
            attempt_index, _attempt = ledger._start_attempt(prepared["request_id"])
            self.assertEqual(attempt_index, 1)
            recovered = EvaluationLedger(Path(temporary)).evaluate_once(
                request, lambda: {"combined_score": 0.9, "valid": 1.0}
            )
            snapshot = ledger.snapshot()

        self.assertEqual(recovered["attempt_index"], 2)
        self.assertEqual(snapshot["request_count"], 1)
        self.assertEqual(snapshot["receipt_count"], 1)
        self.assertEqual(snapshot["attempt_count"], 2)
        self.assertEqual(snapshot["incomplete_attempt_count"], 1)

    def test_receipt_commit_survives_crash_before_attempt_completion(self):
        request = {
            "kind": "proposal", "task_id": "T/X", "step": 1,
            "candidate_sha256": "e" * 64,
        }
        calls = {"count": 0}

        def evaluator():
            calls["count"] += 1
            return {"combined_score": 0.6, "valid": 1.0}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = EvaluationLedger(root)
            real_finish = ledger._finish_attempt

            def crash(attempt, *, wall_seconds, outcome):
                if outcome == "receipt_committed":
                    raise RuntimeError("crash before attempt completion")
                return real_finish(
                    attempt, wall_seconds=wall_seconds, outcome=outcome
                )

            ledger._finish_attempt = crash
            with self.assertRaisesRegex(RuntimeError, "attempt completion"):
                ledger.evaluate_once(request, evaluator)
            self.assertEqual(calls["count"], 1)
            recovered = EvaluationLedger(root).evaluate_once(
                request,
                lambda: (_ for _ in ()).throw(AssertionError("called twice")),
            )
            snapshot = EvaluationLedger(root).snapshot()

        self.assertTrue(recovered["receipt_reused"])
        self.assertEqual(calls["count"], 1)
        self.assertEqual(snapshot["request_count"], 1)
        self.assertEqual(snapshot["receipt_count"], 1)
        self.assertEqual(snapshot["incomplete_attempt_count"], 1)

    def test_tampered_receipt_is_rejected(self):
        request = {
            "kind": "proposal", "task_id": "T/X", "step": 1,
            "candidate_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = EvaluationLedger(root)
            result = ledger.evaluate_once(
                request, lambda: {"combined_score": 0.5, "valid": 1.0}
            )
            path = root / "evaluation_ledger/receipts" / (result["request_id"] + ".json")
            receipt = json.loads(path.read_text(encoding="utf-8"))
            receipt["metrics"]["combined_score"] = 1.0
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "receipt content binding"):
                EvaluationLedger(root).evaluate_once(request, lambda: {})

    def test_run_lease_rejects_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary) / "run"
            with RunLease(workdir):
                with self.assertRaisesRegex(RuntimeError, "already leased"):
                    with RunLease(workdir):
                        pass
            with RunLease(workdir):
                pass


if __name__ == "__main__":
    unittest.main()
