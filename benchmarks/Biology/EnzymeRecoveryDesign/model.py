"""Public effective enzyme-subpopulation model; no private world generation.

Each conformer can reversibly bind inhibitor; damage independently removes
active enzyme during exposure. Pools denote kinetic populations, not uniquely
identified microscopic binding sites. Fractions sum to at most one.
"""
from __future__ import annotations

import numpy as np

RESOLUTION = 0.01
RESOLUTION_TIMES = [0.0, 0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 30.0, 40.0]


def activity(model, dose, loading, washout):
    dose, loading, washout = np.broadcast_arrays(dose, loading, washout)
    unavailable = np.zeros_like(dose, dtype=float)
    for pool in model["pools"]:
        association = pool["kon"] * dose
        exchange = association + pool["koff"]
        unavailable += (pool["fraction"] * association / exchange *
                        (-np.expm1(-exchange * loading)) * np.exp(-pool["koff"] * washout))
    return np.exp(-model["k_loss"] * dose * loading) * (1.0 - unavailable)


def observable(model, nuisance, arguments):
    dose = arguments["dose"]
    loading = arguments["loading"]
    washout = arguments["washout"]
    control = arguments["control"]
    if control == "blank":
        latent = np.zeros_like(np.asarray(dose), dtype=float)
    elif control == "standard":
        latent = np.ones_like(np.asarray(dose), dtype=float)
    else:
        latent = activity(model, dose, loading, washout) + arguments["rescue"]
    if arguments["readout"] == "orthogonal":
        return latent
    carryover = (nuisance["carryover"] * np.asarray(dose) / (1 + np.asarray(dose)) *
                 (-np.expm1(-np.asarray(loading) / nuisance["tau"])) *
                 np.exp(-np.asarray(washout) / nuisance["tau"]))
    return nuisance["gain"] * latent + nuisance["offset"] + carryover


def equivalence_grid():
    """Declared resolution grid; external confirmation is not this fixed grid."""
    dose, loading, washout = np.meshgrid([0.2, 1.0, 4.0], [0.3, 2.0, 8.0],
                                        RESOLUTION_TIMES, indexing="ij")
    return dose.ravel(), loading.ravel(), washout.ravel()


def canonical_pools(pools):
    """Merge exactly identical kinetic populations and remove zero fractions."""
    merged = {}
    for pool in pools:
        if pool["fraction"] <= 1e-12:
            continue
        key = (pool["kon"], pool["koff"])
        merged[key] = merged.get(key, 0.0) + pool["fraction"]
    return [{"kon": key[0], "koff": key[1], "fraction": fraction} for key, fraction in sorted(merged.items())]


def order_two_certificate(model, tolerance=RESOLUTION):
    """A sufficient lower bound ruling out EVERY constant-plus-one-exponential.

    For four equally spaced activities let d0,d1,d2 be the increments.
    A one-exponential curve has d0*d2-d1*d1=0, regardless of its offset
    (including irreversible loss) and amplitude. If each activity can change by
    epsilon then each increment changes by at most 2*epsilon; the determinant
    changes by at most 2*epsilon*(|d0|+|d2|+2|d1|)+8*epsilon**2.
    This operates on calibrated latent activity, never uncorrected optics.
    Nonpositive margin is INCONCLUSIVE, not evidence for one population.
    """
    margin = -float("inf")
    for dose in (0.2, 1.0, 4.0):
        for loading in (0.3, 2.0, 8.0):
            for step in (0.25, 1.0, 4.0, 10.0):
                values = activity(model, dose, loading, np.arange(4) * step)
                d0, d1, d2 = np.diff(values)
                bound = 2 * tolerance * (abs(d0) + abs(d2) + 2 * abs(d1)) + 8 * tolerance ** 2
                margin = max(margin, float(d0 * d2 - d1 ** 2 - bound))
    return margin
