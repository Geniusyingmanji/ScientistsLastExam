"""Truth-blind reference for ActiveNoiseSpectroscopy.

The reference spends shots on Ramsey, echo and offset-echo filters, reconstructs
the complex coherence, and fits the public two-state transfer model.  It does not
import the evaluator or know which world it is evaluating.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares


CONTROLS = (
    {"name": "ramsey_0p5", "duration_us": 0.5, "pulse_times_us": ()},
    {"name": "ramsey_1p0", "duration_us": 1.0, "pulse_times_us": ()},
    {"name": "ramsey_2p0", "duration_us": 2.0, "pulse_times_us": ()},
    {"name": "ramsey_3p5", "duration_us": 3.5, "pulse_times_us": ()},
    {"name": "echo_3p0", "duration_us": 3.0, "pulse_times_us": (1.5,)},
    {"name": "offset_echo", "duration_us": 2.4, "pulse_times_us": (0.4,)},
)
SHOTS = 1_950


def _intervals(control):
    points = [0.0] + [float(x) for x in control["pulse_times_us"]]
    points.append(float(control["duration_us"]))
    return [
        (points[index + 1] - points[index], 1.0 if index % 2 == 0 else -1.0)
        for index in range(len(points) - 1)
    ]


def _single_fluctuator(control, rate, variance, high_probability):
    low_probability = 1.0 - high_probability
    gap = math.sqrt(variance / (low_probability * high_probability))
    levels = np.asarray([-high_probability * gap, low_probability * gap])
    propagator = np.asarray([
        [-rate * high_probability, rate * low_probability],
        [rate * high_probability, -rate * low_probability],
    ])
    state = np.asarray([low_probability, high_probability], dtype=complex)
    for duration, sign in _intervals(control):
        state = expm(
            (propagator - 1j * sign * np.diag(levels)) * duration
        ).dot(state)
    return complex(np.sum(state))


def _gaussian_ou(control, rate, variance):
    memory = 0.0
    chi = 0.0
    for duration, sign in _intervals(control):
        decay = math.exp(-rate * duration)
        chi += variance * (
            sign * memory * (1.0 - decay) / rate
            + duration / rate
            - (1.0 - decay) / (rate * rate)
        )
        memory = memory * decay + sign * (1.0 - decay) / rate
    return complex(math.exp(-max(0.0, chi)), 0.0)


def _fit(controls, observations, parameter_bounds):
    lower = [
        float(parameter_bounds["switching_rate_per_us"][0]),
        float(parameter_bounds["noise_variance_rad2_per_us2"][0]),
        float(parameter_bounds["high_state_probability"][0]),
    ]
    upper = [
        float(parameter_bounds["switching_rate_per_us"][1]),
        float(parameter_bounds["noise_variance_rad2_per_us2"][1]),
        float(parameter_bounds["high_state_probability"][1]),
    ]

    def residual(parameters):
        predicted = [
            _single_fluctuator(control, *parameters) for control in controls
        ]
        values = []
        for estimate, measured in zip(predicted, observations):
            values.extend([
                estimate.real - measured.real,
                estimate.imag - measured.imag,
            ])
        return np.asarray(values)

    starts = (
        [0.55, 0.16, 0.16],
        [1.10, 0.24, 0.24],
        [1.90, 0.32, 0.36],
    )
    fits = [
        least_squares(
            residual,
            np.clip(start, lower, upper),
            bounds=(lower, upper),
            max_nfev=600,
        )
        for start in starts
    ]
    best = min(fits, key=lambda fit: float(np.dot(fit.fun, fit.fun)))
    return best.x, math.sqrt(float(np.mean(best.fun ** 2)))


def _fit_gaussian(controls, observations, parameter_bounds):
    lower = [
        float(parameter_bounds["switching_rate_per_us"][0]),
        float(parameter_bounds["noise_variance_rad2_per_us2"][0]),
    ]
    upper = [
        float(parameter_bounds["switching_rate_per_us"][1]),
        float(parameter_bounds["noise_variance_rad2_per_us2"][1]),
    ]

    def residual(parameters):
        predicted = [_gaussian_ou(control, *parameters) for control in controls]
        values = []
        for estimate, measured in zip(predicted, observations):
            values.extend([
                estimate.real - measured.real,
                estimate.imag - measured.imag,
            ])
        return np.asarray(values)

    fit = least_squares(
        residual, [1.0, 0.2], bounds=(lower, upper), max_nfev=600
    )
    return math.sqrt(float(np.mean(fit.fun ** 2)))


def discover_noise(problem, measure):
    observations = []
    for control in CONTROLS:
        result = measure(control["name"], SHOTS)
        shots = int(result["shots_per_quadrature"])
        observations.append(complex(
            2.0 * result["x_plus_counts"] / shots - 1.0,
            2.0 * result["y_plus_counts"] / shots - 1.0,
        ))

    parameters, residual_rms = _fit(
        CONTROLS, observations, problem["parameter_bounds"]
    )
    gaussian_rms = _fit_gaussian(
        CONTROLS, observations, problem["parameter_bounds"]
    )
    ramsey_phase = max(
        value.imag for control, value in zip(CONTROLS, observations)
        if control["name"].startswith("ramsey_")
    )
    long_phase = observations[3].imag
    # A PSD-matched Gaussian has zero phase.  Negative long-time phase and a
    # poor one-source fit are signatures of the deliberately out-of-family
    # two-fluctuator worlds.
    asymmetric_supported = ramsey_phase >= 0.045 and long_phase >= 0.035
    symmetric_supported = (
        abs(long_phase) < 0.045
        and parameters[2] >= 0.43
        and residual_rms + 0.010 < gaussian_rms
    )
    if (
        not (asymmetric_supported or symmetric_supported)
        or long_phase < -0.045
        or residual_rms > 0.045
    ):
        return {"abstain": True, "confidence": 0.78}
    return {
        "abstain": False,
        "noise_model": "single_telegraph",
        "switching_rate_per_us": float(parameters[0]),
        "noise_variance_rad2_per_us2": float(parameters[1]),
        "high_state_probability": float(parameters[2]),
        "confidence": 0.82,
    }
