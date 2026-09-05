"""Pin streaming chat assembly for endpoints that reject a non-stream request.

Tencent Copilot returns 400 `Non-stream chat request is currently not supported`. The
client must send `stream: true` and join `data:` chunks. Usage, when present, is on the
final chunk. Reasoning deltas are ignored: the searcher only consumes visible content.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sle.llm import LLMClient, LLMConfig, _chat_thinking_tokens


SSE = """\
data: {"choices":[{"delta":{"role":"assistant","content":""}}]}

data: {"choices":[{"delta":{"content":"FS"}}]}

data: {"choices":[{"delta":{"content":"_SMOKE_OK"}}], "usage": {"prompt_tokens": 24, "completion_tokens": 6, "total_tokens": 30}}

data: [DONE]
"""


class ChatStreamTests(unittest.TestCase):
    def test_sse_chunks_join_into_the_answer(self):
        text, usage, reasoning, finish_reason = LLMClient._assemble_chat_sse(SSE)
        self.assertEqual(text, "FS_SMOKE_OK")
        self.assertEqual(usage["total_tokens"], 30)
        self.assertEqual(reasoning, "")

    def test_stream_mode_sends_stream_true_and_skips_json_post(self):
        client = LLMClient(LLMConfig(
            wire="chat", base_url="https://copilot.tencent.com/v2",
            api_key="ck-test", model="hy3-ioa", stream=True,
        ))
        with patch.object(LLMClient, "_post_sse", return_value=SSE) as sse, \
                patch.object(LLMClient, "_post") as json_post:
            self.assertEqual(client.complete("Reply with exactly: FS_SMOKE_OK"), "FS_SMOKE_OK")
        self.assertTrue(sse.called)
        json_post.assert_not_called()
        _url, payload, _headers = sse.call_args[0]
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["stream_options"], {"include_usage": True})
        self.assertEqual(client.total_usage["total_tokens"], 30)

    def test_provider_error_event_is_not_returned_as_an_empty_answer(self):
        error_stream = """\
data: {"error":{"message":"provider rejected request"}}

data: [DONE]
"""
        client = LLMClient(LLMConfig(stream=True))
        with patch.object(LLMClient, "_post_sse", return_value=error_stream):
            with self.assertRaises(RuntimeError) as raised:
                client.complete("rewrite the program")
        self.assertIn("provider rejected request", str(raised.exception))

    def test_reasoning_tokens_are_read_from_chat_usage(self):
        usage = {
            "completion_tokens": 8000,
            "completion_tokens_details": {"reasoning_tokens": 8000},
            "completion_thinking_tokens": 8000,
        }
        self.assertEqual(_chat_thinking_tokens(usage), 8000)

    def test_a_thinking_only_chat_stream_is_an_error_not_an_empty_answer(self):
        """hy3-ioa spent 8000 tokens on reasoning_content and returned no
        visible fence. That must not reach the searcher as `no_code`."""
        thinking_only = """\
data: {"choices":[{"delta":{"role":"assistant","content":"","reasoning_content":"plan"}}]}

data: {"choices":[{"delta":{"content":"","reasoning_content":"..."},"finish_reason":"length"}], "usage": {"prompt_tokens": 2000, "completion_tokens": 8000, "completion_tokens_details": {"reasoning_tokens": 8000}, "total_tokens": 10000}}

data: [DONE]
"""
        client = LLMClient(LLMConfig(
            wire="chat", base_url="https://copilot.tencent.com/v2",
            api_key="ck-test", model="hy3-ioa", stream=True,
        ))
        with patch.object(LLMClient, "_post_sse", return_value=thinking_only):
            with self.assertRaises(RuntimeError) as raised:
                client.complete("rewrite the program")
        self.assertIn("no visible chat content", str(raised.exception))
        self.assertIn("8000", str(raised.exception))

    def test_reasoning_fallback_returns_the_scratchpad_when_asked(self):
        thinking_only = """\
data: {"choices":[{"delta":{"content":"","reasoning_content":"```python\\ndef f():\\n    return 1\\n```"}}]}

data: {"choices":[{"delta":{"content":""},"finish_reason":"length"}], "usage": {"prompt_tokens": 10, "completion_tokens": 40, "completion_tokens_details": {"reasoning_tokens": 40}, "total_tokens": 50}}

data: [DONE]
"""
        client = LLMClient(LLMConfig(
            wire="chat", base_url="https://copilot.tencent.com/v2",
            api_key="ck-test", model="hy3-ioa", stream=True,
            chat_reasoning_fallback=True,
        ))
        with patch.object(LLMClient, "_post_sse", return_value=thinking_only):
            text = client.complete("rewrite the program")
        self.assertIn("def f()", text)


if __name__ == "__main__":
    unittest.main()
