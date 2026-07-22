"""Active thermal-infrared sounding and atmospheric-mechanism retrieval.

Candidates choose public spectral channels and viewing geometries under a charged
measurement budget.  They return four temperature-anomaly knot values, one optical-depth
scale, support labels and calibrated abstention.  The evaluator separates mechanism
recovery, radiance prediction, held-out noise transfer and model-inadequacy refusal.

This is a deterministic plane-parallel, non-scattering LTE emulator.  It is deliberately
not described as a line-by-line model or as validation on satellite observations.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np


PLANCK_H = 6.62607015e-34
LIGHT_C = 299792458.0
BOLTZMANN_K = 1.380649e-23

N_LAYERS = 16
N_CHANNELS = 24
N_TEMPERATURE_KNOTS = 4
N_PARAMETERS = 5
PRESSURE_EDGES_HPA = np.geomspace(1000.0, 20.0, N_LAYERS + 1)
PRESSURE_MIDPOINTS_HPA = np.sqrt(
    PRESSURE_EDGES_HPA[:-1] * PRESSURE_EDGES_HPA[1:]
)
LOG_PRESSURE_COORDINATE = (
    np.log(1000.0 / PRESSURE_MIDPOINTS_HPA) / np.log(50.0)
)
ALTITUDE_KM = 7.0 * np.log(1000.0 / PRESSURE_MIDPOINTS_HPA)
REFERENCE_TEMPERATURE_K = np.where(
    ALTITUDE_KM <= 11.0,
    288.0 - 6.5 * ALTITUDE_KM,
    216.5 + 1.5 * (ALTITUDE_KM - 11.0),
)


def _linear_temperature_basis():
    controls = np.asarray((0.0, 0.32, 0.66, 1.0))
    basis = np.zeros((N_LAYERS, N_TEMPERATURE_KNOTS), dtype=float)
    for row, coordinate in enumerate(LOG_PRESSURE_COORDINATE):
        interval = int(np.searchsorted(controls, coordinate) - 1)
        interval = max(0, min(N_TEMPERATURE_KNOTS - 2, interval))
        fraction = np.clip(
            (coordinate - controls[interval])
            / (controls[interval + 1] - controls[interval]),
            0.0, 1.0,
        )
        basis[row, interval] = 1.0 - fraction
        basis[row, interval + 1] = fraction
    return basis


TEMPERATURE_BASIS = _linear_temperature_basis()
CHANNEL_WAVENUMBERS_CM = np.linspace(620.0, 760.0, N_CHANNELS)
CHANNEL_OPTICAL_STRENGTHS = np.geomspace(0.06, 40.0, N_CHANNELS)
LAYER_MASS_FRACTIONS = (
    (PRESSURE_EDGES_HPA[:-1] - PRESSURE_EDGES_HPA[1:])
    / (PRESSURE_EDGES_HPA[0] - PRESSURE_EDGES_HPA[-1])
)
BASE_LAYER_OPTICAL_DEPTHS = (
    CHANNEL_OPTICAL_STRENGTHS[:, None] * LAYER_MASS_FRACTIONS[None, :]
)

VIEW_COSINE_BOUNDS = (0.45, 1.0)
MAX_CHANNELS_PER_CALL = 12
MAX_EXPERIMENT_CALLS = 4
EXPERIMENT_BUDGET_UNITS = 18
TEMPERATURE_ANOMALY_BOUNDS_K = (-12.0, 12.0)
OPTICAL_DEPTH_SCALE_BOUNDS = (0.65, 1.35)
MIN_ACTIVE_TEMPERATURE_ANOMALY_K = 0.5
MIN_ACTIVE_OPTICAL_DEPTH_DEVIATION = 0.02


# Four temperature anomaly knots followed by the optical-depth scale.  These hidden
# procedural templates span lower-, middle- and upper-atmospheric perturbations.
PARAMETER_TEMPLATES = (
    ((4.0, -5.0, 0.0, 0.0), 0.82),
    ((-3.0, 0.0, -5.0, 3.0), 1.00),
    ((0.0, -2.0, 3.0, 1.0), 0.95),
    ((-5.0, 1.0, 0.0, 4.0), 1.22),
    ((2.0, 6.0, 4.0, 0.0), 0.76),
    ((-6.0, 0.0, 2.0, 5.0), 1.00),
    ((0.0, -7.0, -5.0, 6.0), 1.05),
)


# (seed, template, radiance-noise standard deviation, kind).  Unsupported noise
# levels deliberately coincide with supported levels in the same split.
DEVELOPMENT_SPECS = (
    (91009, 0, 0.000600, "in_library"),
    (91019, 1, 0.000672, "in_library"),
    (91033, 2, 0.000744, "in_library"),
    (91079, 3, 0.000816, "in_library"),
    (91081, 0, 0.000600, "null"),
    (91097, 0, 0.000816, "absorber"),
)
HELDOUT_SPECS = (
    (101003, 4, 0.001200, "in_library"),
    (101009, 5, 0.001344, "in_library"),
    (101021, 6, 0.001488, "in_library"),
    (101041, 0, 0.001200, "null"),
    (101051, 1, 0.001488, "cloud"),
)


PUBLIC_MODEL = {
    "pressure_midpoints_hpa": PRESSURE_MIDPOINTS_HPA.copy(),
    "reference_temperature_K": REFERENCE_TEMPERATURE_K.copy(),
    "temperature_basis": TEMPERATURE_BASIS.copy(),
    "channel_wavenumbers_cm": CHANNEL_WAVENUMBERS_CM.copy(),
    "base_layer_optical_depths": BASE_LAYER_OPTICAL_DEPTHS.copy(),
    "view_cosine_bounds": tuple(VIEW_COSINE_BOUNDS),
    "temperature_anomaly_bounds_K": tuple(TEMPERATURE_ANOMALY_BOUNDS_K),
    "optical_depth_scale_bounds": tuple(OPTICAL_DEPTH_SCALE_BOUNDS),
}


def planck_radiance(temperature_K, wavenumber_cm):
    """Spectral radiance per inverse centimetre for a black body."""
    temperature = np.asarray(temperature_K, dtype=float)
    sigma_m = 100.0 * np.asarray(wavenumber_cm, dtype=float)
    exponent = PLANCK_H * LIGHT_C * sigma_m / (BOLTZMANN_K * temperature)
    return (
        2.0 * PLANCK_H * LIGHT_C**2 * sigma_m**3
        / np.expm1(exponent) * 100.0
    )


def _make_parameters(seed, template):
    if not 0 <= int(template) < len(PARAMETER_TEMPLATES):
        raise ValueError("unknown atmospheric template")
    rng = np.random.default_rng(int(seed))
    knots = np.asarray(PARAMETER_TEMPLATES[int(template)][0], dtype=float)
    active = np.abs(knots) > 0.0
    knots[active] *= rng.uniform(0.90, 1.10, size=int(np.sum(active)))
    optical_scale = float(PARAMETER_TEMPLATES[int(template)][1])
    if optical_scale != 1.0:
        optical_scale = 1.0 + (optical_scale - 1.0) * rng.uniform(0.90, 1.10)
    return np.concatenate((knots, (optical_scale,)))


def _world(spec):
    seed, template, noise, kind = spec
    parameters = _make_parameters(seed, template)
    if kind == "null":
        parameters = np.asarray((0.0, 0.0, 0.0, 0.0, 1.0))
    return {
        "seed": int(seed),
        "template": int(template),
        "noise": float(noise),
        "kind": str(kind),
        "parameters": parameters,
    }


def temperature_profile(parameters):
    values = np.asarray(parameters, dtype=float)
    if values.shape != (N_PARAMETERS,):
        raise ValueError("parameter vector must have length five")
    return REFERENCE_TEMPERATURE_K + TEMPERATURE_BASIS @ values[:4]


def forward_radiances(parameters, channel_indices, view_cosines,
                      model_kind="in_library"):
    """Evaluate the public non-scattering, plane-parallel thermal model."""
    values = np.asarray(parameters, dtype=float)
    channels = np.asarray(channel_indices, dtype=int).ravel()
    views = np.broadcast_to(
        np.asarray(view_cosines, dtype=float), channels.shape
    ).ravel()
    if values.shape != (N_PARAMETERS,):
        raise ValueError("parameter vector must have length five")
    if np.any(channels < 0) or np.any(channels >= N_CHANNELS):
        raise ValueError("channel index outside public bounds")
    if np.any(views <= 0.0):
        raise ValueError("view cosines must be positive")
    profile = temperature_profile(values)
    result = np.empty(len(channels), dtype=float)
    for output_index, (channel, view_cosine) in enumerate(zip(channels, views)):
        optical_depth = values[4] * BASE_LAYER_OPTICAL_DEPTHS[channel].copy()
        if model_kind == "cloud":
            # A grey layer not present in the public clear-sky model.
            optical_depth[5] += 0.80
        elif model_kind == "absorber":
            # A spectrally localized, vertically concentrated absorber outside the
            # public global optical-depth scaling family.
            vertical = np.exp(
                -0.5 * ((LOG_PRESSURE_COORDINATE - 0.27) / 0.13) ** 2
            )
            spectral = math.exp(
                -0.5 * ((CHANNEL_WAVENUMBERS_CM[channel] - 735.0) / 10.0) ** 2
            )
            optical_depth += 1.60 * vertical * spectral
        elif model_kind not in {"in_library", "null"}:
            raise ValueError("unknown radiative model kind")

        # Upwelling black-surface radiance propagated from the surface layer to TOA.
        radiance = float(planck_radiance(profile[0], CHANNEL_WAVENUMBERS_CM[channel]))
        for layer in range(N_LAYERS):
            transmittance = math.exp(-optical_depth[layer] / float(view_cosine))
            layer_emission = float(planck_radiance(
                profile[layer], CHANNEL_WAVENUMBERS_CM[channel]
            ))
            radiance = radiance * transmittance + layer_emission * (1.0 - transmittance)
        result[output_index] = radiance
    return result


def _world_radiances(world, channel_indices, view_cosines):
    kind = world["kind"] if world["kind"] in {"cloud", "absorber"} else "in_library"
    return forward_radiances(
        world["parameters"], channel_indices, view_cosines, kind
    )


def _query_seed(world_seed, call_index, channels, view_cosine):
    payload = (
        np.asarray((view_cosine,), dtype="<f8").tobytes()
        + np.asarray(channels, dtype="<i8").ravel().tobytes()
    )
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _SoundingLaboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.failure_reason = None

    def _reject(self, message, exception_type=ValueError):
        self.violated = True
        if self.failure_reason is None:
            self.failure_reason = str(message)
        raise exception_type(message)

    def observe(self, channel_indices, view_cosine):
        try:
            raw_channels = np.asarray(channel_indices, dtype=float)
        except (TypeError, ValueError, OverflowError):
            self._reject("channel indices must be numeric")
        if raw_channels.ndim != 1 or not (
            1 <= len(raw_channels) <= MAX_CHANNELS_PER_CALL
        ):
            self._reject("channel_indices must contain 1-12 entries")
        if np.any(~np.isfinite(raw_channels)) or np.any(
            raw_channels != np.rint(raw_channels)
        ):
            self._reject("channel indices must be finite integers")
        channels = raw_channels.astype(int)
        if np.any(channels < 0) or np.any(channels >= N_CHANNELS):
            self._reject("channel index outside public bounds")
        if len(np.unique(channels)) != len(channels):
            self._reject("channel indices must be unique within one call")
        try:
            view = float(view_cosine)
        except (TypeError, ValueError, OverflowError):
            self._reject("view cosine must be numeric")
        if not math.isfinite(view) or not (
            VIEW_COSINE_BOUNDS[0] <= view <= VIEW_COSINE_BOUNDS[1]
        ):
            self._reject("view cosine outside public bounds")
        if self.calls + 1 > MAX_EXPERIMENT_CALLS:
            self._reject("sounding experiment call limit exceeded", RuntimeError)
        cost = len(channels)
        if self.used + cost > EXPERIMENT_BUDGET_UNITS:
            self._reject("sounding experiment budget exceeded", RuntimeError)
        self.used += cost
        self.calls += 1
        clean = _world_radiances(self.world, channels, np.full(len(channels), view))
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, channels, view
        ))
        observed = clean + rng.normal(
            scale=self.world["noise"], size=len(channels)
        )
        return {
            "channel_indices": channels.copy(),
            "wavenumbers_cm": CHANNEL_WAVENUMBERS_CM[channels].copy(),
            "view_cosine": float(view),
            "radiances": observed,
            "radiance_noise_std": float(self.world["noise"]),
            "budget_cost": int(cost),
        }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    try:
        confidence = float(submission.get("confidence"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("confidence must be numeric") from exc
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    try:
        knots = np.asarray(
            submission.get("temperature_anomaly_knots_K"), dtype=float
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("temperature anomalies must be numeric") from exc
    try:
        support_raw = np.asarray(submission.get("support"), dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("support must be numeric") from exc
    try:
        optical_scale = float(submission.get("optical_depth_scale"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("optical-depth scale must be numeric") from exc
    if knots.shape != (N_TEMPERATURE_KNOTS,) or np.any(~np.isfinite(knots)):
        raise ValueError("temperature anomalies must be a finite length-four array")
    if support_raw.shape != (N_PARAMETERS,) or np.any(~np.isfinite(support_raw)):
        raise ValueError("support must be a finite length-five array")
    if np.any(support_raw < 0.0) or np.any(support_raw > 1.0) or np.any(
        support_raw != np.rint(support_raw)
    ):
        raise ValueError("support must contain exact zero/one labels")
    if not math.isfinite(optical_scale) or not (
        OPTICAL_DEPTH_SCALE_BOUNDS[0]
        <= optical_scale <= OPTICAL_DEPTH_SCALE_BOUNDS[1]
    ):
        raise ValueError("optical-depth scale outside public bounds")
    support = support_raw.astype(bool)
    abstain = bool(submission["abstain"])
    if abstain:
        if np.any(support) or np.any(np.abs(knots) > 1e-12) or abs(optical_scale - 1.0) > 1e-12:
            raise ValueError("abstention requires the canonical empty mechanism")
        return np.asarray((0.0, 0.0, 0.0, 0.0, 1.0)), support, confidence, True
    if not np.any(support):
        raise ValueError("a non-abstaining retrieval needs an active parameter")
    if np.any(np.abs(knots[~support[:4]]) > 1e-12):
        raise ValueError("inactive temperature knots must be exactly zero")
    active_knots = np.abs(knots[support[:4]])
    if np.any(active_knots < MIN_ACTIVE_TEMPERATURE_ANOMALY_K) or np.any(
        active_knots > TEMPERATURE_ANOMALY_BOUNDS_K[1]
    ):
        raise ValueError("active temperature anomalies outside public bounds")
    if support[4]:
        deviation = abs(optical_scale - 1.0)
        if not MIN_ACTIVE_OPTICAL_DEPTH_DEVIATION <= deviation <= 0.35:
            raise ValueError("active optical-depth deviation outside public bounds")
    elif abs(optical_scale - 1.0) > 1e-12:
        raise ValueError("inactive optical-depth scale must equal one")
    parameters = np.concatenate((knots, (optical_scale,)))
    profile = temperature_profile(parameters)
    if np.any(profile < 180.0) or np.any(profile > 320.0):
        raise ValueError("retrieved temperature profile outside public bounds")
    return parameters, support, confidence, False


def _truth_support(parameters):
    values = np.asarray(parameters, dtype=float)
    return np.concatenate((
        np.abs(values[:4]) >= MIN_ACTIVE_TEMPERATURE_ANOMALY_K,
        (abs(values[4] - 1.0) >= MIN_ACTIVE_OPTICAL_DEPTH_DEVIATION,),
    ))


def _mechanism_metrics(world, parameters, predicted_support, abstain):
    if world["kind"] in {"null", "absorber", "cloud"}:
        correct = bool(abstain and not np.any(predicted_support))
        return {
            "support_f1": 1.0 if correct else 0.0,
            "parameter_score": 1.0 if correct else 0.0,
            "profile_score": 1.0 if correct else 0.0,
            "optical_depth_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        }
    if abstain:
        return {
            "support_f1": 0.0,
            "parameter_score": 0.0,
            "profile_score": 0.0,
            "optical_depth_score": 0.0,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
        }
    truth = world["parameters"]
    true_support = _truth_support(truth)
    tp = int(np.sum(true_support & predicted_support))
    fp = int(np.sum(~true_support & predicted_support))
    fn = int(np.sum(true_support & ~predicted_support))
    support_f1 = 0.0 if tp == 0 else 2.0 * tp / (2.0 * tp + fp + fn)
    truth_vector = np.concatenate((truth[:4], (truth[4] - 1.0,)))
    predicted_vector = np.concatenate((parameters[:4], (parameters[4] - 1.0,)))
    scaled_error = float(np.sqrt(np.mean(
        ((predicted_vector - truth_vector)
         / np.asarray((5.0, 5.0, 5.0, 5.0, 0.10))) ** 2
    )))
    parameter_score = math.exp(-0.5 * (scaled_error / 0.30) ** 2)
    profile_rmse = float(np.sqrt(np.mean(
        (temperature_profile(parameters) - temperature_profile(truth)) ** 2
    )))
    profile_score = math.exp(-0.5 * (profile_rmse / 1.75) ** 2)
    optical_score = math.exp(
        -0.5 * ((parameters[4] - truth[4]) / 0.045) ** 2
    )
    mechanism = (
        0.35 * support_f1 + 0.35 * parameter_score
        + 0.20 * profile_score + 0.10 * optical_score
    )
    return {
        "support_f1": float(support_f1),
        "parameter_score": float(parameter_score),
        "profile_score": float(profile_score),
        "optical_depth_score": float(optical_score),
        "mechanism_score": float(mechanism),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _radiance_prediction_score(world, parameters, view_shift):
    channels = np.tile(np.arange(N_CHANNELS), 2)
    views = (
        np.repeat((0.45, 0.95), N_CHANNELS)
        if view_shift else np.repeat((0.60, 0.85), N_CHANNELS)
    )
    truth = _world_radiances(world, channels, views)
    prediction = forward_radiances(parameters, channels, views)
    baseline = forward_radiances(
        np.asarray((0.0, 0.0, 0.0, 0.0, 1.0)), channels, views
    )
    rmse = float(np.sqrt(np.mean((prediction - truth) ** 2)))
    baseline_rmse = max(0.001, float(np.sqrt(np.mean((baseline - truth) ** 2))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _reference_submission(world):
    if world["kind"] != "in_library":
        return {
            "temperature_anomaly_knots_K": np.zeros(N_TEMPERATURE_KNOTS),
            "optical_depth_scale": 1.0,
            "support": np.zeros(N_PARAMETERS, dtype=int),
            "confidence": 0.0,
            "abstain": True,
        }
    parameters = world["parameters"]
    return {
        "temperature_anomaly_knots_K": parameters[:4].copy(),
        "optical_depth_scale": float(parameters[4]),
        "support": _truth_support(parameters).astype(int),
        "confidence": 1.0,
        "abstain": False,
    }


def _public_failure_kind(stage, laboratory):
    """Return a finite label-blind error category for iterative feedback.

    Raw exception strings remain in the sealed per-world record.  They are not safe search
    feedback because a candidate could deliberately include observed radiances in its own
    exception message.  This taxonomy communicates which public contract boundary failed
    without exposing a world index, split, hidden category, truth, or candidate-controlled
    text.
    """
    if laboratory.violated:
        return "invalid_experiment_request"
    if stage == "submission_validation":
        return "invalid_return_artifact"
    if stage == "candidate_execution":
        return "candidate_runtime_or_callback_processing_error"
    return "trusted_evaluator_internal_error"


def _evaluate_world(discover_atmosphere, spec, split, index):
    world = _world(spec)
    laboratory = _SoundingLaboratory(world)
    stage = "candidate_execution"
    try:
        public_model = {
            key: value.copy() if isinstance(value, np.ndarray) else value
            for key, value in PUBLIC_MODEL.items()
        }
        submission = discover_atmosphere(
            public_model, laboratory.observe, EXPERIMENT_BUDGET_UNITS
        )
        if laboratory.violated:
            raise RuntimeError(
                laboratory.failure_reason or "invalid sounding experiment"
            )
        stage = "submission_validation"
        parameters, support, confidence, abstain = _validate_submission(submission)
        stage = "trusted_scoring"
        mechanism = _mechanism_metrics(world, parameters, support, abstain)
        prediction = _radiance_prediction_score(world, parameters, False)
        view_shift = _radiance_prediction_score(world, parameters, True)
        target_confidence = (
            mechanism["mechanism_score"] if world["kind"] == "in_library" else 0.0
        )
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "support_f1": round(mechanism["support_f1"], 6),
            "parameter_score": round(mechanism["parameter_score"], 6),
            "profile_score": round(mechanism["profile_score"], 6),
            "optical_depth_score": round(mechanism["optical_depth_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "radiance_prediction_score": round(prediction, 6),
            "radiance_view_shift_score": round(view_shift, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - target_confidence) ** 2, 6
            ),
            "correct_refusal": mechanism["correct_refusal"],
            "false_discovery": mechanism["false_discovery"],
            "abstained": abstain,
            "confidence": round(confidence, 6),
            "n_true_parameters": int(np.sum(_truth_support(world["parameters"]))),
            "n_predicted_parameters": int(np.sum(support)),
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }
    except Exception as exc:
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "failure_kind": _public_failure_kind(stage, laboratory),
            "support_f1": 0.0,
            "parameter_score": 0.0,
            "profile_score": 0.0,
            "optical_depth_score": 0.0,
            "mechanism_score": 0.0,
            "radiance_prediction_score": 0.0,
            "radiance_view_shift_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "abstained": False,
            "confidence": 0.0,
            "n_true_parameters": int(np.sum(_truth_support(world["parameters"]))),
            "n_predicted_parameters": 0,
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }


def _split_summary(records, unsupported_count):
    raw = float(np.mean([row["mechanism_score"] for row in records]))
    abstain_anchor = unsupported_count / len(records)
    normalized = float(np.clip(
        (raw - abstain_anchor) / (1.0 - abstain_anchor), 0.0, 1.0
    ))
    supported = [row for row in records if row["kind"] == "in_library"]
    unsupported = [row for row in records if row["kind"] != "in_library"]
    misspecified = [row for row in records if row["kind"] in {"absorber", "cloud"}]
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "supported_mechanism": float(np.mean([
            row["mechanism_score"] for row in supported
        ])),
        "discovery_coverage": float(np.mean([
            not row["abstained"] for row in supported
        ])),
        "support_f1": float(np.mean([row["support_f1"] for row in supported])),
        "parameter_score": float(np.mean([
            row["parameter_score"] for row in supported
        ])),
        "profile_score": float(np.mean([
            row["profile_score"] for row in supported
        ])),
        "optical_depth_score": float(np.mean([
            row["optical_depth_score"] for row in supported
        ])),
        "radiance_prediction": float(np.mean([
            row["radiance_prediction_score"] for row in supported
        ])),
        "radiance_view_shift": float(np.mean([
            row["radiance_view_shift_score"] for row in supported
        ])),
        "misspecified_radiance_prediction": float(np.mean([
            row["radiance_prediction_score"] for row in misspecified
        ])),
        "confidence_calibration": float(np.mean([
            row["confidence_calibration_score"] for row in records
        ])),
        "false_discovery_rate": float(np.mean([
            row["false_discovery"] for row in unsupported
        ])),
        "correct_refusal_rate": float(np.mean([
            row["correct_refusal"] for row in unsupported
        ])),
        "valid_count": sum(bool(row["valid"]) for row in records),
    }


def _reset_candidate_session(discover_atmosphere):
    reset = getattr(discover_atmosphere, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(discover_atmosphere):
    development = []
    heldout = []
    first_world = True
    for split, specs, records in (
        ("development", DEVELOPMENT_SPECS, development),
        ("heldout", HELDOUT_SPECS, heldout),
    ):
        for index, spec in enumerate(specs):
            if not first_world:
                _reset_candidate_session(discover_atmosphere)
            first_world = False
            records.append(_evaluate_world(
                discover_atmosphere, spec, split, index
            ))
    dev = _split_summary(
        development,
        sum(spec[3] != "in_library" for spec in DEVELOPMENT_SPECS),
    )
    hold = _split_summary(
        heldout,
        sum(spec[3] != "in_library" for spec in HELDOUT_SPECS),
    )
    all_records = development + heldout
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    result = {
        "combined_score": dev["normalized_mechanism"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "development_supported_mechanism_score": dev["supported_mechanism"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_support_f1": dev["support_f1"],
        "development_parameter_score": dev["parameter_score"],
        "development_profile_score": dev["profile_score"],
        "development_optical_depth_score": dev["optical_depth_score"],
        "development_radiance_prediction_score": dev["radiance_prediction"],
        "development_radiance_view_shift_score": dev["radiance_view_shift"],
        "development_misspecified_radiance_score": dev["misspecified_radiance_prediction"],
        "development_confidence_calibration_score": dev["confidence_calibration"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "robustness_score": hold["normalized_mechanism"] if hold_valid else 0.0,
        "heldout_mechanism_score": hold["raw_mechanism"],
        "heldout_supported_mechanism_score": hold["supported_mechanism"],
        "heldout_discovery_coverage": hold["discovery_coverage"],
        "heldout_support_f1": hold["support_f1"],
        "heldout_parameter_score": hold["parameter_score"],
        "heldout_profile_score": hold["profile_score"],
        "heldout_optical_depth_score": hold["optical_depth_score"],
        "heldout_radiance_prediction_score": hold["radiance_prediction"],
        "heldout_radiance_view_shift_score": hold["radiance_view_shift"],
        "heldout_misspecified_radiance_score": hold["misspecified_radiance_prediction"],
        "heldout_confidence_calibration_score": hold["confidence_calibration"],
        "heldout_false_discovery_rate": hold["false_discovery_rate"],
        "heldout_correct_refusal_rate": hold["correct_refusal_rate"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in all_records
        ])),
        "mean_experiment_budget_units": float(np.mean([
            row["experiment_budget_units"] for row in all_records
        ])),
        "per_world": all_records,
    }
    if not dev_valid:
        failure_kinds = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(failure_kinds)
    return result
