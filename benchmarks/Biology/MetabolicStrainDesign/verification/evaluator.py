"""Deterministic constraint-based strain-design oracle."""
from __future__ import annotations

import itertools
from functools import lru_cache
import numpy as np
from scipy.optimize import linprog

SPECS = (
    (1.00, 0.20, 2.00, 10.0, 2),
    (1.10, 0.25, 2.20, 9.0, 3),
    (0.90, 0.18, 1.80, 11.0, 4),
    (1.20, 0.30, 2.35, 8.5, 3),
    (0.95, 0.22, 1.95, 10.5, 4),
    (1.05, 0.27, 2.15, 9.5, 2),
)
DEVELOPMENT = tuple(range(4))
HELDOUT = (4, 5)
KNOCKOUT_BUDGET = 4


def _problem(index):
    redox_in, redox_biomass, redox_product, uptake, _ = SPECS[index]
    # Carbon, reducing equivalents, energy, and two intracellular intermediates.
    # Alternative routes share intermediates and couple redox disposal to energy
    # supply. Blocking a terminal drain alone need not block the competing route.
    # Keeping an energy-producing route can help growth but compete with product.
    energy_cost = (0.45, 0.65, 0.15, 0.20, 0.55, 0.30)[index]
    redox_energy_cost = (0.15, 0.25, 0.65, 0.85, 0.30, 0.95)[index]
    logical = [
        [1.0, redox_in, 0.0, 0.0, 0.0],
        [-1.0, -redox_biomass, -1.0, 0.0, 0.0],
        [-1.0, -redox_product, 0.0, 0.0, 0.0],
        [-energy_cost, 0.0, 1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, -1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 0.0, 0.0, -1.0],
        [0.0, -redox_energy_cost, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.2 + 0.2 * (index % 3), -1.0, 0.0],
        [0.0, 0.0, 0.3 + 0.2 * ((index + 1) % 3), 0.0, -1.0],
        [-1.0, 0.0, 0.0, 0.0, 0.0],
    ]
    permutation = np.random.default_rng(7100 + index).permutation(len(logical))
    reaction_ids = [f"R{i:02d}" for i in range(len(logical))]
    column_roles = list(permutation)
    matrix = np.asarray(logical, float).T[:, permutation]
    return {
        "reaction_ids": reaction_ids, "stoichiometric_matrix": matrix.tolist(),
        "lower_bounds": [0.0] * len(logical),
        "upper_bounds": [uptake if role == 0 else 100.0 for role in column_roles],
        "biomass_reaction": reaction_ids[column_roles.index(1)],
        "product_reaction": reaction_ids[column_roles.index(2)],
        "allowed_reaction_knockouts": [reaction_ids[j] for j, role in enumerate(column_roles) if role >= 4],
        "maximum_knockouts": KNOCKOUT_BUDGET, "minimum_growth": 1.0,
        "growth_optimality_tolerance": 1e-7,
    }


def _flux(problem, knockouts, objective, *, growth_floor=None):
    ids = problem["reaction_ids"]
    bounds = list(zip(problem["lower_bounds"], problem["upper_bounds"]))
    for name in knockouts:
        j = ids.index(name)
        bounds[j] = (0.0, 0.0)
    c = np.zeros(len(ids)); c[ids.index(objective)] = -1.0
    a_ub = b_ub = None
    if growth_floor is not None:
        a_ub = np.zeros((1, len(ids))); a_ub[0, ids.index(problem["biomass_reaction"])] = -1.0
        b_ub = np.array([-growth_floor])
    out = linprog(c, A_eq=np.asarray(problem["stoichiometric_matrix"]), b_eq=np.zeros(len(problem["stoichiometric_matrix"])),
                  A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")
    return None if not out.success else np.asarray(out.x)


def _utility(problem, knockouts):
    growth = _flux(problem, knockouts, problem["biomass_reaction"])
    if growth is None:
        return 0.0
    ids = problem["reaction_ids"]
    mu = float(growth[ids.index(problem["biomass_reaction"])])
    if mu < problem["minimum_growth"]:
        return 0.0
    bounds = list(zip(problem["lower_bounds"], problem["upper_bounds"]))
    for name in knockouts:
        bounds[ids.index(name)] = (0.0, 0.0)
    c = np.zeros(len(ids)); c[ids.index(problem["product_reaction"])] = 1.0
    a = np.zeros((1, len(ids))); a[0, ids.index(problem["biomass_reaction"])] = -1.0
    out = linprog(c, A_eq=np.asarray(problem["stoichiometric_matrix"]), b_eq=np.zeros(len(problem["stoichiometric_matrix"])),
                  A_ub=a, b_ub=[-(mu - problem["growth_optimality_tolerance"])],
                  bounds=bounds, method="highs")
    if not out.success:
        return 0.0
    product = max(0.0, float(out.x[ids.index(problem["product_reaction"])]))
    return product * mu / (1.0 + 0.08 * len(knockouts))


@lru_cache(maxsize=None)
def _reference_value(index):
    problem=_problem(index); allowed=problem["allowed_reaction_knockouts"]
    return max(_utility(problem, combo) for k in range(KNOCKOUT_BUDGET + 1)
               for combo in itertools.combinations(allowed, k))


def _score_output(index,problem, output):
    if not isinstance(output, dict) or set(output) != {"reaction_knockouts"}:
        return 0.0, False
    value = output["reaction_knockouts"]
    if not isinstance(value, list) or len(value) > KNOCKOUT_BUDGET or len(set(value)) != len(value):
        return 0.0, False
    if any(not isinstance(x, str) or x not in problem["allowed_reaction_knockouts"] for x in value):
        return 0.0, False
    ref = _reference_value(index)
    utility = _utility(problem, tuple(value))
    return (utility / ref if ref > 0 else 0.0), True


def evaluate(design_strain):
    rows = []
    for index in range(len(SPECS)):
        problem = _problem(index)
        try:
            output = design_strain(problem)
            score, valid = _score_output(index,problem, output)
        except Exception:
            score, valid = 0.0, False
        rows.append({"index": index, "score": float(score), "valid": bool(valid)})
    dev = [rows[i] for i in DEVELOPMENT]; held = [rows[i] for i in HELDOUT]
    valid_rate = float(np.mean([r["valid"] for r in dev]))
    return {"combined_score": float(np.mean([r["score"] for r in dev])),
            "valid": 1.0 if valid_rate == 1.0 else 0.0, "feasibility_rate": valid_rate,
            "heldout_score": float(np.mean([r["score"] for r in held])), "per_instance": rows}
