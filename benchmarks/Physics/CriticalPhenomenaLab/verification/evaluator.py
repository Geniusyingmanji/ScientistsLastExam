"""Trusted finite-size-scaling laboratory for critical-phenomena discovery."""

from __future__ import annotations

import hashlib
import math

import numpy as np


LATTICE_SIZES = (12, 16, 24, 32, 48, 64)
TEMPERATURE_BOUNDS = (0.8, 3.8)
BUDGET_UNITS = 42
MIN_SAMPLES = 128
MAX_SAMPLES = 1024
SEALED_SIZES = (20, 40, 72)
HISTOGRAM_CENTERS = np.linspace(-1.75, -0.55, 25)

# seed, world kind, mechanism, Tc, nu, beta/nu, finite-size shift,
# scaling width, critical Binder value, latent heat
DEVELOPMENT_SPECS = (
    (52011, "supported", "continuous", 2.18, 1.0, 0.125, 0.48, 1.15, 0.610, 0.0),
    (52021, "supported", "continuous", 1.66, 5.0 / 6.0, 2.0 / 15.0, -0.35, 1.25, 0.640, 0.0),
    (52027, "supported", "continuous", 2.63, 1.0, 0.125, 0.22, 1.05, 0.606, 0.0),
    (52033, "supported", "first_order", 2.08, None, None, 4.0, 19.0, 0.0, 0.18),
    (52039, "supported", "first_order", 2.88, None, None, -3.0, 24.0, 0.0, 0.12),
    (52051, "null", "none", 2.35, None, None, 0.0, 0.48, 0.0, 0.0),
    (52057, "misspecified", "bkt", 1.92, None, None, 1.35, 0.46, 0.0, 0.0),
)

VALIDATION_SPECS = (
    (62003, "supported", "continuous", 1.48, 1.0, 0.125, -0.42, 1.30, 0.614, 0.0),
    (62011, "supported", "continuous", 2.91, 5.0 / 6.0, 2.0 / 15.0, 0.31, 1.10, 0.636, 0.0),
    (62017, "supported", "continuous", 2.36, 1.0, 0.125, 0.62, 1.20, 0.608, 0.0),
    (62029, "supported", "first_order", 1.79, None, None, 5.0, 21.0, 0.0, 0.15),
    (62039, "null", "none", 2.74, None, None, 0.0, 0.58, 0.0, 0.0),
    (62047, "misspecified", "bkt", 2.22, None, None, 1.10, 0.50, 0.0, 0.0),
)


def _world(spec):
    keys = (
        "seed", "kind", "mechanism", "tc", "nu", "beta_over_nu",
        "shift", "width", "binder_star", "latent_heat",
    )
    return dict(zip(keys, spec))


def _sigmoid(value):
    value = float(np.clip(value, -60.0, 60.0))
    return 1.0 / (1.0 + math.exp(-value))


def _normal_histogram(mean, sigma):
    sigma = max(float(sigma), 1e-4)
    values = np.exp(-0.5 * ((HISTOGRAM_CENTERS - mean) / sigma) ** 2)
    return values / np.sum(values)


def _ideal_observables(world, size, temperature):
    size = float(size)
    temperature = float(temperature)
    mechanism = world["mechanism"]

    if mechanism == "continuous":
        nu = float(world["nu"])
        beta_over_nu = float(world["beta_over_nu"])
        tc_size = world["tc"] + world["shift"] * size ** (-1.0 / nu)
        x = (temperature - tc_size) * size ** (1.0 / nu) / world["width"]
        target = 1.0 - 1.5 * world["binder_star"]
        offset = math.log(target / (1.0 - target))
        binder = (2.0 / 3.0) * (1.0 - _sigmoid(0.72 * x + offset))
        binder += 0.055 * math.sin(world["seed"] % 13) * size ** -0.8 * math.exp(-0.08 * x * x)
        beta = beta_over_nu * nu
        below = (1.0 + max(-x, 0.0)) ** beta
        above = math.exp(-0.32 * max(x, 0.0))
        magnetization = 0.82 * size ** (-beta_over_nu) * below * above
        gamma_over_nu = 2.0 - 2.0 * beta_over_nu
        susceptibility = 0.032 * size ** gamma_over_nu / (1.0 + (x / 1.75) ** 2) + 0.12
        alpha_over_nu = 0.0 if abs(nu - 1.0) < 0.05 else 0.40
        heat_peak = math.log(size) if alpha_over_nu == 0.0 else size ** alpha_over_nu
        specific_heat = 0.24 * heat_peak / (1.0 + (x / 1.9) ** 2) + 0.18
        energy_mean = -1.22 + 0.22 * math.tanh(x / 3.2)
        histogram = _normal_histogram(energy_mean, 0.055 + 0.65 / size)

    elif mechanism == "first_order":
        tc_size = world["tc"] + world["shift"] * size ** -2.0
        x = (temperature - tc_size) * size**2 / world["width"]
        ordered_weight = 1.0 - _sigmoid(x)
        magnetization_jump = 0.66
        m2 = ordered_weight * magnetization_jump**2 + (1.0 - ordered_weight) * (0.9 / size) ** 2
        m4 = ordered_weight * magnetization_jump**4 + (1.0 - ordered_weight) * 3.0 * (0.9 / size) ** 4
        binder = 1.0 - m4 / max(3.0 * m2 * m2, 1e-12)
        magnetization = ordered_weight * magnetization_jump + (1.0 - ordered_weight) * 0.9 / size
        susceptibility = 0.010 * size**2 * ordered_weight * (1.0 - ordered_weight) + 0.10
        latent = world["latent_heat"]
        energy_ordered = -1.20 - 0.5 * latent
        energy_disordered = -1.20 + 0.5 * latent
        energy_mean = ordered_weight * energy_ordered + (1.0 - ordered_weight) * energy_disordered
        variance = ordered_weight * (1.0 - ordered_weight) * latent**2 + (0.035 + 0.5 / size) ** 2
        specific_heat = 0.22 * size**2 * variance / max(temperature * temperature, 0.2)
        histogram = (
            ordered_weight * _normal_histogram(energy_ordered, 0.030 + 0.40 / size)
            + (1.0 - ordered_weight) * _normal_histogram(energy_disordered, 0.030 + 0.40 / size)
        )
        histogram /= np.sum(histogram)

    elif mechanism == "none":
        x = (temperature - world["tc"]) / world["width"]
        smooth = _sigmoid(x)
        finite_correction = 0.035 / math.sqrt(size)
        binder = 0.53 * (1.0 - smooth) + finite_correction
        magnetization = 0.72 * (1.0 - smooth) + 0.8 / size
        susceptibility = 0.45 + 1.20 * math.exp(-0.5 * x * x) + 0.3 / math.sqrt(size)
        specific_heat = 0.35 + 0.85 * math.exp(-0.35 * x * x) + 0.2 / math.sqrt(size)
        energy_mean = -1.18 + 0.20 * math.tanh(x / 1.8)
        histogram = _normal_histogram(energy_mean, 0.060 + 0.5 / size)

    else:  # BKT-like essential scaling, intentionally outside the public power-law family.
        log_size = math.log(size)
        tc_size = world["tc"] + world["shift"] / (log_size + 0.7) ** 2
        x = (temperature - tc_size) * (log_size + 0.7) ** 2 / world["width"]
        smooth = _sigmoid(0.7 * x)
        eta = 0.20 + 0.12 * _sigmoid((temperature - world["tc"]) / 0.12)
        binder = 0.57 * (1.0 - 0.82 * smooth) + 0.025 / log_size
        magnetization = 0.88 * size ** (-0.5 * eta) * math.exp(-0.14 * max(x, 0.0))
        susceptibility = 0.024 * size ** (2.0 - eta) / (1.0 + (x / 2.0) ** 2) + 0.15
        specific_heat = 0.42 + 0.75 * math.exp(-0.22 * x * x)
        energy_mean = -1.16 + 0.16 * math.tanh(x / 2.7)
        histogram = _normal_histogram(energy_mean, 0.055 + 0.55 / size)

    return {
        "abs_magnetization": max(0.0, float(magnetization)),
        "binder_cumulant": float(np.clip(binder, -1.5, 2.0 / 3.0)),
        "susceptibility": max(0.0, float(susceptibility)),
        "specific_heat": max(0.0, float(specific_heat)),
        "energy_mean": float(energy_mean),
        "histogram": np.asarray(histogram, dtype=float),
    }


def _query_seed(world_seed, call_index, size, temperature, samples):
    payload = ("%d|%.12g|%d" % (size, temperature, samples)).encode("ascii")
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4")
    sequence = np.random.SeedSequence(
        [int(world_seed), int(call_index), *[int(value) for value in words]]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.query_ids = []

    def experiment(self, lattice_size, temperature, samples):
        if isinstance(lattice_size, bool) or int(lattice_size) != lattice_size:
            raise ValueError("lattice_size must be an allowed integer")
        size = int(lattice_size)
        if size not in LATTICE_SIZES:
            raise ValueError("lattice_size is not in lattice_sizes")
        temperature = float(temperature)
        if not math.isfinite(temperature) or not TEMPERATURE_BOUNDS[0] <= temperature <= TEMPERATURE_BOUNDS[1]:
            raise ValueError("temperature outside temperature_bounds")
        if isinstance(samples, bool) or int(samples) != samples:
            raise ValueError("samples must be an integer")
        samples = int(samples)
        if not MIN_SAMPLES <= samples <= MAX_SAMPLES:
            raise ValueError("samples outside [128,1024]")
        cost = int(math.ceil(samples / 256.0) * math.ceil(size / 24.0))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("experimental budget exceeded")
        self.used += cost
        self.calls += 1
        ideal = _ideal_observables(self.world, size, temperature)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, size, temperature, samples
        ))
        scale = math.sqrt(256.0 / samples)
        standard_errors = {
            "abs_magnetization": 0.008 * scale,
            "binder_cumulant": 0.006 * scale,
            "susceptibility": max(0.010, 0.030 * ideal["susceptibility"]) * scale,
            "specific_heat": max(0.008, 0.030 * ideal["specific_heat"]) * scale,
            "energy_mean": 0.0030 * scale,
        }
        observed = {}
        for name in (
            "abs_magnetization", "binder_cumulant", "susceptibility",
            "specific_heat", "energy_mean",
        ):
            observed[name] = ideal[name] + rng.normal(scale=standard_errors[name])
        observed["abs_magnetization"] = max(0.0, observed["abs_magnetization"])
        observed["susceptibility"] = max(0.0, observed["susceptibility"])
        observed["specific_heat"] = max(0.0, observed["specific_heat"])
        observed["binder_cumulant"] = float(np.clip(observed["binder_cumulant"], -1.5, 2.0 / 3.0))
        counts = rng.multinomial(samples, ideal["histogram"])
        histogram = counts.astype(float) / max(1, int(np.sum(counts)))
        token = hashlib.sha256(
            ("%d|%d|%.12g|%d|%d" % (
                self.world["seed"], size, temperature, samples, self.calls
            )).encode("ascii")
        ).hexdigest()[:12]
        query_id = "obs-%02d-%s" % (self.calls, token)
        self.query_ids.append(query_id)
        return {
            "query_id": query_id,
            "lattice_size": size,
            "temperature": temperature,
            "samples": samples,
            "abs_magnetization": float(observed["abs_magnetization"]),
            "binder_cumulant": float(observed["binder_cumulant"]),
            "susceptibility": float(observed["susceptibility"]),
            "specific_heat": float(observed["specific_heat"]),
            "energy_mean": float(observed["energy_mean"]),
            "energy_histogram_centers": HISTOGRAM_CENTERS.copy(),
            "energy_histogram_density": histogram,
            "standard_errors": standard_errors,
            "budget_cost": cost,
            "budget_used": self.used,
        }


def _finite(value, name):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("%s must be finite" % name)
    return value


def _validate_submission(submission, laboratory):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dict")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = _finite(submission.get("confidence", 0.5), "confidence")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if abstain:
        return {
            "abstain": True, "confidence": confidence, "transition_type": None,
            "tc": None, "nu": None, "beta_over_nu": None, "shift": None,
        }
    transition_type = submission.get("transition_type")
    if transition_type not in {"continuous", "first_order"}:
        raise ValueError("transition_type must be continuous or first_order")
    tc = _finite(submission.get("critical_temperature"), "critical_temperature")
    if not TEMPERATURE_BOUNDS[0] <= tc <= TEMPERATURE_BOUNDS[1]:
        raise ValueError("critical_temperature outside temperature_bounds")
    shift = _finite(submission.get("finite_size_shift"), "finite_size_shift")
    if not -12.0 <= shift <= 12.0:
        raise ValueError("finite_size_shift outside [-12,12]")
    nu = None
    beta_over_nu = None
    if transition_type == "continuous":
        nu = _finite(submission.get("nu"), "nu")
        beta_over_nu = _finite(submission.get("beta_over_nu"), "beta_over_nu")
        if not 0.3 <= nu <= 3.0:
            raise ValueError("nu outside [0.3,3.0]")
        if not 0.02 <= beta_over_nu <= 0.5:
            raise ValueError("beta_over_nu outside [0.02,0.5]")
    evidence = submission.get("evidence_query_ids")
    if not isinstance(evidence, (list, tuple)) or len(evidence) < 2:
        raise ValueError("a claim must cite at least two evidence_query_ids")
    if any(not isinstance(value, str) for value in evidence):
        raise ValueError("evidence_query_ids must contain strings")
    if len(set(evidence)) != len(evidence):
        raise ValueError("evidence_query_ids must be unique")
    if not set(evidence).issubset(set(laboratory.query_ids)):
        raise ValueError("evidence_query_ids must come from this laboratory")
    return {
        "abstain": False, "confidence": confidence,
        "transition_type": transition_type, "tc": tc, "nu": nu,
        "beta_over_nu": beta_over_nu, "shift": shift,
    }


def _credit(error, tolerance):
    return float(np.clip(1.0 - abs(float(error)) / float(tolerance), 0.0, 1.0))


def _mechanism_metrics(world, claim):
    if world["kind"] != "supported":
        correct = bool(claim["abstain"])
        return {
            "mechanism_score": 1.0 if correct else 0.0,
            "transition_type_score": 1.0 if correct else 0.0,
            "critical_temperature_score": 1.0 if correct else 0.0,
            "exponent_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        }
    if claim["abstain"]:
        return {
            "mechanism_score": 0.0,
            "transition_type_score": 0.0,
            "critical_temperature_score": 0.0,
            "exponent_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
        }
    type_score = float(claim["transition_type"] == world["mechanism"])
    tc_score = _credit(claim["tc"] - world["tc"], 0.35)
    shift_tolerance = 2.5 if world["mechanism"] == "first_order" else 0.9
    shift_score = _credit(claim["shift"] - world["shift"], shift_tolerance)
    if world["mechanism"] == "continuous":
        nu_score = 0.0 if claim["nu"] is None else _credit(claim["nu"] - world["nu"], 0.50)
        beta_score = (
            0.0 if claim["beta_over_nu"] is None
            else _credit(claim["beta_over_nu"] - world["beta_over_nu"], 0.12)
        )
        exponent_score = 0.60 * nu_score + 0.40 * beta_score
        mechanism_score = (
            0.30 * type_score + 0.25 * tc_score + 0.20 * nu_score
            + 0.15 * beta_score + 0.10 * shift_score
        )
    else:
        exponent_score = 1.0 if type_score else 0.0
        mechanism_score = 0.45 * type_score + 0.35 * tc_score + 0.20 * shift_score
    return {
        "mechanism_score": float(mechanism_score),
        "transition_type_score": type_score,
        "critical_temperature_score": tc_score,
        "exponent_score": float(exponent_score),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _finite_size_prediction_score(world, claim):
    if world["kind"] != "supported":
        return None
    if claim["abstain"] or claim["transition_type"] != world["mechanism"]:
        return 0.0
    if world["mechanism"] == "continuous":
        if claim["nu"] is None:
            return 0.0
        true_power = 1.0 / world["nu"]
        predicted_power = 1.0 / claim["nu"]
        tolerance = 0.12
    else:
        true_power = 2.0
        predicted_power = 2.0
        tolerance = 0.08
    credits = []
    for size in SEALED_SIZES:
        truth = world["tc"] + world["shift"] * size ** (-true_power)
        prediction = claim["tc"] + claim["shift"] * size ** (-predicted_power)
        credits.append(_credit(prediction - truth, tolerance))
    return float(np.mean(credits))


def _evaluate_world(candidate, spec, split, index):
    world = _world(spec)
    laboratory = _Laboratory(world)
    try:
        submission = candidate(
            LATTICE_SIZES, TEMPERATURE_BOUNDS, laboratory.experiment, BUDGET_UNITS
        )
        claim = _validate_submission(submission, laboratory)
        if laboratory.violated:
            raise RuntimeError("experimental budget exceeded")
        mechanism = _mechanism_metrics(world, claim)
        prediction = _finite_size_prediction_score(world, claim)
        return {
            "split": split,
            "world_index": int(index),
            "world_kind": world["kind"],
            "valid": True,
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "transition_type_score": round(mechanism["transition_type_score"], 6),
            "critical_temperature_score": round(mechanism["critical_temperature_score"], 6),
            "exponent_score": round(mechanism["exponent_score"], 6),
            "finite_size_prediction_score": (
                None if prediction is None else round(prediction, 6)
            ),
            "correct_refusal": bool(mechanism["correct_refusal"]),
            "false_discovery": bool(mechanism["false_discovery"]),
            "abstained": bool(claim["abstain"]),
            "confidence": round(claim["confidence"], 6),
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }
    except Exception as exc:
        return {
            "split": split,
            "world_index": int(index),
            "world_kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "mechanism_score": 0.0,
            "transition_type_score": 0.0,
            "critical_temperature_score": 0.0,
            "exponent_score": 0.0,
            "finite_size_prediction_score": 0.0 if world["kind"] == "supported" else None,
            "correct_refusal": False,
            "false_discovery": False,
            "abstained": False,
            "confidence": 0.0,
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }


def _split_metrics(records, unsupported_count):
    raw_mechanism = float(np.mean([row["mechanism_score"] for row in records]))
    abstention_baseline = unsupported_count / len(records)
    normalized = float(np.clip(
        (raw_mechanism - abstention_baseline) / (1.0 - abstention_baseline),
        0.0, 1.0,
    ))
    supported = [row for row in records if row["world_kind"] == "supported"]
    unsupported = [row for row in records if row["world_kind"] != "supported"]
    predictions = [row["finite_size_prediction_score"] for row in supported]
    false_discoveries = sum(bool(row["false_discovery"]) for row in unsupported)
    correct_refusals = sum(bool(row["correct_refusal"]) for row in unsupported)
    attempts = sum(not bool(row["abstained"]) for row in supported)
    return {
        "normalized": normalized,
        "raw_mechanism": raw_mechanism,
        "finite_size_prediction": float(np.mean(predictions)),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "false_discoveries": false_discoveries,
        "correct_refusals": correct_refusals,
        "unsupported_count": len(unsupported),
        "supported_count": len(supported),
        "attempts": attempts,
        "false_discovery_rate": false_discoveries / max(1, len(unsupported)),
        "correct_refusal_rate": correct_refusals / max(1, len(unsupported)),
        "discovery_coverage": attempts / max(1, len(supported)),
    }


def _evaluate_specs(candidate, specs, split, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(candidate, "reset_session"):
            candidate.reset_session()
        records.append(_evaluate_world(candidate, spec, split, index))
    return records


def evaluate(candidate):
    development = _evaluate_specs(candidate, DEVELOPMENT_SPECS, "development")
    validation = _evaluate_specs(candidate, VALIDATION_SPECS, "validation", True)
    dev = _split_metrics(
        development, sum(spec[1] != "supported" for spec in DEVELOPMENT_SPECS)
    )
    val = _split_metrics(
        validation, sum(spec[1] != "supported" for spec in VALIDATION_SPECS)
    )
    all_records = development + validation
    return {
        "combined_score": dev["normalized"],
        "valid": 1.0 if dev["valid_count"] == len(development) else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "finite_size_prediction_score": dev["finite_size_prediction"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_false_discoveries": dev["false_discoveries"],
        "development_false_discovery_denominator": dev["unsupported_count"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_correct_refusals": dev["correct_refusals"],
        "development_refusal_denominator": dev["unsupported_count"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_discovery_attempts": dev["attempts"],
        "development_supported_worlds": dev["supported_count"],
        "robustness_score": val["normalized"],
        "validation_finite_size_prediction_score": val["finite_size_prediction"],
        "validation_feasibility_rate": val["valid_count"] / len(validation),
        "validation_false_discovery_rate": val["false_discovery_rate"],
        "validation_false_discoveries": val["false_discoveries"],
        "validation_false_discovery_denominator": val["unsupported_count"],
        "validation_correct_refusal_rate": val["correct_refusal_rate"],
        "validation_correct_refusals": val["correct_refusals"],
        "validation_refusal_denominator": val["unsupported_count"],
        "validation_discovery_coverage": val["discovery_coverage"],
        "validation_discovery_attempts": val["attempts"],
        "validation_supported_worlds": val["supported_count"],
        "mean_experiment_calls": float(np.mean([row["experiment_calls"] for row in all_records])),
        "mean_experiment_budget_units": float(np.mean([
            row["experiment_budget_units"] for row in all_records
        ])),
        "per_world": all_records,
    }


def reference_anchor():
    """Recompute the exact-descriptor upper anchor from the frozen world panel."""
    def score(specs):
        rows = []
        for spec in specs:
            world = _world(spec)
            if world["kind"] == "supported":
                claim = {
                    "abstain": False,
                    "transition_type": world["mechanism"],
                    "tc": world["tc"],
                    "nu": world["nu"],
                    "beta_over_nu": world["beta_over_nu"],
                    "shift": world["shift"],
                }
            else:
                claim = {
                    "abstain": True, "transition_type": None, "tc": None,
                    "nu": None, "beta_over_nu": None, "shift": None,
                }
            rows.append(_mechanism_metrics(world, claim)["mechanism_score"])
        unsupported = sum(spec[1] != "supported" for spec in specs)
        raw = float(np.mean(rows))
        baseline = unsupported / len(specs)
        return float((raw - baseline) / (1.0 - baseline))
    return {
        "development_score": score(DEVELOPMENT_SPECS),
        "validation_score": score(VALIDATION_SPECS),
    }
