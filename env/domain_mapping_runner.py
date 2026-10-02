"""Separate single-model domain executor using unchanged prospective transport.

Only operator specs enter candidate workers. Verification executes neither a
World nor candidate code. A trusted receipt head is mandatory for verification.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import secrets
import sys
import time

from . import domain_mapping as evidence
from . import prospective_runner as transport
from .registry import ENVIRONMENTS, load_world


DEFAULT_LIMITS = {
    "actions": 1, "experiments": 96, "experiment_units": 10000,
    "predictor_calls": 24, "predictor_seconds": 120.0,
    "predictor_seconds_per_call": 5.0, "predictor_memory_mb": 2048,
    "simulation_seconds": 300.0, "simulation_seconds_per_call": 3.0,
    "wall_seconds": 900.0, "artifact_bytes": 64 * 1024 * 1024,
    "wall_margin_seconds": 30.0,
}
MAX_INPUT_BYTES, MAX_DOCUMENT_BYTES = 512 * 1024, 8 * 1024 * 1024
BINDING_SCHEMA = "sle-domain-runtime-binding-0.2"
AUDIT_SCHEMA = "sle-domain-resource-audit-0.2"
REPLAY_SOURCE_IDS = ("env/domain_mapping.py", "env/domain_mapping_runner.py", "env/prospective.py",
                     "env/analysis_api.py", "env/claim_semantics.py", "env/registry.py", "env/prospective_runner.py")


def _repo_root():
    return Path(__file__).resolve().parents[1]


def _source_path(logical_id):
    if (type(logical_id) is not str or "\\" in logical_id or
            PurePosixPath(logical_id).as_posix() != logical_id or
            not logical_id.startswith(("env/", "sle/")) or not logical_id.endswith(".py") or
            any(part in ("", ".", "..") for part in logical_id.split("/"))):
        raise ValueError("invalid logical source identity")
    return _repo_root().joinpath(*logical_id.split("/"))


def _seconds(value, label):
    if type(value) not in (int, float):
        raise ValueError("invalid " + label)
    try:
        valid = math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("invalid " + label)
    return value


def _counter(value, label):
    if type(value) is not int or value < 0:
        raise ValueError("invalid " + label)
    return value


def _retained_bytes(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _limits(changes=None):
    if changes is not None and (type(changes) is not dict or set(changes) - set(DEFAULT_LIMITS)):
        raise ValueError("unknown domain limit")
    result = dict(DEFAULT_LIMITS, **(changes or {}))
    for name, maximum in DEFAULT_LIMITS.items():
        value = result[name]
        _seconds(value, "limit " + name)
        if (not 0 < value <= maximum or
                (type(maximum) is int and type(value) is not int)):
            raise ValueError("limits may only reduce positive domain ceilings")
    return result


def _read_bytes(path, maximum=MAX_DOCUMENT_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("missing, symlink or oversized artifact")
    content = path.read_bytes()
    if len(content) > maximum:
        raise ValueError("oversized artifact")
    return content


def read_json(path, maximum=MAX_DOCUMENT_BYTES):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON")
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite JSON")
        return number
    return json.loads(_read_bytes(path, maximum), object_pairs_hook=pairs,
                      parse_constant=invalid, parse_float=finite)


def _runtime_binding(world):
    binding = transport._runtime_binding(world)
    directory = Path(__file__).parent
    additions = [Path(__file__), Path(evidence.__file__)]
    additions += [directory / name for name in ("analysis_api.py", "claim_semantics.py", "registry.py")]
    additions.append(directory.parent / "sle" / "episode_deadline.py")
    binding["source_files"].update({str(p.resolve()): _sha(p.read_bytes()) for p in additions})
    # Absolute roots are provenance only. Logical IDs are the replay keys.
    sources = {}
    for original, expected in binding["source_files"].items():
        logical = Path(original).resolve().relative_to(_repo_root()).as_posix()
        _source_path(logical)
        if logical in sources:
            raise ValueError("ambiguous runtime source identity")
        sources[logical] = expected
    binding["source_files"] = sources
    binding["binding_schema"] = BINDING_SCHEMA
    binding["origin_root"] = str(_repo_root())
    binding["domain_protocol"] = evidence.PROTOCOL
    binding["arithmetic"] = "Python Fraction and Decimal precision 80 with rational upper-bound verification"
    return binding


class _QuotaJournal(transport.PrivateJournal):
    def __init__(self, root, maximum, started):
        self.maximum = maximum
        self.started = started
        self.finished_elapsed = {}
        super().__init__(root)

    def append(self, kind, payload):
        payload = deepcopy(payload)
        if "_domain_audit" in payload:
            raise ValueError("reserved resource audit field")
        payload["_domain_audit"] = {"schema": AUDIT_SCHEMA, "wall_elapsed_seconds": time.monotonic()-self.started}
        used = _retained_bytes(self.root.parent)
        # Reserve space for a final small report/head even after a large entry.
        if used + len(_encoded(payload)) + 1024 + 262144 > self.maximum:
            raise transport.TaskBudgetExceeded("artifact budget exhausted")
        receipt = super().append(kind, payload)
        if kind in ("prediction_attempt_finished", "observation_attempt_finished"):
            self.finished_elapsed[kind] = payload["elapsed_seconds"]
        return receipt


class DomainMappingTask(transport.ProspectiveTask):
    """Own lifecycle; reuse only guarded prediction/observation transport methods.

    Does not call ProspectiveTask.__init__, build a two-rival session, or permit
    source acquisition and preregistration through the historical entry points.
    """

    def __init__(self, environment, seed, directory, *, limits=None):
        self._limits = _limits(limits)
        if environment not in ENVIRONMENTS or type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError("invalid registered domain environment or seed")
        self.directory = Path(directory).absolute()
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir(mode=0o700)
        self._started = time.monotonic()
        self._journal = _QuotaJournal(self.directory / "receipts", self._limits["artifact_bytes"], self._started)
        self._candidates = self.directory / "candidates"
        self._candidates.mkdir(mode=0o700)
        self._state, self._phase, self._error = "active", "created", None
        self._records, self._registration, self._evidence, self._plan = [], None, None, None
        self._namespace, self._noise_keys = secrets.token_hex(16), set()
        self._pending = None
        self._usage = {"actions": 0, "experiment_attempts": 0, "experiment_units": 0,
                       "predictor_attempts": 0, "predictor_seconds_charged": 0.0,
                       "predictor_seconds_actual": 0.0, "simulation_seconds_actual": 0.0}
        self._binding = None
        try:
            self._world = load_world(environment, seed)[0]
            self._contract = transport._observation_contract(self._world)
            self._binding = _runtime_binding(self._world)
            self._runtime_id = evidence.digest(self._binding)
            archive = self.directory / "runtime-sources"
            archive.mkdir(mode=0o700)
            for logical, expected in self._binding["source_files"].items():
                content = _read_bytes(_source_path(logical))
                if _sha(content) != expected:
                    raise ValueError("runtime source changed during binding")
                destination = archive / (expected + ".src")
                if not destination.exists():
                    self._publish_bytes(destination, content)
            metadata = {"protocol": evidence.PROTOCOL, "transport_envelope_protocol": transport.RUNNER_PROTOCOL,
                        "audit_schema": AUDIT_SCHEMA,
                        "environment": environment, "private_world_seed": seed, "limits": self._limits,
                        "public_contract": self._contract, "runtime_binding": self._binding,
                        "runtime_id": self._runtime_id}
            self._publish("operator-private.json", metadata)
            self._event("domain_created", {"operator_metadata_sha256": evidence.digest(metadata)})
            self._checkpoint()
        except Exception as error:
            self._fail(error)
            raise

    def _publish_bytes(self, path, content, *, replace=False):
        used = sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file())
        old = path.stat().st_size if replace and path.is_file() else 0
        if used - old + len(content) > self._limits["artifact_bytes"]:
            raise transport.TaskBudgetExceeded("artifact budget exhausted")
        transport._atomic_bytes(path, content, replace=replace)

    def _publish(self, name, value, *, replace=False):
        content = _encoded(value)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise transport.TaskBudgetExceeded("artifact document too large")
        self._publish_bytes(self.directory / name, content, replace=replace)

    def _event(self, kind, payload):
        return self._journal.append(kind, dict(payload, protocol=evidence.PROTOCOL))

    def _guard(self):
        self._require_active()
        if self._remaining_wall() <= 0:
            raise transport.TaskBudgetExceeded("wall budget exhausted")
        if self._binding is not None:
            for logical, expected in self._binding["source_files"].items():
                if _sha(_read_bytes(_source_path(logical))) != expected:
                    raise ValueError("runtime source changed after binding")

    def _predict(self, code, spec):
        if self._phase != "predicting_all_points":
            raise RuntimeError("prediction outside preseal phase")
        values = super()._predict(code, spec)
        if self._journal.finished_elapsed["prediction_attempt_finished"] > self._limits["predictor_seconds_per_call"]:
            raise transport.TaskBudgetExceeded("actual per-call prediction budget exhausted")
        return values

    def _observe(self, spec, *, noise_key):
        if (self._phase != "collecting_fixed_family" or self._registration is None or self._pending is None or
                noise_key != self._pending["noise_key"] or evidence.digest(spec) != self._pending["spec_sha256"]):
            raise RuntimeError("observation without sealed planned acquisition")
        values = super()._observe(spec, noise_key=noise_key)
        if self._journal.finished_elapsed["observation_attempt_finished"] > self._limits["simulation_seconds_per_call"]:
            raise transport.TaskBudgetExceeded("actual per-call simulation budget exhausted")
        return values

    def observe_source(self, spec):
        raise RuntimeError("source evidence must precede the domain task")

    def preregister(self, request):
        raise RuntimeError("use the separate single-model run method")

    def describe(self):
        return {"protocol": evidence.PROTOCOL, "observation_contract": deepcopy(self._contract),
                "limits": deepcopy(self._limits), "boundary_identified": False,
                "mechanism_identified": False, "discovery_depth_certified": False}

    def _admit_domain(self, plan):
        observations = sum(p["replicates"] for p in plan["points"])
        calls = 2 * len(plan["points"])
        costs = {p["id"]: self._world.cost(p["spec"]) for p in plan["points"]}
        if any(type(c) is not int or c <= 0 for c in costs.values()):
            raise ValueError("invalid public experiment cost")
        units = sum(costs[p["id"]] * p["replicates"] for p in plan["points"])
        predicted_seconds = calls * self._limits["predictor_seconds_per_call"]
        observed_seconds = observations * self._limits["simulation_seconds_per_call"]
        # Numeric cells are bounded by _matrix; budget both raw transport and
        # domain receipts plus all prediction passes and the sealed table.
        matrix_bytes = {p["id"]: 512 + 32 * len(p["spec"][plan["public"]["axis_field"]]) * len(plan["public"]["channels"]) for p in plan["points"]}
        planned_bytes = 2 * MAX_INPUT_BYTES + 1048576 + sum((4 + 2*p["replicates"]) * matrix_bytes[p["id"]] for p in plan["points"])
        admission_elapsed = time.monotonic()-self._started
        admission_remaining = self._limits["wall_seconds"]-admission_elapsed
        if (observations > self._limits["experiments"] or units > self._limits["experiment_units"] or
                calls > self._limits["predictor_calls"] or predicted_seconds > self._limits["predictor_seconds"] or
                observed_seconds > self._limits["simulation_seconds"] or
                predicted_seconds + observed_seconds + self._limits["wall_margin_seconds"] > admission_remaining or
                planned_bytes > self._limits["artifact_bytes"]):
            raise transport.TaskBudgetExceeded("entire domain family does not fit budget")
        admitted = {"observation_calls": observations, "point_costs": costs, "observation_units": units,
                    "prediction_calls": calls, "prediction_seconds_reserved": predicted_seconds,
                    "simulation_seconds_reserved": observed_seconds, "artifact_bytes_reserved": planned_bytes,
                    "wall_elapsed_at_admission": admission_elapsed, "wall_seconds_remaining_at_admission": admission_remaining}
        self._event("domain_admitted", admitted)

    def run(self, request, snapshot, source_history, *, original_inputs=None):
        """One immutable family; synchronous execution has no adaptive interface."""
        self._require_active()
        try:
            if self._phase != "created":
                raise RuntimeError("domain family cannot be replaced or retried")
            self._guard()
            self._usage["actions"] += 1
            self._event("domain_run_started", {"attempt": self._usage["actions"]})
            if any(len(_encoded(v)) > MAX_INPUT_BYTES for v in (request, snapshot, source_history)):
                raise ValueError("domain input exceeds byte limit")
            plan = evidence.validate_plan(deepcopy(request), self._contract, self._world.validate, deepcopy(source_history))
            code, binding = evidence.resolve_model(snapshot, plan["model_snapshot"])
            self._guard()
            self._publish("input-plan.json", request)
            self._publish("input-snapshot.json", snapshot)
            self._publish("source-history.json", source_history)
            self._publish("canonical-plan.json", plan)
            original_hashes = {}
            if original_inputs is not None:
                evidence.keys(original_inputs, ("plan", "snapshot", "source-history"), "original inputs")
                for name, content in original_inputs.items():
                    if type(content) is not bytes or len(content) > MAX_INPUT_BYTES:
                        raise ValueError("invalid original input bytes")
                    path = self.directory / ("original-" + name + ".json")
                    self._publish_bytes(path, content)
                    value = read_json(path, MAX_INPUT_BYTES)
                    expected = {"plan": request, "snapshot": snapshot, "source-history": source_history}[name]
                    if value != expected:
                        raise ValueError("original bytes differ from parsed input")
                    original_hashes[path.name] = _sha(content)
            self._event("domain_input", {"request_sha256": evidence.digest(request), "snapshot_sha256": evidence.digest(snapshot),
                                        "source_history_sha256": evidence.digest(source_history), "binding": binding,
                                        "canonical_plan_sha256": evidence.digest(plan), "original_input_sha256": original_hashes})
            self._plan = plan
            self._admit_domain(plan)
            self._phase = "predicting_all_points"
            predictions, repeated = {}, {}
            for point in plan["points"]:
                for index, target in enumerate((predictions, repeated)):
                    values = self._predict(code, deepcopy(point["spec"]))
                    target[point["id"]] = values
                    self._event("domain_prediction", {"point_id": point["id"], "pass": index,
                                                      "spec_sha256": evidence.digest(point["spec"]), "values": values})
            registration = evidence.seal(plan, snapshot, predictions, repeated, self._runtime_id)
            self._publish("registration.json", registration)
            self._event("domain_sealed", {"seal_sha256": registration["seal_sha256"]})
            self._registration = registration
            self._phase = "collecting_fixed_family"
            for point in plan["points"]:
                for replica in range(point["replicates"]):
                    planned = {"id": "obs-%s-%02d" % (point["id"], replica), "point_id": point["id"], "replica": replica,
                               "spec_sha256": evidence.digest(point["spec"]),
                               "noise_key": "%s:%s:%d" % (self._namespace, point["id"], replica)}
                    self._event("domain_observation_planned", planned)
                    self._pending = planned
                    response = self._observe(deepcopy(point["spec"]), noise_key=planned["noise_key"])
                    record = dict(planned, observation=response)
                    self._event("domain_observation", {"record": record, "record_sha256": evidence.digest(record)})
                    self._records.append(record)
                    self._pending = None
                self._refresh_evidence()
                self._checkpoint()
            return self.finish()
        except Exception as error:
            self._fail(error)
            raise

    def _refresh_evidence(self):
        if self._registration is not None:
            self._evidence = evidence.recompute(self._registration, self._records,
                expected_seal=self._registration["seal_sha256"], expected_observations_sha256=evidence.digest(self._records))

    def public_records(self):
        return [{"id": r["id"], "point_id": r["point_id"], "replica": r["replica"],
                 "observation": deepcopy(r["observation"])} for r in self._records]

    def public_report(self):
        return {"protocol": evidence.PROTOCOL, "status": self._state, "phase": self._phase, "error": self._error,
                "environment": getattr(getattr(self, "_world", None), "name", None),
                "limits": deepcopy(self._limits), "usage": deepcopy(self._usage),
                "public_plan": evidence.public_plan(self._plan), "evidence": deepcopy(self._evidence), "receipt_head": self._journal.head,
                "boundary_identified": False, "mechanism_identified": False, "discovery_depth_certified": False}

    def _checkpoint(self):
        self._publish("report.json", self.public_report(), replace=True)

    def _terminal(self, state, reason):
        self._refresh_evidence()
        self._event("domain_terminal", {"status": state, "reason": reason, "usage": deepcopy(self._usage),
                                        "observations_sha256": evidence.digest(self._records), "evidence": self._evidence})
        self._state, self._error = state, reason
        self._phase = "closed"
        self._checkpoint()

    def _fail(self, error):
        if self._state != "active":
            return
        reason = ("budget_exhausted" if isinstance(error, transport.TaskBudgetExceeded) else
                  str(error) if isinstance(error, (transport.CandidateExecutionFailed, transport.PredictorInfrastructureFailed,
                                                  transport.PredictorInitializationUnresolved)) else type(error).__name__)
        try:
            self._terminal("incomplete" if isinstance(error, transport.TaskBudgetExceeded) else "failed", reason)
        except Exception:
            self._state, self._phase, self._error = "failed", "closed", "artifact_persistence_failed"

    def finish(self):
        self._require_active()
        self._guard()
        self._refresh_evidence()
        if self._evidence is None or not self._evidence["complete_family"]:
            raise ValueError("cannot finish an incomplete finite family")
        self._terminal("completed", None)
        return self.public_report()

    def close(self, reason="operator_stopped"):
        if reason != "operator_stopped":
            raise ValueError("invalid domain close reason")
        if self._state == "active":
            self._terminal("incomplete", reason)
        return self.public_report()


def verify_domain_directory(directory, *, expected_head):
    """Authenticate the complete journal or retained failed prefix; never run code."""
    evidence.hash_value(expected_head)
    root = Path(directory)
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("symlink in domain bundle")
    head = read_json(root / "receipts" / "head.json")
    evidence.keys(head, ("sequence", "sha256"), "receipt head")
    if head["sha256"] != expected_head or type(head["sequence"]) is not int or not 1 <= head["sequence"] <= 4096:
        raise ValueError("external receipt head mismatch")
    files = sorted((root / "receipts").glob("[0-9]*.json"))
    if len(files) != head["sequence"]:
        raise ValueError("receipt count mismatch")
    metadata = read_json(root / "operator-private.json")
    evidence.keys(metadata, ("protocol", "transport_envelope_protocol", "audit_schema", "environment", "private_world_seed",
                             "limits", "public_contract", "runtime_binding", "runtime_id"), "operator metadata")
    if (metadata["protocol"] != evidence.PROTOCOL or metadata["audit_schema"] != AUDIT_SCHEMA or
            metadata["transport_envelope_protocol"] != transport.RUNNER_PROTOCOL or
            metadata["runtime_id"] != evidence.digest(metadata["runtime_binding"])):
        raise ValueError("operator runtime binding mismatch")
    evidence.keys(metadata["limits"], DEFAULT_LIMITS, "complete resource limits")
    limits = _limits(metadata["limits"])
    retained_bytes = _retained_bytes(root)
    if retained_bytes > limits["artifact_bytes"]:
        raise ValueError("retained artifact quota exceeded")
    binding = metadata["runtime_binding"]
    if binding.get("binding_schema") != BINDING_SCHEMA or type(binding.get("source_files")) is not dict:
        raise ValueError("unsupported logical runtime binding schema")
    if not set(REPLAY_SOURCE_IDS) <= set(binding["source_files"]):
        raise ValueError("missing required replay source identity")
    for logical_id, source_hash in binding["source_files"].items():
        _source_path(logical_id)
        evidence.hash_value(source_hash)
        if _sha(_read_bytes(root / "runtime-sources" / (source_hash + ".src"))) != source_hash:
            raise ValueError("archived runtime source mismatch")
    # Numeric replay requires this implementation, not an unversioned upgrade.
    for logical_id in REPLAY_SOURCE_IDS:
        path = _source_path(logical_id)
        expected = binding["source_files"][logical_id]
        if expected != _sha(path.read_bytes()):
            raise ValueError("numeric replay implementation changed")
    previous, request, snapshot, source, plan, registration = None, None, None, None, None, None
    predictions, repeated, records, pending, started, returned = {}, {}, [], None, None, None
    predictor_started, predictor_finished, prediction_pending = 0, 0, False
    observation_started, observation_finished = 0, 0
    attempted_noise_keys, units_charged, predictor_charged = set(), 0, 0.0
    predictor_elapsed, observation_elapsed = 0.0, 0.0
    prediction_started_wall, observation_started_wall, previous_wall = None, None, 0.0
    execution_blocked = False
    admitted, terminal, sealed, run_started = None, None, False, False
    for index, path in enumerate(files, 1):
        entry = read_json(path)
        evidence.keys(entry, ("protocol", "sequence", "previous_sha256", "kind", "payload", "sha256"), "receipt")
        if (path.name != "%06d.json" % index or entry["protocol"] != transport.RUNNER_PROTOCOL or
                entry["sequence"] != index or entry["previous_sha256"] != previous or
                evidence.digest({k: v for k, v in entry.items() if k != "sha256"}) != entry["sha256"]):
            raise ValueError("receipt chain mismatch")
        previous = entry["sha256"]
        kind, payload = entry["kind"], deepcopy(entry["payload"])
        if type(kind) is not str or type(payload) is not dict:
            raise ValueError("invalid journal event")
        audit = payload.pop("_domain_audit", None)
        evidence.keys(audit, ("schema", "wall_elapsed_seconds"), "resource audit stamp")
        wall = _seconds(audit["wall_elapsed_seconds"], "event wall duration")
        if audit["schema"] != AUDIT_SCHEMA or wall < previous_wall:
            raise ValueError("invalid monotone resource audit")
        prior_event_wall = previous_wall
        previous_wall = wall
        if execution_blocked and kind != "domain_terminal":
            raise ValueError("execution continued after failed or over-budget call")
        if terminal is not None:
            raise ValueError("events after terminal state")
        if (index == 1) != (kind == "domain_created"):
            raise ValueError("domain creation order mismatch")
        if kind.startswith("domain_") and payload.get("protocol") != evidence.PROTOCOL:
            raise ValueError("domain event protocol mismatch")
        if kind == "domain_created":
            if payload["operator_metadata_sha256"] != evidence.digest(metadata):
                raise ValueError("operator metadata anchor mismatch")
        elif kind == "domain_run_started":
            if run_started or type(payload["attempt"]) is not int or payload["attempt"] != 1:
                raise ValueError("repeated domain run")
            run_started = True
        elif kind == "domain_input":
            if request is not None or admitted is not None or not run_started:
                raise ValueError("replaced input family")
            request, snapshot, source = [read_json(root / name, MAX_INPUT_BYTES) for name in
                                         ("input-plan.json", "input-snapshot.json", "source-history.json")]
            if any(evidence.digest(value) != payload[key] for key, value in
                   (("request_sha256", request), ("snapshot_sha256", snapshot), ("source_history_sha256", source))):
                raise ValueError("input artifact anchor mismatch")
            # Canonical specs were validated by the trusted World before input
            # publication. Replay validates public semantics without importing it.
            canonical = read_json(root / "canonical-plan.json")
            if evidence.digest(canonical) != payload["canonical_plan_sha256"]:
                raise ValueError("canonical plan anchor mismatch")
            normalized = deepcopy(request)
            if len(normalized["points"]) != len(canonical["points"]):
                raise ValueError("canonical point count mismatch")
            for original, point in zip(normalized["points"], canonical["points"]):
                original["spec"] = deepcopy(point["spec"])
            plan = evidence.validate_plan(normalized, metadata["public_contract"], deepcopy, source)
            if plan != canonical:
                raise ValueError("canonical public plan mismatch")
            original_hashes = payload["original_input_sha256"]
            if type(original_hashes) is not dict or set(original_hashes) - {"original-plan.json", "original-snapshot.json", "original-source-history.json"}:
                raise ValueError("invalid original input paths")
            for name, wanted in original_hashes.items():
                if _sha(_read_bytes(root / name, MAX_INPUT_BYTES)) != wanted:
                    raise ValueError("original input bytes changed")
            code, binding = evidence.resolve_model(snapshot, plan["model_snapshot"])
            if binding != payload["binding"]:
                raise ValueError("snapshot binding mismatch")
        elif kind == "domain_admitted":
            if plan is None or admitted is not None:
                raise ValueError("admission order mismatch")
            admitted = payload
            evidence.keys(payload, ("protocol", "observation_calls", "point_costs", "observation_units", "prediction_calls",
                                    "prediction_seconds_reserved", "simulation_seconds_reserved", "artifact_bytes_reserved",
                                    "wall_elapsed_at_admission", "wall_seconds_remaining_at_admission"), "family admission")
            for field in ("observation_calls", "observation_units", "prediction_calls", "artifact_bytes_reserved"):
                _counter(payload[field], field)
            if (payload["prediction_calls"] != 2*len(plan["points"]) or
                    payload["observation_calls"] != sum(p["replicates"] for p in plan["points"])):
                raise ValueError("admitted counts mismatch")
            costs = payload["point_costs"]
            if (type(costs) is not dict or set(costs) != {p["id"] for p in plan["points"]} or
                    any(type(c) is not int or c <= 0 for c in costs.values()) or
                    payload["observation_units"] != sum(costs[p["id"]]*p["replicates"] for p in plan["points"])):
                raise ValueError("admitted cost binding mismatch")
            predicted_seconds = payload["prediction_calls"] * limits["predictor_seconds_per_call"]
            observed_seconds = payload["observation_calls"] * limits["simulation_seconds_per_call"]
            planned_bytes = 2*MAX_INPUT_BYTES + 1048576 + sum(
                (4+2*p["replicates"])*(512+32*len(p["spec"][plan["public"]["axis_field"]])*len(plan["public"]["channels"]))
                for p in plan["points"])
            admission_elapsed = _seconds(payload["wall_elapsed_at_admission"], "admission wall duration")
            remaining = _seconds(payload["wall_seconds_remaining_at_admission"], "admission remaining wall")
            if (payload["prediction_seconds_reserved"] != predicted_seconds or
                    payload["simulation_seconds_reserved"] != observed_seconds or payload["artifact_bytes_reserved"] != planned_bytes or
                    not prior_event_wall <= admission_elapsed <= wall or remaining != limits["wall_seconds"]-admission_elapsed or
                    payload["observation_calls"] > limits["experiments"] or payload["prediction_calls"] > limits["predictor_calls"] or
                    payload["observation_units"] > limits["experiment_units"] or predicted_seconds > limits["predictor_seconds"] or
                    observed_seconds > limits["simulation_seconds"] or planned_bytes > limits["artifact_bytes"] or
                    predicted_seconds+observed_seconds+limits["wall_margin_seconds"] > remaining):
                raise ValueError("family admission violates resource limits or reservations")
        elif kind == "prediction_attempt_started":
            if admitted is None or sealed or prediction_pending:
                raise ValueError("prediction attempt order mismatch")
            point = plan["points"][predictor_started // 2] if predictor_started < admitted["prediction_calls"] else None
            if (point is None or type(payload["attempt"]) is not int or payload["code_sha256"] != _sha(code.encode("utf-8")) or
                    payload["spec_sha256"] != evidence.digest(point["spec"]) or payload["attempt"] != predictor_started+1):
                raise ValueError("prediction attempt binding mismatch")
            predictor_started += 1
            if payload["seconds_charged"] != metadata["limits"]["predictor_seconds_per_call"]:
                raise ValueError("prediction allowance changed")
            predictor_charged += payload["seconds_charged"]
            prediction_pending = True
            prediction_started_wall = wall
        elif kind == "prediction_attempt_finished":
            if not prediction_pending or type(payload["attempt"]) is not int or payload["attempt"] != predictor_started:
                raise ValueError("prediction finish order mismatch")
            if type(payload["ok"]) is not bool or type(payload["cleanup_failed"]) is not bool:
                raise ValueError("invalid prediction result boolean")
            if (payload["failure_stage"] not in (None, "artifact", "sandbox_initialization", "candidate_call") or
                    (payload["ok"] and (payload["failure_stage"] is not None or payload["cleanup_failed"]))):
                raise ValueError("invalid prediction failure semantics")
            elapsed = _seconds(payload["elapsed_seconds"], "prediction elapsed duration")
            if elapsed > wall-prediction_started_wall:
                raise ValueError("prediction duration exceeds elapsed wall interval")
            predictor_elapsed += elapsed
            execution_blocked = (not payload["ok"] or elapsed > limits["predictor_seconds_per_call"] or
                                 predictor_elapsed > limits["predictor_seconds"] or wall > limits["wall_seconds"])
            prediction_pending = False
            predictor_finished += int(payload["ok"] and not payload["cleanup_failed"])
        elif kind == "domain_prediction":
            total = len(predictions) + len(repeated)
            if predictor_finished != total+1 or prediction_pending or sealed:
                raise ValueError("prediction receipt without successful execution")
            point = plan["points"][total // 2]
            if payload["point_id"] != point["id"] or type(payload["pass"]) is not int or payload["pass"] != total % 2 or payload["spec_sha256"] != evidence.digest(point["spec"]):
                raise ValueError("prediction table order mismatch")
            (predictions if total % 2 == 0 else repeated)[point["id"]] = payload["values"]
        elif kind == "domain_sealed":
            if sealed or admitted is None or predictor_finished != admitted["prediction_calls"]:
                raise ValueError("seal before complete predictions")
            registration = read_json(root / "registration.json")
            expected = evidence.seal(plan, snapshot, predictions, repeated, metadata["runtime_id"])
            if registration != expected or payload["seal_sha256"] != expected["seal_sha256"]:
                raise ValueError("complete family seal mismatch")
            candidate = root / "candidates" / (_sha(code.encode("utf-8")) + ".py")
            if _read_bytes(candidate).decode("utf-8") != code:
                raise ValueError("frozen candidate file mismatch")
            sealed = True
        elif kind == "domain_observation_planned":
            if not sealed or pending is not None:
                raise ValueError("observation before complete seal or duplicate plan")
            schedule = [(p, k) for p in plan["points"] for k in range(p["replicates"])]
            if len(records) >= len(schedule):
                raise ValueError("excess observation")
            point, replica = schedule[len(records)]
            pending = {k: v for k, v in payload.items() if k != "protocol"}
            if (pending["point_id"] != point["id"] or pending["replica"] != replica or
                    type(pending["replica"]) is not int or
                    pending["spec_sha256"] != evidence.digest(point["spec"])):
                raise ValueError("fixed acquisition order mismatch")
        elif kind == "observation_attempt_started":
            if pending is None or started is not None or payload["noise_key"] != pending["noise_key"] or evidence.digest(payload["spec"]) != pending["spec_sha256"]:
                raise ValueError("unplanned observation attempt")
            key = payload["noise_key"]
            _counter(payload["units_charged"], "observation units")
            if key in attempted_noise_keys or payload["units_charged"] != admitted["point_costs"][pending["point_id"]]:
                raise ValueError("reused measurement key or changed observation cost")
            attempted_noise_keys.add(key)
            units_charged += payload["units_charged"]
            observation_started += 1
            if type(payload["attempt"]) is not int or payload["attempt"] != observation_started:
                raise ValueError("observation attempt number mismatch")
            started = payload
            observation_started_wall = wall
        elif kind == "observation_returned":
            if (started is None or returned is not None or type(payload["attempt"]) is not int or
                    any(payload[k] != started[k] for k in ("attempt", "spec", "noise_key"))):
                raise ValueError("unmatched raw observation")
            returned = payload["observation"]
            point = next(p for p in plan["points"] if p["id"] == pending["point_id"])
            evidence.validate_observation(returned, point["spec"], metadata["public_contract"])
        elif kind == "observation_attempt_finished":
            if started is None or type(payload["attempt"]) is not int or payload["attempt"] != started["attempt"]:
                raise ValueError("observation finish mismatch")
            if payload["ok"] and returned is None:
                raise ValueError("successful observation without raw data")
            if type(payload["ok"]) is not bool:
                raise ValueError("invalid observation result boolean")
            elapsed = _seconds(payload["elapsed_seconds"], "observation elapsed duration")
            if elapsed > wall-observation_started_wall:
                raise ValueError("observation duration exceeds elapsed wall interval")
            observation_elapsed += elapsed
            execution_blocked = (not payload["ok"] or elapsed > limits["simulation_seconds_per_call"] or
                                 observation_elapsed > limits["simulation_seconds"] or wall > limits["wall_seconds"])
            observation_finished += int(payload["ok"])
            started = None
        elif kind == "domain_observation":
            record = payload["record"]
            if (pending is None or returned is None or started is not None or
                    record != dict(pending, observation=returned) or payload["record_sha256"] != evidence.digest(record) or
                    observation_finished != len(records)+1):
                raise ValueError("observation receipt mismatch")
            records.append(record)
            pending, returned = None, None
        elif kind == "domain_terminal":
            if payload["status"] not in ("completed", "failed", "incomplete") or payload["observations_sha256"] != evidence.digest(records):
                raise ValueError("invalid terminal event")
            result = None if registration is None else evidence.recompute(registration, records,
                expected_seal=registration["seal_sha256"], expected_observations_sha256=payload["observations_sha256"])
            if result != payload["evidence"]:
                raise ValueError("terminal numeric evidence mismatch")
            if payload["status"] == "completed" and (result is None or not result["complete_family"] or pending is not None):
                raise ValueError("incomplete family marked complete")
            usage = payload["usage"]
            evidence.keys(usage, ("actions", "experiment_attempts", "experiment_units", "predictor_attempts",
                                  "predictor_seconds_charged", "predictor_seconds_actual", "simulation_seconds_actual"), "terminal usage")
            for field in ("actions", "experiment_attempts", "experiment_units", "predictor_attempts"):
                _counter(usage[field], field)
            for field in ("predictor_seconds_charged", "predictor_seconds_actual", "simulation_seconds_actual"):
                _seconds(usage[field], field)
            if (payload["usage"]["predictor_attempts"] != predictor_started or
                    payload["usage"]["experiment_attempts"] != observation_started or
                    payload["usage"]["actions"] != int(run_started) or
                    payload["usage"]["experiment_units"] != units_charged or
                    payload["usage"]["predictor_seconds_charged"] != predictor_charged or
                    payload["usage"]["predictor_seconds_actual"] != predictor_elapsed or
                    payload["usage"]["simulation_seconds_actual"] != observation_elapsed):
                raise ValueError("terminal attempt accounting mismatch")
            if (usage["actions"] > limits["actions"] or observation_started > limits["experiments"] or
                    predictor_started > limits["predictor_calls"] or units_charged > limits["experiment_units"] or
                    predictor_charged > limits["predictor_seconds"]):
                raise ValueError("terminal usage exceeds fixed call/resource limits")
            if payload["status"] == "completed" and (execution_blocked or prediction_pending or started is not None or
                    predictor_elapsed > limits["predictor_seconds"] or observation_elapsed > limits["simulation_seconds"] or
                    wall > limits["wall_seconds"] or payload["reason"] is not None):
                raise ValueError("completed family exceeds elapsed/resource limits")
            terminal = payload
        else:
            raise ValueError("unsupported domain journal event")
    if previous != expected_head:
        raise ValueError("receipt head mismatch")
    result = None if registration is None else evidence.recompute(registration, records,
        expected_seal=registration["seal_sha256"], expected_observations_sha256=evidence.digest(records))
    report_missing = not (root / "report.json").exists()
    if terminal is not None and not report_missing:
        expected_report = {"protocol": evidence.PROTOCOL, "status": terminal["status"], "phase": "closed", "error": terminal["reason"],
                           "environment": metadata["environment"], "limits": metadata["limits"], "usage": terminal["usage"],
                           "public_plan": evidence.public_plan(plan), "evidence": result, "receipt_head": expected_head,
                           "boundary_identified": False, "mechanism_identified": False, "discovery_depth_certified": False}
        if read_json(root / "report.json") != expected_report:
            raise ValueError("public report differs from authenticated evidence")
    return {"protocol": evidence.PROTOCOL, "receipt_head": expected_head, "receipt_count": len(files),
            "status": terminal["status"] if terminal else "interrupted_prefix", "evidence": result,
            "report_missing": report_missing,
            "resource_verification": {"audit_schema": AUDIT_SCHEMA, "retained_artifact_bytes": retained_bytes,
                                      "wall_elapsed_at_last_receipt": previous_wall,
                                      "timing_basis": "trusted operator monotone receipt clock; final report I/O and historical transient byte peaks are not reconstructed"},
            "raw_returned_but_unclassified": returned is not None,
            "source_history_authentication": "requires trusted supplied source cutoff and complete history",
            "boundary_identified": False, "mechanism_identified": False, "discovery_depth_certified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--environment", choices=ENVIRONMENTS, required=True)
    run.add_argument("--seed", type=int, required=True)
    for name in ("plan", "snapshot", "source-history", "output"):
        run.add_argument("--" + name, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory")
    verify.add_argument("--expected-head", required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        result = verify_domain_directory(args.directory, expected_head=args.expected_head)
    else:
        request, snapshot, source = [read_json(p, MAX_INPUT_BYTES) for p in (args.plan, args.snapshot, args.source_history)]
        task = DomainMappingTask(args.environment, args.seed, args.output)
        result = task.run(request, snapshot, source, original_inputs={
            "plan": _read_bytes(args.plan, MAX_INPUT_BYTES), "snapshot": _read_bytes(args.snapshot, MAX_INPUT_BYTES),
            "source-history": _read_bytes(args.source_history, MAX_INPUT_BYTES)})
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
