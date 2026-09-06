"""Frozen solver: fully developed turbulent channel flow under an eddy-viscosity closure.

In wall units the total shear in a fully developed channel is exactly linear,

    (1 + nu_t+) dU+/dy+ = 1 - y+/Re_tau,

so a closure `nu_t+(y+)` determines the mean velocity profile by a single quadrature. That is the
whole solver: no turbulence model beyond the closure being tested, no numerics to argue about, and
the profile is a deterministic functional of the closure. It is also the exact setting in which
data-driven closure discovery is done, and the reason the field's results are contested is visible
here - the profile constrains the closure only where the flow samples it.
"""
from __future__ import annotations

import numpy as np


def wall_normal_grid(re_tau, points=400):
    """Stretched grid from the wall to the centreline, dense where the gradient is."""
    uniform = np.linspace(0.0, 1.0, points)
    return re_tau * (1.0 - np.cos(0.5 * np.pi * uniform))  # clusters near y+ = 0


def velocity_profile(mixing_length, re_tau, points=400):
    """Integrate the mean profile for a mixing-length closure.

    The closure is a mixing length `l+(y+)`, and the eddy viscosity it implies is
    `nu_t+ = l+^2 |dU+/dy+|`, which makes the momentum balance implicit:

        l+^2 (dU+/dy+)^2 + dU+/dy+ - tau+ = 0,    tau+ = 1 - y+/Re_tau.

    Taking the positive root and writing it in the numerically stable form

        dU+/dy+ = 2 tau+ / (1 + sqrt(1 + 4 l+^2 tau+))

    gives the profile by one quadrature. Writing the closure as an explicit `nu_t+(y+)` instead -
    the first thing tried here - does not reproduce the log law at all: the fitted von Karman
    constant came out between 13 and 31 against the accepted 0.41, because the implicit coupling
    between eddy viscosity and mean gradient is exactly what produces `dU+/dy+ ~ 1/(kappa y+)`.
    """
    y = wall_normal_grid(re_tau, points)
    length = np.asarray(mixing_length(y, re_tau), dtype=float)
    if length.shape != y.shape:
        raise ValueError("closure must return one mixing length per grid point")
    if not np.all(np.isfinite(length)):
        raise ValueError("closure returned a non-finite value")
    if np.any(length < 0.0):
        raise ValueError("mixing length must be non-negative")
    stress = np.clip(1.0 - y / re_tau, 0.0, None)
    gradient = 2.0 * stress / (1.0 + np.sqrt(1.0 + 4.0 * length ** 2 * stress))
    velocity = np.concatenate(
        [[0.0], np.cumsum(np.diff(y) * 0.5 * (gradient[1:] + gradient[:-1]))])
    return y, velocity


def van_driest(kappa=0.41, a_plus=26.0):
    """The textbook mixing length: linear in the wall distance with exponential damping."""
    def closure(y, re_tau):
        return kappa * y * (1.0 - np.exp(-y / a_plus))
    return closure
