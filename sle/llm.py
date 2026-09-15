"""LLM client for Frontier-Science.

Supports three wire formats behind one interface:

- ``chat``      : OpenAI-compatible ``POST {base_url}/chat/completions``.
                  This is the public, vendor-neutral path (base_url + api_key + model).
- ``responses`` : OpenAI ``POST {base_url}/responses`` (Responses API). Used by our
                  local keyless proxy, which injects auth itself — selected only via a
                  git-ignored local config.
- ``anthropic`` : Anthropic ``POST {base_url}/messages``. Different enough to need its own
                  path: the key travels in ``x-api-key`` rather than a bearer token, the API
                  version is a required header, ``system`` is a top-level field rather than a
                  message, ``max_tokens`` is mandatory, and the reply is a list of content
                  blocks of which only the ``text`` ones are the answer.

The client is configured from a YAML/dict; see ``conf/llm/openai_compatible.example.yaml``.
No endpoint or credential is hard-coded here.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


def _expand(value: Any) -> Any:
    """Expand ``${ENV_VAR}`` references in strings using os.environ."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        variable = value[2:-1]
        resolved = os.environ.get(variable)
        if not resolved:
            raise ValueError(
                f"required environment variable {variable} is missing or empty"
            )
        return resolved
    return value


def _chat_thinking_tokens(usage: dict) -> int:
    """Reasoning tokens reported on an OpenAI-compatible chat usage object."""
    details = usage.get("completion_tokens_details") or {}
    if isinstance(details, dict):
        for key in ("reasoning_tokens", "thinking_tokens"):
            if key in details and details[key] is not None:
                return int(details[key])
    for key in ("completion_thinking_tokens", "reasoning_tokens"):
        if key in usage and usage[key] is not None:
            return int(usage[key])
    return 0


@dataclass
class LLMConfig:
    wire: str = "chat"  # "chat" | "responses" | "anthropic"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    max_output_tokens: int = 8000
    # Reasoning models on the chat wire reject "max_tokens" and require
    # "max_completion_tokens"; older chat models accept only the former. Declared rather than
    # sniffed so a request body is reproducible from the config alone.
    chat_max_tokens_field: str = "max_tokens"
    temperature: Optional[float] = 0.7
    reasoning_effort: Optional[str] = None  # for reasoning models on the responses wire
    # Anthropic wire only. The API version header is required and pinned rather than defaulted
    # so a recorded run says which contract it spoke.
    anthropic_version: str = "2023-06-01"
    # Extended thinking. Off by default, and sent as such: omitting the field leaves a
    # reasoning-by-default model thinking, which is not the same thing. A comparison across model
    # families has to hold the decoding condition fixed, and turning it on for one side only
    # would compare a reasoning budget rather than a model. When set, Anthropic requires
    # temperature to be unset and max_tokens to exceed the thinking budget.
    thinking_budget_tokens: Optional[int] = None
    timeout_seconds: float = 600.0
    # Tencent Copilot (and some other proxies) reject non-stream chat. Off by default so
    # OpenAI-compatible JSON endpoints keep returning one object.
    stream: bool = False
    extra_headers: dict = field(default_factory=dict)
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    # hy3-ioa puts a long scratchpad on `reasoning_content` and only then writes
    # the visible fence on `content`. Both count against max_output_tokens. Off
    # by default: the searcher is defined as visible content, which is what Wave-1
    # recorded. Turn this on in a git-ignored local.yaml to debug a task whose
    # prompt is long enough that thinking never yields a content token.
    chat_reasoning_fallback: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "LLMConfig":
        d = {k: _expand(v) for k, v in (d or {}).items()}
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.last_usage: dict[str, Any] = {}
        # Why this is recorded separately from the reply text: a reply that carries no code block
        # is charged to the model as `no_code`, and that reading is only true when the model had
        # room to finish. Measured on Mathematics/NonlinearCodeRecords, six of nine Opus 5
        # proposals were 36 KB of coding-theory prose that stop mid-word - the output cap, not a
        # refusal to write a program - and the ledger said nothing that could tell the two apart.
        self.last_stop_reason: Optional[str] = None
        self.total_usage: dict[str, Any] = {
            "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": (
                0.0 if config.input_cost_per_million is not None
                and config.output_cost_per_million is not None else None
            ),
        }

    # ---- public API -----------------------------------------------------
    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        self.last_stop_reason = None
        if self.config.wire == "responses":
            return self._complete_responses(prompt, system)
        if self.config.wire == "anthropic":
            return self._complete_anthropic(prompt, system)
        return self._complete_chat(prompt, system)

    # ---- wire: chat completions ----------------------------------------
    def _complete_chat(self, prompt: str, system: Optional[str]) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            self.config.chat_max_tokens_field: int(self.config.max_output_tokens),
        }
        if self.config.temperature is not None:
            payload["temperature"] = float(self.config.temperature)
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.extra_headers)
        if self.config.stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
            raw = self._post_sse(url, payload, headers)
            text, usage, reasoning, finish_reason = self._assemble_chat_sse(raw)
            self.last_stop_reason = finish_reason
            self._record_usage(usage)
            if (text or "").strip():
                return text
            if self.config.chat_reasoning_fallback and (reasoning or "").strip():
                return reasoning
            thinking = _chat_thinking_tokens(usage)
            output = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
            if thinking or output:
                raise RuntimeError(
                    "LLM returned no visible chat content: %s output tokens "
                    "(%s reasoning, %s reasoning chars). Reasoning deltas are "
                    "ignored unless chat_reasoning_fallback is set; raise "
                    "max_output_tokens so the visible fence can finish."
                    % (output, thinking, len(reasoning or ""))
                )
            return text
        data = self._post(url, payload, headers)
        self._record_usage(data.get("usage") or {})
        choices = data.get("choices") or [{}]
        self.last_stop_reason = choices[0].get("finish_reason")
        return data["choices"][0]["message"]["content"] or ""

    # ---- wire: responses API -------------------------------------------
    def _complete_responses(self, prompt: str, system: Optional[str]) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": prompt,
            "max_output_tokens": int(self.config.max_output_tokens),
        }
        if system:
            payload["instructions"] = system
        if self.config.temperature is not None:
            payload["temperature"] = float(self.config.temperature)
        if self.config.reasoning_effort:
            payload["reasoning"] = {"effort": self.config.reasoning_effort}
        url = self.config.base_url.rstrip("/") + "/responses"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.extra_headers)
        data = self._post(url, payload, headers)
        self._record_usage(data.get("usage") or {})
        incomplete = data.get("incomplete_details") or {}
        self.last_stop_reason = incomplete.get("reason") or data.get("status")
        return self._extract_responses_text(data)

    # ---- wire: anthropic messages ---------------------------------------
    def _complete_anthropic(self, prompt: str, system: Optional[str]) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": int(self.config.max_output_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if self.config.thinking_budget_tokens:
            budget = int(self.config.thinking_budget_tokens)
            if budget >= int(self.config.max_output_tokens):
                raise ValueError(
                    "thinking_budget_tokens (%d) must be below max_output_tokens (%d)"
                    % (budget, self.config.max_output_tokens)
                )
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            # Anthropic rejects a temperature alongside extended thinking.
        else:
            # Stated explicitly, because omitting the field does not mean off. Models that reason
            # by default - Opus 5 among them - spend the whole of `max_tokens` on a thinking block
            # and return no text at all: measured here, 8000 of 8000 output tokens were thinking
            # tokens and the response carried zero text blocks. The searcher then reads `no_code`
            # on every proposal and the run reports a model that cannot write a program, when what
            # happened is that nothing ever asked it to answer. With the field set, the same
            # prompt returns a complete program in 4996 tokens.
            payload["thinking"] = {"type": "disabled"}
            if self.config.temperature is not None:
                payload["temperature"] = float(self.config.temperature)
        url = self.config.base_url.rstrip("/") + "/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.config.anthropic_version,
        }
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        headers.update(self.config.extra_headers)
        data = self._post(url, payload, headers)
        usage = data.get("usage") or {}
        # Anthropic names its token fields differently from OpenAI; map them so the recorded
        # accounting is comparable across wires rather than silently zero.
        self._record_usage({
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": (usage.get("input_tokens", 0) or 0)
                            + (usage.get("output_tokens", 0) or 0),
        })
        self.last_stop_reason = data.get("stop_reason")
        blocks = [b for b in (data.get("content") or []) if isinstance(b, dict)]
        parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        answer = "".join(parts)
        if not answer.strip() and blocks:
            # An empty answer is returned to the searcher as "the model produced no code", which
            # is a statement about the model. When every output token went somewhere other than a
            # text block, that statement is false and the run's conclusion is wrong. Say which it
            # was instead of letting the two look the same.
            kinds = sorted({str(b.get("type")) for b in blocks})
            raise RuntimeError(
                "LLM returned no text: %d output tokens across content blocks %s "
                "(stop_reason=%s). A thinking-only response means extended thinking consumed "
                "max_tokens; set thinking_budget_tokens below max_output_tokens, or leave it "
                "unset so thinking is explicitly disabled."
                % (usage.get("output_tokens", 0), ", ".join(kinds), data.get("stop_reason")))
        return answer

    def _record_usage(self, usage: dict[str, Any]) -> None:
        input_key = "input_tokens" if "input_tokens" in usage else "prompt_tokens"
        output_key = "output_tokens" if "output_tokens" in usage else "completion_tokens"
        input_tokens = int(usage[input_key]) if input_key in usage else None
        output_tokens = int(usage[output_key]) if output_key in usage else None
        if "total_tokens" in usage:
            total_tokens = int(usage["total_tokens"])
        elif input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        else:
            total_tokens = None
        pricing_available = (
            self.config.input_cost_per_million is not None
            and self.config.output_cost_per_million is not None
        )
        estimated_cost = None
        if pricing_available and input_tokens is not None and output_tokens is not None:
            estimated_cost = (
                input_tokens * float(self.config.input_cost_per_million) / 1_000_000
                + output_tokens * float(self.config.output_cost_per_million) / 1_000_000
            )
        self.last_usage = {
            "usage_available": input_tokens is not None and output_tokens is not None,
            "pricing_available": pricing_available,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "total_tokens": total_tokens, "estimated_cost_usd": estimated_cost,
        }
        self.total_usage["calls"] += 1
        for key in ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd"):
            value = self.last_usage[key]
            if self.total_usage[key] is None or value is None:
                self.total_usage[key] = None
            else:
                self.total_usage[key] += value

    @staticmethod
    def _extract_responses_text(data: dict) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct:
            return direct
        chunks: list[str] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content", []) or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        if not chunks and data.get("error"):
            raise RuntimeError(f"LLM error: {data['error']}")
        return "".join(chunks)

    # ---- transport ------------------------------------------------------
    def _post(self, url: str, payload: dict, headers: dict, retries: int = 3) -> dict:
        body = json.dumps(payload).encode("utf-8")
        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - surface after retries
                last_err = exc
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"LLM request failed after {retries} attempts: {last_err}")

    @staticmethod
    def _assemble_chat_sse(raw: str) -> tuple[str, dict, str, str | None]:
        """Join OpenAI-style `data:` chunks. Usage, if present, is on the last chunk.

        Visible `content` and `reasoning_content` are assembled separately. The
        searcher consumes content; reasoning is scratchpad unless the caller opts
        into `chat_reasoning_fallback`.
        """
        parts: list[str] = []
        reasoning_parts: list[str] = []
        usage: dict[str, Any] = {}
        finish_reason: Optional[str] = None
        for line in raw.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(chunk, dict):
                continue
            if "error" in chunk and chunk["error"] is not None:
                error = chunk["error"]
                if isinstance(error, dict):
                    detail = error.get("message") or error.get("code")
                else:
                    detail = str(error)
                raise RuntimeError(
                    "LLM stream error: %s"
                    % str(detail or "provider returned an error event")[:500]
                )
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices or not isinstance(choices[0], dict):
                continue
            if choices[0].get("finish_reason"):
                finish_reason = str(choices[0]["finish_reason"])
            delta = choices[0].get("delta") or {}
            if isinstance(delta, dict):
                piece = delta.get("content")
                if isinstance(piece, str) and piece:
                    parts.append(piece)
                thought = delta.get("reasoning_content")
                if isinstance(thought, str) and thought:
                    reasoning_parts.append(thought)
        return "".join(parts), usage, "".join(reasoning_parts), finish_reason

    def _post_sse(self, url: str, payload: dict, headers: dict, retries: int = 3) -> str:
        body = json.dumps(payload).encode("utf-8")
        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    return resp.read().decode("utf-8")
            except Exception as exc:  # noqa: BLE001 - surface after retries
                last_err = exc
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"LLM stream request failed after {retries} attempts: {last_err}")
