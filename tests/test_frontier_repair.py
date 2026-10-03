"""Opt-in v0.3 repairs use public schema fixtures, never API or hidden solvers."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from env import prospective_runner as prospective
from env import research_runner as runner
from env.field_ecology import protocol


class PublicFixture:
    name, version, axis_field = "field_ecology", "schema-fixture", "habitat_values"
    channels, scales, noise_std = protocol.CHANNELS, protocol.SCALES, protocol.NOISE_STD
    calls = []

    def describe(self):
        return protocol.describe()

    def validate(self, spec):
        return protocol.validate_spec(spec)

    def cost(self, spec):
        self.validate(spec)
        return 1

    def run(self, spec, *, noise_key=None):
        self.calls.append(deepcopy(spec))
        return {"axis": spec["habitat_values"], "channels": list(self.channels),
                "values": [[.3,.4,.2] for _ in spec["habitat_values"]]}


class LiteralProxy:
    calls = []

    def __init__(self, path, entrypoint, **kwargs):
        # Read/parse the fixture only; never execute candidate code on the host.
        ast.parse(Path(path).read_text())
        assert entrypoint == "predict"

    def __call__(self, spec):
        self.calls.append(deepcopy(spec))
        return [[.3,.4,.2] for _ in spec["habitat_values"]]

    def close(self, **kwargs):
        pass


class EmptyAnalysis:
    def __init__(self, seconds):
        self.remaining = seconds

    def bind_model_snapshots(self, store):
        self.store = store

    def close(self):
        pass


class Client:
    def __init__(self, manifest, actions):
        self.config = SimpleNamespace(model=manifest["requested_model"], **manifest["decoding"])
        self.actions, self.prompts = actions, []
        self.systems = []
        self.last_usage, self.last_response_metadata, self.last_stop_reason = None, {}, None

    def complete(self, encoded, *, system):
        prompt = json.loads(encoded)
        self.prompts.append(prompt)
        self.systems.append(system)
        action = self.actions[len(self.prompts)-1]
        self.last_usage = {"total_tokens": 1}
        self.last_response_metadata = {"provider_reported_models": [self.config.model]}
        self.last_stop_reason = "stop"
        return json.dumps(action(prompt) if callable(action) else action)


@pytest.fixture
def harness(monkeypatch):
    world = PublicFixture()
    PublicFixture.calls, LiteralProxy.calls = [], []
    monkeypatch.setattr(runner, "load_world", lambda name, seed: (world, None))
    monkeypatch.setattr(prospective, "load_world", lambda name, seed: (world, None))
    monkeypatch.setattr(runner, "source_digest", lambda: "fixed-schema-fixture-source")
    monkeypatch.setattr(prospective, "CandidateProxy", LiteralProxy)
    return world


def spec(h=0):
    return {"habitat_values": [h], "visits": ["rapid", "rapid"]}


def source(_=None):
    return {"note": "source", "experiments": [spec()]}


def registration(prompt):
    return {"note": "new habitat prediction", "preregister": {
        "profile": "predictive_validation", "scope": "one fixture readout",
        "rivals": [{"id": "model-v1", "rationale": "source fixture",
                    "evidence_ids": [prompt["observation_catalog"][0]["id"]], "tolerance": .15,
                    "predictor_code": 'def predict(spec):\n    return [[.3,.4,.2] for _ in spec["habitat_values"]]\n'}],
        "experiments": [{"id": "target", "role": "target", "spec": spec(1)}],
        "readout": [{"experiment_id": "target", "row": 0, "channel": "first_visit_detection", "weight": 1.}],
        "replicates": 16, "revision_of": None, "change_note": ""}}


def finish(prompt):
    return {"note": "finish", "finish": {"explanation": "Fixture-scoped evidence only.",
            "evidence_ids": [prompt["observation_catalog"][0]["id"]],
            "test_ids": [prompt["scientific_task"]["results"][0]["test_id"]]}}


def execute(tmp_path, actions, workflow="frontier_repair", **limits):
    manifest = runner.create_manifest("schema-repair-fixture", "field_ecology", 74101,
        workflow=workflow, limits=dict({"rounds": max(4,len(actions))}, **limits))
    client = Client(manifest, actions)
    report = runner.run_research(manifest, tmp_path/"run", lambda _: client, analysis_factory=EmptyAnalysis)
    return manifest, client, report


def test_oversized_valid_batch_rejected_without_oracle_and_correction_finishes(tmp_path, harness):
    actions = [{"note": "oversized", "experiments": [spec() for _ in range(9)]}, source, registration, finish]
    manifest, client, report = execute(tmp_path, actions)
    assert report["status"] == "completed"
    assert report["history"][0]["outcome"] == "schema_rejected"
    assert report["history"][0]["scientific_dispatch"] is False
    assert "1..8" in report["history"][0]["feedback"]
    assert client.prompts[1]["scientific_task"]["usage"]["experiment_attempts"] == 0
    assert len(PublicFixture.calls) == 17 and len(LiteralProxy.calls) == 2
    assert report["usage"]["model_request_attempts"] == 4
    assert report["scientific_task"]["results"][0]["result"]["protocol"] == "sle-prospective-evidence-0.2"
    assert manifest["protocol"] == runner.REPAIR_PROTOCOL


def test_invalid_later_spec_prevalidates_whole_batch_without_partial_data(tmp_path, harness):
    actions = [{"note": "second invalid", "experiments": [spec(), {"habitat_values": [0]}]}, source, registration, finish]
    _, client, report = execute(tmp_path, actions)
    assert report["status"] == "completed"
    assert report["history"][0]["feedback"] == "expected exactly habitat_values and visits"
    assert client.prompts[1]["observation_catalog"] == []
    assert client.prompts[1]["scientific_task"]["usage"]["actions"] == 0
    assert len(PublicFixture.calls) == 17


def test_preregistration_preview_is_read_only_and_invalid_request_can_be_corrected(tmp_path, harness):
    def invalid(prompt):
        value = registration(prompt)
        value["preregister"]["readout"][0]["channel"] = "unknown"
        return value
    _, client, report = execute(tmp_path, [source, invalid, registration, finish])
    assert report["status"] == "completed"
    assert report["history"][1]["outcome"] == "schema_rejected"
    assert client.prompts[2]["scientific_task"]["usage"]["predictor_attempts"] == 0
    assert client.prompts[2]["scientific_task"]["usage"]["experiment_attempts"] == 1
    assert report["scientific_task"]["results"][0]["test_id"].endswith("-01")
    assert len(LiteralProxy.calls) == 2 and len(PublicFixture.calls) == 17


def test_direct_preview_never_executes_or_mutates_alpha_known_records_or_usage(tmp_path, harness):
    task = prospective.ProspectiveTask("field_ecology", 74101, tmp_path/"science", frontier=True)
    record = task.observe_source(spec())
    request = registration({"observation_catalog": [record]})["preregister"]
    state_before = task._session.snapshot()
    known_before = deepcopy(task._session._known)
    usage_before = task.public_report()["usage"]
    event_head = task.public_report()["receipt_head"]
    task.preview_preregistration(request)
    assert task._session.snapshot() == state_before
    assert task._session._known == known_before
    assert task.public_report()["usage"] == usage_before
    assert task.public_report()["receipt_head"] == event_head
    assert len(PublicFixture.calls) == 1 and LiteralProxy.calls == []
    task.close("driver_stopped")


@pytest.mark.parametrize("kind", ["value_error", "schema_subclass"])
def test_dispatched_observation_failure_never_retries_or_exposes_exception(tmp_path, harness, kind):
    def failed(spec, **kwargs):
        PublicFixture.calls.append(spec)
        error = ValueError if kind == "value_error" else prospective.PublicSchemaRejected
        raise error("PRIVATE_PATH_CANARY")
    harness.run = failed
    _, client, report = execute(tmp_path, [source, source, registration, finish])
    assert len(client.prompts) == 1 and len(PublicFixture.calls) == 1
    assert report["status"] == "failed"
    assert "PRIVATE_PATH_CANARY" not in json.dumps(report)
    assert report["history"][0]["outcome"] == "operator_failure"


def test_unexpected_validator_valueerror_is_terminal_not_public_feedback(tmp_path, harness):
    def broken(spec):
        raise ValueError("PRIVATE_VALIDATOR_CANARY")
    harness.validate = broken
    _, client, report = execute(tmp_path, [source, source, registration, finish])
    assert len(client.prompts) == 1 and PublicFixture.calls == []
    assert report["status"] == "failed" and report["infrastructure_failure"] is not None
    assert "PRIVATE_VALIDATOR_CANARY" not in json.dumps(report)


def test_dispatched_prediction_failure_remains_terminal(tmp_path, harness, monkeypatch):
    def failed(self, spec):
        LiteralProxy.calls.append(spec)
        raise RuntimeError("PRIVATE_PREDICTION_CANARY")
    monkeypatch.setattr(LiteralProxy, "__call__", failed)
    _, client, report = execute(tmp_path, [source, registration, registration, finish])
    assert len(client.prompts) == 2 and len(LiteralProxy.calls) == 1
    assert len(PublicFixture.calls) == 1
    assert report["status"] == "invalid_action"
    assert report["stop_reason"] == "candidate_prediction_failed"
    assert "PRIVATE_PREDICTION_CANARY" not in json.dumps(report)


def test_public_limits_system_statistics_and_versioned_manifest(tmp_path, harness):
    manifest, client, report = execute(tmp_path, [source, registration, finish], max_experiments_per_turn=3)
    assert report["status"] == "completed"
    assert client.prompts[0]["problem"]["research_limits"] == manifest["limits"]
    assert client.prompts[0]["problem"]["research_limits"]["max_experiments_per_turn"] == 3
    assert all(system == runner.REPAIR_SYSTEM for system in client.systems)
    assert "at most 8 specs" in runner.REPAIR_SYSTEM
    assert "R=B+sqrt(V/(n*alpha))" in runner.REPAIR_SYSTEM
    assert "A malformed experimental\nor preregistration action closes" not in runner.REPAIR_SYSTEM
    runner.validate_manifest(manifest)
    changed = deepcopy(manifest)
    changed["protocol"] = runner.FRONTIER_PROTOCOL
    with pytest.raises(ValueError):
        runner.validate_manifest(changed)


def test_v02_keeps_terminal_batch_error_and_no_new_prompt_fields(tmp_path, harness):
    _, client, report = execute(tmp_path, [{"note": "oversized", "experiments": [spec() for _ in range(9)]}], workflow="frontier")
    assert report["status"] == "invalid_action" and len(client.prompts) == 1
    assert "research_limits" not in client.prompts[0]["problem"]
    assert client.systems == [runner.FRONTIER_SYSTEM]
    assert PublicFixture.calls == []


def test_legacy_system_strings_remain_byte_identical():
    assert hashlib.sha256(runner.SYSTEM.encode()).hexdigest() == 'bb87d948ebffed5037c4bc30c4299e2406696422cff8aadce20330bd8db97ef3'
    assert hashlib.sha256(runner.FRONTIER_SYSTEM.encode()).hexdigest() == '67fa21f0636af129382c1cbdf24afd92ea0bd5335544bd1a1470c63a8d8489d8'


def test_missing_snapshot_binding_is_recoverable_before_prediction(tmp_path, harness):
    def missing(prompt):
        action = registration(prompt)
        rival = action["preregister"]["rivals"][0]
        rival.pop("predictor_code")
        rival["model_snapshot"] = {"name": "missing", "version": "v1", "sha256": "a"*64}
        return action
    _, client, report = execute(tmp_path, [source, missing, registration, finish])
    assert report["status"] == "completed"
    assert report["history"][1]["feedback"] == "unknown model snapshot"
    assert client.prompts[2]["scientific_task"]["usage"]["predictor_attempts"] == 0
    assert len(LiteralProxy.calls) == 2


def test_later_dispatched_failure_retains_partial_data_without_retry(tmp_path, harness):
    def partly_failed(value, **kwargs):
        PublicFixture.calls.append(value)
        if len(PublicFixture.calls) == 2:
            raise RuntimeError("PRIVATE_SECOND_ORACLE_CANARY")
        return {"axis": value["habitat_values"], "channels": list(harness.channels), "values": [[.3,.4,.2]]}
    harness.run = partly_failed
    _, client, report = execute(tmp_path, [{"note": "batch", "experiments": [spec(), spec(.5)]}, source, registration, finish])
    assert len(client.prompts) == 1 and len(PublicFixture.calls) == 2
    assert len(report["history"][0]["observations"]) == 1
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 2
    assert report["status"] == "failed"
    assert "PRIVATE_SECOND_ORACLE_CANARY" not in json.dumps(report)


@pytest.mark.parametrize("environment", ["molecular_forces", "climate_response", "catalyst_aging", "field_ecology", "phase_equilibria"])
def test_each_new_world_uses_audited_public_schema_feedback(environment):
    from importlib import import_module
    module = import_module("env."+environment+".protocol")
    task = object.__new__(prospective.ProspectiveTask)
    task._frontier = True
    task._world = SimpleNamespace(name=environment, validate=module.validate_spec)
    with pytest.raises(prospective.PublicSchemaRejected) as caught:
        task._preview_validate({})
    assert 0 < len(str(caught.value)) <= 500
    assert "/" not in str(caught.value)
    example = module.example()
    assert task._preview_validate(example) == module.validate_spec(example)
