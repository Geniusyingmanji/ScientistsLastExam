"""Independent operator-only numerical check, never used to generate observations.

The reference uses polar state variables, angular momentum, an integrated drag
work coordinate and Radau. It applies impulses by Cartesian velocity conversion.
It is restricted to non-radial test trajectories that avoid r=0; the production
Cartesian solver also supports passage through the origin.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp


def polar_reference(spec, parameters):
    mu, power, gamma, epsilon = (parameters.mu, parameters.exponent, parameters.drag, parameters.softening)
    x, y = spec["position"]
    vx, vy = spec["velocity"]
    radius = math.hypot(x, y)
    state = np.asarray([radius, math.atan2(y, x), (x*vx + y*vy) / radius, x*vy - y*vx, 0.0])
    current, cursor, evaluations = 0.0, 0, 0
    rows, work = [], []

    def equation(t, z):
        r, theta, radial_speed, momentum, loss = z
        if r <= 1e-7:
            raise ValueError("polar reference requires a trajectory away from the origin")
        centripetal = momentum**2 / r**3
        inward = mu * r / (r*r + epsilon*epsilon)**((power + 1) / 2)
        speed_squared = radial_speed**2 + (momentum / r)**2
        return [radial_speed, momentum / r**2, centripetal - inward - gamma*radial_speed,
                -gamma*momentum, -gamma*speed_squared]

    def advance(end):
        nonlocal state, current, evaluations
        if end > current:
            solution = solve_ivp(equation, (current, end), state, method="Radau", rtol=5e-12, atol=5e-14, max_step=.035)
            if not solution.success:
                raise RuntimeError("independent reference integration failed")
            evaluations += solution.nfev
            state = solution.y[:, -1]
            current = end

    def cartesian():
        r, theta, u, momentum, _ = state
        c, s = math.cos(theta), math.sin(theta)
        return [r*c, r*s, u*c - momentum*s/r, u*s + momentum*c/r]

    for target in spec["times"]:
        while cursor < len(spec["impulses"]) and spec["impulses"][cursor]["time"] <= target:
            event = spec["impulses"][cursor]
            advance(event["time"])
            x, y, vx, vy = cartesian()
            dx, dy = event["delta_v"]
            vx, vy = vx + dx, vy + dy
            state[2], state[3] = (x*vx + y*vy) / state[0], x*vy - y*vx
            cursor += 1
        advance(target)
        rows.append(cartesian())
        work.append(state[4])
    return np.asarray(rows), np.asarray(work), evaluations


def energy(values, parameters):
    """Independently written per-mass energy, fixed additive convention."""
    rows = np.asarray(values)
    rho = np.sqrt(rows[:, 0]**2 + rows[:, 1]**2 + parameters.softening**2)
    if parameters.exponent == 1:
        potential = parameters.mu * np.log(rho)
    else:
        potential = parameters.mu * rho**(1 - parameters.exponent) / (1 - parameters.exponent)
    return (rows[:, 2]**2 + rows[:, 3]**2) / 2 + potential
