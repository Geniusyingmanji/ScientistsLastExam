"""Operator numerical reference: independent FFT RHS and stiff Radau steps.

This knows the actual private parameters and is never a candidate baseline.
It checks time integration of the same finite collocation ODE, not PDE convergence.
"""

import numpy as np
from scipy.integrate import solve_ivp

from .protocol import GRID_SIZE, PROBE_COUNT, initial_values


def radau_reference(parameters, spec):
    wave = 2*np.pi*np.fft.fftfreq(GRID_SIZE, d=spec["length"]/GRID_SIZE)
    multiplier = parameters.r0 + parameters.gain*spec["drive"] - (parameters.q0**2-wave**2)**2
    theta = 2*np.pi*np.arange(GRID_SIZE)/GRID_SIZE
    force = parameters.forcing*np.cos(parameters.forcing_mode*theta+parameters.forcing_phase)
    evaluations = 0

    def rhs(t, state):
        nonlocal evaluations
        evaluations += 1
        if evaluations > 20000:
            raise RuntimeError("independent reference work limit exceeded")
        return np.fft.ifft(multiplier*np.fft.fft(state)).real - parameters.cubic*state**3 + force

    initial = initial_values(spec, GRID_SIZE)
    if spec["times"][-1] == 0:
        return initial[None, ::GRID_SIZE//PROBE_COUNT], {"rhs_evaluations": 0}
    result = solve_ivp(rhs, (0, spec["times"][-1]), initial, method="Radau", rtol=2e-10, atol=2e-12,
                       max_step=.25, t_eval=spec["times"])
    if not result.success or not np.isfinite(result.y).all():
        raise RuntimeError("independent reference failed")
    return result.y.T[:, ::GRID_SIZE//PROBE_COUNT], {"rhs_evaluations": evaluations, "jacobian_evaluations": result.njev}
