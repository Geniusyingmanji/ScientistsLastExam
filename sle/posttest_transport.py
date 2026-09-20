"""Single-attempt transport for the bounded post-test discovery protocol.

One started transport attempt consumes a slot, including an uncertain timeout.
JSON and SSE share the quota; neither can retry or silently reset it. This is an
in-memory client for one episode, not a durable cross-process campaign ledger.
The configured endpoint, model, wire and decoding parameters are unchanged.
"""
from __future__ import annotations

import json
import urllib.request

from .llm import LLMClient


def _strict_json(text):
    def reject_constant(_value):
        raise ValueError("nonfinite response constant")
    return json.loads(text, parse_constant=reject_constant)


def _complete_sse(raw, wire):
    """Validate framing and a wire-specific terminal event before decoding.

    The legacy chat assembler skips malformed frames and accepts an abrupt EOF.
    Canonicalizing complete data events also preserves valid multiline SSE JSON
    when it subsequently reaches that line-oriented assembler.
    """
    data, event, normalized = [], "", []
    terminal = False
    # SSE line endings are CR/LF, not Unicode separators inside JSON strings.
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line in lines + [""]:
        if not line:
            if not data:
                event = ""
                continue
            payload = "\n".join(data)
            if terminal:
                raise ValueError("stream continues after terminal event")
            if payload == "[DONE]":
                if wire != "chat":
                    raise ValueError("wrong stream terminal marker")
                terminal = True
                canonical = payload
            else:
                chunk = _strict_json(payload)
                if not isinstance(chunk, dict):
                    raise ValueError("stream event must be an object")
                kind = chunk.get("type", event)
                if (event == "error" or kind in ("error", "response.failed")
                        or chunk.get("error") is not None):
                    raise ValueError("provider stream error")
                if wire == "responses":
                    terminal = kind in ("response.completed", "response.incomplete")
                elif wire == "anthropic":
                    terminal = kind == "message_stop"
                elif wire != "chat":
                    raise ValueError("unknown stream wire")
                canonical = json.dumps(chunk, allow_nan=False)
            if event:
                normalized.append("event: " + event)
            normalized.extend(("data: " + canonical, ""))
            data, event = [], ""
            continue
        if line.startswith(":"):
            continue
        field, _separator, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            data.append(value)
        elif field == "event":
            event = value
    if not terminal:
        raise ValueError("stream lacks its terminal event")
    return "\n".join(normalized) + "\n"


class PostTestLLMClient(LLMClient):
    """Bound started requests without logging credentials or provider errors."""

    def __init__(self, config, max_attempts=32):
        if type(max_attempts) is not int or not 2 <= max_attempts <= 32:
            raise ValueError("posttest transport needs 2..32 total attempts")
        super().__init__(config)
        self._max_attempts = max_attempts
        self._attempts = 0
        self._failed_attempts = 0

    def complete(self, prompt, system=None):
        attempts, failures = self._attempts, self._failed_attempts
        try:
            return super().complete(prompt, system)
        except BaseException as exc:
            # Wire decoding happens after the transport method returns. Count
            # those failures too, without double-counting transport exceptions.
            if self._attempts > attempts and self._failed_attempts == failures:
                self._failed_attempts += 1
                if "usage_available" not in self.last_usage:
                    self._unknown_usage()
            self.last_stop_reason = None
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, TimeoutError):
                raise TimeoutError("posttest transport timed out; retry disabled") from None
            raise RuntimeError("posttest model response failed; retry disabled") from None

    def transport_summary(self):
        """Return detached, allowlisted metadata; missing usage is never zero."""
        return {"attempts": self._attempts, "max_attempts": self._max_attempts,
                "automatic_retries": 0, "failed_attempts": self._failed_attempts,
                "usage_on_missing_response": "unknown"}

    def _unknown_usage(self):
        self.last_usage = {
            "usage_available": False,
            "pricing_available": (self.config.input_cost_per_million is not None
                                  and self.config.output_cost_per_million is not None),
            "input_tokens": None, "output_tokens": None,
            "total_tokens": None, "estimated_cost_usd": None,
        }
        # Known response usage remains in episode model-reply records. It cannot
        # be presented as complete aggregate usage after an unanswered request.
        for key in ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd"):
            self.total_usage[key] = None

    def _request_once(self, url, payload, headers, *, stream):
        if self._attempts >= self._max_attempts:
            raise RuntimeError("posttest transport attempt budget exhausted")
        self._attempts += 1
        self.last_usage = {}
        self.last_stop_reason = None
        try:
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            request = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                text = response.read().decode("utf-8")
            if stream:
                return _complete_sse(text, self.config.wire)
            value = _strict_json(text)
            if not isinstance(value, dict):
                raise ValueError("response must be an object")
            if value.get("error") is not None:
                raise ValueError("provider response error")
            return value
        except BaseException as exc:
            self._failed_attempts += 1
            self._unknown_usage()
            # The deadline's BaseException must escape to its owning wrapper.
            # Never retry it or convert it into a normal, retriable exception.
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, TimeoutError):
                raise TimeoutError("posttest transport timed out; retry disabled") from None
            # Provider exceptions may contain URLs, headers, keys or response
            # bodies. Keep them out of both public errors and saved summaries.
            raise RuntimeError("posttest transport failed; retry disabled") from None

    def _post(self, url, payload, headers, retries=1):
        # Accept the legacy signature, but a caller cannot expand the quota by
        # requesting retries. Every invocation attempts exactly one request.
        return self._request_once(url, payload, headers, stream=False)

    def _post_sse(self, url, payload, headers, retries=1):
        return self._request_once(url, payload, headers, stream=True)
