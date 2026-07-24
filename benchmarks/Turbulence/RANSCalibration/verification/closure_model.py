"""Public equations for the RANSCalibration-v2 channel-flow closure family."""

from __future__ import annotations

import numpy as np


PARAMETER_NAMES = ("kappa", "A_plus", "outer_linear", "outer_quadratic")
PARAMETER_BOUNDS = np.asarray((
    (0.20, 0.70),
    (5.0, 80.0),
    (-3.0, 3.0),
    (-3.0, 3.0),
), dtype=float)
STANDARD_PARAMETERS = np.asarray((0.41, 26.0, 0.0, 0.0), dtype=float)


def validate_parameters(parameters):
    if isinstance(parameters, dict):
        if set(parameters) != set(PARAMETER_NAMES):
            raise ValueError("parameter keys must match the public closure contract")
        raw = np.asarray([parameters[name] for name in PARAMETER_NAMES])
    else:
        raw = np.asarray(parameters)
    if raw.shape != (4,) or raw.dtype.kind not in "fiu":
        raise ValueError("closure parameters must be a numeric length-four vector")
    values = raw.astype(float, copy=False)
    if not np.all(np.isfinite(values)):
        raise ValueError("closure parameters must be four finite numbers")
    if np.any(values < PARAMETER_BOUNDS[:, 0]) or np.any(
        values > PARAMETER_BOUNDS[:, 1]
    ):
        raise ValueError("closure parameters outside public bounds")
    return values


def closure_profiles(parameters, re_tau, y_plus):
    """Return U+, dU+/dy+ and -u'v'+ from one algebraic closure.

    The Cess-style outer shape supplies a positive eddy viscosity.  A van-Driest
    damping factor enforces the near-wall limit.  Mean momentum is then solved
    independently from ``(1 + nu_t+) dU+/dy+ = 1-y/h``.
    """
    values = validate_parameters(parameters)
    kappa, a_plus, outer_linear, outer_quadratic = values
    re_tau = float(re_tau)
    y_plus = np.asarray(y_plus, dtype=float).reshape(-1)
    if (
        not np.isfinite(re_tau) or re_tau <= 50.0
        or y_plus.size < 2 or not np.all(np.isfinite(y_plus))
        or np.any(y_plus < 0.0) or np.any(np.diff(y_plus) <= 0.0)
        or y_plus[-1] >= re_tau
    ):
        raise ValueError("invalid channel grid")
    eta = y_plus / re_tau
    outer_shape = (
        (2.0 * eta - eta * eta)
        * (3.0 - 4.0 * eta + 2.0 * eta * eta)
        * np.exp(np.clip(
            outer_linear * eta + outer_quadratic * eta * eta,
            -8.0, 8.0,
        ))
    )
    damping = -np.expm1(-y_plus / a_plus)
    radicand = 1.0 + (
        (kappa * re_tau / 3.0) * outer_shape * damping
    ) ** 2
    eddy_viscosity_plus = 0.5 * (np.sqrt(radicand) - 1.0)
    total_shear_plus = 1.0 - eta
    mean_shear_plus = total_shear_plus / (1.0 + eddy_viscosity_plus)
    mean_u_plus = np.empty_like(y_plus)
    # The first retained DNS location is below y+=0.7.  U+=y+ is the exact
    # viscous-wall boundary condition used to close the tiny omitted interval.
    mean_u_plus[0] = y_plus[0]
    mean_u_plus[1:] = mean_u_plus[0] + np.cumsum(
        0.5
        * (mean_shear_plus[1:] + mean_shear_plus[:-1])
        * np.diff(y_plus)
    )
    reynolds_shear_plus = eddy_viscosity_plus * mean_shear_plus
    if not all(np.all(np.isfinite(value)) for value in (
        mean_u_plus, mean_shear_plus, reynolds_shear_plus,
    )):
        raise ValueError("closure produced non-finite profiles")
    return mean_u_plus, mean_shear_plus, reynolds_shear_plus
