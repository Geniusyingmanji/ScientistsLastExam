#!/usr/bin/env python3
"""Calibrate OceanCurrentInversion-v2 with truth-blind active drifter fitting."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/EarthScience/OceanCurrentInversion"
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402

DAY_S = 86400.0
DOMAIN_LENGTH_M = 200000.0


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("ocean_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load OceanCurrentInversion-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plan():
    return (
        (
            np.asarray(((30000.0, 35000.0), (35000.0, 160000.0),
                        (105000.0, 60000.0))),
            0.0,
        ),
        (
            np.asarray(((120000.0, 165000.0), (165000.0, 85000.0),
                        (70000.0, 115000.0))),
            3.5 * DAY_S,
        ),
    )


def _sample_times():
    return np.linspace(0.0, 1.5 * DAY_S, 13)


def _temporal_value(code, period_s, absolute_time_s):
    if code == "steady":
        return np.ones_like(np.asarray(absolute_time_s, dtype=float))
    phase = 2.0 * np.pi * np.asarray(absolute_time_s, dtype=float) / float(period_s)
    if code == "cos":
        return np.cos(phase)
    if code == "sin":
        return np.sin(phase)
    raise ValueError("unknown temporal mode")


def _public_mode_velocity(
    coefficients, mode_specifications, positions_m, absolute_time_s
):
    """Independent implementation of the equations printed in Task.md."""
    positions = np.asarray(positions_m, dtype=float)
    flat = positions.reshape((-1, 2))
    times = np.asarray(absolute_time_s, dtype=float)
    if times.ndim == 0:
        times = np.full(len(flat), float(times))
    else:
        times = np.broadcast_to(times, positions.shape[:-1]).ravel()
    x = flat[:, 0]
    y = flat[:, 1]
    u = np.zeros(len(flat))
    v = np.zeros(len(flat))
    for coefficient, (m, n, code, period) in zip(
        np.asarray(coefficients, dtype=float), mode_specifications
    ):
        temporal = _temporal_value(code, period, times)
        u += (
            coefficient * float(n)
            * np.sin(float(m) * np.pi * x / DOMAIN_LENGTH_M)
            * np.cos(float(n) * np.pi * y / DOMAIN_LENGTH_M)
            * temporal
        )
        v -= (
            coefficient * float(m)
            * np.cos(float(m) * np.pi * x / DOMAIN_LENGTH_M)
            * np.sin(float(n) * np.pi * y / DOMAIN_LENGTH_M)
            * temporal
        )
    return np.column_stack((u, v)).reshape(positions.shape)


def _mode_design(mode_specifications, positions, absolute_times):
    columns = []
    for index in range(len(mode_specifications)):
        coefficients = np.zeros(len(mode_specifications))
        coefficients[index] = 1.0
        columns.append(_public_mode_velocity(
            coefficients, mode_specifications, positions, absolute_times
        ))
    return np.stack(columns, axis=-1)


def _fit_observations(mode_specifications, records):
    matrices = []
    velocities = []
    standard_deviations = []
    for record in records:
        trajectories = np.asarray(record["trajectories_m"], dtype=float)
        times = np.asarray(record["time_s"], dtype=float)
        elapsed = times[2:] - times[:-2]
        estimated_velocity = (
            trajectories[:, 2:, :] - trajectories[:, :-2, :]
        ) / elapsed[None, :, None]
        midpoint_position = trajectories[:, 1:-1, :]
        absolute_time = float(record["release_time_s"]) + times[1:-1]
        design = _mode_design(
            mode_specifications, midpoint_position, absolute_time[None, :]
        )
        noise = float(record["position_noise_std_m"])
        velocity_noise = noise * math.sqrt(2.0) / elapsed
        matrices.append(design.reshape((-1, len(mode_specifications))))
        velocities.append(estimated_velocity.ravel())
        standard_deviations.append(np.broadcast_to(
            velocity_noise[None, :, None], estimated_velocity.shape
        ).ravel())

    matrix = np.concatenate(matrices)
    observed = np.concatenate(velocities)
    sigma = np.concatenate(standard_deviations)
    weighted_matrix = matrix / sigma[:, None]
    weighted_observed = observed / sigma
    coefficients = np.linalg.lstsq(
        weighted_matrix, weighted_observed, rcond=None
    )[0]
    normalized_residual = (matrix @ coefficients - observed) / sigma
    matrix_rank = int(np.linalg.matrix_rank(weighted_matrix))
    degrees_of_freedom = max(1, len(observed) - matrix_rank)
    residual_per_dof = float(
        np.sum(normalized_residual**2) / degrees_of_freedom
    )
    covariance = np.linalg.pinv(weighted_matrix.T @ weighted_matrix)
    standard_error = np.sqrt(np.diag(covariance) * max(residual_per_dof, 1.0))
    z_score = np.abs(coefficients) / np.maximum(standard_error, 1e-12)
    support = (np.abs(coefficients) >= 0.008) & (z_score >= 3.0)
    wald_statistic = float(coefficients @ np.linalg.pinv(covariance) @ coefficients)
    abstain = bool(
        residual_per_dof > 3.0 or wald_statistic < 45.0 or not np.any(support)
    )
    return {
        "coefficients": coefficients,
        "support": support,
        "standard_error": standard_error,
        "approximate_velocity_residual_per_dof": residual_per_dof,
        "wald_statistic": wald_statistic,
        "abstain": abstain,
        "row_count": len(observed),
        "degrees_of_freedom": degrees_of_freedom,
        "matrix_rank": matrix_rank,
        "matrix_condition_number": float(np.linalg.cond(weighted_matrix)),
    }


def _public_velocity_derivatives(
    coefficients, mode_specifications, positions_m, absolute_time_s
):
    """Velocity, spatial Jacobian and coefficient basis for the public equations."""
    positions = np.asarray(positions_m, dtype=float)
    flat = positions.reshape((-1, 2))
    times = np.asarray(absolute_time_s, dtype=float)
    if times.ndim == 0:
        times = np.full(len(flat), float(times))
    else:
        times = np.broadcast_to(times, positions.shape[:-1]).ravel()
    coefficients = np.asarray(coefficients, dtype=float)
    n_modes = len(mode_specifications)
    basis = np.zeros((len(flat), 2, n_modes))
    spatial = np.zeros((len(flat), 2, 2))
    alpha = np.pi / DOMAIN_LENGTH_M
    x = flat[:, 0]
    y = flat[:, 1]
    for index, (coefficient, specification) in enumerate(zip(
        coefficients, mode_specifications
    )):
        m, n, code, period = specification
        m = float(m)
        n = float(n)
        temporal = _temporal_value(code, period, times)
        sin_x = np.sin(m * alpha * x)
        cos_x = np.cos(m * alpha * x)
        sin_y = np.sin(n * alpha * y)
        cos_y = np.cos(n * alpha * y)
        basis[:, 0, index] = n * sin_x * cos_y * temporal
        basis[:, 1, index] = -m * cos_x * sin_y * temporal
        spatial[:, 0, 0] += (
            coefficient * m * n * alpha * cos_x * cos_y * temporal
        )
        spatial[:, 0, 1] -= (
            coefficient * n * n * alpha * sin_x * sin_y * temporal
        )
        spatial[:, 1, 0] += (
            coefficient * m * m * alpha * sin_x * sin_y * temporal
        )
        spatial[:, 1, 1] -= (
            coefficient * m * n * alpha * cos_x * cos_y * temporal
        )
    velocity = np.einsum("nip,p->ni", basis, coefficients)
    return velocity, spatial, basis


def _public_trajectory_with_sensitivity(
    coefficients, mode_specifications, initial_positions, release_time,
    sample_times, step_limit_s=1800.0,
):
    """Integrate public modes and their exact first-order coefficient sensitivity."""
    positions = np.asarray(initial_positions, dtype=float).copy()
    times = np.asarray(sample_times, dtype=float)
    n_drifters = len(positions)
    n_modes = len(mode_specifications)
    sensitivity = np.zeros((n_drifters, 2, n_modes))
    trajectory = np.empty((n_drifters, len(times), 2))
    trajectory_sensitivity = np.empty((n_drifters, len(times), 2, n_modes))
    trajectory[:, 0, :] = positions
    trajectory_sensitivity[:, 0, :, :] = sensitivity

    def derivative(position, current_sensitivity, absolute_time):
        velocity, spatial, basis = _public_velocity_derivatives(
            coefficients, mode_specifications, position, absolute_time
        )
        sensitivity_rate = (
            np.einsum("nij,njp->nip", spatial, current_sensitivity) + basis
        )
        return velocity, sensitivity_rate

    current = 0.0
    for sample_index in range(1, len(times)):
        target = float(times[sample_index])
        interval = target - current
        n_steps = max(1, int(math.ceil(interval / step_limit_s)))
        step = interval / n_steps
        for local in range(n_steps):
            absolute = float(release_time) + current + local * step
            k1_x, k1_s = derivative(positions, sensitivity, absolute)
            k2_x, k2_s = derivative(
                positions + 0.5 * step * k1_x,
                sensitivity + 0.5 * step * k1_s,
                absolute + 0.5 * step,
            )
            k3_x, k3_s = derivative(
                positions + 0.5 * step * k2_x,
                sensitivity + 0.5 * step * k2_s,
                absolute + 0.5 * step,
            )
            k4_x, k4_s = derivative(
                positions + step * k3_x,
                sensitivity + step * k3_s,
                absolute + step,
            )
            positions += step * (k1_x + 2.0 * k2_x + 2.0 * k3_x + k4_x) / 6.0
            sensitivity += step * (
                k1_s + 2.0 * k2_s + 2.0 * k3_s + k4_s
            ) / 6.0
        current = target
        trajectory[:, sample_index, :] = positions
        trajectory_sensitivity[:, sample_index, :, :] = sensitivity
    return trajectory, trajectory_sensitivity


def _nonlinear_library_fit(oracle, world):
    """Bound the best public-library trajectory fit with analytic sensitivities."""
    records = _clean_plan_records(oracle, world)
    linear = _fit_observations(oracle.MODE_SPECIFICATIONS, records)
    targets = [np.asarray(record["trajectories_m"]) for record in records]
    cache = {}

    def evaluate(vector):
        key = np.asarray(vector, dtype=float).tobytes()
        if key not in cache:
            residual_rows = []
            jacobian_rows = []
            for (initial, release), target in zip(_plan(), targets):
                prediction, sensitivity = _public_trajectory_with_sensitivity(
                    vector, oracle.MODE_SPECIFICATIONS, initial, release,
                    _sample_times(),
                )
                residual_rows.extend(
                    ((prediction[:, 1:, :] - target[:, 1:, :])
                     / world["noise"]).ravel()
                )
                jacobian_rows.append(
                    sensitivity[:, 1:, :, :].reshape((-1, oracle.N_MODES))
                    / world["noise"]
                )
            cache.clear()
            cache[key] = (
                np.asarray(residual_rows), np.concatenate(jacobian_rows)
            )
        return cache[key]

    rng = np.random.default_rng(220729)
    starts = (
        np.zeros(oracle.N_MODES),
        np.clip(linear["coefficients"], -0.35, 0.35),
        rng.normal(0.0, 0.03, size=oracle.N_MODES),
        rng.normal(0.0, 0.03, size=oracle.N_MODES),
    )
    fits = []
    for start in starts:
        fit = least_squares(
            lambda vector: evaluate(vector)[0],
            start,
            jac=lambda vector: evaluate(vector)[1],
            bounds=(-0.35, 0.35),
            max_nfev=100,
            x_scale="jac",
            ftol=1e-9,
            xtol=1e-9,
            gtol=1e-9,
        )
        residual = evaluate(fit.x)[0]
        jacobian = evaluate(fit.x)[1]
        rank = int(np.linalg.matrix_rank(jacobian))
        dof = max(1, len(residual) - rank)
        minimum_boundary_margin = math.inf
        for initial, release in _plan():
            trajectory, _sensitivity = _public_trajectory_with_sensitivity(
                fit.x, oracle.MODE_SPECIFICATIONS, initial, release,
                _sample_times(),
            )
            margin = np.minimum.reduce((
                trajectory[..., 0],
                DOMAIN_LENGTH_M - trajectory[..., 0],
                trajectory[..., 1],
                DOMAIN_LENGTH_M - trajectory[..., 1],
            ))
            minimum_boundary_margin = min(
                minimum_boundary_margin, float(np.min(margin))
            )
        fits.append({
            "reduced_chi2": float(np.sum(residual**2) / dof),
            "residual_count": len(residual),
            "jacobian_rank": rank,
            "degrees_of_freedom": dof,
            "n_function_evaluations": int(fit.nfev),
            "maximum_absolute_coefficient_m_s": float(np.max(np.abs(fit.x))),
            "minimum_boundary_margin_m": minimum_boundary_margin,
            "success": bool(fit.success),
            "status": int(fit.status),
            "first_order_optimality": float(fit.optimality),
        })
    return min(fits, key=lambda row: row["reduced_chi2"]), fits


def classical_discover_currents(
    domain_m, mode_specifications, observe, budget_units
):
    """Two-phase sparse velocity fit without hidden seed, template or world labels."""
    del domain_m, budget_units
    times = _sample_times()
    records = [
        observe(initial, release, times)
        for initial, release in _plan()
    ]
    fit = _fit_observations(mode_specifications, records)
    n_modes = len(mode_specifications)
    if fit["abstain"]:
        return {
            "coefficients_m_s": np.zeros(n_modes),
            "support": np.zeros(n_modes, dtype=int),
            "confidence": 0.0,
            "abstain": True,
        }
    return {
        "coefficients_m_s": np.where(
            fit["support"], fit["coefficients"], 0.0
        ),
        "support": fit["support"].astype(int),
        "confidence": float(np.clip(
            1.0 - math.sqrt(
                fit["approximate_velocity_residual_per_dof"]
            ) / 6.0,
            0.0, 1.0,
        )),
        "abstain": False,
    }


def _always_abstain(domain_m, mode_specifications, observe, budget_units):
    del domain_m, budget_units
    observe(
        np.asarray(((30000.0, 30000.0),)), 0.0,
        np.linspace(0.0, DAY_S, 7),
    )
    return {
        "coefficients_m_s": np.zeros(len(mode_specifications)),
        "support": np.zeros(len(mode_specifications), dtype=int),
        "confidence": 0.0,
        "abstain": True,
    }


def _clean_plan_records(oracle, world):
    records = []
    times = _sample_times()
    for initial, release in _plan():
        trajectories = oracle._simulate(world, initial, release, times)
        records.append({
            "release_time_s": release,
            "time_s": times,
            "trajectories_m": trajectories,
            "position_noise_std_m": world["noise"],
        })
    return records


def _trajectory_identifiability(oracle, world, split, world_index):
    times = _sample_times()
    truth = world["coefficients"]
    rows = []
    for initial, release in _plan():
        _trajectory, sensitivity = _public_trajectory_with_sensitivity(
            truth, oracle.MODE_SPECIFICATIONS, initial, release, times
        )
        rows.append(
            sensitivity[:, 1:, :, :].reshape((-1, oracle.N_MODES))
            / world["noise"]
        )
    jacobian = np.concatenate(rows)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1e-8))
    condition = float(singular[0] / singular[-1])
    return {
        "split": split,
        "world_index": world_index,
        "coefficient_count": oracle.N_MODES,
        "jacobian_shape": list(jacobian.shape),
        "jacobian_rank": rank,
        "condition_number": condition,
        "minimum_singular_value": float(singular[-1]),
        "survey_budget_units": 12,
        "passed": rank == oracle.N_MODES and condition < 1e3,
    }


def _fine_simulation(oracle, world, initial, release, times, step_limit_s=300.0):
    trajectory = np.empty((len(initial), len(times), 2), dtype=float)
    trajectory[:, 0, :] = initial
    positions = initial.copy()
    current = 0.0
    for index in range(1, len(times)):
        target = float(times[index])
        interval = target - current
        steps = max(1, int(math.ceil(interval / step_limit_s)))
        step = interval / steps
        for local in range(steps):
            absolute = release + current + local * step
            velocity = lambda position, time: oracle._world_velocity(
                world, position, time
            )
            k1 = velocity(positions, absolute)
            k2 = velocity(
                positions + 0.5 * step * k1, absolute + 0.5 * step
            )
            k3 = velocity(
                positions + 0.5 * step * k2, absolute + 0.5 * step
            )
            k4 = velocity(positions + step * k3, absolute + step)
            positions = positions + step * (
                k1 + 2.0 * k2 + 2.0 * k3 + k4
            ) / 6.0
            positions[:, 0] = np.clip(
                positions[:, 0], oracle.DOMAIN_M[0], oracle.DOMAIN_M[1]
            )
            positions[:, 1] = np.clip(
                positions[:, 1], oracle.DOMAIN_M[2], oracle.DOMAIN_M[3]
            )
        current = target
        trajectory[:, index, :] = positions
    return trajectory


def _physics_checks(oracle):
    rng = np.random.default_rng(220726)
    positions = rng.uniform(20000.0, 180000.0, size=(64, 2))
    public_equation_error = 0.0
    for _ in range(12):
        coefficients = rng.normal(scale=0.03, size=oracle.N_MODES)
        absolute_times = rng.uniform(
            0.0, 8.0 * oracle.DAY_S, size=len(positions)
        )
        oracle_values = oracle.mode_velocity(
            coefficients, oracle.MODE_SPECIFICATIONS,
            positions, absolute_times,
        )
        independent_values = _public_mode_velocity(
            coefficients, oracle.MODE_SPECIFICATIONS,
            positions, absolute_times,
        )
        public_equation_error = max(
            public_equation_error,
            float(np.max(np.abs(oracle_values - independent_values))),
        )
    sensitivity_world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    sensitivity_initial, sensitivity_release = _plan()[0]
    sensitivity_times = _sample_times()
    trajectory, analytic_sensitivity = _public_trajectory_with_sensitivity(
        sensitivity_world["coefficients"], oracle.MODE_SPECIFICATIONS,
        sensitivity_initial, sensitivity_release, sensitivity_times,
    )
    oracle_trajectory = oracle._simulate(
        sensitivity_world, sensitivity_initial, sensitivity_release,
        sensitivity_times,
        candidate_coefficients=sensitivity_world["coefficients"],
    )
    trajectory_error = float(np.max(np.abs(trajectory - oracle_trajectory)))
    maximum_relative_sensitivity_error = 0.0
    for column in (0, 7, 14, 21, 29):
        step = 1e-6
        upper = sensitivity_world["coefficients"].copy()
        lower = sensitivity_world["coefficients"].copy()
        upper[column] += step
        lower[column] -= step
        finite_difference = (
            oracle._simulate(
                sensitivity_world, sensitivity_initial, sensitivity_release,
                sensitivity_times, candidate_coefficients=upper,
            )
            - oracle._simulate(
                sensitivity_world, sensitivity_initial, sensitivity_release,
                sensitivity_times, candidate_coefficients=lower,
            )
        ) / (2.0 * step)
        relative = float(np.linalg.norm(
            finite_difference - analytic_sensitivity[..., column]
        ) / np.linalg.norm(finite_difference))
        maximum_relative_sensitivity_error = max(
            maximum_relative_sensitivity_error, relative
        )
    h = 1.0
    maximum_divergence = 0.0
    maximum_boundary_normal_velocity = 0.0
    for index in range(oracle.N_MODES):
        coefficients = np.zeros(oracle.N_MODES)
        coefficients[index] = 0.1
        for time in (0.0, 1.1 * oracle.DAY_S, 4.2 * oracle.DAY_S):
            xp, xm = positions.copy(), positions.copy()
            yp, ym = positions.copy(), positions.copy()
            xp[:, 0] += h
            xm[:, 0] -= h
            yp[:, 1] += h
            ym[:, 1] -= h
            du_dx = (
                oracle.mode_velocity(
                    coefficients, oracle.MODE_SPECIFICATIONS, xp, time
                )[:, 0]
                - oracle.mode_velocity(
                    coefficients, oracle.MODE_SPECIFICATIONS, xm, time
                )[:, 0]
            ) / (2.0 * h)
            dv_dy = (
                oracle.mode_velocity(
                    coefficients, oracle.MODE_SPECIFICATIONS, yp, time
                )[:, 1]
                - oracle.mode_velocity(
                    coefficients, oracle.MODE_SPECIFICATIONS, ym, time
                )[:, 1]
            ) / (2.0 * h)
            maximum_divergence = max(
                maximum_divergence, float(np.max(np.abs(du_dx + dv_dy)))
            )
        boundary_coordinate = np.linspace(
            oracle.DOMAIN_M[0], oracle.DOMAIN_M[1], 97
        )
        x_boundaries = np.vstack((
            np.column_stack((
                np.full(len(boundary_coordinate), oracle.DOMAIN_M[0]),
                boundary_coordinate,
            )),
            np.column_stack((
                np.full(len(boundary_coordinate), oracle.DOMAIN_M[1]),
                boundary_coordinate,
            )),
        ))
        y_boundaries = np.vstack((
            np.column_stack((
                boundary_coordinate,
                np.full(len(boundary_coordinate), oracle.DOMAIN_M[2]),
            )),
            np.column_stack((
                boundary_coordinate,
                np.full(len(boundary_coordinate), oracle.DOMAIN_M[3]),
            )),
        ))
        for time in (0.0, 2.3 * oracle.DAY_S):
            x_normal = oracle.mode_velocity(
                coefficients, oracle.MODE_SPECIFICATIONS,
                x_boundaries, time,
            )[:, 0]
            y_normal = oracle.mode_velocity(
                coefficients, oracle.MODE_SPECIFICATIONS,
                y_boundaries, time,
            )[:, 1]
            maximum_boundary_normal_velocity = max(
                maximum_boundary_normal_velocity,
                float(np.max(np.abs(x_normal))),
                float(np.max(np.abs(y_normal))),
            )

    convergence = []
    signal = []
    sealed_rollout_boundary = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            displacements = []
            clipped = 0
            sample_count = 0
            maximum_error = 0.0
            for initial, release in _plan():
                times = _sample_times()
                standard = oracle._simulate(world, initial, release, times)
                fine = _fine_simulation(
                    oracle, world, initial, release, times
                )
                maximum_error = max(
                    maximum_error,
                    float(np.max(np.linalg.norm(standard - fine, axis=-1))),
                )
                stationary = np.repeat(initial[:, None, :], len(times), axis=1)
                displacements.extend((standard - stationary).ravel())
                clipped += int(np.sum(
                    (standard[..., 0] <= oracle.DOMAIN_M[0])
                    | (standard[..., 0] >= oracle.DOMAIN_M[1])
                    | (standard[..., 1] <= oracle.DOMAIN_M[2])
                    | (standard[..., 1] >= oracle.DOMAIN_M[3])
                ))
                sample_count += standard.shape[0] * standard.shape[1]
            convergence.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "maximum_1800s_vs_300s_position_error_m": maximum_error,
                "passed": maximum_error < 2.0,
            })
            displacement_rms = float(np.sqrt(np.mean(
                np.asarray(displacements)**2
            )))
            ratio = displacement_rms / world["noise"]
            signal.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "displacement_rms_m": displacement_rms,
                "position_noise_std_m": world["noise"],
                "displacement_signal_to_noise": ratio,
                "boundary_clip_fraction": clipped / sample_count,
                "passed": bool(
                    (ratio == 0.0 if world["kind"] == "null" else ratio > 8.0)
                    and clipped == 0
                ),
            })
            for extrapolation in (False, True):
                rng = np.random.default_rng(
                    world["seed"] + (150001 if extrapolation else 140009)
                )
                initial = rng.uniform(15000.0, 185000.0, size=(8, 2))
                release = (
                    9.0 * oracle.DAY_S
                    if extrapolation else 4.25 * oracle.DAY_S
                )
                duration = (
                    5.0 * oracle.DAY_S
                    if extrapolation else 2.5 * oracle.DAY_S
                )
                trajectory = oracle._simulate(
                    world, initial, release, np.linspace(0.0, duration, 21)
                )
                clipped = np.mean(
                    (trajectory[..., 0] <= oracle.DOMAIN_M[0])
                    | (trajectory[..., 0] >= oracle.DOMAIN_M[1])
                    | (trajectory[..., 1] <= oracle.DOMAIN_M[2])
                    | (trajectory[..., 1] >= oracle.DOMAIN_M[3])
                )
                margin = np.minimum.reduce((
                    trajectory[..., 0],
                    oracle.DOMAIN_M[1] - trajectory[..., 0],
                    trajectory[..., 1],
                    oracle.DOMAIN_M[3] - trajectory[..., 1],
                ))
                sealed_rollout_boundary.append({
                    "split": split,
                    "world_index": index,
                    "kind": world["kind"],
                    "extrapolation": extrapolation,
                    "boundary_clip_fraction": float(clipped),
                    "minimum_boundary_margin_m": float(np.min(margin)),
                    "passed": bool(clipped == 0.0),
                })
    return {
        "independent_public_equation": {
            "maximum_absolute_velocity_error_m_s": public_equation_error,
            "passed": public_equation_error < 1e-13,
        },
        "trajectory_sensitivity": {
            "maximum_trajectory_error_m": trajectory_error,
            "maximum_relative_jacobian_error": (
                maximum_relative_sensitivity_error
            ),
            "checked_columns": [0, 7, 14, 21, 29],
            "passed": bool(
                trajectory_error < 1e-6
                and maximum_relative_sensitivity_error < 1e-7
            ),
        },
        "finite_difference_divergence": {
            "maximum_absolute_divergence_s_inverse": maximum_divergence,
            "passed": maximum_divergence < 1e-12,
        },
        "no_normal_boundary_flow": {
            "maximum_absolute_normal_velocity_m_s": (
                maximum_boundary_normal_velocity
            ),
            "passed": maximum_boundary_normal_velocity < 1e-12,
        },
        "rk4_convergence": convergence,
        "signal_and_boundary": signal,
        "sealed_rollout_boundary": sealed_rollout_boundary,
    }


def _determinism_check(oracle):
    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    initial, release = _plan()[0]
    times = _sample_times()
    first_laboratory = oracle._DrifterLaboratory(world)
    first = first_laboratory.observe(initial, release, times)
    repeated_same_laboratory = first_laboratory.observe(
        initial, release, times
    )
    second = oracle._DrifterLaboratory(world).observe(initial, release, times)
    fresh_laboratory_equal = np.array_equal(
        first["trajectories_m"], second["trajectories_m"]
    )
    repeated_call_distinct = not np.array_equal(
        first["trajectories_m"], repeated_same_laboratory["trajectories_m"]
    )
    passed = bool(
        fresh_laboratory_equal and repeated_call_distinct
        and first["budget_cost"] == second["budget_cost"] == 6
        and repeated_same_laboratory["budget_cost"] == 6
        and first_laboratory.used == oracle.EXPERIMENT_BUDGET_UNITS
    )
    return {
        "same_query_same_fresh_lab": bool(fresh_laboratory_equal),
        "same_query_repeated_call_uses_distinct_noise": bool(
            repeated_call_distinct
        ),
        "per_call_budget_cost": first["budget_cost"],
        "two_call_budget_units": first_laboratory.used,
        "passed": passed,
    }


def _noise_label_blind_checks(oracle):
    checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        supported = sorted({
            float(spec[2]) for spec in specs if spec[3] == "in_library"
        })
        unsupported = sorted({
            float(spec[2]) for spec in specs if spec[3] != "in_library"
        })
        checks.append({
            "split": split,
            "supported_noise_std_m": supported,
            "unsupported_noise_std_m": unsupported,
            "unsupported_is_subset_of_supported": set(unsupported).issubset(
                set(supported)
            ),
            "passed": set(unsupported).issubset(set(supported)),
        })
    return checks


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(classical_discover_currents)
    physics = _physics_checks(oracle)
    determinism = _determinism_check(oracle)
    noise_label_blind = _noise_label_blind_checks(oracle)

    exact = []
    identifiability = []
    misspecified = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            submission = oracle._reference_submission(world)
            coefficients, support, _confidence, abstain = (
                oracle._validate_submission(submission)
            )
            mechanism = oracle._mechanism_metrics(
                world, coefficients, support, abstain
            )
            field = oracle._field_prediction_score(world, coefficients, False)
            field_extra = oracle._field_prediction_score(
                world, coefficients, True
            )
            trajectory = oracle._trajectory_prediction_score(
                world, coefficients, False
            )
            trajectory_extra = oracle._trajectory_prediction_score(
                world, coefficients, True
            )
            exact.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "mechanism_score": mechanism["mechanism_score"],
                "field_prediction_score": field,
                "field_extrapolation_score": field_extra,
                "trajectory_prediction_score": trajectory,
                "trajectory_extrapolation_score": trajectory_extra,
                "passed": bool(
                    mechanism["mechanism_score"] == 1.0
                    and (
                        world["kind"] == "misspecified"
                        or (field == field_extra == trajectory == trajectory_extra == 1.0)
                    )
                ),
            })
            if world["kind"] == "in_library":
                identifiability.append(_trajectory_identifiability(
                    oracle, world, split, index
                ))
            if world["kind"] == "misspecified":
                linear_fit = _fit_observations(
                    oracle.MODE_SPECIFICATIONS,
                    _clean_plan_records(oracle, world),
                )
                nonlinear_best, nonlinear_starts = _nonlinear_library_fit(
                    oracle, world
                )
                nonlinear_values = [
                    item["reduced_chi2"] for item in nonlinear_starts
                ]
                nonlinear_spread = max(nonlinear_values) - min(
                    nonlinear_values
                )
                row = next(
                    item for item in classical["per_world"]
                    if item["split"] == split and item["world_index"] == index
                )
                misspecified.append({
                    "split": split,
                    "world_index": index,
                    "approximate_velocity_residual_per_dof": linear_fit[
                        "approximate_velocity_residual_per_dof"
                    ],
                    "best_nonlinear_trajectory_fit": nonlinear_best,
                    "nonlinear_start_fits": nonlinear_starts,
                    "nonlinear_reduced_chi2_spread": nonlinear_spread,
                    "refusal_threshold": 3.0,
                    "classical_abstained": row["abstained"],
                    "classical_false_discovery": row["false_discovery"],
                    "passed": bool(
                        linear_fit[
                            "approximate_velocity_residual_per_dof"
                        ] > 3.0
                        and nonlinear_best["reduced_chi2"] > 3.0
                        and nonlinear_spread < 1e-5
                        and all(item["success"] for item in nonlinear_starts)
                        and all(
                            item["minimum_boundary_margin_m"] > 0.0
                            for item in nonlinear_starts
                        )
                        and row["abstained"] and not row["false_discovery"]
                    ),
                })

    difficulty_passed = bool(
        0.35 <= classical["combined_score"] <= 0.85
        and 0.20 <= classical["robustness_score"] <= 0.75
        and classical["combined_score"]
        > classical["robustness_score"] + 0.15
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
    )
    execution_passed = bool(
        oracle.N_MODES == 30
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["valid"] == 1.0
        and classical["valid"] == 1.0
        and classical["heldout_feasibility_rate"] == 1.0
        and difficulty_passed
        and physics["independent_public_equation"]["passed"]
        and physics["trajectory_sensitivity"]["passed"]
        and physics["finite_difference_divergence"]["passed"]
        and physics["no_normal_boundary_flow"]["passed"]
        and all(row["passed"] for row in physics["rk4_convergence"])
        and all(row["passed"] for row in physics["signal_and_boundary"])
        and all(row["passed"] for row in physics["sealed_rollout_boundary"])
        and determinism["passed"]
        and all(row["passed"] for row in noise_label_blind)
        and all(row["passed"] for row in exact)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in misspecified)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_FIELD_OR_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "public_mode_count": oracle.N_MODES,
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "drifter_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
        },
        "always_abstain_baseline": baseline,
        "truth_blind_classical_fit": classical,
        "exact_mechanism_or_refusal_checks": exact,
        "trajectory_identifiability_checks": identifiability,
        "misspecified_resolvability_checks": misspecified,
        "physics_checks": physics,
        "determinism_and_budget_check": determinism,
        "noise_label_blind_checks": noise_label_blind,
        "difficulty_gate": {
            "classical_development_interval": [0.35, 0.85],
            "classical_heldout_interval": [0.20, 0.75],
            "minimum_development_minus_heldout_gap": 0.15,
            "maximum_false_discovery_rate": 0.0,
            "passed": difficulty_passed,
        },
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
