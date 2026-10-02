"""Small authored-code fixtures; native material execution is an explicit opt-in.

In-process exec below is confined to fixed, trusted demo source in tests. It is
not an isolation test or an alternate production execution path.
"""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from env.analysis_api import ModelSnapshots, bind_parameters
from env.hysteresis_material import research_demo as demo
from env.hysteresis_material.protocol import validate_spec
from env.research_runner import SYSTEM, _parse


def public_fixture():
    """Independent analytic relaxation, no World, seed or private parameters."""
    rows = []
    for index, spec in enumerate(demo.source_specs()):
        h = spec["protocol"][0]["field"]
        initial = -1. if spec["reset"] == "negative" else 1.
        equilibrium = np.tanh(1.2*h)
        values = equilibrium+(initial-equilibrium)*np.exp(-np.array(spec["times"])/9.)
        rows.append({"id": "public-%02d" % index, "spec": spec,
                     "observation": {"axis": list(spec["times"]), "channels": ["response"],
                                     "values": values[:,None].tolist()}})
    return rows


def execute_authored_unit_code(records, store=None):
    store = store or ModelSnapshots()
    namespace = {"records": deepcopy(records), "save_model": store.save_model}
    # The code needs no problem, history, truth object, filesystem or seed.
    exec(compile(demo.ANALYSIS_CODE, "<authored-unit-fixture>", "exec"), namespace, namespace)
    return namespace["result"], store


@pytest.fixture(scope="module")
def fitted():
    return execute_authored_unit_code(public_fixture())


def prompt_for(number, fitted, outcome="inconclusive"):
    result, store = fitted
    records = public_fixture()
    return {"round": number, "phase": "finish_required" if number == 4 else "research",
            "observation_catalog": [{"id": r["id"], "spec": r["spec"]} for r in records],
            "model_snapshots": store.catalog(),
            "recent_results": [{"round": 2, "analysis": {"ok": True, "result": deepcopy(result)}}],
            "scientific_task": {"results": [{"test_id": "test-actual", "result": {
                "outcome": outcome, "mean_readout": .23, "confidence_interval": [.22, .24],
                "candidates": [{"id": name, "predicted_readout": float(index)}
                               for index, name in enumerate(demo.RIVALS)]}}]
                                if number == 4 else []}}


def test_fixed_public_design_and_reservations(fitted):
    specs = demo.source_specs()
    assert len(specs) == 8
    assert [validate_spec(spec) for spec in specs] == specs
    request = demo.comparison_request(prompt_for(3, fitted))
    targets = [experiment["spec"] for experiment in request["experiments"]]
    assert [validate_spec(spec) for spec in targets] == targets
    assert all(target not in specs for target in targets)
    assert all(target["protocol"] == [{"time": 0., "field": 0.}] for target in targets)
    assert len(specs)+len(targets)*request["replicates"] == demo.SCIENCE_LIMITS["experiments"]
    assert 4*len(targets) == demo.SCIENCE_LIMITS["predictor_calls"]
    assert 4*len(targets)*demo.SCIENCE_LIMITS["predictor_seconds_per_call"] == demo.SCIENCE_LIMITS["predictor_seconds"]
    assert request["replicates"] == 8 and demo.SCIENCE_LIMITS["max_tests"] == 1
    assert demo.DRIVER_LIMITS["rounds"] == 4
    assert all(term["row"] == 1 for term in request["readout"])


def test_isolated_sources_are_python38_self_contained_and_bounded():
    ast.parse(Path(demo.__file__).read_text(), feature_version=(3, 8))
    allowed = {"numpy", "scipy.integrate", "scipy.optimize"}
    for source in (demo.ANALYSIS_CODE, demo.PREDICTOR_CODE):
        tree = ast.parse(source, feature_version=(3, 8))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            if isinstance(node, ast.Name):
                assert node.id not in {"World", "seed", "open", "eval", "exec", "compile", "__import__"}
        assert imports <= allowed
        assert "env." not in source
    assert len(demo.ANALYSIS_CODE.encode()) <= 32000
    assert len(demo.PREDICTOR_CODE.encode()) <= 32768
    assert "max_nfev=80" in demo.ANALYSIS_CODE and "calls[0] > 500" in demo.ANALYSIS_CODE


def test_fit_records_only_matches_independent_analytic_fixture_and_snapshots(fitted):
    result, store = fitted
    assert result["failures"] == {} and set(result["models"]) == set(demo.RIVALS)
    relaxation = result["models"]["relaxation"]
    assert relaxation["source_rmse"] < 1e-12 and relaxation["optimizer_success"]
    for name, diagnostic in result["models"].items():
        assert diagnostic["optimizer_evaluations"] <= 80
        assert 1 <= diagnostic["residual_calls"] <= 500
        assert len(diagnostic["source_rmse_by_record"]) == 8
        body = store.read_model(name, "v1")
        assert body["reference"] == diagnostic["model_snapshot"]
        assert body["predictor_code"] == demo.PREDICTOR_CODE
        assert body["parameters"]["reset_response"] == {"negative": -1., "positive": 1.}
        changed = deepcopy(body["parameters"])
        changed["parameters"][0] += .01
        with pytest.raises(ValueError, match="already exists"):
            store.save_model(name, "v1", changed, demo.PREDICTOR_CODE)
        assert store.read_model(name, "v1")["parameters"] == body["parameters"]


def test_same_public_records_produce_identical_snapshot_hashes(fitted):
    second, store = execute_authored_unit_code(public_fixture())
    assert second == fitted[0]
    assert store.catalog() == fitted[1].catalog()


def test_unit_solver_matches_zero_field_analytic_limits():
    fixtures = [
        ({"kind": "relaxation", "parameters": [0.,1.,1.2,0.,9.],
          "reset_response": {"positive": 1., "negative": -1.}},
         lambda t: np.exp(-t/9.)),
        ({"kind": "cubic_memory", "parameters": [0.,0.,.1,.1,.07],
          "reset_response": {"positive": .4, "negative": -.4}},
         lambda t: np.sqrt(1./(1.+(1./.4**2-1.)*np.exp(-.2*t))))]
    for model, exact in fixtures:
        namespace = {}
        exec(bind_parameters(demo.PREDICTOR_CODE, model), namespace, namespace)
        for reset, sign in (("positive", 1.), ("negative", -1.)):
            spec = {"reset": reset, "preparation": [],
                    "protocol": [{"time": 0., "field": 0.}], "times": [0., .5, 5., 20., 80., 300.]}
            actual = np.array(namespace["predict"](spec))[:,0]
            expected = sign*exact(np.array(spec["times"]))
            assert np.allclose(actual, expected, atol=2e-6, rtol=2e-6)


@pytest.mark.parametrize("mutation", ["nan", "shape", "grid", "design", "duplicate_id", "target"])
def test_analysis_rejects_bad_or_post_test_record_sets_without_saving(mutation):
    records = public_fixture()
    if mutation == "nan":
        records[0]["observation"]["values"][1][0] = float("nan")
    elif mutation == "shape":
        records[0]["observation"]["values"][1] = [1., 2.]
    elif mutation == "grid":
        records[0]["observation"]["axis"][1] = .6
    elif mutation == "design":
        records[0]["spec"]["protocol"][0]["field"] = 0.
    elif mutation == "duplicate_id":
        records[1]["id"] = records[0]["id"]
    else:
        records.append(deepcopy(records[0]))
    store = ModelSnapshots()
    with pytest.raises(ValueError):
        execute_authored_unit_code(records, store)
    assert store.catalog() == []


def test_failed_fit_is_retained_and_never_substituted(monkeypatch):
    import scipy.optimize
    def failed(*args, **kwargs):
        raise RuntimeError("authored numerical fixture failure")
    monkeypatch.setattr(scipy.optimize, "least_squares", failed)
    result, store = execute_authored_unit_code(public_fixture())
    assert result["models"] == {} and set(result["failures"]) == set(demo.RIVALS)
    assert all(item["error"] == "RuntimeError" for item in result["failures"].values())
    assert store.catalog() == []
    with pytest.raises(ValueError, match="both frozen"):
        demo.comparison_request(prompt_for(3, (result, store)))


def test_finite_unconverged_fit_is_frozen_with_truthful_status(monkeypatch):
    import scipy.optimize
    monkeypatch.setattr(scipy.optimize, "least_squares", lambda residual, start, **kwargs:
                        SimpleNamespace(x=np.array(start), success=False, status=0, nfev=80))
    result, store = execute_authored_unit_code(public_fixture())
    assert not result["failures"] and len(store.catalog()) == 2
    request = demo.comparison_request(prompt_for(3, (result, store)))
    assert all(not value["optimizer_success"] for value in result["models"].values())
    assert all("optimizer_success=False" in rival["rationale"] for rival in request["rivals"])


def test_client_four_real_actions_honest_metadata_and_transport(tmp_path, fitted):
    client = demo.ScriptedReferenceClient(tmp_path, "a"*64)
    actions = []
    for number in range(1, 5):
        raw = client.complete(json.dumps(prompt_for(number, fitted, "both_candidates_refuted")), system=SYSTEM)
        actions.append(_parse(raw))
        assert client.last_usage is None and client.last_response_metadata == {}
        assert client.last_stop_reason == "reference_action"
    assert [set(row)-{"note"} for row in actions] == [{"experiments"}, {"analyze"}, {"preregister"}, {"finish"}]
    assert actions[1]["analyze"]["code"] == demo.ANALYSIS_CODE
    assert all("predictor_code" not in rival for rival in actions[2]["preregister"]["rivals"])
    assert "both_candidates_refuted" in actions[3]["finish"]["explanation"]
    assert '"mean_readout": 0.23' in actions[3]["finish"]["explanation"]
    assert "entire mechanism family" in actions[3]["finish"]["explanation"]
    assert actions[3]["finish"]["test_ids"] == ["test-actual"]
    assert len(list(tmp_path.glob("*-request.json"))) == 4
    assert len(list(tmp_path.glob("*-response.json"))) == 4
    assert not hasattr(client, "config") and not hasattr(client, "seed")
    with pytest.raises(ValueError, match="exactly four"):
        client.complete(json.dumps(prompt_for(4, fitted)), system=SYSTEM)


def test_receipt_tamper_and_missing_completed_test_fail_closed(fitted):
    prompt = prompt_for(3, fitted)
    prompt["recent_results"][0]["analysis"]["result"]["models"]["relaxation"]["model_snapshot"]["sha256"] = "f"*64
    with pytest.raises(ValueError, match="receipt differs"):
        demo.comparison_request(prompt)
    with pytest.raises(ValueError, match="actual completed test"):
        demo._finish(prompt_for(3, fitted))


def test_manifest_real_world_reference_identity_no_api_and_development_scope():
    manifest = demo.freeze_manifest(7, "material-unit-freeze")
    assert manifest["environment"] == "hysteresis_material"
    assert manifest["client_kind"] == "scripted_reference"
    assert manifest["requested_model"] is None and manifest["decoding"] == {}
    assert manifest["reference"]["id"] == demo.REFERENCE_ID
    assert manifest["reference"]["source_sha256"] == demo.reference_source_sha256()
    assert manifest["science_limits"]["predictor_calls"] == 8
    for seed in (8, -1, True):
        with pytest.raises(ValueError, match="development seeds"):
            demo.freeze_manifest(seed, "disallowed")


def test_operator_dispatches_real_runner_without_analysis_override(tmp_path, monkeypatch):
    from env import research_runner, prospective_runner
    manifest = demo.freeze_manifest(7, "material-dispatch-unit")
    received = {}
    def runner(frozen, output, factory, **kwargs):
        received.update(manifest=frozen, kwargs=kwargs)
        Path(output).mkdir()
        transport = Path(output)/"transport"
        transport.mkdir()
        client = factory(transport)
        assert set(vars(client)) == {"reference_source_sha256", "directory", "calls",
                                     "last_usage", "last_response_metadata", "last_stop_reason"}
        assert client.reference_source_sha256 == demo.reference_source_sha256()
        return {"status": "incomplete", "stop_reason": "unit-boundary", "infrastructure_failure": None,
                "usage": {"model_request_attempts": 0, "reference_request_attempts": 0},
                "elapsed_seconds": 0., "history": [], "scientific_task": {"results": []}}
    monkeypatch.setattr(research_runner, "run_research", runner)
    monkeypatch.setattr(prospective_runner, "verify_directory", lambda path: {"replayed_tests": 0, "receipt_count": 1})
    summary = demo.run_frozen(manifest, tmp_path/"run")
    assert received["manifest"] == manifest and received["kwargs"] == {}
    assert summary["status"] == "incomplete" and summary["outcomes"] == []
    encoded = json.dumps(summary)
    assert "seed" not in encoded and "parameters" not in encoded and "stratum" not in encoded


def test_demo_rejects_changed_plan_before_operator_execution(tmp_path, monkeypatch):
    from env import research_runner
    manifest = demo.freeze_manifest(7, "material-fixed-plan-unit")
    manifest["science_limits"]["replicates"] = 16
    monkeypatch.setattr(research_runner, "run_research", lambda *args, **kwargs: pytest.fail("must not dispatch"))
    with pytest.raises(ValueError, match="fixed development reference plan"):
        demo.run_frozen(manifest, tmp_path/"absent")
    assert not (tmp_path/"absent").exists()


def test_completed_report_cannot_use_real_incomplete_archive(tmp_path, monkeypatch):
    from env import research_runner, prospective_runner
    def stale_archive(frozen, output, factory):
        Path(output).mkdir()
        task = prospective_runner.ProspectiveTask("prospective_fixture", 7, Path(output)/"science")
        task.close("driver_stopped")
        scientific = task.public_report()
        scientific.update(status="completed", results=[{"test_id": "expected-test",
                                                       "result": {"outcome": "inconclusive"}}])
        return {"status": "completed", "stop_reason": "finished", "infrastructure_failure": None,
                "history": [], "elapsed_seconds": 0., "usage": {}, "scientific_task": scientific}
    monkeypatch.setattr(research_runner, "run_research", stale_archive)
    summary = demo.run_frozen(demo.freeze_manifest(7, "stale-science"), tmp_path/"boundary")
    assert summary["receipt_replay"]["archive_verified"]
    assert summary["receipt_replay"]["replayed_tests"] == 0
    assert not summary["receipt_replay"]["ok"]
    assert not summary["receipt_replay"]["completed_report_verified"]


@pytest.mark.parametrize("mismatch", [None, "verdict", "head", "state", "zero_completed"])
def test_completion_requires_exact_replayed_results_and_report_binding(tmp_path, monkeypatch, mismatch):
    from env import research_runner, prospective_runner
    result = {"outcome": "inconclusive", "mean_readout": .23, "confidence_interval": [.22, .24]}
    scientific = {"status": "completed", "receipt_head": "a"*64,
                  "results": [{"test_id": "test-one", "result": deepcopy(result)}]}
    checked = {"replayed_tests": 1, "receipt_count": 5, "receipt_head": "a"*64,
               "results": [deepcopy(result)]}
    if mismatch == "verdict":
        checked["results"][0]["mean_readout"] = .24
    elif mismatch == "head":
        checked["receipt_head"] = "b"*64
    elif mismatch == "state":
        scientific["status"] = "incomplete"
    elif mismatch == "zero_completed":
        scientific["results"] = []
        checked.update(replayed_tests=0, results=[])
    def runner(frozen, output, factory):
        Path(output).mkdir()
        return {"status": "completed", "stop_reason": "finished", "infrastructure_failure": None,
                "history": [], "elapsed_seconds": 0., "usage": {}, "scientific_task": scientific}
    monkeypatch.setattr(research_runner, "run_research", runner)
    monkeypatch.setattr(prospective_runner, "verify_directory", lambda path: checked)
    summary = demo.run_frozen(demo.freeze_manifest(7, "exact-science-binding"), tmp_path/"run")
    assert summary["receipt_replay"]["archive_verified"]
    assert summary["receipt_replay"]["ok"] is (mismatch is None)
    assert summary["receipt_replay"]["completed_report_verified"] is (mismatch is None)


def test_public_diagnostics_keep_errors_but_omit_fit_parameter_bodies(fitted):
    result = deepcopy(fitted[0])
    result["models"]["relaxation"]["parameters"] = [12345.6789]
    result["failures"] = {"deliberate-fixture": {"error": "ValueError", "residual_calls": 5}}
    report = {"history": [{"analysis": {"ok": True, "result": result}}],
              "scientific_task": {"results": [{"result": {"outcome": "inconclusive"}}]},
              "status": "completed", "stop_reason": "finished", "infrastructure_failure": None,
              "elapsed_seconds": 1., "usage": {"model_request_attempts": 0}}
    summary = demo._public_summary(report, {"ok": True})
    assert summary["outcomes"] == ["inconclusive"]
    assert summary["analysis_failures"] == [{"candidate": "deliberate-fixture", "error": "ValueError", "residual_calls": 5}]
    assert "parameters" not in json.dumps(summary) and "12345.6789" not in json.dumps(summary)


def test_cli_counts_wrapper_failure_without_retry_or_dropping_planned_case(tmp_path, monkeypatch):
    attempts = []
    def failed(manifest, directory):
        attempts.append(directory)
        raise RuntimeError("unit operator boundary")
    monkeypatch.setattr(demo, "run_frozen", failed)
    output = tmp_path/"cohort"
    assert demo.main(["--seeds", "7,46", "--output", str(output)]) == 1
    summary = json.loads((output/"summary-public.json").read_text())
    assert summary["planned_instances"] == summary["attempted_instances"] == len(attempts) == 2
    assert summary["completed_instances"] == summary["verified_completed_instances"] == 0
    assert summary["model_api_calls"] == 0
    assert all(row["status"] == "operator_wrapper_failed" for row in summary["rows"])
    with pytest.raises(FileExistsError):
        demo.main(["--seeds", "7,46", "--output", str(output)])
    assert len(attempts) == 2


@pytest.mark.skipif(sys.platform != "linux" or os.environ.get("SLE_RUN_MATERIAL_RESEARCH_NATIVE") != "1",
                    reason="explicit remote Linux native validation only; never local fallback")
def test_native_real_material_research_sequence(tmp_path):
    manifest = demo.freeze_manifest(7, "material-native-reference")
    summary = demo.run_frozen(manifest, tmp_path/"native")
    assert summary["status"] == "completed", summary
    assert summary["usage"]["model_request_attempts"] == 0
    assert summary["usage"]["reference_request_attempts"] == 4
    assert summary["science_usage"]["experiment_attempts"] == 24
    assert summary["receipt_replay"]["ok"] and summary["receipt_replay"]["replayed_tests"] == 1
    assert len(summary["outcomes"]) == 1
    assert set(summary["source_fit"]) == set(demo.RIVALS)
