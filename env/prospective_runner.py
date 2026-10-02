"""Execute prospective evidence tasks with real isolation and private receipts.

Run ``python -m env.prospective_runner --help``. This operator path never changes
the historical episode runner and never executes candidate code in-process.
"""

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time

import numpy as np
import scipy

from sle.episode_deadline import call_with_deadline
from sle.secure_eval import CandidateProxy, sanitized_candidate_failure
from .prospective import ProspectiveSession, _matrix, digest, recompute_result
from .registry import ENVIRONMENTS, load_world


RUNNER_PROTOCOL = "sle-prospective-runner-0.1"
PLAN_PROTOCOL = "sle-prospective-plan-0.1"
DEFAULT_LIMITS = {
    "actions": 32, "max_tests": 3, "experiments": 96, "experiment_units": 10000,
    "predictor_calls": 24, "predictor_seconds": 360.0,
    "predictor_seconds_per_call": 15.0, "predictor_memory_mb": 2048,
    "simulation_seconds": 300.0, "simulation_seconds_per_call": 30.0,
    "wall_seconds": 900.0, "family_alpha": 0.05,
}


class TaskBudgetExceeded(RuntimeError):
    pass


class CandidateExecutionFailed(RuntimeError):
    pass


def _limits(changes):
    if changes is not None and (not isinstance(changes, dict) or set(changes) - set(DEFAULT_LIMITS)):
        raise ValueError("unknown limit")
    values = dict(DEFAULT_LIMITS, **(changes or {}))
    for key, default in DEFAULT_LIMITS.items():
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("invalid limit " + key)
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite or value <= 0:
            raise ValueError("invalid limit " + key)
        if isinstance(default, int) and type(value) is not int:
            raise ValueError("limit must be an integer: " + key)
    if values["max_tests"] > 8 or values["family_alpha"] > 0.05:
        raise ValueError("test family exceeds prospective policy")
    if values["actions"] > 128 or values["experiments"] > 512 or values["predictor_calls"] > 128:
        raise ValueError("task limit exceeds bounded runner capacity")
    if values["predictor_memory_mb"] > 4096 or values["wall_seconds"] > 7200:
        raise ValueError("runtime limit exceeds bounded runner capacity")
    return values


def _sync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_bytes(path, content, *, replace=False, mode=0o600):
    """Publish a complete file atomically; new artifacts never overwrite."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            if path.is_symlink():
                raise ValueError("refusing symlink artifact")
            os.replace(temporary, str(path))
        else:
            os.link(temporary, str(path))  # Atomic no-clobber publication.
            os.unlink(temporary)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path, value, *, replace=False):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    _atomic_bytes(path, encoded, replace=replace)


class PrivateJournal:
    """One writer, no resume: immutable entries plus an atomic head pointer."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(mode=0o700)
        self.sequence, self.head = 0, None

    def append(self, kind, payload):
        entry = {"protocol": RUNNER_PROTOCOL, "sequence": self.sequence + 1,
                 "previous_sha256": self.head, "kind": kind, "payload": deepcopy(payload)}
        entry["sha256"] = digest(entry)
        _atomic_json(self.root / ("%06d.json" % entry["sequence"]), entry)
        _atomic_json(self.root / "head.json", {"sequence": entry["sequence"], "sha256": entry["sha256"]}, replace=True)
        self.sequence, self.head = entry["sequence"], entry["sha256"]
        return "%06d:%s" % (self.sequence, self.head)


def _runtime_binding(world):
    import sle.secure_eval as secure
    files = [Path(__file__), Path(__file__).with_name("prospective.py")]
    files += [Path(secure.__file__).with_name(name) for name in
              ("secure_eval.py", "candidate_worker.py", "rpc_codec.py", "contract_lint.py")]
    directory = Path(__file__).parent / world.name
    if directory.is_dir():
        files += sorted(directory.rglob("*.py"))
    return {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
            "world_version": world.version,
            "source_files": {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}}


def _observation_contract(world):
    additive = {"coupled_oscillators", "reaction_kinetics", "heat_transport", "gene_regulation",
                "ising_spin", "hysteresis_material", "prospective_fixture"}
    clipped = {"microecology", "microecology_causal"}
    if world.name not in additive | clipped:
        raise ValueError("public noise bias model has not been approved for this environment")
    # For nonnegative latent x, E[max(x + N(0, sigma^2), 0)] - x is
    # nonnegative and at most sigma/sqrt(2*pi), attained when x = 0.
    bias = [value / math.sqrt(2.0 * math.pi) if world.name in clipped else 0.0 for value in world.noise_std]
    return {"environment": world.name, "world_version": world.version, "axis_field": world.axis_field,
            "channels": list(world.channels), "scales": list(world.scales),
            "noise_std": list(world.noise_std), "noise_mean_bias_bound": bias}


class ProspectiveTask:
    """Trusted operator API. Only public specs enter candidate RPC calls."""

    def __init__(self, environment, seed, directory, *, limits=None):
        self._limits = _limits(limits)
        if environment not in ENVIRONMENTS + ("prospective_fixture",):
            raise ValueError("unknown environment")
        if type(seed) is not int or not 0 <= seed < 2 ** 63:
            raise ValueError("invalid operator seed")
        self.directory = Path(directory).absolute()
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        self.directory.mkdir(mode=0o700)  # Existing directories and symlinks fail closed.
        self._journal = PrivateJournal(self.directory / "receipts")
        self._candidates = self.directory / "candidates"
        self._candidates.mkdir(mode=0o700)
        self._started = time.monotonic()
        self._state, self._error = "active", None
        self._records, self._results = [], []
        self._source_counter = 0
        self._namespace = secrets.token_hex(16)
        self._noise_keys = set()
        self._session = None
        self._usage = {"actions": 0, "experiment_attempts": 0, "experiment_units": 0,
                       "predictor_attempts": 0, "predictor_seconds_charged": 0.0,
                       "predictor_seconds_actual": 0.0, "simulation_seconds_actual": 0.0}
        try:
            self._world = _FixtureWorld(seed) if environment == "prospective_fixture" else load_world(environment, seed)[0]
            self._contract = _observation_contract(self._world)
            binding = _runtime_binding(self._world)
            self._runtime_id = digest(binding)
            metadata = {"protocol": RUNNER_PROTOCOL, "environment": environment, "private_world_seed": seed,
                        "world_version": self._world.version, "limits": self._limits,
                        "runtime_binding": binding, "runtime_id": self._runtime_id}
            _atomic_json(self.directory / "operator-private.json", metadata)
            self._journal.append("task_created", {"operator_metadata_sha256": digest(metadata),
                                                  "public_contract": self._contract, "limits": self._limits})
            self._session = ProspectiveSession(self._contract, validate_spec=self._world.validate,
                                                predict=self._predict, observe=self._observe,
                                                persist=self._persist_event, runtime_id=self._runtime_id,
                                                max_tests=self._limits["max_tests"], family_alpha=self._limits["family_alpha"])
            self._checkpoint()
        except Exception as error:
            self._fail(error)
            raise

    @property
    def limits(self):
        return deepcopy(self._limits)

    def describe(self):
        return {"problem": deepcopy(self._world.describe()), "protocol": RUNNER_PROTOCOL,
                "observation_contract": deepcopy(self._contract),
                "limits": deepcopy(self._limits), "runtime_id": self._runtime_id,
                "mechanism_identified": False, "discovery_depth_certified": False}

    def _remaining_wall(self):
        return self._limits["wall_seconds"] - (time.monotonic() - self._started)

    def _require_active(self):
        if self._state != "active":
            raise RuntimeError("task is closed; failures cannot be resumed or rerun")

    def _guard(self):
        self._require_active()
        if self._remaining_wall() <= 0:
            raise TaskBudgetExceeded("wall budget exhausted")

    def _action(self, kind, payload):
        self._guard()
        if self._usage["actions"] >= self._limits["actions"]:
            raise TaskBudgetExceeded("action budget exhausted")
        self._usage["actions"] += 1
        self._journal.append("action_started", {"kind": kind, "request": deepcopy(payload), "usage": deepcopy(self._usage)})

    def _persist_event(self, event):
        receipt = self._journal.append("prospective_event", event)
        self._checkpoint()
        return receipt

    def _predict(self, code, spec):
        self._guard()
        allowance = self._limits["predictor_seconds_per_call"]
        if (self._usage["predictor_attempts"] >= self._limits["predictor_calls"]
                or max(self._usage["predictor_seconds_charged"], self._usage["predictor_seconds_actual"]) + allowance > self._limits["predictor_seconds"]
                or self._remaining_wall() < allowance):
            raise TaskBudgetExceeded("isolated prediction budget exhausted")
        self._usage["predictor_attempts"] += 1
        self._usage["predictor_seconds_charged"] += allowance
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        path = self._candidates / (code_hash + ".py")
        self._journal.append("prediction_attempt_started", {"attempt": self._usage["predictor_attempts"],
                                                             "code_sha256": code_hash, "spec_sha256": digest(spec),
                                                             "seconds_charged": allowance})
        start, proxy, succeeded = time.monotonic(), None, False
        try:
            if path.exists():
                if path.read_bytes() != code.encode("utf-8") or path.is_symlink():
                    raise RuntimeError("frozen candidate artifact changed")
            else:
                # Only this nonsecret leaf is mounted. The parent/private files
                # remain 0700/0600, while the sandbox UID can read the leaf.
                _atomic_bytes(path, code.encode("utf-8"), mode=0o444)
            proxy = CandidateProxy(path, "predict", timeout_s=allowance,
                                   memory_mb=self._limits["predictor_memory_mb"], packages=())
            values = _matrix(proxy(deepcopy(spec)), spec, self._contract)
            succeeded = True
            return values
        except Exception as error:
            category = sanitized_candidate_failure(error)["candidate_failure_kind"]
            raise CandidateExecutionFailed(category) from None
        finally:
            if proxy is not None:
                proxy.close(kill=True)
            elapsed = time.monotonic() - start
            self._usage["predictor_seconds_actual"] += elapsed
            self._journal.append("prediction_attempt_finished", {"attempt": self._usage["predictor_attempts"],
                                                                  "ok": succeeded, "elapsed_seconds": elapsed})
            self._checkpoint()
            if self._usage["predictor_seconds_actual"] > self._limits["predictor_seconds"] or self._remaining_wall() <= 0:
                raise TaskBudgetExceeded("actual isolated prediction time budget exhausted")

    def _observe(self, spec, *, noise_key):
        self._guard()
        if not isinstance(noise_key, str) or not noise_key:
            raise ValueError("operator-generated measurement key is required")
        if noise_key in self._noise_keys:
            raise ValueError("measurement keys cannot be reused")
        canonical = self._world.validate(deepcopy(spec))
        cost = self._world.cost(canonical)
        if type(cost) is not int or cost <= 0:
            raise ValueError("invalid public experiment cost")
        if self._usage["experiment_attempts"] >= self._limits["experiments"] or self._usage["experiment_units"] + cost > self._limits["experiment_units"]:
            raise TaskBudgetExceeded("experiment budget exhausted")
        seconds = min(self._limits["simulation_seconds_per_call"], self._remaining_wall(),
                      self._limits["simulation_seconds"] - self._usage["simulation_seconds_actual"])
        if seconds <= 0:
            raise TaskBudgetExceeded("simulation time budget exhausted")
        self._usage["experiment_attempts"] += 1
        self._usage["experiment_units"] += cost
        self._noise_keys.add(noise_key)
        attempt = self._usage["experiment_attempts"]
        self._journal.append("observation_attempt_started", {"attempt": attempt, "spec": canonical,
                                                              "noise_key": noise_key, "units_charged": cost})
        start, succeeded = time.monotonic(), False
        try:
            response = call_with_deadline(lambda: self._world.run(canonical, noise_key=noise_key), seconds)
            if response["axis"] != canonical[self._contract["axis_field"]] or response["channels"] != self._contract["channels"]:
                raise ValueError("operator observation contract mismatch")
            response = {"axis": deepcopy(response["axis"]), "channels": list(response["channels"]),
                        "values": _matrix(response["values"], canonical, self._contract)}
            self._journal.append("observation_returned", {"attempt": attempt, "spec": canonical,
                                                         "noise_key": noise_key, "observation": response})
            succeeded = True
            return response
        finally:
            elapsed = time.monotonic() - start
            self._usage["simulation_seconds_actual"] += elapsed
            self._journal.append("observation_attempt_finished", {"attempt": attempt, "ok": succeeded,
                                                                  "elapsed_seconds": elapsed})
            self._checkpoint()
            if self._usage["simulation_seconds_actual"] > self._limits["simulation_seconds"] or self._remaining_wall() <= 0:
                raise TaskBudgetExceeded("actual simulation time budget exhausted")

    def observe_source(self, spec):
        """Budgeted source evidence; accepts a spec, never user-provided data."""
        self._require_active()
        try:
            self._action("source_experiment", spec)
            canonical = self._world.validate(deepcopy(spec))
            self._source_counter += 1
            rid = "obs-source-%04d" % self._source_counter
            response = self._observe(canonical, noise_key=self._namespace + ":" + rid)
            record = {"id": rid, "spec": canonical, "observation": response}
            self._records.append(record)
            self._journal.append("source_evidence", record)
            self._checkpoint()
            return deepcopy(record)
        except Exception as error:
            self._fail(error)
            raise

    def _admit(self, request):
        if not isinstance(request, dict) or not isinstance(request.get("experiments"), list):
            raise ValueError("invalid preregistration plan")
        experiments, repeats = request["experiments"], request.get("replicates")
        if not 1 <= len(experiments) <= 2 or type(repeats) is not int or not 4 <= repeats <= 16:
            raise ValueError("invalid preregistration replication plan")
        units = sum(self._world.cost(self._world.validate(deepcopy(item["spec"]))) for item in experiments) * repeats
        count, calls = len(experiments) * repeats, len(experiments) * 4
        seconds = calls * self._limits["predictor_seconds_per_call"]
        if (self._usage["experiment_attempts"] + count > self._limits["experiments"]
                or self._usage["experiment_units"] + units > self._limits["experiment_units"]
                or self._usage["predictor_attempts"] + calls > self._limits["predictor_calls"]
                or max(self._usage["predictor_seconds_charged"], self._usage["predictor_seconds_actual"]) + seconds > self._limits["predictor_seconds"]
                or seconds > self._remaining_wall()):
            raise TaskBudgetExceeded("entire prospective plan does not fit remaining budget")
        self._journal.append("plan_admitted", {"maximum_prediction_calls": calls,
                                               "prediction_seconds": seconds, "observation_calls": count,
                                               "observation_units": units})

    def preregister(self, request):
        """Seal and immediately collect the fixed plan, without a second action."""
        self._require_active()
        try:
            self._action("preregister", request)
            self._admit(request)
            registration = self._session.register(deepcopy(request), records=deepcopy(self._records))
            result = self._session.collect(registration["test_id"])
            self._sync_records()
            response = {"test_id": registration["test_id"], "seal_sha256": registration["seal_sha256"],
                        "result": result, "observation_ids": [record["id"] for record in self._session.snapshot()["tests"][-1]["observations"]]}
            self._results.append(response)
            self._checkpoint()
            return deepcopy(response)
        except Exception as error:
            self._sync_records()
            self._fail(error)
            raise

    def _sync_records(self):
        if self._session is None:
            return
        known = {record["id"] for record in self._records}
        for test in self._session.snapshot()["tests"]:
            experiments = {item["id"]: item["spec"] for item in test.get("registration", {}).get("experiments", [])}
            for item in test["observations"]:
                if item["id"] not in known:
                    self._records.append({"id": item["id"], "spec": experiments[item["experiment_id"]],
                                          "observation": item["observation"]})
                    known.add(item["id"])

    def public_records(self):
        """Return observed source/fresh data only, without private keys or state."""
        return deepcopy(self._records)

    def public_report(self):
        return {"protocol": RUNNER_PROTOCOL, "status": self._state, "error": self._error,
                "environment": getattr(getattr(self, "_world", None), "name", None),
                "usage": deepcopy(self._usage), "limits": deepcopy(self._limits),
                "results": deepcopy(self._results), "receipt_head": self._journal.head,
                "mechanism_identified": False, "discovery_depth_certified": False}

    def _checkpoint(self):
        _atomic_json(self.directory / "bundle-private.json",
                     {"protocol": RUNNER_PROTOCOL, "status": self._state, "usage": self._usage,
                      "records": self._records, "prospective": self._session.snapshot() if self._session else None}, replace=True)
        _atomic_json(self.directory / "report.json", self.public_report(), replace=True)

    def _fail(self, error):
        if self._state == "failed":
            return
        self._state = "failed"
        self._error = ("budget_exhausted" if isinstance(error, TaskBudgetExceeded) else
                       str(error) if isinstance(error, CandidateExecutionFailed) else type(error).__name__)
        try:
            self._journal.append("task_failed", {"error": self._error, "usage": self._usage})
            self._checkpoint()
        except Exception:
            self._error = "artifact_persistence_failed"

    def finish(self):
        self._require_active()
        try:
            self._guard()
            if not self._results:
                raise ValueError("a task needs at least one completed prospective test")
            self._state = "completed"
            self._journal.append("task_completed", {"tests": len(self._results), "usage": self._usage})
            self._checkpoint()
            return self.public_report()
        except Exception as error:
            self._fail(error)
            raise

    def close(self, reason="driver_stopped"):
        """End an unfinished task without discarding evidence or allowing resume."""
        reasons = {"driver_stopped", "model_budget", "model_transport_error",
                   "analysis_unavailable", "invalid_action", "final_missing"}
        if reason not in reasons:
            raise ValueError("unknown task close reason")
        if self._state != "active":
            return self.public_report()
        self._state, self._error = "incomplete", reason
        self._journal.append("task_closed", {"reason": reason, "usage": self._usage})
        self._checkpoint()
        return self.public_report()


def verify_directory(directory):
    """Verify private receipts and replay numerical verdicts without new runs."""
    root = Path(directory)
    head = json.loads((root / "receipts" / "head.json").read_text())
    entries = sorted((root / "receipts").glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"))
    previous, registrations, observations, verdicts = None, {}, {}, []
    native_previous, native_sequence, collecting, returned = None, 0, {}, {}
    native_session = None
    if len(entries) != head["sequence"]:
        raise ValueError("receipt head or entry count mismatch; no implicit recovery")
    for index, path in enumerate(entries, 1):
        if path.is_symlink() or path.name != "%06d.json" % index:
            raise ValueError("receipt sequence mismatch")
        entry = json.loads(path.read_text())
        if (entry["protocol"] != RUNNER_PROTOCOL or entry["sequence"] != index or entry["previous_sha256"] != previous
                or digest({k: v for k, v in entry.items() if k != "sha256"}) != entry["sha256"]):
            raise ValueError("receipt hash mismatch")
        previous = entry["sha256"]
        if entry["kind"] == "observation_returned":
            key = entry["payload"]["noise_key"]
            if key in returned:
                raise ValueError("reused observation key")
            returned[key] = (index, entry["payload"]["observation"])
        if entry["kind"] == "input_plan":
            if digest(json.loads((root / "input-plan.json").read_text())) != entry["payload"]["sha256"]:
                raise ValueError("input plan mismatch")
        if (index == 1) != (entry["kind"] == "task_created"):
            raise ValueError("task creation order mismatch")
        if entry["kind"] == "task_created":
            if digest(json.loads((root / "operator-private.json").read_text())) != entry["payload"]["operator_metadata_sha256"]:
                raise ValueError("operator metadata mismatch")
        if entry["kind"] != "prospective_event":
            continue
        event = entry["payload"]
        if (digest({k: v for k, v in event.items() if k != "event_sha256"}) != event["event_sha256"]
                or event["sequence"] != native_sequence + 1 or event["previous_event_sha256"] != native_previous):
            raise ValueError("prospective event hash mismatch")
        if native_session is not None and event["session_id"] != native_session:
            raise ValueError("prospective session changed")
        native_session = event["session_id"]
        native_previous, native_sequence = event["event_sha256"], event["sequence"]
        payload = event["payload"]
        if event["kind"] == "registered":
            if payload["test_id"] in registrations:
                raise ValueError("duplicate registration")
            if digest({k: v for k, v in payload.items() if k != "seal_sha256"}) != payload["seal_sha256"]:
                raise ValueError("registration seal mismatch")
            registrations[payload["test_id"]] = payload
            observations[payload["test_id"]] = []
            for rival in payload["rivals"]:
                candidate = root / "candidates" / (rival["code_sha256"] + ".py")
                if candidate.is_symlink() or candidate.read_text() != rival["predictor_code"]:
                    raise ValueError("frozen candidate source mismatch")
        elif event["kind"] == "collection_started":
            if payload["test_id"] not in registrations or payload["test_id"] in collecting or payload["seal_sha256"] != registrations[payload["test_id"]]["seal_sha256"]:
                raise ValueError("collection order mismatch")
            collecting[payload["test_id"]] = index
        elif event["kind"] == "fresh_observation":
            raw = returned.get(payload["record"]["noise_key"])
            if (payload["test_id"] not in collecting or digest(payload["record"]) != payload["record_sha256"]
                    or raw is None or raw[0] <= collecting[payload["test_id"]]
                    or raw[1] != payload["record"]["observation"]):
                raise ValueError("observation before registration or corrupted record")
            observations[payload["test_id"]].append(payload["record"])
        elif event["kind"] == "completed":
            test_id = payload["test_id"]
            if test_id not in collecting:
                raise ValueError("completion before collection")
            result = recompute_result(registrations[test_id], observations[test_id],
                                      expected_seal=payload["seal_sha256"],
                                      expected_observations_sha256=payload["observations_sha256"])
            if result != payload["result"]:
                raise ValueError("numerical verdict mismatch")
            verdicts.append(result)
            del collecting[test_id]
    if previous != head["sha256"]:
        raise ValueError("receipt head hash mismatch")
    return {"protocol": RUNNER_PROTOCOL, "receipt_count": len(entries), "receipt_head": previous,
            "replayed_tests": len(verdicts), "results": verdicts,
            "mechanism_identified": False, "discovery_depth_certified": False}


def _resolve_previous(request, previous):
    request = deepcopy(request)
    if request.get("revision_of") == "$previous_test":
        if previous is None:
            raise ValueError("no previous test for refinement")
        request["revision_of"] = previous["test_id"]
    for rival in request.get("rivals", []):
        resolved = []
        for rid in rival.get("evidence_ids", []):
            if isinstance(rid, str) and rid.startswith("$previous_fresh:"):
                if previous is None:
                    raise ValueError("no previous observations for refinement")
                try:
                    index = int(rid.split(":", 1)[1])
                    if index < 0:
                        raise ValueError("negative evidence index")
                    rid = previous["observation_ids"][index]
                except (ValueError, IndexError):
                    raise ValueError("invalid previous observation reference") from None
            resolved.append(rid)
        rival["evidence_ids"] = resolved
    return request


def run_plan(environment, seed, directory, plan, *, limits=None):
    if not isinstance(plan, dict) or set(plan) != {"protocol", "source_experiments", "tests"} or plan["protocol"] != PLAN_PROTOCOL:
        raise ValueError("invalid prospective plan protocol")
    if not isinstance(plan["source_experiments"], list) or not 1 <= len(plan["source_experiments"]) <= 32 or not isinstance(plan["tests"], list) or not 1 <= len(plan["tests"]) <= 8:
        raise ValueError("invalid prospective plan size")
    task = ProspectiveTask(environment, seed, directory, limits=limits)
    try:
        _atomic_json(task.directory / "input-plan.json", plan)
        task._journal.append("input_plan", {"sha256": digest(plan)})
        for spec in plan["source_experiments"]:
            task.observe_source(spec)
        previous = None
        for request in plan["tests"]:
            previous = task.preregister(_resolve_previous(request, previous))
        return task.finish()
    except Exception as error:
        if task._state != "failed":
            task._fail(error)
        return task.public_report()


class _FixtureWorld:
    """Protocol demonstration only; not a registered scientific benchmark."""
    name, version, axis_field = "prospective_fixture", "prospective-fixture-1", "times"
    channels, scales, noise_std = ("response",), (1.0,), (0.001,)

    def __init__(self, seed):
        self._seed = seed
        self._slope = 2.8 + (seed % 11) * 0.04

    def describe(self):
        return {"name": self.name, "version": self.version, "channels": list(self.channels),
                "schema": {"drive": "0..3", "times": "increasing list beginning at zero, at most 8 values in 0..4"},
                "scales": list(self.scales), "noise_std": list(self.noise_std),
                "role": "synthetic protocol demonstration, not discovery-depth evidence"}

    def validate(self, spec):
        if not isinstance(spec, dict) or set(spec) != {"drive", "times"}:
            raise ValueError("invalid fixture spec")
        drive, times = spec["drive"], spec["times"]
        if isinstance(drive, bool) or not isinstance(drive, (int, float)) or not 0 <= drive <= 3:
            raise ValueError("invalid fixture drive")
        if not isinstance(times, list) or not 2 <= len(times) <= 8 or times[0] != 0 or any(isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 <= t <= 4 for t in times) or any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("invalid fixture times")
        return {"drive": float(drive), "times": [float(t) for t in times]}

    def cost(self, spec):
        self.validate(spec)
        return 1

    def run(self, spec, *, noise_key=None):
        if not isinstance(noise_key, str) or not noise_key:
            raise ValueError("fixture requires an explicit measurement key")
        spec = self.validate(spec)
        key = hashlib.sha256((str(self._seed) + noise_key).encode()).digest()
        rng = np.random.default_rng(int.from_bytes(key[:16], "big"))
        values = self._slope * spec["drive"] * np.asarray(spec["times"])
        values += rng.normal(0, self.noise_std[0], len(values))
        return {"axis": spec["times"], "channels": list(self.channels), "values": values[:, None].tolist()}


def _fixture_request(coefficients, drive):
    return {"profile": "mechanism_discrimination", "scope": "One-hour response under the specified drive; protocol fixture only.",
            "rivals": [{"id": "rival-%d" % index,
                        "predictor_code": 'COEFFICIENT = %.17g\ndef predict(spec):\n    return [[COEFFICIENT * spec["drive"] * t] for t in spec["times"]]\n' % coefficient,
                        "rationale": "A source-compatible linear coefficient, to be tested prospectively.",
                        "evidence_ids": ["obs-source-0001"], "tolerance": 0.03}
                       for index, coefficient in enumerate(coefficients)],
            "experiments": [{"id": "target", "role": "target", "spec": {"drive": drive, "times": [0, 1, 2]}}],
            "readout": [{"experiment_id": "target", "row": 1, "channel": "response", "weight": 1.0}],
            "replicates": 8, "revision_of": None, "change_note": ""}


def run_demo(directory, *, seed=7, limits=None):
    """Actual sandbox demo; revision is fitted only from the public counterexample."""
    task = ProspectiveTask("prospective_fixture", seed, directory, limits=limits)
    try:
        task.observe_source({"drive": 0, "times": [0, 1, 2]})
        first = task.preregister(_fixture_request((1.0, 2.0), 1.0))
        # The one-hour, unit-drive readout is the coefficient estimate. Never
        # inspect _world._slope or use a clean target to construct the revision.
        estimate = first["result"]["mean_readout"]
        revised = _fixture_request((1.0, estimate), 2.0)
        revised["revision_of"] = first["test_id"]
        revised["change_note"] = "Fit the coefficient from the observed counterexample, retain the refuted old law, and predict a different drive."
        revised["rivals"][1]["evidence_ids"].append(first["observation_ids"][0])
        task.preregister(revised)
        return task.finish()
    except Exception as error:
        if task._state != "failed":
            task._fail(error)
        return task.public_report()


def _read_json(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("input JSON exceeds two MiB")
    return json.loads(path.read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "demo"):
        command_parser = commands.add_parser(command)
        command_parser.add_argument("--directory", required=True, help="new private output directory; existing paths are rejected")
        command_parser.add_argument("--seed", type=int, default=7, help="operator-only instance seed")
        command_parser.add_argument("--limits", help="operator JSON overrides for bounded resource limits")
        if command == "run":
            command_parser.add_argument("--environment", required=True, choices=ENVIRONMENTS + ("prospective_fixture",))
            command_parser.add_argument("--plan", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_directory(args.directory)
        else:
            limits = _read_json(args.limits) if args.limits else None
            result = (run_demo(args.directory, seed=args.seed, limits=limits) if args.command == "demo" else
                      run_plan(args.environment, args.seed, args.directory, _read_json(args.plan), limits=limits))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1 if result.get("status") == "failed" else 0
    except Exception as error:
        # No operator paths, private state or arbitrary candidate exception text.
        print(json.dumps({"status": "failed", "error": type(error).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
