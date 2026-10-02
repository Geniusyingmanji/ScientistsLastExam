"""Trusted broker for public JSON actions, evidence and terminal confirmation."""
from __future__ import annotations

import hashlib
import platform
from pathlib import Path

import numpy
import scipy

from .kernel import VERSION
from .lab import MicroecologyLab, public_description
from .verification import claim_schema, validate_claims, verify_claims
from .protocol import API_VERSION, EventLog, InvalidAction, clone, digest, identifier, keys


def source_binding():
    paths = ("kernel.py", "lab.py", "verification.py", "protocol.py", "session.py", "cli.py", "demo.py")
    return {"sources": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in paths},
            "runtime": {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__}}


class WorldSession:
    def __init__(self, seed=0, *, budget=1200, confirmation_budget=4000, max_steps=1000):
        for value in (budget, confirmation_budget, max_steps):
            if type(value) is not int or not 1 <= value <= 10000:
                raise ValueError("invalid resource limit")
        self.lab = MicroecologyLab(seed)
        self._binding = source_binding()
        self.budget, self.confirmation_budget, self.max_steps = budget, confirmation_budget, max_steps
        self.spent = self.steps = 0
        self.state = "exploring"
        self.log = EventLog()
        self._requests = {}
        self._evidence = set()
        self.claims = self.verification = self.interpretation = None
        self.claim_hash = None
        self.log.append("start", self.describe())

    def describe(self):
        return {**public_description(), "budget_units": self.budget,
                "confirmation_budget_units": self.confirmation_budget, "max_steps": self.max_steps,
                "request_schema": {"request_id": "unique identifier; identical retries are idempotent",
                                   "operation": "tool name or commit or interpret", "arguments": "object"},
                "commit": {"arguments": {"claims": claim_schema()},
                           "effect": "Freezes claims and closes exploration; new experiments check predictions. No replacement claims."},
                "interpret": {"arguments": {"claim_sha256": "commit receipt", "text": "final explanation of all results"},
                              "effect": "One final read-only interpretation; no further experiments."}}

    def step(self, request):
        try:
            request = clone(request)
            keys(request, ("request_id", "operation", "arguments"), ("api_version",))
            rid = identifier(request["request_id"])
            if "api_version" in request and request["api_version"] != API_VERSION:
                raise InvalidAction("unsupported_api_version")
            if not isinstance(request["operation"], str) or not isinstance(request["arguments"], dict):
                raise InvalidAction("invalid_action")
        except (ValueError, TypeError, OverflowError, RecursionError):
            return {"ok": False, "error": "invalid_request"}
        request_hash = digest(request)
        if rid in self._requests:
            prior_hash, response = self._requests[rid]
            return clone(response) if prior_hash == request_hash else {"ok": False, "error": "request_id_conflict"}
        if self.state in ("completed", "infrastructure_error", "budget_exhausted"):
            return {"ok": False, "error": "session_closed"}
        if source_binding() != self._binding:
            self.state = "infrastructure_error"
            self.log.append("failure", {"category": "source_or_runtime_changed"})
            return {"ok": False, "error": "source_or_runtime_changed"}
        if self.steps >= self.max_steps:
            self.state = "budget_exhausted"
            self.log.append("stop", {"reason": "step_limit"})
            return {"ok": False, "error": "step_limit"}
        self.steps += 1
        self.log.append("request", request)
        try:
            response = self._dispatch(request["operation"], request["arguments"])
        except InvalidAction as error:
            response = {"ok": False, "error": str(error)}
        except Exception as error:
            self.state = "infrastructure_error"
            # Do not expose exception text, internal arrays, recipe, or stack.
            self.log.append("failure", {"category": "infrastructure_error", "exception_type": type(error).__name__})
            response = {"ok": False, "error": "environment_failure"}
        response = clone(response)
        self.log.append("response", response)
        self._requests[rid] = (request_hash, response)
        return clone(response)

    def _dispatch(self, operation, args):
        if operation == "interpret":
            if self.state != "interpreting":
                raise InvalidAction("interpretation_not_available")
            keys(args, ("claim_sha256", "text"))
            if args["claim_sha256"] != self.claim_hash:
                raise InvalidAction("claim_binding_mismatch")
            if not isinstance(args["text"], str) or not 1 <= len(args["text"]) <= 16000:
                raise InvalidAction("invalid_interpretation")
            self.interpretation = clone(args)
            self.state = "completed"
            self.log.append("interpretation", args)
            return {"ok": True, "state": self.state}
        if self.state != "exploring":
            raise InvalidAction("exploration_closed")
        if operation == "commit":
            keys(args, ("claims",))
            claims, cost = validate_claims(args["claims"], self._evidence)
            if cost > self.confirmation_budget:
                raise InvalidAction("confirmation_budget_exceeded")
            self.claims = claims
            self.claim_hash = digest(claims)
            self.state = "confirming"
            self.log.append("commit", {"claims": claims, "claim_sha256": self.claim_hash, "reserved_units": cost})
            self.verification = verify_claims(self.lab, claims, self.log)
            if self.verification["charged_units"] != cost:
                raise RuntimeError("confirmation_cost_mismatch")
            self.state = "interpreting"
            return {"ok": True, "state": self.state, "claim_sha256": self.claim_hash,
                    "verification": clone(self.verification)}
        cost = self.lab.validate(operation, args)
        if self.spent + cost > self.budget:
            raise InvalidAction("experiment_budget_exceeded")
        observation = self.lab.execute(operation, args)
        self.spent += cost
        if "observation_id" in observation:
            self._evidence.add(observation["observation_id"])
        return {"ok": True, "observation": observation, "charged_units": cost,
                "remaining_units": self.budget - self.spent, "time_h": self.lab.time_h}

    def report(self, *, private=False):
        report = {"api_version": API_VERSION, "world_version": VERSION, "state": self.state,
                  "resources": {"experiment_units": self.spent, "budget_units": self.budget,
                                "confirmation_budget_units": self.confirmation_budget,
                                "steps": self.steps, "max_steps": self.max_steps},
                  "claims": clone(self.claims), "claim_sha256": self.claim_hash,
                  "verification": clone(self.verification), "interpretation": clone(self.interpretation),
                  "events": clone(self.log.events), "discovery_depth": None,
                  "scientific_status": "prototype; numerical contrasts checked, mechanisms and novelty unassessed"}
        if private:
            report["reproducibility"] = clone(self._binding)
            report["operator_recipe"] = {"seed": self.lab._seed, "mechanism": vars(self.lab.kernel.mechanism),
                                         "channels": self.lab._channels}
            report["material_balance_residual_mmol"] = self.lab.carbon_residual()
        report["sha256"] = digest(report)
        return report


def replay_report(report):
    """Replay trusted JSON actions only; never execute candidate code from a report."""
    if report.get("world_version") != VERSION or "operator_recipe" not in report:
        raise ValueError("replay_requires_matching_version_and_private_recipe")
    if digest({k: v for k, v in report.items() if k != "sha256"}) != report["sha256"]:
        raise ValueError("altered_report")
    EventLog.validate(report["events"])
    if report.get("reproducibility") != source_binding():
        raise ValueError("replay_requires_matching_source_and_runtime")
    resources = report["resources"]
    session = WorldSession(report["operator_recipe"]["seed"], budget=resources["budget_units"],
                           confirmation_budget=resources["confirmation_budget_units"], max_steps=resources["max_steps"])
    for event in report["events"]:
        if event["kind"] == "request":
            session.step(event["payload"])
        elif event["kind"] == "stop":
            session.state = "budget_exhausted"
            session.log.append("stop", event["payload"])
    expected = session.report(private=True)
    if expected != report:
        raise ValueError("replay_mismatch")
    return {"status": "exact_replay_passed", "events": len(report["events"])}
