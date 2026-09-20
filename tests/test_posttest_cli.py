"""Protocol selection must not silently reuse historical baselines or budgets."""
import argparse
import hashlib
import json
from types import SimpleNamespace

import pytest

from sle import episode_cli


def null_claim():
    return {"claims": [], "replication_tests": [], "limitations": []}


def null_interpretation(committed):
    return {"plan_sha256": committed["plan_sha256"], "results_sha256": committed["results_sha256"],
            "test_responses": [], "conclusions": [], "posthoc_hypotheses": [], "limitations": []}


def arguments(directory, *options):
    parser = argparse.ArgumentParser()
    episode_cli.add_parser(parser.add_subparsers())
    return parser.parse_args([
        "episode", "--task", "MeasurementAudit", "--output-dir", str(directory),
        *options,
    ])


def forbid_setup(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("invalid protocol must be rejected before I/O or environment construction")
    for name in ("prepare_output", "source_binding", "create_environment"):
        monkeypatch.setattr(episode_cli, name, unexpected)


def test_protocol_default_preserves_v1_and_defers_step_default(tmp_path):
    args = arguments(tmp_path / "unused", "--actions", "unused.json")
    assert args.evaluation_mode == "evidence"
    assert args.evidence_protocol == "v1"
    assert args.max_steps is None


def test_listing_identifies_opt_in_protocol_without_starting_episode(capsys):
    parser = argparse.ArgumentParser()
    episode_cli.add_parser(parser.add_subparsers())
    args = parser.parse_args(["episode", "--list"])
    assert episode_cli.command(args) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing["default_evidence_protocol"] == "v1"
    assert listing["evidence_protocols"] == ["v1", "posttest-v2"]


def test_posttest_rejects_oracle_before_opening_private_resources(tmp_path, monkeypatch):
    forbid_setup(monkeypatch)
    args = arguments(tmp_path / "unused", "--actions", "unused.json",
                     "--evidence-protocol", "posttest-v2", "--evaluation-mode", "oracle")
    with pytest.raises(ValueError, match="requires --evaluation-mode evidence"):
        episode_cli.command(args)


def test_posttest_cannot_relabel_legacy_baseline_as_new_protocol(tmp_path, monkeypatch):
    forbid_setup(monkeypatch)
    args = arguments(tmp_path / "unused", "--baseline", "protocol",
                     "--evidence-protocol", "posttest-v2")
    with pytest.raises(ValueError, match="Existing evidence baselines use v1"):
        episode_cli.command(args)


@pytest.mark.parametrize("steps", [0, 1, 33, 64, -1, True, 2.5])
def test_posttest_budget_includes_interpretation_and_is_bounded(tmp_path, monkeypatch, steps):
    forbid_setup(monkeypatch)
    args = arguments(tmp_path / "unused", "--actions", "unused.json",
                     "--evidence-protocol", "posttest-v2")
    args.max_steps = steps
    with pytest.raises(ValueError, match="between 2 and 32, including final interpretation"):
        episode_cli.command(args)


def test_unknown_protocol_is_not_silently_downgraded(tmp_path, monkeypatch):
    forbid_setup(monkeypatch)
    args = arguments(tmp_path / "unused", "--actions", "unused.json")
    args.evidence_protocol = "posttest-v99"
    with pytest.raises(ValueError, match="unknown evidence protocol"):
        episode_cli.command(args)


@pytest.mark.parametrize("explicit_steps, expected", [(None, 64), (7, 7)])
def test_v1_replay_keeps_historical_schema_and_step_budget(tmp_path, capsys, explicit_steps, expected):
    actions_file = tmp_path / "manual-null.json"
    actions_file.write_text(json.dumps([{
        "action": "commit",
        "claim": {"claims": [], "replication_tests": [], "limitations": ["Manual protocol fixture only."]},
    }]), encoding="utf-8")
    directory = tmp_path.resolve() / "v1"
    options = ["--actions", str(actions_file)]
    if explicit_steps is not None:
        options += ["--max-steps", str(explicit_steps)]
    assert episode_cli.command(arguments(directory, *options)) == 0
    report = json.loads((directory / "episode.json").read_text())
    summary = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == 1
    assert report["binding"]["episode_protocol"] == "sle-scientific-episode-v1"
    assert report["resources"]["max_steps"] == expected
    assert report["resources"]["experiment_calls"] == 0
    assert report["metrics"]["discovery_score"] is None
    assert summary["evidence_protocol"] == "v1"


@pytest.mark.parametrize("explicit_steps, expected", [(None, 32), (2, 2), (32, 32)])
def test_posttest_empty_replay_saves_incomplete_schema2_without_fabricating_a_conclusion(
        tmp_path, capsys, explicit_steps, expected):
    actions_file = tmp_path / "manual-empty.json"
    actions_file.write_text("[]", encoding="utf-8")
    directory = tmp_path.resolve() / "posttest"
    options = ["--actions", str(actions_file), "--evidence-protocol", "posttest-v2"]
    if explicit_steps is not None:
        options += ["--max-steps", str(explicit_steps)]
    assert episode_cli.command(arguments(directory, *options)) == 2
    report = json.loads((directory / "episode.json").read_text())
    summary = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == 2
    assert report["status"] == "incomplete_delivery"
    assert report["resources"]["max_steps"] == expected
    assert report["resources"]["steps"] == report["resources"]["experiment_calls"] == 0
    assert report["metrics"] is None
    assert summary["evidence_protocol"] == "posttest-v2"


def test_posttest_replay_digest_placeholders_avoid_a_circular_file_hash(tmp_path, capsys):
    actions_file = tmp_path / "manual-two-freezes.json"
    interpretation = null_interpretation({"plan_sha256": "$commit.plan_sha256",
                                           "results_sha256": "$commit.results_sha256"})
    interpretation["limitations"] = ["$commit.plan_sha256"]
    actions_file.write_text(json.dumps([
        {"action": "commit", "claim": null_claim()},
        {"action": "submit_interpretation", "interpretation": interpretation},
    ]), encoding="utf-8")
    original = actions_file.read_bytes()
    directory = tmp_path.resolve() / "replay-report"
    args = arguments(directory, "--actions", str(actions_file),
                     "--evidence-protocol", "posttest-v2", "--max-steps", "2")
    assert episode_cli.command(args) == 0
    report = json.loads((directory / "episode.json").read_text())
    assert report["resources"]["steps"] == 2 and report["schema_version"] == 2
    assert report["binding"]["actions_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["binding"]["action_replay_substitutions"] == "posttest_digest_placeholders_v1"
    assert actions_file.read_bytes() == original
    final = report["interpretation"]
    assert final["plan_sha256"] == report["plan_sha256"]
    assert final["results_sha256"] == report["results_sha256"]
    assert final["limitations"] == ["$commit.plan_sha256"], "scientific content is never templated"
    actions = [event["payload"] for event in report["events"] if event["kind"] == "action"]
    assert actions[-1]["interpretation"] == final
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


def test_replay_placeholder_cannot_borrow_another_or_incomplete_freeze():
    action = {"action": "submit_interpretation", "interpretation": {
        "plan_sha256": "$commit.plan_sha256", "results_sha256": "$commit.results_sha256",
    }}
    for session in (SimpleNamespace(state="exploring", plan_sha256=None, results_sha256=None),
                    SimpleNamespace(state="testing", plan_sha256="a" * 64, results_sha256=None)):
        with pytest.raises(ValueError, match="this episode's completed plan and results freeze"):
            episode_cli._resolve_posttest_replay_action(action, session)


@pytest.mark.parametrize("self_submit", [False, True])
def test_posttest_program_routes_through_proxy_and_final_interpretation_runner(
        tmp_path, monkeypatch, capsys, self_submit):
    from sle import secure_eval

    proxies = []

    class FakeProxy:
        def __init__(self, candidate, name, timeout_s):
            assert candidate == program.resolve() and name == "solve"
            self.closed = False
            proxies.append(self)

        def __call__(self, context, act):
            assert context["problem"]["discovery_contract"]["ground_truth_required"] is False
            committed = act({"action": "commit", "claim": null_claim()})
            assert committed["ok"] and committed["episode_complete"] is False
            final = null_interpretation(committed)
            if self_submit:
                assert act({"action": "submit_interpretation", "interpretation": final})["ok"]
                return None
            return final

        def close(self):
            self.closed = True

    program = tmp_path / "not-executed.py"
    program.write_text("raise AssertionError('host execution is forbidden')\n", encoding="utf-8")
    monkeypatch.setattr(secure_eval, "CandidateProxy", FakeProxy)
    directory = tmp_path.resolve() / "program-report"
    args = arguments(directory, "--program", str(program), "--evidence-protocol", "posttest-v2",
                     "--max-steps", "2")
    assert episode_cli.command(args) == 0
    report = json.loads((directory / "episode.json").read_text())
    assert report["schema_version"] == 2 and report["status"] == "completed"
    assert report["resources"]["steps"] == report["resources"]["max_steps"] == 2
    assert report["resources"]["experiment_calls"] == 0
    assert report["interpretation"]["plan_sha256"] == report["plan_sha256"]
    assert report["interpretation"]["results_sha256"] == report["results_sha256"]
    assert len(proxies) == 1 and proxies[0].closed
    assert json.loads(capsys.readouterr().out)["mode"] == "program_interactive"


def test_posttest_mock_llm_gets_two_freezes_with_no_extra_interpretation_call(
        tmp_path, monkeypatch, capsys):
    import urllib.request
    from sle import config, posttest_transport

    configuration = SimpleNamespace(
        model="offline-fixture", wire="chat", temperature=None, reasoning_effort=None,
        max_output_tokens=1000, thinking_budget_tokens=None, stream=False,
        chat_reasoning_fallback=False, timeout_seconds=10,
    )
    models = []

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("CLI fixture must never open a real network request")

    class FakeLLM:
        last_usage = {}
        last_stop_reason = "stop"

        def __init__(self, configured, max_attempts):
            assert configured is configuration and max_attempts == 2
            self.calls = 0
            self.config = configured
            models.append(self)

        def transport_summary(self):
            return {"attempts": self.calls, "max_attempts": 2, "automatic_retries": 0,
                    "failed_attempts": 0, "usage_on_missing_response": "unknown"}

        def complete(self, prompt, system):
            self.calls += 1
            assert "ground-truth-free" in system
            if self.calls == 1:
                return json.dumps({"action": "commit", "claim": null_claim()})
            assert self.calls == 2, "interpretation must not create a third paid call"
            committed = json.loads(prompt)["history"][-1]["response"]
            return json.dumps({"action": "submit_interpretation",
                               "interpretation": null_interpretation(committed)})

    monkeypatch.setattr(config, "load_llm_client", lambda _path: SimpleNamespace(config=configuration))
    monkeypatch.setattr(posttest_transport, "PostTestLLMClient", FakeLLM)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_network)
    directory = tmp_path.resolve() / "mock-model-report"
    args = arguments(directory, "--llm-config", "never-opened-private-config",
                     "--analysis", "none", "--evidence-protocol", "posttest-v2", "--max-steps", "2")
    assert episode_cli.command(args) == 0
    report = json.loads((directory / "episode.json").read_text())
    assert len(models) == 1 and models[0].calls == report["resources"]["steps"] == 2
    assert report["binding"]["model_transport_policy"] == {"max_attempts": 2, "automatic_retries": 0}
    assert report["schema_version"] == 2 and report["status"] == "completed"
    assert len([event for event in report["events"] if event["kind"] == "model_reply"]) == 2
    assert json.loads(capsys.readouterr().out)["mode"] == "llm_interactive"
