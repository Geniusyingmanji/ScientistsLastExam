"""Truth-blind reference for LookElsewhereAnomaly.

It never reads the hidden world kind. Against the public flat background it computes a
local z, a sideband reduced chi-square that excludes bins around the leading excess, and
a Bonferroni trials factor over n_mass_windows. A global 5σ with clean sidebands is a
discovery; a local 5σ that dies after trials, a blank, or a sideband that rejects the
prior is a refusal. Toys are unused: the analytic correction is enough on these worlds
and leftover budget is headroom, not an exploit.
"""
from __future__ import annotations

import math


def _local_z(counts, bkg):
    root = math.sqrt(bkg)
    return [(float(c) - bkg) / root for c in counts]


def _p_one_sided(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _sideband_redchi(counts, bkg, peak_idx, exclude):
    n = len(counts)
    lo = max(0, peak_idx - exclude)
    hi = min(n, peak_idx + exclude + 1)
    resid = []
    for index, count in enumerate(counts):
        if lo <= index < hi:
            continue
        resid.append((float(count) - bkg) ** 2 / bkg)
    if not resid:
        return 0.0
    return sum(resid) / len(resid)


def interpret_spectrum(problem, toys):
    del toys
    counts = list(problem["counts"])
    mass = list(problem["mass_gev"])
    bkg = float(problem["expected_background"])
    n_windows = int(problem["n_mass_windows"])
    p_thresh = float(problem["five_sigma_global_p"])
    z = _local_z(counts, bkg)
    peak_idx = max(range(len(z)), key=lambda i: z[i])
    redchi = _sideband_redchi(counts, bkg, peak_idx, exclude=2)
    if redchi > 2.5:
        return {"abstain": True, "confidence": 0.85}
    p_global = min(1.0, n_windows * _p_one_sided(z[peak_idx]))
    if p_global < p_thresh:
        return {
            "abstain": False,
            "discovery": True,
            "mass_gev": float(mass[peak_idx]),
            "confidence": 0.9,
        }
    return {"abstain": True, "confidence": 0.75}
