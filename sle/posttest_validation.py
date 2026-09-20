"""Replay the opt-in two-freeze protocol without loading task or oracle code.

Hashes establish internal consistency, not authenticity or scientific validity.
The validator deliberately does not weaken the historical schema-1 validator.
"""
from __future__ import annotations

import math

from .discovery_review import DiscoveryLedger
from .scientific_episode import digest, parse_action


PROTOCOL = "sle-discovery-posttest-v2"
_NO_ACTION = object()
_STATUSES = {
    "exploring", "test_plan_committed", "testing", "interpreting", "completed",
    "budget_exhausted", "invalid_candidate", "model_error", "infrastructure_error",
    "evidence_limit", "incomplete_delivery",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_transport_summary(summary, max_steps):
    """Check bookkeeping bounds only; this neither authenticates nor grades it."""
    if summary is None:
        return
    _require(isinstance(summary, dict), "invalid posttest transport summary")
    for key in ("attempts", "max_attempts", "automatic_retries", "failed_attempts"):
        _require(_integer(summary.get(key)), "invalid posttest transport count")
    _require(0 <= summary["failed_attempts"] <= summary["attempts"]
             <= summary["max_attempts"] <= max_steps, "posttest transport budget exceeded")
    _require(summary["automatic_retries"] == 0, "posttest automatic retries are forbidden")
    _require(summary.get("usage_on_missing_response") == "unknown",
             "missing transport usage must remain unknown")


def _validate_posttest_report(report):
    from .posttest_episode import build_posttest_metrics, validate_interpretation
    from .discovery_structure import validate_structures

    _require(isinstance(report, dict) and report.get("schema_version") == 2,
             "invalid posttest report schema")
    _require(report.get("kind") == "scientific_episode_pilot"
             and report.get("frontier_eligible") is False
             and report.get("difficulty") == "calibration_required"
             and report.get("status") in _STATUSES, "invalid posttest status or eligibility")
    _require(report.get("sha256") == digest({k: v for k, v in report.items() if k != "sha256"}),
             "posttest report digest mismatch")
    binding = report["binding"]
    _require(binding.get("episode_protocol") == PROTOCOL
             and binding.get("evaluation_mode") == "evidence_only",
             "posttest protocol binding mismatch")
    events = report["events"]
    _require(isinstance(events, list) and events and events[0].get("kind") == "start",
             "posttest start missing")
    _require(events[0]["payload"]["binding"] == binding, "posttest start binding mismatch")
    previous = None
    for index, event in enumerate(events):
        _require(set(event) == {"seq", "kind", "payload", "previous_sha256", "sha256"},
                 "invalid posttest event fields")
        _require(_integer(event["seq"]) and event["seq"] == index
                 and event["previous_sha256"] == previous
                 and event["sha256"] == digest({k: v for k, v in event.items() if k != "sha256"}),
                 "posttest event chain mismatch")
        previous = event["sha256"]
    resources = report["resources"]
    for key in ("steps", "max_steps", "experiment_calls", "experiment_units", "budget_units", "analysis_calls"):
        _require(_integer(resources[key]), "invalid posttest resource count")
    _require(2 <= resources["max_steps"] <= 32 and resources["budget_units"] > 0,
             "invalid posttest resource budget")
    _require(resources["steps"] <= resources["max_steps"]
             and resources["experiment_units"] <= resources["budget_units"],
             "posttest resource budget exceeded")
    _validate_transport_summary(report.get("model_transport"), resources["max_steps"])
    for key in ("wall_seconds", "max_wall_seconds", "verification_wall_seconds"):
        value = resources[key]
        _require(not isinstance(value, bool) and isinstance(value, (int, float))
                 and math.isfinite(value) and value >= 0, "invalid posttest resource time")
    _require(resources["max_wall_seconds"] > 0, "invalid posttest wall budget")
    complete = report.get("recording_complete") is True
    _require(complete or (report["status"] == "evidence_limit" and report.get("metrics") is None),
             "incomplete posttest evidence cannot carry an outcome")

    ledger = DiscoveryLedger(binding["task_id"])
    hypotheses, tests, charges, replicas, executed_replications = [], [], [], [], []
    plan = results = interpretation = None
    phase = "exploring"
    active_action = _NO_ACTION
    pending_charge = None
    action_native = action_analyses = 0
    frozen_response = final_response = None
    exploration_response = None
    awaiting_model_action = False
    parsed_model_action = _NO_ACTION
    actions = observations = analyses = native = posttest_actions = outcomes = 0
    failed = False
    notes = {
        "discovery_hypothesis": ("hypothesize", "hypothesis", ledger.append_hypothesis, hypotheses),
        "discovery_revision": ("revise_hypothesis", "revision", ledger.revise_hypothesis, hypotheses),
        "discovery_test": ("plan_test", "test", ledger.plan_test, tests),
    }
    for event in events[1:]:
        kind, payload = event["kind"], event["payload"]
        _require(not failed or kind == "observation", "events continue after failure")
        if kind == "action":
            _require(active_action is _NO_ACTION and not failed and phase != "completed",
                     "posttest action outside an open turn")
            _require(phase in {"exploring", "interpreting"}, "action during frozen testing")
            actions += 1
            if phase == "interpreting":
                posttest_actions += 1
                _require(posttest_actions == 1, "more than one interpretation attempt")
            else:
                _require(actions <= resources["max_steps"] - 1,
                         "exploration consumed the reserved interpretation turn")
            if awaiting_model_action and parsed_model_action is not _NO_ACTION:
                _require(payload == parsed_model_action, "action differs from recorded model response")
            active_action = payload
            action_native = action_analyses = 0
            awaiting_model_action = False
        elif kind == "model_reply":
            _require(active_action is _NO_ACTION and not failed and phase in {"exploring", "interpreting"},
                     "model response after episode closure")
            _require(not awaiting_model_action, "multiple model responses in one action turn")
            awaiting_model_action = True
            parsed_model_action = _NO_ACTION
            if "text" in payload:
                try:
                    parsed_model_action = parse_action(payload["text"])
                except (ValueError, TypeError, RecursionError):
                    parsed_model_action = {"action": "invalid"}
        elif kind in notes:
            action, field, callback, collection = notes[kind]
            _require(phase == "exploring" and active_action == {"action": action, field: payload},
                     "discovery mutation lacks its exploration action")
            registered = callback(payload)
            collection.append(payload)
            exploration_response = {"ok": True, "registered": registered}
        elif kind == "analysis_started":
            _require(phase == "exploring" and isinstance(active_action, dict)
                     and set(active_action) == {"action", "code"}
                     and active_action["action"] == "analyze", "analysis outside exploration")
            action_analyses += 1
            _require(action_analyses == 1, "multiple analyses in one action")
            analyses += 1
        elif kind == "test_plan_committed":
            _require(phase == "exploring" and plan is None and pending_charge is None and isinstance(active_action, dict)
                     and active_action.get("action") == "commit", "plan freeze lacks its commit action")
            _require(set(payload) == {"plan", "plan_sha256"}, "invalid plan freeze fields")
            plan = payload["plan"]
            _require(set(plan) == {"schema_version", "dossier", "structures", "hypotheses", "tests",
                                  "problem_sha256", "binding_sha256"}
                     and type(plan["schema_version"]) is int and plan["schema_version"] == 1,
                     "invalid frozen plan fields")
            _require(payload["plan_sha256"] == digest(plan), "frozen plan digest mismatch")
            _require(plan["hypotheses"] == hypotheses and plan["tests"] == tests,
                     "frozen plan differs from registered history")
            _require(plan["problem_sha256"] == digest(events[0]["payload"]["problem"])
                     and plan["binding_sha256"] == digest(binding), "frozen plan context mismatch")
            _require(set(active_action) in ({"action", "claim"}, {"action", "claim", "structures"})
                     and ledger.validate_dossier(active_action["claim"], allow_pending=True) == plan["dossier"]
                     and validate_structures(active_action.get("structures", []), hypotheses, tests) == plan["structures"],
                     "frozen plan differs from submitted action")
            ledger.validate_dossier(plan["dossier"], allow_pending=True)
            _require(len(plan["dossier"]["replication_tests"]) <= 8, "too many frozen tests")
            _require(set(plan["dossier"]["replication_tests"]) == {test["id"] for test in tests if test["phase"] == "replication"},
                     "frozen plan omits registered sealed tests")
            phase = "testing"
        elif kind == "experiment_charge":
            _require(pending_charge is None and phase in {"exploring", "testing"},
                     "experiment charge outside native execution")
            _require(isinstance(active_action, dict)
                     and active_action.get("action") == ("experiment" if phase == "exploring" else "commit"),
                     "experiment charge lacks native action")
            _require(set(payload) == {"units", "tool"} and _integer(payload["units"], 1),
                     "invalid recorded experiment charge")
            charges.append(payload)
            pending_charge = payload
        elif kind == "native_observation":
            _require(pending_charge is not None and phase in {"exploring", "testing"},
                     "native observation lacks unique charge")
            _require(set(payload) == {"evidence_id", "action", "observation", "phase"},
                     "invalid native observation fields")
            call = payload["action"]
            _require(payload["evidence_id"] == "experiment-%04d" % len(charges)
                     and pending_charge["tool"] == call["tool"], "native evidence charge mismatch")
            if phase == "exploring":
                action_native += 1
                _require(action_native == 1, "multiple exploratory observations in one action")
                _require(payload["phase"] == "exploration"
                         and active_action == {"action": "experiment", **call},
                         "native exploration lacks its action")
                if call.get("test_id") is not None:
                    _require(ledger.get_test(call["test_id"])["phase"] == "exploration",
                             "sealed evidence before commitment")
            else:
                frozen_ids = plan["dossier"]["replication_tests"]
                _require(payload["phase"] == "replication" and len(executed_replications) < len(frozen_ids)
                         and call.get("test_id") == frozen_ids[len(executed_replications)],
                         "sealed evidence differs from frozen test order")
                _require(ledger.get_test(call["test_id"])["phase"] == "replication",
                         "sealed evidence has an exploration test")
                executed_replications.append(call["test_id"])
                replicas.append({"evidence_id": payload["evidence_id"], "observation": payload["observation"],
                                 "charged_units": pending_charge["units"]})
            ledger.record_observation(payload["evidence_id"], call, payload["observation"])
            if phase == "exploring":
                exploration_response = {
                    "ok": True, "evidence_id": payload["evidence_id"],
                    "observation": payload["observation"], "charged_units": pending_charge["units"],
                    "remaining_units": resources["budget_units"] - sum(charge["units"] for charge in charges),
                }
            native += 1
            pending_charge = None
        elif kind == "sealed_results":
            _require(phase == "testing" and results is None and pending_charge is None,
                     "sealed results outside testing")
            _require(set(payload) == {"results", "results_sha256"}, "invalid sealed results fields")
            results = payload["results"]
            expected = {"schema_version": 1, "plan_sha256": digest(plan), "observations": replicas}
            _require(executed_replications == plan["dossier"]["replication_tests"]
                     and results == expected and type(results["schema_version"]) is int
                     and payload["results_sha256"] == digest(results),
                     "sealed result package incomplete or inconsistent")
            frozen_response = {"ok": True, "plan_sha256": digest(plan), "results_sha256": digest(results),
                               "results": results, "next_action": "submit_interpretation",
                               "episode_complete": False}
            phase = "interpreting"
        elif kind == "interpretation_submitted":
            _require(phase == "interpreting" and posttest_actions == 1 and interpretation is None
                     and isinstance(active_action, dict)
                     and active_action.get("action") == "submit_interpretation",
                     "interpretation freeze lacks its sole action")
            _require(set(payload) == {"interpretation", "interpretation_sha256"},
                     "invalid interpretation freeze fields")
            interpretation = validate_interpretation(payload["interpretation"], plan, results, ledger)
            _require(active_action == {"action": "submit_interpretation", "interpretation": interpretation}
                     and payload["interpretation_sha256"] == digest(interpretation),
                     "interpretation differs from action or digest")
        elif kind == "outcome":
            _require(phase == "interpreting" and interpretation is not None and outcomes == 0,
                     "outcome before final interpretation")
            expected_metrics = build_posttest_metrics(ledger, plan, results, interpretation, events)
            _require(payload == {"metrics": expected_metrics, "plan_sha256": digest(plan),
                                 "results_sha256": digest(results),
                                 "interpretation_sha256": digest(interpretation)},
                     "posttest outcome differs from replay")
            outcomes += 1
            phase = "completed"
            final_response = {"ok": True, "interpretation_sha256": digest(interpretation), "episode_complete": True}
        elif kind == "observation":
            _require(active_action is not _NO_ACTION, "observation lacks its action")
            _require(isinstance(payload, dict) and type(payload.get("ok")) is bool,
                     "invalid public action response")
            if payload["ok"]:
                action = active_action.get("action") if isinstance(active_action, dict) else None
                if action in {"experiment", "hypothesize", "revise_hypothesis", "plan_test"}:
                    _require(exploration_response is not None,
                             "successful exploration response lacks its native record")
                elif action == "analyze":
                    _require(action_analyses == 1,
                             "successful analysis response lacks its execution record")
                elif action == "commit":
                    _require(frozen_response is not None,
                             "successful commit response lacks both freezes")
                elif action == "submit_interpretation":
                    _require(final_response is not None,
                             "successful interpretation response lacks its final freeze")
                else:
                    raise ValueError("successful response to an unknown action")
            if exploration_response is not None:
                # A synchronous exploratory action may have completed just as
                # the wall budget expired; the runtime then suppresses delivery.
                if failed:
                    _require(report["error"] == "wall_budget_exhausted"
                             and payload == {"ok": False, "error": "budget_exhausted"},
                             "exploratory response differs from failure")
                else:
                    _require(payload == exploration_response,
                             "exploratory response differs from native record")
                exploration_response = None
            if frozen_response is not None:
                _require(payload == frozen_response, "candidate did not receive the full sealed result package")
                frozen_response = None
            if final_response is not None:
                _require(payload == final_response, "final interpretation response mismatch")
                final_response = None
            observations += 1
            active_action = _NO_ACTION
        elif kind == "failure":
            _require(not failed and phase != "completed" and set(payload) == {"status", "error"},
                     "failure outside active episode")
            _require(payload["status"] == report["status"] and payload["error"] == report["error"],
                     "failure differs from report")
            failed = True
        else:
            raise ValueError("unknown posttest event kind")

    for key, count in (("steps", actions), ("experiment_calls", len(charges)),
                       ("experiment_units", sum(charge["units"] for charge in charges)),
                       ("analysis_calls", analyses)):
        _require(resources[key] == count if complete else resources[key] >= count,
                 "posttest resource accounting mismatch")
    if complete:
        _require(actions == observations and active_action is _NO_ACTION, "posttest turn accounting mismatch")
        for name, value in (("plan", plan), ("results", results), ("interpretation", interpretation)):
            _require(report.get(name) == value
                     and report.get(name + "_sha256") == (digest(value) if value is not None else None),
                     "posttest report freeze binding mismatch")
        _require(report.get("claim") == (plan["dossier"] if plan is not None else None)
                 and report.get("claim_sha256") == (digest(plan["dossier"]) if plan is not None else None)
                 and report.get("confirmation") == results, "legacy report aliases differ from frozen data")
    if report["status"] == "completed":
        _require(complete and phase == "completed" and not failed and outcomes == 1
                 and native == len(charges) and pending_charge is None,
                 "completed posttest report is incomplete")
        _require(report["metrics"] == build_posttest_metrics(ledger, plan, results, interpretation, events),
                 "posttest metrics differ from replay")
    else:
        # The cap can be reached while recording the final public response,
        # after an outcome event. Preserve that prefix without granting a result.
        _require(report.get("metrics") is None and (outcomes == 0 or not complete),
                 "unfinished posttest episode carries metrics")
        if complete and not failed:
            _require(report["status"] == phase or (phase == "testing" and report["status"] == "test_plan_committed"),
                     "posttest report status differs from replay")
    return {"status": "structurally_consistent" if complete else "incomplete_evidence",
            "scientific_validity": "not_assessed", "ground_truth_used": False}


def validate_posttest_report(report):
    """Validate bounded resources and replay both immutable freezes."""
    try:
        return _validate_posttest_report(report)
    except (KeyError, TypeError, IndexError, AttributeError, RecursionError, OverflowError) as exc:
        raise ValueError("malformed posttest report") from exc
