"""Multi-fidelity Pareto oracle for counter-flow heat-exchanger design.

The candidate returns a bounded archive of shell-and-tube geometries.  A public, cheap
constant-property model and a sealed segmented model evaluate the same archive.  Search is
selected only by development exact-model hypervolume.  Proxy/exact disagreement, held-out
transfer and operating/fouling shifts are retained as evaluator-only diagnostics.

This is a deterministic correlation-based engineering benchmark, not experimental truth.
The segmented model is deliberately more detailed than the public proxy, but downstream
engineering claims still require CFD/process-simulator and experimental replication.
"""

from __future__ import annotations

import copy
import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import qmc


MIN_ARCHIVE_SIZE = 4
MAX_ARCHIVE_SIZE = 24
DESIGN_COLUMNS = (
    "tube_inner_diameter_m",
    "tube_length_m",
    "tube_count",
    "baffle_spacing_m",
    "tube_passes",
)
N_SEGMENTS = 10
BOUNDARY_TOLERANCE_K = 2.0e-6


def _fluid(cp, rho, viscosity, conductivity, reference_temperature):
    return {
        "cp_j_kgk": float(cp),
        "rho_kg_m3": float(rho),
        "viscosity_pa_s": float(viscosity),
        "conductivity_w_mk": float(conductivity),
        "reference_temperature_k": float(reference_temperature),
    }


# Instance membership is interleaved.  Candidates receive only the public problem mapping;
# split, temperature-property coefficients and all shifted conditions remain sealed.
INSTANCE_SPECS = (
    {
        "name": "dev_water_process",
        "split": "development",
        "hot_inlet_k": 368.0,
        "cold_inlet_k": 291.0,
        "hot_mass_flow_kg_s": 1.65,
        "cold_mass_flow_kg_s": 2.10,
        "hot_reference": _fluid(4190.0, 965.0, 3.15e-4, 0.674, 330.0),
        "cold_reference": _fluid(4180.0, 995.0, 8.20e-4, 0.610, 315.0),
        "hot_family": "water",
        "cold_family": "water",
        "diameter_bounds_m": (0.010, 0.026),
        "length_bounds_m": (1.4, 5.6),
        "tube_count_bounds": (24, 180),
        "baffle_spacing_bounds_m": (0.10, 0.46),
        "max_shell_diameter_m": 0.54,
        "pressure_drop_limits_pa": (18000.0, 4200.0),
        "fouling_resistances_m2k_w": (8.0e-5, 1.2e-4),
        "cost": (0.14, 1800.0, 300.0, 5200.0, 110.0, 7200.0, 0.16, 0.72),
    },
    {
        "name": "heldout_viscous_oil",
        "split": "heldout",
        "hot_inlet_k": 413.0,
        "cold_inlet_k": 298.0,
        "hot_mass_flow_kg_s": 1.15,
        "cold_mass_flow_kg_s": 1.90,
        "hot_reference": _fluid(2260.0, 815.0, 1.35e-2, 0.132, 360.0),
        "cold_reference": _fluid(4180.0, 992.0, 6.60e-4, 0.628, 325.0),
        "hot_family": "oil",
        "cold_family": "water",
        "diameter_bounds_m": (0.011, 0.030),
        "length_bounds_m": (1.8, 6.2),
        "tube_count_bounds": (28, 190),
        "baffle_spacing_bounds_m": (0.12, 0.52),
        "max_shell_diameter_m": 0.62,
        "pressure_drop_limits_pa": (4500.0, 900.0),
        "fouling_resistances_m2k_w": (2.5e-4, 1.4e-4),
        "cost": (0.15, 2100.0, 330.0, 5500.0, 125.0, 7600.0, 0.17, 0.70),
    },
    {
        "name": "dev_oil_cooler",
        "split": "development",
        "hot_inlet_k": 398.0,
        "cold_inlet_k": 295.0,
        "hot_mass_flow_kg_s": 1.35,
        "cold_mass_flow_kg_s": 1.75,
        "hot_reference": _fluid(2180.0, 830.0, 9.5e-3, 0.137, 352.0),
        "cold_reference": _fluid(4180.0, 994.0, 7.20e-4, 0.620, 320.0),
        "hot_family": "oil",
        "cold_family": "water",
        "diameter_bounds_m": (0.011, 0.029),
        "length_bounds_m": (1.6, 5.8),
        "tube_count_bounds": (26, 176),
        "baffle_spacing_bounds_m": (0.11, 0.48),
        "max_shell_diameter_m": 0.58,
        "pressure_drop_limits_pa": (6500.0, 900.0),
        "fouling_resistances_m2k_w": (2.2e-4, 1.3e-4),
        "cost": (0.15, 1950.0, 320.0, 5400.0, 120.0, 7400.0, 0.17, 0.70),
    },
    {
        "name": "dev_glycol_recovery",
        "split": "development",
        "hot_inlet_k": 356.0,
        "cold_inlet_k": 283.0,
        "hot_mass_flow_kg_s": 1.80,
        "cold_mass_flow_kg_s": 1.55,
        "hot_reference": _fluid(4175.0, 973.0, 3.90e-4, 0.660, 325.0),
        "cold_reference": _fluid(3520.0, 1055.0, 4.8e-3, 0.405, 310.0),
        "hot_family": "water",
        "cold_family": "glycol",
        "diameter_bounds_m": (0.010, 0.027),
        "length_bounds_m": (1.5, 5.5),
        "tube_count_bounds": (24, 170),
        "baffle_spacing_bounds_m": (0.10, 0.44),
        "max_shell_diameter_m": 0.55,
        "pressure_drop_limits_pa": (9000.0, 2800.0),
        "fouling_resistances_m2k_w": (1.0e-4, 2.0e-4),
        "cost": (0.14, 1850.0, 305.0, 5250.0, 115.0, 7000.0, 0.18, 0.71),
    },
    {
        "name": "heldout_brine_recovery",
        "split": "heldout",
        "hot_inlet_k": 378.0,
        "cold_inlet_k": 278.0,
        "hot_mass_flow_kg_s": 2.25,
        "cold_mass_flow_kg_s": 1.70,
        "hot_reference": _fluid(4010.0, 1010.0, 1.20e-3, 0.540, 330.0),
        "cold_reference": _fluid(3370.0, 1080.0, 3.20e-3, 0.455, 305.0),
        "hot_family": "brine",
        "cold_family": "glycol",
        "diameter_bounds_m": (0.012, 0.031),
        "length_bounds_m": (1.8, 6.4),
        "tube_count_bounds": (30, 200),
        "baffle_spacing_bounds_m": (0.12, 0.54),
        "max_shell_diameter_m": 0.66,
        "pressure_drop_limits_pa": (18000.0, 1400.0),
        "fouling_resistances_m2k_w": (1.8e-4, 2.4e-4),
        "cost": (0.16, 2200.0, 340.0, 5700.0, 130.0, 7800.0, 0.19, 0.69),
    },
    {
        "name": "dev_high_flow_water",
        "split": "development",
        "hot_inlet_k": 388.0,
        "cold_inlet_k": 303.0,
        "hot_mass_flow_kg_s": 2.60,
        "cold_mass_flow_kg_s": 2.35,
        "hot_reference": _fluid(4210.0, 951.0, 2.45e-4, 0.682, 345.0),
        "cold_reference": _fluid(4185.0, 987.0, 5.25e-4, 0.642, 330.0),
        "hot_family": "water",
        "cold_family": "water",
        "diameter_bounds_m": (0.012, 0.032),
        "length_bounds_m": (1.6, 6.0),
        "tube_count_bounds": (32, 210),
        "baffle_spacing_bounds_m": (0.12, 0.52),
        "max_shell_diameter_m": 0.68,
        "pressure_drop_limits_pa": (13000.0, 2200.0),
        "fouling_resistances_m2k_w": (7.0e-5, 1.1e-4),
        "cost": (0.15, 2050.0, 315.0, 5600.0, 120.0, 7600.0, 0.16, 0.73),
    },
)


PROPERTY_SLOPES = {
    # fractional change per kelvin about the supplied reference state
    "water": (3.0e-4, -3.8e-4, -2.25e-2, 9.0e-4),
    "oil": (1.15e-3, -6.5e-4, -2.85e-2, -3.0e-4),
    "glycol": (7.5e-4, -5.5e-4, -3.15e-2, -5.0e-4),
    "brine": (4.0e-4, -4.2e-4, -2.45e-2, 4.0e-4),
}


SHIFT_SPECS = (
    {
        "name": "fouling_and_roughness_growth",
        "hot_flow_scale": 1.0,
        "cold_flow_scale": 1.0,
        "hot_inlet_delta_k": 0.0,
        "cold_inlet_delta_k": 0.0,
        "fouling_scale": 2.2,
        "viscosity_scale": 1.0,
        "inner_diameter_scale": 1.0,
        "active_tube_fraction": 1.0,
        "roughness_scale": 3.0,
    },
    {
        "name": "manufacturing_inner_diameter_shift",
        "hot_flow_scale": 1.0,
        "cold_flow_scale": 1.0,
        "hot_inlet_delta_k": 0.0,
        "cold_inlet_delta_k": 0.0,
        "fouling_scale": 1.0,
        "viscosity_scale": 1.0,
        "inner_diameter_scale": 0.94,
        "active_tube_fraction": 1.0,
        "roughness_scale": 1.5,
    },
    {
        "name": "partial_blockage_and_operation_shift",
        "hot_flow_scale": 1.12,
        "cold_flow_scale": 0.90,
        "hot_inlet_delta_k": -6.0,
        "cold_inlet_delta_k": 4.0,
        "fouling_scale": 1.8,
        "viscosity_scale": 1.15,
        "inner_diameter_scale": 0.94,
        "active_tube_fraction": 0.82,
        "roughness_scale": 3.0,
    },
)


def _public_problem(spec):
    annualization, fixed, area, shell, pass_cost, hours, price, efficiency = spec["cost"]
    return {
        "hot_inlet_temperature_k": float(spec["hot_inlet_k"]),
        "cold_inlet_temperature_k": float(spec["cold_inlet_k"]),
        "hot_mass_flow_kg_s": float(spec["hot_mass_flow_kg_s"]),
        "cold_mass_flow_kg_s": float(spec["cold_mass_flow_kg_s"]),
        "hot_reference_properties": copy.deepcopy(spec["hot_reference"]),
        "cold_reference_properties": copy.deepcopy(spec["cold_reference"]),
        "tube_inner_diameter_bounds_m": tuple(spec["diameter_bounds_m"]),
        "tube_length_bounds_m": tuple(spec["length_bounds_m"]),
        "tube_count_bounds": tuple(spec["tube_count_bounds"]),
        "baffle_spacing_bounds_m": tuple(spec["baffle_spacing_bounds_m"]),
        "tube_pass_bounds": (1, 4),
        "tube_wall_thickness_m": 0.0012,
        "tube_wall_conductivity_w_mk": 16.0,
        "tube_pitch_ratio": 1.28,
        "max_shell_diameter_m": float(spec["max_shell_diameter_m"]),
        "hot_pressure_drop_limit_pa": float(spec["pressure_drop_limits_pa"][0]),
        "cold_pressure_drop_limit_pa": float(spec["pressure_drop_limits_pa"][1]),
        "hot_fouling_resistance_m2k_w": float(spec["fouling_resistances_m2k_w"][0]),
        "cold_fouling_resistance_m2k_w": float(spec["fouling_resistances_m2k_w"][1]),
        "cost_model": {
            "capital_annualization": float(annualization),
            "fixed_capital_usd": float(fixed),
            "area_coefficient": float(area),
            "shell_volume_coefficient": float(shell),
            "extra_pass_capital_usd": float(pass_cost),
            "operating_hours_per_year": float(hours),
            "electricity_usd_per_kwh": float(price),
            "pump_efficiency": float(efficiency),
        },
        "archive_size_bounds": (MIN_ARCHIVE_SIZE, MAX_ARCHIVE_SIZE),
        "design_columns": DESIGN_COLUMNS,
    }


def _make_instance(spec):
    instance = dict(spec)
    instance["problem"] = _public_problem(spec)
    return instance


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "development")
HELDOUT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "heldout")


def _geometry(problem, design):
    diameter, length, count_value, baffle, passes_value = map(float, design)
    count = int(round(count_value))
    passes = int(round(passes_value))
    wall = float(problem["tube_wall_thickness_m"])
    outer = diameter + 2.0 * wall
    pitch = float(problem["tube_pitch_ratio"]) * outer
    shell_diameter = pitch * math.sqrt(count / 0.78) + outer
    area = math.pi * outer * length * count
    shell_volume = math.pi * shell_diameter**2 * length / 4.0
    equivalent_shell_diameter = (
        4.0 * (pitch**2 - math.pi * outer**2 / 4.0) / (math.pi * outer)
    )
    shell_flow_area = shell_diameter * baffle * (pitch - outer) / pitch
    return {
        "diameter": diameter,
        "outer_diameter": outer,
        "length": length,
        "count": count,
        "baffle_spacing": baffle,
        "passes": passes,
        "pitch": pitch,
        "shell_diameter": shell_diameter,
        "heat_transfer_area_m2": area,
        "shell_volume_m3": shell_volume,
        "equivalent_shell_diameter": equivalent_shell_diameter,
        "shell_flow_area_m2": shell_flow_area,
    }


def _validate_archive(value, problem):
    raw = np.asarray(value)
    if raw.ndim != 2 or raw.shape[1] != len(DESIGN_COLUMNS):
        raise ValueError("return a two-dimensional archive with five design columns")
    if raw.shape[0] < MIN_ARCHIVE_SIZE or raw.shape[0] > MAX_ARCHIVE_SIZE:
        raise ValueError("archive must contain between 4 and 24 designs")
    designs = np.asarray(raw, dtype=float)
    if not np.all(np.isfinite(designs)):
        raise ValueError("archive designs must be finite")
    diameter_bounds = problem["tube_inner_diameter_bounds_m"]
    length_bounds = problem["tube_length_bounds_m"]
    count_bounds = problem["tube_count_bounds"]
    baffle_bounds = problem["baffle_spacing_bounds_m"]
    pass_bounds = problem["tube_pass_bounds"]
    bounds = (diameter_bounds, length_bounds, count_bounds, baffle_bounds, pass_bounds)
    for column, (lower, upper) in enumerate(bounds):
        if np.any(designs[:, column] < float(lower)) or np.any(
            designs[:, column] > float(upper)
        ):
            raise ValueError("design variable outside public bounds")
    for column in (2, 4):
        if np.any(abs(designs[:, column] - np.rint(designs[:, column])) > 1e-9):
            raise ValueError("tube count and pass count must be integers")
    canonical = designs.copy()
    canonical[:, 2] = np.rint(canonical[:, 2])
    canonical[:, 4] = np.rint(canonical[:, 4])
    rounded = np.round(canonical, decimals=12)
    if len(np.unique(rounded, axis=0)) < MIN_ARCHIVE_SIZE:
        raise ValueError("archive must contain at least four unique designs")
    return canonical


def _friction_factor(reynolds, relative_roughness, exact):
    reynolds = max(float(reynolds), 1e-12)
    if reynolds < 2300.0:
        return 64.0 / reynolds
    if exact:
        term = (float(relative_roughness) / 3.7) ** 1.11 + 6.9 / reynolds
        return (-1.8 * math.log10(term)) ** -2
    return 0.3164 * reynolds ** -0.25


def _tube_nusselt(reynolds, prandtl, friction, exact):
    reynolds = max(float(reynolds), 1e-12)
    prandtl = max(float(prandtl), 1e-12)
    if reynolds <= 2300.0:
        return 3.66
    if exact:
        turbulent = (
            (friction / 8.0) * (reynolds - 1000.0) * prandtl
            / (1.0 + 12.7 * math.sqrt(friction / 8.0) * (prandtl ** (2.0 / 3.0) - 1.0))
        )
        if reynolds < 4000.0:
            weight = (reynolds - 2300.0) / 1700.0
            return (1.0 - weight) * 3.66 + weight * max(turbulent, 3.66)
        return max(turbulent, 3.66)
    return 0.023 * reynolds**0.8 * prandtl**0.4


def _properties(reference, family, temperature, viscosity_scale=1.0):
    cp_slope, rho_slope, mu_slope, k_slope = PROPERTY_SLOPES[family]
    delta = float(temperature) - float(reference["reference_temperature_k"])
    cp = float(reference["cp_j_kgk"]) * float(np.clip(1.0 + cp_slope * delta, 0.70, 1.45))
    rho = float(reference["rho_kg_m3"]) * float(np.clip(1.0 + rho_slope * delta, 0.72, 1.30))
    viscosity = float(reference["viscosity_pa_s"]) * math.exp(mu_slope * delta)
    viscosity *= float(viscosity_scale)
    conductivity = float(reference["conductivity_w_mk"]) * float(
        np.clip(1.0 + k_slope * delta, 0.72, 1.30)
    )
    return {"cp": cp, "rho": rho, "mu": viscosity, "k": conductivity}


def _constant_properties(reference):
    return {
        "cp": float(reference["cp_j_kgk"]),
        "rho": float(reference["rho_kg_m3"]),
        "mu": float(reference["viscosity_pa_s"]),
        "k": float(reference["conductivity_w_mk"]),
    }


def _transport(problem, geometry, hot, cold, hot_flow, cold_flow, exact,
               fouling_scale, roughness_scale=1.0):
    diameter = geometry["diameter"]
    count = geometry["count"]
    passes = geometry["passes"]
    tubes_per_pass = count / float(passes)
    hot_flow_area = tubes_per_pass * math.pi * diameter**2 / 4.0
    hot_velocity = hot_flow / (hot["rho"] * hot_flow_area)
    hot_reynolds = hot["rho"] * hot_velocity * diameter / hot["mu"]
    hot_prandtl = hot["cp"] * hot["mu"] / hot["k"]
    hot_friction = _friction_factor(
        hot_reynolds, 4.5e-5 * float(roughness_scale) / diameter, exact
    )
    hot_nusselt = _tube_nusselt(hot_reynolds, hot_prandtl, hot_friction, exact)
    hot_coefficient = hot_nusselt * hot["k"] / diameter

    shell_area = geometry["shell_flow_area_m2"]
    shell_velocity = cold_flow / (cold["rho"] * shell_area)
    shell_de = geometry["equivalent_shell_diameter"]
    shell_reynolds = cold["rho"] * shell_velocity * shell_de / cold["mu"]
    shell_prandtl = cold["cp"] * cold["mu"] / cold["k"]
    if exact:
        if shell_reynolds < 100.0:
            shell_nusselt = 0.90 * max(shell_reynolds, 1e-12) ** 0.40 * shell_prandtl ** 0.36
        else:
            shell_nusselt = 0.36 * shell_reynolds**0.55 * shell_prandtl ** (1.0 / 3.0)
        leakage_correction = float(np.clip(
            0.76 + 0.16 * geometry["baffle_spacing"] / geometry["shell_diameter"],
            0.72,
            0.94,
        ))
        shell_nusselt *= leakage_correction
    else:
        shell_nusselt = max(3.66, 0.33 * max(shell_reynolds, 1e-12) ** 0.60 * shell_prandtl ** (1.0 / 3.0))
    shell_coefficient = shell_nusselt * cold["k"] / shell_de

    outer = geometry["outer_diameter"]
    wall_k = float(problem["tube_wall_conductivity_w_mk"])
    hot_fouling = float(problem["hot_fouling_resistance_m2k_w"]) * float(fouling_scale)
    cold_fouling = float(problem["cold_fouling_resistance_m2k_w"]) * float(fouling_scale)
    resistance = (
        outer / (hot_coefficient * diameter)
        + outer * hot_fouling / diameter
        + outer * math.log(outer / diameter) / (2.0 * wall_k)
        + cold_fouling
        + 1.0 / shell_coefficient
    )
    overall = 1.0 / resistance
    return {
        "overall_coefficient": overall,
        "hot_velocity": hot_velocity,
        "cold_velocity": shell_velocity,
        "hot_reynolds": hot_reynolds,
        "cold_reynolds": shell_reynolds,
        "hot_friction": hot_friction,
    }


def _counterflow_effectiveness(ntu, capacity_ratio):
    ntu = max(float(ntu), 0.0)
    capacity_ratio = float(np.clip(capacity_ratio, 0.0, 1.0))
    if abs(1.0 - capacity_ratio) < 1e-10:
        return ntu / (1.0 + ntu)
    exponent = math.exp(-ntu * (1.0 - capacity_ratio))
    return (1.0 - exponent) / (1.0 - capacity_ratio * exponent)


def _pressure_and_cost(problem, geometry, hot, cold, hot_flow, cold_flow,
                       transport, exact, segment_length=None):
    diameter = geometry["diameter"]
    passes = geometry["passes"]
    hot_dynamic = hot["rho"] * transport["hot_velocity"] ** 2 / 2.0
    cold_dynamic = cold["rho"] * transport["cold_velocity"] ** 2 / 2.0
    path_length = geometry["length"] if segment_length is None else float(segment_length)
    hot_drop = transport["hot_friction"] * path_length * passes / diameter * hot_dynamic
    shell_re = max(transport["cold_reynolds"], 1e-12)
    shell_friction = 24.0 / shell_re if shell_re < 100.0 else 0.20 * shell_re**-0.15
    cold_drop = (
        shell_friction
        * geometry["shell_diameter"] / geometry["equivalent_shell_diameter"]
        * path_length / geometry["baffle_spacing"]
        * cold_dynamic
    )
    if segment_length is not None:
        return hot_drop, cold_drop
    hot_drop += (1.5 + 1.5 * max(0, passes - 1)) * hot_dynamic
    cold_drop += 1.5 * cold_dynamic
    return _annual_cost(problem, geometry, hot_flow, cold_flow, hot, cold, hot_drop, cold_drop)


def _annual_cost(problem, geometry, hot_flow, cold_flow, hot, cold, hot_drop, cold_drop):
    cost = problem["cost_model"]
    capital = (
        float(cost["fixed_capital_usd"])
        + float(cost["area_coefficient"]) * geometry["heat_transfer_area_m2"] ** 0.82
        + float(cost["shell_volume_coefficient"]) * geometry["shell_volume_m3"] ** 0.65
        + float(cost["extra_pass_capital_usd"]) * max(0, geometry["passes"] - 1)
    )
    hydraulic_power = (
        hot_flow * hot_drop / hot["rho"] + cold_flow * cold_drop / cold["rho"]
    ) / float(cost["pump_efficiency"])
    electricity = (
        hydraulic_power / 1000.0
        * float(cost["operating_hours_per_year"])
        * float(cost["electricity_usd_per_kwh"])
    )
    annual = float(cost["capital_annualization"]) * capital + electricity
    return {
        "hot_pressure_drop_pa": float(hot_drop),
        "cold_pressure_drop_pa": float(cold_drop),
        "pumping_power_w": float(hydraulic_power),
        "annualized_cost_usd": float(annual),
        "annualized_capital_usd": float(cost["capital_annualization"]) * capital,
        "annual_electricity_cost_usd": float(electricity),
    }


def _base_geometry_feasible(problem, geometry):
    return bool(
        geometry["shell_diameter"] <= float(problem["max_shell_diameter_m"]) + 1e-12
        and geometry["count"] >= 6 * geometry["passes"]
        and geometry["count"] % geometry["passes"] == 0
        and geometry["length"] / geometry["baffle_spacing"] >= 3.0
        and geometry["shell_flow_area_m2"] > 0.0
    )


def _proxy_metrics(instance, design):
    problem = instance["problem"]
    geometry = _geometry(problem, design)
    hot = _constant_properties(problem["hot_reference_properties"])
    cold = _constant_properties(problem["cold_reference_properties"])
    hot_flow = float(problem["hot_mass_flow_kg_s"])
    cold_flow = float(problem["cold_mass_flow_kg_s"])
    transport = _transport(
        problem, geometry, hot, cold, hot_flow, cold_flow, False, 1.0, 1.0
    )
    hot_capacity = hot_flow * hot["cp"]
    cold_capacity = cold_flow * cold["cp"]
    minimum = min(hot_capacity, cold_capacity)
    maximum = max(hot_capacity, cold_capacity)
    ntu = transport["overall_coefficient"] * geometry["heat_transfer_area_m2"] / minimum
    effectiveness = _counterflow_effectiveness(ntu, minimum / maximum)
    q_max = minimum * (
        float(problem["hot_inlet_temperature_k"]) - float(problem["cold_inlet_temperature_k"])
    )
    duty = effectiveness * q_max
    cost = _pressure_and_cost(
        problem, geometry, hot, cold, hot_flow, cold_flow, transport, False
    )
    feasible = bool(
        _base_geometry_feasible(problem, geometry)
        and cost["hot_pressure_drop_pa"] <= float(problem["hot_pressure_drop_limit_pa"])
        and cost["cold_pressure_drop_pa"] <= float(problem["cold_pressure_drop_limit_pa"])
    )
    return dict({
        "feasible": feasible,
        "heat_duty_w": float(duty),
        "effectiveness": float(effectiveness),
        "heat_transfer_area_m2": geometry["heat_transfer_area_m2"],
        "shell_volume_m3": geometry["shell_volume_m3"],
        "shell_diameter_m": geometry["shell_diameter"],
    }, **cost)


def _shifted_problem(instance, shift):
    problem = copy.deepcopy(instance["problem"])
    problem["hot_mass_flow_kg_s"] *= float(shift["hot_flow_scale"])
    problem["cold_mass_flow_kg_s"] *= float(shift["cold_flow_scale"])
    problem["hot_inlet_temperature_k"] += float(shift["hot_inlet_delta_k"])
    problem["cold_inlet_temperature_k"] += float(shift["cold_inlet_delta_k"])
    return problem


def _exact_metrics(instance, design, shift=None):
    shift = shift or {
        "name": "nominal",
        "hot_flow_scale": 1.0,
        "cold_flow_scale": 1.0,
        "hot_inlet_delta_k": 0.0,
        "cold_inlet_delta_k": 0.0,
        "fouling_scale": 1.0,
        "viscosity_scale": 1.0,
        "inner_diameter_scale": 1.0,
        "active_tube_fraction": 1.0,
        "roughness_scale": 1.0,
    }
    problem = _shifted_problem(instance, shift)
    geometry = _geometry(problem, design)
    # Outer bundle dimensions remain those of the intended design.  Manufacturing undersize
    # changes only the tube-side bore; blockage reduces hydraulically and thermally active
    # tubes while leaving the installed shell and capital cost unchanged.
    geometry["diameter"] *= float(shift["inner_diameter_scale"])
    geometry["count"] *= float(shift["active_tube_fraction"])
    hot_flow = float(problem["hot_mass_flow_kg_s"])
    cold_flow = float(problem["cold_mass_flow_kg_s"])
    hot_inlet = float(problem["hot_inlet_temperature_k"])
    cold_inlet = float(problem["cold_inlet_temperature_k"])
    viscosity_scale = float(shift["viscosity_scale"])
    fouling_scale = float(shift["fouling_scale"])
    roughness_scale = float(shift["roughness_scale"])
    segment_length = geometry["length"] / N_SEGMENTS

    def integrate(cold_outlet):
        hot_temperature = hot_inlet
        cold_temperature = float(cold_outlet)
        duty = 0.0
        hot_drop = 0.0
        cold_drop = 0.0
        hot_rho_sum = 0.0
        cold_rho_sum = 0.0
        for _ in range(N_SEGMENTS):
            hot = _properties(
                problem["hot_reference_properties"], instance["hot_family"],
                hot_temperature, viscosity_scale,
            )
            cold = _properties(
                problem["cold_reference_properties"], instance["cold_family"],
                cold_temperature, viscosity_scale,
            )
            transport = _transport(
                problem, geometry, hot, cold, hot_flow, cold_flow, True,
                fouling_scale, roughness_scale,
            )
            conductance = (
                transport["overall_coefficient"]
                * math.pi * geometry["outer_diameter"] * geometry["count"]
                * segment_length
            )
            delta = hot_temperature - cold_temperature
            hot_capacity = hot_flow * hot["cp"]
            cold_capacity = cold_flow * cold["cp"]
            exponent = conductance * (1.0 / cold_capacity - 1.0 / hot_capacity)
            if abs(exponent) <= 1e-9:
                local_duty = conductance * delta
            else:
                local_duty = conductance * delta * math.expm1(exponent) / exponent
            if not math.isfinite(local_duty) or local_duty < 0.0:
                raise ValueError("invalid segmented heat transfer")
            hot_temperature -= local_duty / (hot_flow * hot["cp"])
            cold_temperature -= local_duty / (cold_flow * cold["cp"])
            duty += local_duty
            d_hot, d_cold = _pressure_and_cost(
                problem, geometry, hot, cold, hot_flow, cold_flow, transport,
                True, segment_length,
            )
            hot_drop += d_hot
            cold_drop += d_cold
            hot_rho_sum += hot["rho"]
            cold_rho_sum += cold["rho"]
        return {
            "residual": cold_temperature - cold_inlet,
            "hot_outlet": hot_temperature,
            "cold_end": cold_temperature,
            "duty": duty,
            "hot_drop": hot_drop,
            "cold_drop": cold_drop,
            "hot_rho": hot_rho_sum / N_SEGMENTS,
            "cold_rho": cold_rho_sum / N_SEGMENTS,
        }

    lower = cold_inlet
    upper = hot_inlet - 1e-7
    low_result = integrate(lower)
    high_result = integrate(upper)
    low_residual = float(low_result["residual"])
    high_residual = float(high_result["residual"])
    if low_residual > 0.0 or high_residual < 0.0:
        raise ValueError("segmented counter-flow boundary solve is not bracketed")
    # Brent's bracketed interpolation is both deterministic and materially faster here than
    # a fixed 34-step shooting bisection, while retaining a strict convergence guarantee.
    cold_outlet = float(brentq(
        lambda value: float(integrate(value)["residual"]),
        lower,
        upper,
        xtol=2.0e-7,
        rtol=4.0 * np.finfo(float).eps,
        maxiter=40,
    ))
    result = integrate(cold_outlet)

    hot_ref = _properties(
        problem["hot_reference_properties"], instance["hot_family"],
        0.5 * (hot_inlet + result["hot_outlet"]), viscosity_scale,
    )
    cold_ref = _properties(
        problem["cold_reference_properties"], instance["cold_family"],
        0.5 * (cold_inlet + cold_outlet), viscosity_scale,
    )
    hot_dynamic_area = (
        geometry["count"] / geometry["passes"]
        * math.pi * geometry["diameter"]**2 / 4.0
    )
    hot_velocity = hot_flow / (hot_ref["rho"] * hot_dynamic_area)
    cold_velocity = cold_flow / (cold_ref["rho"] * geometry["shell_flow_area_m2"])
    result["hot_drop"] += (1.5 + 1.5 * max(0, geometry["passes"] - 1)) * hot_ref["rho"] * hot_velocity**2 / 2.0
    result["cold_drop"] += 1.5 * cold_ref["rho"] * cold_velocity**2 / 2.0
    cost = _annual_cost(
        problem, geometry, hot_flow, cold_flow, hot_ref, cold_ref,
        result["hot_drop"], result["cold_drop"],
    )
    reference_hot_capacity = hot_flow * float(problem["hot_reference_properties"]["cp_j_kgk"])
    reference_cold_capacity = cold_flow * float(problem["cold_reference_properties"]["cp_j_kgk"])
    q_max = min(reference_hot_capacity, reference_cold_capacity) * (hot_inlet - cold_inlet)
    effectiveness = result["duty"] / max(q_max, 1e-12)
    energy_error = abs(
        result["cold_end"] - cold_inlet
    )
    feasible = bool(
        _base_geometry_feasible(problem, _geometry(problem, design))
        and cost["hot_pressure_drop_pa"] <= float(problem["hot_pressure_drop_limit_pa"])
        and cost["cold_pressure_drop_pa"] <= float(problem["cold_pressure_drop_limit_pa"])
        and cold_inlet <= result["hot_outlet"] <= hot_inlet
        and cold_inlet <= cold_outlet <= hot_inlet
        and 0.0 <= effectiveness <= 1.02
        and energy_error <= 1e-5
    )
    return dict({
        "feasible": feasible,
        "heat_duty_w": float(result["duty"]),
        "effectiveness": float(effectiveness),
        "hot_outlet_temperature_k": float(result["hot_outlet"]),
        "cold_outlet_temperature_k": float(cold_outlet),
        "boundary_residual_k": float(energy_error),
        "heat_transfer_area_m2": geometry["heat_transfer_area_m2"],
        "shell_volume_m3": geometry["shell_volume_m3"],
        "shell_diameter_m": geometry["shell_diameter"],
    }, **cost)


def _cost_bounds(problem):
    cost = problem["cost_model"]
    d_low, d_high = problem["tube_inner_diameter_bounds_m"]
    l_low, l_high = problem["tube_length_bounds_m"]
    n_low, n_high = problem["tube_count_bounds"]

    def capital_bound(diameter, length, count, passes):
        baffle = problem["baffle_spacing_bounds_m"][1]
        geometry = _geometry(problem, (diameter, length, count, baffle, passes))
        capital = (
            float(cost["fixed_capital_usd"])
            + float(cost["area_coefficient"]) * geometry["heat_transfer_area_m2"] ** 0.82
            + float(cost["shell_volume_coefficient"]) * geometry["shell_volume_m3"] ** 0.65
            + float(cost["extra_pass_capital_usd"]) * max(0, passes - 1)
        )
        return float(cost["capital_annualization"]) * capital

    lower = capital_bound(d_low, l_low, n_low, 1)
    upper_capital = capital_bound(d_high, l_high, n_high, 4)
    maximum_hydraulic = (
        float(problem["hot_mass_flow_kg_s"]) * float(problem["hot_pressure_drop_limit_pa"])
        / float(problem["hot_reference_properties"]["rho_kg_m3"])
        + float(problem["cold_mass_flow_kg_s"]) * float(problem["cold_pressure_drop_limit_pa"])
        / float(problem["cold_reference_properties"]["rho_kg_m3"])
    ) / float(cost["pump_efficiency"])
    upper = upper_capital + (
        maximum_hydraulic / 1000.0
        * float(cost["operating_hours_per_year"])
        * float(cost["electricity_usd_per_kwh"])
    )
    return float(lower), float(max(upper, lower + 1.0))


def _qualities(instance, metrics, shift=None):
    problem = instance["problem"] if shift is None else _shifted_problem(instance, shift)
    hot_capacity = (
        float(problem["hot_mass_flow_kg_s"])
        * float(problem["hot_reference_properties"]["cp_j_kgk"])
    )
    cold_capacity = (
        float(problem["cold_mass_flow_kg_s"])
        * float(problem["cold_reference_properties"]["cp_j_kgk"])
    )
    q_max = min(hot_capacity, cold_capacity) * (
        float(problem["hot_inlet_temperature_k"]) - float(problem["cold_inlet_temperature_k"])
    )
    cost_low, cost_high = _cost_bounds(problem)
    thermal = float(np.clip(metrics["heat_duty_w"] / max(q_max, 1e-12), 0.0, 1.0))
    economy = float(np.clip(
        (cost_high - metrics["annualized_cost_usd"]) / (cost_high - cost_low), 0.0, 1.0
    ))
    return thermal, economy


def _pareto_indices(records):
    feasible = [index for index, row in enumerate(records) if row["feasible"]]
    front = []
    for index in feasible:
        row = records[index]
        dominated = False
        for other_index in feasible:
            if other_index == index:
                continue
            other = records[other_index]
            no_worse = (
                other["heat_duty_w"] >= row["heat_duty_w"] - 1e-10
                and other["annualized_cost_usd"] <= row["annualized_cost_usd"] + 1e-10
            )
            strictly_better = (
                other["heat_duty_w"] > row["heat_duty_w"] + 1e-10
                or other["annualized_cost_usd"] < row["annualized_cost_usd"] - 1e-10
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(index)
    return tuple(front)


def _hypervolume(instance, records, shift=None):
    points = []
    for index in _pareto_indices(records):
        points.append(_qualities(instance, records[index], shift))
    if not points:
        return 0.0
    unique_x = sorted(set(float(point[0]) for point in points if point[0] > 0.0))
    area = 0.0
    previous = 0.0
    for x_value in unique_x:
        best_y = max(
            (float(y) for x, y in points if x >= x_value - 1e-15),
            default=0.0,
        )
        area += (x_value - previous) * max(best_y, 0.0)
        previous = x_value
    return float(np.clip(area, 0.0, 1.0))


def _rankdata(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    return ranks


def _rank_correlation(instance, proxy_records, exact_records):
    if len(proxy_records) < 3:
        return 0.0
    proxy_utility = []
    exact_utility = []
    for proxy, exact in zip(proxy_records, exact_records):
        proxy_quality = _qualities(instance, proxy)
        exact_quality = _qualities(instance, exact)
        proxy_utility.append(sum(proxy_quality) if proxy["feasible"] else -1.0)
        exact_utility.append(sum(exact_quality) if exact["feasible"] else -1.0)
    proxy_rank = _rankdata(proxy_utility)
    exact_rank = _rankdata(exact_utility)
    proxy_rank -= np.mean(proxy_rank)
    exact_rank -= np.mean(exact_rank)
    denominator = float(np.linalg.norm(proxy_rank) * np.linalg.norm(exact_rank))
    if denominator <= 1e-15:
        return 0.0
    return float(np.clip(np.dot(proxy_rank, exact_rank) / denominator, -1.0, 1.0))


def _archive_diagnostics(instance, designs, proxy, exact, shifts):
    proxy_front = set(_pareto_indices(proxy))
    exact_front = set(_pareto_indices(exact))
    false_promotions = proxy_front - exact_front
    exact_front_records = [exact[index] for index in sorted(exact_front)]
    shift_hypervolumes = [
        _hypervolume(instance, records, shift)
        for shift, records in zip(SHIFT_SPECS, shifts)
    ]
    return {
        "archive_size": int(len(designs)),
        "proxy_feasibility_rate": float(np.mean([row["feasible"] for row in proxy])),
        "exact_feasibility_rate": float(np.mean([row["feasible"] for row in exact])),
        "proxy_front_size": len(proxy_front),
        "exact_front_size": len(exact_front),
        "false_promotion_rate": (
            float(len(false_promotions) / len(proxy_front)) if proxy_front else 0.0
        ),
        "proxy_exact_rank_correlation": _rank_correlation(instance, proxy, exact),
        "raw_proxy_hypervolume": _hypervolume(instance, proxy),
        "raw_exact_hypervolume": _hypervolume(instance, exact),
        "raw_shifted_hypervolumes": shift_hypervolumes,
        "worst_shifted_raw_hypervolume": min(shift_hypervolumes),
        "mean_exact_front_heat_duty_kw": (
            float(np.mean([row["heat_duty_w"] for row in exact_front_records])) / 1000.0
            if exact_front_records else 0.0
        ),
        "mean_exact_front_annualized_cost_usd": (
            float(np.mean([row["annualized_cost_usd"] for row in exact_front_records]))
            if exact_front_records else 0.0
        ),
        "mean_exact_front_pumping_power_w": (
            float(np.mean([row["pumping_power_w"] for row in exact_front_records]))
            if exact_front_records else 0.0
        ),
        "mean_exact_front_area_m2": (
            float(np.mean([row["heat_transfer_area_m2"] for row in exact_front_records]))
            if exact_front_records else 0.0
        ),
    }


def _baseline_archive(problem):
    d_low, d_high = problem["tube_inner_diameter_bounds_m"]
    l_low, l_high = problem["tube_length_bounds_m"]
    n_low, n_high = problem["tube_count_bounds"]
    b_low, b_high = problem["baffle_spacing_bounds_m"]
    rows = []
    for fraction in np.linspace(0.18, 0.78, 12):
        rows.append((
            d_low + 0.72 * (d_high - d_low),
            l_low + fraction * (l_high - l_low),
            int(round(n_low + fraction * 0.62 * (n_high - n_low))),
            b_low + 0.78 * (b_high - b_low),
            1,
        ))
    return np.asarray(rows, dtype=float)


# Fixed Sobol seeds and selected sample indices make every normalization witness compact and
# exactly reproducible.  The calibration command starts from all 4096 points, uses the cheap
# proxy only to form a shortlist, evaluates that shortlist with the segmented oracle, and then
# greedily maximizes two-dimensional hypervolume.  These archives are strong feasible local
# witnesses, not global-optimality certificates.
REFERENCE_SOBOL = {
    "dev_water_process": {
        "seed": 8113,
        "nominal": (2877, 1261, 1941, 1106, 2957, 2557, 1578, 1741, 141, 3373,
                    2925, 3746, 3522, 82, 210, 2781, 2290, 386, 50, 354, 965,
                    477, 4082, 2325),
        "robust": (589, 1941, 3218, 1106, 2125, 3853, 2290, 141, 2925, 1741,
                   1293, 50, 3746, 1914, 1261, 2325, 477, 2877, 386, 965, 2690,
                   3917, 354, 530),
    },
    "heldout_viscous_oil": {
        "seed": 8114,
        "nominal": (500, 235, 2091, 1428, 3264, 3988, 555, 2475, 2028, 2923,
                    1323, 1643, 660, 1122, 3179, 1044, 1780, 3636, 2776, 2795,
                    3339, 2059, 1291, 820),
        "robust": (500, 235, 2091, 1428, 3264, 3988, 555, 2475, 2028, 2923,
                   1323, 1122, 660, 1643, 3179, 1044, 1780, 3636, 2776, 2795,
                   1147, 2059, 1291, 3851),
    },
    "dev_oil_cooler": {
        "seed": 8115,
        "nominal": (3176, 376, 791, 879, 1192, 2792, 1688, 2920, 1132, 1047,
                    663, 3991, 2952, 1431, 2392, 3415, 2024, 2327, 3031, 4072,
                    1832, 40, 2522, 3560),
        "robust": (2952, 791, 376, 2920, 2199, 3031, 2792, 1132, 3176, 3415,
                   1047, 2392, 3991, 1192, 663, 1431, 2327, 2024, 1631, 4072,
                   1688, 2522, 40, 1832),
    },
    "dev_glycol_recovery": {
        "seed": 8116,
        "nominal": (2556, 588, 3616, 1987, 1203, 2324, 1372, 2915, 1244, 3036,
                    3484, 3572, 796, 2051, 2611, 475, 1508, 755, 3852, 3235,
                    2220, 931, 2467, 764),
        "robust": (1244, 2611, 3616, 3235, 2915, 2324, 2051, 1203, 3572, 2220,
                   3843, 3036, 755, 2652, 4019, 2564, 476, 475, 1987, 931,
                   2752, 2467, 188, 1580),
    },
    "heldout_brine_recovery": {
        "seed": 8117,
        "nominal": (4086, 201, 2390, 3865, 3606, 1641, 1929, 2710, 1729, 2806,
                    1590, 854, 1673, 950, 294, 742, 3830, 3550, 1198, 3390,
                    310, 2614, 2377, 2601),
        "robust": (950, 598, 406, 3865, 3606, 2937, 1122, 742, 1590, 294,
                   1729, 2710, 201, 1673, 3462, 3830, 3550, 2377, 310, 2601,
                   1046, 3390, 3050, 2982),
    },
    "dev_high_flow_water": {
        "seed": 8118,
        "nominal": (1963, 1572, 4027, 2619, 1908, 2907, 763, 580, 539, 795,
                    2075, 1691, 1835, 3924, 1371, 3387, 1211, 1251, 3763, 3716,
                    2043, 3460, 3675, 3195),
        "robust": (2907, 1251, 4027, 580, 1211, 2619, 1908, 257, 1572, 219,
                   795, 539, 1691, 2075, 2043, 1835, 3460, 3763, 3716, 3675,
                   763, 1755, 1515, 2532),
    },
}


def _sobol_design_pool(problem, seed):
    unit = qmc.Sobol(d=5, scramble=True, seed=int(seed)).random_base2(12)
    lower = np.asarray((
        problem["tube_inner_diameter_bounds_m"][0],
        problem["tube_length_bounds_m"][0],
        problem["tube_count_bounds"][0],
        problem["baffle_spacing_bounds_m"][0],
        1.0,
    ), dtype=float)
    upper = np.asarray((
        problem["tube_inner_diameter_bounds_m"][1],
        problem["tube_length_bounds_m"][1],
        problem["tube_count_bounds"][1] + 0.999999,
        problem["baffle_spacing_bounds_m"][1],
        4.999999,
    ), dtype=float)
    designs = lower + unit * (upper - lower)
    designs[:, 2] = np.floor(designs[:, 2])
    designs[:, 4] = np.floor(designs[:, 4])
    return designs


def _reference_archive(instance, kind):
    record = REFERENCE_SOBOL[instance["name"]]
    pool = _sobol_design_pool(instance["problem"], record["seed"])
    return pool[np.asarray(record[str(kind)], dtype=int)].copy()


REFERENCE_ARCHIVES = {
    instance["name"]: _reference_archive(instance, "nominal")
    for instance in INSTANCES
}
ROBUST_REFERENCE_ARCHIVES = {
    instance["name"]: _reference_archive(instance, "robust")
    for instance in INSTANCES
}


# Frozen scalar anchors remove reference recomputation from every candidate evaluation.  The
# independent calibration command reconstructs and verifies each value from the seeds above.
CALIBRATED_ANCHORS = {
    "dev_water_process": {
        "baseline_exact_hypervolume": 0.5155380893203289,
        "reference_exact_hypervolume": 0.8244995126576996,
        "baseline_proxy_hypervolume": 0.5613297828149204,
        "reference_proxy_hypervolume": 0.8395404150196933,
        "baseline_shifted_hypervolumes": (0.5089424554158373, 0.5274285147480914, 0.4621276333542970),
        "reference_shifted_hypervolumes": (0.7846261730573458, 0.8193674873916849, 0.6906581700325121),
    },
    "heldout_viscous_oil": {
        "baseline_exact_hypervolume": 0.19244291487448495,
        "reference_exact_hypervolume": 0.35680781548550705,
        "baseline_proxy_hypervolume": 0.19482205964049332,
        "reference_proxy_hypervolume": 0.35812094595737265,
        "baseline_shifted_hypervolumes": (0.1910711918396159, 0.1922473061994921, 0.14489199620831408),
        "reference_shifted_hypervolumes": (0.35343320973019504, 0.3564061212021855, 0.2758176200856486),
    },
    "dev_oil_cooler": {
        "baseline_exact_hypervolume": 0.15710452408747197,
        "reference_exact_hypervolume": 0.29792144080873517,
        "baseline_proxy_hypervolume": 0.15928153495380198,
        "reference_proxy_hypervolume": 0.2984978661661053,
        "baseline_shifted_hypervolumes": (0.1560047020978782, 0.15693803536203385, 0.11760906109480519),
        "reference_shifted_hypervolumes": (0.29439238972540543, 0.2971160230111221, 0.22750974626349182),
    },
    "dev_glycol_recovery": {
        "baseline_exact_hypervolume": 0.4763163767993251,
        "reference_exact_hypervolume": 0.7789733209083308,
        "baseline_proxy_hypervolume": 0.5203986027428213,
        "reference_proxy_hypervolume": 0.7996489628111664,
        "baseline_shifted_hypervolumes": (0.4651006585351168, 0.4857900076360162, 0.48253254043594024),
        "reference_shifted_hypervolumes": (0.7387662894181951, 0.7758253114610241, 0.7541626808363884),
    },
    "heldout_brine_recovery": {
        "baseline_exact_hypervolume": 0.3371605828497717,
        "reference_exact_hypervolume": 0.8416712424230526,
        "baseline_proxy_hypervolume": 0.2903850094653687,
        "reference_proxy_hypervolume": 0.8320021572048260,
        "baseline_shifted_hypervolumes": (0.3290613555448279, 0.3495274468714834, 0.36286976693473305),
        "reference_shifted_hypervolumes": (0.7763333293620885, 0.8212632217260447, 0.7997185855240911),
    },
    "dev_high_flow_water": {
        "baseline_exact_hypervolume": 0.5454820913651016,
        "reference_exact_hypervolume": 0.8153880941391274,
        "baseline_proxy_hypervolume": 0.5513029115012870,
        "reference_proxy_hypervolume": 0.8205154693658888,
        "baseline_shifted_hypervolumes": (0.5399825682965803, 0.5507266039661676, 0.5684517654762477),
        "reference_shifted_hypervolumes": (0.7862955413777916, 0.8136009504768174, 0.8223780192960068),
    },
}


def _evaluate_archive(instance, designs):
    proxy = [_proxy_metrics(instance, row) for row in designs]
    exact = [_exact_metrics(instance, row) for row in designs]
    shifted = [
        [_exact_metrics(instance, row, shift) for row in designs]
        for shift in SHIFT_SPECS
    ]
    return proxy, exact, shifted


def _recompute_anchors(instance):
    baseline_designs = _baseline_archive(instance["problem"])
    reference_designs = REFERENCE_ARCHIVES[instance["name"]]
    robust_designs = ROBUST_REFERENCE_ARCHIVES[instance["name"]]
    baseline_proxy, baseline_exact, baseline_shifted = _evaluate_archive(
        instance, baseline_designs
    )
    reference_proxy, reference_exact, _ = _evaluate_archive(instance, reference_designs)
    _, _, robust_shifted = _evaluate_archive(instance, robust_designs)
    return {
        "baseline_exact_hypervolume": _hypervolume(instance, baseline_exact),
        "reference_exact_hypervolume": _hypervolume(instance, reference_exact),
        "baseline_proxy_hypervolume": _hypervolume(instance, baseline_proxy),
        "reference_proxy_hypervolume": _hypervolume(instance, reference_proxy),
        "baseline_shifted_hypervolumes": tuple(
            _hypervolume(instance, rows, shift)
            for shift, rows in zip(SHIFT_SPECS, baseline_shifted)
        ),
        "reference_shifted_hypervolumes": tuple(
            _hypervolume(instance, rows, shift)
            for shift, rows in zip(SHIFT_SPECS, robust_shifted)
        ),
    }


def _anchors(instance):
    return copy.deepcopy(CALIBRATED_ANCHORS[instance["name"]])


def _normalized(value, baseline, reference):
    """Zero at the baseline, one at the reference witness, unbounded above it.

    The upper clip made the witness the best achievable score, so a better result read as exactly
    as good as the witness and the task could report nothing about a searcher that had beaten it.
    Every recorded run scored at or below one, so their scores are unchanged. The floor stays,
    because below the baseline is a worse result rather than a negative achievement.
    """
    denominator = float(reference) - float(baseline)
    if denominator <= 1e-9:
        raise RuntimeError("reference hypervolume does not exceed the baseline")
    return float(max((float(value) - float(baseline)) / denominator, 0.0))


def _score_instance(design_exchanger, instance):
    try:
        returned = design_exchanger(copy.deepcopy(instance["problem"]))
        designs = _validate_archive(returned, instance["problem"])
        proxy, exact, shifted = _evaluate_archive(instance, designs)
        if not any(row["feasible"] for row in exact):
            raise ValueError("archive contains no exact-feasible nominal design")
        diagnostics = _archive_diagnostics(instance, designs, proxy, exact, shifted)
        anchors = _anchors(instance)
        score = _normalized(
            diagnostics["raw_exact_hypervolume"],
            anchors["baseline_exact_hypervolume"],
            anchors["reference_exact_hypervolume"],
        )
        proxy_score = _normalized(
            diagnostics["raw_proxy_hypervolume"],
            anchors["baseline_proxy_hypervolume"],
            anchors["reference_proxy_hypervolume"],
        )
        shifted_scores = [
            _normalized(value, baseline, reference)
            for value, baseline, reference in zip(
                diagnostics["raw_shifted_hypervolumes"],
                anchors["baseline_shifted_hypervolumes"],
                anchors["reference_shifted_hypervolumes"],
            )
        ]
        return dict({
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": score,
            "proxy_score": proxy_score,
            "robustness_score": min(shifted_scores),
            "shifted_scores": shifted_scores,
            "anchors": anchors,
        }, **diagnostics)
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "proxy_score": 0.0,
            "robustness_score": 0.0,
            "archive_size": 0,
            "proxy_feasibility_rate": 0.0,
            "exact_feasibility_rate": 0.0,
            "false_promotion_rate": 0.0,
            "proxy_exact_rank_correlation": 0.0,
            "raw_proxy_hypervolume": 0.0,
            "raw_exact_hypervolume": 0.0,
            "raw_shifted_hypervolumes": [0.0 for _ in SHIFT_SPECS],
        }


def evaluate(design_exchanger):
    records = [_score_instance(design_exchanger, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_score = float(np.mean([row["score"] for row in development]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    return {
        # Only these development-derived fields enter the search-visible allowlist.
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": float(np.mean([
            row["exact_feasibility_rate"] for row in development
        ])),
        # All following fields are evaluator-only under default metric sealing.
        "development_exact_score": development_score,
        "heldout_exact_score": heldout_score,
        "robustness_score": float(np.mean([
            row["robustness_score"] for row in development
        ])),
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "development_proxy_score": float(np.mean([
            row["proxy_score"] for row in development
        ])),
        "heldout_proxy_score": float(np.mean([
            row["proxy_score"] for row in heldout
        ])),
        "development_proxy_exact_rank_correlation": float(np.mean([
            row["proxy_exact_rank_correlation"] for row in development
        ])),
        "heldout_proxy_exact_rank_correlation": float(np.mean([
            row["proxy_exact_rank_correlation"] for row in heldout
        ])),
        "development_false_promotion_rate": float(np.mean([
            row["false_promotion_rate"] for row in development
        ])),
        "heldout_false_promotion_rate": float(np.mean([
            row["false_promotion_rate"] for row in heldout
        ])),
        "heldout_feasibility_rate": float(np.mean([
            row["exact_feasibility_rate"] for row in heldout
        ])),
        "heldout_structural_validity_rate": heldout_valid / len(heldout),
        "per_instance": records,
    }
