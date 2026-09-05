"""Truth-blind reference witness: greedy edit search on the public LP.

Standalone: it builds the same steady-state programs from the public problem
statement (nominal capacities, no knowledge of the sealed draws), and greedily
applies the single edit — knockout of an editable reaction, or an overexpression
multiplier from a fixed ladder — that most improves product flux under the nominal
capacities, until the edit budget is spent or no edit helps. It deliberately lacks
lookahead beyond one edit, robustness-aware selection across capacity draws, and
continuous multiplier optimization.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

MULTIPLIER_LADDER = (1.5, 2.0, 2.5, 4.0)
DEVIATION = (0.65, 1.35)


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
    for name in design["knockouts"]:
        applied[name] = 0.0
    for name, multiplier in design["overexpressions"].items():
        applied[name] = min(applied[name] * multiplier,
                            4.0 * problem["nominal_capacity"][name])
    return applied


def _draws(problem, seed=0):
    """Stratified capacity draws from the public deviation model: the nominal
    capacities, the both extremes, and two random spreads. Capacity corners are
    where individual enzyme caps start to bind and single-edit greedy otherwise
    cannot see the need for further overexpression."""
    rng = np.random.default_rng(seed)
    names = list(problem["reactions"])
    draws = [dict(problem["nominal_capacity"])]
    for factor in DEVIATION:
        draws.append({name: problem["nominal_capacity"][name] * factor
                      for name in names})
    for _ in range(2):
        factors = rng.uniform(DEVIATION[0], DEVIATION[1], size=len(names))
        draws.append({name: problem["nominal_capacity"][name] * float(factor)
                      for name, factor in zip(names, factors)})
    return draws


def _evaluate(problem, design, draws):
    """Worst-case product flux across the public deviation model draws.

    The viability gate is a fraction of the un-engineered maximum under each draw —
    the same semantics the oracle applies.
    """
    worst = None
    for capacities in draws:
        demand = problem["biomass_fraction_gate"] * _max_biomass(problem, capacities)
        applied = _applied(problem, design, capacities)
        value = _solve(problem, applied, demand) or 0.0
        worst = value if worst is None else min(worst, value)
    return worst


def design_strain(problem):
    draws = _draws(problem, seed=0)
    design = {"knockouts": [], "overexpressions": {}}
    best_value = _evaluate(problem, design, draws)
    for _ in range(problem["max_edits"]):
        candidates = []
        for name in problem["editable_reactions"]:
            if name in design["knockouts"]:
                continue
            trial = {"knockouts": design["knockouts"] + [name],
                     "overexpressions": dict(design["overexpressions"])}
            candidates.append((_evaluate(problem, trial, draws), trial))
            for multiplier in MULTIPLIER_LADDER:
                if name in design["overexpressions"]:
                    continue
                trial = {"knockouts": list(design["knockouts"]),
                         "overexpressions": dict(design["overexpressions"],
                                                 **{name: multiplier})}
                candidates.append((_evaluate(problem, trial, draws), trial))
        candidates.sort(key=lambda row: (-row[0], sorted(row[1]["knockouts"]),
                                         sorted(row[1]["overexpressions"])))
        if not candidates or candidates[0][0] <= best_value + 1e-9:
            break
        best_value, design = candidates[0][0], candidates[0][1]
    return design
