"""The chat request must send the reasoning condition recorded for the run."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from sle.algorithms.common import llm_condition_descriptor
from sle.llm import LLMClient, LLMConfig


class ChatReasoningEffortTests(unittest.TestCase):
    def _complete(self, **config):
        client = LLMClient(LLMConfig(
            base_url="https://provider.invalid/v1/",
            model="reasoning-test-model", **config,
        ))
        if client.config.stream:
            reply = (
                'data: {"choices":[{"delta":{"content":"answer"},'
                '"finish_reason":"stop"}],"usage":{"prompt_tokens":3,'
                '"completion_tokens":5,"total_tokens":8}}\n\n'
                'data: [DONE]\n'
            ).encode("utf-8")
        else:
            reply = json.dumps({
                "choices": [{"message": {"content": "answer"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5,
                          "total_tokens": 8},
            }).encode("utf-8")
        # Exercise the actual JSON serialization and Request construction; only
        # the network boundary is replaced, so no endpoint or key is needed.
        with patch("urllib.request.urlopen", return_value=io.BytesIO(reply)) as urlopen:
            self.assertEqual(client.complete("question", system="instruction"), "answer")
        urlopen.assert_called_once()
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://provider.invalid/v1/chat/completions")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(client.last_stop_reason, "stop")
        self.assertEqual(client.total_usage["total_tokens"], 8)
        return client, json.loads(request.data.decode("utf-8"))

    def test_configured_reasoning_effort_reaches_json_request(self):
        client, payload = self._complete(
            reasoning_effort="high", temperature=None,
            chat_max_tokens_field="max_completion_tokens", max_output_tokens=16384,
        )
        self.assertEqual(payload, {
            "model": "reasoning-test-model",
            "messages": [{"role": "system", "content": "instruction"},
                         {"role": "user", "content": "question"}],
            "max_completion_tokens": 16384,
            "reasoning_effort": "high",
        })
        self.assertEqual(payload["reasoning_effort"],
                         llm_condition_descriptor(client)["reasoning_effort"])

    def test_configured_reasoning_effort_reaches_stream_request(self):
        _, payload = self._complete(
            reasoning_effort="high", temperature=None, stream=True,
            chat_max_tokens_field="max_completion_tokens", max_output_tokens=16384,
        )
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(payload["max_completion_tokens"], 16384)
        self.assertNotIn("max_tokens", payload)
        self.assertNotIn("temperature", payload)
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["stream_options"], {"include_usage": True})

    def test_unset_effort_is_omitted_without_changing_legacy_chat(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                _, payload = self._complete(stream=stream)
                self.assertNotIn("reasoning_effort", payload)
                self.assertEqual(payload["temperature"], 0.7)
                self.assertEqual(payload["max_tokens"], 8000)

    def test_explicit_none_effort_and_zero_temperature_are_preserved(self):
        _, payload = self._complete(reasoning_effort="none", temperature=0)
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(payload["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
