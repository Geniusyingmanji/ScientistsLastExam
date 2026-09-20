"""Two immutable boundaries with hand-authored observations; no API or real data."""
import copy
import json

import pytest

from sle.posttest_episode import PostTestEvidenceSession, run_posttest_policy
from sle.scientific_episode import digest, run_llm, validate_episode_report
from tests.test_evidence_episode import ObservationsOnly, hypothesis, plan, dossier, register


def frozen(environment=None, **kwargs):
    session = PostTestEvidenceSession(environment or ObservationsOnly(), **kwargs)
    register(session, exploration=False)
    response = session.step({"action": "commit", "claim": dossier()})
    assert response["ok"] and not response["episode_complete"]
    assert session.state == "interpreting" and session.metrics is None
    return session


def interpretation(session):
    responses = []
    tests = {test["id"]: test for test in session.plan["tests"]}
    for test_id, result in zip(session.claim["replication_tests"], session.results["observations"]):
        responses.append({"test_id": test_id, "evidence_id": result["evidence_id"],
            "predictions": [{"hypothesis_id": p["hypothesis_id"],
                "assessment": "compatible" if p["hypothesis_id"] == "positive" else "incompatible",
                "explanation": "Compare the observed scalar with the frozen interval."}
                for p in tests[test_id]["predictions"]]})
    return {"plan_sha256": session.plan_sha256, "results_sha256": session.results_sha256,
        "test_responses": responses,
        "conclusions": [{"hypothesis_id": claim["hypothesis_id"], "disposition": "retain",
            "statement": "The fixture observation is compatible with this interval.",
            "scope": ["Only the recorded fixture observation."], "limitations": ["No scientific truth or independent sample."],
            "rationale": "Retain only a bounded operational statement.",
            "evidence": [{"evidence_id": result["evidence_id"], "role": "prospective_test"}
                         for result in session.results["observations"]]}
            for claim in session.claim["claims"]],
        "posthoc_hypotheses": [], "limitations": ["Hand-authored protocol fixture."]}


def complete(session):
    response = session.step({"action": "submit_interpretation", "interpretation": interpretation(session)})
    assert response["ok"]
    return session.report()


def test_two_freezes_preserve_originals_and_keep_science_unassessed():
    session = frozen()
    first = copy.deepcopy((session.plan, session.results, session.claim))
    report = complete(session)
    assert session.state == "completed"
    assert (session.plan, session.results, session.claim) == first
    assert report["schema_version"] == 2
    assert report["metrics"]["discovery_score"] is None
    assert report["metrics"]["semantic_review"]["status"] == "unassessed"
    assert "conclusion_matches_operational_checks" not in json.dumps(report["metrics"])
    assert report["metrics"]["candidate_interpretation"]["coverage"]["value"] == 1
    assert validate_episode_report(report)["scientific_validity"] == "not_assessed"
    steps = session.steps
    assert session.step({"action": "submit_interpretation", "interpretation": {}})["error"] == "episode_closed"
    assert session.steps == steps


@pytest.mark.parametrize("attempted_action", [
    {"action": "experiment", "tool": "measure", "arguments": {"partition": "replication"}},
    {"action": "analyze", "code": "result = 1"},
    {"action": "hypothesize", "hypothesis": hypothesis("after")},
    {"action": "plan_test", "test": plan("new")},
    {"action": "commit", "claim": dossier()},
])
def test_posttest_tools_and_plan_edits_fail_without_new_measurements(attempted_action):
    session = frozen(analysis=lambda *_: pytest.fail("analysis must not execute"))
    before = copy.deepcopy((session.plan, session.results, session.environment.calls, session.ledger.snapshot()))
    assert session.step(attempted_action)["error"] == "interpretation_phase_is_read_only"
    assert session.done and session.metrics is None
    assert before == (session.plan, session.results, session.environment.calls, session.ledger.snapshot())
    assert session.step({"action": "submit_interpretation", "interpretation": interpretation(session)})["error"] == "episode_closed"
    validate_episode_report(session.report())


@pytest.mark.parametrize("corruption", ["plan_hash", "results_hash", "omit_test", "omit_prediction", "fake_evidence", "omit_claim", "validated_posthoc"])
def test_interpretation_cannot_omit_or_forge_evidence_or_posthoc_validation(corruption):
    session = frozen()
    value = interpretation(session)
    if corruption == "plan_hash": value["plan_sha256"] = "wrong"
    if corruption == "results_hash": value["results_sha256"] = "wrong"
    if corruption == "omit_test": value["test_responses"] = []
    if corruption == "omit_prediction": value["test_responses"][0]["predictions"].pop()
    if corruption == "fake_evidence": value["test_responses"][0]["evidence_id"] = "fabricated"
    if corruption == "omit_claim": value["conclusions"] = []
    if corruption == "validated_posthoc": value["posthoc_hypotheses"] = [{"id": "new", "statement": "A new idea.", "status": "validated"}]
    assert session.step({"action": "submit_interpretation", "interpretation": value})["error"] == "invalid_interpretation"
    assert session.metrics is None and session.interpretation is None
    assert session.plan and session.results
    validate_episode_report(session.report())


def test_wrong_prediction_interpretation_is_recorded_for_review_not_silently_corrected():
    session = frozen()
    value = interpretation(session)
    value["test_responses"][0]["predictions"][0]["assessment"] = "incompatible"
    value["posthoc_hypotheses"] = [{"id": "next", "statement": "Try another explanation in a new study.", "status": "posthoc_unvalidated"}]
    assert session.step({"action": "submit_interpretation", "interpretation": value})["ok"]
    response = session.metrics["candidate_interpretation"]["test_responses"][0]
    assert response["matches_measurement_check"] is False
    assert response["reasoning_quality"] == "unassessed"
    assert session.interpretation == value
    assert session.metrics["posthoc_hypotheses"][0]["status"] == "posthoc_unvalidated"
    validate_episode_report(session.report())


def test_unavailable_measurement_requires_response_but_is_not_model_failure():
    class Missing(ObservationsOnly):
        def experiment(self, tool, arguments):
            super().experiment(tool, arguments)
            return {"value": None, "status": "insufficient_samples"}
    session = frozen(Missing())
    value = interpretation(session)
    for prediction in value["test_responses"][0]["predictions"]:
        prediction["assessment"] = "unavailable"
    assert session.step({"action": "submit_interpretation", "interpretation": value})["ok"]
    assert all(row["matches_measurement_check"] for row in session.metrics["candidate_interpretation"]["test_responses"])
    assert session.metrics["discovery_score"] is None
    validate_episode_report(session.report())


def test_unrelated_prospective_observation_does_not_support_citation_role():
    session = PostTestEvidenceSession(ObservationsOnly())
    register(session, exploration=False)
    session.step({"action": "hypothesize", "hypothesis": hypothesis("unrelated")})
    claim = dossier()
    claim["claims"][0].update(hypothesis_id="unrelated", tests=[])
    assert session.step({"action": "commit", "claim": claim})["ok"]
    report = complete(session)
    role = report["metrics"]["evidence_roles"][0]
    assert role["native_reference"] and role["has_prospective_measurement"]
    assert not role["tests_claim_or_declared_component"]
    assert not role["requested_role_supported"]
    assert role["scientific_support"] == "requires_semantic_review"
    validate_episode_report(report)


@pytest.mark.parametrize("missing_condition", [False, True])
def test_frozen_compound_structure_exposes_necessary_failure_or_missing_condition(missing_condition):
    class DifferentPeriod(ObservationsOnly):
        def experiment(self, tool, arguments):
            super().experiment(tool, arguments)
            return {"value": 0.25 if self.phase == "exploration" or missing_condition else 0.0}
    session = PostTestEvidenceSession(DifferentPeriod())
    register(session)
    observed = session.step({"action": "experiment", "tool": "measure",
        "arguments": {"partition": "exploration"}, "test_id": "test"})
    structures = [{"hypothesis_id": "positive", "operator": "all_of", "components": [
        {"id": "two_periods", "statement": "Both registered periods satisfy the numeric constraint.",
         "hypothesis_id": "positive", "test_ids": ["test", "replication"]}]}]
    if missing_condition:
        structures[0]["components"].append({"id": "missing", "statement": "Another necessary condition.",
            "hypothesis_id": "null", "test_ids": []})
    assert session.step({"action": "commit", "claim": dossier([observed["evidence_id"]]),
                         "structures": structures})["ok"]
    report = complete(session)
    claim = next(row for row in report["metrics"]["compound_claims"]["claims"] if row["hypothesis_id"] == "positive")
    assert claim["operational_compatibility"] == ("undetermined" if missing_condition else "incompatible")
    assert claim["prospective_compatibility"] == ("undetermined" if missing_condition else "incompatible")
    assert claim["requires_semantic_review"]
    validate_episode_report(report)


def test_null_result_is_valid_and_zero_denominators_are_null():
    session = PostTestEvidenceSession(ObservationsOnly(), max_steps=2)
    assert session.step({"action": "commit", "claim": {"claims": [], "replication_tests": [], "limitations": []}})["ok"]
    report = complete(session)
    assert report["resources"]["steps"] == 2 and report["resources"]["experiment_calls"] == 0
    assert report["metrics"]["candidate_interpretation"]["coverage"]["value"] is None
    validate_episode_report(report)


def test_all_registered_sealed_tests_must_be_frozen():
    session = PostTestEvidenceSession(ObservationsOnly())
    register(session, exploration=False)
    assert session.step({"action": "plan_test", "test": plan("omitted", "replication")})["ok"]
    assert session.step({"action": "commit", "claim": dossier()})["error"] == "invalid_test_plan"
    assert session.plan is None and session.environment.calls == []


def test_llm_reserves_interpretation_within_32_calls_and_never_calls_33():
    class Model:
        last_usage = {}
        last_stop_reason = "stop"
        def __init__(self): self.calls = 0
        def complete(self, prompt, system):
            self.calls += 1
            assert "read-only interpretation" in system
            if self.calls < 31:
                return json.dumps({"action": "invalid"})
            if self.calls == 31:
                return json.dumps({"action": "commit", "claim": {"claims": [], "replication_tests": [], "limitations": []}})
            response = json.loads(prompt)["history"][-1]["response"]
            assert "prediction_checks" not in prompt
            return json.dumps({"action": "submit_interpretation", "interpretation": {
                "plan_sha256": response["plan_sha256"], "results_sha256": response["results_sha256"],
                "test_responses": [], "conclusions": [], "posthoc_hypotheses": [], "limitations": []}})
    model = Model()
    report = run_llm(PostTestEvidenceSession(ObservationsOnly()), model)
    assert report["status"] == "completed" and model.calls == 32
    validate_episode_report(report)


def test_uncommitted_research_stops_before_spending_reserved_model_call():
    class Model:
        last_usage = {}
        last_stop_reason = "stop"
        calls = 0
        def complete(self, *args, **kwargs):
            self.calls += 1
            return '{"action":"invalid"}'
    model = Model()
    report = run_llm(PostTestEvidenceSession(ObservationsOnly()), model)
    assert model.calls == 31 and report["status"] == "incomplete_delivery"
    validate_episode_report(report)


def test_program_must_supply_own_interpretation_and_freeze_hashes():
    def policy(context, act):
        response = act({"action": "commit", "claim": {"claims": [], "replication_tests": [], "limitations": []}})
        return {"plan_sha256": response["plan_sha256"], "results_sha256": response["results_sha256"],
                "test_responses": [], "conclusions": [], "posthoc_hypotheses": [], "limitations": []}
    report = run_posttest_policy(PostTestEvidenceSession(ObservationsOnly()), policy)
    assert report["status"] == "completed"
    validate_episode_report(report)


@pytest.mark.parametrize("configuration", ["legacy", "oversized", "reused"])
def test_real_transport_requires_single_attempt_policy_and_fresh_episode_budget(monkeypatch, configuration):
    from sle.llm import LLMClient, LLMConfig
    from sle.posttest_transport import PostTestLLMClient
    from unittest.mock import Mock
    request = Mock(side_effect=AssertionError("invalid transport must not make a request"))
    monkeypatch.setattr("urllib.request.urlopen", request)
    if configuration == "legacy":
        model = LLMClient(LLMConfig())
    else:
        model = PostTestLLMClient(LLMConfig(), max_attempts=32 if configuration == "oversized" else 2)
        if configuration == "reused":
            model._attempts = 1
    with pytest.raises(ValueError, match="posttest-v2 requires"):
        run_llm(PostTestEvidenceSession(ObservationsOnly(), max_steps=2), model)
    assert request.call_count == 0


def test_real_transport_timeout_is_retained_in_episode_without_automatic_retry(monkeypatch):
    from sle.llm import LLMConfig
    from sle.posttest_transport import PostTestLLMClient
    from unittest.mock import Mock
    request = Mock(side_effect=TimeoutError("manual missing response"))
    monkeypatch.setattr("urllib.request.urlopen", request)
    model = PostTestLLMClient(LLMConfig(), max_attempts=2)
    report = run_llm(PostTestEvidenceSession(ObservationsOnly(), max_steps=2), model)
    assert request.call_count == 1 and report["status"] == "budget_exhausted"
    assert report["model_transport"]["attempts"] == report["model_transport"]["failed_attempts"] == 1
    assert report["model_transport"]["usage_on_missing_response"] == "unknown"
    assert report["resources"]["steps"] == 0 and report["metrics"] is None
    validate_episode_report(report)
