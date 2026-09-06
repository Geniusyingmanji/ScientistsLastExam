"""Deterministic extended-period water-storage and pump-scheduling oracle."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
HOURS = 24
_REFERENCE_CACHE = {}
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
        "minimum_operating_speed": .65, "minimum_run_hours": 2,
        "running_auxiliary_power_kw": 2.5, "startup_cost_usd": .30,
        "contract": "return 24 pump_speed values: zero or [minimum_operating_speed,1]; on-runs last at least minimum_run_hours; ramp applies between consecutive running hours; initial pump is off",
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
    on = speeds > 1e-9
    if np.any(on & (speeds < problem["minimum_operating_speed"] - 1e-9)):
        raise ValueError("running speed below stable operating range")
    edges = np.diff(np.r_[False,on,False].astype(int))
    if np.any(np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1) < problem["minimum_run_hours"]):
        raise ValueError("minimum run duration violated")
    if np.any((np.abs(np.diff(speeds)) > float(problem["maximum_speed_change"]) + 1e-12) & on[1:] & on[:-1]):
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
        if speed > 1e-9:
            power_kw += problem["running_auxiliary_power_kw"]
        costs.append(power_kw * float(problem["electricity_usd_kwh"][h]))
    feasible &= volume >= float(problem["terminal_minimum_volume_m3"]) - 1e-9
    switching = 0.035 * sum(abs(float(x)) for x in np.diff(speeds))
    on = np.asarray(speeds) > 1e-9
    switching += problem["startup_cost_usd"] * np.count_nonzero(on & ~np.r_[False,on[:-1]])
    return {"feasible": bool(feasible), "cost": float(sum(costs)+switching),
            "minimum_volume": float(min(volumes)), "maximum_volume": float(max(volumes)),
            "terminal_volume": float(volume), "minimum_pressure_margin_m": float(min(pressure_margins))}


def _baseline(problem):
    demand = np.asarray(problem["demand_forecast_m3_h"], dtype=float)
    average = max(float(np.mean(demand))/float(problem["pump_capacity_m3_h"])*1.14, 0.1)
    return np.full(HOURS, min(0.94, average))


def _continuous_schedule(problem, on):
    from scipy.optimize import minimize, LinearConstraint, Bounds
    demand = np.asarray(problem["demand_forecast_m3_h"])
    prices = np.asarray(problem["electricity_usd_kwh"])
    capacity = float(problem["pump_capacity_m3_h"])
    minimum = float(problem["tank_minimum_volume_m3"])
    maximum = float(problem["tank_maximum_volume_m3"])
    initial = float(problem["tank_initial_volume_m3"])
    # Pressure >=20 gives a time-varying minimum storage, affine in speeds.
    high = 1.045 * demand; low = .955 * demand
    pressure_min = minimum + (maximum - minimum) * (.00023 * high**2 - 3.0) / 10.0
    lower = np.maximum(minimum, pressure_min) - initial + np.cumsum(high)
    lower[-1] = max(lower[-1], problem["terminal_minimum_volume_m3"] - initial + high.sum())
    upper = maximum - initial + np.cumsum(low)
    cumulative = capacity * np.tril(np.ones((HOURS, HOURS)))
    difference = np.diff(np.eye(HOURS), axis=0)
    ramp = float(problem["maximum_speed_change"])
    # Auxiliary epigraph variables make the switching term differentiable and convex.
    matrices = [np.c_[cumulative, np.zeros((HOURS,HOURS-1))],
                np.c_[difference, np.zeros((HOURS-1,HOURS-1))],
                np.c_[difference, -np.eye(HOURS-1)],
                np.c_[-difference, -np.eye(HOURS-1)]]
    lb = np.r_[lower + 1e-4, np.where(on[1:] & on[:-1], -ramp+1e-6, -1.), np.full(2*(HOURS-1),-np.inf)]
    ub = np.r_[upper - 1e-4, np.where(on[1:] & on[:-1], ramp-1e-6, 1.), np.zeros(2*(HOURS-1))]
    factor = 9.81 * capacity * prices / (3600 * problem["wire_to_water_efficiency"])
    h0 = problem["pump_static_head_m"]; h2 = problem["pump_speed_head_coefficient_m"]
    def objective(z):
        x=z[:HOURS]
        return float(np.sum(factor*(h0*x+h2*x**3)) + .035*np.sum(z[HOURS:])) / 100.0
    def jac(z):
        return np.r_[factor*(h0+3*h2*z[:HOURS]**2), np.full(HOURS-1,.035)] / 100.0
    start = _baseline(problem)
    result = minimize(objective, np.r_[start,np.abs(np.diff(start))], jac=jac,
                      method="SLSQP", bounds=Bounds(np.r_[on * problem["minimum_operating_speed"],np.zeros(HOURS-1)],
                                    np.r_[on.astype(float),np.ones(HOURS-1)]),
                      constraints=[LinearConstraint(np.vstack(matrices),lb,ub)],
                      options={"maxiter":200,"ftol":1e-10})
    speeds = result.x[:HOURS]
    if (not result.success or not _simulate(problem,speeds,high)["feasible"]
            or not _simulate(problem,speeds,low)["feasible"]):
        return None
    return speeds



def _reference(problem):
    """Mixed commitment/local continuous dispatch search using public demand bands.

    Fixed masks have convex dispatch subproblems. Block exchanges change commitment;
    this is a feasible heuristic, not a certificate of global mixed-integer optimality.
    """
    key = repr(problem)
    if key in _REFERENCE_CACHE:
        return _REFERENCE_CACHE[key].copy()
    demand = np.asarray(problem["demand_forecast_m3_h"])
    cache = {}
    def solve(on):
        key = tuple(on)
        if key not in cache:
            edges = np.diff(np.r_[False,on,False].astype(int))
            if np.any(np.flatnonzero(edges == -1)-np.flatnonzero(edges == 1) < problem["minimum_run_hours"]):
                cache[key] = (float('inf'),None)
            else:
                speeds = _continuous_schedule(problem,on)
                cache[key] = (float('inf'),None) if speeds is None else (_simulate(problem,speeds,demand)["cost"],speeds)
        return cache[key]
    on = np.ones(HOURS,dtype=bool)
    cost, best = solve(on)
    if best is None:
        raise RuntimeError("no feasible public pumping reference")
    for _ in range(2):
        next_mask, next_best, next_cost = on, best, cost
        for width in (2,3,4):
            for start in range(HOURS-width+1):
                trial = on.copy(); trial[start:start+width] = ~trial[start:start+width]
                value, speeds = solve(trial)
                if value < next_cost - 1e-8:
                    next_mask, next_best, next_cost = trial, speeds, value
        if next_cost >= cost - 1e-8:
            break
        on,best,cost = next_mask,next_best,next_cost
    _REFERENCE_CACHE[key] = best.copy()
    return best


def _score_instance(candidate, spec):
    problem = _problem(spec); seed = int(spec[-1])
    demand = _actual_demand(problem, seed)
    baseline, reference = _baseline(problem), _reference(problem)
    b = _simulate(problem, baseline, demand); r = _simulate(problem, reference, demand)
    # A failed reference must never create an attractive denominator. Fall back to the better
    # valid public schedule while retaining the baseline as zero.
    if not b["feasible"] or not r["feasible"] or r["cost"] >= b["cost"]:
        raise RuntimeError("invalid pumping normalization anchors")
    ref_cost = r["cost"]
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
    return {"combined_score": max(0.0, float(np.mean([r["score"] for r in dev]))) if all(r["valid"] for r in dev) else 0.0,
            "valid": float(all(r["valid"] for r in dev)),
            "feasibility_rate": float(np.mean([r["valid"] for r in dev])),
            "resilience_score": float(np.mean([r["resilience_score"] for r in dev])),
            "heldout_policy_score": float(np.mean([r["score"] for r in held])),
            "heldout_resilience_score": float(np.mean([r["resilience_score"] for r in held])),
            "heldout_feasibility_rate": float(np.mean([r["valid"] for r in held])),
            "per_instance": rows}
