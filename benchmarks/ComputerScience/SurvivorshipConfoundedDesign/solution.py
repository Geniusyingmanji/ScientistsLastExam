"""Weak but valid baseline for SurvivorshipConfoundedDesign.

It does what the returned table invites: regress outcome on treatment among survivors,
publish the OLS sign as a causal effect, never intervene, never decline. Collider and
blank worlds therefore become papers.
"""
from __future__ import annotations


def recover_effect(problem, observe_survivors, intervene):
    del intervene
    _ = problem["treatment_name"]
    _ = problem["outcome_name"]
    _ = int(problem["observe_batch_max"])
    _ = int(problem["intervene_batch_max"])
    _ = int(problem["budget_units"])
    _ = int(problem["sample_unit"])
    _ = float(problem["treatment_probe_low"])
    _ = float(problem["treatment_probe_high"])
    _ = problem["measurement_model"]
    _ = problem["selection_note"]
    _ = problem["abstain_when"]
    try:
        rows = observe_survivors(min(400, int(problem["observe_batch_max"])))
    except Exception:
        return {"abstain": True, "confidence": 0.0}
    t = list(rows.get("treatment") or [])
    y = list(rows.get("outcome") or [])
    if len(t) < 8 or len(t) != len(y):
        return {
            "abstain": False,
            "has_treatment_effect": True,
            "effect_sign": 1.0,
            "confidence": 0.4,
        }
    t_mean = sum(t) / len(t)
    y_mean = sum(y) / len(y)
    num = sum((ti - t_mean) * (yi - y_mean) for ti, yi in zip(t, y))
    den = sum((ti - t_mean) ** 2 for ti in t)
    slope = num / den if den > 1e-12 else 1.0
    return {
        "abstain": False,
        "has_treatment_effect": True,
        "effect_sign": 1.0 if slope >= 0 else -1.0,
        "confidence": 0.85,
    }
