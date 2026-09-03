"""Weak but valid baseline for LookElsewhereAnomaly.

It does what a local excess invites: take the highest (count - prior) / sqrt(prior),
publish that bin as a discovery, never buy toys, and never decline. A local 5σ fluke,
a sculpted sideband, and a blank that grazed upward all become papers.
"""
from __future__ import annotations


def interpret_spectrum(problem, toys):
    del toys
    mass = list(problem["mass_gev"])
    counts = list(problem["counts"])
    bkg = float(problem["expected_background"])
    _ = int(problem["n_mass_windows"])
    _ = int(problem["toys_budget_units"])
    _ = int(problem["toys_batch_size"])
    _ = float(problem["five_sigma_global_p"])
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    _ = problem["look_elsewhere_note"]
    root = bkg ** 0.5
    z = [(float(count) - bkg) / root for count in counts]
    idx = max(range(len(z)), key=lambda i: z[i])
    return {
        "abstain": False,
        "discovery": True,
        "mass_gev": float(mass[idx]),
        "confidence": 0.9,
    }
