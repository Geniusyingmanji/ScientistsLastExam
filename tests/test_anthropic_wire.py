"""Pin the Anthropic wire, which differs from the OpenAI ones in four ways that all bite.

The key travels in `x-api-key` rather than a bearer token; the API version is a required header;
`system` is a top-level field rather than a message; and the reply is a list of content blocks of
which only the `text` ones are the answer. Getting any of them wrong fails at request time or,
worse, returns an empty string that looks like a model declining to answer.

Token accounting is pinned too. Anthropic reports `input_tokens` / `output_tokens` where OpenAI
reports `prompt_tokens` / `completion_tokens`, so an unmapped usage payload records zero cost for
every Claude run and makes a cross-model comparison look free on one side.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sle.llm import LLMClient, LLMConfig


def client(**overrides):
    base = dict(wire="anthropic", base_url="https://api.anthropic.com/v1",
                api_key="sk-ant-test", model="claude-opus-4-8", max_output_tokens=4096,
                temperature=None)
    base.update(overrides)
    return LLMClient(LLMConfig(**base))


REPLY = {
    "content": [{"type": "text", "text": "hello"}],
    "usage": {"input_tokens": 11, "output_tokens": 7},
}


class AnthropicWireTests(unittest.TestCase):
    def test_request_shape_and_auth_header(self):
        with patch.object(LLMClient, "_post", return_value=REPLY) as post:
            self.assertEqual(client().complete("q", system="s"), "hello")
        url, payload, headers = post.call_args[0]
        self.assertTrue(url.endswith("/messages"))
        self.assertEqual(headers["x-api-key"], "sk-ant-test")
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(payload["system"], "s")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "q"}])
        self.assertEqual(payload["max_tokens"], 4096)

    def test_only_text_blocks_become_the_answer(self):
        reply = {"content": [{"type": "thinking", "thinking": "internal"},
                             {"type": "text", "text": "visible"}],
                 "usage": {"input_tokens": 1, "output_tokens": 1}}
        with patch.object(LLMClient, "_post", return_value=reply):
            self.assertEqual(client().complete("q"), "visible")

    def test_usage_is_mapped_from_anthropic_names(self):
        c = client()
        with patch.object(LLMClient, "_post", return_value=REPLY):
            c.complete("q")
        self.assertEqual(c.total_usage["input_tokens"], 11)
        self.assertEqual(c.total_usage["output_tokens"], 7)
        self.assertEqual(c.total_usage["total_tokens"], 18)

    def test_thinking_is_off_unless_asked_for(self):
        """And is *said* to be off, because omitting the field does not turn it off.

        This asserted that no `thinking` key was sent, on the reading that a field left out is a
        feature left off. For a model that reasons by default it is not. Measured against Opus 5
        with the field omitted: 8000 of 8000 output tokens were thinking tokens, the reply carried
        a single `thinking` block and no `text` block, and the searcher recorded `no_code` on
        every proposal - a result that reads as a model unable to write a program. With
        `{"type": "disabled"}` sent, the same prompt returned a complete program in 4996 tokens.
        """
        with patch.object(LLMClient, "_post", return_value=REPLY) as post:
            client().complete("q")
        self.assertEqual(post.call_args[0][1]["thinking"], {"type": "disabled"})

    def test_a_thinking_only_reply_is_an_error_not_an_empty_answer(self):
        """The two are indistinguishable downstream, and only one is the model's fault."""
        thinking_only = {
            "content": [{"type": "thinking", "thinking": "...", "signature": "x"}],
            "usage": {"input_tokens": 11, "output_tokens": 8000,
                      "output_tokens_details": {"thinking_tokens": 8000}},
            "stop_reason": "max_tokens",
        }
        with patch.object(LLMClient, "_post", return_value=thinking_only):
            with self.assertRaises(RuntimeError) as caught:
                client().complete("q")
        message = str(caught.exception)
        self.assertIn("thinking", message)
        self.assertIn("8000", message)

    def test_thinking_replaces_temperature_when_enabled(self):
        with patch.object(LLMClient, "_post", return_value=REPLY) as post:
            client(thinking_budget_tokens=2000, temperature=0.7).complete("q")
        payload = post.call_args[0][1]
        self.assertEqual(payload["thinking"], {"type": "enabled", "budget_tokens": 2000})
        self.assertNotIn("temperature", payload)

    def test_a_thinking_budget_above_max_tokens_is_refused_before_the_call(self):
        """Anthropic rejects it server-side; failing here says which field is wrong."""
        with self.assertRaises(ValueError):
            client(thinking_budget_tokens=8000, max_output_tokens=4096).complete("q")

    def test_the_wire_is_recorded_in_the_run_condition(self):
        from sle.algorithms.common import llm_condition_descriptor

        descriptor = llm_condition_descriptor(client())
        self.assertEqual(descriptor["wire"], "anthropic")
        self.assertEqual(descriptor["model"], "claude-opus-4-8")


if __name__ == "__main__":
    unittest.main()
