"""Truth-blind reference for SurvivorshipConfoundedDesign.

OLS on returned survivors is not used. Under the public no-direct-T-to-selection and
monotone-outcome-to-selection restrictions, two charged interventions at the public probe
values estimate P(S | do(T=low)) and P(S | do(T=high)). A move larger than
SURVIVAL_DELTA supports a treatment effect whose sign is the sign of the survival
difference; otherwise the survivor association is treated as unsupported.
"""
from __future__ import annotations


def recover_effect(problem, observe_survivors, intervene):
    del observe_survivors
    low = float(problem["treatment_probe_low"])
    high = float(problem["treatment_probe_high"])
    batch = min(400, int(problem["intervene_batch_max"]))
    try:
        lo = intervene(low, batch)
        hi = intervene(high, batch)
    except Exception:
        return {"abstain": True, "confidence": 0.2}
    p_lo = lo["n_returned"] / max(1, lo["n_requested"])
    p_hi = hi["n_returned"] / max(1, hi["n_requested"])
    delta = p_hi - p_lo
    if abs(delta) < 0.12:
        return {"abstain": True, "confidence": 0.8}
    return {
        "abstain": False,
        "has_treatment_effect": True,
        "effect_sign": 1.0 if delta > 0 else -1.0,
        "confidence": 0.9,
    }
