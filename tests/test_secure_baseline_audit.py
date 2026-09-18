from scripts.run_secure_baseline import INVALID_SCORE, _infrastructure_failure

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_secure_baseline as baseline
from scripts import run_measurement_health_preflight as preflight
from sle.metric_visibility import search_visible_metrics
from sle.provenance import finalize_report_trust


def test_parallel_baselines_preserve_task_identity_repeats_and_hidden_drift(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    specs = []
    for name in ("A", "B"):
        path = tmp_path / (name + ".py")
        path.write_text(name)
        specs.append(SimpleNamespace(task_id=name, initial_program_path=path))
    barrier = Barrier(2)
    calls = {"A": 0, "B": 0}

    def run(spec, path, timeout_s):
        assert path == spec.initial_program_path
        calls[spec.task_id] += 1
        barrier.wait(timeout=10)
        return {"combined_score": 0.5, "valid": 1.0,
                "private": {"task": spec.task_id, "draw": calls[spec.task_id]}}

    monkeypatch.setattr(baseline, "evaluate_candidate", run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda spec: baseline._evaluate_spec(spec, 2, 5), specs))
    assert [row["task"] for row in rows] == ["A", "B"]
    for spec, row in zip(specs, rows):
        assert row["candidate_sha256"] == hashlib.sha256(spec.initial_program_path.read_bytes()).hexdigest()
        assert [run["repeat"] for run in row["runs"]] == [0, 1]
        assert [run["metrics"]["private"] for run in row["runs"]] == [
            {"task": spec.task_id, "draw": 1}, {"task": spec.task_id, "draw": 2}]
        assert row["deterministic"] is False
    assert calls == {"A": 2, "B": 2}


def raw_report(metrics):
    row = baseline._entry("Fixture/Task", "a" * 64, [
        {"repeat": index, "wall_seconds": 1.0, "metrics": item}
        for index, item in enumerate(metrics)
    ])
    report = {
        "schema_version": 1, "trust_status": "TRUSTED_SECURE_EVAL",
        "source_provenance": {"git_available": True, "git_revision": "b" * 40,
                              "source_tree_dirty": False, "source_changes": [],
                              "command": ["baseline", "--private-output", "/private/secret-location"]},
        "created_at": "fixture", "environment": {"python": "fixture"},
        "config": {"repeats": len(metrics), "timeout_s": 1}, "tasks": [row],
        "summary": baseline._summary([row]),
    }
    finalize_report_trust(report, row["deterministic"] and row["fail_closed_all"]
                          and not row["infrastructure_failure"])
    return report


def project(raw):
    return baseline.public_projection(raw, "c" * 64,
                                      {"git_revision": "d" * 40, "source_tree_dirty": False},
                                      {"unchanged": True})


def test_explicit_infrastructure_error_cannot_pass_as_candidate_rejection():
    assert _infrastructure_failure({
        "combined_score": INVALID_SCORE, "valid": 0.0,
        "infrastructure_failure": 1.0, "error_message": "sandbox unavailable",
    })
    assert _infrastructure_failure({"combined_score": INVALID_SCORE})
    assert not _infrastructure_failure({
        "combined_score": INVALID_SCORE, "valid": 0.0,
        "error_message": "candidate timeout", "candidate_failure_kind": "candidate_timeout",
    })
    assert not _infrastructure_failure({"combined_score": 0.0, "valid": 1.0})


def test_public_baseline_keeps_full_payload_determinism_and_original_provenance():
    first = {"combined_score": 0.5, "valid": 1.0,
             "per_instance": [{"true_parameter": "DO_NOT_PUBLISH_A"}]}
    second = dict(first, per_instance=[{"true_parameter": "DO_NOT_PUBLISH_B"}])
    raw = raw_report([first, second])
    original = copy.deepcopy(raw)
    public = project(raw)
    assert raw == original
    assert public["schema_version"] == 2
    assert public["source_provenance"]["git_revision"] == "b" * 40
    assert public["export_provenance"]["git_revision"] == "d" * 40
    assert public["private_evidence"]["sha256"] == "c" * 64
    assert public["tasks"][0]["deterministic"] is False
    assert public["execution_passed"] is False
    runs = public["tasks"][0]["runs"]
    assert runs[0]["metrics"] == runs[1]["metrics"] == search_visible_metrics(first)
    assert runs[0]["full_metrics_sha256"] != runs[1]["full_metrics_sha256"]
    assert runs[0]["nested_payload_sha256"] != runs[1]["nested_payload_sha256"]
    assert "DO_NOT_PUBLISH" not in json.dumps(public)
    assert "secret-location" not in json.dumps(public)


def test_diagnostics_and_nested_selection_values_are_not_published():
    metrics = {"combined_score": INVALID_SCORE, "valid": 0.0,
               "error_message": "DO_NOT_PUBLISH_EXCEPTION",
               "candidate_stdout": "DO_NOT_PUBLISH_STDOUT",
               "constraint_violations": {"secret": "DO_NOT_PUBLISH_PAYLOAD"},
               "infrastructure_failure": 1.0}
    public = project(raw_report([metrics, metrics]))
    assert "DO_NOT_PUBLISH" not in json.dumps(public)
    assert public["tasks"][0]["infrastructure_failure"] is True
    assert public["execution_passed"] is False
    assert public["summary"]["invalid_baseline_run_count"] == 2
    assert public["summary"]["malformed_candidate_evaluations"] == 0


def test_valid_baseline_condition_does_not_claim_malformed_coverage():
    public = project(raw_report([{"combined_score": 0.5, "valid": 1.0}] * 2))
    assert public["summary"]["fail_closed_count"] == 1
    assert public["summary"]["invalid_baseline_run_count"] == 0
    assert public["summary"]["malformed_candidate_evaluations"] == 0
    assert "observed baselines only" in public["fail_closed_scope"]
    assert public["determinism_excluded_metrics"] == ["runtime_s"]


@pytest.mark.parametrize("field", ["deterministic", "valid_all", "fail_closed_all", "infrastructure_failure"])
def test_export_rejects_decisions_inconsistent_with_full_private_metrics(field):
    raw = raw_report([{"combined_score": 0.5, "valid": 1.0}] * 2)
    raw["tasks"][0][field] = not raw["tasks"][0][field]
    with pytest.raises(ValueError, match="decisions disagree"):
        project(raw)


def test_export_rejects_missing_repeat_in_the_original_denominator():
    raw = raw_report([{"combined_score": 0.5, "valid": 1.0}] * 2)
    raw["tasks"][0]["runs"].pop()
    with pytest.raises(ValueError, match="repeat cells"):
        project(raw)


def test_private_original_has_strict_permissions_and_cannot_be_overwritten(tmp_path):
    path = tmp_path.resolve() / "private" / "original.json"
    with baseline._open_private(path) as handle:
        handle.write("original bytes")
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert baseline._private_path(path, existing=True) == path
    with pytest.raises(FileExistsError):
        baseline._open_private(path)
    assert path.read_text() == "original bytes"
    path.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        baseline._private_path(path, existing=True)


def test_private_directory_and_symlink_locations_fail_closed(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    directory = tmp_path / "shared"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)  # The operator host intentionally uses umask 077.
    with pytest.raises(ValueError, match="0700"):
        baseline._open_private(directory / "original.json")
    target = tmp_path / "private"
    target.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        baseline._open_private(link / "original.json")
    monkeypatch.setattr(baseline.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    with pytest.raises(ValueError, match="outside a Git"):
        baseline._open_private(target / "original.json")


def test_public_preflight_preserves_hidden_drift_and_seals_results():
    calls = iter(["DO_NOT_PUBLISH_A", "DO_NOT_PUBLISH_B"])
    hidden_values = iter([0.25, 0.75])
    noise = preflight._evaluate_repeated(None, Path("unused"), 2, 1,
        lambda *args: {"combined_score": 0.5, "valid": 1.0,
                       "heldout_secret_scalar": next(hidden_values),
                       "per_world": [{"true_parameter": next(calls)}]})
    report = {"schema_version": 1, "source_provenance": {"git_revision": "b" * 40},
              "tasks": [{"task": "Fixture/Task", "checks": {"fixed_artifact_noise": noise}}]}
    public = preflight.public_projection(report, "c" * 64)
    got = public["tasks"][0]["checks"]["fixed_artifact_noise"]
    assert noise["status"] == got["status"] == "fail"
    assert got["noise_span"] == 0
    assert got["exact_payload_match"] is False
    assert got["canonical_payload_sha256"] == noise["canonical_payload_sha256"]
    assert got["numeric_field_spans"] == {"combined_score": 0.0, "valid": 0.0}
    assert "heldout_secret_scalar" not in got["numeric_field_spans"]
    assert got["maximum_numeric_field_span"] == 0.5
    assert got["complete_numeric_field_spans_sha256"] == baseline._digest(noise["numeric_field_spans"])
    assert got["results"] == [{"combined_score": 0.5, "valid": 1.0}] * 2
    assert "DO_NOT_PUBLISH" not in json.dumps(public)
    assert "heldout_secret_scalar" not in json.dumps(public)
    assert "DO_NOT_PUBLISH" in json.dumps(report)


def test_public_preflight_does_not_expose_oracle_exception_text():
    def raises(*args):
        raise RuntimeError("DO_NOT_PUBLISH_EXCEPTION")
    noise = preflight._evaluate_repeated(None, Path("unused"), 2, 1, raises)
    public = preflight.public_projection({"schema_version": 1, "tasks": [
        {"checks": {"fixed_artifact_noise": noise}}]}, "c" * 64)
    assert noise["status"] == "fail"
    assert noise["infrastructure_failure_count"] == 2
    assert "DO_NOT_PUBLISH" not in json.dumps(public)


@pytest.mark.parametrize("kind", ["baseline_alias", "preflight_alias", "existing_markdown"])
def test_destination_conflicts_refuse_before_evaluation_and_preserve_originals(tmp_path, monkeypatch, kind):
    path = tmp_path.resolve() / "original.json"
    calls = []
    monkeypatch.setattr(baseline, "evaluate_candidate", lambda *a, **k: calls.append("baseline"))
    monkeypatch.setattr(preflight, "build_report", lambda *a, **k: calls.append("preflight"))
    if kind == "baseline_alias":
        argv = ["baseline", "--output", str(path), "--private-output", str(path.parent / "." / path.name)]
        main = baseline.main
    elif kind == "preflight_alias":
        argv = ["preflight", "--private-output", str(path), "--markdown-output", str(path)]
        main = preflight.main
    else:
        path.write_text("original bytes")
        argv = ["preflight", "--private-output", str(path.parent / "new.json"),
                "--markdown-output", str(path)]
        main = preflight.main
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises((ValueError, FileExistsError)):
        main()
    assert calls == []
    if kind == "existing_markdown":
        assert path.read_text() == "original bytes"
        assert not (path.parent / "new.json").exists()
    else:
        assert not path.exists()


def test_one_repeat_is_not_determinism_and_fresh_cli_refuses_before_execution(tmp_path, monkeypatch):
    raw = raw_report([{"combined_score": 0.5, "valid": 1.0}])
    assert raw["tasks"][0]["deterministic"] is False
    with pytest.raises(ValueError, match="at least two"):
        project(raw)
    calls = []
    monkeypatch.setattr(baseline, "evaluate_candidate", lambda *a, **k: calls.append("called"))
    monkeypatch.setattr(sys, "argv", ["baseline", "--output", str(tmp_path / "public.json"),
        "--private-output", str(tmp_path / "private.json"), "--repeats", "1"])
    with pytest.raises(SystemExit, match=">= 2"):
        baseline.main()
    assert calls == []
    assert not list(tmp_path.iterdir())


def test_private_export_binds_real_git_history_and_refuses_runtime_drift(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "repo"
    root.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
            cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
    git("init", "-q")
    (root / "sle").mkdir()
    runtime = root / "sle" / "runtime.py"
    runtime.write_text("version = 1\n")
    candidate = root / "candidate.py"
    candidate.write_text("pass\n")
    git("add", ".")
    git("commit", "-qm", "fixture source")
    source_revision = git("rev-parse", "HEAD")
    raw = raw_report([{"combined_score": 0.5, "valid": 1.0,
                       "per_world": [{"truth": "DO_NOT_PUBLISH"}]}] * 2)
    raw["source_provenance"]["git_revision"] = source_revision
    raw["tasks"][0]["candidate_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    private = tmp_path.resolve() / "private" / "original.json"
    original = json.dumps(raw).encode()
    with baseline._open_private(private) as handle:
        handle.write(original.decode())
    monkeypatch.setattr(baseline, "ROOT", root)
    monkeypatch.setattr(baseline, "list_tasks", lambda _: [SimpleNamespace(
        task_id="Fixture/Task", initial_program_path=candidate)])
    public_path = root / "experiments" / "public.json"
    public = baseline.export_private(private, public_path)
    assert public["source_provenance"]["git_revision"] == source_revision
    assert public["private_evidence"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert public["export_runtime_compatibility"]["changed_paths"] == []
    assert public["trusted_evidence"] is True
    assert "DO_NOT_PUBLISH" not in public_path.read_text()
    assert private.read_bytes() == original
    runtime.write_text("version = 2\n")
    git("add", "sle/runtime.py")
    git("commit", "-qm", "runtime changed")
    with pytest.raises(ValueError, match="runtime/task source changed"):
        baseline.export_private(private, root / "experiments" / "rejected.json")
    assert not (root / "experiments" / "rejected.json").exists()
    assert private.read_bytes() == original
