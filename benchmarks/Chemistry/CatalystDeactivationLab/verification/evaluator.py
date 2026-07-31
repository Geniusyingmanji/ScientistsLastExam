"""Stateful synthetic catalyst-deactivation laboratory, version 1.

The candidate schedules blank, calibration-standard and irreversible reaction
events against a finite coupon inventory.  The trusted callback enforces state
parents, idempotent request IDs, coupon depletion and deterministic out-of-order
completion.  Submitted kinetics, drift, model refusal and a fresh-batch policy
are scored on separate axes.

This reduced-order laboratory is a benchmark state machine, not experimental
catalysis or evidence for an autonomous scientific discovery.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
from scipy.optimize import least_squares


CATALYST_DEACTIVATION_LAB_V1 = True

GAS_CONSTANT = 8.31446261815324
STANDARD_RESPONSE = 1.5
PHYSICAL_ACT_BUDGET = 12
MAX_BATCH_SIZE = 3
COUPON_COUNT = 4
COUPON_MAX_REACTIONS = 3

TEMPERATURE_BOUNDS = (440.0, 560.0)
CONCENTRATION_BOUNDS = (0.10, 1.20)
DURATION_BOUNDS = (2.0, 15.0)
LOG10_A_BOUNDS = (4.5, 7.5)
ACTIVATION_ENERGY_BOUNDS = (35.0, 90.0)
DEACTIVATION_BOUNDS = (0.001, 0.050)
GAIN_DRIFT_BOUNDS = (-0.030, 0.030)
OFFSET_DRIFT_BOUNDS = (-0.010, 0.010)

DEVELOPMENT_SPECS = (
    (18401, "in_library", 0.0030),
    (18413, "in_library", 0.0032),
    (18427, "in_library", 0.0035),
    (18433, "step_drift", 0.0030),
    (18443, "two_site", 0.0032),
)
HELDOUT_SPECS = (
    (28403, "in_library", 0.0040),
    (28411, "in_library", 0.0042),
    (28429, "two_site", 0.0040),
)

SUBMISSION_KEYS = {
    "log10_preexponential",
    "activation_energy_kj_mol",
    "deactivation_rate_per_min",
    "gain_drift_per_event",
    "offset_drift_per_event",
    "operating_policy",
    "confidence",
    "abstain",
    "evidence_event_ids",
    "final_lab_state_version",
    "final_coupon_state_versions",
}
POLICY_KEYS = {"temperature_k", "feed_concentration", "duration_min"}


def _token(prefix, *values):
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:14]


def _strict_int(value, name):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be an integer")
    try:
        integer = int(value)
    except Exception as exc:
        raise ValueError(name + " must be an integer") from exc
    if integer != value:
        raise ValueError(name + " must be an integer")
    return integer


def _finite_scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise ValueError(name + " must be real-valued and non-boolean")
    try:
        scalar = float(value)
    except Exception as exc:
        raise ValueError(name + " must be numeric") from exc
    if not math.isfinite(scalar):
        raise ValueError(name + " must be finite")
    return scalar


def _bounded(value, bounds, name):
    scalar = _finite_scalar(value, name)
    if scalar < bounds[0] or scalar > bounds[1]:
        raise ValueError(name + " outside public bounds")
    return scalar


def _strict_bool(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be boolean")
    return bool(value)


def _rate_constant(log10_a, activation_energy_kj_mol, temperature_k):
    return float(
        (10.0 ** float(log10_a))
        * math.exp(
            -1000.0 * float(activation_energy_kj_mol)
            / (GAS_CONSTANT * float(temperature_k))
        )
    )


def _production_rate(log10_a, activation_energy_kj_mol, temperature_k,
                     concentration):
    concentration = float(concentration)
    return float(
        _rate_constant(log10_a, activation_energy_kj_mol, temperature_k)
        * concentration / (1.0 + 0.4 * concentration)
    )


def _deactivation_rate(d_ref, temperature_k, concentration):
    return float(
        float(d_ref) * float(concentration)
        * math.exp(
            (30000.0 / GAS_CONSTANT)
            * (1.0 / 500.0 - 1.0 / float(temperature_k))
        )
    )


def _closed_form_reaction(activity, log10_a, activation_energy_kj_mol,
                          d_ref, temperature_k, concentration, duration_min):
    activity = float(activity)
    duration_min = float(duration_min)
    q_value = _production_rate(
        log10_a, activation_energy_kj_mol, temperature_k, concentration
    )
    decay = _deactivation_rate(d_ref, temperature_k, concentration)
    if decay <= 1.0e-14:
        product = activity * q_value * duration_min
    else:
        product = activity * q_value * (-math.expm1(-decay * duration_min)) / decay
    post_activity = activity * math.exp(-decay * duration_min)
    return float(product), float(post_activity)


def _numerical_reaction(activity, log10_a, activation_energy_kj_mol,
                        d_ref, temperature_k, concentration, duration_min,
                        steps=20000):
    """Independent midpoint quadrature used only by calibration/tests."""
    steps = int(steps)
    grid = (np.arange(steps, dtype=float) + 0.5) * float(duration_min) / steps
    q_value = _production_rate(
        log10_a, activation_energy_kj_mol, temperature_k, concentration
    )
    decay = _deactivation_rate(d_ref, temperature_k, concentration)
    rates = float(activity) * np.exp(-decay * grid) * q_value
    product = float(np.sum(rates) * float(duration_min) / steps)
    post_activity = float(activity) * math.exp(-decay * float(duration_min))
    return product, post_activity


def _make_world(spec):
    seed, kind, noise = int(spec[0]), str(spec[1]), float(spec[2])
    rng = np.random.default_rng(seed)
    world = {
        "seed": seed,
        "kind": kind,
        "noise": noise,
        "log10_a": float(rng.uniform(5.65, 6.35)),
        "activation_energy": float(rng.uniform(55.0, 72.0)),
        "d_ref": float(rng.uniform(0.007, 0.018)),
        "gain_base": float(rng.uniform(0.90, 1.10)),
        "offset_base": float(rng.uniform(-0.018, 0.018)),
        "gain_drift": float(rng.uniform(-0.0065, 0.0065)),
        "offset_drift": float(rng.uniform(-0.0014, 0.0014)),
        "shift_log10_a": float(rng.uniform(-0.025, 0.025)),
        "shift_activation_energy": float(rng.uniform(-0.8, 0.8)),
        "shift_d_ref_scale": float(rng.uniform(0.90, 1.10)),
        "shift_initial_activity": float(rng.uniform(0.90, 0.98)),
    }
    if kind == "step_drift":
        world.update({
            "gain_step": float(rng.choice((-1.0, 1.0)) * rng.uniform(0.10, 0.15)),
            "offset_step": float(rng.choice((-1.0, 1.0)) * rng.uniform(0.022, 0.036)),
            "step_sequence": 7,
        })
    if kind == "two_site":
        world.update({
            "site_fraction": float(rng.uniform(0.50, 0.68)),
            "slow_scale": float(rng.uniform(0.18, 0.30)),
            "fast_scale": float(rng.uniform(3.8, 5.2)),
            "site_rate_scale": float(rng.uniform(0.82, 1.18)),
        })
    return world


def _instrument_state(world, sequence):
    x_value = float(int(sequence) - 1)
    gain = world["gain_base"] + world["gain_drift"] * x_value
    offset = world["offset_base"] + world["offset_drift"] * x_value
    if world["kind"] == "step_drift" and int(sequence) >= world["step_sequence"]:
        gain += world["gain_step"]
        offset += world["offset_step"]
    return float(gain), float(offset)


def _request_noise(world, request_id, sequence):
    digest = hashlib.sha256(
        (str(world["seed"]) + "|" + str(request_id) + "|" + str(sequence)).encode("utf-8")
    ).digest()
    words = np.frombuffer(digest[:16], dtype="<u4")
    seed = np.random.SeedSequence([int(value) for value in words]).generate_state(1)[0]
    return float(np.random.default_rng(int(seed)).normal(0.0, world["noise"]))


def _request_latency(world, request):
    digest = hashlib.sha256(
        (str(world["seed"]) + "|latency|" + request["request_id"]).encode("utf-8")
    ).digest()
    jitter = int.from_bytes(digest[:2], "little") / 65535.0
    if request["kind"] == "blank":
        base = 1.1
    elif request["kind"] == "standard":
        base = 1.8
    else:
        base = (
            0.32 * request["duration_min"]
            + 0.012 * (TEMPERATURE_BOUNDS[1] - request["temperature_k"])
            + 0.45 * request["feed_concentration"]
        )
    return float(base + 0.7 * jitter)


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _StatefulLaboratory:
    def __init__(self, world):
        self.world = world
        self.lab_state_version = 0
        self.physical_acts = 0
        self.callback_calls = 0
        self.failure = None
        self.events = []
        self.cache = {}
        self.exact_retry_count = 0
        self.conflicting_retry_count = 0
        self.stale_parent_attempt_count = 0
        self.out_of_order_batch_count = 0
        self.duplicate_physical_act_count = 0
        self.calibration_parent_event_id = None
        self.calibration_id = _token("CAL-", world["seed"], "instrument")
        self.coupons = {}
        for index in range(COUPON_COUNT):
            coupon_id = _token("CPN-", world["seed"], index)
            if world["kind"] == "two_site":
                activity = [1.0, 1.0]
            else:
                activity = 1.0
            self.coupons[coupon_id] = {
                "version": 0,
                "remaining_uses": COUPON_MAX_REACTIONS,
                "activity": activity,
                "parent_event_id": None,
            }

    def _fail(self, code, message):
        if self.failure is None:
            self.failure = str(code)
        raise ValueError(str(message))

    def public_problem(self):
        return {
            "kinetic_model": (
                "q=10**log10_A*exp(-Ea/(R*T))*C/(1+0.4*C); "
                "lambda=d_ref*C*exp(30000/R*(1/500-1/T)); "
                "activity(t)=activity_before*exp(-lambda*t); "
                "true_product=integral(activity(t)*q,t=0..duration)"
            ),
            "gas_constant_j_mol_k": GAS_CONSTANT,
            "standard_reference_response": STANDARD_RESPONSE,
            "parameter_bounds": {
                "log10_preexponential": list(LOG10_A_BOUNDS),
                "activation_energy_kj_mol": list(ACTIVATION_ENERGY_BOUNDS),
                "deactivation_rate_per_min": list(DEACTIVATION_BOUNDS),
                "gain_drift_per_event": list(GAIN_DRIFT_BOUNDS),
                "offset_drift_per_event": list(OFFSET_DRIFT_BOUNDS),
            },
            "condition_bounds": {
                "temperature_k": list(TEMPERATURE_BOUNDS),
                "feed_concentration": list(CONCENTRATION_BOUNDS),
                "duration_min": list(DURATION_BOUNDS),
            },
            "policy_objective": (
                "maximize three-cycle fresh-coupon product minus 0.0012*(T-440)*duration "
                "and 0.055*C*duration per cycle"
            ),
            "coupon_ids": sorted(self.coupons),
            "coupon_state_versions": {
                key: int(value["version"]) for key, value in self.coupons.items()
            },
            "coupon_remaining_uses": {
                key: int(value["remaining_uses"]) for key, value in self.coupons.items()
            },
            "lab_state_version": int(self.lab_state_version),
            "physical_act_budget": PHYSICAL_ACT_BUDGET,
            "maximum_batch_size": MAX_BATCH_SIZE,
            "maximum_reactions_per_coupon": COUPON_MAX_REACTIONS,
            "model_scope": (
                "single-site first-order production, exponential deactivation and linear "
                "instrument gain/offset drift; abstain for resolvable departures"
            ),
        }

    def _normalize_request(self, request):
        if not isinstance(request, dict):
            self._fail("invalid_request", "each request must be a dictionary")
        allowed = {
            "request_id", "kind", "lab_state_version", "coupon_id",
            "coupon_state_version", "temperature_k", "feed_concentration",
            "duration_min",
        }
        if not set(request).issubset(allowed):
            self._fail("invalid_request", "request contains unknown keys")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 80:
            self._fail("invalid_request", "request_id must be a nonempty short string")
        kind = request.get("kind")
        if kind not in {"blank", "standard", "reaction"}:
            self._fail("invalid_request", "unknown experiment kind")
        normalized = {
            "request_id": request_id,
            "kind": kind,
            "lab_state_version": _strict_int(
                request.get("lab_state_version"), "lab_state_version"
            ),
        }
        if kind == "reaction":
            required = {
                "request_id", "kind", "lab_state_version", "coupon_id",
                "coupon_state_version", "temperature_k", "feed_concentration",
                "duration_min",
            }
            if set(request) != required:
                self._fail("invalid_request", "reaction request has an incomplete schema")
            coupon_id = request.get("coupon_id")
            if not isinstance(coupon_id, str):
                self._fail("invalid_request", "coupon_id must be a string")
            normalized.update({
                "coupon_id": coupon_id,
                "coupon_state_version": _strict_int(
                    request.get("coupon_state_version"), "coupon_state_version"
                ),
                "temperature_k": _bounded(
                    request.get("temperature_k"), TEMPERATURE_BOUNDS, "temperature_k"
                ),
                "feed_concentration": _bounded(
                    request.get("feed_concentration"), CONCENTRATION_BOUNDS,
                    "feed_concentration",
                ),
                "duration_min": _bounded(
                    request.get("duration_min"), DURATION_BOUNDS, "duration_min"
                ),
            })
        elif set(request) != {"request_id", "kind", "lab_state_version"}:
            self._fail("invalid_request", "calibration request has an invalid schema")
        return normalized

    def _reaction_truth(self, coupon, request):
        world = self.world
        conditions = (
            request["temperature_k"], request["feed_concentration"],
            request["duration_min"],
        )
        if world["kind"] != "two_site":
            product, activity = _closed_form_reaction(
                coupon["activity"], world["log10_a"], world["activation_energy"],
                world["d_ref"], *conditions
            )
            return product, activity
        fraction = world["site_fraction"]
        activities = list(coupon["activity"])
        slow_product, slow_activity = _closed_form_reaction(
            activities[0],
            world["log10_a"] + math.log10(world["site_rate_scale"]),
            world["activation_energy"],
            world["d_ref"] * world["slow_scale"],
            *conditions
        )
        fast_product, fast_activity = _closed_form_reaction(
            activities[1],
            world["log10_a"] + math.log10(world["site_rate_scale"]),
            world["activation_energy"],
            world["d_ref"] * world["fast_scale"],
            *conditions
        )
        return (
            float(fraction * slow_product + (1.0 - fraction) * fast_product),
            [float(slow_activity), float(fast_activity)],
        )

    def _execute(self, request, latency):
        sequence = self.physical_acts + 1
        execution_parent = self.lab_state_version
        gain, offset = _instrument_state(self.world, sequence)
        if request["kind"] == "blank":
            reference = 0.0
        elif request["kind"] == "standard":
            reference = STANDARD_RESPONSE
        else:
            coupon = self.coupons[request["coupon_id"]]
            reference, post_activity = self._reaction_truth(coupon, request)
        raw_signal = (
            gain * float(reference) + offset
            + _request_noise(self.world, request["request_id"], sequence)
        )
        event_id = _token(
            "EVT-", self.world["seed"], request["request_id"], sequence,
            _canonical_json(request),
        )
        event = {
            "event_id": event_id,
            "request_id": request["request_id"],
            "kind": request["kind"],
            "scheduled_lab_state_version": int(request["lab_state_version"]),
            "execution_parent_lab_state_version": int(execution_parent),
            "post_lab_state_version": int(execution_parent + 1),
            "instrument_sequence": int(sequence),
            "completion_latency": round(float(latency), 8),
            "calibration_id": self.calibration_id,
            "calibration_parent_event_id": self.calibration_parent_event_id,
            "raw_signal": round(float(raw_signal), 12),
        }
        if request["kind"] in {"blank", "standard"}:
            event["known_reference_signal"] = (
                0.0 if request["kind"] == "blank" else STANDARD_RESPONSE
            )
        else:
            coupon = self.coupons[request["coupon_id"]]
            event.update({
                "coupon_id": request["coupon_id"],
                "scheduled_coupon_state_version": int(
                    request["coupon_state_version"]
                ),
                "coupon_parent_event_id": coupon["parent_event_id"],
                "post_coupon_state_version": int(coupon["version"] + 1),
                "temperature_k": request["temperature_k"],
                "feed_concentration": request["feed_concentration"],
                "duration_min": request["duration_min"],
                "remaining_coupon_uses": int(coupon["remaining_uses"] - 1),
            })
            coupon["activity"] = post_activity
            coupon["version"] += 1
            coupon["remaining_uses"] -= 1
            coupon["parent_event_id"] = event_id
        self.physical_acts += 1
        self.lab_state_version += 1
        self.calibration_parent_event_id = event_id
        self.events.append(event)
        self.cache[request["request_id"]] = {
            "payload": _canonical_json(request),
            "event": copy.deepcopy(event),
        }
        return event

    def experiment(self, requests):
        self.callback_calls += 1
        if not isinstance(requests, (list, tuple)):
            self._fail("invalid_request", "experiment expects a list of requests")
        if not 1 <= len(requests) <= MAX_BATCH_SIZE:
            self._fail("invalid_request", "batch size outside public bounds")
        normalized = [self._normalize_request(request) for request in requests]
        request_ids = [request["request_id"] for request in normalized]
        if len(set(request_ids)) != len(request_ids):
            self._fail("invalid_request", "request IDs must be unique within a batch")

        cached = []
        fresh = []
        for request in normalized:
            previous = self.cache.get(request["request_id"])
            if previous is None:
                fresh.append(request)
            elif previous["payload"] == _canonical_json(request):
                cached.append(copy.deepcopy(previous["event"]))
                self.exact_retry_count += 1
            else:
                self.conflicting_retry_count += 1
                self._fail(
                    "conflicting_retry", "request_id was reused with a different payload"
                )

        active_coupons = []
        for request in fresh:
            if request["lab_state_version"] != self.lab_state_version:
                self.stale_parent_attempt_count += 1
                self._fail("stale_parent", "laboratory state parent is stale")
            if request["kind"] == "reaction":
                coupon_id = request["coupon_id"]
                if coupon_id not in self.coupons:
                    self._fail("invalid_request", "unknown coupon_id")
                coupon = self.coupons[coupon_id]
                if request["coupon_state_version"] != coupon["version"]:
                    self.stale_parent_attempt_count += 1
                    self._fail("stale_parent", "coupon state parent is stale")
                if coupon["remaining_uses"] <= 0:
                    self._fail("sample_exhausted", "coupon has no remaining reactions")
                active_coupons.append(coupon_id)
        if len(active_coupons) != len(set(active_coupons)):
            self._fail(
                "concurrent_sample_conflict",
                "one coupon cannot run two concurrent reactions",
            )
        if self.physical_acts + len(fresh) > PHYSICAL_ACT_BUDGET:
            self._fail("budget_exceeded", "physical-act budget exceeded")

        indexed = [
            (index, _request_latency(self.world, request), request)
            for index, request in enumerate(fresh)
        ]
        execution = sorted(indexed, key=lambda row: (row[1], row[0]))
        if [row[0] for row in execution] != list(range(len(execution))):
            self.out_of_order_batch_count += 1
        new_events = [self._execute(request, latency) for _, latency, request in execution]
        returned = cached + [copy.deepcopy(event) for event in new_events]
        returned.sort(key=lambda event: event["instrument_sequence"])
        return {
            "events": returned,
            "lab_state_version": int(self.lab_state_version),
            "coupon_state_versions": {
                key: int(value["version"]) for key, value in self.coupons.items()
            },
            "coupon_remaining_uses": {
                key: int(value["remaining_uses"]) for key, value in self.coupons.items()
            },
            "physical_acts_used": int(self.physical_acts),
            "physical_acts_remaining": int(PHYSICAL_ACT_BUDGET - self.physical_acts),
        }


def _validate_submission(submission, laboratory):
    if not isinstance(submission, dict) or set(submission) != SUBMISSION_KEYS:
        raise ValueError("submission must contain exactly the documented keys")
    log10_a = _bounded(
        submission["log10_preexponential"], LOG10_A_BOUNDS,
        "log10_preexponential",
    )
    activation = _bounded(
        submission["activation_energy_kj_mol"], ACTIVATION_ENERGY_BOUNDS,
        "activation_energy_kj_mol",
    )
    d_ref = _bounded(
        submission["deactivation_rate_per_min"], DEACTIVATION_BOUNDS,
        "deactivation_rate_per_min",
    )
    gain_drift = _bounded(
        submission["gain_drift_per_event"], GAIN_DRIFT_BOUNDS,
        "gain_drift_per_event",
    )
    offset_drift = _bounded(
        submission["offset_drift_per_event"], OFFSET_DRIFT_BOUNDS,
        "offset_drift_per_event",
    )
    policy_value = submission["operating_policy"]
    if not isinstance(policy_value, dict) or set(policy_value) != POLICY_KEYS:
        raise ValueError("operating_policy must contain exactly the documented keys")
    policy = {
        "temperature_k": _bounded(
            policy_value["temperature_k"], TEMPERATURE_BOUNDS, "temperature_k"
        ),
        "feed_concentration": _bounded(
            policy_value["feed_concentration"], CONCENTRATION_BOUNDS,
            "feed_concentration",
        ),
        "duration_min": _bounded(
            policy_value["duration_min"], DURATION_BOUNDS, "duration_min"
        ),
    }
    confidence = _bounded(submission["confidence"], (0.0, 1.0), "confidence")
    abstain = _strict_bool(submission["abstain"], "abstain")

    evidence = submission["evidence_event_ids"]
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise ValueError("evidence_event_ids must be a nonempty list")
    if not all(isinstance(value, str) and value for value in evidence):
        raise ValueError("evidence_event_ids must contain strings")
    if len(evidence) != len(set(evidence)):
        raise ValueError("evidence_event_ids must be unique")
    observed_ids = {event["event_id"] for event in laboratory.events}
    if not set(evidence).issubset(observed_ids):
        raise ValueError("evidence_event_ids contain an unknown event")

    final_lab = _strict_int(
        submission["final_lab_state_version"], "final_lab_state_version"
    )
    if final_lab != laboratory.lab_state_version:
        raise ValueError("final_lab_state_version does not match the laboratory")
    versions = submission["final_coupon_state_versions"]
    expected_versions = {
        key: int(value["version"]) for key, value in laboratory.coupons.items()
    }
    if not isinstance(versions, dict) or set(versions) != set(expected_versions):
        raise ValueError("final_coupon_state_versions has the wrong coupon set")
    normalized_versions = {
        key: _strict_int(value, "coupon state version")
        for key, value in versions.items()
    }
    if normalized_versions != expected_versions:
        raise ValueError("final_coupon_state_versions does not match the laboratory")
    lineage = len(set(evidence)) / max(len(observed_ids), 1)
    return {
        "log10_a": log10_a,
        "activation": activation,
        "d_ref": d_ref,
        "gain_drift": gain_drift,
        "offset_drift": offset_drift,
        "policy": policy,
        "confidence": confidence,
        "abstain": abstain,
        "lineage": float(lineage),
    }


def _quality(value, truth, tolerance):
    return float(np.clip(1.0 - abs(float(value) - float(truth)) / tolerance, 0.0, 1.0))


def _mechanism_score(world, values):
    return float(
        0.24 * _quality(values["log10_a"], world["log10_a"], 0.55)
        + 0.24 * _quality(values["activation"], world["activation_energy"], 7.0)
        + 0.22 * _quality(
            math.log(values["d_ref"]), math.log(world["d_ref"]), 0.55
        )
        + 0.16 * _quality(values["gain_drift"], world["gain_drift"], 0.0045)
        + 0.14 * _quality(values["offset_drift"], world["offset_drift"], 0.0012)
    )


def _sealed_conditions(seed):
    rng = np.random.default_rng(int(seed) + 51091)
    conditions = []
    for _ in range(8):
        conditions.append((
            float(rng.uniform(*TEMPERATURE_BOUNDS)),
            float(rng.uniform(*CONCENTRATION_BOUNDS)),
            float(rng.uniform(*DURATION_BOUNDS)),
        ))
    return conditions


def _prediction_score(world, values, shifted=False):
    errors = []
    baselines = []
    truth_log10_a = world["log10_a"] + (
        world["shift_log10_a"] if shifted else 0.0
    )
    truth_activation = world["activation_energy"] + (
        world["shift_activation_energy"] if shifted else 0.0
    )
    truth_d_ref = world["d_ref"] * (
        world["shift_d_ref_scale"] if shifted else 1.0
    )
    initial_activity = world["shift_initial_activity"] if shifted else 1.0
    for temperature, concentration, duration in _sealed_conditions(world["seed"]):
        truth, _ = _closed_form_reaction(
            initial_activity, truth_log10_a, truth_activation, truth_d_ref,
            temperature, concentration, duration,
        )
        prediction, _ = _closed_form_reaction(
            1.0, values["log10_a"], values["activation"], values["d_ref"],
            temperature, concentration, duration,
        )
        errors.append((prediction - truth) ** 2)
        baselines.append(truth ** 2)
    rmse = math.sqrt(float(np.mean(errors)))
    baseline_rmse = max(1.0e-9, math.sqrt(float(np.mean(baselines))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _policy_utility(parameters, policy, initial_activity=1.0):
    activity = float(initial_activity)
    total = 0.0
    temperature = float(policy["temperature_k"])
    concentration = float(policy["feed_concentration"])
    duration = float(policy["duration_min"])
    for _ in range(3):
        product, activity = _closed_form_reaction(
            activity,
            parameters["log10_a"], parameters["activation"], parameters["d_ref"],
            temperature, concentration, duration,
        )
        cost = (
            0.0012 * (temperature - TEMPERATURE_BOUNDS[0]) * duration
            + 0.055 * concentration * duration
        )
        total += product - cost
    return float(total)


_POLICY_CACHE = {}


def _policy_grid():
    for temperature in np.linspace(TEMPERATURE_BOUNDS[0], TEMPERATURE_BOUNDS[1], 13):
        for concentration in np.linspace(
            CONCENTRATION_BOUNDS[0], CONCENTRATION_BOUNDS[1], 12
        ):
            for duration in np.linspace(DURATION_BOUNDS[0], DURATION_BOUNDS[1], 14):
                yield {
                    "temperature_k": float(temperature),
                    "feed_concentration": float(concentration),
                    "duration_min": float(duration),
                }


def _truth_parameters(world, shifted=False):
    return {
        "log10_a": world["log10_a"] + (
            world["shift_log10_a"] if shifted else 0.0
        ),
        "activation": world["activation_energy"] + (
            world["shift_activation_energy"] if shifted else 0.0
        ),
        "d_ref": world["d_ref"] * (
            world["shift_d_ref_scale"] if shifted else 1.0
        ),
    }


def _reference_policy(world, shifted=False):
    key = (int(world["seed"]), bool(shifted))
    if key not in _POLICY_CACHE:
        parameters = _truth_parameters(world, shifted=shifted)
        initial = world["shift_initial_activity"] if shifted else 1.0
        best_policy = None
        best_value = -float("inf")
        for policy in _policy_grid():
            value = _policy_utility(parameters, policy, initial_activity=initial)
            if value > best_value:
                best_policy = dict(policy)
                best_value = value
        _POLICY_CACHE[key] = (best_policy, float(best_value))
    policy, value = _POLICY_CACHE[key]
    return dict(policy), float(value)


def _decision_score(world, policy, shifted=False):
    parameters = _truth_parameters(world, shifted=shifted)
    initial = world["shift_initial_activity"] if shifted else 1.0
    value = _policy_utility(parameters, policy, initial_activity=initial)
    _, reference = _reference_policy(world, shifted=shifted)
    if reference <= 1.0e-12:
        return 0.0
    return float(np.clip(value / reference, 0.0, 1.0))


def _invalid_record(split, index, kind, failure_kind, laboratory):
    return {
        "split": str(split),
        "world_index": int(index),
        "kind": str(kind),
        "valid": False,
        "failure_kind": str(failure_kind),
        "lineage_quality": 0.0,
        "mechanism_quality": 0.0,
        "prediction_quality": 0.0,
        "decision_quality": 0.0,
        "robust_prediction_quality": 0.0,
        "robust_decision_quality": 0.0,
        "joint_quality": 0.0,
        "robust_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "abstained": False,
        "confidence": 0.0,
        "confidence_score": 0.0,
        "physical_acts": int(laboratory.physical_acts),
        "callback_calls": int(laboratory.callback_calls),
        "coupon_reactions": int(sum(
            COUPON_MAX_REACTIONS - value["remaining_uses"]
            for value in laboratory.coupons.values()
        )),
        "out_of_order_batches": int(laboratory.out_of_order_batch_count),
        "exact_retries": int(laboratory.exact_retry_count),
        "duplicate_physical_acts": int(laboratory.duplicate_physical_act_count),
        "stale_parent_attempts": int(laboratory.stale_parent_attempt_count),
    }


def _evaluate_world(investigate_catalyst, spec, split, index):
    world = _make_world(spec)
    laboratory = _StatefulLaboratory(world)
    stage = "candidate_execution"
    try:
        submission = investigate_catalyst(
            laboratory.public_problem(), laboratory.experiment
        )
        if laboratory.failure is not None:
            raise ValueError(laboratory.failure)
        stage = "submission_validation"
        values = _validate_submission(submission, laboratory)
        stage = "trusted_scoring"
        supported = world["kind"] == "in_library"
        if supported and not values["abstain"]:
            mechanism = _mechanism_score(world, values)
            prediction = _prediction_score(world, values, shifted=False)
            decision = _decision_score(world, values["policy"], shifted=False)
            robust_prediction = _prediction_score(world, values, shifted=True)
            robust_decision = _decision_score(world, values["policy"], shifted=True)
            correct_refusal = False
            false_discovery = False
        elif not supported and values["abstain"]:
            mechanism = prediction = decision = 1.0
            robust_prediction = robust_decision = 1.0
            correct_refusal = True
            false_discovery = False
        else:
            mechanism = prediction = decision = 0.0
            robust_prediction = robust_decision = 0.0
            correct_refusal = False
            false_discovery = bool(not supported and not values["abstain"])
        joint = float((
            values["lineage"] * mechanism * prediction * decision
        ) ** 0.25)
        robust_joint = float((
            values["lineage"] * mechanism * robust_prediction * robust_decision
        ) ** 0.25)
        confidence_score = float(np.clip(
            1.0 - (values["confidence"] - joint) ** 2, 0.0, 1.0
        ))
        return {
            "split": str(split),
            "world_index": int(index),
            "kind": str(world["kind"]),
            "valid": True,
            "failure_kind": None,
            "lineage_quality": round(values["lineage"], 6),
            "mechanism_quality": round(float(mechanism), 6),
            "prediction_quality": round(float(prediction), 6),
            "decision_quality": round(float(decision), 6),
            "robust_prediction_quality": round(float(robust_prediction), 6),
            "robust_decision_quality": round(float(robust_decision), 6),
            "joint_quality": round(joint, 6),
            "robust_joint_quality": round(robust_joint, 6),
            "correct_refusal": bool(correct_refusal),
            "false_discovery": bool(false_discovery),
            "abstained": bool(values["abstain"]),
            "confidence": round(values["confidence"], 6),
            "confidence_score": round(confidence_score, 6),
            "physical_acts": int(laboratory.physical_acts),
            "callback_calls": int(laboratory.callback_calls),
            "coupon_reactions": int(sum(
                COUPON_MAX_REACTIONS - value["remaining_uses"]
                for value in laboratory.coupons.values()
            )),
            "out_of_order_batches": int(laboratory.out_of_order_batch_count),
            "exact_retries": int(laboratory.exact_retry_count),
            "duplicate_physical_acts": int(laboratory.duplicate_physical_act_count),
            "stale_parent_attempts": int(laboratory.stale_parent_attempt_count),
            "observed_event_count": int(len(laboratory.events)),
        }
    except Exception:
        if laboratory.failure is not None:
            failure_kind = laboratory.failure
        elif stage == "submission_validation":
            failure_kind = "invalid_submission"
        elif stage == "trusted_scoring":
            failure_kind = "trusted_scoring_failure"
        else:
            failure_kind = "candidate_execution_failure"
        return _invalid_record(
            split, index, world["kind"], failure_kind, laboratory
        )


def _normalized_mean(records, field):
    unsupported = sum(row["kind"] != "in_library" for row in records)
    baseline = unsupported / len(records)
    raw = float(np.mean([float(row[field]) for row in records]))
    return float(np.clip((raw - baseline) / max(1.0e-12, 1.0 - baseline), 0.0, 1.0))


def _split_metrics(records):
    supported = sum(row["kind"] == "in_library" for row in records)
    unsupported = len(records) - supported
    claims = sum(not row["abstained"] for row in records if row["valid"])
    return {
        "joint": _normalized_mean(records, "joint_quality"),
        "robust_joint": _normalized_mean(records, "robust_joint_quality"),
        "lineage": _normalized_mean(records, "lineage_quality"),
        "mechanism": _normalized_mean(records, "mechanism_quality"),
        "prediction": _normalized_mean(records, "prediction_quality"),
        "decision": _normalized_mean(records, "decision_quality"),
        "robust_prediction": _normalized_mean(records, "robust_prediction_quality"),
        "robust_decision": _normalized_mean(records, "robust_decision_quality"),
        "valid_rate": float(np.mean([bool(row["valid"]) for row in records])),
        "supported_claim_coverage": sum(
            row["kind"] == "in_library" and row["valid"] and not row["abstained"]
            for row in records
        ) / supported,
        "unsupported_refusal_rate": sum(row["correct_refusal"] for row in records)
        / unsupported,
        "false_discovery_rate": sum(row["false_discovery"] for row in records)
        / max(claims, 1),
        "confidence_score": float(np.mean([
            row["confidence_score"] for row in records
        ])),
        "mean_physical_acts": float(np.mean([
            row["physical_acts"] for row in records
        ])),
        "mean_coupon_reactions": float(np.mean([
            row["coupon_reactions"] for row in records
        ])),
        "mean_out_of_order_batches": float(np.mean([
            row["out_of_order_batches"] for row in records
        ])),
        "mean_exact_retries": float(np.mean([
            row["exact_retries"] for row in records
        ])),
        "duplicate_physical_acts": int(sum(
            row["duplicate_physical_acts"] for row in records
        )),
        "stale_parent_attempts": int(sum(
            row["stale_parent_attempts"] for row in records
        )),
    }


def evaluate(investigate_catalyst):
    development = []
    heldout = []
    rows = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(rows):
        if call_index and hasattr(investigate_catalyst, "reset_session"):
            investigate_catalyst.reset_session()
        record = _evaluate_world(investigate_catalyst, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    return {
        "combined_score": dev["joint"] if development_valid else 0.0,
        "valid": float(development_valid),
        "feasibility_rate": dev["valid_rate"],
        "robustness_score": dev["robust_joint"] if development_valid else 0.0,
        "heldout_policy_score": held["joint"] if heldout_valid else 0.0,
        "heldout_robustness_score": (
            held["robust_joint"] if heldout_valid else 0.0
        ),
        "heldout_feasibility_rate": held["valid_rate"],
        "development_lineage_score": dev["lineage"],
        "heldout_lineage_score": held["lineage"],
        "development_mechanism_score": dev["mechanism"],
        "heldout_mechanism_score": held["mechanism"],
        "development_prediction_score": dev["prediction"],
        "heldout_prediction_score": held["prediction"],
        "development_decision_score": dev["decision"],
        "heldout_decision_score": held["decision"],
        "development_robust_prediction_score": dev["robust_prediction"],
        "heldout_robust_prediction_score": held["robust_prediction"],
        "development_robust_decision_score": dev["robust_decision"],
        "heldout_robust_decision_score": held["robust_decision"],
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_unsupported_refusal_rate": dev["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_confidence_score": dev["confidence_score"],
        "heldout_confidence_score": held["confidence_score"],
        "development_mean_physical_acts": dev["mean_physical_acts"],
        "heldout_mean_physical_acts": held["mean_physical_acts"],
        "development_mean_coupon_reactions": dev["mean_coupon_reactions"],
        "heldout_mean_coupon_reactions": held["mean_coupon_reactions"],
        "development_mean_out_of_order_batches": dev["mean_out_of_order_batches"],
        "heldout_mean_out_of_order_batches": held["mean_out_of_order_batches"],
        "development_mean_exact_retries": dev["mean_exact_retries"],
        "heldout_mean_exact_retries": held["mean_exact_retries"],
        "duplicate_physical_act_count": (
            dev["duplicate_physical_acts"] + held["duplicate_physical_acts"]
        ),
        "stale_parent_attempt_count": (
            dev["stale_parent_attempts"] + held["stale_parent_attempts"]
        ),
        "candidate_instance_call_count": len(rows),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_world": development + heldout,
    }


def _calibration_fit(events):
    calibration = [
        event for event in events if event["kind"] in {"blank", "standard"}
    ]
    design = []
    target = []
    for event in calibration:
        x_value = float(event["instrument_sequence"] - 1)
        reference = float(event["known_reference_signal"])
        design.append((1.0, x_value, reference, reference * x_value))
        target.append(float(event["raw_signal"]))
    coefficients, _, _, _ = np.linalg.lstsq(
        np.asarray(design, dtype=float), np.asarray(target, dtype=float), rcond=None
    )
    residual = np.asarray(target) - np.asarray(design) @ coefficients
    return coefficients, float(math.sqrt(np.mean(residual ** 2)))


def _corrected_reactions(events, calibration):
    offset_base, offset_drift, gain_base, gain_drift = calibration
    rows = []
    for event in sorted(events, key=lambda row: row["instrument_sequence"]):
        if event["kind"] != "reaction":
            continue
        x_value = float(event["instrument_sequence"] - 1)
        gain = gain_base + gain_drift * x_value
        offset = offset_base + offset_drift * x_value
        rows.append({
            "event": event,
            "product": (float(event["raw_signal"]) - offset) / gain,
        })
    return rows


def _fit_kinetics(reactions):
    def residual(parameters):
        log10_a, activation, log_d_ref = parameters
        d_ref = math.exp(float(log_d_ref))
        activities = {}
        errors = []
        for row in reactions:
            event = row["event"]
            coupon_id = event["coupon_id"]
            activity = activities.get(coupon_id, 1.0)
            prediction, activity = _closed_form_reaction(
                activity, log10_a, activation, d_ref,
                event["temperature_k"], event["feed_concentration"],
                event["duration_min"],
            )
            activities[coupon_id] = activity
            errors.append(prediction - row["product"])
        return np.asarray(errors, dtype=float)

    result = least_squares(
        residual,
        np.asarray((6.0, 63.0, math.log(0.012)), dtype=float),
        bounds=(
            np.asarray((LOG10_A_BOUNDS[0], ACTIVATION_ENERGY_BOUNDS[0],
                        math.log(DEACTIVATION_BOUNDS[0]))),
            np.asarray((LOG10_A_BOUNDS[1], ACTIVATION_ENERGY_BOUNDS[1],
                        math.log(DEACTIVATION_BOUNDS[1]))),
        ),
        xtol=1.0e-13,
        ftol=1.0e-13,
        gtol=1.0e-13,
        max_nfev=4000,
    )
    values = {
        "log10_a": float(result.x[0]),
        "activation": float(result.x[1]),
        "d_ref": float(math.exp(result.x[2])),
    }
    rms = float(math.sqrt(np.mean(residual(result.x) ** 2)))
    return values, rms


def _model_policy(parameters):
    best_policy = None
    best_value = -float("inf")
    for policy in _policy_grid():
        value = _policy_utility(parameters, policy, initial_activity=1.0)
        if value > best_value:
            best_policy = dict(policy)
            best_value = value
    return best_policy


def _reference_agent(problem, experiment):
    coupon_ids = list(problem["coupon_ids"])
    lab_version = problem["lab_state_version"]
    coupon_versions = dict(problem["coupon_state_versions"])
    all_events = []
    first_request = None

    batches = (
        (
            ("reaction", coupon_ids[0], 535.0, 0.90, 6.0),
            ("blank",),
            ("standard",),
        ),
        (
            ("reaction", coupon_ids[1], 445.0, 0.25, 10.0),
            ("reaction", coupon_ids[2], 480.0, 0.85, 8.0),
            ("reaction", coupon_ids[3], 545.0, 0.45, 5.0),
        ),
        (
            ("reaction", coupon_ids[0], 535.0, 0.90, 6.0),
            ("blank",),
            ("standard",),
        ),
        (
            ("reaction", coupon_ids[0], 535.0, 0.90, 6.0),
            ("blank",),
            ("standard",),
        ),
    )
    request_number = 0
    for batch in batches:
        requests = []
        for item in batch:
            request_number += 1
            request = {
                "request_id": "reference-%02d" % request_number,
                "kind": item[0],
                "lab_state_version": lab_version,
            }
            if item[0] == "reaction":
                request.update({
                    "coupon_id": item[1],
                    "coupon_state_version": coupon_versions[item[1]],
                    "temperature_k": item[2],
                    "feed_concentration": item[3],
                    "duration_min": item[4],
                })
            requests.append(request)
        if first_request is None:
            first_request = copy.deepcopy(requests[0])
        response = experiment(requests)
        all_events.extend(response["events"])
        lab_version = response["lab_state_version"]
        coupon_versions = dict(response["coupon_state_versions"])

    # An exact retry has a stale scheduled parent by construction, but is served from
    # immutable cache and must not consume another physical act.
    retry = experiment([first_request])
    lab_version = retry["lab_state_version"]
    coupon_versions = dict(retry["coupon_state_versions"])

    calibration, calibration_rms = _calibration_fit(all_events)
    reactions = _corrected_reactions(all_events, calibration)
    fitted, reaction_rms = _fit_kinetics(reactions)
    scale = max(0.01, float(np.mean([abs(row["product"]) for row in reactions])))
    relative_reaction_rms = reaction_rms / scale
    repeated_products = [
        row["product"] for row in reactions
        if row["event"]["temperature_k"] == 535.0
        and row["event"]["feed_concentration"] == 0.90
        and row["event"]["duration_min"] == 6.0
    ]
    repeat_curvature = 0.0
    if len(repeated_products) == 3 and all(value > 0.0 for value in repeated_products):
        first_ratio = repeated_products[1] / repeated_products[0]
        second_ratio = repeated_products[2] / repeated_products[1]
        repeat_curvature = abs(math.log(second_ratio / first_ratio))
    # Calibration residual is on raw-signal scale. The threshold is deliberately
    # well above supported-world noise and below the planted abrupt drift.  Under
    # the declared one-site model identical successive cycles form a geometric
    # sequence; two-site deactivation creates resolvable ratio curvature.
    misspecified = bool(
        calibration_rms > 0.012
        or relative_reaction_rms > 0.018
        or repeat_curvature > 0.022
    )
    policy = _model_policy(fitted)
    return {
        "log10_preexponential": fitted["log10_a"],
        "activation_energy_kj_mol": fitted["activation"],
        "deactivation_rate_per_min": fitted["d_ref"],
        "gain_drift_per_event": float(calibration[3]),
        "offset_drift_per_event": float(calibration[1]),
        "operating_policy": policy,
        "confidence": 0.90,
        "abstain": misspecified,
        "evidence_event_ids": sorted({event["event_id"] for event in all_events}),
        "final_lab_state_version": lab_version,
        "final_coupon_state_versions": coupon_versions,
    }


def _truth_agent(problem, experiment):
    """Audit-only exact agent, installed per world by ``_evaluate_truth_world``."""
    del problem, experiment
    raise RuntimeError("truth agent requires a bound world")


def _evaluate_truth_world(spec, split="development", index=0):
    world = _make_world(spec)

    def bound(problem, experiment):
        # Exercise one blank so the artifact contains a real immutable evidence link.
        response = experiment([{
            "request_id": "truth-blank",
            "kind": "blank",
            "lab_state_version": problem["lab_state_version"],
        }])
        policy, _ = _reference_policy(world, shifted=False)
        return {
            "log10_preexponential": world["log10_a"],
            "activation_energy_kj_mol": world["activation_energy"],
            "deactivation_rate_per_min": world["d_ref"],
            "gain_drift_per_event": world["gain_drift"],
            "offset_drift_per_event": world["offset_drift"],
            "operating_policy": policy,
            "confidence": 1.0,
            "abstain": world["kind"] != "in_library",
            "evidence_event_ids": [response["events"][0]["event_id"]],
            "final_lab_state_version": response["lab_state_version"],
            "final_coupon_state_versions": response["coupon_state_versions"],
        }

    return _evaluate_world(bound, spec, split, index)
