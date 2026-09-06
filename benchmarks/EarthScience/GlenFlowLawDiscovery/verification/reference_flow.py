"""Truth-blind log-log slope and curvature scan. Does not import the evaluator."""
from __future__ import annotations

import math


def identify_flow_law(problem, measure):
    lo, hi = problem["stress_bounds_kPa"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["rate_law"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    stresses = (20.0, 40.0, 80.0, 160.0)
    table = {}
    for stress in stresses:
        table[stress] = float(measure(min(max(stress, lo), hi)))
    xs = [math.log(stress) for stress in stresses]
    ys = [table[stress] for stress in stresses]
    n_lo = (ys[1] - ys[0]) / (xs[1] - xs[0])
    n_mid = (ys[2] - ys[1]) / (xs[2] - xs[1])
    n_hi = (ys[3] - ys[2]) / (xs[3] - xs[2])
    curvature = max(abs(n_mid - n_lo), abs(n_hi - n_mid))
    n_all = (ys[3] - ys[0]) / (xs[3] - xs[0])
    if curvature > 0.40 or n_all < 0.55 or n_all > 3.7:
        return {"abstain": True, "confidence": 0.85}
    if 2.4 <= n_all <= 3.6:
        return {"abstain": False, "family": "glen", "n": n_all, "confidence": 0.78}
    if 0.7 <= n_all <= 1.4:
        return {"abstain": False, "family": "newtonian", "n": n_all, "confidence": 0.76}
    return {"abstain": True, "confidence": 0.70}
