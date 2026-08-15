"""Trusted multi-regime low-thrust trajectory-design oracle.

The candidate returns a compact, bounded local-orbital-frame guidance law.  The trusted
simulator propagates modified equinoctial elements (MEE) and propellant mass without repairing
invalid controls.  Nominal development utility controls search; held-out transfer, terminal
phase, and actuator/navigation/J2 shifts remain evaluator-only diagnostics.

The hidden coefficient tables below are attainable mission generators, not optimal controls or
fuel anchors.  They create deterministic procedural targets and demonstrate reachability.  The
normalization upper bound is the unattainable ideal of exact arrival at zero delta-v, leaving
room for a candidate to improve on every reference witness.
"""

from __future__ import annotations

import functools
import math

import numpy as np


MU_EARTH_M3_S2 = 3.986004418e14
EARTH_RADIUS_M = 6378137.0
J2_EARTH = 1.08262668e-3
G0_M_S2 = 9.80665
N_SEGMENTS = 4
# A calibration-only 900-second construction propagation and independent Cartesian refinement
# bound the 1800-second production error to a small fraction of every terminal tolerance.
INTEGRATION_STEP_S = 1800.0
MINIMUM_ALTITUDE_M = 150000.0
MINIMUM_MASS_FRACTION = 0.50
EFFICIENCY_SCALE_M_S = 2000.0


# Search-visible labels are deliberately absent.  The order interleaves development and
# held-out families, and secure evaluation resets candidate state between instances.
SCENARIO_SPECS = (
    ("dev_raise", "development", 51031, "raise"),
    ("heldout_lower", "heldout", 61043, "lower"),
    ("dev_eccentric", "development", 51047, "eccentric"),
    ("dev_plane", "development", 51059, "plane"),
    ("heldout_combined", "heldout", 61051, "held_combined"),
    ("dev_combined", "development", 51071, "combined"),
)


# Each row is (tangential constant, radial sin/cos, tangential sin/cos,
# normal sin/cos).  Small seed-dependent perturbations are added in _seeded_copy.
FAMILY_SPECS = {
    "raise": {
        "orbit": (7000e3, 0.010, 2.0, 15.0, 20.0, 50.0),
        "mass_kg": 240.0, "thrust_n": 0.22, "isp_s": 1800.0,
        "duration_days": 14.0,
        "coefficients": ((0.55, 0, 0, 0, 0, 0, 0),) * N_SEGMENTS,
    },
    "eccentric": {
        "orbit": (9000e3, 0.050, 7.0, 40.0, 10.0, 80.0),
        "mass_kg": 310.0, "thrust_n": 0.25, "isp_s": 2100.0,
        "duration_days": 18.0,
        "coefficients": (
            (0.32, 0.34, -0.08, 0.12, 0.25, 0, 0),
            (0.30, 0.30, -0.05, 0.10, 0.28, 0, 0),
            (0.26, 0.26, 0.00, 0.06, 0.30, 0, 0),
            (0.18, 0.18, 0.02, 0.03, 0.24, 0, 0),
        ),
    },
    "plane": {
        "orbit": (8000e3, 0.025, 4.0, 25.0, 35.0, 110.0),
        "mass_kg": 280.0, "thrust_n": 0.20, "isp_s": 1900.0,
        "duration_days": 22.0,
        "coefficients": (
            (0.28, 0, 0, 0, 0, 0.18, 0.52),
            (0.30, 0, 0, 0, 0, 0.20, 0.50),
            (0.24, 0, 0, 0, 0, 0.22, 0.46),
            (0.18, 0, 0, 0, 0, 0.18, 0.40),
        ),
    },
    "combined": {
        "orbit": (11000e3, 0.120, 12.0, 65.0, 20.0, 150.0),
        "mass_kg": 420.0, "thrust_n": 0.34, "isp_s": 2300.0,
        "duration_days": 26.0,
        "coefficients": (
            (0.45, -0.16, 0.22, 0.08, -0.18, 0.24, 0.38),
            (0.40, -0.12, 0.18, 0.05, -0.16, 0.28, 0.34),
            (0.32, -0.08, 0.14, 0.02, -0.12, 0.25, 0.30),
            (0.22, -0.04, 0.10, 0.00, -0.08, 0.18, 0.24),
        ),
    },
    "lower": {
        "orbit": (9800e3, 0.080, 9.0, 120.0, 45.0, 200.0),
        "mass_kg": 260.0, "thrust_n": 0.21, "isp_s": 2000.0,
        "duration_days": 20.0,
        "coefficients": (
            (-0.46, 0.08, -0.16, -0.08, 0.18, -0.15, -0.32),
            (-0.42, 0.06, -0.14, -0.06, 0.16, -0.18, -0.30),
            (-0.35, 0.04, -0.10, -0.04, 0.12, -0.18, -0.26),
            (-0.24, 0.02, -0.06, -0.02, 0.08, -0.12, -0.18),
        ),
    },
    "held_combined": {
        "orbit": (13500e3, 0.180, 18.0, 210.0, 70.0, 280.0),
        "mass_kg": 500.0, "thrust_n": 0.42, "isp_s": 2500.0,
        "duration_days": 28.0,
        "coefficients": (
            (-0.30, 0.22, 0.18, 0.10, -0.20, -0.20, -0.35),
            (-0.28, 0.20, 0.16, 0.08, -0.18, -0.18, -0.32),
            (-0.22, 0.16, 0.12, 0.04, -0.14, -0.15, -0.27),
            (-0.15, 0.10, 0.08, 0.02, -0.10, -0.10, -0.20),
        ),
    },
}


# Frozen from the task-construction generator on 2026-07-22 using the equations in this file
# and then independently repropagated by ``scripts/calibrate_low_thrust_v2.py``.  Keeping these
# attainable targets literal prevents target generation from consuming candidate evaluation
# time.  Longitude is retained for the sealed phase diagnostic; nominal utility uses the first
# five elements because the public task is orbit transfer rather than timed rendezvous.
FROZEN_TARGETS = {
    "dev_raise": (
        8318426.324316001, -0.002719298301671085, 0.007326746682113743,
        0.009401011915140381, -0.01763360973838197, 4.204170583803226,
    ),
    "heldout_lower": (
        8380370.083942229, -0.03782737562278188, -0.0358539680562317,
        0.026928757428204962, 0.06929791282950183, 2.235862968075658,
    ),
    "dev_eccentric": (
        9910423.99176705, 0.05946206484221006, 0.08892318145240172,
        0.06315969274115414, -0.0031703264162364748, 3.4819023916598653,
    ),
    "dev_plane": (
        8850979.813595474, -0.01750973558724617, 0.0143858485102522,
        0.04167261113820374, -0.036309937740950746, 5.309935008524221,
    ),
    "heldout_combined": (
        11036999.958345696, 0.09023980092078482, -0.18644348481553522,
        -0.18993503641332013, -0.011244255056378858, 2.806120020340387,
    ),
    "dev_combined": (
        13552532.48784027, -0.08326144090550705, 0.0679799639571284,
        0.11118774200498148, 0.08380500779827853, 5.806525183462696,
    ),
}


# Corresponding zero-thrust terminal accuracies.  They are retained rather than rounded to
# zero so the normalization is exactly reproducible, although every value is scientifically
# negligible and the zero-thrust baseline receives score zero.
FROZEN_BASELINE_UTILITIES = {
    "dev_raise": 2.9511864713404093e-30,
    "heldout_lower": 5.610724242732624e-35,
    "dev_eccentric": 1.3094881577732248e-14,
    "dev_plane": 2.1505883809933296e-14,
    "heldout_combined": 5.696023163706691e-40,
    "dev_combined": 4.555897853981541e-55,
}

# Utility of the reference witness on each scenario: the finite-thrust profile that made the
# target reachable, repropagated through the same dynamics and scored the same way. Frozen here
# rather than recomputed per run for the same reason the baselines are - the value is a property
# of the scenario, and recomputing it would spend six propagations on every evaluation.
#
# Reproduce with:
#     python scripts/measure_reference.py --task Engineering/LowThrustTransfer \
#         --reference solution.py --entry design_guidance
# and the witness numbers with the snippet in references/known_best.md.
FROZEN_REFERENCE_UTILITIES = {
    "dev_raise": 0.7355590266,
    "heldout_lower": 0.7345660848,
    "dev_eccentric": 0.8103903732,
    "dev_plane": 0.7473029816,
    "heldout_combined": 0.6969522546,
    "dev_combined": 0.6457521012,
}


SHIFT_SPECS = (
    {
        "name": "underthrust_navigation",
        "thrust_scale": 0.98,
        "isp_scale": 0.96,
        "j2_scale": 0.985,
        "duration_scale": 1.0,
        "j2": True,
        "radial_tangential_rotation_rad": math.radians(0.5),
        "tangential_normal_rotation_rad": math.radians(-0.3),
        "initial_offset": (800.0, 6.0e-5, -4.0e-5, 2.0e-5, -2.0e-5, 0.0),
    },
    {
        "name": "overthrust_misalignment",
        "thrust_scale": 1.02,
        "isp_scale": 0.97,
        "j2_scale": 1.015,
        "duration_scale": 1.0,
        "j2": True,
        "radial_tangential_rotation_rad": math.radians(-0.7),
        "tangential_normal_rotation_rad": math.radians(0.5),
        "initial_offset": (-700.0, -4.0e-5, 6.0e-5, -2.0e-5, 3.0e-5, 0.0),
    },
    {
        "name": "early_cutoff_navigation",
        "thrust_scale": 0.99,
        "isp_scale": 0.95,
        "j2_scale": 0.990,
        "duration_scale": 0.995,
        "j2": True,
        "radial_tangential_rotation_rad": math.radians(0.35),
        "tangential_normal_rotation_rad": math.radians(0.4),
        "initial_offset": (1200.0, 8.0e-5, 6.0e-5, 3.0e-5, -3.0e-5, 0.001),
    },
)


def _wrap_angle(angle):
    return float((float(angle) + math.pi) % (2.0 * math.pi) - math.pi)


def classical_to_mee(semimajor_axis_m, eccentricity, inclination_rad,
                     raan_rad, argument_of_periapsis_rad, true_anomaly_rad):
    """Convert nonsingular classical elements to Walker modified equinoctial elements."""
    longitude_of_periapsis = float(raan_rad) + float(argument_of_periapsis_rad)
    tangent = math.tan(0.5 * float(inclination_rad))
    return np.asarray((
        float(semimajor_axis_m) * (1.0 - float(eccentricity) ** 2),
        float(eccentricity) * math.cos(longitude_of_periapsis),
        float(eccentricity) * math.sin(longitude_of_periapsis),
        tangent * math.cos(float(raan_rad)),
        tangent * math.sin(float(raan_rad)),
        float(raan_rad) + float(argument_of_periapsis_rad) + float(true_anomaly_rad),
    ), dtype=float)


def mee_to_cartesian(elements, mu=MU_EARTH_M3_S2):
    """Convert prograde MEE to Cartesian position and velocity."""
    p, f, g, h, k, longitude = np.asarray(elements, dtype=float)
    cosine, sine = math.cos(longitude), math.sin(longitude)
    s_squared = 1.0 + h * h + k * k
    w = 1.0 + f * cosine + g * sine
    if p <= 0.0 or w <= 0.0:
        raise ValueError("invalid equinoctial orbit")
    f_hat = np.asarray((1.0 - k * k + h * h, 2.0 * h * k, -2.0 * k)) / s_squared
    g_hat = np.asarray((2.0 * h * k, 1.0 + k * k - h * h, 2.0 * h)) / s_squared
    position = p / w * (cosine * f_hat + sine * g_hat)
    velocity = math.sqrt(float(mu) / p) * (
        -(g + sine) * f_hat + (f + cosine) * g_hat
    )
    return position, velocity


def _local_basis(elements):
    p, f, g, h, k, longitude = np.asarray(elements, dtype=float)
    del p, f, g
    cosine, sine = math.cos(longitude), math.sin(longitude)
    s_squared = 1.0 + h * h + k * k
    f_hat = np.asarray((1.0 - k * k + h * h, 2.0 * h * k, -2.0 * k)) / s_squared
    g_hat = np.asarray((2.0 * h * k, 1.0 + k * k - h * h, 2.0 * h)) / s_squared
    radial = cosine * f_hat + sine * g_hat
    transverse = -sine * f_hat + cosine * g_hat
    normal = np.cross(radial, transverse)
    return radial, transverse, normal


def _control_components(row, longitude):
    row = np.asarray(row, dtype=float)
    sine, cosine = math.sin(float(longitude)), math.cos(float(longitude))
    return np.asarray((
        row[1] * sine + row[2] * cosine,
        row[0] + row[3] * sine + row[4] * cosine,
        row[5] * sine + row[6] * cosine,
    ), dtype=float)


def _maximum_control_norm(row):
    """Return the all-longitude maximum via every stationary point.

    The squared norm is a degree-two trigonometric polynomial.  Substituting
    ``t=tan(L/2)`` in its derivative gives a quartic.  Evaluating all real roots plus the
    finite chart boundaries avoids a sampled-thrust loophole.
    """
    row = np.asarray(row, dtype=float)
    constant = float(row[0])
    sine_coefficients = np.asarray((row[1], row[3], row[5]), dtype=float)
    cosine_coefficients = np.asarray((row[2], row[4], row[6]), dtype=float)
    sine_squared = float(np.dot(sine_coefficients, sine_coefficients))
    cosine_squared = float(np.dot(cosine_coefficients, cosine_coefficients))
    cross = float(np.dot(sine_coefficients, cosine_coefficients))
    constant_sine = constant * float(row[3])
    constant_cosine = constant * float(row[4])
    difference = sine_squared - cosine_squared
    # Ascending coefficients of the half-angle derivative polynomial.
    ascending = np.asarray((
        cross + constant_sine,
        2.0 * difference - 2.0 * constant_cosine,
        -6.0 * cross,
        -2.0 * difference - 2.0 * constant_cosine,
        cross - constant_sine,
    ))
    nonzero = np.flatnonzero(np.abs(ascending) > 1.0e-15)
    longitudes = [0.0, math.pi]
    if len(nonzero):
        roots = np.roots(ascending[:nonzero[-1] + 1][::-1])
        longitudes.extend(
            2.0 * math.atan(float(root.real))
            for root in roots if abs(float(root.imag)) <= 1.0e-9
        )
    maximum_squared = max(
        float(np.dot(vector, vector))
        for vector in (_control_components(row, longitude) for longitude in longitudes)
    )
    return math.sqrt(max(0.0, maximum_squared))


def _validate_coefficients(value):
    coefficients = np.asarray(value, dtype=float)
    if coefficients.shape != (N_SEGMENTS, 7):
        raise ValueError("guidance must have shape (n_segments, 7)")
    if np.any(~np.isfinite(coefficients)):
        raise ValueError("guidance contains non-finite coefficients")
    if np.any(np.abs(coefficients) > 1.25):
        raise ValueError("individual guidance coefficient exceeds 1.25")
    maxima = np.asarray([_maximum_control_norm(row) for row in coefficients])
    if np.any(maxima > 1.0 + 2.0e-10):
        raise ValueError("resultant normalized thrust exceeds one")
    return coefficients, float(np.max(maxima))


def _j2_local_acceleration(elements, j2_scale=1.0):
    position, _ = mee_to_cartesian(elements)
    radius = float(np.linalg.norm(position))
    z_ratio_squared = float(position[2] ** 2 / radius ** 2)
    factor = (
        1.5 * J2_EARTH * float(j2_scale) * MU_EARTH_M3_S2
        * EARTH_RADIUS_M ** 2 / radius ** 5
    )
    acceleration = factor * np.asarray((
        position[0] * (5.0 * z_ratio_squared - 1.0),
        position[1] * (5.0 * z_ratio_squared - 1.0),
        position[2] * (5.0 * z_ratio_squared - 3.0),
    ))
    radial, transverse, normal = _local_basis(elements)
    return np.asarray((
        np.dot(acceleration, radial),
        np.dot(acceleration, transverse),
        np.dot(acceleration, normal),
    ), dtype=float)


def _rotate_control(control, shift):
    radial, transverse, normal = np.asarray(control, dtype=float)
    angle = float(shift.get("radial_tangential_rotation_rad", 0.0))
    cosine, sine = math.cos(angle), math.sin(angle)
    radial, transverse = (
        cosine * radial - sine * transverse,
        sine * radial + cosine * transverse,
    )
    angle = float(shift.get("tangential_normal_rotation_rad", 0.0))
    cosine, sine = math.cos(angle), math.sin(angle)
    transverse, normal = (
        cosine * transverse - sine * normal,
        sine * transverse + cosine * normal,
    )
    return np.asarray((radial, transverse, normal), dtype=float)


def _derivative(state, coefficient_row, scenario, shift):
    p, f, g, h, k, longitude, mass = np.asarray(state, dtype=float)
    cosine, sine = math.cos(longitude), math.sin(longitude)
    w = 1.0 + f * cosine + g * sine
    s_squared = 1.0 + h * h + k * k
    if p <= 0.0 or w <= 0.0 or mass <= 0.0:
        raise ValueError("trajectory left the valid prograde elliptic domain")

    normalized = _rotate_control(_control_components(coefficient_row, longitude), shift)
    thrust = float(scenario["maximum_thrust_n"]) * float(shift.get("thrust_scale", 1.0))
    acceleration = thrust / mass * normalized
    if bool(shift.get("j2", False)):
        acceleration = acceleration + _j2_local_acceleration(
            state[:6], shift.get("j2_scale", 1.0)
        )
    radial_acceleration, transverse_acceleration, normal_acceleration = acceleration

    root = math.sqrt(p / MU_EARTH_M3_S2)
    normal_coupling = h * sine - k * cosine
    derivatives = np.empty(7, dtype=float)
    derivatives[0] = root * 2.0 * p / w * transverse_acceleration
    derivatives[1] = root * (
        radial_acceleration * sine
        + (((w + 1.0) * cosine + f) / w) * transverse_acceleration
        - (normal_coupling * g / w) * normal_acceleration
    )
    derivatives[2] = root * (
        -radial_acceleration * cosine
        + (((w + 1.0) * sine + g) / w) * transverse_acceleration
        + (normal_coupling * f / w) * normal_acceleration
    )
    derivatives[3] = root * s_squared / (2.0 * w) * cosine * normal_acceleration
    derivatives[4] = root * s_squared / (2.0 * w) * sine * normal_acceleration
    derivatives[5] = (
        math.sqrt(MU_EARTH_M3_S2 * p) * (w / p) ** 2
        + root * normal_coupling / w * normal_acceleration
    )
    isp = float(scenario["specific_impulse_s"]) * float(shift.get("isp_scale", 1.0))
    derivatives[6] = -thrust * float(np.linalg.norm(normalized)) / (isp * G0_M_S2)
    return derivatives


def _orbit_altitudes(elements):
    p, f, g = np.asarray(elements, dtype=float)[:3]
    eccentricity = math.hypot(f, g)
    if eccentricity >= 1.0 or p <= 0.0:
        return -math.inf, math.inf
    return p / (1.0 + eccentricity) - EARTH_RADIUS_M, p / (1.0 - eccentricity) - EARTH_RADIUS_M


def _propagate(scenario, coefficients, shift=None):
    # J2 is part of the documented nominal Earth model, not an evaluator-only surprise.
    shift = {"j2": True, **dict(shift or {})}
    state = np.concatenate((
        np.asarray(scenario["initial_elements"], dtype=float),
        np.asarray((scenario["initial_mass_kg"],), dtype=float),
    ))
    state[:6] += np.asarray(shift.get("initial_offset", (0.0,) * 6), dtype=float)
    nominal_duration = float(scenario["duration_s"])
    final_time = nominal_duration * float(shift.get("duration_scale", 1.0))
    segment_duration = nominal_duration / N_SEGMENTS
    time = 0.0
    minimum_altitude, maximum_altitude = _orbit_altitudes(state[:6])
    minimum_mass = float(state[6])

    while time < final_time - 1.0e-9:
        segment = min(N_SEGMENTS - 1, int(max(0.0, time) / segment_duration))
        boundary = min(final_time, (segment + 1) * segment_duration)
        if boundary <= time + 1.0e-9:
            boundary = final_time
        step = min(INTEGRATION_STEP_S, boundary - time, final_time - time)
        if step <= 1.0e-10:
            time = boundary
            continue
        row = coefficients[segment]
        k1 = _derivative(state, row, scenario, shift)
        k2 = _derivative(state + 0.5 * step * k1, row, scenario, shift)
        k3 = _derivative(state + 0.5 * step * k2, row, scenario, shift)
        k4 = _derivative(state + step * k3, row, scenario, shift)
        state = state + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        time += step
        if np.any(~np.isfinite(state)):
            raise ValueError("trajectory became non-finite")
        perigee, apogee = _orbit_altitudes(state[:6])
        minimum_altitude = min(minimum_altitude, perigee)
        maximum_altitude = max(maximum_altitude, apogee)
        minimum_mass = min(minimum_mass, float(state[6]))
        if perigee < MINIMUM_ALTITUDE_M:
            raise ValueError("trajectory violates minimum-altitude constraint")
        if math.hypot(float(state[1]), float(state[2])) >= 0.85:
            raise ValueError("trajectory exceeds eccentricity safety bound")
        if state[6] < MINIMUM_MASS_FRACTION * float(scenario["initial_mass_kg"]):
            raise ValueError("trajectory violates dry-mass reserve")

    return {
        "state": state,
        "effective_specific_impulse_s": (
            float(scenario["specific_impulse_s"])
            * float(shift.get("isp_scale", 1.0))
        ),
        "minimum_altitude_m": float(minimum_altitude),
        "maximum_altitude_m": float(maximum_altitude),
        "minimum_mass_kg": float(minimum_mass),
    }


def _terminal_record(propagation, scenario):
    state = np.asarray(propagation["state"], dtype=float)
    target = np.asarray(scenario["target_elements"], dtype=float)
    scales = np.asarray(scenario["terminal_scales"], dtype=float)
    errors = (state[:5] - target[:5]) / scales
    terminal_accuracy = math.exp(-0.5 * float(np.mean(errors * errors)))
    phase_error = _wrap_angle(state[5] - target[5])
    phase_score = math.exp(-0.5 * (phase_error / 0.20) ** 2)
    final_mass = float(state[6])
    initial_mass = float(scenario["initial_mass_kg"])
    delta_v = float(propagation["effective_specific_impulse_s"]) * G0_M_S2 * math.log(
        initial_mass / final_mass
    )
    propellant = initial_mass - final_mass
    fuel_factor = math.exp(-delta_v / EFFICIENCY_SCALE_M_S)
    utility = terminal_accuracy * fuel_factor
    baseline = float(scenario["baseline_utility"])
    # Normalised against the reference witness, not against a utility of one. A utility of one
    # means perfect terminal accuracy reached with zero propellant, which no finite-thrust
    # transfer can approach - so the old denominator made the score a fraction of an impossible
    # ideal while the task card described it as a fraction of the way to a witness. The witness
    # itself scored 0.65 to 0.81 under that scale and the best recorded searcher 0.04, which read
    # as far weaker than it was: 0.04 of the impossible ideal is 0.055 of the witness.
    #
    # Uncapped above, because the witnesses are feasible transfers generated before the targets
    # were frozen and are not claimed optimal.
    reference = float(scenario["reference_utility"])
    score = float(max((utility - baseline) / max(1.0e-12, reference - baseline), 0.0))
    return {
        "score": score,
        "terminal_accuracy": float(terminal_accuracy),
        "terminal_phase_score": float(phase_score),
        "terminal_phase_error_rad": float(phase_error),
        "maximum_scaled_terminal_error": float(np.max(np.abs(errors))),
        "rms_scaled_terminal_error": float(math.sqrt(np.mean(errors * errors))),
        "mission_feasible": bool(np.max(np.abs(errors)) <= 1.0),
        "delta_v_m_s": delta_v,
        "propellant_kg": float(propellant),
        "final_mass_kg": final_mass,
        "fuel_factor": float(fuel_factor),
        "minimum_altitude_m": propagation["minimum_altitude_m"],
        "maximum_altitude_m": propagation["maximum_altitude_m"],
    }


def _seeded_copy(base, seed):
    rng = np.random.default_rng(int(seed))
    semimajor, eccentricity, inclination, raan, periapsis, anomaly = base["orbit"]
    initial = classical_to_mee(
        semimajor * rng.uniform(0.985, 1.015),
        eccentricity * rng.uniform(0.94, 1.06),
        math.radians(inclination + rng.uniform(-0.35, 0.35)),
        math.radians(raan + rng.uniform(-2.0, 2.0)),
        math.radians(periapsis + rng.uniform(-2.0, 2.0)),
        math.radians(anomaly + rng.uniform(-3.0, 3.0)),
    )
    coefficients = np.asarray(base["coefficients"], dtype=float).copy()
    nonzero = np.abs(coefficients) > 0.0
    coefficients[nonzero] *= rng.uniform(0.97, 1.03, size=np.sum(nonzero))
    return {
        "initial_elements": initial,
        "initial_mass_kg": float(base["mass_kg"] * rng.uniform(0.98, 1.02)),
        "maximum_thrust_n": float(base["thrust_n"] * rng.uniform(0.98, 1.02)),
        "specific_impulse_s": float(base["isp_s"] * rng.uniform(0.985, 1.015)),
        "duration_s": float(base["duration_days"] * 86400.0),
        "reference_coefficients": coefficients,
    }


@functools.lru_cache(maxsize=1)
def _instances():
    instances = []
    for name, split, seed, family in SCENARIO_SPECS:
        scenario = _seeded_copy(FAMILY_SPECS[family], seed)
        scenario.update({"name": name, "split": split, "seed": int(seed), "family": family})
        target = np.asarray(FROZEN_TARGETS[name], dtype=float)
        scenario["target_elements"] = target
        scenario["terminal_scales"] = np.asarray((
            max(50000.0, 0.006 * target[0]), 0.008, 0.008, 0.004, 0.004,
        ))
        scenario["baseline_utility"] = float(FROZEN_BASELINE_UTILITIES[name])
        scenario["reference_utility"] = float(FROZEN_REFERENCE_UTILITIES[name])
        instances.append(scenario)
    return tuple(instances)


def public_instances():
    """Return copies of all nominal public inputs for calibration and invariant tests."""
    records = []
    for scenario in _instances():
        records.append({
            "initial_elements": np.asarray(scenario["initial_elements"]).copy(),
            "target_elements": np.asarray(scenario["target_elements"]).copy(),
            "initial_mass_kg": float(scenario["initial_mass_kg"]),
            "maximum_thrust_n": float(scenario["maximum_thrust_n"]),
            "specific_impulse_s": float(scenario["specific_impulse_s"]),
            "duration_s": float(scenario["duration_s"]),
            "n_segments": N_SEGMENTS,
        })
    return records


def _score_instance(design_guidance, scenario):
    try:
        returned = design_guidance(
            np.asarray(scenario["initial_elements"]).copy(),
            np.asarray(scenario["target_elements"]).copy(),
            float(scenario["initial_mass_kg"]),
            float(scenario["maximum_thrust_n"]),
            float(scenario["specific_impulse_s"]),
            float(scenario["duration_s"]),
            N_SEGMENTS,
        )
        coefficients, maximum_throttle = _validate_coefficients(returned)
        nominal = _terminal_record(_propagate(scenario, coefficients), scenario)
        shifted = []
        for shift in SHIFT_SPECS:
            try:
                record = _terminal_record(
                    _propagate(scenario, coefficients, shift=shift), scenario
                )
                record["name"] = shift["name"]
                record["valid"] = True
            except Exception:
                record = {
                    "name": shift["name"], "valid": False, "score": 0.0,
                    "terminal_accuracy": 0.0, "terminal_phase_score": 0.0,
                    "mission_feasible": False,
                }
            shifted.append(record)
        return {
            "name": scenario["name"],
            "split": scenario["split"],
            "valid": True,
            "score": nominal["score"],
            "robustness_score": float(min(row["score"] for row in shifted)),
            "shift_feasibility_rate": float(np.mean([
                bool(row["mission_feasible"]) for row in shifted
            ])),
            "maximum_throttle": maximum_throttle,
            "nominal": nominal,
            "shifted": shifted,
        }
    except Exception:
        return {
            "name": scenario["name"], "split": scenario["split"],
            "valid": False, "reason": "invalid_candidate_artifact", "score": 0.0,
            "robustness_score": 0.0, "shift_feasibility_rate": 0.0,
            "nominal": {
                "terminal_accuracy": 0.0, "terminal_phase_score": 0.0,
                "mission_feasible": False, "delta_v_m_s": 0.0,
            },
            "shifted": [],
        }


def evaluate(design_guidance):
    records = []
    for index, scenario in enumerate(_instances()):
        if index and hasattr(design_guidance, "reset_session"):
            design_guidance.reset_session()
        records.append(_score_instance(design_guidance, scenario))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_mission_feasibility = float(np.mean([
        bool(row["valid"] and row["nominal"]["mission_feasible"])
        for row in development
    ]))
    development_score = float(np.mean([row["score"] for row in development]))
    robustness_score = float(np.mean([row["robustness_score"] for row in development]))
    return {
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        # This nominal, label-blind quantity is intentionally search-visible. ``valid``
        # distinguishes executable artifacts; feasibility_rate distinguishes trajectories
        # that actually enter every public terminal tolerance.
        "feasibility_rate": development_mission_feasibility,
        "raw_score": development_score,
        "development_score": development_score,
        "robustness_score": robustness_score,
        "development_validation_gap": development_score - robustness_score,
        "heldout_policy_score": float(np.mean([row["score"] for row in heldout])),
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "heldout_artifact_valid_rate": heldout_valid / len(heldout),
        "development_mission_feasibility_rate": development_mission_feasibility,
        "heldout_mission_feasibility_rate": float(np.mean([
            bool(row["valid"] and row["nominal"]["mission_feasible"])
            for row in heldout
        ])),
        "development_shift_feasibility_rate": float(np.mean([
            row["shift_feasibility_rate"] for row in development
        ])),
        "heldout_shift_feasibility_rate": float(np.mean([
            row["shift_feasibility_rate"] for row in heldout
        ])),
        "mean_development_terminal_accuracy": float(np.mean([
            row["nominal"]["terminal_accuracy"] for row in development
        ])),
        "mean_heldout_terminal_accuracy": float(np.mean([
            row["nominal"]["terminal_accuracy"] for row in heldout
        ])),
        "mean_development_phase_score": float(np.mean([
            row["nominal"]["terminal_phase_score"] for row in development
        ])),
        "mean_heldout_phase_score": float(np.mean([
            row["nominal"]["terminal_phase_score"] for row in heldout
        ])),
        "mean_development_delta_v_m_s": float(np.mean([
            row["nominal"]["delta_v_m_s"] for row in development
        ])),
        "mean_heldout_delta_v_m_s": float(np.mean([
            row["nominal"]["delta_v_m_s"] for row in heldout
        ])),
        "per_instance": records,
    }
