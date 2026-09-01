"""A truth-blind reference for EnzymeKineticsLaw.

It uses only what a candidate receives - the public problem and the budgeted assay - and never
reads the hidden world.

    design      three substrate titrations, at zero inhibitor and at two nonzero levels. One
                titration cannot separate competitive, uncompetitive and noncompetitive
                inhibition: all three are hyperbolae at fixed inhibitor. Two more levels make the
                apparent Km and Vmax move in mode-specific directions, which is what identifies
                them.
    select      fit all six laws by least squares and choose by BIC rather than by residual.
                Thresholding a residual would always prefer the law with the most parameters;
                a substrate-inhibition fit has three and will shade a Michaelis-Menten world.
    refuse      two separate tests, because the two no-law worlds fail differently. A null world
                shows no substrate dependence at all - the fitted Vmax is indistinguishable from
                the floor. A misspecified world does depend on substrate, but no law in the family
                reproduces it, so its best BIC still leaves residuals well above the noise the
                problem declares.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

# Residual-to-noise ratio above which the best-fitting law is judged inadequate. Measured on this
# task: in-library worlds fit to about 1.0-1.6 sigma, the two-site worlds to 3.5 and above.
MISSPECIFICATION_RATIO = 2.4

# The velocity range across a titration, in units of the *expected range of pure noise*, above
# which the assay is judged to have seen real substrate dependence.
#
# It has to scale with the number of points, not be a flat multiple of sigma: the range of n
# Gaussian samples grows like sqrt(2 ln n), so 24 points of a dead enzyme span about 4 sigma on
# noise alone. A flat 4-sigma threshold read that as catalysis and let a null world through. The
# weakest real signal on this task spans 22 sigma, so there is room for a wide margin: this sits
# about 3x above the noise range and 3x below the weakest law.
NULL_RESPONSE_SIGMA = 3.0


def _model(law, theta, s, i):
    vmax, km = abs(theta[0]), abs(theta[1]) + 1e-9
    if law == "michaelis_menten":
        return vmax * s / (km + s)
    if law == "hill":
        n = abs(theta[2]) + 1e-6
        return vmax * s ** n / (km ** n + s ** n)
    ki = abs(theta[2]) + 1e-9
    if law == "substrate_inhibition":
        return vmax * s / (km + s + s * s / ki)
    if law == "competitive":
        return vmax * s / (km * (1.0 + i / ki) + s)
    if law == "uncompetitive":
        return vmax * s / (km + s * (1.0 + i / ki))
    if law == "noncompetitive":
        return vmax * s / ((km + s) * (1.0 + i / ki))
    raise ValueError(law)


_START = {
    "michaelis_menten": [1.0, 20.0],
    "hill": [1.0, 20.0, 2.0],
    "substrate_inhibition": [1.0, 20.0, 30.0],
    "competitive": [1.0, 20.0, 30.0],
    "uncompetitive": [1.0, 20.0, 30.0],
    "noncompetitive": [1.0, 20.0, 30.0],
}

_NAMES = {
    "michaelis_menten": ("vmax", "km"),
    "hill": ("vmax", "km", "hill_n"),
    "substrate_inhibition": ("vmax", "km", "ki"),
    "competitive": ("vmax", "km", "ki"),
    "uncompetitive": ("vmax", "km", "ki"),
    "noncompetitive": ("vmax", "km", "ki"),
}


def _fit(law, s, i, v):
    """Least squares from several starts, because these surfaces have flat directions."""
    best = None
    for scale in (0.4, 1.0, 3.0):
        start = [value * scale for value in _START[law]]
        try:
            result = least_squares(
                lambda theta: _model(law, theta, s, i) - v, start,
                method="lm", max_nfev=4000)
        except Exception:  # noqa: BLE001 - a failed start is not a failed fit
            continue
        residual = float(np.sqrt(np.mean(result.fun ** 2)))
        if best is None or residual < best[0]:
            best = (residual, [abs(x) for x in result.x])
    return best


def discover_kinetics(problem, assay):
    budget = int(problem["assay_budget_calls"])
    s_hi = float(problem["substrate_bounds_um"][1])
    i_hi = float(problem["inhibitor_bounds_um"][1])
    sigma = 0.010  # the problem declares 0.008-0.012; the midpoint is enough to size the tests

    # Geometric substrate spacing, because a hyperbola carries its information near Km and a
    # linear grid spends most of its points on the plateau.
    substrate = [0.6, 1.8, 5.0, 14.0, 38.0, 105.0, 290.0, s_hi]
    inhibitors = [0.0, i_hi * 0.35, i_hi * 0.85]

    s_obs, i_obs, v_obs = [], [], []
    for inhibitor in inhibitors:
        for point in substrate:
            if len(v_obs) >= budget:
                break
            try:
                v_obs.append(float(assay(point, inhibitor)))
            except Exception:
                break
            s_obs.append(point)
            i_obs.append(inhibitor)

    if len(v_obs) < 8:
        return {"abstain": True, "confidence": 0.0}

    s = np.asarray(s_obs, dtype=float)
    i = np.asarray(i_obs, dtype=float)
    v = np.asarray(v_obs, dtype=float)

    # Null test first, and on its own terms: a dead enzyme has no substrate dependence, so the
    # spread of velocity across the titration is pure noise.
    #
    # Measured as a full range, not as high-substrate minus low-substrate. A substrate-inhibited
    # enzyme rises and then falls, so its endpoints can nearly coincide: on this task's own worlds
    # the endpoint difference put substrate inhibition at 4.7 sigma against a 4.0 sigma threshold,
    # a 17% margin between a real law and "no catalysis". The range sees the peak and puts the
    # same world at 37 sigma.
    if len(v):
        response = float(np.max(v) - np.min(v))
        expected_noise_range = sigma * math.sqrt(2.0 * math.log(max(len(v), 2)))
        if response < NULL_RESPONSE_SIGMA * expected_noise_range:
            return {"abstain": True, "confidence": 0.05}

    n = len(v)
    scored = []
    for law in problem["candidate_laws"]:
        fit = _fit(law, s, i, v)
        if fit is None:
            continue
        residual, theta = fit
        k = len(_START[law])
        # BIC over the six laws rather than the smallest residual: the extra parameter in a
        # three-parameter law buys a lower residual on every world, including the ones that do
        # not need it.
        bic = n * math.log(max(residual, 1e-12) ** 2) + k * math.log(n)
        scored.append((bic, residual, law, theta))
    if not scored:
        return {"abstain": True, "confidence": 0.0}

    scored.sort()
    bic, residual, law, theta = scored[0]

    # Model-inadequacy test: even the best of six leaves structure behind on a two-site enzyme.
    if residual > MISSPECIFICATION_RATIO * sigma:
        return {"abstain": True, "confidence": 0.1}

    parameters = dict(zip(_NAMES[law], [float(x) for x in theta]))
    confidence = float(np.clip(1.0 - residual / (MISSPECIFICATION_RATIO * sigma), 0.0, 1.0))
    return {
        "law": law,
        "parameters": parameters,
        "confidence": confidence,
        "abstain": False,
    }
