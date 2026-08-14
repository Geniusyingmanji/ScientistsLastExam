"""A truth-blind reference retrieval for RadiativeTransferFit.

The task card says the reference does "exact supported parameters and correct abstention on null
or model-misspecified atmospheres". That was prose. Nothing ran it, so the claim that a candidate
declining every world could have done better was never checked - and every recorded proposal does
decline every world, scoring exactly the all-abstain baseline.

This implements the strategy the card describes, using only what a candidate gets: the public
forward model and the observation callback. It never reads the hidden world.

    observe    two calls, eighteen units: twelve channels looking straight up and six of them
               again at a slanted view. Angle diversity is what separates a change in the
               temperature profile from a change in the optical-depth scale, because slanting
               lengthens the path without changing the emitting temperatures.
    fit        least squares over the five public parameters, bounded to the declared ranges.
    decide     whether to claim, from the fit residual against the declared noise. An atmosphere
               outside the public family cannot be fitted down to the noise floor, so a reduced
               chi-square well above one is the signal to abstain. This is the whole point of the
               task: refusing the out-of-family worlds rather than forcing a clear-sky
               explanation onto them.
    support    a knot counts as active only above the declared 0.5 K threshold, and the optical
               depth only above 0.02, because the contract requires inactive entries to be
               exactly zero and one.

The reference is deliberately not tuned to be unbeatable. A reference that scores 1.0 leaves the
task no headroom, and one that never abstains would fail the false-discovery axis it exists to
demonstrate.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

PLANCK_H = 6.62607015e-34
LIGHT_C = 2.99792458e8
BOLTZMANN_K = 1.380649e-23

# Reduced chi-square above which the in-family fit is judged to have failed. One is a perfect
# fit; the out-of-family worlds here perturb the optical depth by enough that their residual sits
# far above the noise, so the threshold does not need to be delicate. It is set by what a clear
# fit looks like, not by trying values against the hidden worlds.
ABSTAIN_CHI_SQUARE = 4.0

KNOT_ACTIVE_K = 0.5
DEPTH_ACTIVE = 0.02


def _planck(temperature_K, wavenumber_cm):
    sigma_m = 100.0 * float(wavenumber_cm)
    exponent = PLANCK_H * LIGHT_C * sigma_m / (BOLTZMANN_K * float(temperature_K))
    return 2.0 * PLANCK_H * LIGHT_C ** 2 * sigma_m ** 3 / math.expm1(exponent) * 100.0


def _forward(model, parameters, channels, view_cosine):
    """The public clear-sky model, re-implemented from the published recursion."""
    values = np.asarray(parameters, dtype=float)
    profile = (np.asarray(model["reference_temperature_K"], dtype=float)
               + np.asarray(model["temperature_basis"], dtype=float) @ values[:4])
    base = np.asarray(model["base_layer_optical_depths"], dtype=float)
    wavenumbers = np.asarray(model["channel_wavenumbers_cm"], dtype=float)
    out = np.empty(len(channels), dtype=float)
    for index, channel in enumerate(np.asarray(channels, dtype=int)):
        optical_depth = values[4] * base[channel]
        radiance = _planck(profile[0], wavenumbers[channel])
        for layer in range(len(profile)):
            transmittance = math.exp(-optical_depth[layer] / float(view_cosine))
            emission = _planck(profile[layer], wavenumbers[channel])
            radiance = radiance * transmittance + emission * (1.0 - transmittance)
        out[index] = radiance
    return out


def discover_atmosphere(public_model, observe, budget_units):
    wavenumbers = np.asarray(public_model["channel_wavenumbers_cm"], dtype=float)
    n_channels = len(wavenumbers)
    knot_low, knot_high = public_model["temperature_anomaly_bounds_K"]
    depth_low, depth_high = public_model["optical_depth_scale_bounds"]

    # Twelve channels spread across the band, then six of them slanted. Spending the whole budget
    # on one angle would leave the optical-depth scale poorly separated from the profile.
    wide = np.unique(np.linspace(0, n_channels - 1, 12).astype(int))
    slant = wide[:: max(1, len(wide) // 6)][:6]

    observations = []
    first = observe(wide.tolist(), 1.0)
    observations.append((np.asarray(first["channel_indices"], dtype=int),
                         float(first["view_cosine"]),
                         np.asarray(first["radiances"], dtype=float),
                         float(first["radiance_noise_std"])))
    second = observe(slant.tolist(), 0.5)
    observations.append((np.asarray(second["channel_indices"], dtype=int),
                         float(second["view_cosine"]),
                         np.asarray(second["radiances"], dtype=float),
                         float(second["radiance_noise_std"])))

    def residual(values):
        parts = []
        for channels, view_cosine, radiances, noise in observations:
            model = _forward(public_model, values, channels, view_cosine)
            parts.append((model - radiances) / max(noise, 1e-12))
        return np.concatenate(parts)

    start = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
    fit = least_squares(
        residual, start,
        bounds=([-knot_high] * 4 + [depth_low], [knot_high] * 4 + [depth_high]),
        max_nfev=400,
    )
    values = np.asarray(fit.x, dtype=float)
    degrees = max(1, len(fit.fun) - len(values))
    reduced_chi_square = float(np.sum(fit.fun ** 2) / degrees)

    if reduced_chi_square > ABSTAIN_CHI_SQUARE:
        # Out of family: the canonical empty mechanism the contract requires for an abstention.
        return {
            "temperature_anomaly_knots_K": np.zeros(4),
            "optical_depth_scale": 1.0,
            "support": np.zeros(5),
            "confidence": float(np.clip(1.0 / reduced_chi_square, 0.0, 1.0)),
            "abstain": True,
        }

    support = np.zeros(5)
    knots = np.zeros(4)
    for index in range(4):
        if abs(values[index]) >= max(KNOT_ACTIVE_K, knot_low):
            support[index] = 1.0
            knots[index] = float(np.clip(values[index], -knot_high, knot_high))
    depth = 1.0
    if abs(values[4] - 1.0) >= DEPTH_ACTIVE:
        support[4] = 1.0
        depth = float(np.clip(values[4], depth_low, depth_high))

    return {
        "temperature_anomaly_knots_K": knots,
        "optical_depth_scale": depth,
        "support": support,
        "confidence": float(np.clip(1.0 - reduced_chi_square / ABSTAIN_CHI_SQUARE, 0.0, 1.0)),
        "abstain": False,
    }
