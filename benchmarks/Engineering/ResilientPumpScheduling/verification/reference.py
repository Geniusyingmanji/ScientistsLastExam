"""Standalone public-model witness. No oracle imports or hidden instance access.

The public model is reproduced here; independent high-fidelity validation is pending.
"""
import math
import copy
import numpy as np

HOURS=24
_REFERENCE_CACHE={}

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
    """Public-demand-band convex dispatch on a conservative all-on commitment.

    This is a competent feasible fixed-mask method.  The oracle's wider block-mask
    search is the score-one anchor, leaving discrete commitment optimization as
    explicit, reproducible headroom.
    """
    key = repr(problem)
    if key in _REFERENCE_CACHE:
        return _REFERENCE_CACHE[key].copy()
    on = np.ones(HOURS,dtype=bool)
    best = _continuous_schedule(problem,on)
    if best is None:
        raise RuntimeError("no feasible public pumping reference")
    _REFERENCE_CACHE[key] = best.copy()
    return best

def schedule_pumps(problem):
    return {"pump_speed": _reference(problem).tolist()}
