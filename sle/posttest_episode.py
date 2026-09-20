"""Opt-in, two-freeze discovery protocol. No hidden answer or scientific score.

Version one reports and their interpretation are deliberately unchanged. Version
two freezes the complete research plan, exposes only its sealed observations,
then accepts one read-only interpretation within the original action budget.
"""
from __future__ import annotations

from .discovery_review import _keys, _ids, _strings, _text
from .discovery_structure import validate_structures, review_structures, pairwise_predictions
from .episode_deadline import call_with_deadline
from .evidence_episode import EvidenceEpisodeSession, _review_from_events
from .scientific_episode import EvidenceLimitError, digest, json_copy, _positive_int

PROTOCOL = "sle-discovery-posttest-v2"
INTERPRETATION_SCHEMA = {
    "plan_sha256": "hash returned by commit",
    "results_sha256": "hash returned by commit",
    "test_responses": [{"test_id": "every frozen replication test exactly once",
        "evidence_id": "its outer experiment-XXXX id",
        "predictions": [{"hypothesis_id": "every prediction in that test exactly once",
            "assessment": "compatible, incompatible or unavailable",
            "explanation": "what the observation means for this prediction"}]}],
    "conclusions": [{"hypothesis_id": "every hypothesis in the frozen dossier claims exactly once",
        "disposition": "retain, narrow, retract or undetermined",
        "statement": "final scoped claim, not an overwritten original hypothesis",
        "scope": ["objects, periods and conditions"], "limitations": ["remaining uncertainties"],
        "rationale": "why the full evidence warrants this response to the original claim",
        "evidence": [{"evidence_id": "native experiment id",
                      "role": "background, exploratory or prospective_test"}]}],
    "posthoc_hypotheses": [{"id": "new id", "statement": "future hypothesis",
                           "status": "posthoc_unvalidated"}],
    "limitations": ["episode-wide limitations"],
}
STRUCTURE_SCHEMA = [{"hypothesis_id": "registered compound claim",
    "operator": "all_of or any_of",
    "components": [{"id": "component id", "statement": "necessary operational condition",
        "hypothesis_id": "registered hypothesis tested by this component",
        "test_ids": ["registered tests; an empty list exposes an untested condition"]}]}]


def ledger_entries(ledger):
    entries = ledger.snapshot()["events"]
    return ([event["payload"] for event in entries if event["kind"] in {"hypothesis", "hypothesis_revision"}],
            [event["payload"] for event in entries if event["kind"] == "test_plan"])


def native_observations(ledger):
    return {event["payload"]["evidence_id"]: event["payload"]
            for event in ledger.snapshot()["events"] if event["kind"] == "native_observation"}


def validate_interpretation(value, plan, results, ledger):
    value = json_copy(value)
    _keys(value, {"plan_sha256", "results_sha256", "test_responses", "conclusions",
                  "posthoc_hypotheses", "limitations"})
    if value["plan_sha256"] != digest(plan) or value["results_sha256"] != digest(results):
        raise ValueError("interpretation must bind both freezes")
    _strings(value["limitations"], "limitations")
    responses = value["test_responses"]
    if not isinstance(responses, list) or len(responses) > 8:
        raise ValueError("invalid test response list")
    tests = {test["id"]: test for test in plan["tests"]}
    expected_ids = plan["dossier"]["replication_tests"]
    observed = dict(zip(expected_ids, results["observations"]))
    supplied = []
    for response in responses:
        _keys(response, {"test_id", "evidence_id", "predictions"})
        test_id = response["test_id"]
        if not isinstance(test_id, str) or test_id not in observed:
            raise ValueError("unknown frozen test")
        supplied.append(test_id)
        if response["evidence_id"] != observed[test_id]["evidence_id"]:
            raise ValueError("test response cites a different observation")
        predictions = response["predictions"]
        if not isinstance(predictions, list) or len(predictions) > 64:
            raise ValueError("invalid prediction response list")
        ids = []
        for prediction in predictions:
            _keys(prediction, {"hypothesis_id", "assessment", "explanation"})
            ids.append(prediction["hypothesis_id"])
            if prediction["assessment"] not in ("compatible", "incompatible", "unavailable"):
                raise ValueError("unknown operational assessment")
            _text(prediction["explanation"], "explanation")
        _ids(ids, "prediction ids")
        if set(ids) != {item["hypothesis_id"] for item in tests[test_id]["predictions"]}:
            raise ValueError("every competing prediction needs a response")
    _ids(supplied, "test response ids")
    if set(supplied) != set(expected_ids):
        raise ValueError("every frozen test needs a response")
    observations = native_observations(ledger)
    conclusions = value["conclusions"]
    if not isinstance(conclusions, list) or len(conclusions) > 128:
        raise ValueError("invalid conclusion list")
    ids = []
    for conclusion in conclusions:
        _keys(conclusion, {"hypothesis_id", "disposition", "statement", "scope", "limitations",
                           "rationale", "evidence"})
        ids.append(conclusion["hypothesis_id"])
        if conclusion["disposition"] not in ("retain", "narrow", "retract", "undetermined"):
            raise ValueError("unknown conclusion disposition")
        for field in ("statement", "rationale"):
            _text(conclusion[field], field)
        for field in ("scope", "limitations"):
            _strings(conclusion[field], field)
        if not conclusion["scope"]:
            raise ValueError("a conclusion needs an explicit scope")
        refs = conclusion["evidence"]
        if not isinstance(refs, list) or len(refs) > 1024:
            raise ValueError("invalid evidence references")
        cited = []
        for ref in refs:
            _keys(ref, {"evidence_id", "role"})
            cited.append(ref["evidence_id"])
            if not isinstance(ref["evidence_id"], str) or ref["evidence_id"] not in observations:
                raise ValueError("unknown native evidence")
            if ref["role"] not in ("background", "exploratory", "prospective_test"):
                raise ValueError("unknown evidence role; independence is not self-certified")
        _ids(cited, "evidence references")
    _ids(ids, "conclusion ids")
    if set(ids) != {claim["hypothesis_id"] for claim in plan["dossier"]["claims"]}:
        raise ValueError("final conclusions must cover every frozen claim")
    posthoc = value["posthoc_hypotheses"]
    if not isinstance(posthoc, list) or len(posthoc) > 128:
        raise ValueError("invalid posthoc hypotheses")
    new_ids = []
    old_ids = {item["id"] for item in plan["hypotheses"]}
    for hypothesis in posthoc:
        _keys(hypothesis, {"id", "statement", "status"})
        new_ids.append(hypothesis["id"])
        _text(hypothesis["statement"], "statement")
        if hypothesis["status"] != "posthoc_unvalidated":
            raise ValueError("posthoc hypotheses are not validated discoveries")
    _ids(new_ids, "posthoc ids")
    if old_ids & set(new_ids):
        raise ValueError("posthoc hypotheses cannot overwrite earlier versions")
    return value


def build_posttest_metrics(ledger, plan, results, interpretation, events):
    """Private mechanical diagnostics; never candidate scientific-quality labels."""
    checks = ledger._checks()
    by_test = {check["test_id"]: check for check in checks}
    responses = []
    for response in interpretation["test_responses"]:
        check = by_test[response["test_id"]]
        predictions = {item["hypothesis_id"]: item for item in check["hypotheses"]}
        for candidate in response["predictions"]:
            item = predictions.get(candidate["hypothesis_id"])
            expected = ("unavailable" if item is None else
                        "compatible" if item["compatible"] else "incompatible")
            responses.append({"test_id": response["test_id"], "evidence_id": response["evidence_id"],
                "hypothesis_id": candidate["hypothesis_id"], "declared_assessment": candidate["assessment"],
                "operational_assessment": expected,
                "matches_measurement_check": candidate["assessment"] == expected,
                "reasoning_quality": "unassessed"})
    evidence_roles = []
    for conclusion in interpretation["conclusions"]:
        targets = {conclusion["hypothesis_id"]}
        for structure in plan["structures"]:
            if structure["hypothesis_id"] == conclusion["hypothesis_id"]:
                targets.update(component["hypothesis_id"] for component in structure["components"])
        for ref in conclusion["evidence"]:
            matches = [check for check in checks if check["evidence_id"] == ref["evidence_id"]]
            prospective = any(check["prospective"] and check["status"] == "assessed" for check in matches)
            relevant = any(check["prospective"] and check["status"] == "assessed"
                           and any(item["hypothesis_id"] in targets for item in check["hypotheses"])
                           for check in matches)
            evidence_roles.append({"hypothesis_id": conclusion["hypothesis_id"], **ref,
                "native_reference": True, "has_prospective_measurement": prospective,
                "tests_claim_or_declared_component": relevant,
                "requested_role_supported": ref["role"] != "prospective_test" or relevant,
                "scientific_support": "requires_semantic_review", "independent_collection": "unassessed"})
    old = _review_from_events(ledger, plan["dossier"], events)
    return {"schema_version": 2, "kind": "posttest_evidence_review", "ground_truth_used": False,
        "judge_model_used": False, "discovery_score": None,
        "prediction_checks": checks,
        "broker_completeness": {"frozen_tests": len(plan["dossier"]["replication_tests"]),
                                 "returned_observations": len(results["observations"])},
        "candidate_interpretation": {"submitted": True, "test_responses": responses,
            "coverage": {"numerator": len(interpretation["test_responses"]),
                         "denominator": len(plan["dossier"]["replication_tests"]),
                         "value": 1.0 if plan["dossier"]["replication_tests"] else None},
            "scientific_responsiveness": "unassessed"},
        "compound_claims": review_structures(plan["structures"], plan["hypotheses"], plan["tests"], checks),
        "pairwise_predictions": pairwise_predictions(plan["tests"]),
        "evidence_roles": evidence_roles, "final_conclusions": interpretation["conclusions"],
        "posthoc_hypotheses": interpretation["posthoc_hypotheses"],
        "analysis_artifacts": old["analysis_artifacts"], "semantic_review": old["semantic_review"],
        "limitations": ["Logical compatibility concerns declared operational conditions, not scientific truth.",
            "Candidate-provided decompositions, evidence relevance and reasoning require independent scientific review.",
            "Response coverage is not understanding; held-out rows are not automatically independent collections."]}


class PostTestEvidenceSession(EvidenceEpisodeSession):
    def __init__(self, environment, **kwargs):
        steps = kwargs.setdefault("max_steps", 32)
        if type(steps) is not int or not 2 <= steps <= 32:
            raise ValueError("posttest-v2 needs 2..32 total actions, including interpretation")
        self.plan = self.results = self.interpretation = None
        self.model_transport = None
        self.plan_sha256 = self.results_sha256 = self.interpretation_sha256 = None
        binding = json_copy(kwargs.pop("binding", {}) or {})
        binding.update(task_id=environment.task_id, episode_protocol=PROTOCOL)
        super().__init__(environment, binding=binding, **kwargs)

    @property
    def done(self):
        return self.state not in ("exploring", "interpreting")

    def _public_problem(self):
        problem = super()._public_problem()
        contract = problem["discovery_contract"]
        contract.update(protocol=PROTOCOL, interpretation_schema=INTERPRETATION_SCHEMA,
            structures=STRUCTURE_SCHEMA,
            confirmation="commit freezes the research plan; sealed results are followed by one read-only interpretation",
            action_budget="At most 32 total actions. Commit by the penultimate action; reserve one for interpretation.")
        return problem

    def observation(self):
        result = super().observation()
        result["protocol"].update(phase=self.state, episode_protocol=PROTOCOL,
            confirmation="commit freezes research, then submit_interpretation once; no new tools or hypotheses",
            commit={"action": "commit", "claim": "frozen dossier", "structures": STRUCTURE_SCHEMA},
            submit_interpretation={"action": "submit_interpretation", "interpretation": INTERPRETATION_SCHEMA},
            research_action_limit=self.max_steps - 1, interpretation_action_limit=1)
        if self.state == "interpreting":
            result["protocol"]["actions"] = ["submit_interpretation"]
            result.update(plan_sha256=self.plan_sha256, results_sha256=self.results_sha256)
        return json_copy(result)

    def prepare_model_call(self):
        if self.state == "exploring" and self.steps >= self.max_steps - 1:
            self._fail("incomplete_delivery", "test_plan_not_frozen_before_reserved_action")
            return False
        return not self.done

    def _step(self, request):
        if not self.prepare_model_call():
            return {"ok": False, "error": "episode_closed"}
        return super()._step(request)

    def _dispatch(self, request):
        if self.state == "interpreting":
            # Every post-test action consumes the sole interpretation attempt.
            # Rejecting a new experiment must not execute or reopen anything.
            if not isinstance(request, dict) or set(request) != {"action", "interpretation"} or request["action"] != "submit_interpretation":
                self._fail("invalid_candidate", "interpretation_phase_is_read_only")
                return {"ok": False, "error": "interpretation_phase_is_read_only"}
            return self._interpret(request["interpretation"])
        if isinstance(request, dict) and request.get("action") == "commit":
            if set(request) not in ({"action", "claim"}, {"action", "claim", "structures"}):
                return {"ok": False, "error": "invalid_action"}
            return self._freeze(request["claim"], request.get("structures", []))
        return super()._dispatch(request)

    def _freeze(self, claim, structures):
        try:
            claim = self.ledger.validate_dossier(json_copy(claim), allow_pending=True)
            hypotheses, tests = ledger_entries(self.ledger)
            structures = validate_structures(structures, hypotheses, tests)
            calls, cost = [], 0
            if len(claim["replication_tests"]) > 8:
                raise ValueError("too many replication tests")
            # A frozen plan cannot silently omit a registered sealed test.
            if set(claim["replication_tests"]) != {test["id"] for test in tests if test["phase"] == "replication"}:
                raise ValueError("every registered sealed test must be included")
            for test_id in claim["replication_tests"]:
                test = self.ledger.get_test(test_id)
                call = {"tool": test["tool"], "arguments": test["arguments"], "test_id": test_id}
                self.ledger.validate_experiment(call)
                cost += _positive_int(self.environment.action_cost(call["tool"], json_copy(call["arguments"])), "replication cost")
                calls.append(call)
        except (ValueError, KeyError, TypeError):
            return {"ok": False, "error": "invalid_test_plan"}
        if self.units + cost > self.budget_units:
            return {"ok": False, "error": "replication_budget_exceeded"}
        if self.steps >= self.max_steps or self._expired():
            self.stop()
            return {"ok": False, "error": "budget_exhausted"}
        self.claim, self.claim_sha256 = claim, digest(claim)
        self.plan = json_copy({"schema_version": 1, "dossier": claim, "structures": structures,
            "hypotheses": hypotheses, "tests": tests, "problem_sha256": digest(self.problem),
            "binding_sha256": digest(self.binding)})
        self.plan_sha256 = digest(self.plan)
        self.state = "test_plan_committed"
        self._record("test_plan_committed", {"plan": self.plan, "plan_sha256": self.plan_sha256})
        started = self.clock()
        def execute():
            self.state = "testing"
            if calls and hasattr(self.environment, "begin_confirmation"):
                self.environment.begin_confirmation()
            return [self._native_experiment(call, "replication") for call in calls]
        try:
            observed = call_with_deadline(execute, max(0.001, min(60, self.deadline - self.clock())))
        except EvidenceLimitError:
            raise
        except Exception as exc:
            self.verification_seconds = self.clock() - started
            self._fail("infrastructure_error", "replication_timeout" if isinstance(exc, TimeoutError) else "replication_failed")
            return {"ok": False, "error": self.error}
        self.verification_seconds = self.clock() - started
        self.results = {"schema_version": 1, "plan_sha256": self.plan_sha256, "observations": observed}
        self.results_sha256 = digest(self.results)
        self.confirmation = json_copy(self.results)
        self._record("sealed_results", {"results": self.results, "results_sha256": self.results_sha256})
        self.state = "interpreting"
        if self._expired():
            self._fail("incomplete_delivery", "no_time_for_interpretation")
        return {"ok": True, "plan_sha256": self.plan_sha256, "results_sha256": self.results_sha256,
            "results": self.results, "next_action": "submit_interpretation",
            "episode_complete": False}

    def _interpret(self, value):
        try:
            value = validate_interpretation(value, self.plan, self.results, self.ledger)
        except (ValueError, TypeError, KeyError):
            self._fail("invalid_candidate", "invalid_interpretation")
            return {"ok": False, "error": "invalid_interpretation"}
        metrics = build_posttest_metrics(self.ledger, self.plan, self.results, value, self.events)
        if self._expired():
            self._fail("incomplete_delivery", "interpretation_deadline")
            return {"ok": False, "error": "interpretation_deadline"}
        self.interpretation = value
        self.interpretation_sha256 = digest(value)
        self._record("interpretation_submitted", {"interpretation": value,
                                                   "interpretation_sha256": self.interpretation_sha256})
        self.metrics = metrics
        self._record("outcome", {"metrics": self.metrics, "plan_sha256": self.plan_sha256,
            "results_sha256": self.results_sha256, "interpretation_sha256": self.interpretation_sha256})
        self.state = "completed"
        return {"ok": True, "interpretation_sha256": self.interpretation_sha256, "episode_complete": True}

    def report(self):
        report = super().report()
        report.update(schema_version=2, plan=self.plan, plan_sha256=self.plan_sha256,
                      results=self.results, results_sha256=self.results_sha256,
                      interpretation=self.interpretation, interpretation_sha256=self.interpretation_sha256,
                      model_transport=self.model_transport)
        report = json_copy_report(report)
        report["sha256"] = digest({key: value for key, value in report.items() if key != "sha256"})
        return report


def json_copy_report(report):
    # Full event sequences may exceed a single action's 2 MiB bound.
    import json
    return json.loads(json.dumps(report, allow_nan=False))


def run_posttest_policy(session, solve):
    """No implicit scientific interpretation: the candidate must supply it."""
    try:
        result = solve(session.observation(), session.step)
        if session.state == "interpreting":
            session.step({"action": "submit_interpretation", "interpretation": result})
        if not session.done:
            session.stop("incomplete_delivery")
    except TimeoutError:
        if not session.done:
            session._fail("budget_exhausted", "program_timeout")
    except Exception:
        if not session.done:
            session._fail("invalid_candidate", "policy_failed")
    return session.report()
