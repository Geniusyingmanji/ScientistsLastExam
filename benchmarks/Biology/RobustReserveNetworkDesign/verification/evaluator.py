"""Finite-horizon stochastic-occupancy mean-field planning model."""
from copy import deepcopy
from functools import lru_cache
import numpy as np


def _problem(index):
    rng = np.random.default_rng(92710 + index)
    n, s = 40 + 4 * index, 4
    xy = rng.uniform(0, 1, (n, 2))
    distance = np.linalg.norm(xy[:, None] - xy[None, :], axis=2)
    dispersal = np.array([np.exp(-distance/(.12+.04*k))*.28 for k in range(s)])
    for d in dispersal:
        np.fill_diagonal(d, 0.)
    quality = rng.uniform(.35, 1., (3, s, n))
    # Opposite spatial stressors, public in every scenario.
    quality[0] *= .4 + .6*xy[:, 0]
    quality[1] *= 1. - .6*xy[:, 0]
    initial = np.zeros((s, n))
    for k in range(s):
        initial[k, rng.choice(n, 6, replace=False)] = rng.uniform(.6, 1., 6)
    return dict(patch_ids=[f"p{i}" for i in range(n)], costs=rng.integers(2, 7, n).tolist(),
                budget=45+3*index, species_weights=[1., 1.3, .8, 1.5], initial_occupancy=initial.tolist(),
                habitat_quality=quality.tolist(), dispersal_matrices=np.repeat(dispersal[None], 3, axis=0).tolist(),
                extinction_rates=(.08 + .22*(1-quality)).tolist(), time_grid=list(range(13)))


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


@lru_cache(None)
def _reference_value(index):
    p = _problem(index)
    return utility(p, reference(p)["protected_patches"])


def _score_output(index, problem, output):
    if not isinstance(output, dict) or set(output) != {"protected_patches"}:
        return 0., False
    names = output["protected_patches"]
    if not isinstance(names, list) or any(type(n) is not str or n not in problem["patch_ids"] for n in names):
        return 0., False
    if len(set(names)) != len(names) or sum(problem["costs"][problem["patch_ids"].index(n)] for n in names) > problem["budget"]:
        return 0., False
    if not names:
        return 0., True
    return float(np.clip(utility(problem, names)/_reference_value(index), 0, 1)), True


def evaluate(design_reserve):
    rows = []
    for index in range(4):
        p = _problem(index)
        try:
            output = design_reserve(deepcopy(p))
            score, valid = _score_output(index, p, output)
            raw = utility(p, output["protected_patches"]) if valid else 0.
        except Exception:
            score, valid, raw = 0., False, 0.
        rows.append(dict(score=score, valid=valid, worst_case_occupancy=raw))
    return dict(combined_score=float(np.mean([r["score"] for r in rows[:2]])),
                valid=float(all(r["valid"] for r in rows)), heldout_score=float(np.mean([r["score"] for r in rows[2:]])), per_instance=rows)
