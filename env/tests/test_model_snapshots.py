"""Candidate model persistence without model APIs, world access, or object loading."""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from env import analysis_worker
from env.analysis_api import LIMITS, PROTOCOL, ModelSnapshots, bind_parameters
from env.runner import DEFAULT_LIMITS, IsolatedAnalysis, run_episode


PREDICTOR = "def predict(spec):\n    return [[MODEL['slope'] * t] for t in spec['times']]\n"


def _reference(receipt):
    return {key: receipt[key] for key in ("name", "version", "sha256")}


def _submit(reference, **kwargs):
    return dict({"model_snapshot": reference, "claims": [], "explanation": "Fit saved from public data."}, **kwargs)


def test_model_snapshot_exact_json_roundtrip_detachment_and_immutable_version(tmp_path):
    store = ModelSnapshots(tmp_path / "models")
    parameters = {"slope": 2.75, "bounds": [None, True, "λ"]}
    receipt = store.save_model("fit", "v1", parameters, PREDICTOR)
    assert receipt == store.save_model("fit", "v1", parameters, PREDICTOR)
    parameters["slope"] = -99
    restored = store.read_model("fit", "v1")
    assert restored["parameters"]["slope"] == 2.75
    restored["parameters"]["slope"] = 100
    assert store.read_model("fit", "v1")["parameters"]["slope"] == 2.75
    with pytest.raises(ValueError, match="already exists"):
        store.save_model("fit", "v1", {"slope": 3}, PREDICTOR)
    assert len(store.catalog()) == 1
    path = tmp_path / "models" / (receipt["sha256"] + ".json")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
    assert json.loads(raw)["parameters"]["slope"] == 2.75
    assert (path.stat().st_mode & 0o777) == 0o600
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    with pytest.raises(FileExistsError):
        ModelSnapshots(path.parent)  # Never reopen another episode implicitly.


@pytest.mark.parametrize("parameter", [
    {"a": float("nan")}, {"a": float("inf")}, {"a": np.array([1.0])},
    {"a": (1, 2)}, {"a": {1, 2}}, {1: "bad key"}, {"a": 2**53},
    {"__fs_type__": "mapping"}, {"a": complex(1, 2)}, {"a": b"bytes"},
    {"a": "x" * (LIMITS["parameter_bytes"] + 1)}, [], None,
])
def test_model_snapshot_rejects_illegal_serialization_without_partial_write(tmp_path, parameter):
    store = ModelSnapshots(tmp_path / "models")
    with pytest.raises(ValueError):
        store.save_model("fit", "v1", parameter, PREDICTOR)
    assert store.catalog() == [] and list((tmp_path / "models").iterdir()) == []


def test_model_snapshot_depth_nodes_cycles_and_object_hooks_are_bounded(tmp_path):
    class ObjectGadget:
        def __reduce__(self):
            pytest.fail("no pickle/object hooks may execute")

        def __repr__(self):
            pytest.fail("no object repr may execute")

    store = ModelSnapshots(tmp_path / "models")
    deep = {}
    cursor = deep
    for _ in range(LIMITS["json_depth"] + 1):
        cursor["a"] = {}
        cursor = cursor["a"]
    cyclic = {}
    cyclic["self"] = cyclic
    for value in (deep, cyclic, {"a": [0] * LIMITS["json_nodes"]}, {"a": ObjectGadget()}):
        with pytest.raises(ValueError):
            store.save_model("fit", "v1", value)
    assert not store.catalog() and not list((tmp_path / "models").iterdir())


@pytest.mark.parametrize("name", ["../private", "/tmp/x", ".", "..", "x/y", "x\\y", "λ", "", "x" * 49, None])
def test_model_snapshot_names_are_not_filesystem_paths(name):
    with pytest.raises(ValueError):
        ModelSnapshots().save_model(name, "v1", {})


def test_model_snapshot_atomic_persistence_failures_and_existing_file(tmp_path, monkeypatch):
    import env.analysis_api as api
    store = ModelSnapshots(tmp_path / "models")
    for operation in ("fsync", "link"):
        with monkeypatch.context() as patch:
            def failure(*args, **kwargs):
                raise OSError("private path /operator/secret must not appear")
            patch.setattr(api.os, operation, failure)
            with pytest.raises(ValueError, match="^model snapshot persistence failed$"):
                store.save_model("fit", "v1", {"slope": 2.75}, PREDICTOR)
        assert store.catalog() == []
        assert list((tmp_path / "models").iterdir()) == []
    receipt = ModelSnapshots().save_model("fit", "v1", {"slope": 2.75}, PREDICTOR)
    collision = tmp_path / "models" / (receipt["sha256"] + ".json")
    collision.write_text("existing content")
    with pytest.raises(ValueError, match="persistence failed"):
        store.save_model("fit", "v1", {"slope": 2.75}, PREDICTOR)
    assert collision.read_text() == "existing content" and store.catalog() == []


def test_model_snapshot_count_bytes_attempts_and_seal():
    count_store = ModelSnapshots()
    for index in range(LIMITS["snapshots"]):
        count_store.save_model("fit", "v%d" % index, {})
    with pytest.raises(ValueError, match="storage allowance"):
        count_store.save_model("fit", "next", {})
    byte_store = ModelSnapshots()
    code = "#" + "x" * 30000 + "\n" + PREDICTOR
    for index in range(5):
        byte_store.save_model("fit", "v%d" % index, {"slope": 2.75, "padding": "a" * 15000}, code)
    with pytest.raises(ValueError, match="storage allowance"):
        byte_store.save_model("fit", "v5", {"slope": 2.75, "padding": "a" * 15000}, code)
    attempt_store = ModelSnapshots()
    for _ in range(LIMITS["callback_attempts"]):
        with pytest.raises(ValueError, match="unknown"):
            attempt_store.read_model("missing", "v1")
    with pytest.raises(ValueError, match="callback allowance"):
        attempt_store.save_model("fit", "v1", {})
    count_store.seal()
    for call in (lambda: count_store.list_models(), lambda: count_store.read_model("fit", "v0"),
                 lambda: count_store.save_model("fit", "vnew", {})):
        with pytest.raises(ValueError, match="frozen"):
            call()


def test_model_snapshot_malformed_callback_arguments_still_consume_allowance():
    store = ModelSnapshots()
    callbacks = store.callbacks()
    for _ in range(LIMITS["callback_attempts"]):
        with pytest.raises(TypeError):
            callbacks["save_model"](unexpected_keyword="value")
    with pytest.raises(ValueError, match="callback allowance"):
        callbacks["list_models"]()
    assert store.catalog() == []


def test_model_snapshot_reference_pins_version_and_parameters_can_bind_later_code():
    store = ModelSnapshots()
    first = store.save_model("fit", "v1", {"slope": 2.75})
    second = store.save_model("fit", "v2", {"slope": -0.5}, PREDICTOR)
    with pytest.raises(ValueError, match="no predictor code"):
        store.resolve_submission(_submit(_reference(first)))
    frozen, binding = store.resolve_submission(_submit(_reference(first), predictor_code=PREDICTOR))
    namespace = {}
    exec(frozen["predictor_code"], namespace)
    assert namespace["predict"]({"times": [0, 2]}) == [[0.0], [5.5]]
    assert binding["sha256"] == first["sha256"]
    assert binding["bound_source_sha256"] == hashlib.sha256(frozen["predictor_code"].encode()).hexdigest()
    bad_reference = dict(_reference(first), sha256=second["sha256"])
    with pytest.raises(ValueError, match="digest mismatch"):
        store.resolve_submission(_submit(bad_reference))
    with pytest.raises(ValueError, match="name, version, sha256"):
        store.resolve_submission(_submit({"name": "fit", "version": "v1"}))
    # Another episode cannot dereference even a correctly known name and digest.
    with pytest.raises(ValueError, match="unknown model"):
        ModelSnapshots().resolve_submission(_submit(_reference(first)))
    legacy = {"predictor_code": PREDICTOR, "claims": [], "explanation": "legacy"}
    assert store.resolve_submission(legacy) == (legacy, None)


def test_model_snapshot_json_binding_preserves_hostile_strings_and_future_imports(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    payload = "\"); __import__('pathlib').Path(%s).touch(); #" % json.dumps(str(sentinel))
    values = {"slope": 1.25, "text": payload, "unicode": "λ\n\"\\", "flags": [None, True, False]}
    source = bind_parameters('"""Example model."""\nfrom __future__ import annotations\n' + PREDICTOR, values)
    namespace = {}
    exec(source, namespace)
    assert namespace["MODEL"] == values
    assert namespace["predict"]({"times": [2]}) == [[2.5]]
    assert not sentinel.exists()
    for code in ("def broken(:", "x" * (LIMITS["code_bytes"] + 1), "from __future__ import annotations; x = MODEL\n" + PREDICTOR):
        with pytest.raises(ValueError):
            bind_parameters(code, values)


def test_model_snapshot_saving_and_binding_never_execute_candidate_code(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    source = "open(" + json.dumps(str(sentinel)) + ", 'w').write('executed')\n" + PREDICTOR
    store = ModelSnapshots(tmp_path / "models")
    receipt = store.save_model("untrusted-code", "v1", {"slope": 2}, source)
    store.resolve_submission(_submit(_reference(receipt)))
    assert not sentinel.exists()


class _PublicFitWorld:
    name, version, axis_field = "snapshot-fixture", "snapshot-fixture-1", "times"
    channels, scales, noise_std = ("y",), (1.0,), (0.0,)

    def describe(self):
        return {"name": self.name, "channels": ["y"], "scales": [1.0], "schema": {"times": "1..5 times between 0 and 5"}}

    def validate(self, spec):
        if set(spec) != {"times"} or not isinstance(spec["times"], list):
            raise ValueError("times required")
        return copy.deepcopy(spec)

    def cost(self, spec):
        return 1

    def run(self, spec, *, noise_key=None):
        return {"axis": spec["times"], "channels": ["y"], "values": [[2.75 * t] for t in spec["times"]]}

    def panel(self, seed, kind, count):
        return [{"times": [0, 0.7, 1.9]} for _ in range(count)]


class _WorkerShim:
    """Functional worker integration, deliberately no OS-isolation claim."""
    def __init__(self, seconds):
        self.remaining = seconds

    def bind_model_snapshots(self, store):
        self.store = store

    def run(self, code, problem, records, history):
        # Drop all local fitted variables each turn, as if the worker restarted.
        analysis_worker._namespace = {"__name__": "__scientific_analysis__"}
        return analysis_worker.analyze({"code": code, "problem": problem, "records": records,
                                        "history": history, "model_api": self.store.callbacks()})

    def close(self):
        pass


class _OfflineClient:
    def __init__(self):
        self.config = SimpleNamespace(model="offline", timeout_seconds=1)
        self.total_usage, self.last_usage, self.last_transport_error = {}, {}, None
        self.last_response_metadata = {"provider_reported_models": ["offline"]}
        self.last_stop_reason = "stop"
        self.prompts = []

    def complete(self, prompt, system):
        parsed = json.loads(prompt)
        self.prompts.append(parsed)
        turn = len(self.prompts)
        if turn == 1:
            action = {"experiments": [{"times": [0, 1, 2]}]}
        elif turn == 2:
            code = ("import numpy as np\nt = np.asarray(records[0]['observation']['axis'])\n"
                    "y = np.asarray(records[0]['observation']['values'])[:,0]\n"
                    "slope = float(t @ y / (t @ t))\n"
                    "save_model('fitted', 'v1', {'slope': slope}, " + json.dumps(PREDICTOR) + ")\n"
                    "raise ValueError('failure after successful save')")
            action = {"analyze": {"code": code}}
        elif turn == 3:
            assert parsed["model_snapshots"][0]["has_predictor_code"] is True
            action = {"analyze": {"code": "assert 'slope' not in globals()\nresult = read_model('fitted', 'v1')['parameters']"}}
        else:
            assert parsed["recent_results"][-1]["analysis"]["result"] == {"slope": 2.75}
            action = {"submit": _submit(_reference(parsed["model_snapshots"][0]))}
        return json.dumps(dict(note="Offline snapshot test", **action))

    def transport_summary(self):
        return {"attempts": len(self.prompts)}


def test_model_snapshot_real_fitting_error_restart_readback_and_final_reference(tmp_path, monkeypatch):
    client = _OfflineClient()
    monkeypatch.setattr("env.runner.load_world", lambda *args: (_PublicFitWorld(), lambda records, spec: [[0] for _ in spec["times"]]))
    monkeypatch.setattr("env.runner.source_digest", lambda: "test-source")
    instance = {"episode_id": "snapshot-test", "environment": "snapshot-fixture", "world_seed": 7654321,
                "panel_seed": 654321, "confirmation_key": "private-snapshot-canary", "analysis_protocol": PROTOCOL}
    limits = dict(DEFAULT_LIMITS, rounds=4, exploration_rounds=3, wall_seconds=300, verification_reserve_seconds=0, panel_count=1)

    def predict(path, spec, seconds):
        namespace = {}
        exec(path.read_text(), namespace)  # Only this test's fixed predictor fixture.
        assert "records" not in namespace and "world" not in namespace
        return namespace["predict"](spec)

    result = run_episode(instance, limits, tmp_path, client, analysis_factory=_WorkerShim, predict_fn=predict)
    assert result["status"] == "completed"
    assert result["score"] == pytest.approx(80.0)  # No claims, perfect prediction.
    assert result["history"][1]["outcome"] == "analysis_failed"
    assert result["frozen_model_snapshot"]["name"] == "fitted"
    assert result["frozen_model_snapshot"]["bound_source_sha256"] == hashlib.sha256((tmp_path / "predictor.py").read_bytes()).hexdigest()
    assert len(list((tmp_path / "model-snapshots").glob("*.json"))) == 1
    assert not any(secret in json.dumps(client.prompts) for secret in ("7654321", "654321", "private-snapshot-canary"))
    frozen = json.loads((tmp_path / "submission.json").read_text())
    assert set(frozen) == {"predictor_code", "claims", "explanation"}


def test_model_snapshot_callback_capabilities_are_removed_from_legacy_worker_call():
    analysis_worker._namespace = {"__name__": "__scientific_analysis__"}
    public = {"problem": {}, "records": [], "history": []}
    enabled = analysis_worker.analyze(dict(public, model_api=ModelSnapshots().callbacks(),
                                          code="result = callable(save_model)"))
    assert enabled["result"] is True
    legacy = analysis_worker.analyze(dict(public, code="result = 'save_model' in globals()"))
    assert legacy["result"] is False


def test_model_snapshot_protocol_is_explicit_and_unknown_version_never_calls_model(tmp_path, monkeypatch):
    monkeypatch.setattr("env.runner.load_world", lambda *args: (_PublicFitWorld(), lambda records, spec: [[0] for _ in spec["times"]]))
    monkeypatch.setattr("env.runner.source_digest", lambda: "test-source")
    client = _OfflineClient()
    instance = {"episode_id": "unknown-api", "environment": "snapshot-fixture", "world_seed": 1,
                "panel_seed": 2, "confirmation_key": "k", "analysis_protocol": "future-unknown"}
    report = run_episode(instance, DEFAULT_LIMITS, tmp_path, client, analysis_factory=_WorkerShim)
    assert report["status"] == "failed" and report["infrastructure_failure"] == "operator_runtime"
    assert client.prompts == []
    assert not (tmp_path / "model-snapshots").exists()


@pytest.mark.skipif(sys.platform != "linux" or shutil.which("bwrap") is None, reason="native CandidateProxy requires Linux and bubblewrap")
def test_model_snapshot_native_candidate_rpc_and_fresh_predictor_isolation(tmp_path):
    from sle.secure_eval import CandidateProxy
    private = tmp_path / "operator-secret.txt"
    private.write_text("operator-canary-unknown-to-candidate")
    store = ModelSnapshots(tmp_path / "models")
    analysis = IsolatedAnalysis(20)
    analysis.bind_model_snapshots(store)
    try:
        code = ("blocked = []\n"
                "for path in [" + json.dumps(str(private)) + ", '/work/instance-private.json']:\n"
                "    try:\n        open(path).read()\n        blocked.append(False)\n"
                "    except (FileNotFoundError, PermissionError):\n        blocked.append(True)\n"
                "save_model('native', 'v1', {'slope': 2.75}, " + json.dumps(PREDICTOR) + ")\n"
                "result = {'blocked': blocked, 'receipt': list_models()[0]}")
        outcome = analysis.run(code, {}, [], [])
        assert outcome["ok"] and outcome["result"]["blocked"] == [True, True]
        receipt = outcome["result"]["receipt"]
        restored = analysis.run("result = read_model('native', 'v1')['parameters']", {}, [], [])
        assert restored["result"] == {"slope": 2.75}
    finally:
        analysis.close()
    frozen, _ = store.resolve_submission(_submit(_reference(receipt)))
    store.seal()
    path = tmp_path / "predictor.py"
    path.write_text(frozen["predictor_code"])
    with CandidateProxy(path, "predict", timeout_s=20) as proxy:
        assert proxy({"times": [0, 2]}) == [[0.0], [5.5]]
