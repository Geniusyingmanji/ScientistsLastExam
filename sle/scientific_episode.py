"""Trusted, stateful discovery episodes with an immutable confirmation boundary.

Only explicitly registered local adapters are loadable. Candidate Python goes through
CandidateProxy, never exec/import in this process. This is a pilot execution
protocol, not a scientific certification or a replacement for the legacy oracle.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import stat
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOTS = {
    "CausalDiscovery/SurvivorshipAuditDesign": "ComputerScience/SurvivorshipAuditDesign",
    "SystemsBiology/EnzymeMechanismDiscovery": "Biology/EnzymeMechanismDiscovery",
    "CausalDiscovery/CausalTransportDiscovery": "ComputerScience/CausalTransportDiscovery",
    "SystemsBiology/EnzymeRecoveryDesign": "Biology/EnzymeRecoveryDesign",
}
PILOT_ROLES = {
    "CausalDiscovery/SurvivorshipAuditDesign": "historical_control",
    "SystemsBiology/EnzymeMechanismDiscovery": "protocol_only",
    "CausalDiscovery/CausalTransportDiscovery": "hardening_candidate",
    "SystemsBiology/EnzymeRecoveryDesign": "hardening_candidate",
}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024


class EvidenceLimitError(RuntimeError):
    pass


def json_copy(value):
    text = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("episode payload exceeds size limit")
    return json.loads(text)


def digest(value):
    return hashlib.sha256(json.dumps(value, allow_nan=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_json(text):
    """Bounded JSON with no duplicate keys or nonfinite values at any depth."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("action is not bounded JSON")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("nonfinite JSON value")

    return json_copy(json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant))


def parse_action(text):
    """Accept exactly one JSON object; duplicate keys and nonfinite values fail."""
    value = parse_json(text)
    if not isinstance(value, dict):
        raise ValueError("action must be an object")
    return json_copy(value)


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(name + " must be a positive integer")
    return value


def _task_directory(task):
    matches = [key for key in PILOTS if task == key or task == key.split("/")[-1]]
    if len(matches) != 1:
        raise ValueError("unknown discovery episode pilot; use sle episode --list")
    task_id = matches[0]
    path = ROOT / "benchmarks" / PILOTS[task_id]
    if path.resolve() != path:
        raise ValueError("episode package cannot be a symlink")
    return task_id, path


def _load_module(path):
    name = "sle_episode_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ValueError("episode adapter is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def create_environment(task, seed):
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("private seed must be a nonnegative integer")
    task_id, path = _task_directory(task)
    module = _load_module(path / "verification" / "episode.py")
    environment = module.create_environment(seed)
    if environment.task_id != task_id:
        raise ValueError("adapter task identity mismatch")
    return environment


def source_binding(task):
    task_id, path = _task_directory(task)
    files = {}
    for source in sorted(path.rglob("*")):
        if source.is_file() and source.suffix in {".py", ".yaml", ".md", ".json"}:
            if {"__pycache__", "runs", ".pytest_cache"} & set(source.relative_to(path).parts):
                continue
            if source.is_symlink():
                raise ValueError("episode source cannot be a symlink")
            files[source.relative_to(path).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    runtime = {}
    for parent in (path.parent, path.parent.parent):
        initializer = parent / "__init__.py"
        if initializer.is_file():
            runtime[initializer.relative_to(ROOT).as_posix()] = hashlib.sha256(initializer.read_bytes()).hexdigest()
    for source in sorted((ROOT / "sle").rglob("*.py")):
        runtime[source.relative_to(ROOT).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    from .runtime_identity import current_runtime_descriptor
    return {"task_id": task_id, "evaluation_role": PILOT_ROLES[task_id],
            "task_files": files, "task_sha256": digest(files),
            "runtime_source_sha256": digest(runtime),
            "runtime": current_runtime_descriptor(("numpy", "scipy"))}


def public_files(task):
    _task_id, path = _task_directory(task)
    # An explicit allowlist: never discover files recursively for the agent.
    return {name: (path / name).read_text(encoding="utf-8")
            for name in ("Task.md", "model.py") if (path / name).is_file()}


class EpisodeSession:
    """Private environment ownership; public responses cannot contain evaluator output."""

    def __init__(self, environment, *, max_steps=64, wall_seconds=300.0,
                 analysis=None, clock=time.monotonic, binding=None):
        self.environment = environment
        self.max_steps = _positive_int(max_steps, "max_steps")
        if self.max_steps > 1024:
            raise ValueError("max_steps exceeds 1024")
        if (isinstance(wall_seconds, bool) or not isinstance(wall_seconds, (int, float))
                or not math.isfinite(wall_seconds) or wall_seconds <= 0):
            raise ValueError("wall_seconds must be positive and finite")
        self.clock = clock
        self.started = clock()
        self.deadline = self.started + wall_seconds
        self.wall_seconds = float(wall_seconds)
        self.verification_seconds = 0.0
        self.budget_units = _positive_int(environment.budget_units, "budget_units")
        self.analysis = analysis
        self.binding = json_copy(binding or {"task_id": environment.task_id})
        self.problem = json_copy(environment.public_problem())
        if self.problem.get("budget_units") != self.budget_units:
            raise ValueError("public and private budget differ")
        self.state = "exploring"
        self.steps = self.units = self.experiments = self.analysis_calls = 0
        self.events = []
        self.transcript = []
        self.evidence_bytes = 0
        self.recording_complete = True
        self.claim = self.confirmation = self.metrics = None
        self.claim_sha256 = None
        self.error = None
        self._record("start", {"problem": self.problem, "binding": self.binding})

    @property
    def done(self):
        return self.state != "exploring"

    def _record(self, kind, payload):
        payload = json_copy(payload)
        event = {"seq": len(self.events), "kind": kind, "payload": payload,
                 "previous_sha256": self.events[-1]["sha256"] if self.events else None}
        event["sha256"] = digest(event)
        size = len(json.dumps(event).encode("utf-8"))
        if self.evidence_bytes + size > MAX_EVIDENCE_BYTES:
            self.recording_complete = False
            raise EvidenceLimitError("episode evidence size limit reached")
        self.events.append(event)
        self.evidence_bytes += size

    def observation(self):
        return {"task_id": self.environment.task_id, "problem": json_copy(self.problem),
                "protocol": {
                    "actions": ["experiment", "commit"] + (["analyze"] if self.analysis else []),
                    "experiment": {"action": "experiment", "tool": "public tool name", "arguments": {}},
                    "commit": {"action": "commit", "claim": "object conforming to claim_schema"},
                    "analyze": {"action": "analyze", "code": "Python; set result to a JSON value"},
                    "confirmation": "commit is immutable; fresh observations follow; no resubmission",
                    "max_steps": self.max_steps, "budget_units": self.budget_units,
                    "analysis_available": self.analysis is not None,
                }}

    def _fail(self, status, error):
        self.state = status
        self.error = error
        self.metrics = None
        try:
            self._record("failure", {"status": status, "error": error})
        except EvidenceLimitError:
            self.state = "evidence_limit"
            self.error = "evidence_limit"

    def stop(self, status="budget_exhausted"):
        if not self.done:
            self._fail(status, status)

    def _expired(self):
        return self.clock() >= self.deadline

    def step(self, request):
        try:
            return self._step(request)
        except EvidenceLimitError:
            self.state = "evidence_limit"
            self.error = "evidence_limit"
            self.metrics = None
            return {"ok": False, "error": "evidence_limit"}

    def _step(self, request):
        if self.done:
            return {"ok": False, "error": "episode_closed"}
        if self._expired() or self.steps >= self.max_steps:
            self.stop()
            return {"ok": False, "error": "budget_exhausted"}
        self.steps += 1
        try:
            request = json_copy(request)
        except (TypeError, ValueError, RecursionError):
            request = {"action": "invalid"}
        self._record("action", request)
        try:
            response = self._dispatch(request)
        except EvidenceLimitError:
            raise
        except Exception as exc:
            # The full exception may contain hidden scientific state. Public
            # feedback uses fixed categories; private reports keep only its type.
            self._fail("infrastructure_error", type(exc).__name__)
            response = {"ok": False, "error": "environment_failure"}
        # Confirmation is an operator-reserved phase, outside the agent budget.
        # A completed scientific check must not turn into agent time exhaustion.
        if self._expired() and self.state == "exploring":
            self._fail("budget_exhausted", "wall_budget_exhausted")
            response = {"ok": False, "error": "budget_exhausted"}
        response = json_copy(response)
        self._record("observation", response)
        self.transcript.append({"request": request, "response": response})
        return json_copy(response)

    def _dispatch(self, request):
        if not isinstance(request, dict):
            return {"ok": False, "error": "invalid_action"}
        action = request.get("action")
        if action == "experiment" and set(request) == {"action", "tool", "arguments"}:
            try:
                cost = self.environment.action_cost(request["tool"], json_copy(request["arguments"]))
            except ValueError:
                return {"ok": False, "error": "invalid_experiment_arguments"}
            cost = _positive_int(cost, "experiment cost")
            if self.units + cost > self.budget_units:
                return {"ok": False, "error": "experiment_budget_exceeded", "remaining_units": self.budget_units - self.units}
            self.units += cost
            self.experiments += 1
            self._record("experiment_charge", {"units": cost, "tool": request["tool"]})
            observed = json_copy(self.environment.experiment(request["tool"], json_copy(request["arguments"])))
            return {"ok": True, "observation": observed, "charged_units": cost,
                    "remaining_units": self.budget_units - self.units}
        if action == "analyze" and set(request) == {"action", "code"}:
            if self.analysis is None:
                return {"ok": False, "error": "analysis_unavailable"}
            if not isinstance(request["code"], str) or len(request["code"]) > 100000:
                return {"ok": False, "error": "invalid_analysis"}
            self.analysis_calls += 1
            self._record("analysis_started", {})
            try:
                value = self.analysis(request["code"], self.problem, json_copy(self.transcript))
            except TimeoutError:
                self._fail("budget_exhausted", "analysis_timeout")
                return {"ok": False, "error": "analysis_timeout"}
            except Exception:
                self._fail("invalid_candidate", "analysis_worker_failed")
                return {"ok": False, "error": "analysis_worker_failed"}
            return {"ok": True, "analysis": json_copy(value)}
        if action == "commit" and set(request) == {"action", "claim"}:
            claim = json_copy(request["claim"])
            try:
                self.environment.validate_claim(claim)
            except ValueError:
                return {"ok": False, "error": "invalid_claim"}
            if self._expired():
                self.stop()
                return {"ok": False, "error": "budget_exhausted"}
            # Store before calling either verifier method, on detached objects.
            self.claim = json_copy(claim)
            self.claim_sha256 = digest(self.claim)
            self.state = "committed"
            self._record("commit", {"claim": self.claim, "claim_sha256": self.claim_sha256})
            verification_started = self.clock()
            self.confirmation = json_copy(self.environment.confirm(json_copy(self.claim)))
            self._record("confirmation", self.confirmation)
            self.metrics = json_copy(self.environment.evaluate(json_copy(self.claim), json_copy(self.confirmation)))
            self.verification_seconds = self.clock() - verification_started
            if not isinstance(self.metrics, dict):
                raise ValueError("private metrics must be an object")
            self._record("outcome", {"metrics": self.metrics, "claim_sha256": self.claim_sha256,
                                     "confirmation_sha256": digest(self.confirmation)})
            self.state = "completed"
            return {"ok": True, "committed": True, "claim_sha256": self.claim_sha256,
                    "confirmation": json_copy(self.confirmation), "episode_complete": True}
        return {"ok": False, "error": "invalid_action"}

    def report(self):
        value = {"schema_version": 1, "kind": "scientific_episode_pilot",
                 "status": self.state, "binding": self.binding,
                 "resources": {"steps": self.steps, "max_steps": self.max_steps,
                               "experiment_calls": self.experiments, "experiment_units": self.units,
                               "budget_units": self.budget_units, "analysis_calls": self.analysis_calls,
                               "max_wall_seconds": self.wall_seconds,
                               "verification_wall_seconds": self.verification_seconds,
                               "wall_seconds": self.clock() - self.started},
                 "claim": self.claim, "claim_sha256": self.claim_sha256,
                 "confirmation": self.confirmation, "metrics": self.metrics,
                 "error": self.error, "events": self.events,
                 "recording_complete": self.recording_complete,
                 "evidence_semantics": "hashes bind content, not origin; process scientific validity not assessed",
                 "frontier_eligible": False, "difficulty": "calibration_required"}
        # Reports may contain a large but bounded event sequence.
        value = json.loads(json.dumps(value, allow_nan=False))
        value["sha256"] = digest(value)
        return value


def validate_episode_report(report):
    """Structural and resource checks, not authentication or scientific review."""
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("invalid episode report")
    if (report.get("kind") != "scientific_episode_pilot"
            or report.get("frontier_eligible") is not False
            or report.get("difficulty") != "calibration_required"
            or report.get("status") not in {
                "exploring", "committed", "completed", "budget_exhausted", "invalid_candidate",
                "model_error", "infrastructure_error", "evidence_limit", "incomplete_delivery"}):
        raise ValueError("invalid pilot status or eligibility")
    body = {key: value for key, value in report.items() if key != "sha256"}
    if report.get("sha256") != digest(body):
        raise ValueError("episode report digest mismatch")
    events = report.get("events", [])
    if not events or events[0].get("kind") != "start" or events[0]["payload"].get("binding") != report["binding"]:
        raise ValueError("episode start binding missing")
    if sum(e.get("kind") == "start" for e in events) != 1:
        raise ValueError("episode must have exactly one start")
    previous = None
    for seq, event in enumerate(events):
        core = {key: value for key, value in event.items() if key != "sha256"}
        if event.get("seq") != seq or event.get("previous_sha256") != previous or event.get("sha256") != digest(core):
            raise ValueError("episode event chain mismatch")
        previous = event["sha256"]
    resources = report["resources"]
    for name in ("steps", "max_steps", "experiment_calls", "experiment_units", "budget_units", "analysis_calls"):
        value = resources[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("resource counts must be nonnegative integers")
    if resources["max_steps"] == 0 or resources["budget_units"] == 0:
        raise ValueError("resource budgets must be positive")
    for name in ("wall_seconds", "max_wall_seconds", "verification_wall_seconds"):
        value = resources[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("resource times must be finite and nonnegative")
    if not 0 <= resources["steps"] <= resources["max_steps"]:
        raise ValueError("episode exceeded step budget")
    complete = report.get("recording_complete") is True
    if not complete and (report["status"] != "evidence_limit" or report.get("metrics") is not None):
        raise ValueError("incomplete evidence cannot support scientific outcomes")
    if complete and resources["steps"] != sum(e["kind"] == "action" for e in events):
        raise ValueError("action count mismatch")
    if complete and resources["steps"] != sum(e["kind"] == "observation" for e in events):
        raise ValueError("observation count mismatch")
    charges = [e["payload"]["units"] for e in events if e["kind"] == "experiment_charge"]
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in charges):
        raise ValueError("invalid recorded experiment charge")
    if complete and (resources["experiment_calls"] != len(charges) or resources["experiment_units"] != sum(charges)):
        raise ValueError("experiment accounting mismatch")
    if complete and resources["analysis_calls"] != sum(e["kind"] == "analysis_started" for e in events):
        raise ValueError("analysis accounting mismatch")
    if not 0 <= resources["experiment_units"] <= resources["budget_units"]:
        raise ValueError("episode exceeded experiment budget")
    commits = [e for e in report["events"] if e["kind"] == "commit"]
    confirms = [e for e in report["events"] if e["kind"] == "confirmation"]
    if commits and any(e["kind"] == "action" and e["seq"] > commits[0]["seq"] for e in events):
        raise ValueError("action after commitment")
    if report["status"] == "completed":
        if len(commits) != 1 or len(confirms) != 1 or commits[0]["seq"] >= confirms[0]["seq"]:
            raise ValueError("confirmation must follow one immutable commitment")
        if report["claim_sha256"] != digest(report["claim"]):
            raise ValueError("claim binding mismatch")
        if commits[0]["payload"] != {"claim": report["claim"], "claim_sha256": report["claim_sha256"]}:
            raise ValueError("recorded commitment mismatch")
        if confirms[0]["payload"] != report["confirmation"] or not isinstance(report["metrics"], dict):
            raise ValueError("confirmation or outcome missing")
        outcomes = [e for e in events if e["kind"] == "outcome"]
        expected = {"metrics": report["metrics"], "claim_sha256": report["claim_sha256"],
                    "confirmation_sha256": digest(report["confirmation"])}
        if len(outcomes) != 1 or outcomes[0]["seq"] <= confirms[0]["seq"] or outcomes[0]["payload"] != expected:
            raise ValueError("private outcome binding mismatch")
    elif report.get("metrics") is not None:
        raise ValueError("incomplete episodes cannot carry scientific scores")
    return {"status": "structurally_consistent" if complete else "incomplete_evidence",
            "scientific_validity": "not_assessed"}


class SandboxAnalysis:
    """Persistent candidate-only Python; all scientific data arrives as JSON."""

    def __init__(self, task, timeout_s):
        from .secure_eval import CandidateProxy
        self.files = public_files(task)
        self.worker = CandidateProxy(Path(__file__).with_name("episode_analysis_worker.py"),
                                     "analyze", timeout_s=timeout_s)

    def __call__(self, code, problem, transcript):
        return self.worker({"code": code, "problem": problem, "history": transcript,
                            "public_files": self.files})

    def close(self):
        self.worker.close()


def run_policy(session, solve):
    """Operator-reviewed baselines only; untrusted policy code uses the sandbox."""
    def execute(tool, arguments):
        response = session.step({"action": "experiment", "tool": tool, "arguments": arguments})
        if not response.get("ok"):
            raise ValueError(response.get("error", "experiment_failed"))
        return response["observation"]
    try:
        claim = solve(json_copy(session.problem), execute)
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


def run_llm(session, llm, files=None):
    from .episode_deadline import call_with_deadline
    system = ("You are solving a scientific discovery episode. Reply with exactly one JSON action, "
              "without Markdown fences. Use the public experiment schemas and budgets. "
              "Commit a claim only after analyzing evidence. Commitment ends exploration permanently; "
              "confirmation is new data and cannot be used to revise the committed claim. "
              "When analyze is available, problem, history and public_files are Python variables; "
              "assign result to a JSON value. No evaluator scores are available.")
    initial = {"observation": session.observation(), "public_files": files or {}}
    while not session.done:
        if session.steps >= session.max_steps or session._expired():
            session.stop()
            break
        try:
            if hasattr(llm, "config") and hasattr(llm.config, "timeout_seconds"):
                llm.config.timeout_seconds = min(llm.config.timeout_seconds,
                                                max(0.001, session.deadline - session.clock()))
            prompt = json.dumps({**initial, "history": session.transcript}, allow_nan=False)
            reply = call_with_deadline(lambda: llm.complete(prompt, system=system),
                                       max(0.001, session.deadline - session.clock()))
        except TimeoutError:
            session._fail("budget_exhausted", "model_call_timeout")
            break
        except Exception as exc:
            session._fail("budget_exhausted" if session._expired() else "model_error", type(exc).__name__)
            break
        # Account for every completed transport call, including malformed output.
        try:
            action = parse_action(reply)
        except (ValueError, TypeError, RecursionError):
            action = {"action": "invalid"}
        if isinstance(reply, str) and len(reply.encode("utf-8")) <= MAX_JSON_BYTES // 2:
            reply_record = {"text": reply}
        else:
            reply_record = {"invalid_reply_type": type(reply).__name__, "oversized": isinstance(reply, str)}
        try:
            session._record("model_reply", {**reply_record, "usage": json_copy(llm.last_usage),
                                             "stop_reason": llm.last_stop_reason})
        except EvidenceLimitError:
            session.state = "evidence_limit"
            session.error = "evidence_limit"
            session.metrics = None
            break
        session.step(action)
    return session.report()


def prepare_output(path):
    path = Path(path).absolute()
    # Full results include private seeds and oracle outcomes. A private mode bit
    # on a file in a checkout does not make it safe to commit or expose to agents.
    if any((parent / ".git").exists() for parent in (path,) + tuple(path.parents)):
        raise ValueError("episode evidence must be outside Git workspaces")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.getuid() or path.resolve() != path):
        raise ValueError("episode evidence directory must be owner-only and not a symlink")
    if (path / "episode.json").exists():
        raise ValueError("episode output already exists; choose a new directory")
    return path


def save_report(directory, report):
    validate_episode_report(report)
    directory = prepare_output(directory)
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    path = Path(directory) / "episode.json"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path
