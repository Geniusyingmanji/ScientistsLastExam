#!/usr/bin/env python3
"""Calibrate HeatExchanger-v2 references, physics and proxy/exact separation."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/HeatExchangerDesign"
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("heat_exchanger_v2_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load HeatExchanger-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _geometry(problem, design):
    diameter, length, count, baffle, passes = map(float, design)
    outer = diameter + 2.0 * float(problem["tube_wall_thickness_m"])
    pitch = float(problem["tube_pitch_ratio"]) * outer
    shell = pitch * math.sqrt(count / 0.78) + outer
    return {
        "diameter": diameter,
        "outer": outer,
        "length": length,
        "count": int(round(count)),
        "baffle": baffle,
        "passes": int(round(passes)),
        "pitch": pitch,
        "shell": shell,
        "area": math.pi * outer * length * count,
        "volume": math.pi * shell**2 * length / 4.0,
        "shell_hydraulic_diameter": (
            4.0 * (pitch**2 - math.pi * outer**2 / 4.0) / (math.pi * outer)
        ),
        "shell_flow_area": shell * baffle * (pitch - outer) / pitch,
    }


def _independent_proxy(problem, design):
    geometry = _geometry(problem, design)
    hot = problem["hot_reference_properties"]
    cold = problem["cold_reference_properties"]
    hot_flow = float(problem["hot_mass_flow_kg_s"])
    cold_flow = float(problem["cold_mass_flow_kg_s"])
    tubes_per_pass = geometry["count"] / geometry["passes"]
    hot_area = tubes_per_pass * math.pi * geometry["diameter"]**2 / 4.0
    hot_velocity = hot_flow / (float(hot["rho_kg_m3"]) * hot_area)
    hot_reynolds = (
        float(hot["rho_kg_m3"]) * hot_velocity * geometry["diameter"]
        / float(hot["viscosity_pa_s"])
    )
    hot_prandtl = (
        float(hot["cp_j_kgk"]) * float(hot["viscosity_pa_s"])
        / float(hot["conductivity_w_mk"])
    )
    if hot_reynolds <= 2300.0:
        hot_nusselt = 3.66
    else:
        hot_nusselt = 0.023 * hot_reynolds**0.8 * hot_prandtl**0.4
    if hot_reynolds < 2300.0:
        hot_friction = 64.0 / hot_reynolds
    else:
        hot_friction = 0.3164 * hot_reynolds**-0.25
    hot_coefficient = (
        hot_nusselt * float(hot["conductivity_w_mk"]) / geometry["diameter"]
    )

    cold_velocity = (
        cold_flow
        / (float(cold["rho_kg_m3"]) * geometry["shell_flow_area"])
    )
    cold_reynolds = (
        float(cold["rho_kg_m3"]) * cold_velocity
        * geometry["shell_hydraulic_diameter"]
        / float(cold["viscosity_pa_s"])
    )
    cold_prandtl = (
        float(cold["cp_j_kgk"]) * float(cold["viscosity_pa_s"])
        / float(cold["conductivity_w_mk"])
    )
    cold_nusselt = max(
        3.66,
        0.33 * cold_reynolds**0.60 * cold_prandtl ** (1.0 / 3.0),
    )
    cold_coefficient = (
        cold_nusselt * float(cold["conductivity_w_mk"])
        / geometry["shell_hydraulic_diameter"]
    )
    diameter = geometry["diameter"]
    outer = geometry["outer"]
    resistance = (
        outer / (hot_coefficient * diameter)
        + outer * float(problem["hot_fouling_resistance_m2k_w"]) / diameter
        + outer * math.log(outer / diameter)
        / (2.0 * float(problem["tube_wall_conductivity_w_mk"]))
        + float(problem["cold_fouling_resistance_m2k_w"])
        + 1.0 / cold_coefficient
    )
    overall = 1.0 / resistance
    hot_capacity = hot_flow * float(hot["cp_j_kgk"])
    cold_capacity = cold_flow * float(cold["cp_j_kgk"])
    minimum = min(hot_capacity, cold_capacity)
    maximum = max(hot_capacity, cold_capacity)
    ratio = minimum / maximum
    ntu = overall * geometry["area"] / minimum
    if abs(1.0 - ratio) < 1e-10:
        effectiveness = ntu / (1.0 + ntu)
    else:
        exponential = math.exp(-ntu * (1.0 - ratio))
        effectiveness = (1.0 - exponential) / (1.0 - ratio * exponential)
    duty = effectiveness * minimum * (
        float(problem["hot_inlet_temperature_k"])
        - float(problem["cold_inlet_temperature_k"])
    )

    hot_dynamic = float(hot["rho_kg_m3"]) * hot_velocity**2 / 2.0
    cold_dynamic = float(cold["rho_kg_m3"]) * cold_velocity**2 / 2.0
    hot_drop = (
        hot_friction * geometry["length"] * geometry["passes"]
        / diameter * hot_dynamic
        + (1.5 + 1.5 * max(0, geometry["passes"] - 1)) * hot_dynamic
    )
    shell_friction = (
        24.0 / cold_reynolds
        if cold_reynolds < 100.0 else 0.20 * cold_reynolds**-0.15
    )
    cold_drop = (
        shell_friction * geometry["shell"] / geometry["shell_hydraulic_diameter"]
        * geometry["length"] / geometry["baffle"] * cold_dynamic
        + 1.5 * cold_dynamic
    )
    cost = problem["cost_model"]
    capital = (
        float(cost["fixed_capital_usd"])
        + float(cost["area_coefficient"]) * geometry["area"]**0.82
        + float(cost["shell_volume_coefficient"]) * geometry["volume"]**0.65
        + float(cost["extra_pass_capital_usd"])
        * max(0, geometry["passes"] - 1)
    )
    pumping_power = (
        hot_flow * hot_drop / float(hot["rho_kg_m3"])
        + cold_flow * cold_drop / float(cold["rho_kg_m3"])
    ) / float(cost["pump_efficiency"])
    annual = (
        float(cost["capital_annualization"]) * capital
        + pumping_power / 1000.0
        * float(cost["operating_hours_per_year"])
        * float(cost["electricity_usd_per_kwh"])
    )
    feasible = bool(
        geometry["shell"] <= float(problem["max_shell_diameter_m"]) + 1e-12
        and geometry["count"] >= 6 * geometry["passes"]
        and geometry["count"] % geometry["passes"] == 0
        and geometry["length"] / geometry["baffle"] >= 3.0
        and hot_drop <= float(problem["hot_pressure_drop_limit_pa"])
        and cold_drop <= float(problem["cold_pressure_drop_limit_pa"])
    )
    return {
        "feasible": feasible,
        "heat_duty_w": float(duty),
        "effectiveness": float(effectiveness),
        "heat_transfer_area_m2": float(geometry["area"]),
        "shell_volume_m3": float(geometry["volume"]),
        "shell_diameter_m": float(geometry["shell"]),
        "hot_pressure_drop_pa": float(hot_drop),
        "cold_pressure_drop_pa": float(cold_drop),
        "pumping_power_w": float(pumping_power),
        "annualized_cost_usd": float(annual),
    }


def _independent_pool(problem, seed):
    unit = qmc.Sobol(d=5, scramble=True, seed=int(seed)).random_base2(12)
    lower = np.asarray((
        problem["tube_inner_diameter_bounds_m"][0],
        problem["tube_length_bounds_m"][0],
        problem["tube_count_bounds"][0],
        problem["baffle_spacing_bounds_m"][0],
        1.0,
    ))
    upper = np.asarray((
        problem["tube_inner_diameter_bounds_m"][1],
        problem["tube_length_bounds_m"][1],
        problem["tube_count_bounds"][1] + 0.999999,
        problem["baffle_spacing_bounds_m"][1],
        4.999999,
    ))
    designs = lower + unit * (upper - lower)
    designs[:, 2] = np.floor(designs[:, 2])
    designs[:, 4] = np.floor(designs[:, 4])
    return designs


def _pareto_indices(records):
    feasible = [index for index, row in enumerate(records) if row["feasible"]]
    front = []
    for index in feasible:
        row = records[index]
        if not any(
            other_index != index
            and records[other_index]["heat_duty_w"] >= row["heat_duty_w"] - 1e-10
            and records[other_index]["annualized_cost_usd"]
            <= row["annualized_cost_usd"] + 1e-10
            and (
                records[other_index]["heat_duty_w"] > row["heat_duty_w"] + 1e-10
                or records[other_index]["annualized_cost_usd"]
                < row["annualized_cost_usd"] - 1e-10
            )
            for other_index in feasible
        ):
            front.append(index)
    return tuple(front)


def _cost_bounds(problem):
    cost = problem["cost_model"]

    def capital(diameter, length, count, passes):
        design = (
            diameter, length, count,
            problem["baffle_spacing_bounds_m"][1], passes,
        )
        geometry = _geometry(problem, design)
        value = (
            float(cost["fixed_capital_usd"])
            + float(cost["area_coefficient"]) * geometry["area"]**0.82
            + float(cost["shell_volume_coefficient"]) * geometry["volume"]**0.65
            + float(cost["extra_pass_capital_usd"]) * max(0, passes - 1)
        )
        return float(cost["capital_annualization"]) * value

    lower = capital(
        problem["tube_inner_diameter_bounds_m"][0],
        problem["tube_length_bounds_m"][0],
        problem["tube_count_bounds"][0], 1,
    )
    upper = capital(
        problem["tube_inner_diameter_bounds_m"][1],
        problem["tube_length_bounds_m"][1],
        problem["tube_count_bounds"][1], 4,
    )
    hot = problem["hot_reference_properties"]
    cold = problem["cold_reference_properties"]
    hydraulic = (
        float(problem["hot_mass_flow_kg_s"])
        * float(problem["hot_pressure_drop_limit_pa"])
        / float(hot["rho_kg_m3"])
        + float(problem["cold_mass_flow_kg_s"])
        * float(problem["cold_pressure_drop_limit_pa"])
        / float(cold["rho_kg_m3"])
    ) / float(cost["pump_efficiency"])
    upper += (
        hydraulic / 1000.0 * float(cost["operating_hours_per_year"])
        * float(cost["electricity_usd_per_kwh"])
    )
    return float(lower), float(upper)


def _quality(problem, record):
    hot_capacity = (
        float(problem["hot_mass_flow_kg_s"])
        * float(problem["hot_reference_properties"]["cp_j_kgk"])
    )
    cold_capacity = (
        float(problem["cold_mass_flow_kg_s"])
        * float(problem["cold_reference_properties"]["cp_j_kgk"])
    )
    maximum_duty = min(hot_capacity, cold_capacity) * (
        float(problem["hot_inlet_temperature_k"])
        - float(problem["cold_inlet_temperature_k"])
    )
    cost_low, cost_high = _cost_bounds(problem)
    return (
        float(np.clip(record["heat_duty_w"] / maximum_duty, 0.0, 1.0)),
        float(np.clip(
            (cost_high - record["annualized_cost_usd"])
            / (cost_high - cost_low), 0.0, 1.0,
        )),
    )


def _hypervolume(problem, records):
    points = [_quality(problem, records[index]) for index in _pareto_indices(records)]
    unique_x = sorted(set(x for x, _ in points if x > 0.0))
    area = 0.0
    previous = 0.0
    for value in unique_x:
        height = max((y for x, y in points if x >= value - 1e-15), default=0.0)
        area += (value - previous) * max(height, 0.0)
        previous = value
    return float(np.clip(area, 0.0, 1.0))


def _shift_problem(problem, shift):
    shifted = copy.deepcopy(problem)
    shifted["hot_mass_flow_kg_s"] *= float(shift["hot_flow_scale"])
    shifted["cold_mass_flow_kg_s"] *= float(shift["cold_flow_scale"])
    shifted["hot_inlet_temperature_k"] += float(shift["hot_inlet_delta_k"])
    shifted["cold_inlet_temperature_k"] += float(shift["cold_inlet_delta_k"])
    return shifted


def _select_greedy(problem, record_sets, allowed, baseline_hv, pool_hv, robust,
                   shift_specs=()):
    chosen = []
    remaining = list(allowed)
    shifted_problems = [problem] + [
        _shift_problem(problem, shift) for shift in shift_specs
    ]
    for _ in range(24):
        best = None
        for index in remaining:
            take = chosen + [index]
            hypervolumes = [
                _hypervolume(view, [records[row] for row in take])
                for view, records in zip(shifted_problems, record_sets)
            ]
            if robust:
                gains = [
                    (value - baseline) / max(reference - baseline, 1e-12)
                    for value, baseline, reference in zip(
                        hypervolumes[1:], baseline_hv[1:], pool_hv[1:]
                    )
                ]
                objective = min(gains) + 0.05 * sum(gains) / len(gains)
            else:
                objective = hypervolumes[0]
            key = (objective, hypervolumes[0], -index)
            if best is None or key > best[0]:
                best = (key, index)
        chosen.append(best[1])
        remaining.remove(best[1])
    return chosen


def _reproduce_reference(oracle, instance):
    problem = instance["problem"]
    reference = oracle.REFERENCE_SOBOL[instance["name"]]
    pool = _independent_pool(problem, reference["seed"])
    pool_match = bool(np.array_equal(
        pool, oracle._sobol_design_pool(problem, reference["seed"])
    ))
    proxy = [_independent_proxy(problem, design) for design in pool]
    oracle_proxy = [oracle._proxy_metrics(instance, design) for design in pool]
    proxy_error = max(
        abs(float(left[key]) - float(right[key]))
        for left, right in zip(proxy, oracle_proxy)
        for key in (
            "heat_duty_w", "effectiveness", "annualized_cost_usd",
            "hot_pressure_drop_pa", "cold_pressure_drop_pa", "pumping_power_w",
            "heat_transfer_area_m2", "shell_volume_m3", "shell_diameter_m",
        )
    )
    feasibility_match = all(
        left["feasible"] == right["feasible"]
        for left, right in zip(proxy, oracle_proxy)
    )
    feasible = [index for index, row in enumerate(proxy) if row["feasible"]]
    shortlist = set(_pareto_indices(proxy))
    qualities = {index: _quality(problem, proxy[index]) for index in feasible}
    for weight in np.linspace(0.0, 1.0, 81):
        shortlist.update(sorted(
            feasible,
            key=lambda index: (
                weight * qualities[index][0]
                + (1.0 - weight) * qualities[index][1]
            ),
            reverse=True,
        )[:12])
    for criterion in (
        lambda value: value[0],
        lambda value: value[1],
        lambda value: value[0] * value[1],
        lambda value: min(value),
    ):
        shortlist.update(sorted(
            feasible, key=lambda index: criterion(qualities[index]), reverse=True
        )[:32])
    original_indices = sorted(shortlist)
    candidates = pool[original_indices]
    record_sets = [
        [oracle._exact_metrics(instance, design) for design in candidates]
    ] + [
        [oracle._exact_metrics(instance, design, shift) for design in candidates]
        for shift in oracle.SHIFT_SPECS
    ]
    baseline_designs = oracle._baseline_archive(problem)
    _, baseline_exact, baseline_shifted = oracle._evaluate_archive(
        instance, baseline_designs
    )
    views = [problem] + [
        _shift_problem(problem, shift) for shift in oracle.SHIFT_SPECS
    ]
    baseline_sets = [baseline_exact] + baseline_shifted
    baseline_hv = [
        _hypervolume(view, records)
        for view, records in zip(views, baseline_sets)
    ]
    pool_hv = [
        _hypervolume(view, records)
        for view, records in zip(views, record_sets)
    ]
    nominal_allowed = [
        index for index in range(len(candidates))
        if record_sets[0][index]["feasible"]
    ]
    robust_allowed = [
        index for index in range(len(candidates))
        if all(records[index]["feasible"] for records in record_sets)
    ]
    nominal_local = _select_greedy(
        problem, record_sets, nominal_allowed, baseline_hv, pool_hv, False,
        oracle.SHIFT_SPECS,
    )
    robust_local = _select_greedy(
        problem, record_sets, robust_allowed, baseline_hv, pool_hv, True,
        oracle.SHIFT_SPECS,
    )
    nominal_indices = tuple(original_indices[index] for index in nominal_local)
    robust_indices = tuple(original_indices[index] for index in robust_local)

    # A strict proxy-only classical archive never sees exact or shifted records.
    proxy_front = list(_pareto_indices(proxy))
    if len(proxy_front) < 24:
        raise RuntimeError("proxy Pareto front is too small for an archive")
    proxy_local = _select_greedy(
        problem, [proxy], proxy_front, [0.0], [1.0], False
    )
    proxy_archive = pool[proxy_local].copy()
    return {
        "name": instance["name"],
        "sobol_seed": reference["seed"],
        "pool_size": len(pool),
        "proxy_feasible_count": len(feasible),
        "shortlist_size": len(candidates),
        "nominal_allowed_count": len(nominal_allowed),
        "robust_allowed_count": len(robust_allowed),
        "pool_matches_oracle": pool_match,
        "maximum_independent_proxy_error": proxy_error,
        "proxy_feasibility_matches": feasibility_match,
        "nominal_indices_match": nominal_indices == tuple(reference["nominal"]),
        "robust_indices_match": robust_indices == tuple(reference["robust"]),
        "proxy_only_archive": proxy_archive,
    }


def _policy_for(oracle, family):
    def design(problem):
        for instance in oracle.INSTANCES:
            if instance["problem"] == problem:
                if family == "baseline":
                    return oracle._baseline_archive(problem)
                source = (
                    oracle.REFERENCE_ARCHIVES
                    if family == "nominal" else oracle.ROBUST_REFERENCE_ARCHIVES
                )
                return source[instance["name"]].copy()
        raise ValueError("unknown public heat-exchanger problem")
    return design


def _proxy_policy(oracle, reproductions):
    archives = {
        row["name"]: np.asarray(row["proxy_only_archive"], dtype=float)
        for row in reproductions
    }

    def design(problem):
        for instance in oracle.INSTANCES:
            if instance["problem"] == problem:
                return archives[instance["name"]].copy()
        raise ValueError("unknown public heat-exchanger problem")
    return design


def _anchor_checks(oracle):
    rows = []
    for instance in oracle.INSTANCES:
        declared = oracle.CALIBRATED_ANCHORS[instance["name"]]
        reproduced = oracle._recompute_anchors(instance)
        errors = []
        for key, value in declared.items():
            if isinstance(value, tuple):
                errors.extend(
                    abs(float(left) - float(right))
                    for left, right in zip(value, reproduced[key])
                )
            else:
                errors.append(abs(float(value) - float(reproduced[key])))
        nominal = oracle.REFERENCE_ARCHIVES[instance["name"]]
        robust = oracle.ROBUST_REFERENCE_ARCHIVES[instance["name"]]
        _, nominal_exact, nominal_shifts = oracle._evaluate_archive(instance, nominal)
        _, robust_exact, robust_shifts = oracle._evaluate_archive(instance, robust)
        nominal_blockage_hv = oracle._hypervolume(
            instance, nominal_shifts[-1], oracle.SHIFT_SPECS[-1]
        )
        robust_blockage_hv = oracle._hypervolume(
            instance, robust_shifts[-1], oracle.SHIFT_SPECS[-1]
        )
        maximum_boundary_residual = max(
            record["boundary_residual_k"]
            for records in (nominal_exact, robust_exact) + tuple(nominal_shifts) + tuple(robust_shifts)
            for record in records
            if record["feasible"]
        )
        rows.append({
            "name": instance["name"],
            "maximum_anchor_error": max(errors),
            "nominal_feasible_count": sum(row["feasible"] for row in nominal_exact),
            "robust_nominal_feasible_count": sum(row["feasible"] for row in robust_exact),
            "robust_shift_feasible_counts": [
                sum(row["feasible"] for row in records) for records in robust_shifts
            ],
            "nominal_raw_hypervolume": oracle._hypervolume(instance, nominal_exact),
            "robust_raw_nominal_hypervolume": oracle._hypervolume(instance, robust_exact),
            "nominal_blockage_hypervolume": nominal_blockage_hv,
            "robust_blockage_hypervolume": robust_blockage_hv,
            "maximum_boundary_residual_k": maximum_boundary_residual,
            "passed": bool(
                max(errors) <= 1e-12
                and all(row["feasible"] for row in nominal_exact)
                and all(row["feasible"] for row in robust_exact)
                and all(all(row["feasible"] for row in records) for records in robust_shifts)
                and robust_blockage_hv > nominal_blockage_hv + 1e-9
                and maximum_boundary_residual <= 1e-5
            ),
        })
    return rows


def _segment_convergence_checks(oracle):
    checks = []
    original_segments = oracle.N_SEGMENTS
    try:
        for instance in oracle.INSTANCES:
            designs = oracle.REFERENCE_ARCHIVES[instance["name"]][[0, 11, 23]]
            by_resolution = {}
            for segments in (10, 20, 40):
                oracle.N_SEGMENTS = segments
                by_resolution[segments] = [
                    oracle._exact_metrics(instance, design) for design in designs
                ]
            duty_errors = []
            cost_errors = []
            for coarse, fine in zip(by_resolution[10], by_resolution[40]):
                duty_errors.append(abs(
                    coarse["heat_duty_w"] - fine["heat_duty_w"]
                ) / max(abs(fine["heat_duty_w"]), 1e-12))
                cost_errors.append(abs(
                    coarse["annualized_cost_usd"]
                    - fine["annualized_cost_usd"]
                ) / max(abs(fine["annualized_cost_usd"]), 1e-12))
            maximum_residual = max(
                row["boundary_residual_k"]
                for records in by_resolution.values() for row in records
            )
            checks.append({
                "name": instance["name"],
                "design_count": len(designs),
                "segment_resolutions": [10, 20, 40],
                "maximum_10_vs_40_heat_duty_relative_error": max(duty_errors),
                "maximum_10_vs_40_cost_relative_error": max(cost_errors),
                "maximum_boundary_residual_k": maximum_residual,
                "passed": bool(
                    max(duty_errors) <= 0.007
                    and max(cost_errors) <= 5e-4
                    and maximum_residual <= 1e-5
                ),
            })
    finally:
        oracle.N_SEGMENTS = original_segments
    return checks


def calibrate():
    oracle = _load_oracle()
    reproductions = [_reproduce_reference(oracle, instance) for instance in oracle.INSTANCES]
    baseline = oracle.evaluate(_policy_for(oracle, "baseline"))
    nominal = oracle.evaluate(_policy_for(oracle, "nominal"))
    robust = oracle.evaluate(_policy_for(oracle, "robust"))
    proxy_only = oracle.evaluate(_proxy_policy(oracle, reproductions))
    invalid = {
        "nonfinite": oracle.evaluate(
            lambda _problem: np.full((oracle.MIN_ARCHIVE_SIZE, 5), np.nan)
        ),
        "wrong_shape": oracle.evaluate(
            lambda _problem: np.ones((oracle.MIN_ARCHIVE_SIZE, 4))
        ),
        "nonintegral": oracle.evaluate(
            lambda problem: oracle._baseline_archive(problem)
            + np.asarray((0.0, 0.0, 0.5, 0.0, 0.0))
        ),
        "duplicate_only": oracle.evaluate(
            lambda problem: np.repeat(
                oracle._baseline_archive(problem)[:1], oracle.MIN_ARCHIVE_SIZE, axis=0
            )
        ),
    }
    anchors = _anchor_checks(oracle)
    convergence = _segment_convergence_checks(oracle)
    for row in reproductions:
        row.pop("proxy_only_archive")
    invalid_passed = all(
        report["valid"] == 0.0 and report["combined_score"] == 0.0
        for report in invalid.values()
    )
    execution_passed = bool(
        baseline["valid"] == 1.0 and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["valid"] == 1.0 and nominal["combined_score"] > 0.999999
        and nominal["heldout_exact_score"] > 0.999999
        and robust["valid"] == 1.0 and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and proxy_only["valid"] == 1.0
        and invalid_passed
        and all(row["passed"] for row in anchors)
        and all(row["passed"] for row in convergence)
        and all(
            row["pool_matches_oracle"]
            and row["maximum_independent_proxy_error"] <= 1e-8
            and row["proxy_feasibility_matches"]
            and row["nominal_indices_match"]
            and row["robust_indices_match"]
            for row in reproductions
        )
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "CORRELATION_BASED_SCIENTIFIC_OPTIMIZATION_NOT_EXPERIMENTAL_DISCOVERY_OR_MODEL_LEADERBOARD",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reference_method": {
            "description": (
                "Fixed-seed 4096-point scrambled Sobol public-proxy screen; exact nominal "
                "and shifted evaluation of a scalarization/Pareto shortlist; deterministic "
                "greedy two-objective hypervolume selection of 24-point nominal and "
                "all-shift-feasible robust archives."
            ),
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
            "experimental_truth_claimed": False,
        },
        "baseline": baseline,
        "nominal_reference_policy": nominal,
        "robust_reference_policy": robust,
        "proxy_only_classical_policy": proxy_only,
        "invalid_archives": invalid,
        "reference_reproduction": reproductions,
        "anchor_and_physics_checks": anchors,
        "segment_convergence_checks": convergence,
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
