"""Independent research-runner review: numeric stand-ins plus real Linux isolation."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from _sandbox_tools import skip_unless_sandbox
from env import prospective_runner as prospective
from env import research_runner as runner


PREDICTOR = 'def predict(spec):\n    return [[MODEL["slope"] * spec["drive"] * t] for t in spec["times"]]\n'


class NumericProxy:
    """Interpret only a frozen literal parameter; do not execute candidate code."""
    calls = []

    def __init__(self, path, entrypoint, timeout_s, memory_mb, packages):
        tree = ast.parse(Path(path).read_text())
        self.slope = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "COEFFICIENT":
                    self.slope = ast.literal_eval(node.value)
                if node.targets[0].id == "MODEL":
                    self.slope = json.loads(ast.literal_eval(node.value.args[0]))["slope"]
        assert self.slope is not None and entrypoint == "predict" and packages == ()
        self.closed = False
        self.calls.append(self)

    def __call__(self, spec):
        return [[self.slope * spec["drive"] * t] for t in spec["times"]]

    def close(self, kill=True):
        self.closed = True


class FakeAnalysis:
    instances = []

    def __init__(self, seconds):
        self.remaining, self.closed, self.store = seconds, False, None
        self.calls = []
        self.instances.append(self)

    def bind_model_snapshots(self, store):
        self.store = store

    def run(self, code, problem, records, history):
        self.calls.append(code)
        if code == "operator_error":
            raise ValueError("/private/secret-analysis-path CANARY")
        if code == "mutate":
            problem["problem"]["name"] = "MUTATED"
            records[0]["observation"]["values"][0][0] = 9999
            history[0]["note"] = "MUTATED"
        if code == "mutate_new":
            records[-1]["observation"]["values"][1][0] = 9999
            history[-1]["observations"][-1]["observation"]["values"][1][0] = 9999
        if code == "surrogate":
            return {"ok": True, "result": "\ud800"}
        for index, slope in enumerate((1., 2.)):
            self.store.save_model("rival-%d" % index, "v1", {"slope": slope}, PREDICTOR)
        return {"ok": True, "result": self.store.catalog()}

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, manifest, steps):
        self.config = SimpleNamespace(model=manifest["requested_model"], **manifest["decoding"])
        self.steps, self.prompts = list(steps), []
        self.last_usage, self.last_response_metadata, self.last_stop_reason = None, {}, None

    def complete(self, encoded, *, system):
        assert system == runner.SYSTEM
        prompt = json.loads(encoded)
        self.prompts.append(prompt)
        step = self.steps[len(self.prompts) - 1]
        if isinstance(step, Exception):
            raise step
        value = step(prompt) if callable(step) else step
        self.last_usage = {"total_tokens": 5}
        self.last_response_metadata = {"provider_reported_models": [self.config.model]}
        self.last_stop_reason = "stop"
        return value if isinstance(value, str) else json.dumps(value)


class ReferenceClient:
    client_kind = "scripted_reference"

    def __init__(self, manifest, steps):
        self.reference_id = manifest["reference"]["id"]
        self.reference_source_sha256 = manifest["reference"]["source_sha256"]
        self.steps, self.prompts = list(steps), []
        self.last_usage, self.last_response_metadata, self.last_stop_reason = None, {}, None

    def complete(self, encoded, *, system):
        assert system == runner.SYSTEM
        prompt = json.loads(encoded)
        self.prompts.append(prompt)
        step = self.steps[len(self.prompts) - 1]
        if isinstance(step, Exception):
            raise step
        value = step(prompt) if callable(step) else step
        self.last_stop_reason = "reference_action"
        return value if isinstance(value, str) else json.dumps(value)


@pytest.fixture
def fixture_environment(monkeypatch):
    original_profile = runner.get_task_profile
    monkeypatch.setattr(runner, "ENVIRONMENTS", ("prospective_fixture",))
    monkeypatch.setattr(runner, "load_world", lambda name, seed: (prospective._FixtureWorld(seed), None))
    monkeypatch.setattr(runner, "get_task_profile", lambda name, environment: original_profile(name, "hysteresis_material"))
    monkeypatch.setattr(runner, "source_digest", lambda: "fixture-source-digest")
    return lambda **kwargs: runner.create_manifest("fixture-research", "prospective_fixture", 7, **kwargs)


@pytest.fixture
def numeric(monkeypatch, fixture_environment):
    NumericProxy.calls, FakeAnalysis.instances = [], []
    monkeypatch.setattr(prospective, "CandidateProxy", NumericProxy)
    return fixture_environment


def observed(_=None):
    return {"note": "source evidence", "experiments": [{"drive": 0, "times": [0, 1, 2]}]}


def registered(prompt):
    request = prospective._fixture_request((1, 2), 1)
    for rival, snapshot in zip(request["rivals"], prompt["model_snapshots"]):
        rival.pop("predictor_code")
        rival["model_snapshot"] = {key: snapshot[key] for key in ("name", "version", "sha256")}
    return {"note": "compare precommitted laws", "preregister": request}


def finished(prompt):
    return {"note": "report negative evidence", "finish": {
        "explanation": "The fresh readout refuted both initial accounts. This is a scoped negative result.",
        "evidence_ids": [prompt["observation_catalog"][0]["id"]],
        "test_ids": [prompt["scientific_task"]["results"][0]["test_id"]]}}


def successful_steps(code="save"):
    return [observed, {"note": "fit and save rivals", "analyze": {"code": code}}, registered, finished]


def run(tmp_path, manifest, steps, analysis=FakeAnalysis):
    client = FakeClient(manifest, steps)
    report = runner.run_research(manifest, tmp_path / "run", lambda _: client, analysis_factory=analysis)
    return report, client


def receipts(root):
    return [json.loads(path.read_text()) for path in sorted((root / "driver-receipts").glob("[0-9]*.json"))]


def test_manifest_name_roundtrip_public_profile_and_tamper_rejected(tmp_path, numeric):
    manifest = numeric(profile="mechanism_discrimination")
    assert manifest["profile"]["name"] == "mechanism_discrimination"
    assert manifest["profile"]["submission_contract"]["action"] == "finish"
    assert "predictor_code, claims and explanation" not in manifest["profile"]["public_prompt"]
    runner.validate_manifest(manifest)
    manifest["profile"]["name"] = "open_discovery"
    with pytest.raises(ValueError):
        runner.run_research(manifest, tmp_path / "absent", lambda _: pytest.fail("factory called"))
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("malformed", [{}, {"profile": {}}, None, []])
def test_malformed_manifest_has_bounded_preflight_error(malformed):
    with pytest.raises(ValueError, match="invalid research manifest"):
        runner.validate_manifest(malformed)


def test_source_change_rejected_before_any_client(tmp_path, numeric, monkeypatch):
    manifest = numeric()
    monkeypatch.setattr(runner, "source_digest", lambda: "changed")
    with pytest.raises(ValueError, match="changed after freeze"):
        runner.run_research(manifest, tmp_path / "run", lambda _: pytest.fail("client called"))


def test_complete_workflow_freezes_snapshots_and_receipts_before_observation(tmp_path, numeric):
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == "completed", report
    assert report["infrastructure_failure"] is None
    assert report["history"][2]["outcome"] == "both_candidates_refuted"
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 9
    assert report["scientific_task"]["usage"]["predictor_attempts"] == 4
    assert report["usage"]["model_request_attempts"] == 4
    assert report["usage"]["analysis_attempts"] == 1
    assert len(NumericProxy.calls) == 4 and all(proxy.closed for proxy in NumericProxy.calls)
    assert report["score"] is None and not report["discovery_depth_certified"]
    assert FakeAnalysis.instances[0].closed
    with pytest.raises(ValueError, match="frozen"):
        FakeAnalysis.instances[0].store.save_model("later", "v1", {})
    public = json.dumps(client.prompts)
    assert "private_world_seed" not in public and str(tmp_path) not in public
    assert "clean_truth" not in public and "prediction_values" not in public
    assert "observation_contract" in client.prompts[0]["problem"]
    log = receipts(tmp_path / "run")
    previous = None
    for index, entry in enumerate(log, 1):
        assert entry["sequence"] == index and entry["previous_sha256"] == previous
        assert entry["sha256"] == prospective.digest({k: v for k, v in entry.items() if k != "sha256"})
        previous = entry["sha256"]
    assert log[-1]["kind"] == "research_closed"
    assert log[-1]["payload"]["report_sha256"] == prospective.digest(report)
    bound = next(entry["payload"] for entry in log if entry["kind"] == "resolved_preregistration")
    assert len(bound["snapshot_bindings"]) == 2
    assert all("MODEL =" in rival["predictor_code"] for rival in bound["request"]["rivals"])
    assert prospective.verify_directory(tmp_path / "run" / "science")["replayed_tests"] == 1


def test_analysis_cannot_mutate_operator_problem_or_old_observation_arrays(tmp_path, numeric):
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps("mutate"))
    assert report["status"] == "completed"
    assert report["history"][0]["note"] == "source evidence"
    assert report["history"][0]["observations"][0]["observation"]["values"][0][0] != 9999
    assert client.prompts[2]["problem"]["problem"]["name"] == "prospective_fixture"
    bundle = json.loads((tmp_path / "run/science/bundle-private.json").read_text())
    assert bundle["records"][0]["observation"]["values"][0][0] != 9999
    assert "clean_truth" not in json.dumps(bundle["records"])


def test_new_prospective_arrays_are_readonly_to_later_analysis(tmp_path, numeric):
    steps = successful_steps()[:3] + [{"note": "try mutation", "analyze": {"code": "mutate_new"}}, finished]
    report, _ = run(tmp_path, numeric(limits={"rounds": 5}), steps)
    assert report["status"] == "completed"
    values = report["history"][2]["observations"][-1]["observation"]["values"]
    assert values[1][0] != 9999
    bundle = json.loads((tmp_path / "run/science/bundle-private.json").read_text())
    assert bundle["records"][-1]["observation"]["values"] == values
    assert prospective.verify_directory(tmp_path / "run/science")["replayed_tests"] == 1


def reference_manifest(**kwargs):
    return runner.create_reference_manifest(
        "authored-fixture", "prospective_fixture", 7, reference_id="authored-fixture-0.1",
        reference_source_sha256="a" * 64, **kwargs)


def test_authored_reference_uses_science_without_claiming_model_or_provider(tmp_path, numeric):
    manifest = reference_manifest(limits={"rounds": 4})
    client = ReferenceClient(manifest, successful_steps())
    report = runner.run_research(manifest, tmp_path / "reference", lambda _: client,
                                 analysis_factory=FakeAnalysis)
    assert report["status"] == "completed"
    assert report["requested_model"] is None and report["provider_reported_models"] == []
    assert report["client_kind"] == "scripted_reference"
    assert report["reference"] == manifest["reference"]
    assert report["autonomous_discovery"] is False
    assert report["usage"]["model_request_attempts"] == 0
    assert report["usage"]["reference_request_attempts"] == 4
    assert all(row["usage"] is None and row["provider"] == {} for row in report["rounds"])
    assert len(NumericProxy.calls) == 4
    kinds = [entry["kind"] for entry in receipts(tmp_path / "reference")]
    assert kinds.count("reference_request_started") == 4
    assert "model_request_started" not in kinds
    assert prospective.verify_directory(tmp_path / "reference/science")["replayed_tests"] == 1


@pytest.mark.parametrize("field", ["reference_id", "reference_source_sha256", "client_kind"])
def test_reference_identity_mismatch_stops_before_any_action_request(tmp_path, numeric, field):
    manifest = reference_manifest(limits={"rounds": 4})
    client = ReferenceClient(manifest, successful_steps())
    setattr(client, field, "wrong")
    report = runner.run_research(manifest, tmp_path / "reference", lambda _: client,
                                 analysis_factory=FakeAnalysis)
    assert report["status"] == "failed" and client.prompts == []
    assert report["usage"]["model_request_attempts"] == 0
    assert report["usage"]["reference_request_attempts"] == 0


@pytest.mark.parametrize("kind", ["token_usage", "provider_model", "provider_metadata"])
def test_reference_cannot_report_provider_or_token_usage(tmp_path, numeric, kind):
    manifest = reference_manifest(limits={"rounds": 4})

    class ContaminatedReference(ReferenceClient):
        def complete(self, encoded, *, system):
            value = super().complete(encoded, system=system)
            if kind == "token_usage":
                self.last_usage = {"total_tokens": 9}
            elif kind == "provider_model":
                self.last_response_metadata = {"provider_reported_models": ["gpt-5.6-sol"]}
            else:
                self.last_response_metadata = {"request_id": "unexpected"}
            return value

    client = ContaminatedReference(manifest, successful_steps())
    report = runner.run_research(manifest, tmp_path / "reference", lambda _: client,
                                 analysis_factory=FakeAnalysis)
    assert report["status"] == "failed"
    assert report["stop_reason"] == "reference_identity_metadata_mismatch"
    assert report["usage"]["reference_request_attempts"] == 1
    assert report["usage"]["research_action_attempts"] == 0
    assert report["provider_reported_models"] == []


def test_authored_policy_invalid_action_is_not_a_model_failure(tmp_path, numeric):
    manifest = reference_manifest(limits={"rounds": 4})
    client = ReferenceClient(manifest, [{"note": "invalid", "experiments": []}])
    report = runner.run_research(manifest, tmp_path / "reference", lambda _: client,
                                 analysis_factory=FakeAnalysis)
    assert report["status"] == "invalid_action"
    assert report["failure_attribution"] == "reference_policy"
    assert report["usage"]["model_request_attempts"] == 0


def test_api_client_path_cannot_accept_reference_identity(tmp_path, numeric):
    manifest = numeric(limits={"rounds": 4})
    client = FakeClient(manifest, successful_steps())
    client.client_kind = "scripted_reference"
    report = runner.run_research(manifest, tmp_path / "run", lambda _: client,
                                 analysis_factory=FakeAnalysis)
    assert report["status"] == "failed" and client.prompts == []


@pytest.mark.parametrize("field,value", [
    ("requested_model", "gpt-5.6-sol"), ("decoding", {"wire": "chat"}),
    ("client_kind", "model_api"), ("reference", {"id": "bad"}),
])
def test_reference_manifest_rejects_identity_contract_mutation(numeric, field, value):
    manifest = reference_manifest(limits={"rounds": 4})
    manifest[field] = value
    manifest["sha256"] = runner.digest({k: v for k, v in manifest.items() if k != "sha256"})
    with pytest.raises(ValueError):
        runner.validate_manifest(manifest)


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf"), 31])
def test_reference_request_timeouts_are_bounded(numeric, timeout):
    with pytest.raises(ValueError):
        reference_manifest(call_timeout_seconds=timeout)


def test_api_cli_rejects_reference_before_ledger_or_client(tmp_path, numeric, monkeypatch):
    import env.ledger as ledger
    import env.transport as transport

    def forbidden(*args, **kwargs):
        raise AssertionError("ledger or API client must never be constructed")

    monkeypatch.setattr(ledger, "CampaignLedger", forbidden)
    monkeypatch.setattr(transport, "CampaignClient", forbidden)
    manifest = tmp_path / "reference.json"
    manifest.write_text(json.dumps(reference_manifest(limits={"rounds": 4})))
    with pytest.raises(ValueError, match="API CLI does not execute"):
        runner._main(["run", "--manifest", str(manifest), "--model-config", str(tmp_path / "absent-config"),
                      "--ledger", str(tmp_path / "absent-ledger"), "--directory", str(tmp_path / "run")])
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("action", [{"experiments": []}, {"preregister": {"rivals": []}},
                                    {"preregister": {"rivals": [{"model_snapshot": {"name": "missing"}}]}}])
def test_invalid_scientific_actions_before_task_dispatch_close_without_retry(tmp_path, numeric, action):
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), [dict(action, note="bad plan")])
    assert report["status"] == "invalid_action"
    assert report["infrastructure_failure"] is None
    assert report["scientific_task"]["status"] != "active"
    assert report["usage"]["model_request_attempts"] == len(client.prompts) == 1


def test_partial_batch_retains_valid_data_and_invalid_second_spec_is_model_error(tmp_path, numeric):
    batch = {"note": "partial batch", "experiments": [observed()["experiments"][0], {"drive": 99, "times": [0, 1]}]}
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), [batch])
    assert report["status"] == "invalid_action" and report["infrastructure_failure"] is None
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 1
    assert len(report["history"][0]["observations"]) == 1
    assert prospective.verify_directory(tmp_path / "run/science")["replayed_tests"] == 0


def test_operator_kernel_valueerror_is_infrastructure_and_path_is_not_feedback(tmp_path, numeric, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("/private/operator-world-path CANARY")
    monkeypatch.setattr(prospective._FixtureWorld, "run", broken)
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), [observed])
    assert report["status"] == "failed" and report["infrastructure_failure"] == "scientific_operator_error"
    assert "CANARY" not in json.dumps(report) and "/private/operator-world-path" not in json.dumps(client.prompts)
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 1


def test_host_analysis_exception_is_infrastructure_not_model_error(tmp_path, numeric):
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), [{"note": "analysis", "analyze": {"code": "operator_error"}}])
    assert report["status"] == "failed" and report["infrastructure_failure"] == "action_execution_failed"
    assert "CANARY" not in json.dumps(report)
    assert report["usage"]["analysis_attempts"] == 1


def test_candidate_prediction_failure_is_charged_model_outcome(tmp_path, numeric, monkeypatch):
    class Broken(NumericProxy):
        def __call__(self, spec):
            raise RuntimeError("candidate error /private/CANARY")
    monkeypatch.setattr(prospective, "CandidateProxy", Broken)
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == "invalid_action" and report["infrastructure_failure"] is None
    assert report["scientific_task"]["usage"]["predictor_attempts"] == 1
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 1
    assert "CANARY" not in json.dumps(report)


@pytest.mark.parametrize("error, status, attribution, infrastructure", [
    (RuntimeError("sandbox unavailable /private/CANARY"), "failed", "infrastructure", "predictor_infrastructure_failure"),
    (runner.CandidateError("init failed /private/CANARY"), "initialization_unresolved", "unresolved", None),
    (TimeoutError("startup timeout /private/CANARY"), "invalid_action", "model", None),
])
def test_predictor_startup_attribution_is_not_forced_to_model_failure(tmp_path, numeric, monkeypatch,
                                                                    error, status, attribution, infrastructure):
    class BrokenStart:
        def __init__(self, *args, **kwargs):
            raise error
    monkeypatch.setattr(prospective, "CandidateProxy", BrokenStart)
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == status and report["failure_attribution"] == attribution
    assert report["infrastructure_failure"] == infrastructure
    assert report["scientific_task"]["usage"]["predictor_attempts"] == 1
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 1
    assert len(client.prompts) == 3 and "CANARY" not in json.dumps(report)
    if isinstance(error, TimeoutError):
        assert report["history"][-1]["error"] == "candidate_timeout"


@pytest.mark.parametrize("raw", ['{"note":"x","note":"duplicate","experiments":[]}',
                                 '{"note":"x","experiments":[{"drive":1e400}]}',
                                 '{"note":"\\ud800","experiments":[]}', "not json"])
def test_bad_json_consumes_turn_without_storage_infrastructure_failure(tmp_path, numeric, raw):
    report, client = run(tmp_path, numeric(limits={"rounds": 2}), [raw, {"note": "end", "finish": {}}])
    assert len(client.prompts) == 2
    assert report["status"] == "incomplete" and report["infrastructure_failure"] is None
    assert report["history"][0]["outcome"] == "invalid_action_json"
    assert report["scientific_task"]["status"] == "incomplete"


def test_unstorable_analysis_output_is_model_failure_not_disk_failure(tmp_path, numeric):
    steps = [{"note": "unicode", "analyze": {"code": "surrogate"}}, {"note": "end", "finish": {}}]
    report, _ = run(tmp_path, numeric(limits={"rounds": 2}), steps)
    assert report["infrastructure_failure"] is None
    assert report["history"][0]["analysis"]["error"] == "invalid_analysis_output"


def test_last_turn_scientific_action_is_not_dispatched(tmp_path, numeric):
    report, _ = run(tmp_path, numeric(limits={"rounds": 2}), ["bad json", observed])
    assert report["history"][-1]["error"] == "last_turn_requires_finish"
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 0


def test_api_failure_has_no_retry_or_stale_previous_usage(tmp_path, numeric):
    report, client = run(tmp_path, numeric(limits={"rounds": 4}), [observed, RuntimeError("/private/API-CANARY")])
    assert report["status"] == "failed" and report["infrastructure_failure"] == "model_transport_error"
    assert len(client.prompts) == 2 and report["rounds"][1]["usage"] is None
    assert "API-CANARY" not in json.dumps(report)
    assert report["scientific_task"]["status"] == "incomplete"


def test_late_final_artifact_failure_cannot_report_completion(tmp_path, numeric, monkeypatch):
    original = runner._atomic_json
    def fail_final(path, value, **kwargs):
        if Path(path).name == "final.json":
            raise OSError("/private/disk-CANARY")
        return original(path, value, **kwargs)
    monkeypatch.setattr(runner, "_atomic_json", fail_final)
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == "failed" and report["infrastructure_failure"] is not None
    assert report["final"] is None
    assert report["scientific_task"]["status"] == "completed"  # Evidence still exists.
    assert "disk-CANARY" not in json.dumps(report)
    assert json.loads((tmp_path / "run/report.json").read_text())["status"] == "failed"


def test_swallowed_snapshot_disk_failure_is_still_infrastructure(tmp_path, numeric, monkeypatch):
    def broken_persist(*args):
        raise ValueError("/private/snapshot-disk-CANARY")
    monkeypatch.setattr(runner.ModelSnapshots, "_persist", broken_persist)
    class CatchingAnalysis(FakeAnalysis):
        def run(self, *args):
            try:
                self.store.save_model("fit", "v1", {"slope": 1}, PREDICTOR)
            except ValueError:
                pass  # A sandbox can swallow its public callback exception.
            return {"ok": True, "result": "claimed success"}
    report, client = run(tmp_path, numeric(limits={"rounds": 4}),
                         [{"note": "save", "analyze": {"code": "save"}}], analysis=CatchingAnalysis)
    assert report["status"] == "failed" and report["infrastructure_failure"] is not None
    assert len(client.prompts) == 1 and report["usage"]["analysis_attempts"] == 1
    assert report["model_snapshots"] == [] and report["scientific_task"]["status"] == "incomplete"
    assert "CANARY" not in json.dumps(report)


@pytest.mark.parametrize("method", ["seal", "finish"])
def test_validated_finish_operator_valueerror_is_not_invalid_model_action(tmp_path, numeric, monkeypatch, method):
    def broken(*args):
        raise ValueError("/private/finish-CANARY")
    owner = runner.ModelSnapshots if method == "seal" else prospective.ProspectiveTask
    monkeypatch.setattr(owner, method, broken)
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == "failed" and report["infrastructure_failure"] == "action_execution_failed"
    assert report["final"] is None and report["scientific_task"]["status"] != "active"
    assert "CANARY" not in json.dumps(report)


def test_final_report_write_failure_returns_failure_and_retains_partial_evidence(tmp_path, numeric, monkeypatch):
    original = runner._atomic_json
    def fail_report(path, value, **kwargs):
        if Path(path) == tmp_path / "run/report.json":
            raise OSError("/private/report-CANARY")
        return original(path, value, **kwargs)
    monkeypatch.setattr(runner, "_atomic_json", fail_report)
    report, _ = run(tmp_path, numeric(limits={"rounds": 4}), successful_steps())
    assert report["status"] == "failed" and report["infrastructure_failure"] == "artifact_persistence_failed"
    assert not (tmp_path / "run/report.json").exists()
    assert (tmp_path / "run/science/bundle-private.json").exists()
    assert prospective.verify_directory(tmp_path / "run/science")["replayed_tests"] == 1
    assert "CANARY" not in json.dumps(report)


def test_client_configuration_mismatch_fails_before_first_request(tmp_path, numeric):
    manifest = numeric(limits={"rounds": 4})
    client = FakeClient(manifest, [])
    client.config.max_output_tokens += 1
    report = runner.run_research(manifest, tmp_path / "run", lambda _: client, analysis_factory=FakeAnalysis)
    assert report["status"] == "failed" and report["infrastructure_failure"] is not None
    assert client.prompts == [] and report["usage"]["model_request_attempts"] == 0
    assert report["scientific_task"]["status"] == "incomplete"


def test_provider_model_mismatch_does_not_dispatch_response_action(tmp_path, numeric):
    manifest = numeric(limits={"rounds": 4})
    class WrongProvider(FakeClient):
        def complete(self, *args, **kwargs):
            result = super().complete(*args, **kwargs)
            self.last_response_metadata = {"provider_reported_models": ["unfrozen-model"]}
            return result
    client = WrongProvider(manifest, [observed])
    report = runner.run_research(manifest, tmp_path / "run", lambda _: client, analysis_factory=FakeAnalysis)
    assert report["infrastructure_failure"] == "provider_model_mismatch"
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 0
    assert report["usage"]["model_request_attempts"] == 1


def test_cleanup_failure_does_not_skip_snapshot_seal_task_close_or_report(tmp_path, numeric):
    class BrokenClose(FakeAnalysis):
        def close(self):
            super().close()
            raise RuntimeError("/private/cleanup-CANARY")
    report, _ = run(tmp_path, numeric(limits={"rounds": 2}), ["bad", "bad"], analysis=BrokenClose)
    assert report["status"] == "failed" and report["infrastructure_failure"] == "cleanup_failed"
    assert report["cleanup_errors"] == ["analysis_close"]
    assert report["scientific_task"]["status"] == "incomplete"
    with pytest.raises(ValueError, match="frozen"):
        BrokenClose.instances[-1].store.save_model("after", "v1", {})
    assert "cleanup-CANARY" not in json.dumps(report)
    assert (tmp_path / "run/report.json").exists()


def test_task_close_failure_preserves_in_memory_failure_report(tmp_path, numeric, monkeypatch):
    original = prospective.ProspectiveTask.close
    def close_then_fail(self, reason="driver_stopped"):
        original(self, reason)
        raise OSError("/private/close-CANARY")
    monkeypatch.setattr(prospective.ProspectiveTask, "close", close_then_fail)
    report, _ = run(tmp_path, numeric(limits={"rounds": 2}), ["bad", "bad"])
    assert report["status"] == "failed"
    assert "scientific_task_close" in report["cleanup_errors"]
    assert report["scientific_task"]["status"] == "incomplete"
    assert "close-CANARY" not in json.dumps(report)


def test_existing_directory_is_never_reused(tmp_path, numeric):
    directory = tmp_path / "run"
    directory.mkdir()
    (directory / "sentinel").write_text("unchanged")
    with pytest.raises(FileExistsError):
        runner.run_research(numeric(), directory, lambda _: pytest.fail("client created"))
    assert list(directory.iterdir()) == [directory / "sentinel"]


def test_cli_errors_do_not_print_operator_paths(capsys):
    assert runner.main(["run", "--manifest", "/private/CLI-CANARY.json", "--model-config", "absent", "--ledger", "absent", "--directory", "unused"]) == 1
    output = capsys.readouterr().out
    assert "CLI-CANARY" not in output and json.loads(output)["status"] == "failed"


def test_wall_expiry_during_response_prevents_late_experiment(tmp_path, numeric, monkeypatch):
    now = [100.]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    manifest = numeric(limits={"rounds": 4, "wall_seconds": 2}, science_limits={"wall_seconds": 2})
    def late(_):
        now[0] += 3
        return observed()
    report, client = run(tmp_path, manifest, [late])
    assert report["status"] == "incomplete" and report["infrastructure_failure"] is None
    assert len(client.prompts) == 1 and report["scientific_task"]["usage"]["experiment_attempts"] == 0


def test_analysis_wall_time_is_debited_even_when_adapter_does_not_update_it(tmp_path, numeric, monkeypatch):
    now = [100.]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    class SlowAnalysis(FakeAnalysis):
        def run(self, *args):
            now[0] += 2
            return {"ok": False, "error": "synthetic_failure"}
    report, client = run(tmp_path, numeric(limits={"rounds": 2, "analysis_seconds": 3}),
                         [{"note": "analysis", "analyze": {"code": "anything"}}, {"note": "end", "finish": {}}], analysis=SlowAnalysis)
    assert report["usage"]["analysis_seconds_actual"] == 2
    assert client.prompts[1]["analysis_seconds_remaining"] == 1


def test_failed_analysis_startup_still_debits_elapsed_budget(tmp_path, numeric, monkeypatch):
    now = [100.]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    def broken_factory(seconds):
        now[0] += 2
        raise RuntimeError("/private/startup-CANARY")
    report = runner.run_research(numeric(limits={"analysis_seconds": 3}), tmp_path / "run",
                                 lambda _: pytest.fail("client created"), analysis_factory=broken_factory)
    assert report["status"] == "failed" and report["infrastructure_failure"] is not None
    assert report["usage"]["analysis_startup_seconds"] == 2
    assert report["analysis_seconds_remaining"] == 1
    assert report["usage"]["model_request_attempts"] == 0
    assert "CANARY" not in json.dumps(report)


def test_science_budget_failure_is_not_infrastructure(tmp_path, numeric):
    manifest = numeric(limits={"rounds": 4}, science_limits={"experiments": 1})
    report, _ = run(tmp_path, manifest, [observed, observed])
    assert report["status"] == "incomplete" and report["infrastructure_failure"] is None
    assert report["scientific_task"]["usage"]["experiment_attempts"] == 1
    assert report["usage"]["research_action_attempts"] == 2


def test_no_host_candidate_execution_and_python38_syntax():
    tree = ast.parse(Path(runner.__file__).read_text(), feature_version=(3, 8))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "compile"} for node in ast.walk(tree))


@skip_unless_sandbox("bwrap")
def test_linux_real_analysis_snapshots_prospective_freeze_and_finish(tmp_path, fixture_environment):
    manifest = reference_manifest(limits={"rounds": 4, "analysis_seconds": 60, "wall_seconds": 300},
                                  science_limits={"wall_seconds": 300, "predictor_seconds_per_call": 30})
    secret = tmp_path / "operator-secret.json"
    secret.write_text('"private-canary"')
    code = ('from pathlib import Path\n'
            'assert not Path(%r).exists()\n' % str(secret) +
            'assert not Path(%r).exists()\n' % str(Path(runner.__file__).parent) +
            'assert "private_world_seed" not in str(problem)\n'
            'records[0]["observation"]["values"][0][0] = 9999\n'
            'history[0]["note"] = "MUTATED"\n'
            'save_model("rival-0", "v1", {"slope": 1.0}, %r)\n' % PREDICTOR +
            'save_model("rival-1", "v1", {"slope": 2.0}, %r)\n' % PREDICTOR +
            'result = list_models()\n')
    client = ReferenceClient(manifest, successful_steps(code))
    report = runner.run_research(manifest, tmp_path / "run", lambda _: client)
    assert report["status"] == "completed", report
    assert report["history"][1]["outcome"] == "analysis_ok"
    assert report["history"][2]["outcome"] == "both_candidates_refuted"
    assert report["history"][0]["note"] == "source evidence"
    assert report["history"][0]["observations"][0]["observation"]["values"][0][0] != 9999
    assert len(client.prompts) == 4
    assert report["requested_model"] is None and report["provider_reported_models"] == []
    assert report["usage"]["model_request_attempts"] == 0
    assert report["usage"]["reference_request_attempts"] == 4
    assert prospective.verify_directory(tmp_path / "run/science")["replayed_tests"] == 1
