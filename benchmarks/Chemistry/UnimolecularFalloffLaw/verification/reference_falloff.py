"""Truth-blind Lindemann/Troe scan. Does not import the evaluator."""
from __future__ import annotations

import math


def identify_falloff(problem, measure):
    lo_t, hi_t = problem["temperature_bounds_K"]
    lo_p, hi_p = problem["pressure_bounds_bar"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["rate_law"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    temperature = min(max(300.0, lo_t), hi_t)
    pressures = (0.001, 0.003, 0.01, 0.03, 0.1, 1.0, 10.0, 100.0)
    table = {}
    for pressure in pressures:
        table[pressure] = float(measure(temperature, min(max(pressure, lo_p), hi_p)))
    high_t = min(max(600.0, lo_t), hi_t)
    hotter = min(max(900.0, lo_t), hi_t)
    t_high_lo = float(measure(high_t, lo_p))
    t_high_hi = float(measure(high_t, hi_p))
    t_hot_lo = float(measure(hotter, lo_p))
    t_hot_hi = float(measure(hotter, hi_p))
    slope_300 = table[100.0] - table[0.001]
    if slope_300 < -0.1 or t_high_hi < t_high_lo - 0.1 or t_hot_hi < t_hot_lo - 0.1:
        return {"abstain": True, "confidence": 0.86}
    order_close = (table[0.003] - table[0.001]) / math.log(0.003 / 0.001)
    order_decade = (table[0.01] - table[0.001]) / math.log(0.01 / 0.001)
    if order_close < 0.35 or order_decade < 0.42:
        return {"abstain": True, "confidence": 0.82}

    kinf = math.exp(table[100.0])
    k0_1bar = math.exp(table[0.001]) / 0.001
    p_star = kinf / max(k0_1bar, 1e-30)
    p_star = min(max(p_star, lo_p), hi_p)
    nearest = min(pressures, key=lambda pressure: abs(pressure - p_star))
    if abs(nearest - p_star) > 0.25 * max(p_star, 1e-6):
        ln_star = float(measure(temperature, p_star))
    else:
        ln_star = table[nearest]
    pr_star = k0_1bar * p_star / max(kinf, 1e-30)
    lindemann = kinf * pr_star / (1.0 + pr_star)
    f_obs = math.exp(ln_star) / max(lindemann, 1e-30)
    log_pr = math.log(max(k0_1bar / kinf, 1e-12))
    if f_obs < 0.82:
        family, fcent = "troe", 0.40
    else:
        family, fcent = "lindemann", 1.0
    return {
        "abstain": False,
        "family": family,
        "log_k_inf_300K": table[100.0],
        "log_Pr_300K_1bar": log_pr,
        "Fcent": fcent,
        "confidence": 0.72,
    }
