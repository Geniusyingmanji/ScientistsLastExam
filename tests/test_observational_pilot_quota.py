"""Paid draws survive restarts; uncertain transport failures are not retried."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.run_observational_pilot import (
    MODEL, RecordedClient, claim_slot, previous_transport_problem,
)
from sle.llm import LLMConfig


class ObservationalPilotQuotaTests(unittest.TestCase):
    def test_crashed_slot_cannot_be_reclaimed_and_fourth_draw_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for number in (1, 2, 3):
                claim_slot(directory, number, "frozen-plan")
            with self.assertRaises(FileExistsError):
                claim_slot(directory, 1, "frozen-plan")
            with self.assertRaises(ValueError):
                claim_slot(directory, 4, "frozen-plan")
            self.assertEqual(len(list(directory.glob("*.started.json"))), 3)

    def test_http_error_is_logged_once_without_authorization_and_never_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "transport.jsonl"
            client = RecordedClient(LLMConfig(model=MODEL), path)
            error = HTTPError("https://example.invalid", 403, "denied", {}, None)
            with patch("urllib.request.urlopen", side_effect=error) as transport:
                with self.assertRaises(HTTPError):
                    client._post("https://example.invalid", {"model": MODEL},
                                 {"Authorization": "Bearer secret-test-token"})
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(client.attempts, 1)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records[-1]["http_status"], 403)
            self.assertEqual(records[-1]["usage_if_no_response"], "unknown, not zero")
            self.assertNotIn("secret-test-token", path.read_text())
            self.assertTrue(client.transport_failed)

    def test_restart_blocks_failed_or_interrupted_draw_before_spending_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.assertIsNone(previous_transport_problem(directory))
            claim_slot(directory, 1, "frozen-plan")
            self.assertEqual(previous_transport_problem(directory), "interrupted_slot_requires_review")
            output = directory / "model-01"
            output.mkdir()
            (output / "completed.json").write_text('{}')
            self.assertEqual(previous_transport_problem(directory), "missing_transport_record")
            events = [{"kind": "request_started", "attempt": 1},
                      {"kind": "request_failed", "attempt": 1, "error_type": "TimeoutError"}]
            log = output / "transport.jsonl"
            log.write_text("\n".join(json.dumps(row) for row in events))
            self.assertEqual(previous_transport_problem(directory), "failed_or_unresolved_transport")
            events[1] = {"kind": "response_received", "attempt": 1}
            log.write_text("\n".join(json.dumps(row) for row in events))
            self.assertIsNone(previous_transport_problem(directory))
            (output / "completed.json").write_text('{"status":"model_error"}')
            self.assertEqual(previous_transport_problem(directory), "previous_model_error")

    def test_transport_cannot_spend_a_33rd_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = RecordedClient(LLMConfig(model=MODEL), Path(temporary) / "transport.jsonl")
            client.attempts = 32
            with patch("urllib.request.urlopen") as transport:
                with self.assertRaisesRegex(RuntimeError, "quota"):
                    client._post("https://example.invalid", {"model": MODEL}, {})
            transport.assert_not_called()

    def test_other_provider_model_is_recorded_but_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            from io import BytesIO
            path = Path(temporary) / "transport.jsonl"
            client = RecordedClient(LLMConfig(model=MODEL), path)
            response = BytesIO(json.dumps({"model": "other-model", "usage": {"total_tokens": 7}}).encode())
            with patch("urllib.request.urlopen", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    client._post("https://example.invalid", {"model": MODEL}, {})
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(records[1]["provider_model"], "other-model")
            self.assertEqual(records[1]["usage"]["total_tokens"], 7)


if __name__ == "__main__":
    unittest.main()
