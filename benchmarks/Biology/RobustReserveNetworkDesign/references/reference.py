"""Standalone input-only classical reference; no world generator or truth."""

from copy import deepcopy

from functools import lru_cache

import numpy as np

def scenario_utilities(problem, selected):
    x = np.zeros(len(problem["patch_ids"]))
    for name in selected:
        x[problem["patch_ids"].index(name)] = 1.
    quality = np.asarray(problem["habitat_quality"])
    d = np.asarray(problem["dispersal_matrices"])
    e = np.asarray(problem["extinction_rates"])
    p = np.broadcast_to(np.asarray(problem["initial_occupancy"]), quality.shape).copy()*x
    for _ in problem["time_grid"][1:]:
        pressure = np.einsum('csji,csj->csi', d, p*x)
        p = x*(p*(1-e)+(1-p)*(-np.expm1(-pressure)))
    return np.sum(p*quality*np.asarray(problem["species_weights"])[None, :, None], axis=(1, 2))

def utility(problem, selected):
    return float(np.min(scenario_utilities(problem, selected)))

def reference(problem, swaps=1):
    ids, costs = problem["patch_ids"], dict(zip(problem["patch_ids"], problem["costs"]))
    selected, spent = [], 0
    while True:
        base = utility(problem, selected)
        options = [((utility(problem, selected+[name])-base)/costs[name], name)
                   for name in ids if name not in selected and spent+costs[name] <= problem["budget"]]
        if not options:
            break
        gain, name = max(options)
        if gain <= 1e-12:
            break
        selected.append(name)
        spent += costs[name]
    for _ in range(swaps):
        best, value = list(selected), utility(problem, selected)
        for old in sorted(selected):
            for new in ids:
                if new in selected or spent-costs[old]+costs[new] > problem["budget"]:
                    continue
                candidate = sorted([v for v in selected if v != old]+[new])
                u = utility(problem, candidate)
                if u > value+1e-12:
                    best, value = candidate, u
        if set(best) == set(selected):
            break
        selected = best
        spent = sum(costs[v] for v in selected)
    return {"protected_patches": sorted(selected)}

design_reserve = reference
