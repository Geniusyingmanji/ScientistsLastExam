"""Ground-truth-free discovery protocol over observations and prospective tests.

The reviewer receives no environment object. It cannot call a hidden evaluator or
read a latent answer. Deterministic evidence checks are distinct from scientific
semantic review, novelty, causal validity and independent replication quality.
"""
from __future__ import annotations

from .discovery_review import DiscoveryLedger
from .episode_deadline import call_with_deadline
from .scientific_episode import EpisodeSession, digest, json_copy, _positive_int


DISCOVERY_CONTRACT = {
    "evaluation_mode": "evidence_only",
    "ground_truth_required": False,
    "hypothesis": {"id": "unique string", "statement": "falsifiable scientific claim",
                   "rationale": "concise scientific justification, not a private reasoning trace",
                   "assumptions": ["explicit assumption"], "alternatives": ["competing explanation"]},
    "revision": "new hypothesis fields plus revises:<existing id>, revision_reason:<brief reason>; old version retained",
    "test": {"id": "unique string", "phase": "exploration or replication", "tool": "public tool",
             "arguments": {}, "rationale": "why this observation discriminates competing explanations",
             "measurement": {"path": ["value"], "reducer": "scalar, mean, sum, min or max"},
             "predictions": [{"hypothesis_id": "registered id", "interval": [0, 1],
                              "falsifiers": [[2, 3]]}],
             "requirements": "at least two registered competing predictions; exact tool/arguments; one execution"},
    "claim_schema": {
        "claims": [{"hypothesis_id": "registered id", "conclusion": "supported, rejected or inconclusive",
                    "support": ["native evidence id"], "counterevidence": ["native evidence id"],
                    "tests": ["registered test id, including pending replication"],
                    "limitations": ["scope and uncertainty"]}],
        "replication_tests": ["pending replication-phase test ids, at most 8"],
        "limitations": ["episode-level limitations"],
    },
    "interpretation": "Compatibility and discrimination of preregistered predictions are evidence, not ground-truth correctness.",
    "review_limits": "Scientific meaning, novelty, causal justification and adequacy of assumptions require explicit independent review.",
    "budget": "exploration and postcommit replication share the same finite experimental budget",
    "confirmation": "dossier and predictions freeze before reserved replication tools; no resubmission",
}


def _review_from_events(ledger, claim, events):
    review = ledger.review_dossier(claim)
    artifacts = []
    pending = None
    for event in events:
        if event["kind"] == "action":
            pending = event if isinstance(event["payload"], dict) and event["payload"].get("action") == "analyze" else None
        elif event["kind"] == "observation" and pending is not None:
            response = event["payload"]
            if response.get("ok") and isinstance(response.get("analysis"), dict):
                artifacts.append({"action_event": pending["seq"], "observation_event": event["seq"],
                                  "code_sha256": digest(pending["payload"]["code"]),
                                  "output_sha256": digest(response["analysis"]),
                                  "execution_status": "completed" if response["analysis"].get("ok") else "analysis_error",
                                  "replay_status": "not_replayed", "native_measurement": False})
            pending = None
    review["analysis_artifacts"] = artifacts
    for axis in review["semantic_review"]["axes"]:
        if "analysis_artifacts" in axis["required_evidence_references"]:
            axis["available_references"]["analysis_artifacts"] = ["action_event:%d" % item["action_event"] for item in artifacts]
    return json_copy(review)


class EvidenceEpisodeSession(EpisodeSession):
    def __init__(self, environment, **kwargs):
        self.ledger = DiscoveryLedger(environment.task_id)
        binding = json_copy(kwargs.pop("binding", None) or {"task_id": environment.task_id})
        binding["evaluation_mode"] = "evidence_only"
        if hasattr(environment, "data_binding"):
            binding["measurement_data"] = json_copy(environment.data_binding())
        super().__init__(environment, binding=binding, **kwargs)

    def _public_problem(self):
        problem = json_copy(self.environment.public_problem())
        # Legacy oracle-specific submissions are not part of the active mode.
        problem["claim_schema"] = json_copy(DISCOVERY_CONTRACT["claim_schema"])
        problem["discovery_contract"] = json_copy(DISCOVERY_CONTRACT)
        return problem

    def observation(self):
        result = super().observation()
        result["protocol"].update({
            "actions": ["hypothesize", "revise_hypothesis", "plan_test", "experiment", "commit"]
                       + (["analyze"] if self.analysis else []),
            "hypothesize": {"action": "hypothesize", "hypothesis": DISCOVERY_CONTRACT["hypothesis"]},
            "revise_hypothesis": {"action": "revise_hypothesis", "revision": DISCOVERY_CONTRACT["revision"]},
            "plan_test": {"action": "plan_test", "test": DISCOVERY_CONTRACT["test"]},
            "experiment": {"action": "experiment", "tool": "public tool", "arguments": {},
                           "test_id": "optional preregistered exploration test id"},
            "confirmation": DISCOVERY_CONTRACT["confirmation"],
            "replication_budget": "included in experiment budget; at most 8 frozen tests",
        })
        return json_copy(result)

    def _native_experiment(self, action, phase):
        self.ledger.validate_experiment(action)
        cost = _positive_int(self.environment.action_cost(action["tool"], json_copy(action["arguments"])),
                             "experiment cost")
        if self.units + cost > self.budget_units:
            raise ValueError("experiment budget exceeded")
        self.units += cost
        self.experiments += 1
        evidence_id = "experiment-%04d" % self.experiments
        self._record("experiment_charge", {"units": cost, "tool": action["tool"]})
        invoke = lambda: self.environment.experiment(action["tool"], json_copy(action["arguments"]))
        if phase == "exploration":
            observed = json_copy(call_with_deadline(invoke, max(0.001, self.deadline - self.clock())))
        else:
            # The complete reserved phase has one outer deadline.
            observed = json_copy(invoke())
        self.ledger.record_observation(evidence_id, json_copy(action), observed)
        self._record("native_observation", {"evidence_id": evidence_id, "action": action,
                                             "observation": observed, "phase": phase})
        return {"evidence_id": evidence_id, "observation": observed, "charged_units": cost}

    def _dispatch(self, request):
        if not isinstance(request, dict):
            return {"ok": False, "error": "invalid_action"}
        action = request.get("action")
        if not isinstance(action, str):
            return {"ok": False, "error": "invalid_action"}
        notes = {
            "hypothesize": ("hypothesis", self.ledger.append_hypothesis, "discovery_hypothesis"),
            "revise_hypothesis": ("revision", self.ledger.revise_hypothesis, "discovery_revision"),
            "plan_test": ("test", self.ledger.plan_test, "discovery_test"),
        }
        if action in notes:
            field, callback, kind = notes[action]
            if set(request) != {"action", field}:
                return {"ok": False, "error": "invalid_action"}
            try:
                if action == "plan_test":
                    plan = request[field]
                    _positive_int(self.environment.action_cost(plan["tool"], json_copy(plan["arguments"])),
                                  "experiment cost")
                    if hasattr(self.environment, "is_sealed_action"):
                        sealed = self.environment.is_sealed_action(plan["tool"], plan["arguments"])
                        if sealed != (plan.get("phase") == "replication"):
                            raise ValueError("plan phase differs from measurement partition")
                entry = callback(json_copy(request[field]))
            except (ValueError, TypeError, KeyError):
                return {"ok": False, "error": "invalid_discovery_entry"}
            self._record(kind, request[field])
            return {"ok": True, "registered": entry}
        if action == "experiment" and set(request) in (
                {"action", "tool", "arguments"}, {"action", "tool", "arguments", "test_id"}):
            call = {key: value for key, value in request.items() if key != "action"}
            try:
                self.ledger.validate_experiment(call)
                if call.get("test_id") is not None and self.ledger.get_test(call["test_id"])["phase"] != "exploration":
                    return {"ok": False, "error": "replication_requires_commit"}
                if hasattr(self.environment, "is_sealed_action") and self.environment.is_sealed_action(call["tool"], call["arguments"]):
                    return {"ok": False, "error": "replication_requires_commit"}
                cost = _positive_int(self.environment.action_cost(call["tool"], json_copy(call["arguments"])),
                                     "experiment cost")
            except (ValueError, TypeError, KeyError):
                return {"ok": False, "error": "invalid_experiment_arguments"}
            if self.units + cost > self.budget_units:
                return {"ok": False, "error": "experiment_budget_exceeded", "remaining_units": self.budget_units - self.units}
            try:
                result = self._native_experiment(call, "exploration")
            except TimeoutError:
                self._fail("budget_exhausted", "experiment_timeout")
                return {"ok": False, "error": "experiment_timeout"}
            return {"ok": True, **result, "remaining_units": self.budget_units - self.units}
        if action == "analyze":
            return super()._dispatch(request)
        if action == "commit" and set(request) == {"action", "claim"}:
            return self._commit(request["claim"])
        return {"ok": False, "error": "invalid_action"}

    def _commit(self, claim):
        try:
            claim = json_copy(claim)
            self.ledger.validate_dossier(claim, allow_pending=True)
            if len(claim["replication_tests"]) > 8:
                raise ValueError("too many replication tests")
            calls = []
            cost = 0
            for test_id in claim["replication_tests"]:
                test = self.ledger.get_test(test_id)
                if test["phase"] != "replication":
                    raise ValueError("replication phase required")
                call = {"tool": test["tool"], "arguments": test["arguments"], "test_id": test_id}
                self.ledger.validate_experiment(call)
                cost += _positive_int(self.environment.action_cost(call["tool"], json_copy(call["arguments"])),
                                      "replication cost")
                calls.append(call)
        except (ValueError, TypeError, KeyError):
            return {"ok": False, "error": "invalid_discovery_dossier"}
        if cost + self.units > self.budget_units:
            return {"ok": False, "error": "replication_budget_exceeded", "remaining_units": self.budget_units - self.units}
        if self._expired():
            self.stop()
            return {"ok": False, "error": "budget_exhausted"}
        self.claim = claim
        self.claim_sha256 = digest(claim)
        self.state = "committed"
        self._record("commit", {"claim": claim, "claim_sha256": self.claim_sha256})
        started = self.clock()
        def verify():
            # No call to environment.validate_claim, confirm, evaluate or hidden GT.
            if calls and hasattr(self.environment, "begin_confirmation"):
                self.environment.begin_confirmation()
            observations = [self._native_experiment(call, "replication") for call in calls]
            self.confirmation = {"protocol": "preregistered-replication-without-ground-truth-v1",
                                 "observations": observations}
            self._record("confirmation", self.confirmation)
            self.metrics = _review_from_events(self.ledger, claim, self.events)
        try:
            call_with_deadline(verify, max(1.0, min(60.0, self.wall_seconds)))
        except TimeoutError:
            self.verification_seconds = self.clock() - started
            self._fail("infrastructure_error", "replication_timeout")
            return {"ok": False, "error": "replication_timeout"}
        self.verification_seconds = self.clock() - started
        self._record("outcome", {"metrics": self.metrics, "claim_sha256": self.claim_sha256,
                                 "confirmation_sha256": digest(self.confirmation)})
        self.state = "completed"
        return {"ok": True, "committed": True, "claim_sha256": self.claim_sha256,
                "confirmation": json_copy(self.confirmation), "episode_complete": True}


def validate_discovery_report(report):
    """Recompute review from the native evidence chain, without task or oracle code."""
    ledger = DiscoveryLedger(report["binding"]["task_id"])
    committed = False
    claim = None
    current_action = None
    charges = []
    replicas = []
    replication_tests = []
    native_count = 0
    note_actions = {"discovery_hypothesis": ("hypothesize", "hypothesis", ledger.append_hypothesis),
                    "discovery_revision": ("revise_hypothesis", "revision", ledger.revise_hypothesis),
                    "discovery_test": ("plan_test", "test", ledger.plan_test)}
    for event in report["events"]:
        kind, payload = event["kind"], event["payload"]
        if kind == "action":
            current_action = payload
        elif kind in note_actions:
            action, key, function = note_actions[kind]
            if committed or current_action != {"action": action, key: payload}:
                raise ValueError("discovery note lacks its native action")
            function(payload)
        elif kind == "commit":
            claim = payload["claim"]
            ledger.validate_dossier(claim, allow_pending=True)
            committed = True
        elif kind == "experiment_charge":
            charges.append(payload)
        elif kind == "native_observation":
            native_count += 1
            call = payload["action"]
            if not charges or payload["evidence_id"] != "experiment-%04d" % len(charges):
                raise ValueError("native evidence does not bind its charge")
            if charges[-1]["tool"] != call["tool"]:
                raise ValueError("native evidence tool mismatch")
            if committed:
                test_id = call.get("test_id")
                if payload["phase"] != "replication" or test_id not in claim["replication_tests"]:
                    raise ValueError("unplanned postcommit evidence")
                if ledger.get_test(test_id)["phase"] != "replication":
                    raise ValueError("invalid replication phase")
            else:
                if payload["phase"] != "exploration" or current_action != {"action": "experiment", **call}:
                    raise ValueError("native evidence lacks its experiment action")
                if call.get("test_id") is not None and ledger.get_test(call["test_id"])["phase"] != "exploration":
                    raise ValueError("replication evidence predates commitment")
            ledger.record_observation(payload["evidence_id"], call, payload["observation"])
            if committed:
                replicas.append({"evidence_id": payload["evidence_id"], "observation": payload["observation"],
                                 "charged_units": charges[-1]["units"]})
                replication_tests.append(call["test_id"])
    if report["status"] == "completed":
        if native_count != len(charges):
            raise ValueError("completed discovery requires one native observation per charge")
        if replication_tests != claim["replication_tests"] or len(replication_tests) > 8:
            raise ValueError("not every frozen replication plan executed exactly once")
        confirmation = {"protocol": "preregistered-replication-without-ground-truth-v1", "observations": replicas}
        if report["confirmation"] != confirmation:
            raise ValueError("replication confirmation does not match native evidence")
        if report["metrics"] != _review_from_events(ledger, claim, report["events"]):
            raise ValueError("review differs from recomputed evidence assessment")
    return {"status": "evidence_recomputed", "ground_truth_used": False,
            "scientific_semantic_review": "not_assessed"}


def run_discovery_policy(session, solve):
    """Trusted baseline or sandbox RPC: solve(context, act) may issue many actions."""
    try:
        claim = solve(session.observation(), lambda action: session.step(action))
        if not session.done:
            session.step({"action": "commit", "claim": claim})
            if not session.done:
                session.stop("invalid_candidate")
    except TimeoutError:
        if not session.done:
            session._fail("budget_exhausted", "program_timeout")
    except Exception as exc:
        if not session.done:
            session._fail("invalid_candidate", type(exc).__name__)
    return session.report()
