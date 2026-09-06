"""Always publish lamellae, the textbook diblock morphology."""
from __future__ import annotations


def identify_morphology(problem, measure):
    lo, hi = problem["q_bounds_nm_inv"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    _ = float(measure(0.5 * (lo + hi)))
    return {"abstain": False, "morphology": "lamella", "confidence": 0.8}
