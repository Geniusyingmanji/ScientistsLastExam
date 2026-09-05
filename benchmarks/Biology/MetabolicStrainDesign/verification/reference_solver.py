"""Truth-blind reference witness: worst-case greedy over public enzyme edits.

Standalone: it rebuilds the linear programs from the public problem statement and
greedily applies the enzyme edit (knockout, or an overexpression multiplier from
the ladder) that most improves the worst-case product flux across stratified draws
from the public deviation model, under the shared engineering budget, until the
edit budget is spent. It deliberately lacks continuous multiplier optimization,
lookahead, and robustness weighting beyond the worst case.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

MULTIPLIER_LADDER = (1.5, 2.0, 2.5, 3.0, 4.0)


def _solve(problem, capacities, demand):
    names = list(problem["reactions"])
    stoichiometry = problem["stoichiometry"]
    metabolites = list(stoichiometry)
    rows = [[stoichiometry[m].get(name, 0.0) for name in names] for m in metabolites]
    objective = np.zeros(len(names))
    objective[names.index("product")] = -1.0
    bounds = [(0.0, capacities[name]) for name in names]
    bounds[names.index("biomass")] = (demand, demand)
    result = linprog(objective, A_eq=np.asarray(rows), b_eq=np.zeros(len(rows)),
                     bounds=bounds, method="highs")
    if not result.success:
        return None
    return float(-result.fun)


def _max_biomass(problem, capacities):
    names = list(problem["reactions"])
    stoichiometry = problem["stoichiometry"]
    metabolites = list(stoichiometry)
    rows = [[stoichiometry[m].get(name, 0.0) for name in names] for m in metabolites]
    objective = np.zeros(len(names))
    objective[names.index("biomass")] = -1.0
    result = linprog(objective, A_eq=np.asarray(rows), b_eq=np.zeros(len(rows)),
                     bounds=[(0.0, capacities[name]) for name in names],
                     method="highs")
    if not result.success:
        return 0.0
    return float(-result.fun)


def _applied(problem, design, capacities):
    applied = dict(capacities)
    enzymes = problem["enzymes"]
    nominal = problem["nominal_capacity"]
    for enzyme in design["knockouts"]:
        for reaction in enzymes[enzyme]:
            applied[reaction] = 0.0
    for enzyme, multiplier in design["overexpressions"].items():
        for reaction in enzymes[enzyme]:
            applied[reaction] = min(applied[reaction] * multiplier,
                                    4.0 * nominal[reaction])
    return applied


def _draws(problem, seed=0):
    """Stratified draws: nominal, both deviation corners, two random spreads."""
    rng = np.random.default_rng(seed)
    names = list(problem["reactions"])
    draws = [dict(problem["nominal_capacity"])]
    for factor in (0.65, 1.35):
        draws.append({name: problem["nominal_capacity"][name] * factor
                      for name in names})
    for _ in range(2):
        factors = rng.uniform(0.65, 1.35, size=len(names))
        draws.append({name: problem["nominal_capacity"][name] * float(factor)
                      for name, factor in zip(names, factors)})
    return draws


def _spent(design):
    return sum(multiplier - 1.0 for multiplier in design["overexpressions"].values())


def _evaluate(problem, design, draws):
    """Worst-case product flux across draws under the viability gate."""
    worst = None
    for capacities in draws:
        demand = problem["biomass_fraction_gate"] * _max_biomass(problem, capacities)
        value = _solve(problem, _applied(problem, design, capacities), demand)
        value = value if value is not None else 0.0
        worst = value if worst is None else min(worst, value)
    return worst


def design_strain(problem):
    draws = _draws(problem, seed=0)
    budget = problem["engineering_budget"]
    design = {"knockouts": [], "overexpressions": {}}
    best_value = _evaluate(problem, design, draws)
    for _ in range(problem["max_enzyme_edits"]):
        candidates = []
        for enzyme in problem["enzymes"]:
            if enzyme in design["knockouts"]:
                continue
            trial = {"knockouts": design["knockouts"] + [enzyme],
                     "overexpressions": dict(design["overexpressions"])}
            candidates.append((_evaluate(problem, trial, draws), trial))
            for multiplier in MULTIPLIER_LADDER:
                if enzyme in design["overexpressions"]:
                    continue
                if _spent(design) + multiplier - 1.0 > budget + 1e-9:
                    continue
                trial = {"knockouts": list(design["knockouts"]),
                         "overexpressions": dict(design["overexpressions"],
                                                 **{enzyme: multiplier})}
                candidates.append((_evaluate(problem, trial, draws), trial))
        candidates.sort(key=lambda row: (-row[0], sorted(row[1]["knockouts"]),
                                         sorted(row[1]["overexpressions"])))
        if not candidates or candidates[0][0] <= best_value + 1e-9:
            break
        best_value, design = candidates[0][0], candidates[0][1]
    return design
