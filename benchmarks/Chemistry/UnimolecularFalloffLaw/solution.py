"""Weak baseline: treat every assay as a pressure-independent Arrhenius law."""
from __future__ import annotations


def identify_falloff(problem, measure):
    lo_t, hi_t = problem["temperature_bounds_K"]
    lo_p, hi_p = problem["pressure_bounds_bar"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["rate_law"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    lnk = float(measure(0.5 * (lo_t + hi_t), 0.5 * (lo_p + hi_p)))
    return {
        "abstain": False,
        "family": "lindemann",
        "log_k_inf_300K": lnk,
        "log_Pr_300K_1bar": -2.0,
        "Fcent": 1.0,
        "confidence": 0.75,
    }
