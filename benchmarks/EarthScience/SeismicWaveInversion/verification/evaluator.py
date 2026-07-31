"""Active laterally varying reflection-waveform inversion with refusal.

The public model is a locally layered, lossless acoustic medium with two quadratic interfaces.
Candidates choose CMP midpoints, receiver offsets and source peak frequencies under a charged
acquisition budget, then infer three interval velocities and two interface shapes or abstain.
The evaluator keeps waveform
prediction, physical-parameter recovery, experiment information, far-offset transfer and
null/out-of-library refusal separate.

This is a controlled ray-theoretical reflection laboratory, not field FWI.  Exact reflection
traveltimes solve Snell's-law ray geometry rather than using a normal-moveout approximation.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np


SEISMIC_WAVE_INVERSION_V2 = True

MIDPOINT_BOUNDS_M = (0.0, 10000.0)
OFFSET_BOUNDS_M = (0.0, 3000.0)
FREQUENCY_BOUNDS_HZ = (6.0, 28.0)
MIN_OFFSETS = 4
MAX_OFFSETS = 12
ACQUISITION_BUDGET_UNITS = 12

TIME_STEP_S = 0.004
TIME_S = np.arange(0.0, 2.0 + 0.5 * TIME_STEP_S, TIME_STEP_S)

PARAMETER_NAMES = (
    "v1_m_s", "v2_m_s", "v3_m_s",
    "h1_center_m", "h1_slope_m", "h1_curvature_m",
    "h2_center_m", "h2_slope_m", "h2_curvature_m",
)
PARAMETER_BOUNDS = np.asarray((
    (1400.0, 2400.0),
    (1800.0, 3400.0),
    (2400.0, 4800.0),
    (180.0, 600.0),
    (-160.0, 160.0),
    (-100.0, 100.0),
    (300.0, 1000.0),
    (-220.0, 220.0),
    (-150.0, 150.0),
), dtype=float)
PARAMETER_SCALES = np.asarray((
    180.0, 220.0, 300.0, 70.0, 55.0, 40.0, 110.0, 75.0, 55.0,
))


BASE_MODELS = (
    (1780.0, 2440.0, 3340.0, 285.0, 70.0, -25.0, 540.0, -95.0, 35.0),
    (1580.0, 2220.0, 3920.0, 235.0, -55.0, 30.0, 720.0, 125.0, -45.0),
    (2070.0, 2810.0, 4140.0, 420.0, 105.0, 45.0, 470.0, -120.0, 60.0),
    (1740.0, 3060.0, 4380.0, 350.0, -90.0, -35.0, 790.0, 150.0, 55.0),
    (1940.0, 2590.0, 3620.0, 500.0, 60.0, 55.0, 390.0, -70.0, -35.0),
    (1510.0, 2340.0, 4580.0, 230.0, 35.0, -40.0, 850.0, 175.0, -65.0),
    (2220.0, 3020.0, 4520.0, 555.0, -115.0, 30.0, 650.0, -145.0, 70.0),
)

# (seed, supported-template index, trace-noise standard deviation, kind).
DEVELOPMENT_SPECS = (
    (76103, 0, 0.0020, "in_library"),
    (76123, 1, 0.0022, "in_library"),
    (76129, 2, 0.0024, "in_library"),
    (76147, 3, 0.0022, "in_library"),
    (76157, 0, 0.0020, "null"),
    (76171, 0, 0.0024, "misspecified"),
)
HELDOUT_SPECS = (
    (86111, 4, 0.0030, "in_library"),
    (86117, 5, 0.0032, "in_library"),
    (86131, 6, 0.0034, "in_library"),
    (86137, 0, 0.0030, "null"),
    (86143, 0, 0.0034, "misspecified"),
)

REFERENCE_EXPERIMENTS = (
    (
        np.full(8, 5000.0),
        np.linspace(120.0, 3000.0, 8),
        24.0,
    ),
    (
        np.linspace(500.0, 9500.0, 8),
        np.linspace(0.0, 700.0, 8),
        16.0,
    ),
)


def _density_from_velocity(velocity_m_s):
    """Gardner-style deterministic density relation in kg/m^3."""
    velocity = np.asarray(velocity_m_s, dtype=float)
    return 310.0 * np.power(velocity, 0.25)


def _ricker(time_difference_s, peak_frequency_hz):
    phase = np.pi * float(peak_frequency_hz) * np.asarray(
        time_difference_s, dtype=float
    )
    squared = phase * phase
    return (1.0 - 2.0 * squared) * np.exp(-squared)


def _reflection_travel_time(path_velocities, path_thicknesses, offsets_m):
    """Exact two-way ray time for a horizontal reflector by Snell's law."""
    velocities = np.asarray(path_velocities, dtype=float).ravel()
    thicknesses = np.asarray(path_thicknesses, dtype=float).ravel()
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    if len(velocities) != len(thicknesses) or not len(velocities):
        raise ValueError("ray path velocities and thicknesses must align")
    if np.any(velocities <= 0.0) or np.any(thicknesses <= 0.0):
        raise ValueError("ray path values must be positive")

    low = np.zeros(len(offsets), dtype=float)
    high = np.full(
        len(offsets), (1.0 - 1.0e-10) / float(np.max(velocities))
    )
    target = 0.5 * offsets
    for _ in range(64):
        ray_parameter = 0.5 * (low + high)
        pv = ray_parameter[:, None] * velocities[None, :]
        cosine = np.sqrt(np.maximum(1.0 - pv * pv, 1.0e-18))
        half_offset = np.sum(
            thicknesses[None, :] * pv / cosine, axis=1
        )
        move_right = half_offset < target
        low = np.where(move_right, ray_parameter, low)
        high = np.where(move_right, high, ray_parameter)
    ray_parameter = 0.5 * (low + high)
    pv = ray_parameter[:, None] * velocities[None, :]
    cosine = np.sqrt(np.maximum(1.0 - pv * pv, 1.0e-18))
    half_time = np.sum(
        thicknesses[None, :] / (velocities[None, :] * cosine), axis=1
    )
    return 2.0 * half_time


def synthesize_layers(velocities_m_s, thicknesses_m, offsets_m,
                      peak_frequency_hz, time_s=TIME_S):
    """Return primary reflected pressure traces for an arbitrary layer stack.

    ``velocities_m_s`` contains every layer velocity. ``thicknesses_m`` contains the
    finite thickness above each interface, hence has length ``len(velocities)-1``.
    Normal-incidence acoustic-impedance reflection coefficients set amplitudes; exact
    ray-theoretical reflection times set waveform positions.
    """
    velocities = np.asarray(velocities_m_s, dtype=float).ravel()
    thicknesses = np.asarray(thicknesses_m, dtype=float).ravel()
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    times = np.asarray(time_s, dtype=float).ravel()
    if len(velocities) != len(thicknesses) + 1 or len(velocities) < 2:
        raise ValueError("layer stack requires one more velocity than thickness")
    if np.any(~np.isfinite(velocities)) or np.any(~np.isfinite(thicknesses)):
        raise ValueError("layer stack must be finite")
    if np.any(~np.isfinite(offsets)) or np.any(~np.isfinite(times)):
        raise ValueError("sampling coordinates must be finite")
    if not FREQUENCY_BOUNDS_HZ[0] <= float(peak_frequency_hz) <= FREQUENCY_BOUNDS_HZ[1]:
        raise ValueError("source frequency outside public bounds")

    density = _density_from_velocity(velocities)
    impedance = density * velocities
    reflection = (impedance[1:] - impedance[:-1]) / (
        impedance[1:] + impedance[:-1]
    )
    traces = np.zeros((len(offsets), len(times)), dtype=float)
    transmission = 1.0
    for interface in range(len(thicknesses)):
        travel_time = _reflection_travel_time(
            velocities[:interface + 1], thicknesses[:interface + 1], offsets
        )
        amplitude = transmission * reflection[interface]
        traces += amplitude * _ricker(
            times[None, :] - travel_time[:, None], peak_frequency_hz
        )
        transmission *= 1.0 - reflection[interface] ** 2
    return traces


def local_thicknesses(parameters, midpoints_m):
    """Return the two positive local layer thicknesses at each CMP midpoint."""
    parameters = np.asarray(parameters, dtype=float).ravel()
    if parameters.shape != (9,):
        raise ValueError("parameters must contain nine values")
    normalized = (np.asarray(midpoints_m, dtype=float).ravel() - 5000.0) / 5000.0
    h1 = parameters[3] + parameters[4] * normalized + parameters[5] * normalized**2
    h2 = parameters[6] + parameters[7] * normalized + parameters[8] * normalized**2
    return np.column_stack((h1, h2))


def _quadratic_profile_extrema(center, slope, curvature):
    """Return the exact extrema of ``center + slope*q + curvature*q^2``.

    The public profile coordinate is q in [-1, 1].  Sampling a fixed grid can miss
    a shallow interior vertex, so physical submission validation uses the analytic
    endpoint/vertex set instead.
    """
    coordinates = [-1.0, 1.0]
    if curvature != 0.0:
        vertex = -float(slope) / (2.0 * float(curvature))
        if -1.0 < vertex < 1.0:
            coordinates.append(vertex)
    values = [
        float(center) + float(slope) * coordinate
        + float(curvature) * coordinate**2
        for coordinate in coordinates
    ]
    return min(values), max(values)


def synthesize_public(parameters, midpoints_m, offsets_m, peak_frequency_hz,
                      time_s=TIME_S):
    parameters = np.asarray(parameters, dtype=float).ravel()
    midpoints = np.asarray(midpoints_m, dtype=float).ravel()
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    if parameters.shape != (9,):
        raise ValueError("parameters must contain nine values")
    if midpoints.shape != offsets.shape:
        raise ValueError("midpoints and offsets must align")
    thicknesses = local_thicknesses(parameters, midpoints)
    if np.any(thicknesses <= 0.0):
        raise ValueError("local layer thickness must be positive")
    traces = np.empty((len(offsets), len(np.asarray(time_s).ravel())))
    for row, (local_h, offset) in enumerate(zip(thicknesses, offsets)):
        traces[row] = synthesize_layers(
            parameters[:3], local_h, np.asarray((offset,)),
            peak_frequency_hz, time_s,
        )[0]
    return traces


def _make_parameters(seed, template):
    if not 0 <= int(template) < len(BASE_MODELS):
        raise ValueError("unknown velocity template")
    rng = np.random.default_rng(int(seed))
    parameters = np.asarray(BASE_MODELS[int(template)], dtype=float).copy()
    parameters[:3] *= rng.uniform(0.985, 1.015, size=3)
    parameters[[3, 6]] *= rng.uniform(0.97, 1.03, size=2)
    parameters[[4, 5, 7, 8]] *= rng.uniform(0.92, 1.08, size=4)
    return np.clip(
        parameters, PARAMETER_BOUNDS[:, 0] + 1.0,
        PARAMETER_BOUNDS[:, 1] - 1.0,
    )


def _make_misspecified_layers(seed):
    """A resolvable four-layer thin low-velocity-zone world."""
    rng = np.random.default_rng(int(seed) + 5099)
    velocities = np.asarray((1720.0, 2860.0, 2180.0, 4120.0))
    thicknesses = np.asarray((250.0, 175.0, 590.0))
    velocities *= rng.uniform(0.985, 1.015, size=4)
    thicknesses *= rng.uniform(0.97, 1.03, size=3)
    return velocities, thicknesses


def _world(spec):
    seed, template, noise, kind = spec
    return {
        "seed": int(seed),
        "kind": str(kind),
        "noise": float(noise),
        "parameters": (
            _make_parameters(seed, template)
            if kind == "in_library" else np.zeros(9, dtype=float)
        ),
        "misspecified_layers": (
            _make_misspecified_layers(seed)
            if kind == "misspecified" else None
        ),
    }


def _world_traces(world, midpoints_m, offsets_m, peak_frequency_hz,
                  time_s=TIME_S):
    if world["kind"] == "in_library":
        return synthesize_public(
            world["parameters"], midpoints_m, offsets_m,
            peak_frequency_hz, time_s
        )
    if world["kind"] == "misspecified":
        velocities, thicknesses = world["misspecified_layers"]
        midpoints = np.asarray(midpoints_m, dtype=float).ravel()
        offsets = np.asarray(offsets_m, dtype=float).ravel()
        traces = np.empty((len(offsets), len(np.asarray(time_s).ravel())))
        normalized = (midpoints - 5000.0) / 5000.0
        for row, (coordinate, offset) in enumerate(zip(normalized, offsets)):
            local = thicknesses * np.asarray((
                1.0 + 0.10 * coordinate,
                1.0 - 0.07 * coordinate + 0.04 * coordinate**2,
                1.0 + 0.06 * coordinate**2,
            ))
            traces[row] = synthesize_layers(
                velocities, local, np.asarray((offset,)),
                peak_frequency_hz, time_s,
            )[0]
        return traces
    offsets = np.asarray(offsets_m, dtype=float).ravel()
    times = np.asarray(time_s, dtype=float).ravel()
    return np.zeros((len(offsets), len(times)), dtype=float)


def _query_seed(world_seed, call_index, midpoints_m, offsets_m,
                peak_frequency_hz):
    payload = np.concatenate((
        np.asarray((peak_frequency_hz,), dtype="<f8"),
        np.asarray(midpoints_m, dtype="<f8").ravel(),
        np.asarray(offsets_m, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _SeismicLaboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.failure_reason = None
        self.records = []

    def acquire(self, midpoints_m, offsets_m, peak_frequency_hz):
        try:
            midpoints = np.asarray(midpoints_m, dtype=float)
            offsets = np.asarray(offsets_m, dtype=float)
            frequency = float(peak_frequency_hz)
            if midpoints.ndim != 1 or midpoints.shape != offsets.shape:
                raise ValueError("midpoints_m and offsets_m must be aligned vectors")
            if offsets.ndim != 1 or not MIN_OFFSETS <= len(offsets) <= MAX_OFFSETS:
                raise ValueError("acquisition must contain 4-12 traces")
            if np.any(~np.isfinite(midpoints)) or np.any(
                midpoints < MIDPOINT_BOUNDS_M[0]
            ) or np.any(midpoints > MIDPOINT_BOUNDS_M[1]):
                raise ValueError("CMP midpoints outside public bounds")
            if np.any(~np.isfinite(offsets)) or np.any(
                offsets < OFFSET_BOUNDS_M[0]
            ) or np.any(offsets > OFFSET_BOUNDS_M[1]):
                raise ValueError("receiver offsets outside public bounds")
            if len(np.unique(np.column_stack((midpoints, offsets)), axis=0)) != len(offsets):
                raise ValueError("CMP-offset pairs must be unique")
            if not math.isfinite(frequency) or not (
                FREQUENCY_BOUNDS_HZ[0] <= frequency <= FREQUENCY_BOUNDS_HZ[1]
            ):
                raise ValueError("peak frequency outside public bounds")
            cost = 2 + int(math.ceil(len(offsets) / 2.0))
            if self.used + cost > ACQUISITION_BUDGET_UNITS:
                raise RuntimeError("acquisition budget exceeded")
        except Exception as exc:
            self.violated = True
            self.failure_reason = "invalid acquisition request"
            raise exc

        self.used += cost
        self.calls += 1
        clean = _world_traces(self.world, midpoints, offsets, frequency)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, midpoints, offsets, frequency
        ))
        observed = clean + rng.normal(
            scale=self.world["noise"], size=clean.shape
        )
        record = {
            "midpoints_m": midpoints.copy(),
            "offsets_m": offsets.copy(),
            "peak_frequency_hz": frequency,
            "time_s": TIME_S.copy(),
            "traces": observed,
            "noise_std": float(self.world["noise"]),
            "budget_cost": int(cost),
            "budget_used": int(self.used),
        }
        self.records.append(record)
        return {
            key: (value.copy() if isinstance(value, np.ndarray) else value)
            for key, value in record.items()
        }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    parameters = np.asarray(submission.get("parameters"), dtype=float)
    if parameters.shape != (9,) or np.any(~np.isfinite(parameters)):
        raise ValueError("parameters must be nine finite values")
    abstain = bool(submission["abstain"])
    if abstain:
        if np.any(parameters != 0.0):
            raise ValueError("abstention requires the canonical zero parameter vector")
        return parameters.copy(), confidence, True
    if np.any(parameters < PARAMETER_BOUNDS[:, 0]) or np.any(
        parameters > PARAMETER_BOUNDS[:, 1]
    ):
        raise ValueError("velocity-model parameters outside public bounds")
    if not (
        parameters[1] >= parameters[0] + 100.0
        and parameters[2] >= parameters[1] + 100.0
    ):
        raise ValueError("the supported model requires increasing interval velocities")
    thickness_extrema = (
        _quadratic_profile_extrema(*parameters[3:6]),
        _quadratic_profile_extrema(*parameters[6:9]),
    )
    if any(
        minimum < 120.0 or maximum > 1200.0
        for minimum, maximum in thickness_extrema
    ):
        raise ValueError("local interface thicknesses leave the public physical range")
    return parameters.copy(), confidence, False


def _mechanism_quality(parameters, truth):
    scaled = (np.asarray(parameters) - np.asarray(truth)) / PARAMETER_SCALES
    return float(math.exp(-0.5 * float(np.mean(scaled * scaled))))


def _trace_quality(actual, predicted, noise):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    rmse = float(np.sqrt(np.mean((predicted - actual) ** 2)))
    signal = max(
        3.0 * float(noise), float(np.sqrt(np.mean(actual * actual)))
    )
    quality = math.exp(-0.5 * (rmse / (0.35 * signal)) ** 2)
    return float(np.clip(quality, 0.0, 1.0)), rmse, signal


def _prediction_quality(world, parameters, far_offset=False):
    if far_offset:
        midpoints = np.linspace(300.0, 9700.0, 9)
        offsets = np.linspace(1900.0, 3000.0, 9)
        frequencies = (10.0, 22.0)
    else:
        midpoints = np.linspace(150.0, 9850.0, 11)
        offsets = np.linspace(80.0, 2700.0, 11)
        frequencies = (7.0, 15.0, 27.0)
    actual = []
    predicted = []
    for frequency in frequencies:
        actual.append(_world_traces(world, midpoints, offsets, frequency))
        predicted.append(synthesize_public(
            parameters, midpoints, offsets, frequency
        ))
    return _trace_quality(
        np.concatenate(actual), np.concatenate(predicted), world["noise"]
    )


def _observed_fit_quality(laboratory, parameters):
    if not laboratory.records:
        return 0.0
    actual = []
    predicted = []
    for record in laboratory.records:
        actual.append(record["traces"])
        predicted.append(synthesize_public(
            parameters, record["midpoints_m"], record["offsets_m"],
            record["peak_frequency_hz"]
        ))
    return _trace_quality(
        np.concatenate(actual), np.concatenate(predicted),
        laboratory.world["noise"],
    )[0]


def _design_jacobian(parameters, records, noise):
    if not records:
        return np.empty((0, 9), dtype=float)
    parameters = np.asarray(parameters, dtype=float)
    columns = []
    for column in range(9):
        step = 1.0e-4 * PARAMETER_SCALES[column]
        upper = parameters.copy()
        lower = parameters.copy()
        upper[column] += step
        lower[column] -= step
        responses = []
        for record in records:
            high = synthesize_public(
                upper, record["midpoints_m"], record["offsets_m"],
                record["peak_frequency_hz"]
            )
            low = synthesize_public(
                lower, record["midpoints_m"], record["offsets_m"],
                record["peak_frequency_hz"]
            )
            responses.append((high - low).ravel())
        derivative = np.concatenate(responses) / (2.0 * step)
        columns.append(derivative * PARAMETER_SCALES[column] / float(noise))
    return np.column_stack(columns)


def _experiment_information(world, records):
    if world["kind"] != "in_library" or not records:
        return {
            "information_score": 0.0,
            "jacobian_rank": 0,
            "condition_number": None,
            "log_determinant": None,
            "reference_log_determinant": None,
        }
    jacobian = _design_jacobian(
        world["parameters"], records, world["noise"]
    )
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(
        jacobian, tol=singular[0] * 1.0e-8
    )) if len(singular) and singular[0] > 0.0 else 0
    condition = (
        float(singular[0] / singular[-1])
        if rank == 9 and singular[-1] > 0.0 else None
    )
    information = jacobian.T @ jacobian + np.eye(9) * 1.0e-9
    sign, log_determinant = np.linalg.slogdet(information)

    reference_records = [
        {
            "midpoints_m": midpoints,
            "offsets_m": offsets,
            "peak_frequency_hz": frequency,
        }
        for midpoints, offsets, frequency in REFERENCE_EXPERIMENTS
    ]
    reference_jacobian = _design_jacobian(
        world["parameters"], reference_records, world["noise"]
    )
    reference_information = (
        reference_jacobian.T @ reference_jacobian + np.eye(9) * 1.0e-9
    )
    reference_sign, reference_log = np.linalg.slogdet(reference_information)
    if rank < 9 or sign <= 0.0 or reference_sign <= 0.0:
        score = 0.0
    else:
        score = float(np.clip(math.exp(
            (float(log_determinant) - float(reference_log)) / 18.0
        ), 0.0, 1.0))
    return {
        "information_score": score,
        "jacobian_rank": rank,
        "condition_number": condition,
        "log_determinant": float(log_determinant) if sign > 0.0 else None,
        "reference_log_determinant": (
            float(reference_log) if reference_sign > 0.0 else None
        ),
    }


def _joint_quality(mechanism, prediction, information):
    if min(mechanism, prediction, information) <= 0.0:
        return 0.0
    return float(
        mechanism ** 0.45 * prediction ** 0.35 * information ** 0.20
    )


def _public_failure_kind(stage, laboratory):
    if laboratory.violated:
        return "invalid_acquisition_request"
    if stage == "submission_validation":
        return "invalid_return_artifact"
    if stage == "candidate_execution":
        return "candidate_runtime_or_callback_processing_error"
    return "trusted_evaluator_internal_error"


def _invalid_record(split, index, kind, failure_kind, laboratory):
    return {
        "split": split,
        "world_index": int(index),
        "kind": str(kind),
        "valid": False,
        "reason": str(failure_kind),
        "failure_kind": str(failure_kind),
        "abstain": False,
        "confidence": 0.0,
        "mechanism_quality": 0.0,
        "prediction_quality": 0.0,
        "far_offset_prediction_quality": 0.0,
        "observed_fit_quality": 0.0,
        "experiment_information_score": 0.0,
        "experiment_jacobian_rank": 0,
        "experiment_condition_number": None,
        "joint_quality": 0.0,
        "robust_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "acquisition_calls": int(laboratory.calls),
        "acquisition_budget_units": int(laboratory.used),
        "acquired_trace_count": int(sum(
            len(record["offsets_m"]) for record in laboratory.records
        )),
    }


def _evaluate_world(discover_layered_velocity, spec, split, index):
    world = _world(spec)
    laboratory = _SeismicLaboratory(world)
    stage = "candidate_execution"
    try:
        submission = discover_layered_velocity(
            MIDPOINT_BOUNDS_M, OFFSET_BOUNDS_M, FREQUENCY_BOUNDS_HZ,
            PARAMETER_NAMES,
            PARAMETER_BOUNDS.copy(), laboratory.acquire,
            ACQUISITION_BUDGET_UNITS,
        )
        stage = "submission_validation"
        parameters, confidence, abstain = _validate_submission(submission)
        if laboratory.violated:
            raise RuntimeError(
                laboratory.failure_reason or "invalid acquisition request"
            )
    except Exception:
        return _invalid_record(
            split, index, world["kind"],
            _public_failure_kind(stage, laboratory), laboratory,
        )

    if world["kind"] != "in_library":
        correct = bool(abstain)
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "abstain": abstain,
            "confidence": float(confidence),
            "mechanism_quality": 1.0 if correct else 0.0,
            "prediction_quality": 1.0 if correct else 0.0,
            "far_offset_prediction_quality": 1.0 if correct else 0.0,
            "observed_fit_quality": 1.0 if correct else 0.0,
            "experiment_information_score": 0.0,
            "experiment_jacobian_rank": 0,
            "experiment_condition_number": None,
            "joint_quality": 1.0 if correct else 0.0,
            "robust_joint_quality": 1.0 if correct else 0.0,
            "confidence_calibration_score": float(
                1.0 - (confidence - float(correct)) ** 2
            ),
            "correct_refusal": correct,
            "false_discovery": not correct,
            "acquisition_calls": int(laboratory.calls),
            "acquisition_budget_units": int(laboratory.used),
            "acquired_trace_count": int(sum(
                len(record["offsets_m"]) for record in laboratory.records
            )),
        }

    information = _experiment_information(world, laboratory.records)
    if abstain:
        mechanism = prediction = far_prediction = observed_fit = 0.0
        joint = robust_joint = 0.0
    else:
        mechanism = _mechanism_quality(parameters, world["parameters"])
        prediction = _prediction_quality(world, parameters, False)[0]
        far_prediction = _prediction_quality(world, parameters, True)[0]
        observed_fit = _observed_fit_quality(laboratory, parameters)
        joint = _joint_quality(
            mechanism, prediction, information["information_score"]
        )
        robust_joint = _joint_quality(
            mechanism, far_prediction, information["information_score"]
        )
    return {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "valid": True,
        "abstain": abstain,
        "confidence": float(confidence),
        "mechanism_quality": float(mechanism),
        "prediction_quality": float(prediction),
        "far_offset_prediction_quality": float(far_prediction),
        "observed_fit_quality": float(observed_fit),
        "experiment_information_score": float(
            information["information_score"]
        ),
        "experiment_jacobian_rank": int(information["jacobian_rank"]),
        "experiment_condition_number": information["condition_number"],
        "experiment_log_determinant": information["log_determinant"],
        "reference_experiment_log_determinant": information[
            "reference_log_determinant"
        ],
        "joint_quality": float(joint),
        "robust_joint_quality": float(robust_joint),
        "confidence_calibration_score": float(
            1.0 - (confidence - joint) ** 2
        ),
        "correct_refusal": False,
        "false_discovery": False,
        "acquisition_calls": int(laboratory.calls),
        "acquisition_budget_units": int(laboratory.used),
        "acquired_trace_count": int(sum(
            len(record["offsets_m"]) for record in laboratory.records
        )),
    }


def _normalized_joint(records, field):
    unsupported = sum(row["kind"] != "in_library" for row in records)
    baseline = unsupported / len(records)
    raw = float(np.mean([row[field] for row in records]))
    return float(np.clip(
        (raw - baseline) / (1.0 - baseline), 0.0, 1.0
    ))


def _split_summary(records):
    supported = [row for row in records if row["kind"] == "in_library"]
    unsupported = [row for row in records if row["kind"] != "in_library"]
    return {
        "joint": _normalized_joint(records, "joint_quality"),
        "robust_joint": _normalized_joint(records, "robust_joint_quality"),
        "mechanism": float(np.mean([
            row["mechanism_quality"] for row in supported
        ])),
        "prediction": float(np.mean([
            row["prediction_quality"] for row in supported
        ])),
        "far_prediction": float(np.mean([
            row["far_offset_prediction_quality"] for row in supported
        ])),
        "observed_fit": float(np.mean([
            row["observed_fit_quality"] for row in supported
        ])),
        "information": float(np.mean([
            row["experiment_information_score"] for row in supported
        ])),
        "supported_claim_coverage": float(np.mean([
            not row["abstain"] for row in supported
        ])),
        "false_discovery_rate": float(np.mean([
            row["false_discovery"] for row in unsupported
        ])),
        "correct_refusal_rate": float(np.mean([
            row["correct_refusal"] for row in unsupported
        ])),
        "confidence_calibration": float(np.mean([
            row.get("confidence_calibration_score", 0.0) for row in records
        ])),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "mean_calls": float(np.mean([
            row["acquisition_calls"] for row in records
        ])),
        "mean_budget": float(np.mean([
            row["acquisition_budget_units"] for row in records
        ])),
        "mean_traces": float(np.mean([
            row["acquired_trace_count"] for row in records
        ])),
    }


def evaluate(discover_layered_velocity):
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
        if call_index and hasattr(discover_layered_velocity, "reset_session"):
            discover_layered_velocity.reset_session()
        record = _evaluate_world(
            discover_layered_velocity, spec, split, index
        )
        (development if split == "development" else heldout).append(record)
    dev = _split_summary(development)
    hold = _split_summary(heldout)
    development_valid = dev["valid_count"] == len(development)
    heldout_valid = hold["valid_count"] == len(heldout)
    result = {
        "combined_score": dev["joint"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "raw_score": dev["joint"] if development_valid else 0.0,
        "mechanism_score": dev["mechanism"],
        "development_prediction_score": dev["prediction"],
        "development_far_offset_prediction_score": dev["far_prediction"],
        "development_observed_fit_score": dev["observed_fit"],
        "development_experiment_information_score": dev["information"],
        "robustness_score": (
            dev["robust_joint"] if development_valid else 0.0
        ),
        "development_validation_gap": dev["joint"] - dev["robust_joint"],
        "heldout_policy_score": hold["joint"] if heldout_valid else 0.0,
        "heldout_mechanism_score": hold["mechanism"],
        "heldout_prediction_score": hold["prediction"],
        "heldout_far_offset_prediction_score": hold["far_prediction"],
        "heldout_observed_fit_score": hold["observed_fit"],
        "heldout_experiment_information_score": hold["information"],
        "heldout_robustness_score": (
            hold["robust_joint"] if heldout_valid else 0.0
        ),
        "development_supported_claim_coverage": dev[
            "supported_claim_coverage"
        ],
        "heldout_supported_claim_coverage": hold[
            "supported_claim_coverage"
        ],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": hold["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "heldout_correct_refusal_rate": hold["correct_refusal_rate"],
        "development_confidence_calibration_score": dev[
            "confidence_calibration"
        ],
        "heldout_confidence_calibration_score": hold[
            "confidence_calibration"
        ],
        "development_mean_acquisition_calls": dev["mean_calls"],
        "heldout_mean_acquisition_calls": hold["mean_calls"],
        "development_mean_budget_units": dev["mean_budget"],
        "heldout_mean_budget_units": hold["mean_budget"],
        "development_mean_acquired_traces": dev["mean_traces"],
        "heldout_mean_acquired_traces": hold["mean_traces"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "candidate_world_call_count": len(all_specs),
        "candidate_world_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_world": development + heldout,
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
    if world["kind"] != "in_library":
        return {
            "parameters": np.zeros(9),
            "confidence": 1.0,
            "abstain": True,
        }
    return {
        "parameters": world["parameters"].copy(),
        "confidence": 1.0,
        "abstain": False,
    }
