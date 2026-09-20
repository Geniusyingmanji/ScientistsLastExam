"""Adversarial schema-2 replay tests using invented observations only."""
import copy
import json

import pytest

from sle.posttest_episode import PostTestEvidenceSession
from sle.posttest_validation import validate_posttest_report
from sle.scientific_episode import EvidenceLimitError, digest, validate_episode_report


class FixtureEnvironment:
    task_id = "Fixture/TwoFreezes"
    budget_units = 4

    def __init__(self, fail=False):
        self.sealed = False
        self.fail = fail
        self.calls = 0

    def public_problem(self):
        return {"budget_units": self.budget_units, "question": "An invented bounded contrast."}

    def action_cost(self, tool, arguments):
        if tool != "measure" or arguments != {"partition": "replication"}:
            raise ValueError("fixture action")
        return 1

    def is_sealed_action(self, tool, arguments):
        self.action_cost(tool, arguments)
        return True

    def begin_confirmation(self):
        assert not self.sealed
        self.sealed = True

    def experiment(self, tool, arguments):
        assert self.sealed
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture unavailable")
        return {"value": 0.75}


def hypothesis(name):
    return {"id": name, "statement": "Invented prediction " + name,
            "rationale": "Test an invented descriptive contrast.",
            "assumptions": [], "alternatives": ["The competing invented prediction."]}


def frozen_session(fail=False):
    session = PostTestEvidenceSession(FixtureEnvironment(fail=fail), max_steps=8)
    for name in ("high", "low"):
        assert session.step({"action": "hypothesize", "hypothesis": hypothesis(name)})["ok"]
    test = {"id": "sealed", "phase": "replication", "tool": "measure",
            "arguments": {"partition": "replication"}, "rationale": "Distinguish the predictions.",
            "measurement": {"path": ["value"], "reducer": "scalar"},
            "predictions": [{"hypothesis_id": "high", "interval": [0.5, 1.0], "falsifiers": [[0.0, 0.4]]},
                            {"hypothesis_id": "low", "interval": [0.0, 0.4], "falsifiers": [[0.5, 1.0]]}]}
    assert session.step({"action": "plan_test", "test": test})["ok"]
    claim = {"claims": [{"hypothesis_id": "high", "conclusion": "inconclusive", "support": [],
                         "counterevidence": [], "tests": ["sealed"], "limitations": ["An invented fixture."]}],
             "replication_tests": ["sealed"], "limitations": []}
    result = session.step({"action": "commit", "claim": claim})
    assert result["ok"] is not fail
    return session


def interpretation(session):
    return {"plan_sha256": session.plan_sha256, "results_sha256": session.results_sha256,
            "test_responses": [{"test_id": "sealed", "evidence_id": "experiment-0001",
                                "predictions": [{"hypothesis_id": "high", "assessment": "compatible", "explanation": "Within interval."},
                                                {"hypothesis_id": "low", "assessment": "incompatible", "explanation": "Outside interval."}]}],
            "conclusions": [{"hypothesis_id": "high", "disposition": "retain", "statement": "A bounded descriptive compatibility.",
                             "scope": ["Invented fixture only."], "limitations": ["No population inference."],
                             "rationale": "The returned observation matches the interval.",
                             "evidence": [{"evidence_id": "experiment-0001", "role": "prospective_test"}]}],
            "posthoc_hypotheses": [], "limitations": []}


def completed_report():
    session = frozen_session()
    assert session.step({"action": "submit_interpretation", "interpretation": interpretation(session)})["ok"]
    return session.report()


def rehash(report):
    previous = None
    for seq, event in enumerate(report["events"]):
        event["seq"] = seq
        event["previous_sha256"] = previous
        event["sha256"] = digest({k: v for k, v in event.items() if k != "sha256"})
        previous = event["sha256"]
    report["sha256"] = digest({k: v for k, v in report.items() if k != "sha256"})
    return report


def event(report, kind):
    return next(item for item in report["events"] if item["kind"] == kind)


def test_two_freezes_replay_without_task_or_oracle_execution():
    report = completed_report()
    assert validate_posttest_report(report)["status"] == "structurally_consistent"
    assert validate_episode_report(report)["scientific_validity"] == "not_assessed"
    assert report["metrics"]["discovery_score"] is None
    assert all(axis["status"] == "unassessed" for axis in report["metrics"]["semantic_review"]["axes"])


def test_results_without_candidate_interpretation_remain_incomplete():
    session = frozen_session()
    report = session.report()
    assert report["status"] == "interpreting" and report["results"]["observations"]
    assert report["interpretation"] is None and report["metrics"] is None
    validate_posttest_report(report)
    session.stop("incomplete_delivery")
    validate_posttest_report(session.report())


def test_native_failure_preserves_charge_and_plan_without_fabricated_results():
    report = frozen_session(fail=True).report()
    assert report["status"] == "infrastructure_error"
    assert report["resources"]["experiment_calls"] == 1
    assert report["plan"] and report["results"] is None and report["metrics"] is None
    validate_posttest_report(report)


@pytest.mark.parametrize("kind", ["discovery_hypothesis", "discovery_test", "test_plan_committed",
                                  "sealed_results", "interpretation_submitted", "outcome"])
def test_duplicate_append_record_rejected_even_after_full_rehash(kind):
    report = completed_report()
    target = event(report, kind)
    report["events"].insert(target["seq"] + 1, copy.deepcopy(target))
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("kind", ["test_plan_committed", "experiment_charge", "native_observation",
                                  "sealed_results", "interpretation_submitted", "outcome"])
def test_deleting_a_required_record_rejected_after_full_rehash(kind):
    report = completed_report()
    report["events"].remove(event(report, kind))
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("field", ["plan", "results", "interpretation", "claim", "confirmation"])
def test_report_alias_cannot_diverge_from_events(field):
    report = completed_report()
    report[field] = None
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


def test_commit_action_cannot_retroactively_freeze_another_plan():
    report = completed_report()
    action = next(item for item in report["events"]
                  if item["kind"] == "action" and item["payload"].get("action") == "commit")
    action["payload"]["claim"]["claims"][0]["conclusion"] = "supported"
    with pytest.raises(ValueError, match="submitted action"):
        validate_posttest_report(rehash(report))


def test_unrecorded_hypothesis_cannot_enter_frozen_plan():
    report = completed_report()
    frozen = event(report, "test_plan_committed")["payload"]
    frozen["plan"]["hypotheses"].append(hypothesis("unregistered"))
    frozen["plan_sha256"] = digest(frozen["plan"])
    with pytest.raises(ValueError, match="registered history"):
        validate_posttest_report(rehash(report))


def test_rehashed_metrics_cannot_self_certify_scientific_review():
    report = completed_report()
    report["metrics"]["semantic_review"]["axes"][0]["status"] = "passed"
    event(report, "outcome")["payload"]["metrics"] = copy.deepcopy(report["metrics"])
    with pytest.raises(ValueError, match="replay"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("max_steps", [True, 1, 33, 1024])
def test_rehashed_report_cannot_expand_or_remove_interpretation_budget(max_steps):
    report = completed_report()
    report["resources"]["max_steps"] = max_steps
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


def test_posttest_action_cannot_be_replaced_by_a_research_action():
    report = completed_report()
    action = next(item for item in report["events"] if item["kind"] == "action"
                  and item["payload"].get("action") == "submit_interpretation")
    action["payload"] = {"action": "analyze", "code": "result = 1"}
    with pytest.raises(ValueError, match="sole action"):
        validate_posttest_report(rehash(report))


def test_native_observation_after_results_is_never_new_evidence():
    report = completed_report()
    charge = copy.deepcopy(event(report, "experiment_charge"))
    native = copy.deepcopy(event(report, "native_observation"))
    index = event(report, "sealed_results")["seq"] + 1
    report["events"][index:index] = [charge, native]
    report["resources"]["experiment_calls"] += 1
    report["resources"]["experiment_units"] += 1
    with pytest.raises(ValueError, match="outside native execution"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("action_request", [{"action": "analyze", "code": "result = 1"},
                                     {"action": "experiment", "tool": "measure", "arguments": {"partition": "replication"}},
                                     {"action": "hypothesize", "hypothesis": hypothesis("late")}])
def test_rejected_posttest_mutations_have_replayable_terminal_records(action_request):
    session = frozen_session()
    before = session.environment.calls
    assert not session.step(action_request)["ok"]
    assert session.done and session.environment.calls == before
    assert session.step({"action": "submit_interpretation", "interpretation": interpretation(session)})["error"] == "episode_closed"
    validate_posttest_report(session.report())


@pytest.mark.parametrize("action_request", [None, [], "not-an-object", 17, {"action": []}])
def test_invalid_bounded_actions_are_still_replayable_consumed_turns(action_request):
    session = PostTestEvidenceSession(FixtureEnvironment(), max_steps=8)
    assert not session.step(action_request)["ok"]
    session.stop("incomplete_delivery")
    report = session.report()
    assert report["resources"]["steps"] == 1
    validate_posttest_report(report)


@pytest.mark.parametrize("kind", ["interpretation_submitted", "outcome", "observation"])
def test_evidence_limit_during_final_freeze_does_not_produce_a_scientific_outcome(kind):
    session = frozen_session()
    original_record = session._record

    def limited_record(record_kind, payload):
        if record_kind == kind:
            session.recording_complete = False
            raise EvidenceLimitError("fixture evidence cap")
        original_record(record_kind, payload)

    session._record = limited_record
    assert session.step({"action": "submit_interpretation", "interpretation": interpretation(session)})["error"] == "evidence_limit"
    report = session.report()
    assert report["metrics"] is None and report["status"] == "evidence_limit"
    assert validate_posttest_report(report)["status"] == "incomplete_evidence"


@pytest.mark.parametrize("kind", ["test_plan_committed", "experiment_charge", "native_observation", "sealed_results"])
def test_evidence_limit_during_first_freeze_preserves_a_valid_incomplete_prefix(kind):
    actions = [item["payload"] for item in frozen_session().report()["events"] if item["kind"] == "action"]
    session = PostTestEvidenceSession(FixtureEnvironment(), max_steps=8)
    for action in actions[:-1]:
        assert session.step(action)["ok"]
    original_record = session._record

    def limited_record(record_kind, payload):
        if record_kind == kind:
            session.recording_complete = False
            raise EvidenceLimitError("fixture evidence cap")
        original_record(record_kind, payload)

    session._record = limited_record
    assert session.step(actions[-1])["error"] == "evidence_limit"
    report = session.report()
    assert report["metrics"] is None and report["status"] == "evidence_limit"
    assert validate_posttest_report(report)["status"] == "incomplete_evidence"


def test_broker_cannot_claim_complete_delivery_but_hide_sealed_results_from_candidate():
    report = completed_report()
    delivered = next(item for item in report["events"] if item["kind"] == "observation"
                     and "results" in item["payload"])
    delivered["payload"]["results"]["observations"] = []
    with pytest.raises(ValueError, match="full sealed result"):
        validate_posttest_report(rehash(report))


def test_final_candidate_response_must_bind_the_second_freeze():
    report = completed_report()
    report["events"][-1]["payload"]["interpretation_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="response mismatch"):
        validate_posttest_report(rehash(report))


def test_recorded_model_reply_binds_the_action_it_actually_requested():
    report = completed_report()
    first_action = event(report, "action")
    reply = {"seq": 0, "kind": "model_reply",
             "payload": {"text": json.dumps(first_action["payload"]), "usage": {}, "stop_reason": "stop"},
             "previous_sha256": None, "sha256": None}
    report["events"].insert(first_action["seq"], reply)
    validate_posttest_report(rehash(report))
    reply["payload"]["text"] = '{"action":"invalid"}'
    with pytest.raises(ValueError, match="recorded model response"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("field, value", [("observation", {"value": 999}), ("evidence_id", "fabricated"),
                                         ("charged_units", 3), ("remaining_units", 999)])
def test_exploration_delivery_binds_native_measurement_identity_and_budget(field, value):
    class ExploratoryEnvironment(FixtureEnvironment):
        def action_cost(self, tool, arguments):
            if tool != "measure" or arguments != {"partition": "exploration"}:
                raise ValueError("fixture action")
            return 1

        def is_sealed_action(self, tool, arguments):
            self.action_cost(tool, arguments)
            return False

        def experiment(self, tool, arguments):
            self.calls += 1
            return {"value": 0.25}

    session = PostTestEvidenceSession(ExploratoryEnvironment(), max_steps=8)
    assert session.step({"action": "experiment", "tool": "measure", "arguments": {"partition": "exploration"}})["ok"]
    session.stop("incomplete_delivery")
    report = session.report()
    validate_posttest_report(report)
    event(report, "observation")["payload"][field] = value
    with pytest.raises(ValueError, match="exploratory response"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("kind", ["discovery_hypothesis", "discovery_test"])
def test_registration_receipt_matches_the_entry_actually_appended(kind):
    report = completed_report()
    registered = event(report, kind)
    receipt = report["events"][registered["seq"] + 1]
    assert receipt["kind"] == "observation" and receipt["payload"]["ok"]
    receipt["payload"]["registered"]["id"] = "not-the-registered-entry"
    with pytest.raises(ValueError, match="exploratory response"):
        validate_posttest_report(rehash(report))


def test_completed_exploratory_measurement_can_be_undelivered_when_wall_budget_expires():
    now = [0.0]

    class SlowFixture(FixtureEnvironment):
        def action_cost(self, tool, arguments):
            return 1

        def is_sealed_action(self, tool, arguments):
            return False

        def experiment(self, tool, arguments):
            now[0] = 2.0
            return {"value": 0.25}

    session = PostTestEvidenceSession(SlowFixture(), max_steps=8, wall_seconds=1.0, clock=lambda: now[0])
    result = session.step({"action": "experiment", "tool": "measure", "arguments": {}})
    assert result == {"ok": False, "error": "budget_exhausted"}
    report = session.report()
    assert report["error"] == "wall_budget_exhausted"
    assert report["resources"]["experiment_calls"] == 1
    validate_posttest_report(report)


def transport_summary():
    return {"attempts": 5, "max_attempts": 8, "automatic_retries": 0,
            "failed_attempts": 0, "usage_on_missing_response": "unknown"}


@pytest.mark.parametrize("attempts, failed, maximum", [(0, 0, 0), (1, 1, 8), (8, 0, 8)])
def test_optional_transport_summary_preserves_attempt_budget_and_unknown_usage(attempts, failed, maximum):
    report = completed_report()
    report["model_transport"] = {**transport_summary(), "attempts": attempts,
                                 "failed_attempts": failed, "max_attempts": maximum}
    assert validate_posttest_report(rehash(report))["scientific_validity"] == "not_assessed"


@pytest.mark.parametrize("field", ["attempts", "max_attempts", "automatic_retries", "failed_attempts"])
@pytest.mark.parametrize("value", [True, False, -1, 1.0, "1", None])
def test_transport_counters_are_nonnegative_integers_not_boolean(field, value):
    report = completed_report()
    report["model_transport"] = {**transport_summary(), field: value}
    with pytest.raises(ValueError, match="transport count"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("changes", [{"failed_attempts": 6}, {"attempts": 9}, {"max_attempts": 9},
                                     {"max_attempts": 4}, {"automatic_retries": 1},
                                     {"usage_on_missing_response": 0}, {"usage_on_missing_response": "zero"}])
def test_transport_summary_cannot_hide_retries_expand_budget_or_zero_unknown_usage(changes):
    report = completed_report()
    report["model_transport"] = {**transport_summary(), **changes}
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("summary", [[], "summary", 0, False, {}])
def test_non_object_or_incomplete_transport_summary_is_rejected(summary):
    report = completed_report()
    report["model_transport"] = summary
    with pytest.raises(ValueError):
        validate_posttest_report(rehash(report))


def test_successful_public_measurement_requires_native_record_even_in_incomplete_episode():
    class ExplorationOnly(FixtureEnvironment):
        def action_cost(self, tool, arguments):
            return 1

        def is_sealed_action(self, tool, arguments):
            return False

        def experiment(self, tool, arguments):
            return {"value": 0.25}

    session = PostTestEvidenceSession(ExplorationOnly(), max_steps=8)
    assert session.step({"action": "experiment", "tool": "measure", "arguments": {}})["ok"]
    session.stop("incomplete_delivery")
    report = session.report()
    report["events"] = [item for item in report["events"]
                        if item["kind"] not in {"experiment_charge", "native_observation"}]
    report["resources"]["experiment_calls"] = report["resources"]["experiment_units"] = 0
    with pytest.raises(ValueError, match="successful exploration response lacks"):
        validate_posttest_report(rehash(report))


@pytest.mark.parametrize("action_kind, event_kind", [("hypothesize", "discovery_hypothesis"),
                                                    ("revise_hypothesis", "discovery_revision"),
                                                    ("plan_test", "discovery_test")])
def test_successful_registration_cannot_lose_its_native_entry(action_kind, event_kind):
    session = PostTestEvidenceSession(FixtureEnvironment(), max_steps=8)
    if action_kind == "hypothesize":
        session.step({"action": "hypothesize", "hypothesis": hypothesis("high")})
    elif action_kind == "revise_hypothesis":
        session.step({"action": "hypothesize", "hypothesis": hypothesis("high")})
        session.step({"action": "revise_hypothesis", "revision": {
            **hypothesis("revised"), "revises": "high", "revision_reason": "Narrow the invented claim."}})
    else:
        source_actions = [item["payload"] for item in frozen_session().report()["events"] if item["kind"] == "action"]
        for action in source_actions[:-1]:
            session.step(action)
    session.stop("incomplete_delivery")
    report = session.report()
    report["events"].remove(event(report, event_kind))
    with pytest.raises(ValueError, match="successful exploration response lacks"):
        validate_posttest_report(rehash(report))


def test_successful_analysis_cannot_lose_its_execution_record():
    session = PostTestEvidenceSession(FixtureEnvironment(), max_steps=8,
                                      analysis=lambda *args: {"ok": True, "result": 1})
    assert session.step({"action": "analyze", "code": "result = 1"})["ok"]
    session.stop("incomplete_delivery")
    report = session.report()
    report["events"].remove(event(report, "analysis_started"))
    report["resources"]["analysis_calls"] = 0
    with pytest.raises(ValueError, match="successful analysis response lacks"):
        validate_posttest_report(rehash(report))
