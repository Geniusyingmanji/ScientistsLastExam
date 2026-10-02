import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from sle.llm import LLMConfig
from sle.posttest_transport import PostTestLLMClient
from sle.world_agent import AuditedWorldClient, parse_turn, run_agent
from sle.world_session import WorldSession, replay_report


INITIAL = {"biomass": {"A": 0.06, "B": 0.04, "C": 0.06}, "nutrient": 4,
           "volume_ml": 10, "temperature_c": 30}


class ScriptedClient(PostTestLLMClient):
    def __init__(self, replies):
        super().__init__(LLMConfig(model="test-only"), max_attempts=4)
        self.replies = iter(replies)
        self.prompts = []

    def complete(self, prompt, system=None):
        self._attempts += 1
        self.prompts.append(prompt)
        self._record_usage({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        reply = next(self.replies)
        return json.dumps(reply() if callable(reply) else reply)


def action(rid, operation, arguments=None):
    return {"request_id": rid, "operation": operation, "arguments": arguments or {}}


def test_model_can_finish_batched_exploration_confirmation_and_interpretation(tmp_path):
    session = WorldSession(2718)
    claim = {"id": "agent-chosen-prediction", "statement": "Numerical nutrient-pulse effect.",
             "initial": INITIAL, "control": [],
             "treatment": [{"at_h": 8, "operation": "feed", "arguments": {"amount_mmol": 0.01}}],
             "readout": {"species": "A", "time_h": 24}, "expected_difference": [-1, 1], "replicates": 4}
    client = ScriptedClient([
        {"note": "Prepare, observe and freeze.", "actions": [action("a", "create", INITIAL),
            action("b", "advance", {"hours": 12}),
            action("c", "measure", {"vessel_id": "vessel-0001", "instrument": "counts"}),
            action("d", "commit", {"claims": [claim]})]},
        lambda: {"note": "Interpret confirmation.", "actions": [action("e", "interpret", {
            "claim_sha256": session.claim_hash, "text": "Only the declared contrast was checked."})]},
    ])
    report = run_agent(session, client, tmp_path, max_rounds=2)
    assert report["stop_reason"] == "completed"
    assert report["transport"]["attempts"] == 2
    assert report["usage"]["total_tokens"] == 30
    assert replay_report(json.loads((tmp_path / "operator-report.json").read_text()))["status"] == "exact_replay_passed"
    for prompt in client.prompts:
        assert "operator_recipe" not in prompt and '"uptake_a"' not in prompt
    assert report["provider_reported_models"] == []  # Never substitute the requested name.


def test_bad_action_stops_batch_without_executing_later_actions(tmp_path):
    session = WorldSession()
    client = ScriptedClient([{"note": "Invalid first operation.", "actions": [
        action("bad", "unknown"), action("must-not-run", "create", INITIAL)]},
        {"note": "Read state.", "actions": [action("inventory", "inventory")]}])
    report = run_agent(session, client, tmp_path, max_rounds=2)
    assert session.spent == 0 and not session.lab.vessels
    assert report["stop_reason"] == "model_round_limit"
    assert report["history"][0]["results"][0]["error"] == "unknown_operation"


def test_analysis_receives_only_public_history_and_description(tmp_path):
    seen = []
    def analysis(code, problem, history):
        seen.append((code, problem, history))
        return {"ok": True, "result": 123}
    client = ScriptedClient([{"note": "Read inventory.", "actions": [action("inventory", "inventory")]},
                             {"note": "Compute.", "analyze": {"code": "result = 123"}}])
    run_agent(WorldSession(732198), client, tmp_path, max_rounds=2, analysis=analysis)
    assert len(seen[0][2]) == 1
    assert "operator_recipe" not in json.dumps(seen) and "732198" not in json.dumps(seen)


@pytest.mark.parametrize("value", [
    {"note": "", "actions": []},
    {"note": "", "actions": [action("a", "commit"), action("b", "advance", {"hours": 1})]},
    {"note": "", "analyze": {"code": "pass"}, "actions": []},
])
def test_reject_malformed_turn_before_world_mutation(value):
    with pytest.raises(ValueError):
        parse_turn(json.dumps(value))


def test_transport_logs_started_before_network_and_does_not_save_credentials(tmp_path):
    client = AuditedWorldClient(LLMConfig(api_key="SECRET-CANARY", model="requested"), tmp_path, 2)
    response = {"id": "provider-id", "model": "provider-reported-model", "choices": [
        {"message": {"content": "{}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    def request(*args, **kwargs):
        ledger = (tmp_path / "model-transport.jsonl").read_text()
        assert '"event": "started"' in ledger and "SECRET-CANARY" not in ledger
        return io.BytesIO(json.dumps(response).encode())
    with patch("urllib.request.urlopen", side_effect=request):
        client.complete("public data")
    assert client.last_response_metadata["provider_reported_models"] == ["provider-reported-model"]
    with pytest.raises(FileExistsError):
        AuditedWorldClient(LLMConfig(), tmp_path, 2)
    assert "SECRET-CANARY" not in (tmp_path / "model-transport.jsonl").read_text()


def test_transport_failure_stops_episode_without_retry_and_keeps_unknown_usage(tmp_path):
    client = AuditedWorldClient(LLMConfig(), tmp_path, 2)
    with patch("urllib.request.urlopen", side_effect=TimeoutError("PRIVATE-URL-SECRET")) as network:
        report = run_agent(WorldSession(), client, tmp_path, max_rounds=2)
    assert network.call_count == 1
    assert report["stop_reason"] == "model_request_failed"
    assert report["usage"]["total_tokens"] is None
    assert report["transport"]["attempts"] == 1
    assert report["transport"]["failed_attempts"] == 1
    assert "PRIVATE-URL-SECRET" not in json.dumps(report)


def test_azure_deployment_route_uses_explicit_version_without_changing_model(tmp_path):
    config = LLMConfig(base_url="https://example.openai.azure.com/openai/deployments/my-deployment",
                       model="my-deployment", api_key="TRANSIENT-TOKEN")
    client = AuditedWorldClient(config, tmp_path, 2, azure_api_version="2024-12-01-preview")
    def request(req, **kwargs):
        assert req.full_url == config.base_url + "/chat/completions?api-version=2024-12-01-preview"
        assert json.loads(req.data)["model"] == "my-deployment"
        assert req.get_header("Authorization") == "Bearer TRANSIENT-TOKEN"
        return io.BytesIO(json.dumps({"model": "reported", "choices": [{"message": {"content": "{}"}}]}).encode())
    with patch("urllib.request.urlopen", side_effect=request):
        client.complete("public data")
    assert "TRANSIENT-TOKEN" not in (tmp_path / "model-transport.jsonl").read_text()


def test_http_failure_retains_status_but_never_provider_details(tmp_path):
    client = AuditedWorldClient(LLMConfig(), tmp_path, 2)
    failure = urllib.error.HTTPError("PRIVATE-URL", 429, "PRIVATE-MESSAGE", {"x-secret":"PRIVATE-HEADER"}, None)
    with patch("urllib.request.urlopen", side_effect=failure):
        report = run_agent(WorldSession(), client, tmp_path, max_rounds=2)
    assert report["rounds"][0]["diagnostic"] == {"stage":"request", "exception_type":"HTTPError", "http_status":429}
    assert "PRIVATE-" not in json.dumps(report)
    assert "PRIVATE-" not in (tmp_path / "model-transport.jsonl").read_text()


def test_closure_phase_blocks_more_experiments_without_fabricating_a_claim(tmp_path):
    session = WorldSession()
    client = ScriptedClient([
        {"note": "prepare", "actions": [action("a", "create", INITIAL)]},
        {"note": "late experiment", "actions": [action("b", "advance", {"hours": 12})]},
        {"note": "late analysis", "analyze": {"code": "result = 1"}},
    ])
    report = run_agent(session, client, tmp_path, max_rounds=3, exploration_rounds=1)
    assert session.lab.time_h == 0 and session.claims is None
    assert json.loads(client.prompts[1])["driver_phase"] == "commit_required"
    assert report["history"][1]["results"][0]["error"] == "commit_required_by_turn_contract"
    assert report["stop_reason"] == "model_round_limit"


def test_evaluation_profile_requires_forecasts_but_allows_candidate_to_repair_before_freeze(tmp_path):
    session = WorldSession()
    claim = {"id": "zero", "statement": "No operation contrast.", "initial": INITIAL,
             "control": [], "treatment": [], "readout": {"species": "A", "time_h": 24},
             "expected_difference": [-.02, .02], "replicates": 8, "evidence_ids": ["obs-000001"]}
    client = ScriptedClient([
        {"note": "measure", "actions": [action("a", "create", INITIAL),
            action("b", "measure", {"vessel_id": "vessel-0001", "instrument": "counts"})]},
        {"note": "missing forecast", "actions": [action("c", "commit", {"claims": [claim]})]},
        {"note": "complete forecast", "actions": [action("d", "commit", {"claims": [
            {**claim, "forecast": {"coverage": .9, "interval": [-.005, .005]}}]})]},
        lambda: {"note": "scope", "actions": [action("e", "interpret", {
            "claim_sha256": session.claim_hash, "text": "A numerical zero contrast is not a novel discovery."})]},
    ])
    report = run_agent(session, client, tmp_path, max_rounds=4, exploration_rounds=1,
                       evaluation_profile="paired-effects-v2")
    assert report["world_state"] == "completed"
    assert not report["history"][1]["results"][0]["ok"]
    assert "forecast_evaluation" in session.verification["results"][0]
    assert session.report()["discovery_depth"] is None
    assert replay_report(session.report(private=True))["status"] == "exact_replay_passed"


def test_analysis_idle_time_does_not_consume_active_budget_or_reset_it(monkeypatch):
    from sle.world_agent import WorldAnalysis
    clock = [100.0]
    class Worker:
        def __init__(self, *args, timeout_s, **kwargs):
            self.deadline = clock[0] + timeout_s
        def __call__(self, payload):
            available = self.deadline - clock[0]
            clock[0] += min(2.0, available)
            if available < 2:
                raise TimeoutError("active budget exhausted")
            return {"ok": True}
        def close(self):
            pass
    monkeypatch.setattr("sle.world_agent.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("sle.secure_eval.CandidateProxy", Worker)
    analysis = WorldAnalysis(timeout_s=5)
    clock[0] += 100  # More model idle time than the entire analysis allowance.
    assert analysis("pass", {}, [])["ok"]
    assert analysis.remaining_seconds == 3
    clock[0] += 100
    assert analysis("pass", {}, [])["ok"]
    assert analysis.remaining_seconds == 1
    clock[0] += 100
    with pytest.raises(TimeoutError):
        analysis("pass", {}, [])
    assert analysis.remaining_seconds == 0
