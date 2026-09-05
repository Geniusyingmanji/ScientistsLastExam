"""Deterministic extended-period water-storage and pump-scheduling oracle."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
HOURS = 24
PROFILE = np.array([.72,.68,.65,.64,.68,.82,1.08,1.28,1.32,1.18,1.05,.98,
                    .96,.98,1.02,1.10,1.22,1.30,1.18,1.02,.92,.86,.80,.76])
TARIFF = np.array([.09]*6 + [.18]*5 + [.13]*5 + [.31]*5 + [.13]*3)

INSTANCE_SPECS = (
    ("dev_hilly", "development", 118.0, 165.0, 820.0, 310.0, 1510.0, 0),
    ("dev_dense", "development", 132.0, 184.0, 930.0, 360.0, 1700.0, 3),
    ("dev_small", "development", 91.0, 138.0, 650.0, 245.0, 1210.0, 7),
    ("dev_industrial", "development", 146.0, 202.0, 1040.0, 400.0, 1880.0, 11),
    ("heldout_coastal", "heldout", 126.0, 176.0, 875.0, 330.0, 1600.0, 19),
    ("heldout_growth", "heldout", 154.0, 214.0, 1080.0, 420.0, 1950.0, 23),
)


def _problem(spec):
    name, split, average, capacity, initial, minimum, maximum, phase = spec
    forecast = average * np.roll(PROFILE, phase % 4)
    prices = np.roll(TARIFF, phase % 3)
    return {
        "horizon_hours": HOURS, "time_step_hours": 1.0,
        "demand_forecast_m3_h": forecast.tolist(), "electricity_usd_kwh": prices.tolist(),
        "pump_capacity_m3_h": capacity, "pump_static_head_m": 34.0 + 0.02*average,
        "pump_speed_head_coefficient_m": 18.0, "wire_to_water_efficiency": 0.78,
        "tank_initial_volume_m3": initial, "tank_minimum_volume_m3": minimum,
        "tank_maximum_volume_m3": maximum, "terminal_minimum_volume_m3": initial,
        "maximum_speed_change": 0.55,
        "contract": "return pump_speed, one finite value in [0,1] per hour",
    }


def _actual_demand(problem, seed, scale=1.0):
    forecast = np.asarray(problem["demand_forecast_m3_h"], dtype=float)
    hour = np.arange(HOURS)
    ripple = 1.0 + 0.025*np.sin(.73*hour + seed) + 0.018*np.cos(1.31*hour + .4*seed)
    return forecast * ripple * scale


def _validate(problem, value):
    if isinstance(value, dict): value = value.get("pump_speed")
    speeds = np.asarray(value, dtype=float)
    if speeds.shape != (HOURS,) or not np.all(np.isfinite(speeds)):
        raise ValueError("pump_speed must contain 24 finite values")
    if np.any(speeds < 0.0) or np.any(speeds > 1.0):
        raise ValueError("pump speeds lie outside [0,1]")
    if np.max(np.abs(np.diff(speeds))) > float(problem["maximum_speed_change"]) + 1e-12:
        raise ValueError("speed ramp limit exceeded")
    return speeds


def _simulate(problem, speeds, demand, outage=None):
    outage = set(outage or ())
    volume = float(problem["tank_initial_volume_m3"])
    minimum, maximum = float(problem["tank_minimum_volume_m3"]), float(problem["tank_maximum_volume_m3"])
    cap = float(problem["pump_capacity_m3_h"]); eta = float(problem["wire_to_water_efficiency"])
    costs, volumes, pressure_margins = [], [volume], []
    feasible = True
    for h in range(HOURS):
        speed = 0.0 if h in outage else float(speeds[h])
        flow = cap * speed
        volume += flow - float(demand[h])
        volumes.append(volume)
        feasible &= minimum - 1e-9 <= volume <= maximum + 1e-9
        tank_head = 43.0 + 10.0*(volume-minimum)/max(maximum-minimum, 1e-9)
        remote_pressure = tank_head - 20.0 - 0.00023*float(demand[h])**2
        pressure_margins.append(remote_pressure - 20.0)
        feasible &= remote_pressure >= 20.0
        head = float(problem["pump_static_head_m"]) + float(problem["pump_speed_head_coefficient_m"])*speed*speed
        power_kw = 9.81 * flow * head / (3600.0 * eta)
        costs.append(power_kw * float(problem["electricity_usd_kwh"][h]))
    feasible &= volume >= float(problem["terminal_minimum_volume_m3"]) - 1e-9
    switching = 0.035 * sum(abs(float(x)) for x in np.diff(speeds))
    return {"feasible": bool(feasible), "cost": float(sum(costs)+switching),
            "minimum_volume": float(min(volumes)), "maximum_volume": float(max(volumes)),
            "terminal_volume": float(volume), "minimum_pressure_margin_m": float(min(pressure_margins))}


def _baseline(problem):
    demand = np.asarray(problem["demand_forecast_m3_h"], dtype=float)
    average = max(float(np.mean(demand))/float(problem["pump_capacity_m3_h"])*1.14, 0.1)
    return np.full(HOURS, min(0.94, average))


def _reference(problem):
    forecast = np.asarray(problem["demand_forecast_m3_h"], dtype=float)
    speeds = _baseline(problem)
    nominal = lambda x: _simulate(problem, x, forecast)
    def acceptable(x):
        try:
            _validate(problem, x)
        except ValueError:
            return False
        return (_simulate(problem, x, 1.045*forecast)["feasible"]
                and _simulate(problem, x, .955*forecast)["feasible"])

    # Move equal pumping capacity from costly hours to cheap hours. Equal total volume preserves
    # terminal storage; every accepted move is replayed against upper/lower public-demand bands,
    # pressure and ramp constraints. This is slower than an LP but has no hidden solver dependency.
    best_cost = nominal(speeds)["cost"]
    cheap = np.argsort(problem["electricity_usd_kwh"])
    costly = cheap[::-1]
    for delta in (.04, .02, .01, .005):
        changed = True
        while changed:
            changed = False
            for expensive in costly:
                if speeds[expensive] < delta:
                    continue
                trial = speeds.copy(); trial[expensive] -= delta
                if acceptable(trial) and nominal(trial)["cost"] < best_cost-1e-10:
                    speeds, best_cost, changed = trial, nominal(trial)["cost"], True
    for delta in (.08, .04, .02, .01):
        changed = True
        while changed:
            changed = False
            for expensive in costly:
                for inexpensive in cheap:
                    if problem["electricity_usd_kwh"][inexpensive] >= problem["electricity_usd_kwh"][expensive]:
                        continue
                    amount = min(delta, speeds[expensive], 1.0-speeds[inexpensive])
                    if amount <= 1e-12:
                        continue
                    trial = speeds.copy(); trial[expensive] -= amount; trial[inexpensive] += amount
                    if not acceptable(trial):
                        continue
                    cost = nominal(trial)["cost"]
                    if cost < best_cost-1e-10:
                        speeds, best_cost, changed = trial, cost, True
    return speeds


def _score_instance(candidate, spec):
    problem = _problem(spec); seed = int(spec[-1])
    demand = _actual_demand(problem, seed)
    baseline, reference = _baseline(problem), _reference(problem)
    b = _simulate(problem, baseline, demand); r = _simulate(problem, reference, demand)
    # A failed reference must never create an attractive denominator. Fall back to the better
    # valid public schedule while retaining the baseline as zero.
    ref_cost = r["cost"] if r["feasible"] else 0.92*b["cost"]
    try:
        speeds = _validate(problem, candidate(copy.deepcopy(problem)))
        nominal = _simulate(problem, speeds, demand)
        if not nominal["feasible"]: raise ValueError("nominal hydraulic/storage constraints violated")
        score = (b["cost"]-nominal["cost"])/max(b["cost"]-ref_cost, 1e-9)
        high = _simulate(problem, speeds, _actual_demand(problem, seed, 1.12))
        outage_start = 16 + seed % 3
        outage = _simulate(problem, speeds, _actual_demand(problem, seed, 1.05), range(outage_start, min(outage_start+4, HOURS)))
        resilience = 0.5*float(high["feasible"]) + 0.5*float(outage["feasible"])
        return {"name": spec[0], "split": spec[1], "valid": True, "score": float(score),
                "energy_cost_usd": nominal["cost"], "minimum_pressure_margin_m": nominal["minimum_pressure_margin_m"],
                "resilience_score": resilience, "high_demand_feasible": high["feasible"],
                "outage_feasible": outage["feasible"]}
    except Exception as exc:
        return {"name": spec[0], "split": spec[1], "valid": False, "score": 0.0,
                "energy_cost_usd": 0.0, "minimum_pressure_margin_m": -1e6,
                "resilience_score": 0.0, "high_demand_feasible": False, "outage_feasible": False,
                "reason": f"{type(exc).__name__}: {exc}"}


def evaluate(schedule_pumps):
    rows = [_score_instance(schedule_pumps, spec) for spec in INSTANCE_SPECS]
    dev = [r for r in rows if r["split"] == "development"]
    held = [r for r in rows if r["split"] == "heldout"]
    return {"combined_score": float(np.mean([r["score"] for r in dev])),
            "valid": float(all(r["valid"] for r in dev)),
            "feasibility_rate": float(np.mean([r["valid"] for r in dev])),
            "resilience_score": float(np.mean([r["resilience_score"] for r in dev])),
            "heldout_policy_score": float(np.mean([r["score"] for r in held])),
            "heldout_resilience_score": float(np.mean([r["resilience_score"] for r in held])),
            "heldout_feasibility_rate": float(np.mean([r["valid"] for r in held])),
            "per_instance": rows}
