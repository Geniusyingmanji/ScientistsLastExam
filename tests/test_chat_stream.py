"""Pin streaming chat assembly for endpoints that reject a non-stream request.

Tencent Copilot returns 400 `Non-stream chat request is currently not supported`. The
client must send `stream: true` and join `data:` chunks. Usage, when present, is on the
final chunk. Reasoning deltas are ignored: the searcher only consumes visible content.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sle.llm import LLMClient, LLMConfig


SSE = """\
data: {"choices":[{"delta":{"role":"assistant","content":""}}]}

data: {"choices":[{"delta":{"content":"FS"}}]}

data: {"choices":[{"delta":{"content":"_SMOKE_OK"}}], "usage": {"prompt_tokens": 24, "completion_tokens": 6, "total_tokens": 30}}

data: [DONE]
"""


class ChatStreamTests(unittest.TestCase):
    def test_sse_chunks_join_into_the_answer(self):
        text, usage = LLMClient._assemble_chat_sse(SSE)
        self.assertEqual(text, "FS_SMOKE_OK")
        self.assertEqual(usage["total_tokens"], 30)

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
        self.assertEqual(client.total_usage["total_tokens"], 30)


if __name__ == "__main__":
    unittest.main()
