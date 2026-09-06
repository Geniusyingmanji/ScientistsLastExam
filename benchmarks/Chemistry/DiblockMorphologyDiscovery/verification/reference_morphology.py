"""Truth-blind SAXS first-peak plus distinctive-harmonic matcher."""
from __future__ import annotations

import math


PROBES = {
    "lamella": 3.0,
    "hex": math.sqrt(7.0),
    "bcc": math.sqrt(2.0),
    "gyroid": math.sqrt(4.0 / 3.0),
}


def identify_morphology(problem, measure):
    lo, hi = problem["q_bounds_nm_inv"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    coarse = [0.28 + 0.044 * index for index in range(10)]
    intensity = [float(measure(min(max(q, lo), hi))) for q in coarse]
    peak = max(intensity)
    locals_idx = []
    for index in range(1, 9):
        value = intensity[index]
        if value >= intensity[index - 1] and value >= intensity[index + 1] and value >= 0.38 * peak:
            locals_idx.append(index)
    first = locals_idx[0] if locals_idx else intensity.index(peak)
    q0 = coarse[first]
    refine = (q0 - 0.014, q0 + 0.014)
    refined = [(float(measure(min(max(q, lo), hi))), q) for q in refine]
    i_star, q_star = max([(intensity[first], q0)] + refined)
    harmonics = {
        name: float(measure(min(hi, max(lo, q_star * ratio))))
        for name, ratio in PROBES.items()
    }
    ranked = sorted(harmonics, key=harmonics.get, reverse=True)
    best, second = ranked[0], ranked[1]
    baseline = 0.18
    excess = {name: max(harmonics[name] - baseline, 0.0) for name in PROBES}
    ratio = None
    if len(locals_idx) >= 2:
        ratio = coarse[locals_idx[1]] / max(coarse[locals_idx[0]], 1e-9)
    if i_star > 7.0:
        return {"abstain": False, "morphology": "disorder", "confidence": 0.8}
    in_family_second = ratio is not None and (
        1.13 <= ratio <= 1.18 or 1.33 <= ratio <= 1.50 or 1.65 <= ratio <= 1.82
    )
    if len(locals_idx) >= 2 and not in_family_second:
        return {"abstain": True, "confidence": 0.78}
    if max(excess.values()) < 0.45:
        return {"abstain": False, "morphology": "disorder", "confidence": 0.74}
    if excess[best] < 1.35 * max(excess[second], 0.08):
        return {"abstain": True, "confidence": 0.7}
    return {"abstain": False, "morphology": best, "confidence": 0.73}
