"""Static JSON / inert executor tests. Never evaluate candidate source strings."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from env import analysis_replay as replay


def evidence():
    records = [{"id": "obs-0001", "spec": {"x": 1}, "observation": {"values": [[2]]}, "cost": 1},
               {"id": "obs-0002", "spec": {"x": 2}, "observation": {"values": [[3]]}, "cost": 1}]
    history = [
        {"round": 1, "note": "partial experiment", "observations": records[:1],
         "outcome": "invalid_action", "error": "later experiment failed"},
        {"round": 2, "note": "initialize", "analysis": {"ok": True, "result": {"k": 1}, "stdout": ""}, "outcome": "analysis_ok"},
        {"round": 3, "note": "first error", "analysis": {"ok": False, "error": "TypeError", "stdout": ""}, "outcome": "analysis_failed"},
        {"round": 4, "note": "later experiment", "observations": records[1:], "outcome": "observed obs-0002"},
        {"round": 5, "note": "second error", "analysis": {"ok": False, "error": "TypeError", "stdout": ""}, "outcome": "analysis_failed"},
        {"round": 6, "note": "later analysis", "analysis": {"ok": True, "result": None, "stdout": ""}, "outcome": "analysis_ok"},
    ]
    report = {"episode_id": "fixture", "history": history, "records": records,
              "experiment_count": 2, "limits": {"analysis_active_seconds": 60}, "rounds": [],
              "panels": {"private_target": "NEVER_COPY"}, "score": 99}
    transport, prior_records = [], []
    for index, turn in enumerate(history):
        n = turn["round"]
        prompt = {"round": n, "problem": {"public": "description"}, "limits": report["limits"],
                  "budget": {"analysis_active_seconds_remaining": 58, "wall_seconds_remaining": 800},
                  "observation_catalog": [{k: row[k] for k in ("id", "spec", "cost")} for row in prior_records],
                  "research_notes": [{"round": t["round"], "note": t["note"], "outcome": t["outcome"]} for t in history[:index]],
                  "recent_results": history[max(0, index-2):index]}
        action = {"note": turn["note"], "analyze": {"code": "THIS STRING MUST NEVER EXECUTE: " + str(n)}}
        request = {"messages": [{"role": "system", "content": "system"},
                                {"role": "user", "content": json.dumps(prompt)}]}
        report["rounds"].append({"round": n, "response": json.dumps(action),
                                 "prompt_sha256": replay.digest(prompt), "system_sha256": replay.digest("system")})
        transport.append({"event": "started", "attempt": n, "request": request,
                          "request_sha256": replay.digest(request, ascii=False)})
        prior_records.extend(turn.get("observations", []))
    return report, transport


def rebuild_request_hash(event):
    event["request_sha256"] = replay.digest(event["request"], ascii=False)


def test_exact_public_inputs_and_no_future_or_private_data():
    report, transport = evidence()
    original = deepcopy((report, transport))
    episode = replay.reconstruct(report, transport, [3, 5])
    assert [c["round"] for c in episode["calls"]] == [2, 3, 5]
    early, first, last = episode["calls"]
    assert len(early["payload"]["records"]) == len(first["payload"]["records"]) == 1
    assert len(last["payload"]["records"]) == 2
    assert early["payload"]["history"] == report["history"][:1]
    assert last["payload"]["history"] == report["history"][:4]
    assert "NEVER_COPY" not in json.dumps(episode)
    assert (report, transport) == original
    for call in episode["calls"]:
        assert call["payload_sha256"] == replay.digest(call["payload"])
        for field in ("problem", "records", "history", "code"):
            assert call["input_hashes"][field + "_sha256"] == replay.digest(call["payload"][field])


@pytest.mark.parametrize("mutation,category", [
    (lambda r, t: t[1].update(request_sha256="0" * 64), "request_hash_mismatch"),
    (lambda r, t: r["rounds"][1].update(prompt_sha256="0" * 64), "prompt_hash_mismatch"),
    (lambda r, t: r["rounds"][1].update(system_sha256="0" * 64), "system_hash_mismatch"),
    (lambda r, t: t.append(deepcopy(t[1])), "ambiguous_request_round"),
    (lambda r, t: t.pop(1), "missing_analysis_prompt"),
    (lambda r, t: r["records"].append({}), "complete_records_mismatch"),
    (lambda r, t: r["history"][0].update(round=2), "incomplete_round_sequence"),
    (lambda r, t: r.update(analysis_protocol="sle-analysis-snapshots-0.1"), "unsupported_snapshot_protocol"),
    (lambda r, t: r["history"][1]["analysis"].update(error="candidate_timeout"), "original_namespace_interrupted"),
])
def test_evidence_gaps_fail_closed(mutation, category):
    report, transport = evidence()
    mutation(report, transport)
    with pytest.raises(replay.EvidenceGap, match=category):
        replay.reconstruct(report, transport, [3, 5])


def test_catalog_cannot_introduce_later_records_even_with_valid_prompt_hashes():
    report, transport = evidence()
    event = transport[1]
    prompt = json.loads(event["request"]["messages"][1]["content"])
    prompt["observation_catalog"].append({k: report["records"][1][k] for k in ("id", "spec", "cost")})
    event["request"]["messages"][1]["content"] = json.dumps(prompt)
    rebuild_request_hash(event)
    report["rounds"][1]["prompt_sha256"] = replay.digest(prompt)
    with pytest.raises(replay.EvidenceGap, match="catalog_mismatch"):
        replay.reconstruct(report, transport, [3, 5])


def test_changed_or_partial_target_selection_rejected():
    with pytest.raises(replay.EvidenceGap, match="target_selection_changed"):
        replay.reconstruct(*evidence(), [3])


def test_duplicate_and_nonfinite_json_rejected():
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        with pytest.raises(replay.EvidenceGap):
            replay.strict_json(text)


class Clock:
    now = 0.

    def __call__(self):
        return self.now


class InertExecutor:
    """Returns declared receipts. It does not parse or execute payload['code']."""
    def __init__(self, clock, responses, calls, seconds=1):
        self.clock, self.responses, self.calls, self.seconds = clock, iter(responses), calls, seconds
        self.closed = False
        self.ordinal = 0

    def run(self, payload, allowance):
        self.ordinal += 1
        self.calls.append((deepcopy(payload), allowance, self.ordinal))
        self.clock.now += self.seconds
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        payload["history"].append({"fake_mutation": True})
        return response

    def close(self):
        self.closed = True


def test_single_persistent_executor_original_history_and_bounded_private_diagnostics():
    episode = replay.reconstruct(*evidence(), [3, 5])
    before = deepcopy(episode)
    responses = [deepcopy(c["original"]) for c in episode["calls"]]
    responses[1].update(message="PRIVATE_" * 1000, phase="result_serialization", candidate_line=None)
    responses[2].update(message="PRIVATE_LAST", phase="execution", candidate_line=7)
    clock, calls, factories = Clock(), [], []
    executor = InertExecutor(clock, responses, calls)

    def factory(seconds):
        factories.append(seconds)
        clock.now += 1  # Startup consumes the same episode allowance.
        return executor

    result = replay.replay_episode(episode, factory, clock)
    assert factories == [60]
    assert executor.closed and [c[2] for c in calls] == [1, 2, 3]
    assert episode == before
    assert calls[2][0]["history"] == episode["calls"][2]["payload"]["history"]
    assert "PRIVATE_" not in json.dumps(calls)
    assert len(result["events"][1]["private_message"]) == 600
    assert all(e["same_recorded_result"] for e in result["events"])
    assert [c[1] for c in calls] == [57.9995, 56.9995, 55.9995]
    assert result["events"][2]["same_error_type"]


def test_budget_exhaustion_never_restarts_or_retries_namespace():
    episode = replay.reconstruct(*evidence(), [3, 5])
    clock, calls = Clock(), []
    executor = InertExecutor(clock, [{"ok": True, "result": None}], calls, seconds=60)
    result = replay.replay_episode(episode, lambda _: executor, clock)
    assert len(calls) == 1
    assert [e["status"] for e in result["events"]] == ["returned", "budget_exhausted", "budget_exhausted"]


def test_executor_failure_stops_all_later_calls_and_does_not_leak_host_text():
    episode = replay.reconstruct(*evidence(), [3, 5])
    clock, calls = Clock(), []
    executor = InertExecutor(clock, [RuntimeError("HOST_SECRET")], calls)
    result = replay.replay_episode(episode, lambda _: executor, clock)
    assert len(calls) == 1 and executor.closed
    assert [e["status"] for e in result["events"]] == ["executor_failed", "namespace_unavailable", "namespace_unavailable"]
    assert "HOST_SECRET" not in json.dumps(result)


def test_cleanup_failure_retains_events_incrementally_and_marks_incomplete():
    episode = replay.reconstruct(*evidence(), [3, 5])
    clock, calls, persisted = Clock(), [], []

    class BadCleanup(InertExecutor):
        def close(self):
            assert len(persisted) == 3
            raise RuntimeError("SECRET_CLEANUP_TEXT")

    executor = BadCleanup(clock, [deepcopy(c["original"]) for c in episode["calls"]], calls)
    result = replay.replay_episode(episode, lambda _: executor, clock, persisted.append)
    assert len(result["events"]) == len(persisted) == 3
    assert result["cleanup_error"] == "RuntimeError" and result["complete"] is False
    assert "SECRET_CLEANUP_TEXT" not in json.dumps(result)
    plan = {"episodes": [{"target_rounds": [3, 5], "calls": episode["calls"]}]}
    summary = replay.public_summary(plan, [result],
              postcheck={"inputs_unchanged": True, "source_unchanged": True}, execution_finished=True)
    assert summary["status"] == "invalid" and summary["conclusions_valid"] is False
    assert summary["selected_target_events"] == 2 and summary["returned_prefix_calls"] == 3


def test_prefix_divergence_is_explicit_and_not_overwritten_by_same_error():
    episode = replay.reconstruct(*evidence(), [3, 5])
    clock, calls = Clock(), []
    responses = [deepcopy(c["original"]) for c in episode["calls"]]
    responses[0]["result"] = {"k": 2}
    executor = InertExecutor(clock, responses, calls)
    result = replay.replay_episode(episode, lambda _: executor, clock)
    assert result["events"][1]["same_error_type"]
    assert result["events"][1]["prefix_diverged_before_event"]


def test_public_allowlist_drops_raw_ids_messages_and_custom_error_labels():
    episode = replay.reconstruct(*evidence(), [3, 5])
    clock, calls = Clock(), []
    response = {"ok": False, "error": "SECRET_ERROR_LABEL", "message": "SECRET_MESSAGE", "phase": "SECRET_PHASE"}
    executor = InertExecutor(clock, [response] * 3, calls)
    result = replay.replay_episode(episode, lambda _: executor, clock)
    plan = {"episodes": [{"target_rounds": [3, 5], "calls": episode["calls"]}]}
    summary = replay.public_summary(plan, [result])
    serialized = json.dumps(summary)
    assert "SECRET" not in serialized and "fixture" not in serialized
    assert summary["target_error_categories"] == {"other": 2}
    assert summary["target_phase_categories"] == {"unknown": 2}


def test_gap_never_constructs_executor():
    def forbidden(_):
        pytest.fail("executor constructed for input gap")
    assert replay.replay_episode({"episode_id": "gap", "gap": "missing_analysis_prompt"}, forbidden)["events"] == []


def test_native_gate_rejects_mac_before_any_executor(tmp_path, monkeypatch):
    monkeypatch.setattr(replay.sys, "platform", "darwin")
    with pytest.raises(replay.EvidenceGap, match="native_bubblewrap_required"):
        replay.native_run(tmp_path, tmp_path / "absent.json", tmp_path / "out", "x", "y", replay.HOST)
    assert not (tmp_path / "out").exists()


def test_freeze_and_raw_hash_mismatch_precede_execution(tmp_path):
    report, transport = evidence()
    (tmp_path / "report.json").write_text(json.dumps(report))
    (tmp_path / "transport.jsonl").write_text("\n".join(json.dumps(e) for e in transport))
    episode = replay.reconstruct(report, transport, [3, 5])
    item = replay.episode_manifest(episode) | {"target_rounds": [3, 5], "report": "report.json", "transport": "transport.jsonl"}
    plan = {"protocol": replay.PROTOCOL, "budget_mode": "original_total_cap", "attempts_per_episode": 1,
            "episodes": [item], "raw_inputs": {n: replay.file_hash(tmp_path / n) for n in ("report.json", "transport.jsonl")}}
    assert replay.precheck(plan, tmp_path)[0] == episode
    item["calls"][0]["input_hashes"]["history_sha256"] = "0" * 64
    with pytest.raises(replay.EvidenceGap, match="frozen_public_input_mismatch"):
        replay.precheck(plan, tmp_path)
    (tmp_path / "report.json").write_text("{}")
    with pytest.raises(replay.EvidenceGap, match="raw_input_changed"):
        replay.precheck(plan, tmp_path)


def native_fixture(tmp_path, monkeypatch, episodes=1):
    """Fake the production boundary; no candidate, bwrap or source is executed."""
    root = tmp_path / "raw"
    root.mkdir()
    report, transport = evidence()
    (root / "report.json").write_text(json.dumps(report))
    (root / "transport.jsonl").write_text("\n".join(json.dumps(e) for e in transport))
    episode = replay.reconstruct(report, transport, [3, 5])
    entry = replay.episode_manifest(episode) | {"target_rounds": [3, 5], "report": "report.json", "transport": "transport.jsonl"}
    plan = {"protocol": replay.PROTOCOL, "budget_mode": "original_total_cap", "attempts_per_episode": 1,
            "episodes": [deepcopy(entry) for _ in range(episodes)],
            "raw_inputs": {n: replay.file_hash(root / n) for n in ("report.json", "transport.jsonl")}}
    plan_path = tmp_path / "plan.json"
    replay.write_new(plan_path, plan)
    bwrap = tmp_path / "inert-bwrap"
    bwrap.write_text("never execute")
    monkeypatch.setattr(replay.sys, "platform", "linux")
    monkeypatch.setattr(replay.shutil, "which", lambda _: str(bwrap))
    monkeypatch.setattr(replay.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(replay.importlib.metadata, "version", lambda _: "test-version")
    monkeypatch.setattr(replay, "source_fingerprint", lambda: {"files": {}, "sha256": "frozen-source"})
    args = (root, plan_path, tmp_path / "output", replay.file_hash(plan_path), "frozen-source", replay.HOST)
    return args, episode


def test_native_fake_cleanup_failure_continues_fixed_plan_without_retry(tmp_path, monkeypatch):
    args, episode = native_fixture(tmp_path, monkeypatch, episodes=2)
    calls, factories, clock = [], [], Clock()

    class BadCleanup(InertExecutor):
        def close(self):
            raise RuntimeError("private cleanup text")

    def factory(seconds):
        factories.append(seconds)
        return BadCleanup(clock, [deepcopy(c["original"]) for c in episode["calls"]], calls, seconds=0)

    monkeypatch.setattr(replay, "BubblewrapExecutor", factory)
    replay.native_run(*args)
    out = args[2]
    assert len(factories) == 2 and len(calls) == 6
    assert len(list(out.glob("episode-*-event-*-private.json"))) == 6
    summary = replay.read_json(out / "summary-public.json")
    assert summary["status"] == "invalid" and not summary["conclusions_valid"]
    assert summary["selected_episodes"] == 2 and summary["selected_target_events"] == 4
    assert summary["episodes_with_cleanup_error"] == 2


@pytest.mark.parametrize("change", ["input", "source"])
def test_native_fake_postcheck_failure_writes_invalid_summary_after_checks(tmp_path, monkeypatch, change):
    args, episode = native_fixture(tmp_path, monkeypatch)
    calls, clock = [], Clock()

    class MutatingCleanup(InertExecutor):
        def close(self):
            assert not (args[2] / "summary-public.json").exists()
            if change == "input":
                (args[0] / "report.json").write_text("changed synthetic fixture only")
            else:
                monkeypatch.setattr(replay, "source_fingerprint", lambda: {"files": {}, "sha256": "changed-source"})

    monkeypatch.setattr(replay, "BubblewrapExecutor", lambda _: MutatingCleanup(
        clock, [deepcopy(c["original"]) for c in episode["calls"]], calls, seconds=0))
    with pytest.raises(replay.EvidenceGap, match="inputs_or_source_changed_during_replay"):
        replay.native_run(*args)
    summary = replay.read_json(args[2] / "summary-public.json")
    assert summary["status"] == "invalid" and not summary["conclusions_valid"]
    assert summary["selected_target_events"] == 2 and summary["planned_prefix_calls"] == 3
    assert summary["returned_prefix_calls"] == 3


def test_native_fake_interruption_keeps_returned_event_and_full_denominators(tmp_path, monkeypatch):
    args, episode = native_fixture(tmp_path, monkeypatch, episodes=2)
    calls, clock = [], Clock()

    class Interrupted(InertExecutor):
        def run(self, payload, allowance):
            if self.ordinal == 1:
                raise KeyboardInterrupt()
            return super().run(payload, allowance)

    monkeypatch.setattr(replay, "BubblewrapExecutor", lambda _: Interrupted(
        clock, [deepcopy(c["original"]) for c in episode["calls"]], calls, seconds=0))
    with pytest.raises(KeyboardInterrupt):
        replay.native_run(*args)
    assert len(list(args[2].glob("episode-*-event-*-private.json"))) == 1
    summary = replay.read_json(args[2] / "summary-public.json")
    assert summary["status"] == "invalid" and not summary["conclusions_valid"]
    assert summary["selected_episodes"] == 2 and summary["selected_target_events"] == 4
    assert summary["planned_prefix_calls"] == 6 and summary["returned_prefix_calls"] == 1
    assert summary["target_status_counts"] == {"not_attempted": 4}
    # The claim survives interruption; another output directory cannot retry.
    retry_args = (*args[:2], tmp_path / "retry-output", *args[3:])
    with pytest.raises(FileExistsError):
        replay.native_run(*retry_args)


def test_no_exec_eval_world_api_or_scoring_imports():
    import ast
    tree = ast.parse(Path(replay.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile"}
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"env.runner", "env.analysis_worker", "env.scoring", "env.registry", "sle.posttest_transport"}


def test_exclusive_output_and_path_escape(tmp_path):
    path = tmp_path / "result.json"
    replay.write_new(path, {"one": 1})
    with pytest.raises(FileExistsError):
        replay.write_new(path, {"two": 2})
    with pytest.raises(replay.EvidenceGap, match="input_path_escape"):
        replay.input_path(tmp_path, "../escape")
