"""A reply with no code block is charged to the model. Pin what makes that charge honest.

Measured on Mathematics/NonlinearCodeRecords: six of nine Opus 5 proposals were 36 KB of
coding-theory prose ending mid-word, and every one was recorded as `no_code` with
`response_truncated: false` - a field that described the retained diagnostic copy, not the
model's reply. Read literally, the run said the model could not write a program. What happened
is that it never reached the point of writing one. These tests hold the two apart.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sle.algorithms.evolve import OUTPUT_CAP_STOP_REASONS, _retain_rejected
from sle.llm import LLMClient, LLMConfig


CAPPED_SSE = """\
data: {"choices":[{"delta":{"content":"Let me think about A(24,10)."}}]}

data: {"choices":[{"delta":{"content":""},"finish_reason":"length"}], "usage": {"prompt_tokens": 10, "completion_tokens": 8000, "total_tokens": 8010}}

data: [DONE]
"""


class StopReasonIsRecordedTests(unittest.TestCase):
    def test_sse_reports_the_finish_reason(self):
        text, usage, _reasoning, finish_reason = LLMClient._assemble_chat_sse(CAPPED_SSE)
        self.assertEqual(text, "Let me think about A(24,10).")
        self.assertEqual(usage["completion_tokens"], 8000)
        self.assertEqual(finish_reason, "length")
        self.assertIn(finish_reason, OUTPUT_CAP_STOP_REASONS)

    def test_anthropic_wire_records_stop_reason(self):
        client = LLMClient(LLMConfig(wire="anthropic", base_url="https://example.invalid",
                                     model="m", api_key="k"))
        response = {"content": [{"type": "text", "text": "prose without a fence"}],
                    "stop_reason": "max_tokens",
                    "usage": {"input_tokens": 10, "output_tokens": 8000}}
        with patch.object(LLMClient, "_post", return_value=response):
            self.assertEqual(client.complete("p"), "prose without a fence")
        self.assertEqual(client.last_stop_reason, "max_tokens")
        self.assertIn(client.last_stop_reason, OUTPUT_CAP_STOP_REASONS)

    def test_a_completed_reply_is_not_an_output_cap(self):
        client = LLMClient(LLMConfig(wire="anthropic", base_url="https://example.invalid",
                                     model="m", api_key="k"))
        response = {"content": [{"type": "text", "text": "done"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 20}}
        with patch.object(LLMClient, "_post", return_value=response):
            client.complete("p")
        self.assertEqual(client.last_stop_reason, "end_turn")
        self.assertNotIn(client.last_stop_reason, OUTPUT_CAP_STOP_REASONS)

    def test_stop_reason_does_not_leak_across_calls(self):
        client = LLMClient(LLMConfig(wire="anthropic", base_url="https://example.invalid",
                                     model="m", api_key="k"))
        capped = {"content": [{"type": "text", "text": "a"}], "stop_reason": "max_tokens",
                  "usage": {"input_tokens": 1, "output_tokens": 1}}
        silent = {"content": [{"type": "text", "text": "b"}],
                  "usage": {"input_tokens": 1, "output_tokens": 1}}
        with patch.object(LLMClient, "_post", return_value=capped):
            client.complete("p")
        with patch.object(LLMClient, "_post", return_value=silent):
            client.complete("p")
        self.assertIsNone(client.last_stop_reason)


class RejectedDiagnosticTests(unittest.TestCase):
    def test_the_rejected_record_names_the_cap_and_the_clip_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            _retain_rejected(
                workdir, 1, "", {"combined_score": -1e18, "valid": 0.0,
                                 "error_message": "no_code"},
                valid=False, response="prose that stops mid-wo",
                parse_status="no_code", stop_reason="max_tokens")
            record = json.loads((workdir / "rejected" / "step_001.json").read_text())
        self.assertEqual(record["parse_status"], "no_code")
        self.assertEqual(record["provider_stop_reason"], "max_tokens")
        # The old name claimed the model's reply was truncated. This one claims only what it
        # measures: whether the copy kept on disk was clipped.
        self.assertFalse(record["retained_reply_truncated"])
        self.assertNotIn("response_truncated", record)
