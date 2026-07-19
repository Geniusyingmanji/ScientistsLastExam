"""LLM client for Frontier-Science.

Supports two wire formats behind one interface:

- ``chat``      : OpenAI-compatible ``POST {base_url}/chat/completions``.
                  This is the public, vendor-neutral path (base_url + api_key + model).
- ``responses`` : OpenAI ``POST {base_url}/responses`` (Responses API). Used by our
                  local keyless proxy, which injects auth itself — selected only via a
                  git-ignored local config.

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
        return os.environ.get(value[2:-1], "")
    return value


@dataclass
class LLMConfig:
    wire: str = "chat"  # "chat" | "responses"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    max_output_tokens: int = 8000
    temperature: Optional[float] = 0.7
    reasoning_effort: Optional[str] = None  # for reasoning models on the responses wire
    timeout_seconds: float = 600.0
    extra_headers: dict = field(default_factory=dict)
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "LLMConfig":
        d = {k: _expand(v) for k, v in (d or {}).items()}
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.last_usage: dict[str, Any] = {}
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
        if self.config.wire == "responses":
            return self._complete_responses(prompt, system)
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
            "max_tokens": int(self.config.max_output_tokens),
        }
        if self.config.temperature is not None:
            payload["temperature"] = float(self.config.temperature)
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.extra_headers)
        data = self._post(url, payload, headers)
        self._record_usage(data.get("usage") or {})
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
        return self._extract_responses_text(data)

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
