"""Evaluator-owned, sealed evidence at the candidate/callback boundary.

This records observable actions, not private reasoning or proof that observations
caused a decision. Existing scientific scores and candidate APIs are unchanged.
Hashes bind records; authentication comes from the enclosing trusted run evidence.
"""
from __future__ import annotations

import hashlib
import json

from .discovery_profiles import pilot_contract
from .rpc_codec import encode

SCHEMA_VERSION = 1
MAX_TRACE_BYTES = 32 * 1024 * 1024
MAX_EVENTS_PER_INSTANCE = 512


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


class DiscoveryRecorder:
    """Wrap only host-owned callbacks; never accept a candidate's self-authored log."""

    def __init__(self, candidate, task_id, *, candidate_sha256, oracle_sha256,
                 max_bytes=MAX_TRACE_BYTES):
        self.candidate = candidate
        self.task_id = task_id
        self.contract = pilot_contract(task_id)
        if self.contract is None:
            raise ValueError("task has no discovery recording adapter")
        self.identity = {"task_id": task_id, "candidate_sha256": candidate_sha256,
                         "oracle_sha256": oracle_sha256,
                         "contract_sha256": digest(self.contract)}
        self.instances = []
        self.remaining_bytes = max_bytes

    def reset_session(self):
        reset = getattr(self.candidate, "reset_session", None)
        if callable(reset):
            reset()

    def _snapshot(self, value):
        try:
            # Serialization detaches arrays/maps before the candidate can mutate them.
            rendered = json.dumps(encode(value), allow_nan=False, separators=(",", ":"))
            size = len(rendered.encode())
            if size > self.remaining_bytes:
                return {"status": "unavailable", "reason": "trace_size_limit"}
            self.remaining_bytes -= size
            return {"status": "recorded", "value": json.loads(rendered)}
        except (TypeError, ValueError, OverflowError, RecursionError):
            # A malformed candidate artifact must not turn a scientific rejection into
            # an evaluator failure. The oracle still receives the unchanged artifact.
            return {"status": "unavailable", "reason": "unsupported_payload"}

    def _event(self, instance, kind, value, **attributes):
        events = instance["events"]
        if len(events) >= MAX_EVENTS_PER_INSTANCE:
            instance["dropped_event_count"] += 1
            instance["capture_complete"] = False
            return None
        payload = self._snapshot(value)
        if payload["status"] != "recorded":
            instance["capture_complete"] = False
        event = {"seq": len(events), "kind": kind, "payload": payload,
                 "previous_sha256": events[-1]["sha256"] if events else None,
                 **attributes}
        event["sha256"] = digest(event)
        events.append(event)
        return event["seq"]

    def _callback(self, instance, name, callback):
        def recorded(*args, **kwargs):
            request_seq = self._event(instance, "callback_request",
                                      {"args": list(args), "kwargs": kwargs}, tool=name)
            try:
                result = callback(*args, **kwargs)
            except Exception as exc:
                self._event(instance, "callback_error", {"exception_type": type(exc).__name__},
                            tool=name, request_seq=request_seq)
                raise
            self._event(instance, "callback_result", result, tool=name, request_seq=request_seq)
            return result
        return recorded

    def __call__(self, *args, **kwargs):
        instance = {"instance_id": "instance-%04d" % len(self.instances),
                    "capture_complete": True, "dropped_event_count": 0, "events": []}
        self.instances.append(instance)
        recorded_args = list(args)
        public_args = list(args)
        for position, name in self.contract["callbacks"].items():
            if position >= len(args) or not callable(args[position]):
                raise ValueError("discovery adapter no longer matches oracle callback interface")
            recorded_args[position] = self._callback(instance, name, args[position])
            public_args[position] = {"callback": name}
        self._event(instance, "input", {"args": public_args, "kwargs": kwargs})
        try:
            result = self.candidate(*recorded_args, **kwargs)
        except Exception as exc:
            self._event(instance, "candidate_error", {"exception_type": type(exc).__name__})
            raise
        self._event(instance, "submission", result)
        return result

    def finish(self, metrics, *, evaluation_complete=True):
        rows = metrics.get("per_confirmation_world", metrics.get("per_world"))
        matched = isinstance(rows, list) and len(rows) == len(self.instances)
        for index, instance in enumerate(self.instances):
            if not matched:
                instance["outcome"] = {"status": "unavailable"}
                continue
            row = rows[index]
            if not isinstance(row, dict) or "split" not in row or "world_index" not in row:
                raise ValueError("discovery outcome lacks an explicit split/world identity")
            instance["outcome"] = {
                "status": "oracle_evaluated", "split": row["split"],
                "world_index": row["world_index"], "valid": row["valid"],
                "axes": {group: {key: row[key] for key in names if key in row}
                         for group, names in self.contract["result_axes"].items()},
            }
        if evaluation_complete and not matched:
            raise ValueError("discovery candidate calls and oracle outcome rows do not align")
        evidence = {
            "schema_version": SCHEMA_VERSION, "producer": "trusted_evaluator_callback_boundary",
            "identity": self.identity, "world_type": "simulation",
            "evaluation_complete": evaluation_complete,
            "capture_complete": all(i["capture_complete"] for i in self.instances),
            "instances": self.instances,
        }
        evidence["sha256"] = digest(evidence)
        return evidence


def validate_evidence(evidence, *, expected_candidate_sha256=None):
    """Check detached records without executing recorded code or accepting self-reports.

    A successful check establishes structural consistency, not authentication,
    scientific correctness, field novelty, or benchmark task certification.
    """
    if (not isinstance(evidence, dict) or type(evidence.get("schema_version")) is not int
            or evidence.get("schema_version") != SCHEMA_VERSION):
        raise ValueError("unsupported discovery evidence schema")
    if evidence.get("producer") != "trusted_evaluator_callback_boundary":
        raise ValueError("unsupported discovery evidence producer")
    if evidence.get("world_type") != "simulation":
        raise ValueError("pilot evidence must remain explicitly simulated")
    if evidence.get("sha256") != digest({k: v for k, v in evidence.items() if k != "sha256"}):
        raise ValueError("discovery evidence digest mismatch")
    identity = evidence.get("identity") or {}
    if not isinstance(identity, dict):
        raise ValueError("invalid discovery identity")
    contract = pilot_contract(identity.get("task_id"))
    if contract is None or identity.get("contract_sha256") != digest(contract):
        raise ValueError("discovery adapter mismatch; use the producing runtime")
    for key in ("candidate_sha256", "oracle_sha256", "contract_sha256"):
        value = identity.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("invalid discovery identity hash")
    if expected_candidate_sha256 is not None and identity["candidate_sha256"] != expected_candidate_sha256:
        raise ValueError("discovery evidence belongs to another candidate")
    if type(evidence.get("evaluation_complete")) is not bool or type(evidence.get("capture_complete")) is not bool:
        raise ValueError("invalid discovery completeness flag")
    instances = evidence.get("instances")
    if not isinstance(instances, list):
        raise ValueError("discovery instances must be a list")
    if evidence["evaluation_complete"] and not instances:
        raise ValueError("complete discovery evaluation has no instances")
    outcomes = set()
    all_complete = True
    for index, instance in enumerate(instances):
        if not isinstance(instance, dict) or instance.get("instance_id") != "instance-%04d" % index:
            raise ValueError("invalid discovery instance order")
        if type(instance.get("capture_complete")) is not bool:
            raise ValueError("invalid instance completeness flag")
        dropped = instance.get("dropped_event_count")
        if type(dropped) is not int or dropped < 0:
            raise ValueError("invalid dropped event count")
        events = instance.get("events")
        if not isinstance(events, list):
            raise ValueError("discovery events must be a list")
        previous, pending, terminal = None, None, False
        complete = dropped == 0
        for seq, event in enumerate(events):
            if not isinstance(event, dict) or type(event.get("seq")) is not int or event.get("seq") != seq or terminal:
                raise ValueError("invalid event order")
            if event.get("previous_sha256") != previous or event.get("sha256") != digest(
                    {k: v for k, v in event.items() if k != "sha256"}):
                raise ValueError("event chain mismatch")
            previous = event["sha256"]
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("invalid event payload")
            if payload.get("status") not in {"recorded", "unavailable"}:
                raise ValueError("invalid payload status")
            if payload["status"] == "recorded" and "value" not in payload:
                raise ValueError("missing recorded payload")
            complete = complete and payload["status"] == "recorded"
            kind = event.get("kind")
            if seq == 0:
                if kind != "input":
                    raise ValueError("instance must begin with public input")
            elif kind == "callback_request":
                if pending is not None or event.get("tool") not in contract["callbacks"].values():
                    raise ValueError("invalid callback request")
                pending = (seq, event["tool"])
            elif kind in {"callback_result", "callback_error"}:
                if pending is None or (event.get("request_seq"), event.get("tool")) != pending:
                    raise ValueError("observation has no preceding matching request")
                pending = None
            elif kind in {"submission", "candidate_error"}:
                if pending is not None:
                    raise ValueError("submission precedes callback completion")
                terminal = True
            else:
                raise ValueError("unknown discovery event")
        complete = complete and terminal and pending is None
        if instance["capture_complete"] and not complete:
            raise ValueError("incomplete trace claims complete capture")
        all_complete = all_complete and instance["capture_complete"]
        outcome = instance.get("outcome")
        if not isinstance(outcome, dict):
            raise ValueError("invalid outcome")
        if outcome.get("status") == "oracle_evaluated":
            key = (outcome.get("split"), outcome.get("world_index"))
            if key[0] not in {"unsplit", "development", "heldout", "validation", "confirmation"} or type(key[1]) is not int or key[1] < 0:
                raise ValueError("invalid outcome split/world identity")
            if key in outcomes:
                raise ValueError("duplicate outcome identity")
            outcomes.add(key)
            if type(outcome.get("valid")) is not bool or not isinstance(outcome.get("axes"), dict):
                raise ValueError("invalid outcome")
            if set(outcome["axes"]) != set(contract["result_axes"]):
                raise ValueError("invalid outcome axis groups")
            for group, values in outcome["axes"].items():
                if not isinstance(values, dict) or not set(values) <= set(contract["result_axes"][group]):
                    raise ValueError("unknown outcome axis")
        elif outcome.get("status") != "unavailable" or evidence["evaluation_complete"]:
            raise ValueError("complete evaluation is missing outcome evidence")
    if evidence["capture_complete"] != all_complete:
        raise ValueError("aggregate capture status mismatch")
    return True


def evidence_report(metrics, *, expected_candidate_sha256=None):
    if metrics.get("infrastructure_failure"):
        return {"status": "infrastructure_failure", "process": "unobserved",
                "discovery_certification": "not_assessed"}
    evidence = metrics.get("discovery_evidence")
    if evidence is None:
        return {"status": "not_recorded", "process": "unobserved",
                "discovery_certification": "not_assessed"}
    validate_evidence(evidence, expected_candidate_sha256=expected_candidate_sha256)
    if evidence["evaluation_complete"]:
        outcomes = metrics.get("per_confirmation_world", metrics.get("per_world"))
        if not isinstance(outcomes, list) or len(outcomes) != len(evidence["instances"]):
            raise ValueError("discovery evidence lacks matching oracle result rows")
        contract = pilot_contract(evidence["identity"]["task_id"])
        for instance, source in zip(evidence["instances"], outcomes):
            if not isinstance(source, dict):
                raise ValueError("invalid oracle result row")
            expected = {"status": "oracle_evaluated", "split": source.get("split"),
                        "world_index": source.get("world_index"), "valid": source.get("valid"),
                        "axes": {group: {k: source[k] for k in keys if k in source}
                                 for group, keys in contract["result_axes"].items()}}
            if instance["outcome"] != expected:
                raise ValueError("recorded outcome differs from oracle result row")
    rows = []
    for instance in evidence["instances"]:
        events = instance["events"]
        submitted = next((e for e in events if e["kind"] == "submission"), None)
        inputs = [e["seq"] for e in events if e["kind"] in {"input", "callback_result"}]
        commitments = [e["seq"] for e in events if e["kind"] == "callback_request" and e["tool"] == "confirm"]
        rows.append({
            "instance_id": instance["instance_id"],
            "process": {
                "capture_status": "recorded" if instance["capture_complete"] else "incomplete",
                "successful_callbacks": sum(e["kind"] == "callback_result" for e in events),
                "failed_callbacks": sum(e["kind"] == "callback_error" for e in events),
                "available_evidence_seq": inputs,
                "submission_seq": submitted["seq"] if submitted else None,
                "pre_result_commit_request_seq": commitments,
                "evidence_use": "not_inferred_from_availability",
                "reasoning_quality": "not_scored",
                "repair_quality": "not_assessed",
            },
            "result": instance["outcome"],
            "discovery_certification": "not_assessed",
        })
    return {"status": "structurally_consistent", "identity": evidence["identity"],
            "authentication": "requires_enclosing_trusted_run_verification",
            "world_type": evidence["world_type"],
            "evaluation_complete": evidence["evaluation_complete"],
            "capture_complete": evidence["capture_complete"], "rows": rows}


def checked_science_metrics(metrics, *, expected_candidate_sha256=None):
    """Separate verified telemetry for exact direct-vs-sandbox science comparison.

    Only the newly added telemetry field is excluded. Missing/incomplete traces,
    broken bindings and changed scientific fields cannot silently pass calibration.
    This structural check still relies on the caller's trusted evaluator provenance.
    """
    report = evidence_report(metrics, expected_candidate_sha256=expected_candidate_sha256)
    if (report["status"] != "structurally_consistent"
            or not report["evaluation_complete"] or not report["capture_complete"]):
        raise ValueError("calibration requires complete discovery evidence")
    return {key: value for key, value in metrics.items() if key != "discovery_evidence"}
