"""Prospective discovery protocol without a correctness oracle."""
import copy
import argparse
import json
from unittest.mock import patch

import pytest

from sle.evidence_episode import EvidenceEpisodeSession, run_discovery_policy
from sle.scientific_episode import digest, run_llm, validate_episode_report


class ObservationsOnly:
    task_id = "Test/NoGroundTruth"
    budget_units = 8

    def __init__(self):
        self.calls = []
        self.phase = "exploration"

    def public_problem(self):
        return {"budget_units": self.budget_units}

    def action_cost(self, tool, arguments):
        if tool != "measure" or set(arguments) != {"partition"} or arguments["partition"] not in ("exploration", "replication"):
            raise ValueError("invalid")
        return 1

    def is_sealed_action(self, tool, arguments):
        self.action_cost(tool, arguments)
        return arguments["partition"] == "replication"

    def begin_confirmation(self):
        assert self.phase == "exploration"
        self.phase = "replication"

    def experiment(self, tool, arguments):
        assert arguments["partition"] == self.phase
        self.calls.append(copy.deepcopy(arguments))
        return {"value": 0.25 if self.phase == "exploration" else 0.3}

    def validate_claim(self, *args):
        raise AssertionError("GT submission validator must never be called")

    def confirm(self, *args):
        raise AssertionError("oracle confirmation must never be called")

    def evaluate(self, *args):
        raise AssertionError("GT evaluator must never be called")


def hypothesis(name):
    return {"id": name, "statement": "A bounded operational prediction for " + name,
            "rationale": "Two competing observed-response explanations.",
            "assumptions": ["measurement units are comparable"], "alternatives": ["the competing explanation"]}


def plan(name="test", phase="exploration"):
    return {"id": name, "phase": phase, "tool": "measure", "arguments": {"partition": phase},
            "rationale": "Check a prospectively specified contrast in observed measurements.",
            "measurement": {"path": ["value"], "reducer": "scalar"},
            "predictions": [
                {"hypothesis_id": "positive", "interval": [0.2, 0.4], "falsifiers": [[-0.1, 0.1]]},
                {"hypothesis_id": "null", "interval": [-0.1, 0.1], "falsifiers": [[0.2, 0.4]]}]}


def dossier(support=None):
    return {"claims": [{"hypothesis_id": "positive", "conclusion": "supported",
                        "support": support or [], "counterevidence": [], "tests": ["replication"],
                        "limitations": ["Compatibility does not establish a causal mechanism."]}],
            "replication_tests": ["replication"], "limitations": ["Protocol test, not a scientific finding."]}


def register(session, exploration=True):
    for name in ("positive", "null"):
        assert session.step({"action": "hypothesize", "hypothesis": hypothesis(name)})["ok"]
    if exploration:
        assert session.step({"action": "plan_test", "test": plan()})["ok"]
    assert session.step({"action": "plan_test", "test": plan("replication", "replication")})["ok"]


def rehash(report):
    previous = None
    for event in report["events"]:
        event["previous_sha256"] = previous
        event["sha256"] = digest({k: v for k, v in event.items() if k != "sha256"})
        previous = event["sha256"]
    report["sha256"] = digest({k: v for k, v in report.items() if k != "sha256"})
    return report


def completed():
    session = EvidenceEpisodeSession(ObservationsOnly())
    register(session)
    observed = session.step({"action": "experiment", "tool": "measure",
                             "arguments": {"partition": "exploration"}, "test_id": "test"})
    assert session.step({"action": "commit", "claim": dossier([observed["evidence_id"]])})["ok"]
    return session


def test_complete_multiround_discovery_uses_no_gt_and_reserves_replication():
    session = completed()
    report = session.report()
    assert report["status"] == "completed"
    assert report["metrics"]["ground_truth_used"] is False
    assert report["metrics"]["discovery_score"] is None
    assert report["metrics"]["claims"][0]["evidence_status"] == "evidence-supported"
    assert report["resources"]["experiment_units"] == 2
    assert report["metrics"]["prospective_checks"]["replication_checks_assessed"] == 1
    kinds = [entry["kind"] for entry in report["events"]]
    assert kinds.index("commit") < max(i for i, kind in enumerate(kinds) if kind == "native_observation")
    assert validate_episode_report(report)["status"] == "structurally_consistent"


def test_replication_is_sealed_even_if_called_without_a_plan():
    session = EvidenceEpisodeSession(ObservationsOnly())
    register(session)
    for extra in ({}, {"test_id": "replication"}):
        result = session.step({"action": "experiment", "tool": "measure",
                               "arguments": {"partition": "replication"}, **extra})
        assert result["error"] == "replication_requires_commit"
    assert session.units == 0 and session.environment.calls == []


def test_phase_disguising_plan_is_rejected_before_any_measurement():
    session = EvidenceEpisodeSession(ObservationsOnly())
    register(session, exploration=False)
    bad = plan("dishonest", "exploration")
    bad["arguments"]["partition"] = "replication"
    assert session.step({"action": "plan_test", "test": bad})["error"] == "invalid_discovery_entry"
    assert session.units == 0


def test_fabricated_analysis_evidence_cannot_support_a_claim():
    session = EvidenceEpisodeSession(ObservationsOnly(), analysis=lambda *args: {"evidence_id": "fabricated", "value": 0.3})
    register(session)
    assert session.step({"action": "analyze", "code": "result = 'fabricated'"})["ok"]
    result = session.step({"action": "commit", "claim": dossier(["fabricated"])})
    assert result["error"] == "invalid_discovery_dossier"
    assert session.state == "exploring" and session.metrics is None
    assert not session.step({"action": "native_observation", "value": 0.3})["ok"]


def test_analysis_artifact_is_linked_for_review_but_not_promoted_to_native_evidence():
    session = EvidenceEpisodeSession(ObservationsOnly(), analysis=lambda *args: {"ok": True, "result": 42})
    register(session, exploration=False)
    session.step({"action": "analyze", "code": "result = 42"})
    session.step({"action": "commit", "claim": dossier()})
    artifact = session.metrics["analysis_artifacts"][0]
    assert artifact["code_sha256"] == digest("result = 42")
    assert artifact["native_measurement"] is False
    assert artifact["replay_status"] == "not_replayed"
    axis = next(item for item in session.metrics["semantic_review"]["axes"] if item["axis"] == "reproducibility")
    assert axis["status"] == "unassessed"
    assert axis["available_references"]["analysis_artifacts"]
    validate_episode_report(session.report())


def test_replication_budget_checked_before_freezing_or_reading_sealed_data():
    environment = ObservationsOnly()
    environment.budget_units = 1
    session = EvidenceEpisodeSession(environment)
    register(session)
    session.step({"action": "experiment", "tool": "measure", "arguments": {"partition": "exploration"}})
    assert session.step({"action": "commit", "claim": dossier()})["error"] == "replication_budget_exceeded"
    assert session.state == "exploring" and environment.phase == "exploration"
    assert len(environment.calls) == 1


def test_tool_timeout_is_not_scored_as_failed_science():
    session = EvidenceEpisodeSession(ObservationsOnly())
    with patch("sle.evidence_episode.call_with_deadline", side_effect=TimeoutError):
        response = session.step({"action": "experiment", "tool": "measure", "arguments": {"partition": "exploration"}})
    assert response["error"] == "experiment_timeout"
    assert session.state == "budget_exhausted" and session.metrics is None
    assert session.units == 1
    validate_episode_report(session.report())


def test_reserved_replication_timeout_keeps_frozen_claim_and_no_scientific_grade():
    session = EvidenceEpisodeSession(ObservationsOnly())
    register(session, exploration=False)
    with patch("sle.evidence_episode.call_with_deadline", side_effect=TimeoutError):
        response = session.step({"action": "commit", "claim": dossier()})
    assert response["error"] == "replication_timeout"
    assert session.claim is not None and session.metrics is None
    assert session.state == "infrastructure_error"
    validate_episode_report(session.report())


def test_postcommit_edits_and_replication_data_access_cannot_reopen_episode():
    session = completed()
    digest_before = session.claim_sha256
    for action in ({"action": "hypothesize", "hypothesis": hypothesis("new")},
                   {"action": "commit", "claim": {}}):
        assert session.step(action)["error"] == "episode_closed"
    assert session.claim_sha256 == digest_before


def test_recomputed_review_rejects_rehashed_invented_outcomes():
    report = completed().report()
    report["metrics"]["ground_truth_used"] = True
    for event in report["events"]:
        if event["kind"] == "outcome":
            event["payload"]["metrics"] = report["metrics"]
    with pytest.raises(ValueError, match="recomputed"):
        validate_episode_report(rehash(report))


def test_native_evidence_must_match_the_actual_experiment_action():
    report = completed().report()
    native = next(event for event in report["events"] if event["kind"] == "native_observation")
    native["payload"]["action"]["arguments"]["partition"] = "replication"
    with pytest.raises(ValueError, match="experiment action"):
        validate_episode_report(rehash(report))


def test_evidence_mode_marker_cannot_be_removed_from_a_discovery_report():
    report = completed().report()
    report["binding"].pop("evaluation_mode")
    report["events"][0]["payload"]["binding"] = report["binding"]
    with pytest.raises(ValueError, match="mode binding"):
        validate_episode_report(rehash(report))


def test_null_discovery_has_no_fabricated_success_or_zero_denominator_score():
    session = EvidenceEpisodeSession(ObservationsOnly())
    assert session.step({"action": "commit", "claim": {"claims": [], "replication_tests": [], "limitations": []}})["ok"]
    metrics = session.metrics
    assert metrics["null_discovery"] is True and metrics["discovery_score"] is None
    assert metrics["process"]["support_citation_verification"]["value"] is None
    validate_episode_report(session.report())


def test_malformed_action_is_candidate_input_not_an_infrastructure_failure():
    session = EvidenceEpisodeSession(ObservationsOnly())
    for value in ([], {}, None, 123):
        assert session.step({"action": value})["error"] == "invalid_action"
    assert session.state == "exploring" and session.steps == 4


def test_rehashed_extra_charge_without_native_observation_is_rejected():
    report = completed().report()
    extra = {"seq": 0, "kind": "experiment_charge", "payload": {"units": 1, "tool": "measure"}}
    report["events"].append(extra)
    for seq, event in enumerate(report["events"]):
        event["seq"] = seq
    report["resources"]["experiment_calls"] += 1
    report["resources"]["experiment_units"] += 1
    with pytest.raises(ValueError, match="one native observation"):
        validate_episode_report(rehash(report))


def test_program_policy_receives_broker_actions_without_environment_handles():
    def solve(context, act):
        assert context["problem"]["discovery_contract"]["ground_truth_required"] is False
        for name in ("positive", "null"):
            assert act({"action": "hypothesize", "hypothesis": hypothesis(name)})["ok"]
        assert act({"action": "plan_test", "test": plan("replication", "replication")})["ok"]
        return dossier()
    report = run_discovery_policy(EvidenceEpisodeSession(ObservationsOnly()), solve)
    assert report["status"] == "completed"
    validate_episode_report(report)


def test_live_multiturn_actions_preserve_evidence_and_hide_review_metrics():
    actions = [{"action": "hypothesize", "hypothesis": hypothesis(name)} for name in ("positive", "null")]
    actions += [{"action": "plan_test", "test": plan("replication", "replication")},
                {"action": "commit", "claim": dossier()}]
    class FakeModel:
        last_usage = {}
        last_stop_reason = "stop"
        def __init__(self):
            self.prompts = []
        def complete(self, prompt, system):
            self.prompts.append(prompt)
            assert "ground-truth-free" in system
            return json.dumps(actions[len(self.prompts) - 1])
    model = FakeModel()
    report = run_llm(EvidenceEpisodeSession(ObservationsOnly()), model)
    assert report["status"] == "completed"
    assert len(model.prompts) == 4
    assert "evidence_status" not in "".join(model.prompts)
    validate_episode_report(report)


def cli_args(output_dir, *options):
    from sle.episode_cli import add_parser
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers())
    return parser.parse_args(["episode", "--task", "MeasurementAudit", "--baseline", "protocol",
                              "--output-dir", str(output_dir), *options])


@pytest.mark.parametrize("budget, expected_status, expected_units", [
    (32, "completed", 32), (31, "invalid_candidate", 16),
])
def test_cli_evidence_default_binds_and_enforces_total_replication_budget(
        tmp_path, capsys, budget, expected_status, expected_units):
    from sle.episode_cli import command
    directory = tmp_path.resolve() / "episode"
    args = cli_args(directory, "--experiment-budget", str(budget))
    assert args.evaluation_mode == "evidence"
    result = command(args)
    summary = json.loads(capsys.readouterr().out)
    report = json.loads((directory / "episode.json").read_text())
    assert result == (0 if expected_status == "completed" else 2)
    assert summary["status"] == report["status"] == expected_status
    assert report["binding"]["evaluation_mode"] == "evidence_only"
    assert report["binding"]["experiment_budget_override"] == budget
    assert report["resources"]["budget_units"] == budget
    assert report["resources"]["experiment_units"] == expected_units
    if expected_status == "completed":
        assert report["metrics"]["ground_truth_used"] is False
    else:
        assert report["claim"] is None and report["metrics"] is None
    validate_episode_report(report)


@pytest.mark.parametrize("budget", [0, -1, True])
def test_cli_rejects_invalid_operator_budget_before_measurements(tmp_path, budget):
    from sle.episode_cli import command
    args = cli_args(tmp_path.resolve() / "episode")
    args.experiment_budget = budget
    with pytest.raises(ValueError, match="positive integer"):
        command(args)


def test_cli_cannot_request_oracle_evaluation_from_observations_only(tmp_path):
    from sle.episode_cli import command
    args = cli_args(tmp_path.resolve() / "episode", "--evaluation-mode", "oracle")
    with pytest.raises(ValueError, match="no ground-truth evaluator"):
        command(args)
