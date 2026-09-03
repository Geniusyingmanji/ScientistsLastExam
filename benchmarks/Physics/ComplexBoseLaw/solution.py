"""Weak but valid baseline for ComplexBoseLaw.

It treats every cavity occupancy as textbook Planck/Bose occupation with (C, α, β) = (1, 1, 1)
and never declines. A Fermi gas and a T-independent blank therefore become Bose papers.
"""
from __future__ import annotations


def interpret_cavity(problem, measure):
    _ = problem["omega_bounds"]
    _ = problem["temperature_bounds"]
    _ = int(problem["measure_budget_calls"])
    _ = problem["family_names"]
    _ = problem["in_family_occupation"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    lo_w, hi_w = problem["omega_bounds"]
    lo_t, hi_t = problem["temperature_bounds"]
    value = float(measure(0.5 * (lo_w + hi_w), 0.5 * (lo_t + hi_t)))
    _ = value
    return {
        "abstain": False,
        "family": "bose",
        "C": 1.0,
        "alpha": 1.0,
        "beta": 1.0,
        "confidence": 0.7,
    }
