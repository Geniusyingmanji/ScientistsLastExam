"""Trusted oracle for active two-layer climate-response identification, version 2.

Candidates design bounded radiative-forcing experiments and either identify a
public two-layer energy-balance model or abstain when that model family is not
supported.  Parameter recovery, sealed forcing transfer, refusal and held-out
worlds remain separate evaluator outputs.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.linalg import expm


CLIMATE_V2 = True

PARAMETER_NAMES = (
    "feedback_w_m2_k",
    "surface_capacity_w_yr_m2_k",
    "deep_capacity_w_yr_m2_k",
    "ocean_exchange_w_m2_k",
    "forcing_scale",
)
PARAMETER_BOUNDS = np.asarray((
    (0.80, 2.20),
    (6.0, 15.0),
    (70.0, 180.0),
    (0.35, 1.20),
    (0.85, 1.15),
), dtype=float)
PARAMETER_TOLERANCES = np.asarray((0.03, 0.30, 3.0, 0.02, 0.006))

EXPERIMENT_BUDGET_UNITS = 8
MIN_EXPERIMENT_YEARS = 12
MAX_EXPERIMENT_YEARS = 160
YEARS_PER_BUDGET_UNIT = 20
FORCING_MIN_W_M2 = -1.0
FORCING_MAX_W_M2 = 8.0
SURFACE_NOISE_STD_K = 0.060
TOA_NOISE_STD_W_M2 = 0.140

DEVELOPMENT_SPECS = (
    (4101, "in_library"),
    (4102, "in_library"),
    (4103, "in_library"),
    (4104, "in_library"),
    (4105, "null"),
    (4106, "feedback_drift"),
)
HELDOUT_SPECS = (
    (5101, "in_library"),
    (5102, "in_library"),
    (5103, "in_library"),
    (5104, "null"),
    (5105, "three_layer"),
)


def _parameters(seed):
    rng = np.random.default_rng(int(seed))
    unit = rng.uniform(0.12, 0.88, size=len(PARAMETER_NAMES))
    return PARAMETER_BOUNDS[:, 0] + unit * (
        PARAMETER_BOUNDS[:, 1] - PARAMETER_BOUNDS[:, 0]
    )


def _world(spec):
    seed, kind = int(spec[0]), str(spec[1])
    rng = np.random.default_rng(seed + 97)
    world = {
        "seed": seed,
        "kind": kind,
        "parameters": _parameters(seed),
        "surface_noise_std_k": SURFACE_NOISE_STD_K,
        "toa_noise_std_w_m2": TOA_NOISE_STD_W_M2,
    }
    if kind == "feedback_drift":
        # The synthetic curvature is deliberately resolvable within the public
        # 160-year window under a well-designed high-amplitude forcing experiment.
        world["feedback_curvature_w_m2_k2"] = float(rng.uniform(0.30, 0.45))
    elif kind == "three_layer":
        # Likewise, the extra slow reservoir is stronger than a literal abyssal
        # calibration so structural mismatch is testable on benchmark time scales.
        world["abyss_capacity_w_yr_m2_k"] = float(rng.uniform(300.0, 450.0))
        world["abyss_exchange_w_m2_k"] = float(rng.uniform(1.00, 1.30))
    return world


def _public_transition(parameters):
    feedback, surface_capacity, deep_capacity, exchange, forcing_scale = map(
        float, parameters
    )
    matrix = np.asarray((
        (-(feedback + exchange) / surface_capacity, exchange / surface_capacity),
        (exchange / deep_capacity, -exchange / deep_capacity),
    ))
    forcing = np.asarray((forcing_scale / surface_capacity, 0.0))
    augmented = np.zeros((3, 3), dtype=float)
    augmented[:2, :2] = matrix
    augmented[:2, 2] = forcing
    transition = expm(augmented)
    return transition[:2, :2], transition[:2, 2]


def simulate_public(parameters, forcing_w_m2):
    """Simulate the documented annual piecewise-constant two-layer model."""
    parameters = np.asarray(parameters, dtype=float)
    forcing_w_m2 = np.asarray(forcing_w_m2, dtype=float).ravel()
    transition, response = _public_transition(parameters)
    state = np.zeros(2, dtype=float)
    surface = np.empty(len(forcing_w_m2), dtype=float)
    deep = np.empty(len(forcing_w_m2), dtype=float)
    feedback, _, _, _, forcing_scale = parameters
    imbalance = np.empty(len(forcing_w_m2), dtype=float)
    for index, value in enumerate(forcing_w_m2):
        state = transition @ state + response * float(value)
        surface[index], deep[index] = state
        imbalance[index] = forcing_scale * float(value) - feedback * state[0]
    return surface, deep, imbalance


def _simulate_feedback_drift(world, forcing_w_m2):
    parameters = np.asarray(world["parameters"], dtype=float)
    feedback, surface_capacity, deep_capacity, exchange, forcing_scale = parameters
    curvature = float(world["feedback_curvature_w_m2_k2"])
    state = np.zeros(2, dtype=float)
    surface = np.empty(len(forcing_w_m2), dtype=float)
    deep = np.empty(len(forcing_w_m2), dtype=float)
    imbalance = np.empty(len(forcing_w_m2), dtype=float)

    def derivative(value, forcing):
        surface_value, deep_value = value
        radiative = (
            forcing_scale * forcing
            - feedback * surface_value
            - curvature * surface_value * surface_value
        )
        return np.asarray((
            (radiative - exchange * (surface_value - deep_value))
            / surface_capacity,
            exchange * (surface_value - deep_value) / deep_capacity,
        ))

    for index, forcing in enumerate(np.asarray(forcing_w_m2, dtype=float)):
        step = 0.1
        for _ in range(10):
            k1 = derivative(state, forcing)
            k2 = derivative(state + 0.5 * step * k1, forcing)
            k3 = derivative(state + 0.5 * step * k2, forcing)
            k4 = derivative(state + step * k3, forcing)
            state = state + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
        surface[index], deep[index] = state
        imbalance[index] = (
            forcing_scale * forcing - feedback * state[0]
            - curvature * state[0] * state[0]
        )
    return surface, deep, imbalance


def _simulate_three_layer(world, forcing_w_m2):
    parameters = np.asarray(world["parameters"], dtype=float)
    feedback, surface_capacity, deep_capacity, exchange, forcing_scale = parameters
    abyss_capacity = float(world["abyss_capacity_w_yr_m2_k"])
    abyss_exchange = float(world["abyss_exchange_w_m2_k"])
    matrix = np.asarray((
        (-(feedback + exchange) / surface_capacity, exchange / surface_capacity, 0.0),
        (exchange / deep_capacity,
         -(exchange + abyss_exchange) / deep_capacity,
         abyss_exchange / deep_capacity),
        (0.0, abyss_exchange / abyss_capacity, -abyss_exchange / abyss_capacity),
    ))
    forcing_vector = np.asarray((forcing_scale / surface_capacity, 0.0, 0.0))
    augmented = np.zeros((4, 4), dtype=float)
    augmented[:3, :3] = matrix
    augmented[:3, 3] = forcing_vector
    transition = expm(augmented)
    state = np.zeros(3, dtype=float)
    surface = np.empty(len(forcing_w_m2), dtype=float)
    deep = np.empty(len(forcing_w_m2), dtype=float)
    imbalance = np.empty(len(forcing_w_m2), dtype=float)
    for index, forcing in enumerate(np.asarray(forcing_w_m2, dtype=float)):
        state = transition[:3, :3] @ state + transition[:3, 3] * forcing
        surface[index], deep[index] = state[:2]
        imbalance[index] = forcing_scale * forcing - feedback * state[0]
    return surface, deep, imbalance


def _clean_response(world, forcing_w_m2):
    kind = world["kind"]
    forcing_w_m2 = np.asarray(forcing_w_m2, dtype=float)
    if kind == "null":
        zeros = np.zeros(len(forcing_w_m2), dtype=float)
        return zeros.copy(), zeros.copy(), zeros.copy()
    if kind == "feedback_drift":
        return _simulate_feedback_drift(world, forcing_w_m2)
    if kind == "three_layer":
        return _simulate_three_layer(world, forcing_w_m2)
    return simulate_public(world["parameters"], forcing_w_m2)


class _ClimateLaboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.failure = None

    def observe(self, forcing_w_m2):
        try:
            forcing = np.asarray(forcing_w_m2, dtype=float)
        except Exception as exc:
            self.failure = "forcing must be numeric"
            raise ValueError(self.failure) from exc
        if forcing.ndim != 1:
            self.failure = "forcing must be one-dimensional"
            raise ValueError(self.failure)
        if not MIN_EXPERIMENT_YEARS <= len(forcing) <= MAX_EXPERIMENT_YEARS:
            self.failure = "forcing duration is outside the public range"
            raise ValueError(self.failure)
        if not np.all(np.isfinite(forcing)):
            self.failure = "forcing must be finite"
            raise ValueError(self.failure)
        if (
            float(np.min(forcing)) < FORCING_MIN_W_M2
            or float(np.max(forcing)) > FORCING_MAX_W_M2
        ):
            self.failure = "forcing amplitude is outside the public range"
            raise ValueError(self.failure)
        cost = int(math.ceil(len(forcing) / YEARS_PER_BUDGET_UNIT))
        if self.used + cost > EXPERIMENT_BUDGET_UNITS:
            self.failure = "experiment budget exceeded"
            raise ValueError(self.failure)
        self.used += cost
        surface, _deep, imbalance = _clean_response(self.world, forcing)
        digest = hashlib.sha256(forcing.astype("<f8", copy=False).tobytes()).digest()
        query_seed = int.from_bytes(digest[:4], "little")
        rng = np.random.default_rng(
            int(self.world["seed"]) * 100003 + self.calls * 7919 + query_seed
        )
        self.calls += 1
        observed_surface = surface + rng.normal(
            0.0, SURFACE_NOISE_STD_K, size=len(surface)
        )
        observed_imbalance = imbalance + rng.normal(
            0.0, TOA_NOISE_STD_W_M2, size=len(imbalance)
        )
        return {
            "time_years": np.arange(1, len(forcing) + 1, dtype=float),
            "forcing_w_m2": forcing.copy(),
            "surface_temperature_anomaly_k": observed_surface,
            "toa_imbalance_w_m2": observed_imbalance,
            "surface_noise_std_k": SURFACE_NOISE_STD_K,
            "toa_noise_std_w_m2": TOA_NOISE_STD_W_M2,
            "budget_cost": cost,
            "budget_used": self.used,
        }


def _validate_submission(returned):
    if not isinstance(returned, dict):
        raise ValueError("submission must be a dictionary")
    parameters = np.asarray(returned.get("parameters"), dtype=float).ravel()
    if parameters.shape != (len(PARAMETER_NAMES),):
        raise ValueError("parameters must contain five values")
    if not np.all(np.isfinite(parameters)):
        raise ValueError("parameters must be finite")
    confidence = float(returned.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    abstain = returned.get("abstain", False)
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    if not abstain and (
        np.any(parameters < PARAMETER_BOUNDS[:, 0])
        or np.any(parameters > PARAMETER_BOUNDS[:, 1])
    ):
        raise ValueError("claimed public-model parameters are out of bounds")
    if abstain and float(np.max(np.abs(parameters))) > 1.0e6:
        raise ValueError("abstention parameters exceed finite safety bounds")
    return parameters, confidence, bool(abstain)


def _forcing_suites():
    nominal_one = np.concatenate((
        np.zeros(8), np.full(72, 4.0), np.zeros(40),
    ))
    nominal_two = np.linspace(0.0, 6.0, 120)
    shift_one = np.concatenate((
        np.full(20, -0.8), np.full(35, 7.0), np.zeros(65),
    ))
    time = np.arange(120, dtype=float)
    shift_two = 2.5 + 2.2 * np.sin(2.0 * np.pi * time / 37.0)
    return (nominal_one, nominal_two), (shift_one, shift_two)


def _prediction_score(world, parameters, shifted=False):
    nominal, shifts = _forcing_suites()
    forcings = shifts if shifted else nominal
    scores = []
    for forcing in forcings:
        actual_surface, _deep, actual_imbalance = _clean_response(world, forcing)
        predicted_surface, _predicted_deep, predicted_imbalance = simulate_public(
            parameters, forcing
        )
        surface_scale = max(0.08, 0.08 * math.sqrt(float(np.mean(
            actual_surface * actual_surface
        ))))
        imbalance_scale = max(0.15, 0.08 * math.sqrt(float(np.mean(
            actual_imbalance * actual_imbalance
        ))))
        surface_error = math.sqrt(float(np.mean(
            (predicted_surface - actual_surface) ** 2
        ))) / surface_scale
        imbalance_error = math.sqrt(float(np.mean(
            (predicted_imbalance - actual_imbalance) ** 2
        ))) / imbalance_scale
        scores.append(math.exp(-0.5 * (
            0.65 * surface_error * surface_error
            + 0.35 * imbalance_error * imbalance_error
        )))
    return float(np.mean(scores))


def _mechanism_score(parameters, truth):
    scaled = (np.asarray(parameters) - np.asarray(truth)) / PARAMETER_TOLERANCES
    return float(math.exp(-0.5 * float(np.mean(scaled * scaled))))


def _public_failure_kind(stage, laboratory):
    """Return a finite label-blind public failure category."""
    if laboratory.failure is not None:
        return "invalid_experiment_request"
    if stage == "submission_validation":
        return "invalid_return_artifact"
    if stage == "candidate_execution":
        return "candidate_runtime_or_callback_processing_error"
    return "trusted_evaluator_internal_error"


def _invalid_record(split, index, kind, failure_kind):
    return {
        "split": split,
        "world_index": int(index),
        "valid": False,
        "reason": str(failure_kind),
        "failure_kind": str(failure_kind),
        "kind": str(kind),
        "claimed_public_model": False,
        "abstain": False,
        "confidence": 0.0,
        "budget_used": 0,
        "experiment_calls": 0,
        "mechanism_quality": 0.0,
        "parameter_quality": 0.0,
        "nominal_prediction_quality": 0.0,
        "forcing_shift_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "supported_claim": False,
        "confidence_score": 0.0,
    }


def _evaluate_world(identify_climate_response, spec, split, index):
    world = _world(spec)
    laboratory = _ClimateLaboratory(world)
    stage = "candidate_execution"
    try:
        returned = identify_climate_response(
            tuple(PARAMETER_NAMES), PARAMETER_BOUNDS.copy(), laboratory.observe,
            EXPERIMENT_BUDGET_UNITS,
        )
        if laboratory.failure is not None:
            raise ValueError(laboratory.failure)
        stage = "submission_validation"
        parameters, confidence, abstain = _validate_submission(returned)
        stage = "trusted_scoring"
    except Exception:
        return _invalid_record(
            split, index, world["kind"],
            _public_failure_kind(stage, laboratory),
        )

    supported = world["kind"] == "in_library"
    claimed = not abstain
    correct_refusal = bool(not supported and abstain)
    false_discovery = bool(not supported and claimed)
    supported_claim = bool(supported and claimed)
    if supported_claim:
        parameter_quality = _mechanism_score(parameters, world["parameters"])
        nominal_prediction = _prediction_score(world, parameters, shifted=False)
        forcing_shift = _prediction_score(world, parameters, shifted=True)
        mechanism_quality = math.sqrt(parameter_quality * nominal_prediction)
        forcing_shift_quality = math.sqrt(parameter_quality * forcing_shift)
    elif correct_refusal:
        parameter_quality = 1.0
        nominal_prediction = 1.0
        forcing_shift = 1.0
        mechanism_quality = 1.0
        forcing_shift_quality = 1.0
    else:
        parameter_quality = 0.0
        mechanism_quality = 0.0
        forcing_shift_quality = 0.0
        if claimed:
            nominal_prediction = _prediction_score(world, parameters, shifted=False)
            forcing_shift = _prediction_score(world, parameters, shifted=True)
        else:
            nominal_prediction = 0.0
            forcing_shift = 0.0
    # Confidence is calibrated to the quality of the returned scientific claim,
    # not merely to the binary decision to claim or refuse.  A correct refusal has
    # unit mechanism quality; an inaccurate supported claim has a softer target.
    confidence_score = 1.0 - (confidence - mechanism_quality) ** 2
    return {
        "split": split,
        "world_index": int(index),
        "valid": True,
        "kind": str(world["kind"]),
        "claimed_public_model": claimed,
        "abstain": abstain,
        "confidence": confidence,
        "budget_used": int(laboratory.used),
        "experiment_calls": int(laboratory.calls),
        "mechanism_quality": float(mechanism_quality),
        "parameter_quality": float(parameter_quality),
        "nominal_prediction_quality": float(nominal_prediction),
        "forcing_shift_quality": float(forcing_shift_quality),
        "claimed_model_nominal_fit": float(nominal_prediction),
        "claimed_model_shift_fit": float(forcing_shift),
        "correct_refusal": correct_refusal,
        "false_discovery": false_discovery,
        "supported_claim": supported_claim,
        "confidence_score": float(confidence_score),
        "parameter_absolute_errors": (
            np.abs(parameters - world["parameters"]).tolist()
            if supported_claim else None
        ),
    }


def _normalized_mean(records, field):
    unsupported = sum(
        spec[1] != "in_library"
        for spec in (
            DEVELOPMENT_SPECS if records[0]["split"] == "development"
            else HELDOUT_SPECS
        )
    )
    baseline = unsupported / len(records)
    raw = float(np.mean([float(row[field]) for row in records]))
    return float(np.clip((raw - baseline) / max(1.0e-12, 1.0 - baseline), 0.0, 1.0))


def _split_metrics(records):
    supported_count = sum(
        spec[1] == "in_library"
        for spec in (
            DEVELOPMENT_SPECS if records[0]["split"] == "development"
            else HELDOUT_SPECS
        )
    )
    claims = sum(bool(row["claimed_public_model"]) for row in records)
    supported_claims = sum(bool(row["supported_claim"]) for row in records)
    false_discoveries = sum(bool(row["false_discovery"]) for row in records)
    unsupported_count = len(records) - supported_count
    return {
        "mechanism_score": _normalized_mean(records, "mechanism_quality"),
        "prediction_score": _normalized_mean(records, "nominal_prediction_quality"),
        "forcing_shift_score": _normalized_mean(records, "forcing_shift_quality"),
        "artifact_valid_rate": float(np.mean([row["valid"] for row in records])),
        "supported_claim_coverage": supported_claims / supported_count,
        "false_discovery_rate": false_discoveries / max(claims, 1),
        "unsupported_refusal_rate": sum(
            bool(row["correct_refusal"]) for row in records
        ) / unsupported_count,
        "mean_confidence_score": float(np.mean([
            row["confidence_score"] for row in records
        ])),
        "mean_budget_used": float(np.mean([
            row["budget_used"] for row in records
        ])),
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in records
        ])),
    }


def evaluate(identify_climate_response):
    development = []
    heldout = []
    all_specs = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(all_specs):
        if call_index and hasattr(identify_climate_response, "reset_session"):
            identify_climate_response.reset_session()
        record = _evaluate_world(
            identify_climate_response, spec, split, index
        )
        (development if split == "development" else heldout).append(record)
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    result = {
        "combined_score": dev["mechanism_score"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["artifact_valid_rate"],
        "raw_score": dev["mechanism_score"] if development_valid else 0.0,
        "development_mechanism_score": dev["mechanism_score"],
        "robustness_score": dev["forcing_shift_score"],
        "development_validation_gap": (
            dev["mechanism_score"] - dev["forcing_shift_score"]
        ),
        "heldout_policy_score": held["mechanism_score"] if heldout_valid else 0.0,
        "heldout_robustness_score": (
            held["forcing_shift_score"] if heldout_valid else 0.0
        ),
        "development_prediction_score": dev["prediction_score"],
        "heldout_prediction_score": held["prediction_score"],
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_unsupported_refusal_rate": dev["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_confidence_score": dev["mean_confidence_score"],
        "heldout_confidence_score": held["mean_confidence_score"],
        "development_mean_budget_used": dev["mean_budget_used"],
        "heldout_mean_budget_used": held["mean_budget_used"],
        "development_mean_experiment_calls": dev["mean_experiment_calls"],
        "heldout_mean_experiment_calls": held["mean_experiment_calls"],
        "heldout_feasibility_rate": held["artifact_valid_rate"],
        "per_world": development + heldout,
        "candidate_world_call_count": len(all_specs),
        "candidate_world_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
    }
    if not development_valid:
        failure_kinds = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(
            failure_kinds
        )
    return result


def _reference_submission(world):
    if world["kind"] == "in_library":
        return {
            "parameters": world["parameters"].copy(),
            "confidence": 1.0,
            "abstain": False,
        }
    return {
        "parameters": np.zeros(len(PARAMETER_NAMES)),
        "confidence": 1.0,
        "abstain": True,
    }
