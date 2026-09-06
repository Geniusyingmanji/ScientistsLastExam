"""Truth-blind finite-size-scaling reference using only the public laboratory."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares


def _model(parameters, sizes, temperatures):
    low, high, rate, tc, shift, power = parameters
    centered = temperatures - tc - shift * sizes ** (-power)
    argument = np.clip(rate * centered * sizes**power, -50.0, 50.0)
    return low + (high - low) / (1.0 + np.exp(argument))


def _interpolate(rows, name, temperature):
    ordered = sorted(rows, key=lambda row: row["temperature"])
    x = np.asarray([row["temperature"] for row in ordered], dtype=float)
    y = np.asarray([row[name] for row in ordered], dtype=float)
    return float(np.interp(float(temperature), x, y))


def discover_critical_behavior(
    lattice_sizes, temperature_bounds, experiment, budget_units
):
    low, high = map(float, temperature_bounds)
    evidence = []
    coarse = []
    # Twelve cheap measurements find the only thermodynamic feature without assuming its location.
    for temperature in np.linspace(low + 0.05, high - 0.05, 12):
        row = experiment(12, float(temperature), 256)
        evidence.append(row["query_id"])
        coarse.append(row)
    feature = max(
        coarse,
        key=lambda row: row["susceptibility"] / max(row["standard_errors"]["susceptibility"], 1e-9),
    )
    center = float(feature["temperature"])
    fine_temperatures = np.linspace(
        max(low + 0.01, center - 0.24), min(high - 0.01, center + 0.24), 5
    )
    fine = {24: [], 48: [], 64: []}
    for temperature in fine_temperatures:
        for size in (24, 48, 64):
            row = experiment(size, float(temperature), 256)
            evidence.append(row["query_id"])
            fine[size].append(row)

    all_rows = coarse + [row for rows in fine.values() for row in rows]
    sizes = np.asarray([row["lattice_size"] for row in all_rows], dtype=float)
    temperatures = np.asarray([row["temperature"] for row in all_rows], dtype=float)
    binders = np.asarray([row["binder_cumulant"] for row in all_rows], dtype=float)
    errors = np.asarray([
        max(row["standard_errors"]["binder_cumulant"], 0.008) for row in all_rows
    ], dtype=float)

    initial = np.asarray([0.02, 0.62, 0.7, center, 0.0, 1.0], dtype=float)
    lower_bounds = np.asarray([-1.4, 0.35, 0.02, low, -12.0, 0.05])
    upper_bounds = np.asarray([0.45, 0.75, 4.0, high, 12.0, 2.5])

    def residual(parameters):
        return (_model(parameters, sizes, temperatures) - binders) / errors

    fit = least_squares(
        residual, initial, bounds=(lower_bounds, upper_bounds),
        max_nfev=5000, loss="soft_l1",
    )
    low_fit, high_fit, rate, tc, shift, power = fit.x
    rmse = float(np.sqrt(np.mean((_model(fit.x, sizes, temperatures) - binders) ** 2)))

    # No power-law sharpening means either a smooth crossover or the intentionally unsupported
    # essential (BKT-like) family. Both require refusal under the public model contract.
    if power < 0.72 or rmse > 0.090 or high_fit - low_fit < 0.20:
        return {"abstain": True, "confidence": float(np.clip(1.0 - power / 0.68, 0.25, 0.95))}

    transition_type = "first_order" if power > 1.55 else "continuous"
    if transition_type == "continuous":
        nu = float(1.0 / power)
        magnetizations = []
        used_sizes = []
        for size, rows in fine.items():
            pseudo_tc = tc + shift * size ** (-power)
            magnetizations.append(max(_interpolate(rows, "abs_magnetization", pseudo_tc), 1e-8))
            used_sizes.append(size)
        beta_over_nu = float(np.clip(
            -np.polyfit(np.log(used_sizes), np.log(magnetizations), 1)[0], 0.02, 0.5
        ))
    else:
        nu = None
        beta_over_nu = None

    confidence = float(np.clip(1.0 - rmse / 0.12, 0.05, 0.98))
    return {
        "transition_type": transition_type,
        "critical_temperature": float(tc),
        "nu": nu,
        "beta_over_nu": beta_over_nu,
        "finite_size_shift": float(shift),
        "confidence": confidence,
        "evidence_query_ids": evidence,
        "abstain": False,
    }
