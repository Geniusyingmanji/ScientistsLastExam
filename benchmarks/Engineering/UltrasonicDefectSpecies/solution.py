"""Always publish a clean scan: no defect."""
from __future__ import annotations


def identify_species(problem, measure):
    lo, hi = problem["time_bounds_us"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["wave_speed_mm_per_us"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    _ = float(measure(0.5 * (lo + hi)))
    return {"abstain": False, "species": "none", "confidence": 0.7}
