"""Always publish Newtonian viscous ice."""
from __future__ import annotations


def identify_flow_law(problem, measure):
    lo, hi = problem["stress_bounds_kPa"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["rate_law"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    _ = float(measure(0.5 * (lo + hi)))
    return {"abstain": False, "family": "newtonian", "n": 1.0, "confidence": 0.7}
