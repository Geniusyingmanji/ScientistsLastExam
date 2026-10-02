"""Operator-owned prospective comparisons, independent of pilot scoring.

Candidate code is never executed here. ``predict`` must execute each call in an
already isolated, fresh process. ``observe`` and ``persist`` are trusted operator
callbacks, never supplied by a candidate. Hashes bind artifacts, not chronology;
durable trusted receipts and the operator's complete observation history matter.
"""

import ast
from copy import deepcopy
import hashlib
import json
import math
import secrets

import numpy as np


PROTOCOL = "sle-prospective-evidence-0.1"
MAX_TOLERANCE_PER_SCALE = 0.2
DISCRIMINATION_TOLERANCE_PER_SCALE = 0.05


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _text(value, label, maximum=4000):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ValueError("invalid " + label)
    return value


def _number(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid " + label)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError("invalid " + label) from None
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError("invalid " + label)
    return result


def _integer(value, label, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("invalid " + label)
    return value


def _keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("invalid " + label + " fields")


def _public_contract(public):
    fields = ("environment", "world_version", "axis_field", "channels", "scales",
              "noise_std", "noise_mean_bias_bound")
    _keys(public, fields, "public contract")
    result = {key: _text(public[key], key, 100) for key in fields[:3]}
    channels = public["channels"]
    if not isinstance(channels, list) or not 1 <= len(channels) <= 32:
        raise ValueError("invalid channels")
    channels = [_text(c, "channel", 100) for c in channels]
    if len(set(channels)) != len(channels):
        raise ValueError("duplicate channels")
    result["channels"] = channels
    for key in fields[4:]:
        values = public[key]
        if not isinstance(values, list) or len(values) != len(channels):
            raise ValueError("invalid " + key)
        result[key] = [_number(x, key, 1e-12 if key == "scales" else 0.0, 1e12) for x in values]
    return result


def _axis(spec, public):
    times = spec.get(public["axis_field"])
    if not isinstance(times, list) or not 1 <= len(times) <= 256:
        raise ValueError("invalid public observation axis")
    for value in times:
        _number(value, "axis value", -1e12, 1e12)
    return times


def _matrix(values, spec, public):
    rows, columns = len(_axis(spec, public)), len(public["channels"])
    if not isinstance(values, (list, np.ndarray)) or len(values) != rows:
        raise ValueError("invalid prediction or observation shape")
    if isinstance(values, np.ndarray):
        if values.shape != (rows, columns):
            raise ValueError("invalid prediction or observation shape")
    elif any(not isinstance(row, (list, np.ndarray)) or len(row) != columns for row in values):
        raise ValueError("invalid prediction or observation shape")
    if any(isinstance(value, (bool, np.bool_)) for row in values for value in row):
        raise ValueError("boolean values are not numeric predictions")
    try:
        raw = np.asarray(values)
        if raw.dtype.kind not in "iuf" or raw.shape != (rows, columns):
            raise ValueError("invalid numeric values")
        array = raw.astype(float)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("invalid numeric values") from None
    if not np.all(np.isfinite(array)) or np.any(np.abs(array) > 1e12):
        raise ValueError("nonfinite or unbounded numeric values")
    return array.tolist()


def _controls(spec, public):
    return {key: value for key, value in spec.items() if key != public["axis_field"]}


def _code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _quantity(predictions, registration):
    public = registration["public"]
    total = 0.0
    for term in registration["readout"]:
        channel = public["channels"].index(term["channel"])
        total += term["weight"] * predictions[term["experiment_id"]][term["row"]][channel] / public["scales"][channel]
    return float(total)


def _design(registration):
    public = registration["public"]
    sd_by_experiment, bias, weight_mass = {}, 0.0, 0.0
    for term in registration["readout"]:
        channel = public["channels"].index(term["channel"])
        normalized_weight = abs(term["weight"]) / public["scales"][channel]
        eid = term["experiment_id"]
        sd_by_experiment[eid] = sd_by_experiment.get(eid, 0.0) + normalized_weight * public["noise_std"][channel]
        bias += normalized_weight * public["noise_mean_bias_bound"][channel]
        weight_mass += abs(term["weight"])
    # Arbitrary within-experiment correlation is allowed. Distinct experiments
    # and replicate batches must have independent measurement noise.
    variance = sum(value ** 2 for value in sd_by_experiment.values())
    radius = bias + math.sqrt(variance / (registration["replicates"] * registration["alpha"]))
    rivals = registration["rivals"]
    predictions = [_quantity(rival["predictions"], registration) for rival in rivals]
    targets = {item["id"] for item in registration["experiments"] if item["role"] == "target"}
    target_registration = dict(registration, readout=[t for t in registration["readout"] if t["experiment_id"] in targets])
    target_predictions = [_quantity(rival["predictions"], target_registration) for rival in rivals]
    tolerances = [rival["tolerance"] for rival in rivals]
    gap = abs(predictions[1] - predictions[0]) - sum(tolerances)
    target_gap = abs(target_predictions[1] - target_predictions[0]) - sum(tolerances)
    return {"predicted_readouts": predictions, "variance_bound_per_replicate": variance,
            "mean_bias_bound": bias, "confidence_radius": radius,
            "separation_margin": gap - 2.0 * radius,
            "target_separation_margin": target_gap - 2.0 * radius,
            "planned_separation": bool(gap > 2.0 * radius and target_gap > 2.0 * radius),
            "hard_tolerance_max": MAX_TOLERANCE_PER_SCALE * weight_mass,
            "discrimination_tolerance_max": DISCRIMINATION_TOLERANCE_PER_SCALE * weight_mass,
            "wide_tolerance": [bool(t > DISCRIMINATION_TOLERANCE_PER_SCALE * weight_mass) for t in tolerances]}


def _check_seal(registration, expected_seal):
    if not isinstance(expected_seal, str) or len(expected_seal) != 64:
        raise ValueError("trusted expected seal is required")
    payload = {key: value for key, value in registration.items() if key != "seal_sha256"}
    if registration.get("protocol") != PROTOCOL or registration.get("seal_sha256") != expected_seal or digest(payload) != expected_seal:
        raise ValueError("registration seal mismatch")
    for rival in registration["rivals"]:
        if _code_hash(rival["predictor_code"]) != rival["code_sha256"] or digest(rival["predictions"]) != rival["predictions_sha256"]:
            raise ValueError("frozen predictor artifact mismatch")


def recompute_result(registration, observations, *, expected_seal, expected_observations_sha256):
    """Replay numeric evidence using hash anchors obtained from a trusted log.

    Reading the expected hashes from the same untrusted artifact authenticates
    nothing. This function does not authenticate timestamps, IDs or noise keys.
    """
    _check_seal(registration, expected_seal)
    if digest(observations) != expected_observations_sha256:
        raise ValueError("observation artifact mismatch")
    public = registration["public"]
    experiments = registration["experiments"]
    if not isinstance(observations, list) or len(observations) != registration["replicates"] * len(experiments):
        raise ValueError("incomplete fresh observations")
    batches, observation_ids, keys = {}, set(), set()
    for record in observations:
        eid, replica = record["experiment_id"], record["replica"]
        spec = next((item["spec"] for item in experiments if item["id"] == eid), None)
        if spec is None or type(replica) is not int or not 0 <= replica < registration["replicates"]:
            raise ValueError("invalid fresh observation index")
        if record["id"] in observation_ids or record["noise_key"] in keys or eid in batches.setdefault(replica, {}):
            raise ValueError("duplicate fresh observation")
        observation_ids.add(record["id"])
        keys.add(record["noise_key"])
        observation = record["observation"]
        if observation["axis"] != _axis(spec, public) or observation["channels"] != public["channels"]:
            raise ValueError("fresh observation contract mismatch")
        batches[replica][eid] = _matrix(observation["values"], spec, public)
    quantities = [_quantity(batches[index], registration) for index in range(registration["replicates"])]
    mean = float(np.mean(quantities))
    design = _design(registration)
    radius = design["confidence_radius"]
    interval = [mean - radius, mean + radius]
    evaluations = []
    for rival, predicted in zip(registration["rivals"], design["predicted_readouts"]):
        lower, upper = predicted - rival["tolerance"], predicted + rival["tolerance"]
        rejected = interval[1] < lower or interval[0] > upper
        adequate = lower <= interval[0] and interval[1] <= upper
        evaluations.append({"id": rival["id"], "predicted_readout": predicted,
                            "tolerance_band": [lower, upper], "refuted_on_readout": bool(rejected),
                            "within_tolerance_on_readout": bool(adequate),
                            "not_refuted_is_not_adequacy": True})
    supported = [item["id"] for item in evaluations if item["within_tolerance_on_readout"]]
    rejected = [item["id"] for item in evaluations if item["refuted_on_readout"]]
    discriminated = (design["planned_separation"] and not any(design["wide_tolerance"])
                     and len(supported) == 1 and len(rejected) == 1)
    outcome = ("scoped_predictive_discrimination" if discriminated else
               "both_candidates_refuted" if len(rejected) == 2 else "inconclusive")
    return {"protocol": PROTOCOL, "test_id": registration["test_id"], "scope": registration["scope"],
            "design": design, "mean_readout": mean, "confidence_interval": interval,
            "alpha": registration["alpha"], "replicate_readouts": quantities,
            "candidates": evaluations, "outcome": outcome,
            "predictive_discrimination_supported": bool(discriminated),
            "supported_candidate": supported[0] if discriminated else None,
            "counterexample_candidate_ids": rejected,
            "mechanism_identified": False, "discovery_depth_certified": False,
            "scientific_review_required": ["rival_plausibility", "mechanistic_distinctness",
                                           "readout_not_fixed_by_public_controls", "scientific_scope"],
            "chronology_authentication": "requires_matching_trusted_operator_log"}


def replay_predictors(registration, predict, *, expected_seal):
    """Re-execute frozen code only through the supplied isolated callback."""
    _check_seal(registration, expected_seal)
    checks = []
    for rival in registration["rivals"]:
        values = {item["id"]: _matrix(predict(rival["predictor_code"], deepcopy(item["spec"])),
                                     item["spec"], registration["public"])
                  for item in registration["experiments"]}
        checks.append({"id": rival["id"], "matches_frozen_outputs": digest(values) == rival["predictions_sha256"]})
    return checks


class ProspectiveSession:
    """One bounded, operator-owned family of tests and subsequent refinements.

    persist(event) must durably append the event before returning a nonempty
    receipt string. predict(code, spec) is an isolated executor. observe(spec,
    noise_key=...) returns a public noisy response. None is candidate-controlled.
    """

    def __init__(self, public, *, validate_spec, predict, observe, persist, runtime_id,
                 max_tests=3, family_alpha=0.05):
        self._public = _public_contract(public)
        self._max_tests = _integer(max_tests, "max_tests", 1, 8)
        self._family_alpha = _number(family_alpha, "family_alpha", 0.000001, 0.05)
        self._runtime_id = _text(runtime_id, "runtime_id", 200)
        if not all(callable(callback) for callback in (validate_spec, predict, observe, persist)):
            raise ValueError("trusted operator callbacks are required")
        self._validate, self._predict, self._observe, self._persist = validate_spec, predict, observe, persist
        self._session_id = secrets.token_hex(16)
        self._tests, self._events, self._known = [], [], {}

    def _emit(self, kind, payload):
        event = {"protocol": PROTOCOL, "session_id": self._session_id,
                 "sequence": len(self._events) + 1, "kind": kind,
                 "previous_event_sha256": self._events[-1]["event_sha256"] if self._events else None,
                 "payload": deepcopy(payload)}
        event["event_sha256"] = digest(event)
        receipt = _text(self._persist(deepcopy(event)), "durable receipt", 500)
        self._events.append(dict(event, receipt=receipt))
        return receipt

    def _fail(self, test, stage, error):
        test.update(status="failed", failure_stage=stage, failure_type=type(error).__name__)
        try:
            self._emit("failed", {"test_id": test["test_id"], "stage": stage,
                                  "error_type": type(error).__name__,
                                  "collected_observations": len(test["observations"])})
        except Exception:
            test["failure_receipt_missing"] = True

    def _ingest(self, records):
        if not isinstance(records, list) or len(records) > 512:
            raise ValueError("records must be the complete bounded operator history")
        additions = {}
        for record in records:
            rid = _text(record.get("id"), "observation id", 150)
            spec = self._validate(deepcopy(record["spec"]))
            observation = record["observation"]
            if observation["axis"] != _axis(spec, self._public) or observation["channels"] != self._public["channels"]:
                raise ValueError("prior observation contract mismatch")
            canonical = {"id": rid, "spec": spec,
                         "observation": {"axis": observation["axis"], "channels": observation["channels"],
                                         "values": _matrix(observation["values"], spec, self._public)}}
            if rid in additions or (rid in self._known and digest(canonical) != digest(self._known[rid])):
                raise ValueError("duplicate or changed prior observation")
            additions[rid] = canonical
        if len(set(self._known) | set(additions)) > 768:
            raise ValueError("operator observation history exceeds evidence-package bound")
        self._known.update(deepcopy(additions))

    def _request(self, request):
        fields = ("profile", "scope", "rivals", "experiments", "readout", "replicates", "revision_of", "change_note")
        _keys(request, fields, "request")
        if request["profile"] not in ("mechanism_discrimination", "regime_transfer"):
            raise ValueError("unsupported prospective profile")
        result = {"profile": request["profile"], "scope": _text(request["scope"], "scope"),
                  "replicates": _integer(request["replicates"], "replicates", 4, 16)}
        experiments = request["experiments"]
        if not isinstance(experiments, list) or not 1 <= len(experiments) <= 2:
            raise ValueError("require one or two experiments")
        canonical, ids = [], set()
        for item in experiments:
            _keys(item, ("id", "role", "spec"), "experiment")
            eid = _text(item["id"], "experiment id", 40)
            if eid in ids or item["role"] not in ("target", "reference"):
                raise ValueError("invalid experiment identity or role")
            ids.add(eid)
            spec = self._validate(deepcopy(item["spec"]))
            if len(json.dumps(spec, allow_nan=False)) > 64000:
                raise ValueError("experiment spec too large")
            _axis(spec, self._public)
            canonical.append({"id": eid, "role": item["role"], "spec": spec})
        if len({digest(item["spec"]) for item in canonical}) != len(canonical) or not any(item["role"] == "target" for item in canonical):
            raise ValueError("require distinct experiments and a target")
        result["experiments"] = canonical
        terms = request["readout"]
        if not isinstance(terms, list) or not 1 <= len(terms) <= 4:
            raise ValueError("readout requires one to four terms")
        readout, used, target_novel = [], set(), False
        known_controls = {digest(_controls(r["spec"], self._public)) for r in self._known.values()}
        for term in terms:
            _keys(term, ("experiment_id", "row", "channel", "weight"), "readout term")
            item = next((e for e in canonical if e["id"] == term["experiment_id"]), None)
            if item is None or term["channel"] not in self._public["channels"]:
                raise ValueError("unknown readout experiment or channel")
            axis = _axis(item["spec"], self._public)
            row = _integer(term["row"], "readout row", 0, len(axis) - 1)
            if axis[row] == 0:
                raise ValueError("initial-coordinate readouts are not eligible in this pilot")
            weight = _number(term["weight"], "readout weight", -1.0, 1.0)
            identity = (item["id"], row, term["channel"])
            if weight == 0 or identity in used:
                raise ValueError("zero or duplicate readout term")
            used.add(identity)
            controls_hash = digest(_controls(item["spec"], self._public))
            seen_coordinate = any(controls_hash == digest(_controls(r["spec"], self._public))
                                  and axis[row] in _axis(r["spec"], self._public) for r in self._known.values())
            if item["role"] == "target" and seen_coordinate:
                raise ValueError("target requires previously unobserved readouts; use reference role for known conditions")
            if item["role"] == "target" and not seen_coordinate:
                target_novel = True
            if item["role"] == "target" and request["profile"] == "regime_transfer" and controls_hash in known_controls:
                raise ValueError("transfer target must change previously observed controls, not just sampling")
            readout.append({"experiment_id": item["id"], "row": row, "channel": term["channel"], "weight": weight})
        if not target_novel or {term["experiment_id"] for term in readout} != ids:
            raise ValueError("require a previously unobserved target readout and use every experiment")
        result["readout"] = readout
        rivals = request["rivals"]
        if not isinstance(rivals, list) or len(rivals) != 2:
            raise ValueError("exactly two rival predictors are required")
        result["rivals"] = []
        tolerance_max = MAX_TOLERANCE_PER_SCALE * sum(abs(t["weight"]) for t in readout)
        for rival in rivals:
            _keys(rival, ("id", "predictor_code", "rationale", "evidence_ids", "tolerance"), "rival")
            code = _text(rival["predictor_code"], "predictor_code", 64000)
            try:
                parsed = ast.parse(code, feature_version=8)
            except (SyntaxError, ValueError, RecursionError):
                raise ValueError("invalid predictor syntax") from None
            if not any(isinstance(node, ast.FunctionDef) and node.name == "predict" for node in parsed.body):
                raise ValueError("predictor must define predict(spec)")
            evidence = rival["evidence_ids"]
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 48 or any(not isinstance(e, str) or e not in self._known for e in evidence) or len(set(evidence)) != len(evidence):
                raise ValueError("rival evidence must cite prior operator observations")
            result["rivals"].append({"id": _text(rival["id"], "rival id", 40), "predictor_code": code,
                                     "code_sha256": _code_hash(code), "rationale": _text(rival["rationale"], "rationale"),
                                     "evidence_ids": list(evidence), "tolerance": _number(rival["tolerance"], "tolerance", 0.0, tolerance_max)})
        if len({r["id"] for r in result["rivals"]}) != 2 or len({r["code_sha256"] for r in result["rivals"]}) != 2:
            raise ValueError("rivals need distinct identities and code")
        parent = request["revision_of"]
        result.update(revision_of=parent, change_note=request["change_note"])
        if parent is None:
            if request["change_note"] != "":
                raise ValueError("change_note requires a parent test")
        else:
            parent_test = next((t for t in self._tests if t["test_id"] == parent and t["status"] == "completed"), None)
            if parent_test is None:
                raise ValueError("revision requires a completed parent test")
            _text(request["change_note"], "change_note")
            rejected = parent_test["result"]["counterexample_candidate_ids"]
            old_hashes = {r["code_sha256"] for r in parent_test["registration"]["rivals"]}
            rejected_hashes = {r["code_sha256"] for r in parent_test["registration"]["rivals"] if r["id"] in rejected}
            current_hashes = {r["code_sha256"] for r in result["rivals"]}
            parent_ids = {record["id"] for record in parent_test["observations"]}
            if not (current_hashes & rejected_hashes) or not (current_hashes - old_hashes) or not any(parent_ids & set(r["evidence_ids"]) for r in result["rivals"] if r["code_sha256"] not in old_hashes):
                raise ValueError("refinement must retain a refuted rival and test a new code revision citing the counterexample")
        return result

    def register(self, request, *, records):
        """Freeze predictions and durably seal them before any fresh observation."""
        if len(self._tests) >= self._max_tests or any(t["status"] in ("preparing", "registered", "observing") for t in self._tests):
            raise ValueError("test family exhausted or another test is pending")
        self._ingest(records)
        canonical = self._request(request)
        test_id = "prospective-%s-%02d" % (self._session_id, len(self._tests) + 1)
        test = {"test_id": test_id, "status": "preparing", "observations": []}
        self._tests.append(test)
        try:
            registration = dict(canonical, protocol=PROTOCOL, test_id=test_id,
                                session_id=self._session_id, execution_runtime=self._runtime_id,
                                public=deepcopy(self._public), max_tests=self._max_tests,
                                family_alpha=self._family_alpha, alpha=self._family_alpha / self._max_tests,
                                prior_observation_sha256={rid: digest(r) for rid, r in sorted(self._known.items())})
            for rival in registration["rivals"]:
                outputs = {}
                for experiment in registration["experiments"]:
                    spec = experiment["spec"]
                    first = _matrix(self._predict(rival["predictor_code"], deepcopy(spec)), spec, self._public)
                    second = _matrix(self._predict(rival["predictor_code"], deepcopy(spec)), spec, self._public)
                    if first != second:
                        raise ValueError("predictor is not reproducible in isolated replay")
                    outputs[experiment["id"]] = first
                rival.update(predictions=outputs, predictions_sha256=digest(outputs))
            registration["design"] = _design(registration)
            registration["seal_sha256"] = digest(registration)
            test["registration"] = deepcopy(registration)
            test["registration_receipt"] = self._emit("registered", registration)
            test["status"] = "registered"
            return deepcopy(registration)
        except Exception as error:
            self._fail(test, "registration", error)
            raise

    def collect(self, test_id):
        """Run the fixed replication plan once; failed/partial attempts cannot retry."""
        test = next((t for t in self._tests if t["test_id"] == test_id), None)
        if test is None or test["status"] != "registered":
            raise ValueError("only a registered, uncollected test can collect fresh data")
        registration = test["registration"]
        test["status"] = "observing"
        try:
            self._emit("collection_started", {"test_id": test_id, "seal_sha256": registration["seal_sha256"]})
            for replica in range(registration["replicates"]):
                for experiment in registration["experiments"]:
                    key = "%s:%s:%d" % (test_id, experiment["id"], replica)
                    response = self._observe(deepcopy(experiment["spec"]), noise_key=key)
                    if response["axis"] != _axis(experiment["spec"], self._public) or response["channels"] != self._public["channels"]:
                        raise ValueError("fresh observation contract mismatch")
                    response = {"axis": response["axis"], "channels": response["channels"],
                                "values": _matrix(response["values"], experiment["spec"], self._public)}
                    rid = "%s-%s-%02d" % (test_id, experiment["id"], replica)
                    record = {"id": rid, "experiment_id": experiment["id"], "replica": replica,
                              "noise_key": key, "observation": response}
                    test["observations"].append(record)
                    self._known[rid] = {"id": rid, "spec": deepcopy(experiment["spec"]), "observation": deepcopy(response)}
                    self._emit("fresh_observation", {"test_id": test_id, "record": record, "record_sha256": digest(record)})
            observation_hash = digest(test["observations"])
            result = recompute_result(registration, test["observations"], expected_seal=registration["seal_sha256"],
                                      expected_observations_sha256=observation_hash)
            self._emit("completed", {"test_id": test_id, "seal_sha256": registration["seal_sha256"],
                                     "observations_sha256": observation_hash, "result": result})
            test.update(status="completed", observations_sha256=observation_hash, result=result)
            return deepcopy(result)
        except Exception as error:
            self._fail(test, "collection", error)
            # Never resample after a failure or expose a partial-data decision.
            raise

    def snapshot(self):
        """Export all attempts, including pending and failed tests, without reruns."""
        return deepcopy({"protocol": PROTOCOL, "session_id": self._session_id,
                         "max_tests": self._max_tests, "family_alpha": self._family_alpha,
                         "alpha_reserved": len(self._tests) * self._family_alpha / self._max_tests,
                         "tests": self._tests, "events": self._events,
                         "mechanism_identified": False, "discovery_depth_certified": False})
