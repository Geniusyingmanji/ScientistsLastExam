"""Offline transport controls: no real requests, credentials or sealed data."""
import copy
import json
import traceback
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from sle.llm import LLMConfig
from sle.posttest_transport import PostTestLLMClient


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.payload


def client(**kwargs):
    config = LLMConfig(base_url="https://offline.invalid/v1", model="manual-fixture-model",
                       api_key="private_fixture_key", timeout_seconds=7.0,
                       extra_headers={"X-Fixture-Secret": "private_fixture_header"},
                       input_cost_per_million=1.0, output_cost_per_million=2.0, **kwargs)
    return PostTestLLMClient(config, max_attempts=2)


def chat_response(text="{}"):
    return Response(json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}}).encode())


@pytest.mark.parametrize("stream", [False, True])
def test_uncertain_failure_is_one_request_without_retry_or_sleep(monkeypatch, stream):
    request = Mock(side_effect=TimeoutError("url=/secret?key=private_fixture_key"))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    sleeper = Mock(side_effect=AssertionError("single-attempt transport must not back off"))
    monkeypatch.setattr("sle.llm.time.sleep", sleeper)
    model = client(stream=stream)
    with pytest.raises(TimeoutError, match="retry disabled"):
        model.complete("a handwritten prompt")
    assert request.call_count == 1 and sleeper.call_count == 0
    assert model.transport_summary() == {"attempts": 1, "max_attempts": 2, "automatic_retries": 0,
                                         "failed_attempts": 1, "usage_on_missing_response": "unknown"}
    assert model.last_usage["usage_available"] is False
    for key in ("input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd"):
        assert model.last_usage[key] is None
        assert model.total_usage[key] is None


def test_chat_and_sse_share_budget_and_third_attempt_never_reaches_transport(monkeypatch):
    request = Mock(side_effect=[Response(b'{"ok": true}'), Response(b'data: [DONE]\n\n')])
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    assert model._post("https://offline.invalid", {}, {}, retries=999) == {"ok": True}
    assert model._post_sse("https://offline.invalid", {}, {}, retries=999) == "data: [DONE]\n\n"
    with pytest.raises(RuntimeError, match="attempt budget exhausted"):
        model._post("https://offline.invalid", {}, {})
    with pytest.raises(RuntimeError, match="attempt budget exhausted"):
        model._post_sse("https://offline.invalid", {}, {})
    assert request.call_count == 2
    assert model.transport_summary()["attempts"] == 2
    assert model.transport_summary()["failed_attempts"] == 0


def test_failed_attempt_consumes_shared_quota_and_cannot_be_retried_for_free(monkeypatch):
    request = Mock(side_effect=[ConnectionError("fixture"), Response(b'data: [DONE]\n\n')])
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    with pytest.raises(RuntimeError, match="retry disabled"):
        model._post("https://offline.invalid", {}, {}, retries=32)
    model._post_sse("https://offline.invalid", {}, {})
    with pytest.raises(RuntimeError, match="attempt budget exhausted"):
        model._post("https://offline.invalid", {}, {})
    assert request.call_count == 2
    assert model.transport_summary()["failed_attempts"] == 1


def test_missing_response_cannot_reuse_prior_usage_or_claim_known_total_cost(monkeypatch):
    request = Mock(side_effect=[chat_response(), TimeoutError("fixture missing response")])
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    assert model.complete("first") == "{}"
    assert model.last_usage["total_tokens"] == model.total_usage["total_tokens"] == 6
    assert model.total_usage["estimated_cost_usd"] > 0
    with pytest.raises(TimeoutError):
        model.complete("second")
    assert model.last_usage["total_tokens"] is None
    assert model.total_usage["total_tokens"] is None
    assert model.total_usage["estimated_cost_usd"] is None
    assert model.last_stop_reason is None


def test_later_known_response_cannot_repair_unknown_aggregate_usage(monkeypatch):
    request = Mock(side_effect=[TimeoutError("fixture missing response"), chat_response()])
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    with pytest.raises(TimeoutError):
        model.complete("first")
    assert model.complete("second") == "{}"
    assert model.last_usage["total_tokens"] == 6
    assert model.total_usage["total_tokens"] is None
    assert model.total_usage["estimated_cost_usd"] is None


def test_exception_and_summary_do_not_include_provider_secrets(monkeypatch):
    secret = "private_fixture_key private_fixture_header private_provider_body"
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", Mock(side_effect=ValueError(secret)))
    model = client()
    prompt = "private_prompt_text"
    with pytest.raises(RuntimeError) as captured:
        model.complete(prompt)
    rendered = "".join(traceback.format_exception(type(captured.value), captured.value, captured.value.__traceback__))
    public = json.dumps(model.transport_summary()) + str(captured.value) + rendered
    for item in ("private_fixture_key", "private_fixture_header", "private_provider_body", "private_prompt_text"):
        assert item not in public
    assert set(model.transport_summary()) == {"attempts", "max_attempts", "automatic_retries",
                                             "failed_attempts", "usage_on_missing_response"}


def test_existing_deadline_signal_is_counted_and_propagated_without_retry(monkeypatch):
    class FixtureDeadline(BaseException):
        pass
    request = Mock(side_effect=FixtureDeadline())
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    with pytest.raises(FixtureDeadline):
        model.complete("fixture")
    assert request.call_count == 1
    assert model.transport_summary()["attempts"] == model.transport_summary()["failed_attempts"] == 1
    assert model.total_usage["total_tokens"] is None


@pytest.mark.parametrize("raw", [b"invalid-json", b"[]", b"null", b"\xff"])
def test_unusable_nonstream_response_stops_without_retry(monkeypatch, raw):
    request = Mock(return_value=Response(raw))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client()
    with pytest.raises(RuntimeError, match="retry disabled"):
        model.complete("fixture")
    assert request.call_count == 1
    assert model.transport_summary()["failed_attempts"] == 1
    assert model.total_usage["estimated_cost_usd"] is None


def test_preserves_protocol_configuration_and_honors_timeout(monkeypatch):
    request = Mock(return_value=chat_response("fixture reply"))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(chat_max_tokens_field="max_completion_tokens", reasoning_effort="medium", temperature=None)
    original = copy.deepcopy(asdict(model.config))
    assert model.complete("fixture prompt", system="fixture system") == "fixture reply"
    sent = request.call_args.args[0]
    body = json.loads(sent.data)
    assert sent.full_url == "https://offline.invalid/v1/chat/completions"
    assert body["model"] == "manual-fixture-model"
    assert body["reasoning_effort"] == "medium" and "temperature" not in body
    assert "max_completion_tokens" in body and "max_tokens" not in body
    assert request.call_args.kwargs["timeout"] == 7.0
    assert asdict(model.config) == original
    assert model.last_usage["total_tokens"] == 6


def test_sse_success_uses_original_streaming_parser_once(monkeypatch):
    text = 'data: {"choices":[{"delta":{"content":"fixture"},"finish_reason":null}]}\n\n'
    text += 'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
    text += 'data: [DONE]\n\n'
    request = Mock(return_value=Response(text.encode()))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(stream=True)
    assert model.complete("fixture") == "fixture"
    assert request.call_count == 1 and model.last_usage["total_tokens"] == 6
    assert json.loads(request.call_args.args[0].data)["stream"] is True
    assert model.transport_summary()["failed_attempts"] == 0


@pytest.mark.parametrize("raw", [
    'data: {"choices":[{"delta":{"content":"{}"}}]}\n\n',
    'data: bad-json\n\ndata: [DONE]\n\n',
    'data: {"error":{"message":"private_fixture_key"}}\n\ndata: [DONE]\n\n',
    'data: [DONE]\n\ndata: {"choices":[]}\n\n',
    'data: {"usage":{"prompt_tokens":NaN}}\n\ndata: [DONE]\n\n',
])
def test_broken_or_error_sse_is_rejected_without_partial_action_or_retry(monkeypatch, raw):
    request = Mock(return_value=Response(raw.encode()))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(stream=True)
    with pytest.raises(RuntimeError, match="retry disabled") as captured:
        model.complete("fixture")
    assert "private_fixture_key" not in str(captured.value)
    assert request.call_count == 1
    assert model.transport_summary()["failed_attempts"] == 1
    assert model.total_usage["total_tokens"] is None


def test_valid_multiline_sse_and_comments_are_not_truncated(monkeypatch):
    raw = ': keepalive\n\nevent: message\ndata: {"choices": [\ndata: {"delta":{"content":"fixture"},"finish_reason":"stop"}],\ndata: "usage":{"prompt_tokens":4,"completion_tokens":2}}\n\n'
    raw += ': comment\n\ndata: [DONE]\n\n'
    request = Mock(return_value=Response(raw.encode()))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(stream=True)
    assert model.complete("fixture") == "fixture"
    assert model.last_usage["total_tokens"] == 6
    assert model.transport_summary()["failed_attempts"] == 0


@pytest.mark.parametrize("wire, raw", [
    ("responses", 'event: response.completed\ndata: {"type":"response.completed","response":{}}\n\n'),
    ("responses", 'event: response.incomplete\ndata: {"type":"response.incomplete","response":{}}\n\n'),
    ("anthropic", 'event: message_stop\ndata: {"type":"message_stop"}\n\n'),
])
def test_stream_termination_is_wire_specific(monkeypatch, wire, raw):
    request = Mock(return_value=Response(raw.encode()))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(wire=wire)
    assert model._post_sse("https://offline.invalid", {}, {})
    assert request.call_count == 1 and model.transport_summary()["failed_attempts"] == 0


@pytest.mark.parametrize("wire", ["chat", "responses", "anthropic"])
def test_provider_json_error_is_safe_on_every_wire(monkeypatch, wire):
    raw = json.dumps({"error": {"message": "private_provider_body private_fixture_key"}}).encode()
    request = Mock(return_value=Response(raw))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(wire=wire)
    with pytest.raises(RuntimeError, match="retry disabled") as captured:
        model.complete("fixture")
    assert "private_provider_body" not in str(captured.value)
    assert "private_fixture_key" not in str(captured.value)
    assert request.call_count == 1
    assert model.transport_summary()["failed_attempts"] == 1
    assert model.total_usage["total_tokens"] is None


def test_posttransport_usage_decoder_error_is_safe_and_counts_once(monkeypatch):
    raw = 'data: {"choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}],"usage":{"prompt_tokens":"private_fixture_key","completion_tokens":2}}\n\ndata: [DONE]\n\n'
    request = Mock(return_value=Response(raw.encode()))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    model = client(stream=True)
    with pytest.raises(RuntimeError, match="retry disabled") as captured:
        model.complete("fixture")
    assert "private_fixture_key" not in str(captured.value)
    assert request.call_count == 1
    assert model.transport_summary()["failed_attempts"] == 1
    assert model.last_usage["total_tokens"] is None
    assert model.total_usage["estimated_cost_usd"] is None


def test_known_usage_is_retained_when_complete_response_has_no_visible_answer(monkeypatch):
    raw = 'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"},"finish_reason":"length"}],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n'
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", Mock(return_value=Response(raw.encode())))
    model = client(stream=True)
    with pytest.raises(RuntimeError, match="retry disabled"):
        model.complete("fixture")
    assert model.last_usage["total_tokens"] == model.total_usage["total_tokens"] == 6
    assert model.last_stop_reason is None
    assert model.transport_summary()["failed_attempts"] == 1


@pytest.mark.parametrize("maximum", [True, False, 0, 1, 33, 2.0, "32", None])
def test_invalid_budget_is_rejected_without_request(maximum, monkeypatch):
    request = Mock(side_effect=AssertionError("invalid budget must not request"))
    monkeypatch.setattr("sle.posttest_transport.urllib.request.urlopen", request)
    with pytest.raises(ValueError, match="2..32"):
        PostTestLLMClient(LLMConfig(), max_attempts=maximum)
    assert request.call_count == 0


def test_default_budget_is_32_and_summary_cannot_mutate_client():
    model = PostTestLLMClient(LLMConfig())
    summary = model.transport_summary()
    assert summary["max_attempts"] == 32 and summary["attempts"] == 0
    summary["max_attempts"] = 999
    assert model.transport_summary()["max_attempts"] == 32
