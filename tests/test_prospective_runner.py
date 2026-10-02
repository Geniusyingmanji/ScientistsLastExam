"""Operator tests use numeric stand-ins; Linux tests exercise actual isolation."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

from _sandbox_tools import skip_unless_sandbox
from env import prospective_runner as runner


class NumericProxy:
    """Read only a literal fixture coefficient; never execute candidate source."""
    instances = []

    def __init__(self, candidate, entrypoint, timeout_s, memory_mb, packages):
        self.path = Path(candidate)
        tree = ast.parse(self.path.read_text())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign))
        assert assignment.targets[0].id == "COEFFICIENT"
        self.coefficient = ast.literal_eval(assignment.value)
        self.arguments = (entrypoint, timeout_s, memory_mb, packages)
        self.specs, self.closed = [], False
        self.instances.append(self)

    def __call__(self, spec):
        self.specs.append(deepcopy(spec))
        return [[self.coefficient * spec["drive"] * time] for time in spec["times"]]

    def close(self, *, kill):
        assert kill
        self.closed = True


@pytest.fixture
def numeric_proxy(monkeypatch):
    NumericProxy.instances = []
    monkeypatch.setattr(runner, "CandidateProxy", NumericProxy)
    return NumericProxy


def entries(directory):
    return [json.loads(path.read_text()) for path in sorted((directory / "receipts").glob("[0-9]*.json"))]


def source(task):
    return task.observe_source({"drive": 0, "times": [0, 1, 2]})


def test_demo_seals_full_predictions_then_fresh_data_and_refinement(tmp_path, numeric_proxy):
    directory = tmp_path / "demo"
    result = runner.run_demo(directory)
    assert result["status"] == "completed", result
    assert [test["result"]["outcome"] for test in result["results"]] == [
        "both_candidates_refuted", "scoped_predictive_discrimination"]
    assert not result["mechanism_identified"] and not result["discovery_depth_certified"]
    assert result["usage"]["experiment_attempts"] == 17
    assert result["usage"]["experiment_units"] == 17
    assert result["usage"]["predictor_attempts"] == 8
    assert result["usage"]["predictor_seconds_charged"] == 120
    assert len(numeric_proxy.instances) == 8
    assert all(proxy.closed and len(proxy.specs) == 1 for proxy in numeric_proxy.instances)
    assert all(proxy.arguments == ("predict", 15.0, 2048, ()) for proxy in numeric_proxy.instances)
    assert all(set(proxy.specs[0]) == {"drive", "times"} for proxy in numeric_proxy.instances)
    assert "private_world_seed" not in json.dumps(result)
    log = entries(directory)
    sealed, collecting = set(), set()
    for entry in log:
        if entry["kind"] == "prospective_event":
            event = entry["payload"]
            if event["kind"] == "registered":
                registration = event["payload"]
                sealed.add(registration["test_id"])
                assert all(rival["predictions"]["target"] for rival in registration["rivals"])
            elif event["kind"] == "collection_started":
                assert event["payload"]["test_id"] in sealed
                collecting.add(event["payload"]["test_id"])
            elif event["kind"] == "fresh_observation":
                assert event["payload"]["test_id"] in collecting
        elif entry["kind"] == "observation_attempt_started" and "obs-source" not in entry["payload"]["noise_key"]:
            assert collecting
    replay = runner.verify_directory(directory)
    assert replay["replayed_tests"] == 2
    assert replay["results"] == [test["result"] for test in result["results"]]
    bundle = json.loads((directory / "bundle-private.json").read_text())
    first, second = bundle["prospective"]["tests"]
    assert second["registration"]["revision_of"] == first["test_id"]
    assert second["registration"]["rivals"][1]["predictor_code"] != first["registration"]["rivals"][1]["predictor_code"]
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "operator-private.json").stat().st_mode) == 0o600
    assert all(stat.S_IMODE(proxy.path.stat().st_mode) == 0o444 for proxy in numeric_proxy.instances)
    assert not list(directory.rglob(".pending-*"))


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_directory_fails_closed_before_world_load(tmp_path, monkeypatch, symlink):
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "sentinel").write_text("unchanged")
    target = tmp_path / "link" if symlink else existing
    if symlink:
        target.symlink_to(existing, target_is_directory=True)
    monkeypatch.setattr(runner, "_FixtureWorld", lambda *_: pytest.fail("must not load world"))
    with pytest.raises(FileExistsError):
        runner.ProspectiveTask("prospective_fixture", 7, target)
    assert list(existing.iterdir()) == [existing / "sentinel"]


def test_budget_rejects_whole_plan_before_candidates_or_confirmations(tmp_path, numeric_proxy):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "budget", limits={"experiments": 8})
    source(task)
    with pytest.raises(runner.TaskBudgetExceeded):
        task.preregister(runner._fixture_request((1, 2), 1))
    assert not numeric_proxy.instances
    report = task.public_report()
    assert report["status"] == "failed" and report["error"] == "budget_exhausted"
    assert report["usage"]["actions"] == 2
    assert report["usage"]["experiment_attempts"] == 1


def test_candidate_failure_is_charged_sanitized_and_terminal(tmp_path, monkeypatch):
    class BrokenProxy(NumericProxy):
        def __call__(self, spec):
            raise RuntimeError("SECRET-candidate-error-canary")
    BrokenProxy.instances = []
    monkeypatch.setattr(runner, "CandidateProxy", BrokenProxy)
    directory = tmp_path / "broken"
    task = runner.ProspectiveTask("prospective_fixture", 7, directory)
    source(task)
    with pytest.raises(runner.CandidateExecutionFailed):
        task.preregister(runner._fixture_request((1, 2), 1))
    report = task.public_report()
    assert report["usage"]["predictor_attempts"] == 1
    assert report["usage"]["predictor_seconds_charged"] == 15
    assert report["usage"]["experiment_attempts"] == 1
    assert BrokenProxy.instances[0].closed
    assert "SECRET" not in json.dumps(report)
    before = entries(directory)
    with pytest.raises(RuntimeError, match="closed"):
        task.preregister(runner._fixture_request((1, 2), 1))
    assert entries(directory) == before
    assert runner.verify_directory(directory)["replayed_tests"] == 0


def test_failed_partial_collection_is_retained_and_never_rerun(tmp_path, monkeypatch, numeric_proxy):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "partial")
    source(task)
    original, calls = task._world.run, []
    def fail_second(spec, *, noise_key):
        calls.append(noise_key)
        if len(calls) == 2:
            raise RuntimeError("simulation failed")
        return original(spec, noise_key=noise_key)
    monkeypatch.setattr(task._world, "run", fail_second)
    with pytest.raises(RuntimeError, match="simulation failed"):
        task.preregister(runner._fixture_request((1, 2), 1))
    bundle = json.loads((task.directory / "bundle-private.json").read_text())
    assert bundle["status"] == "failed"
    assert bundle["usage"]["experiment_attempts"] == 3
    assert len(bundle["records"]) == 2
    attempt = bundle["prospective"]["tests"][0]
    assert attempt["status"] == "failed" and len(attempt["observations"]) == 1
    assert "result" not in attempt
    assert len(set(calls)) == 2
    with pytest.raises(RuntimeError, match="closed"):
        task.observe_source({"drive": 2, "times": [0, 1]})
    assert len(calls) == 2
    assert runner.verify_directory(task.directory)["replayed_tests"] == 0


def test_seal_storage_failure_prevents_fresh_sampling(tmp_path, monkeypatch, numeric_proxy):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "storage")
    source(task)
    original = task._journal.append
    def fail_seal(kind, payload):
        if kind == "prospective_event" and payload["kind"] == "registered":
            raise OSError("durable storage failed")
        return original(kind, payload)
    monkeypatch.setattr(task._journal, "append", fail_seal)
    with pytest.raises(OSError):
        task.preregister(runner._fixture_request((1, 2), 1))
    report = task.public_report()
    assert report["status"] == "failed"
    assert report["usage"]["predictor_attempts"] == 4
    assert report["usage"]["experiment_attempts"] == 1
    assert runner.verify_directory(task.directory)["replayed_tests"] == 0


@pytest.mark.parametrize("artifact", ["receipt", "metadata", "candidate", "head"])
def test_replay_rejects_tampering(tmp_path, numeric_proxy, artifact):
    directory = tmp_path / artifact
    runner.run_demo(directory)
    if artifact == "receipt":
        path = directory / "receipts" / "000001.json"
        value = json.loads(path.read_text())
        value["payload"]["limits"]["experiments"] += 1
    elif artifact == "metadata":
        path = directory / "operator-private.json"
        value = json.loads(path.read_text())
        value["private_world_seed"] += 1
    elif artifact == "head":
        path = directory / "receipts" / "head.json"
        value = json.loads(path.read_text())
        value["sequence"] -= 1
    else:
        path = next((directory / "candidates").iterdir())
        path.chmod(0o600)
        path.write_text("def predict(spec): return []\n")
        with pytest.raises(ValueError):
            runner.verify_directory(directory)
        return
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        runner.verify_directory(directory)


def test_atomic_publication_never_overwrites_and_removes_temporary(tmp_path):
    path = tmp_path / "receipt.json"
    runner._atomic_json(path, {"first": True})
    with pytest.raises(FileExistsError):
        runner._atomic_json(path, {"second": True})
    assert json.loads(path.read_text()) == {"first": True}
    assert not list(tmp_path.glob(".pending-*"))


def test_plan_cli_previous_refs_are_operator_resolved(tmp_path, numeric_proxy, capsys):
    initial = runner._fixture_request((1, 2), 1)
    revised = runner._fixture_request((1, 3), 2)
    revised.update(revision_of="$previous_test", change_note="Test revised law on another drive.")
    revised["rivals"][1]["evidence_ids"].append("$previous_fresh:0")
    plan = {"protocol": runner.PLAN_PROTOCOL, "source_experiments": [{"drive": 0, "times": [0, 1, 2]}],
            "tests": [initial, revised]}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    directory = tmp_path / "planned"
    assert runner.main(["run", "--environment", "prospective_fixture", "--seed", "5", "--directory", str(directory), "--plan", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][1]["result"]["outcome"] == "scoped_predictive_discrimination"
    assert runner.main(["verify", "--directory", str(directory)]) == 0
    assert json.loads(capsys.readouterr().out)["replayed_tests"] == 2


@pytest.mark.parametrize("changes", [{"max_tests": 9}, {"family_alpha": .1}, {"experiments": True}, {"wall_seconds": float("nan")}, {"unexpected": 1}])
def test_limits_are_bounded(changes):
    with pytest.raises(ValueError):
        runner._limits(changes)


def test_runner_contains_no_unisolated_execution():
    tree = ast.parse(Path(runner.__file__).read_text(), feature_version=(3, 8))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "compile"} for node in ast.walk(tree))


def test_candidate_mounts_only_leaf_and_runtime(tmp_path, monkeypatch):
    import sle.secure_eval as secure
    private = tmp_path / "private"
    private.mkdir()
    candidate = private / "candidate.py"
    candidate.write_text("def predict(spec): return []\n")
    monkeypatch.setattr(secure.shutil, "which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(secure, "_candidate_runtime", lambda: (Path("/runtime-test/python"), Path("/runtime-test/stdlib"), None))
    monkeypatch.setattr(secure, "_candidate_package_mounts", lambda _: [(Path("/runtime-test/numpy"), "/packages/numpy")])
    monkeypatch.setattr(secure, "_elf_dependency_mount_args", lambda *_: ())
    monkeypatch.setattr(secure, "_hidden_package_mount_args", lambda *_: ())
    monkeypatch.setattr(secure, "_proc_mount_args", lambda: ("--tmpfs", "/proc"))
    command = secure._sandbox_command(candidate, "predict", 10, ())
    sources = [command[i + 1] for i, value in enumerate(command) if value == "--ro-bind"]
    assert str(candidate) in sources
    assert str(private) not in sources
    assert "--unshare-all" in command and "65534" in command
    assert not any("operator-private" in path or "/env/" in path for path in sources)
    repo = str(Path(runner.__file__).resolve().parents[1])
    assert repo not in sources
    assert set(source for source in sources if source.startswith(repo)) == {
        str(secure.PACKAGE_DIR / name) for name in ("candidate_worker.py", "rpc_codec.py", "contract_lint.py", "__init__.py")}


@skip_unless_sandbox("bwrap")
def test_real_sandbox_demo_and_numeric_replay(tmp_path):
    directory = tmp_path / "real-demo"
    result = runner.run_demo(directory, limits={"predictor_seconds_per_call": 30.0})
    assert result["status"] == "completed", result
    assert result["results"][1]["result"]["outcome"] == "scoped_predictive_discrimination"
    assert runner.verify_directory(directory)["replayed_tests"] == 2


@skip_unless_sandbox("bwrap")
def test_real_sandbox_hides_operator_files_env_network_and_prior_process(tmp_path, monkeypatch):
    monkeypatch.setenv("SLE_PRIVATE_PROSPECTIVE_CANARY", "must-not-be-visible")
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "isolated", limits={"predictor_seconds_per_call": 30.0})
    source(task)
    code = '''COEFFICIENT = 1.0
COUNTER = 0
def predict(spec):
    import os
    import socket
    from pathlib import Path
    global COUNTER
    COUNTER += 1
    assert COUNTER == 1
    assert not Path(%r).exists()
    assert not Path(%r).exists()
    assert "SLE_PRIVATE_PROSPECTIVE_CANARY" not in os.environ
    assert set(spec) == {"drive", "times"}
    marker = Path("/tmp/prospective-marker")
    assert not marker.exists()
    marker.write_text("fresh process")
    try:
        os.fork()
    except PermissionError:
        pass
    else:
        raise AssertionError("fork unexpectedly allowed")
    try:
        Path("/work/candidate.py").write_text("mutate")
    except OSError:
        pass
    else:
        raise AssertionError("candidate was writable")
    sock = socket.socket()
    sock.settimeout(.2)
    try:
        sock.connect(("192.0.2.1", 9))
    except OSError:
        pass
    else:
        raise AssertionError("network unexpectedly reachable")
    finally:
        sock.close()
    return [[COEFFICIENT * spec["drive"] * t] for t in spec["times"]]
''' % (str(task.directory / "operator-private.json"), str(Path(runner.__file__).parent))
    request = runner._fixture_request((1, 2), 1)
    request["rivals"][0]["predictor_code"] = code
    task.preregister(request)
    assert task.finish()["status"] == "completed"
    assert runner.verify_directory(task.directory)["replayed_tests"] == 1


def test_expired_wall_budget_records_terminal_failure(tmp_path, monkeypatch):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "expired")
    monkeypatch.setattr(task, "_remaining_wall", lambda: 0)
    with pytest.raises(runner.TaskBudgetExceeded):
        source(task)
    assert task.public_report()["status"] == "failed"
    assert task.public_report()["error"] == "budget_exhausted"
    assert entries(task.directory)[-1]["kind"] == "task_failed"


def test_public_records_include_complete_fresh_data_without_keys(tmp_path, numeric_proxy):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "records")
    source(task)
    task.preregister(runner._fixture_request((1, 2), 1))
    records = task.public_records()
    assert len(records) == 9
    assert all(set(record) == {"id", "spec", "observation"} for record in records)
    records[0]["observation"]["values"][0][0] = 1234
    assert task.public_records()[0]["observation"]["values"][0][0] != 1234
    assert "noise_key" not in json.dumps(task.public_records())


def test_verifier_rejects_raw_confirmation_response_before_seal(tmp_path, numeric_proxy):
    directory = tmp_path / "order"
    runner.run_demo(directory)
    log = entries(directory)
    # Rehash a malformed operator log to exercise chronology, independently
    # of ordinary tamper detection. This is not claimed to authenticate a log.
    start = next(i for i, entry in enumerate(log) if entry["kind"] == "prospective_event" and entry["payload"]["kind"] == "registered")
    raw = next(i for i, entry in enumerate(log[start:], start) if entry["kind"] == "observation_returned")
    observation = log.pop(raw)
    log.insert(start, observation)
    previous = None
    for index, entry in enumerate(log, 1):
        entry.update(sequence=index, previous_sha256=previous)
        entry["sha256"] = runner.digest({k: v for k, v in entry.items() if k != "sha256"})
        previous = entry["sha256"]
        (directory / "receipts" / ("%06d.json" % index)).write_text(json.dumps(entry))
    (directory / "receipts" / "head.json").write_text(json.dumps({"sequence": len(log), "sha256": previous}))
    with pytest.raises(ValueError, match="observation before registration"):
        runner.verify_directory(directory)


def test_invalid_action_is_logged_and_cannot_be_retried(tmp_path):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "invalid")
    with pytest.raises(ValueError):
        task.observe_source({"drive": float("inf"), "times": [0, 1]})
    report = task.public_report()
    assert report["status"] == "failed" and report["usage"]["actions"] == 1
    assert report["usage"]["experiment_attempts"] == 0
    with pytest.raises(RuntimeError, match="closed"):
        source(task)


def test_limits_are_frozen_against_public_mapping_mutation(tmp_path):
    task = runner.ProspectiveTask("prospective_fixture", 7, tmp_path / "fixed-limits")
    limits = task.limits
    limits["experiments"] = 999999
    assert task.limits["experiments"] == runner.DEFAULT_LIMITS["experiments"]


def test_plan_tamper_is_detected(tmp_path, numeric_proxy):
    directory = tmp_path / "plan-tamper"
    plan = {"protocol": runner.PLAN_PROTOCOL,
            "source_experiments": [{"drive": 0, "times": [0, 1, 2]}],
            "tests": [runner._fixture_request((1, 2), 1)]}
    assert runner.run_plan("prospective_fixture", 7, directory, plan)["status"] == "completed"
    path = directory / "input-plan.json"
    plan["tests"][0]["scope"] = "tampered"
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="input plan"):
        runner.verify_directory(directory)
