"""Operator-only independent ODE and analytic references; no kernel imports."""

import cmath
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm


def free_induction(parameters, spec):
    if spec["pulses"]:
        raise ValueError("FID reference requires no pulses")
    u0 = complex(*spec["initial_magnetization"][:2])
    rows = []
    for ms in spec["times_ms"]:
        t = ms / 1000
        u = sum(w*cmath.exp(complex(-parameters.r2_per_s, 2*math.pi*(f+spec["detuning_hz"]))*t)
                for f,w in zip(parameters.offsets_hz,parameters.weights))*u0
        rows.append([u.real,u.imag,spec["initial_magnetization"][2]])
    return np.asarray(rows)


def single_echo(parameters, spec):
    events = spec["pulses"]
    if len(events) != 1 or events[0]["angle_rad"] != math.pi or events[0]["phase_rad"] != 0:
        raise ValueError("echo reference requires one exact +pi pulse about +x")
    tau = events[0]["time_ms"] / 1000
    u0 = complex(*spec["initial_magnetization"][:2])
    z0 = spec["initial_magnetization"][2]
    rows = []
    for ms in spec["times_ms"]:
        t = ms / 1000
        after = ms >= events[0]["time_ms"]
        signed_time = t-2*tau if after else t
        u = (u0.conjugate() if after else u0)*math.exp(-parameters.r2_per_s*t)*sum(
            w*cmath.exp(2j*math.pi*(f+spec["detuning_hz"])*signed_time)
            for f,w in zip(parameters.offsets_hz,parameters.weights))
        rows.append([u.real,u.imag,-z0 if after else z0])
    return np.asarray(rows)


def ode_trajectory(parameters, spec):
    """Cartesian Bloch ODE, with pulse rotations from a matrix exponential.

    Integrates each pulse segment once with dense evaluation. This implementation
    does not call the production free propagator, pulse rotation or validator.
    It expects trusted canonical specs, as other operator references do.
    """
    frequencies = np.asarray(parameters.offsets_hz) + spec["detuning_hz"]
    omega = 2*math.pi*frequencies
    weights = np.asarray(parameters.weights)
    state = np.tile(spec["initial_magnetization"], (len(weights),1)).astype(float)
    rate = parameters.r2_per_s
    times = np.asarray(spec["times_ms"],float)/1000
    values = np.empty((len(times),3))
    current, evaluations = 0.0, 0

    def equation(t, flat):
        m = flat.reshape(-1,3)
        return np.column_stack((-rate*m[:,0]-omega*m[:,1], omega*m[:,0]-rate*m[:,1], np.zeros(len(m)))).ravel()

    # Pulses are handled at exact boundaries, before rows at that timestamp.
    for cursor in range(len(spec["pulses"])+1):
        event = spec["pulses"][cursor] if cursor < len(spec["pulses"]) else None
        end = event["time_ms"]/1000 if event else float(times[-1])
        sample = (times >= current) & ((times < end) if event else (times <= end))
        if end > current:
            solution = solve_ivp(equation,(current,end),state.ravel(),method="DOP853",rtol=2e-12,atol=2e-14,dense_output=True,max_step=.002)
            if not solution.success:
                raise RuntimeError("independent Bloch integration failed")
            evaluations += solution.nfev
            if sample.any():
                raw = solution.sol(times[sample]).T.reshape(-1,len(weights),3)
                values[sample] = np.einsum('j,tjk->tk',weights,raw)
            state = solution.y[:,-1].reshape(-1,3)
        elif sample.any():
            values[sample] = weights @ state
        current = end
        if event:
            nx, ny = math.cos(event["phase_rad"]),math.sin(event["phase_rad"])
            cross = np.asarray([[0.,0.,ny],[0.,0.,-nx],[-ny,nx,0.]])
            state = state @ expm(event["angle_rad"]*cross).T
    if not np.isfinite(values).all():
        raise RuntimeError("independent Bloch reference became nonfinite")
    return values, {"ode_rhs_evaluations": evaluations}
