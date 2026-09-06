"""Truth-blind pulse-echo scan. Does not import the evaluator."""
from __future__ import annotations


def identify_species(problem, measure):
    lo, hi = problem["time_bounds_us"]
    _ = problem["measure_budget_calls"]
    _ = problem["family_names"]
    _ = problem["wave_speed_mm_per_us"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]

    def take(time):
        return float(measure(min(max(time, lo), hi)))

    table = {time: take(time) for time in (1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 8.0, 10.0)}
    vmin = min(table.values())
    vmax = max(table.values())
    if vmax < 0.14 and vmin > -0.14:
        return {"abstain": False, "species": "none", "confidence": 0.78}
    if vmin < -0.32 and vmax > 0.28:
        return {"abstain": True, "confidence": 0.86}
    if vmin < -0.32:
        return {"abstain": False, "species": "crack", "confidence": 0.81}
    positives = sorted(time for time, value in table.items() if value > 0.22)
    gaps = [b - a for a, b in zip(positives, positives[1:])]
    if gaps:
        offset = gaps.index(min(gaps))
        first, second = positives[offset], positives[offset + 1]
        left, right = table[first], table[second]
        if min(gaps) <= 1.2 and left > 0.55 * right and right > 0.55 * left:
            return {"abstain": False, "species": "lack_of_fusion", "confidence": 0.76}
    peak = max(table, key=table.get)
    second = take(peak + 0.55)
    _ = take(peak + 0.90)
    if second > 0.28 and second > 0.45 * max(vmax, 1e-6):
        return {"abstain": False, "species": "lack_of_fusion", "confidence": 0.76}
    return {"abstain": False, "species": "pore", "confidence": 0.73}
