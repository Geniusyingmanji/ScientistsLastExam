"""Active Lagrangian laboratory for time-dependent ocean-current discovery.

Candidates choose drifter release positions, phases and observation times under a charged
budget. They return a sparse divergence-free streamfunction model or explicitly refuse the
public mode library. Mechanism recovery, velocity/vorticity fields, drifter rollout, temporal
extrapolation, null/model-inadequacy refusal and held-out transfer remain separate.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np


DOMAIN_M = (0.0, 200000.0, 0.0, 200000.0)
DOMAIN_LENGTH_M = 200000.0
DAY_S = 86400.0
RELEASE_TIME_BOUNDS_S = (0.0, 6.0 * DAY_S)
MAX_EXPERIMENT_DURATION_S = 1.5 * DAY_S
MIN_SAMPLE_TIMES = 7
MAX_SAMPLE_TIMES = 21
MIN_DRIFTERS = 1
MAX_DRIFTERS = 6
EXPERIMENT_BUDGET_UNITS = 12
COEFFICIENT_ABS_BOUND_M_S = 0.35


# (m, n, temporal code, period seconds). For coefficient c in m/s,
# psi = c L/pi sin(m*pi*x/L) sin(n*pi*y/L) f(t),
# u = dpsi/dy and v = -dpsi/dx.
MODE_SPECIFICATIONS = (
    (1, 1, "steady", 0.0),
    (1, 1, "cos", 3.0 * DAY_S),
    (1, 1, "sin", 3.0 * DAY_S),
    (1, 2, "steady", 0.0),
    (1, 2, "cos", 2.5 * DAY_S),
    (1, 2, "sin", 2.5 * DAY_S),
    (2, 1, "steady", 0.0),
    (2, 1, "cos", 4.5 * DAY_S),
    (2, 1, "sin", 4.5 * DAY_S),
    (2, 2, "steady", 0.0),
    (2, 2, "cos", 5.5 * DAY_S),
    (2, 2, "sin", 5.5 * DAY_S),
    (1, 3, "steady", 0.0),
    (1, 3, "cos", 3.75 * DAY_S),
    (1, 3, "sin", 3.75 * DAY_S),
    (3, 1, "steady", 0.0),
    (3, 1, "cos", 4.0 * DAY_S),
    (3, 1, "sin", 4.0 * DAY_S),
    (2, 3, "steady", 0.0),
    (2, 3, "cos", 2.8 * DAY_S),
    (2, 3, "sin", 2.8 * DAY_S),
    (3, 2, "steady", 0.0),
    (3, 2, "cos", 5.0 * DAY_S),
    (3, 2, "sin", 5.0 * DAY_S),
    (1, 4, "steady", 0.0),
    (1, 4, "cos", 6.25 * DAY_S),
    (1, 4, "sin", 6.25 * DAY_S),
    (4, 1, "steady", 0.0),
    (4, 1, "cos", 3.3 * DAY_S),
    (4, 1, "sin", 3.3 * DAY_S),
)
N_MODES = len(MODE_SPECIFICATIONS)

TEMPLATE_SUPPORTS = (
    (0, 3, 1, 2),
    (0, 6, 7, 8),
    (3, 9, 4, 5, 10, 11),
    (0, 3, 6, 25, 26),
    (6, 9, 12, 13, 14, 19, 20),
    (0, 15, 16, 17, 22, 23, 28, 29),
)
BASE_COEFFICIENTS = np.asarray((
    0.105, 0.043, -0.035,
    -0.057, -0.029, 0.024,
    0.064, 0.026, 0.022,
    -0.037, 0.017, -0.019,
    0.028, 0.016, -0.015,
    -0.030, -0.014, 0.017,
    0.021, 0.013, 0.012,
    -0.019, -0.012, 0.011,
    0.015, 0.010, -0.012,
    -0.014, 0.009, 0.011,
))


# (seed, template, position-noise standard deviation in metres, kind).
DEVELOPMENT_SPECS = (
    (91009, 0, 125.0, "in_library"),
    (91019, 1, 150.0, "in_library"),
    (91033, 2, 175.0, "in_library"),
    (91079, 3, 162.5, "in_library"),
    (91081, 0, 125.0, "null"),
    (91097, 0, 175.0, "misspecified"),
)
HELDOUT_SPECS = (
    (101003, 4, 250.0, "in_library"),
    (101009, 5, 300.0, "in_library"),
    (101021, 0, 350.0, "in_library"),
    (101041, 0, 250.0, "null"),
    (101051, 0, 350.0, "misspecified"),
)


MISSPECIFIED_MODES = (
    (3, 3, "steady", 0.0),
    (3, 3, "cos", 1.7 * DAY_S),
    (3, 3, "sin", 1.7 * DAY_S),
    (1, 5, "steady", 0.0),
    (5, 1, "cos", 2.2 * DAY_S),
)


def _make_coefficients(seed, template):
    if not 0 <= int(template) < len(TEMPLATE_SUPPORTS):
        raise ValueError("unknown current template")
    rng = np.random.default_rng(int(seed))
    support = np.zeros(N_MODES, dtype=bool)
    support[list(TEMPLATE_SUPPORTS[int(template)])] = True
    coefficients = np.zeros(N_MODES, dtype=float)
    coefficients[support] = BASE_COEFFICIENTS[support] * rng.uniform(
        0.88, 1.12, size=int(np.sum(support))
    )
    return support, coefficients


def _world(spec):
    seed, template, noise, kind = spec
    if kind == "in_library":
        support, coefficients = _make_coefficients(seed, template)
        misspecified = np.zeros(len(MISSPECIFIED_MODES))
    elif kind == "misspecified":
        support = np.zeros(N_MODES, dtype=bool)
        coefficients = np.zeros(N_MODES)
        rng = np.random.default_rng(int(seed) + 5077)
        misspecified = np.asarray((0.072, 0.054, -0.046, 0.036, -0.030))
        misspecified *= rng.uniform(0.90, 1.10, size=len(misspecified))
    else:
        support = np.zeros(N_MODES, dtype=bool)
        coefficients = np.zeros(N_MODES)
        misspecified = np.zeros(len(MISSPECIFIED_MODES))
    return {
        "seed": int(seed),
        "template": int(template),
        "noise": float(noise),
        "kind": str(kind),
        "support": support,
        "coefficients": coefficients,
        "misspecified_coefficients": misspecified,
    }


def _temporal_value(code, period_s, absolute_time_s):
    if code == "steady":
        return np.ones_like(np.asarray(absolute_time_s, dtype=float))
    phase = 2.0 * np.pi * np.asarray(absolute_time_s, dtype=float) / float(period_s)
    if code == "cos":
        return np.cos(phase)
    if code == "sin":
        return np.sin(phase)
    raise ValueError("unknown temporal mode")


def mode_velocity(coefficients, mode_specifications, positions_m, absolute_time_s):
    """Evaluate the public divergence-free velocity expansion in m/s."""
    positions = np.asarray(positions_m, dtype=float)
    if positions.shape[-1:] != (2,):
        raise ValueError("positions must end in an x/y coordinate")
    flat = positions.reshape((-1, 2))
    times = np.asarray(absolute_time_s, dtype=float)
    if times.ndim == 0:
        times = np.full(len(flat), float(times))
    else:
        times = np.broadcast_to(times, positions.shape[:-1]).ravel()
    coefficient_array = np.asarray(coefficients, dtype=float)
    if coefficient_array.shape != (len(mode_specifications),):
        raise ValueError("coefficient vector does not match mode library")
    x = flat[:, 0]
    y = flat[:, 1]
    u = np.zeros(len(flat))
    v = np.zeros(len(flat))
    for coefficient, specification in zip(coefficient_array, mode_specifications):
        if coefficient == 0.0:
            continue
        m, n, code, period = specification
        spatial_x = np.sin(float(m) * np.pi * x / DOMAIN_LENGTH_M)
        spatial_y = np.sin(float(n) * np.pi * y / DOMAIN_LENGTH_M)
        temporal = _temporal_value(code, period, times)
        u += (
            coefficient * float(n) * spatial_x
            * np.cos(float(n) * np.pi * y / DOMAIN_LENGTH_M) * temporal
        )
        v -= (
            coefficient * float(m)
            * np.cos(float(m) * np.pi * x / DOMAIN_LENGTH_M)
            * spatial_y * temporal
        )
    return np.column_stack((u, v)).reshape(positions.shape)


def _world_velocity(world, positions_m, absolute_time_s):
    if world["kind"] == "in_library":
        return mode_velocity(
            world["coefficients"], MODE_SPECIFICATIONS,
            positions_m, absolute_time_s,
        )
    if world["kind"] == "misspecified":
        return mode_velocity(
            world["misspecified_coefficients"], MISSPECIFIED_MODES,
            positions_m, absolute_time_s,
        )
    return np.zeros_like(np.asarray(positions_m, dtype=float))


def _rk4_step(velocity_function, positions, absolute_time, step_s):
    k1 = velocity_function(positions, absolute_time)
    k2 = velocity_function(
        positions + 0.5 * step_s * k1, absolute_time + 0.5 * step_s
    )
    k3 = velocity_function(
        positions + 0.5 * step_s * k2, absolute_time + 0.5 * step_s
    )
    k4 = velocity_function(positions + step_s * k3, absolute_time + step_s)
    updated = positions + step_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    updated[:, 0] = np.clip(updated[:, 0], DOMAIN_M[0], DOMAIN_M[1])
    updated[:, 1] = np.clip(updated[:, 1], DOMAIN_M[2], DOMAIN_M[3])
    return updated


def _simulate(world, initial_positions_m, release_time_s, sample_times_s,
              candidate_coefficients=None):
    initial = np.asarray(initial_positions_m, dtype=float)
    relative_times = np.asarray(sample_times_s, dtype=float)
    if candidate_coefficients is None:
        velocity = lambda positions, time: _world_velocity(world, positions, time)
    else:
        velocity = lambda positions, time: mode_velocity(
            candidate_coefficients, MODE_SPECIFICATIONS, positions, time
        )
    trajectory = np.empty((len(initial), len(relative_times), 2), dtype=float)
    trajectory[:, 0, :] = initial
    positions = initial.copy()
    current = 0.0
    for index in range(1, len(relative_times)):
        target = float(relative_times[index])
        interval = target - current
        n_steps = max(1, int(math.ceil(interval / 1800.0)))
        step = interval / n_steps
        for local in range(n_steps):
            positions = _rk4_step(
                velocity, positions,
                float(release_time_s) + current + local * step,
                step,
            )
        current = target
        trajectory[:, index, :] = positions
    return trajectory


def _query_seed(world_seed, call_index, initial, release_time, sample_times):
    payload = np.concatenate((
        np.asarray((release_time,), dtype="<f8"),
        np.asarray(initial, dtype="<f8").ravel(),
        np.asarray(sample_times, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _DrifterLaboratory:
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

    def observe(self, initial_positions_m, release_time_s, sample_times_s):
        try:
            initial = np.asarray(initial_positions_m, dtype=float)
        except (TypeError, ValueError, OverflowError):
            self._reject("initial drifter positions must be numeric")
        if initial.ndim != 2 or initial.shape[1:] != (2,) or not (
            MIN_DRIFTERS <= len(initial) <= MAX_DRIFTERS
        ):
            self._reject("initial_positions_m must have shape (1-6,2)")
        if np.any(~np.isfinite(initial)):
            self._reject("initial drifter positions must be finite")
        margin = 5000.0
        if np.any(initial[:, 0] < DOMAIN_M[0] + margin) or np.any(
            initial[:, 0] > DOMAIN_M[1] - margin
        ) or np.any(initial[:, 1] < DOMAIN_M[2] + margin) or np.any(
            initial[:, 1] > DOMAIN_M[3] - margin
        ):
            self._reject("initial drifters must lie inside the public interior")
        try:
            release = float(release_time_s)
        except (TypeError, ValueError, OverflowError):
            self._reject("release time must be numeric")
        if not math.isfinite(release) or not (
            RELEASE_TIME_BOUNDS_S[0] <= release <= RELEASE_TIME_BOUNDS_S[1]
        ):
            self._reject("release time outside public bounds")
        try:
            times = np.asarray(sample_times_s, dtype=float)
        except (TypeError, ValueError, OverflowError):
            self._reject("sample times must be numeric")
        if times.ndim != 1 or not (
            MIN_SAMPLE_TIMES <= len(times) <= MAX_SAMPLE_TIMES
        ):
            self._reject("sample_times_s must contain 7-21 times")
        if np.any(~np.isfinite(times)) or abs(float(times[0])) > 1e-12:
            self._reject("sample times must be finite and start at zero")
        if np.any(np.diff(times) <= 0.0) or float(times[-1]) > MAX_EXPERIMENT_DURATION_S:
            self._reject("sample times must increase within the public duration")
        cost = 1 + len(initial) + int(math.ceil(len(times) / 8.0))
        if self.used + cost > EXPERIMENT_BUDGET_UNITS:
            self._reject("drifter experiment budget exceeded", RuntimeError)
        self.used += cost
        self.calls += 1
        clean = _simulate(self.world, initial, release, times)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, initial, release, times
        ))
        # Initial release locations are known by construction; noise applies after release.
        observed = clean.copy()
        observed[:, 1:, :] += rng.normal(
            scale=self.world["noise"], size=observed[:, 1:, :].shape
        )
        observed[:, :, 0] = np.clip(observed[:, :, 0], DOMAIN_M[0], DOMAIN_M[1])
        observed[:, :, 1] = np.clip(observed[:, :, 1], DOMAIN_M[2], DOMAIN_M[3])
        return {
            "initial_positions_m": initial.copy(),
            "release_time_s": release,
            "time_s": times.copy(),
            "trajectories_m": observed,
            "position_noise_std_m": float(self.world["noise"]),
            "budget_cost": int(cost),
        }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    coefficients = np.asarray(submission.get("coefficients_m_s"), dtype=float)
    support_raw = np.asarray(submission.get("support"), dtype=float)
    for name, value in (("coefficients_m_s", coefficients), ("support", support_raw)):
        if value.shape != (N_MODES,) or np.any(~np.isfinite(value)):
            raise ValueError("%s must be a finite length-%d array" % (name, N_MODES))
    if np.any(support_raw < 0.0) or np.any(support_raw > 1.0) or np.any(
        support_raw != np.rint(support_raw)
    ):
        raise ValueError("support must contain exact zero/one labels")
    support = support_raw.astype(bool)
    abstain = bool(submission["abstain"])
    if abstain:
        if np.any(support):
            raise ValueError("abstention requires empty support")
        return np.zeros(N_MODES), support, confidence, True
    if not np.any(support):
        raise ValueError("a non-abstaining current needs at least one active mode")
    if np.any(np.abs(coefficients[support]) < 0.005) or np.any(
        np.abs(coefficients[support]) > COEFFICIENT_ABS_BOUND_M_S
    ):
        raise ValueError("active coefficients outside public magnitude bounds")
    coefficients = np.where(support, coefficients, 0.0)
    return coefficients, support, confidence, False


def _mechanism_metrics(world, coefficients, predicted_support, abstain):
    if world["kind"] in {"null", "misspecified"}:
        correct = bool(abstain and not np.any(predicted_support))
        return {
            "support_f1": 1.0 if correct else 0.0,
            "velocity_mode_score": 1.0 if correct else 0.0,
            "vorticity_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        }
    truth_support = world["support"]
    if abstain:
        return {
            "support_f1": 0.0,
            "velocity_mode_score": 0.0,
            "vorticity_score": 0.0,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
        }
    tp = int(np.sum(truth_support & predicted_support))
    fp = int(np.sum(~truth_support & predicted_support))
    fn = int(np.sum(truth_support & ~predicted_support))
    if tp == 0:
        support_f1 = 0.0
    else:
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        support_f1 = 2.0 * precision * recall / (precision + recall)

    grid = np.linspace(10000.0, 190000.0, 11)
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    positions = np.column_stack((xx.ravel(), yy.ravel()))
    times = (0.0, 1.25 * DAY_S, 3.5 * DAY_S, 7.75 * DAY_S)
    true_velocity = np.concatenate([
        mode_velocity(world["coefficients"], MODE_SPECIFICATIONS, positions, time).ravel()
        for time in times
    ])
    predicted_velocity = np.concatenate([
        mode_velocity(coefficients, MODE_SPECIFICATIONS, positions, time).ravel()
        for time in times
    ])
    scale = max(0.01, float(np.sqrt(np.mean(true_velocity**2))))
    velocity_error = float(np.sqrt(np.mean(
        (predicted_velocity - true_velocity) ** 2
    ))) / scale
    velocity_score = math.exp(-0.5 * (velocity_error / 0.35) ** 2)

    # For each public mode, vorticity amplitude scales with (m^2+n^2)*coefficient.
    true_vorticity = np.asarray([
        (mode[0] ** 2 + mode[1] ** 2) * coefficient
        for mode, coefficient in zip(MODE_SPECIFICATIONS, world["coefficients"])
    ])
    predicted_vorticity = np.asarray([
        (mode[0] ** 2 + mode[1] ** 2) * coefficient
        for mode, coefficient in zip(MODE_SPECIFICATIONS, coefficients)
    ])
    vorticity_scale = max(0.02, float(np.linalg.norm(true_vorticity)))
    vorticity_error = float(np.linalg.norm(
        predicted_vorticity - true_vorticity
    )) / vorticity_scale
    vorticity_score = math.exp(-0.5 * (vorticity_error / 0.40) ** 2)
    mechanism = 0.45 * support_f1 + 0.35 * velocity_score + 0.20 * vorticity_score
    return {
        "support_f1": float(support_f1),
        "velocity_mode_score": float(velocity_score),
        "vorticity_score": float(vorticity_score),
        "mechanism_score": float(mechanism),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _field_prediction_score(world, coefficients, extrapolation):
    rng = np.random.default_rng(
        world["seed"] + (130003 if extrapolation else 120011)
    )
    positions = rng.uniform(8000.0, 192000.0, size=(128, 2))
    times = (
        (8.0 * DAY_S, 10.5 * DAY_S, 13.0 * DAY_S)
        if extrapolation else (0.75 * DAY_S, 2.25 * DAY_S, 5.5 * DAY_S)
    )
    errors = []
    baseline = []
    for time in times:
        truth = _world_velocity(world, positions, time)
        prediction = mode_velocity(
            coefficients, MODE_SPECIFICATIONS, positions, time
        )
        errors.extend((prediction - truth).ravel().tolist())
        baseline.extend(truth.ravel().tolist())
    rmse = float(np.sqrt(np.mean(np.asarray(errors) ** 2)))
    baseline_rmse = max(0.015, float(np.sqrt(np.mean(np.asarray(baseline) ** 2))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _trajectory_prediction_score(world, coefficients, extrapolation):
    rng = np.random.default_rng(
        world["seed"] + (150001 if extrapolation else 140009)
    )
    initial = rng.uniform(15000.0, 185000.0, size=(8, 2))
    release = 9.0 * DAY_S if extrapolation else 4.25 * DAY_S
    duration = 5.0 * DAY_S if extrapolation else 2.5 * DAY_S
    times = np.linspace(0.0, duration, 21)
    truth = _simulate(world, initial, release, times)
    prediction = _simulate(
        world, initial, release, times, candidate_coefficients=coefficients
    )
    zero = np.repeat(initial[:, None, :], len(times), axis=1)
    rmse = float(np.sqrt(np.mean((prediction - truth) ** 2)))
    baseline_rmse = max(500.0, float(np.sqrt(np.mean((zero - truth) ** 2))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _reference_submission(world):
    if world["kind"] != "in_library":
        return {
            "coefficients_m_s": np.zeros(N_MODES),
            "support": np.zeros(N_MODES, dtype=int),
            "confidence": 0.0,
            "abstain": True,
        }
    return {
        "coefficients_m_s": world["coefficients"].copy(),
        "support": world["support"].astype(int),
        "confidence": 1.0,
        "abstain": False,
    }


def _evaluate_world(discover_currents, spec, split, index):
    world = _world(spec)
    laboratory = _DrifterLaboratory(world)
    try:
        submission = discover_currents(
            DOMAIN_M, MODE_SPECIFICATIONS, laboratory.observe,
            EXPERIMENT_BUDGET_UNITS,
        )
        coefficients, support, confidence, abstain = _validate_submission(submission)
        if laboratory.violated:
            raise RuntimeError(
                laboratory.failure_reason or "invalid drifter experiment"
            )
        mechanism = _mechanism_metrics(world, coefficients, support, abstain)
        field = _field_prediction_score(world, coefficients, False)
        field_extra = _field_prediction_score(world, coefficients, True)
        trajectory = _trajectory_prediction_score(world, coefficients, False)
        trajectory_extra = _trajectory_prediction_score(world, coefficients, True)
        target_confidence = (
            mechanism["mechanism_score"]
            if world["kind"] == "in_library" else 0.0
        )
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "support_f1": round(mechanism["support_f1"], 6),
            "velocity_mode_score": round(mechanism["velocity_mode_score"], 6),
            "vorticity_score": round(mechanism["vorticity_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "field_prediction_score": round(field, 6),
            "field_extrapolation_score": round(field_extra, 6),
            "trajectory_prediction_score": round(trajectory, 6),
            "trajectory_extrapolation_score": round(trajectory_extra, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - target_confidence) ** 2, 6
            ),
            "correct_refusal": mechanism["correct_refusal"],
            "false_discovery": mechanism["false_discovery"],
            "abstained": abstain,
            "confidence": round(confidence, 6),
            "n_true_modes": int(np.sum(world["support"])),
            "n_predicted_modes": int(np.sum(support)),
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
            "support_f1": 0.0,
            "velocity_mode_score": 0.0,
            "vorticity_score": 0.0,
            "mechanism_score": 0.0,
            "field_prediction_score": 0.0,
            "field_extrapolation_score": 0.0,
            "trajectory_prediction_score": 0.0,
            "trajectory_extrapolation_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "n_true_modes": int(np.sum(world["support"])),
            "n_predicted_modes": 0,
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
    misspecified = [row for row in records if row["kind"] == "misspecified"]
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "support_f1": float(np.mean([row["support_f1"] for row in supported])),
        "velocity_mode": float(np.mean([
            row["velocity_mode_score"] for row in supported
        ])),
        "vorticity": float(np.mean([
            row["vorticity_score"] for row in supported
        ])),
        "field_prediction": float(np.mean([
            row["field_prediction_score"] for row in supported
        ])),
        "field_extrapolation": float(np.mean([
            row["field_extrapolation_score"] for row in supported
        ])),
        "trajectory_prediction": float(np.mean([
            row["trajectory_prediction_score"] for row in supported
        ])),
        "trajectory_extrapolation": float(np.mean([
            row["trajectory_extrapolation_score"] for row in supported
        ])),
        "misspecified_trajectory_prediction": float(np.mean([
            row["trajectory_prediction_score"] for row in misspecified
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


def _reset_candidate_session(discover_currents):
    reset = getattr(discover_currents, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(discover_currents):
    development = []
    heldout = []
    first_world = True
    for split, specs, records in (
        ("development", DEVELOPMENT_SPECS, development),
        ("heldout", HELDOUT_SPECS, heldout),
    ):
        for index, spec in enumerate(specs):
            if not first_world:
                _reset_candidate_session(discover_currents)
            first_world = False
            records.append(
                _evaluate_world(discover_currents, spec, split, index)
            )
    dev = _split_summary(
        development,
        sum(spec[3] != "in_library" for spec in DEVELOPMENT_SPECS),
    )
    hold = _split_summary(
        heldout, sum(spec[3] != "in_library" for spec in HELDOUT_SPECS),
    )
    all_records = development + heldout
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized_mechanism"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "development_support_f1": dev["support_f1"],
        "development_velocity_mode_score": dev["velocity_mode"],
        "development_vorticity_score": dev["vorticity"],
        "development_field_prediction_score": dev["field_prediction"],
        "development_field_extrapolation_score": dev["field_extrapolation"],
        "development_trajectory_prediction_score": dev["trajectory_prediction"],
        "development_trajectory_extrapolation_score": dev["trajectory_extrapolation"],
        "development_misspecified_trajectory_score": (
            dev["misspecified_trajectory_prediction"]
        ),
        "development_confidence_calibration_score": dev["confidence_calibration"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "robustness_score": hold["normalized_mechanism"] if hold_valid else 0.0,
        "heldout_mechanism_score": hold["raw_mechanism"],
        "heldout_support_f1": hold["support_f1"],
        "heldout_velocity_mode_score": hold["velocity_mode"],
        "heldout_vorticity_score": hold["vorticity"],
        "heldout_field_prediction_score": hold["field_prediction"],
        "heldout_field_extrapolation_score": hold["field_extrapolation"],
        "heldout_trajectory_prediction_score": hold["trajectory_prediction"],
        "heldout_trajectory_extrapolation_score": hold["trajectory_extrapolation"],
        "heldout_misspecified_trajectory_score": (
            hold["misspecified_trajectory_prediction"]
        ),
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
