"""Weak but valid baseline for AMOCTippingRefusal.

It treats the first historical year at which the fingerprint is negative as a collapse,
never probes, and never declines. Red-noise crossings and ice-driven declines therefore
become papers; a fold that has not yet jumped scores a wrong century.
"""
from __future__ import annotations


def interpret_amoc(problem, probe):
    del probe
    _ = int(problem["year_start"])
    _ = int(problem["year_now"])
    _ = int(problem["probe_budget"])
    _ = int(problem["min_duration_years"])
    _ = int(problem["max_duration_years"])
    _ = float(problem["freshwater_offset_low"])
    _ = float(problem["freshwater_offset_high"])
    _ = problem["modes"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    years = list(problem["historical_years"])
    amoc = list(problem["historical_amoc"])
    collapse = float(years[-1])
    for year, value in zip(years, amoc):
        if float(value) < 0.0:
            collapse = float(year)
            break
    return {
        "abstain": False,
        "has_tipping": True,
        "collapse_year": collapse,
        "confidence": 0.8,
    }
