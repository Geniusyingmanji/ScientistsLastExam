"""Deterministic robust pump-and-treat archive oracle."""

from __future__ import annotations

import math

import numpy as np
import xarray as xr

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"exact_discrepancy_strength": 1.00, "stress_strength": 1.00,
        "compliance_limit_multiplier": 1.00},
    2: {"exact_discrepancy_strength": 1.25, "stress_strength": 1.18,
        "compliance_limit_multiplier": 0.85},
    3: {"exact_discrepancy_strength": 1.55, "stress_strength": 1.38,
        "compliance_limit_multiplier": 0.70},
}

DEVELOPMENT_SPECS = (
    (0, 0.72, 620.0, 260.0, 0.000055),
    (1, 0.95, 760.0, 310.0, 0.000040),
    (2, 1.18, 880.0, 360.0, 0.000032),
    (3, 0.84, 700.0, 410.0, 0.000047),
)
HELDOUT_SPECS = (
    (4, 1.05, 930.0, 285.0, 0.000028),
    (5, 0.66, 650.0, 455.0, 0.000062),
)
_BASE_SHIFTS = (
    {"velocity": 0.82, "dispersion": 1.22, "decay": 0.78, "release": 1.10},
    {"velocity": 1.18, "dispersion": 0.82, "decay": 1.18, "release": 1.00},
    {"velocity": 1.04, "dispersion": 1.35, "decay": 0.65, "release": 1.22},
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _scale_shift(shift, strength):
    return {key: 1.0 + float(strength) * (float(value) - 1.0)
            for key, value in shift.items()}


SHIFTS = tuple(_scale_shift(shift, _difficulty_profile()["stress_strength"])
               for shift in _BASE_SHIFTS)


def _exact_shift(spec):
    """Evaluator-only departure from the public homogeneous transport proxy."""
    index = int(spec[0])
    shift = {
        "velocity": 0.96 + 0.025 * (index % 4),
        "dispersion": 1.08 + 0.04 * (index % 3),
        "decay": 0.90 + 0.035 * (index % 3),
        "release": 1.02 + 0.025 * (index % 2),
    }
    return _scale_shift(shift, _difficulty_profile()["exact_discrepancy_strength"])


def _compose_shift(base, perturbation):
    return {key: float(base[key]) * float(perturbation[key]) for key in base}


def _public_problem(spec):
    index, velocity, sigma_x, sigma_y, decay = spec
    source_y = 2100.0 + 260.0 * (index % 3)
    return {
        "domain_size_m": np.asarray((10000.0, 5000.0)),
        "horizon_years": 20.0,
        "evaluation_times_years": np.linspace(1.0, 20.0, 20),
        "source_location_m": np.asarray((900.0 + 120.0 * index, source_y)),
        "initial_contaminant_mass_kg": 1800.0 + 90.0 * index,
        "longitudinal_sigma_m": float(sigma_x),
        "transverse_sigma_m": float(sigma_y),
        "groundwater_velocity_m_day": float(velocity),
        "decay_per_day": float(decay),
        "aquifer_thickness_m": 18.0,
        "effective_porosity": 0.24,
        "receptor_locations_m": np.asarray(((7200.0, source_y - 180.0), (9000.0, source_y + 220.0))),
        "concentration_limit_kg_m3": (1.2e-4
                                       * _difficulty_profile()["compliance_limit_multiplier"]),
        "well_count_bounds": np.asarray((1, 5), dtype=int),
        "pumping_rate_bounds_m3_day": np.asarray((80.0, 950.0)),
        "max_total_pumping_m3_day": 2600.0,
        "start_year_bounds": np.asarray((0.0, 8.0)),
        "fixed_well_cost_usd": 110000.0,
        "pumping_cost_usd_per_m3": 0.075,
        "discount_rate": 0.035,
        "archive_size_bounds": np.asarray((4, 16), dtype=int),
        "well_columns": ["x_m", "y_m", "start_year", "pumping_rate_m3_day"],
    }


def _validate_archive(submission, problem):
    if not isinstance(submission, dict) or set(submission) != {"plans"}:
        raise ValueError("submission must contain only plans")
    plans = submission["plans"]
    if not isinstance(plans, (list, tuple)):
        raise ValueError("plans must be a list")
    lo_archive, hi_archive = map(int, problem["archive_size_bounds"])
    if not lo_archive <= len(plans) <= hi_archive:
        raise ValueError("archive size outside bounds")
    output, fingerprints = [], set()
    for plan in plans:
        wells = np.asarray(plan, dtype=float)
        if wells.ndim != 2 or wells.shape[1] != 4:
            raise ValueError("each plan must have shape (n,4)")
        if not int(problem["well_count_bounds"][0]) <= len(wells) <= int(problem["well_count_bounds"][1]):
            raise ValueError("well count outside bounds")
        if np.any(~np.isfinite(wells)):
            raise ValueError("well plan contains non-finite values")
        length, width = problem["domain_size_m"]
        if np.any(wells[:, 0] < 0.0) or np.any(wells[:, 0] > length) or np.any(wells[:, 1] < 0.0) or np.any(wells[:, 1] > width):
            raise ValueError("well coordinates outside domain")
        if np.any(wells[:, 2] < problem["start_year_bounds"][0]) or np.any(wells[:, 2] > problem["start_year_bounds"][1]):
            raise ValueError("start year outside bounds")
        if np.any(wells[:, 3] < problem["pumping_rate_bounds_m3_day"][0]) or np.any(wells[:, 3] > problem["pumping_rate_bounds_m3_day"][1]):
            raise ValueError("pumping rate outside bounds")
        if np.sum(wells[:, 3]) > problem["max_total_pumping_m3_day"] + 1e-9:
            raise ValueError("total pumping exceeds limit")
        if len(np.unique(np.round(wells[:, :2], 8), axis=0)) != len(wells):
            raise ValueError("well coordinates within a plan must be unique")
        fingerprint = tuple(np.round(wells.ravel(), 8))
        if fingerprint in fingerprints:
            raise ValueError("plans must be unique")
        fingerprints.add(fingerprint)
        output.append(wells.copy())
    return output


def _plan_metrics(problem, wells, shift=None):
    shift = shift or {"velocity": 1.0, "dispersion": 1.0, "decay": 1.0, "release": 1.0}
    velocity = problem["groundwater_velocity_m_day"] * shift["velocity"]
    sigma_x0 = problem["longitudinal_sigma_m"] * shift["dispersion"]
    sigma_y0 = problem["transverse_sigma_m"] * shift["dispersion"]
    decay = problem["decay_per_day"] * shift["decay"]
    initial_mass = problem["initial_contaminant_mass_kg"] * shift["release"]
    source_x, source_y = problem["source_location_m"]
    thickness = problem["aquifer_thickness_m"]
    porosity = problem["effective_porosity"]
    mass_history = []
    concentration_history = []
    for year in problem["evaluation_times_years"]:
        days = 365.25 * float(year)
        center_x = source_x + velocity * days
        sigma_x = math.sqrt(sigma_x0 ** 2 + 2.0 * 8.0 * days)
        sigma_y = math.sqrt(sigma_y0 ** 2 + 2.0 * 2.2 * days)
        natural = math.exp(-decay * days)
        removal = 0.0
        for x, y, start_year, rate in wells:
            active_days = max(0.0, days - 365.25 * start_year)
            path_x = source_x + velocity * 365.25 * start_year
            along = (x - path_x) / max(sigma_x, 1.0)
            across = (y - source_y) / max(sigma_y, 1.0)
            proximity = math.exp(-0.5 * (0.32 * along * along + across * across))
            removal += 2.4e-7 * rate * active_days * proximity
        mass = initial_mass * natural * math.exp(-removal)
        mass_history.append(mass)
        denominator = 2.0 * math.pi * sigma_x * sigma_y * thickness * porosity
        receptor_row = []
        for receptor_x, receptor_y in problem["receptor_locations_m"]:
            exponent = -0.5 * (((receptor_x - center_x) / sigma_x) ** 2
                               + ((receptor_y - source_y) / sigma_y) ** 2)
            concentration = mass / max(denominator, 1e-12) * math.exp(exponent)
            receptor_row.append(concentration)
        concentration_history.append(receptor_row)
    transport = xr.Dataset(
        data_vars={
            "remaining_mass_kg": ("time_years", np.asarray(mass_history, dtype=float)),
            "receptor_concentration_kg_m3": (
                ("time_years", "receptor"),
                np.asarray(concentration_history, dtype=float),
            ),
        },
        coords={
            "time_years": np.asarray(problem["evaluation_times_years"], dtype=float),
            "receptor": np.arange(len(problem["receptor_locations_m"])),
        },
    )
    final_mass = float(transport["remaining_mass_kg"].isel(time_years=-1).item())
    max_receptor = float(transport["receptor_concentration_kg_m3"].max().item())
    horizon_days = 365.25 * problem["horizon_years"]
    pumped = float(np.sum([rate * max(0.0, horizon_days - 365.25 * start)
                           for _, _, start, rate in wells]))
    mean_discount = (1.0 + problem["discount_rate"]) ** (-0.5 * problem["horizon_years"])
    cost = len(wells) * problem["fixed_well_cost_usd"] + pumped * problem["pumping_cost_usd_per_m3"] * mean_discount
    compliance = max_receptor <= problem["concentration_limit_kg_m3"]
    return {"remaining_mass_kg": final_mass, "max_receptor_concentration_kg_m3": max_receptor,
            "lifecycle_cost_usd": float(cost), "total_pumped_m3": pumped, "compliant": bool(compliance)}


def _point(problem, metrics):
    if not metrics["compliant"]:
        return None
    cleanup = float(np.clip(1.0 - metrics["remaining_mass_kg"] / problem["initial_contaminant_mass_kg"], 0.0, 1.0))
    max_cost = (5.0 * problem["fixed_well_cost_usd"]
                + problem["max_total_pumping_m3_day"] * 365.25 * problem["horizon_years"]
                * problem["pumping_cost_usd_per_m3"])
    cost_quality = float(np.clip(1.0 - metrics["lifecycle_cost_usd"] / max_cost, 0.0, 1.0))
    return cleanup, cost_quality


def _hypervolume(problem, plans, shift=None):
    points, rows = [], []
    for plan in plans:
        metrics = _plan_metrics(problem, plan, shift)
        rows.append(metrics)
        point = _point(problem, metrics)
        if point is not None:
            points.append(point)
    if not points:
        return 0.0, rows
    points = sorted(set(points))
    nondominated = []
    for point in points:
        if not any(other[0] >= point[0] and other[1] >= point[1]
                   and (other[0] > point[0] or other[1] > point[1]) for other in points):
            nondominated.append(point)
    area, previous_x = 0.0, 0.0
    for cleanup, cost_quality in sorted(nondominated):
        area += max(0.0, cleanup - previous_x) * cost_quality
        previous_x = max(previous_x, cleanup)
    return float(area), rows


def _baseline_archive(problem):
    source_x, source_y = problem["source_location_m"]
    center = min(problem["domain_size_m"][0] * 0.8,
                 source_x + 0.55 * problem["groundwater_velocity_m_day"] * 365.25 * problem["horizon_years"])
    qmin = problem["pumping_rate_bounds_m3_day"][0]
    return [np.asarray([[center, np.clip(source_y + offset, 0.0, problem["domain_size_m"][1]), 2.0, 1.15 * qmin]])
            for offset in (-600.0, -200.0, 200.0, 600.0)]


def _reference_archive(problem):
    source_x, source_y = problem["source_location_m"]
    velocity = problem["groundwater_velocity_m_day"]
    plans = []
    for count in (2, 3, 4, 5):
        for rate in (420.0, 620.0, 820.0):
            rate = min(rate, problem["max_total_pumping_m3_day"] / count)
            xs = np.linspace(source_x + 1400.0, min(problem["domain_size_m"][0] - 300.0,
                                                    source_x + velocity * 365.25 * 13.0), count)
            wells = np.column_stack((xs, source_y + np.linspace(-180.0, 180.0, count),
                                     np.linspace(0.5, 2.5, count), np.full(count, rate)))
            plans.append(wells)
    unique = []
    fingerprints = set()
    for plan in plans:
        fingerprint = tuple(np.round(plan.ravel(), 8))
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            unique.append(plan)
    return unique


def _normalize(value, baseline, reference):
    if reference <= baseline + 1e-12:
        return 0.0
    return float(max(0.0, (value - baseline) / (reference - baseline)))


def _evaluate_problem(candidate, spec, split, index):
    problem = _public_problem(spec)
    try:
        plans = _validate_archive(candidate(problem), problem)
        exact = _exact_shift(spec)
        exact_hv, exact_rows = _hypervolume(problem, plans, exact)
        proxy_hv, _ = _hypervolume(problem, plans)
        baseline_hv, _ = _hypervolume(problem, _baseline_archive(problem), exact)
        reference_hv, _ = _hypervolume(problem, _reference_archive(problem), exact)
        shifted_worlds = [_compose_shift(exact, shift) for shift in SHIFTS]
        shifted = [_hypervolume(problem, plans, shift)[0] for shift in shifted_worlds]
        baseline_shifted = [_hypervolume(problem, _baseline_archive(problem), shift)[0]
                            for shift in shifted_worlds]
        reference_shifted = [_hypervolume(problem, _reference_archive(problem), shift)[0]
                             for shift in shifted_worlds]
        shifted_scores = [_normalize(v, b, r) for v, b, r in zip(shifted, baseline_shifted, reference_shifted)]
        compliant = [row for row in exact_rows if row["compliant"]]
        return {"split": split, "problem_index": index, "valid": True,
                "score": _normalize(exact_hv, baseline_hv, reference_hv),
                "robustness_score": min(shifted_scores), "raw_exact_hypervolume": exact_hv,
                "raw_proxy_hypervolume": proxy_hv,
                "exact_feasibility_rate": len(compliant) / len(exact_rows),
                "mean_remaining_mass_kg": float(np.mean([r["remaining_mass_kg"] for r in compliant])) if compliant else problem["initial_contaminant_mass_kg"],
                "mean_lifecycle_cost_usd": float(np.mean([r["lifecycle_cost_usd"] for r in compliant])) if compliant else 0.0,
                "worst_shifted_raw_hypervolume": min(shifted)}
    except Exception:
        return {"split": split, "problem_index": index, "valid": False, "score": 0.0,
                "robustness_score": 0.0, "raw_exact_hypervolume": 0.0,
                "raw_proxy_hypervolume": 0.0, "exact_feasibility_rate": 0.0,
                "mean_remaining_mass_kg": 0.0, "mean_lifecycle_cost_usd": 0.0,
                "worst_shifted_raw_hypervolume": 0.0}


def evaluate(design_remediation):
    development = [_evaluate_problem(design_remediation, spec, "development", i)
                   for i, spec in enumerate(DEVELOPMENT_SPECS)]
    heldout = [_evaluate_problem(design_remediation, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev_valid = all(row["valid"] for row in development)
    hold_valid = all(row["valid"] for row in heldout)
    return {
        "combined_score": float(np.mean([r["score"] for r in development])) if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": float(np.mean([r["exact_feasibility_rate"] for r in development])),
        "robustness_score": float(np.mean([r["robustness_score"] for r in development])) if dev_valid else 0.0,
        "development_exact_hypervolume": float(np.mean([r["raw_exact_hypervolume"] for r in development])),
        "development_proxy_hypervolume": float(np.mean([r["raw_proxy_hypervolume"] for r in development])),
        "development_mean_remaining_mass_kg": float(np.mean([r["mean_remaining_mass_kg"] for r in development])),
        "development_mean_lifecycle_cost_usd": float(np.mean([r["mean_lifecycle_cost_usd"] for r in development])),
        "heldout_score": float(np.mean([r["score"] for r in heldout])) if hold_valid else 0.0,
        "heldout_feasibility_rate": float(np.mean([r["exact_feasibility_rate"] for r in heldout])),
        "heldout_robustness_score": float(np.mean([r["robustness_score"] for r in heldout])) if hold_valid else 0.0,
        "per_problem": development + heldout,
    }
