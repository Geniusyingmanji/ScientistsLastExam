"""Weak but valid baseline for SuperconductorTcRecord.

Trusts the public historical-proxy prediction at face value: picks whichever family has the
highest quoted pre-experimental Tc upper bound (ignoring families with no quoted number) and
submits at *that proxy's own quoted pressure* -- without spending a single probe to check the
implied electron-phonon coupling against lambda_max_plausible, or whether the true optimum
actually sits at a different pressure.
"""
from __future__ import annotations


def design_superconductor(problem, probe):
    families = list(problem["families"])
    proxy = dict(problem["historical_proxy"])
    ceiling = float(problem["apparatus_pressure_ceiling_gpa"])
    _ = int(problem["probe_budget_calls"])
    _ = problem["allen_dynes_formula"]
    _ = float(problem["lambda_max_plausible"])
    _ = float(problem["known_record_tc_k"])
    _ = problem["measurement_model"]
    _ = problem["scope_note"]

    def proxy_upper(family):
        info = proxy[family]
        return info["tc_range_k"][1] if info["tc_range_k"] is not None else -1.0

    best_family = max(families, key=proxy_upper)
    pressure_gpa = min(proxy[best_family]["pressure_gpa"], ceiling)

    return {
        "family": best_family,
        "pressure_gpa": pressure_gpa,
        "predicted_tc_k": proxy_upper(best_family),
        "confidence": 0.5,
    }
