"""Weak but valid baseline for QuinaryConvexHull.

It relaxes catalog names in order until the budget runs out and publishes every composition
with E_f < 0. Near-hull junk and a non-reproducing glass therefore become new stables.
"""
from __future__ import annotations


def recover_hull(problem, relax):
    catalog = list(problem["catalog"])
    _ = list(problem["elements"])
    _ = int(problem["n_atoms"])
    budget = int(problem["relax_budget_calls"])
    _ = int(problem["max_claimed_stables"])
    _ = problem["energy_unit"]
    _ = problem["measurement_model"]
    _ = problem["hull_note"]
    _ = problem["abstain_when"]
    claimed = []
    for name in catalog[:budget]:
        energy = float(relax(name))
        if energy < 0.0:
            claimed.append(name)
    return {
        "abstain": False,
        "stable": claimed[: int(problem["max_claimed_stables"])],
        "confidence": 0.65,
    }
