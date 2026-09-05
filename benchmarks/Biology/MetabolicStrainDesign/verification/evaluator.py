"""Frozen oracle for MetabolicStrainDesign (hidden from the agent).

Flux-balance analysis on a public reaction network with sealed enzyme capacities:
choose knockouts and overexpressions to maximize product flux under a biomass
viability gate. The score is the gap closed between the wild type and a frozen
truth-blind greedy witness design, evaluated by re-solving the same linear programs
the oracle solves — no literal anchors. Beating the witness design scores above one.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

REACTIONS = ("uptake", "pgi", "glycolysis", "pdh", "biosynthesis", "biomass",
             "product", "overflow", "respiration", "secretion")
INTERNAL_METABOLITES = ("g6p", "pep", "pyr", "accoa", "precursor", "redox")
# Stoichiometry rows: metabolite x reaction.
STOICHIOMETRY = {
    "g6p": {"uptake": 1, "pgi": -1},
    "pep": {"pgi": 1, "glycolysis": -1},
    "pyr": {"glycolysis": 1, "pdh": -1, "overflow": -1},
    "accoa": {"pdh": 1, "biosynthesis": -1, "product": -1, "respiration": -1},
    "precursor": {"biosynthesis": 1, "biomass": -1, "secretion": -1},
    "redox": {"glycolysis": 1, "respiration": -2},
}
NOMINAL_CAPACITY = {
    "uptake": 10.0, "pgi": 12.0, "glycolysis": 12.0, "pdh": 9.0,
    "biosynthesis": 8.0, "biomass": 8.0, "product": 3.0, "overflow": 9.0,
    "respiration": 7.0, "secretion": 6.0,
}
ESSENTIAL = ("uptake", "pgi", "glycolysis", "pdh", "biosynthesis", "biomass",
             "respiration")  # knocking these out cannot yield a viable strain
EDITABLE = ("product", "overflow", "secretion", "pdh")
BIOMASS_FRACTION = 0.4
MAX_EDITS = 5
OVEREXPRESSION_RANGE = (1.0, 4.0)

DEVELOPMENT_DRAWS = (21001, 21007, 21013)
HELDOUT_DRAWS = (22003, 22009, 22015)

# Frozen witness design (truth-blind greedy search, verification/reference_solver.py
# with seed 0; see references/known_best.md). Its fluxes are recomputed by the
# evaluator at scoring time, so only the edit set is frozen.
WITNESS_DESIGN = {
    "knockouts": ["overflow"],
    "overexpressions": {"product": 2.0, "pdh": 2.0},
}


def problem_statement():
    return {
        "reactions": list(REACTIONS),
        "stoichiometry": {name: dict(row) for name, row in STOICHIOMETRY.items()},
        "nominal_capacity": dict(NOMINAL_CAPACITY),
        "essential_reactions": list(ESSENTIAL),
        "editable_reactions": list(EDITABLE),
        "biomass_fraction_gate": BIOMASS_FRACTION,
        "max_edits": MAX_EDITS,
        "overexpression_range": list(OVEREXPRESSION_RANGE),
        "capacity_note": (
            "true enzyme capacities deviate from nominal by up to 35 percent and are "
            "sealed; the objective is product flux and the strain must keep biomass "
            "at or above the gate"
        ),
    }


def _capacities(seed):
    rng = np.random.default_rng(int(seed))
    factors = rng.uniform(0.65, 1.35, size=len(REACTIONS))
    return {name: NOMINAL_CAPACITY[name] * float(factor)
            for name, factor in zip(REACTIONS, factors)}


def _applied_capacities(capacities, design):
    applied = dict(capacities)
    for name in design["knockouts"]:
        applied[name] = 0.0
    for name, multiplier in design["overexpressions"].items():
        applied[name] = min(applied[name] * float(multiplier),
                            4.0 * NOMINAL_CAPACITY[name])
    return applied


def solve_fluxes(capacities, demand_biomass):
    """Maximize product flux at steady state under a biomass demand."""
    names = list(REACTIONS)
    effective = dict(capacities)
    effective["biomass"] = demand_biomass
    upper = [effective[name] for name in names]
    rows, targets = [], []
    for metabolite in INTERNAL_METABOLITES:
        row = [STOICHIOMETRY[metabolite].get(name, 0.0) for name in names]
        rows.append(row)
        targets.append(0.0)
    objective = np.zeros(len(names))
    objective[names.index("product")] = -1.0
    bounds = [(0.0, value) for value in upper]
    bounds[names.index("biomass")] = (demand_biomass, demand_biomass)
    result = linprog(objective, A_eq=np.asarray(rows), b_eq=np.asarray(targets),
                     bounds=bounds, method="highs")
    if not result.success:
        return None
    return {name: float(value) for name, value in zip(names, result.x)}


def _viability_demand(capacities):
    """The un-engineered maximum biomass flux under these capacities."""
    names = list(REACTIONS)
    rows = [[STOICHIOMETRY[m].get(name, 0.0) for name in names]
            for m in INTERNAL_METABOLITES]
    objective = np.zeros(len(names))
    objective[names.index("biomass")] = -1.0
    result = linprog(objective, A_eq=np.asarray(rows), b_eq=np.zeros(len(rows)),
                     bounds=[(0.0, capacities[name]) for name in names],
                     method="highs")
    if not result.success:
        return None
    return BIOMASS_FRACTION * float(-result.fun)


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    knockouts = submission.get("knockouts")
    if not isinstance(knockouts, (list, tuple)) or any(k not in REACTIONS for k in knockouts):
        raise ValueError("knockouts must name known reactions")
    if len(set(knockouts)) != len(knockouts):
        raise ValueError("knockouts must be unique")
    if any(k in ESSENTIAL for k in knockouts):
        raise ValueError("essential reactions cannot be knocked out")
    over = submission.get("overexpressions")
    if not isinstance(over, dict) or any(name not in REACTIONS for name in over):
        raise ValueError("overexpressions must name known reactions")
    if set(knockouts) & set(over):
        raise ValueError("a reaction cannot be both knocked out and overexpressed")
    multipliers = {}
    for name, multiplier in over.items():
        value = float(multiplier)
        if not (OVEREXPRESSION_RANGE[0] - 1e-9) <= value <= (OVEREXPRESSION_RANGE[1] + 1e-9):
            raise ValueError("overexpression multipliers must lie in the public range")
        multipliers[name] = value
    if len(knockouts) + len(multipliers) > MAX_EDITS:
        raise ValueError("edits exceed the public budget")
    return {"knockouts": list(knockouts), "overexpressions": multipliers}


def _score_design(design, seeds):
    scores = []
    for seed in seeds:
        capacities = _capacities(seed)
        demand = _viability_demand(capacities)
        if demand is None:
            scores.append(0.0)
            continue
        wildtype = solve_fluxes(_applied_capacities(capacities, {"knockouts": [],
                                                                 "overexpressions": {}}), demand)
        witness = solve_fluxes(_applied_capacities(capacities, WITNESS_DESIGN), demand)
        engineered = solve_fluxes(_applied_capacities(capacities, design), demand)
        if wildtype is None or witness is None or engineered is None:
            scores.append(0.0)
            continue
        p0 = wildtype["product"]
        w = witness["product"]
        p = engineered["product"]
        if engineered["biomass"] + 1e-9 < demand:
            scores.append(0.0)
            continue
        if w - p0 <= 1e-9:
            scores.append(1.0 if p >= w else 0.0)
            continue
        scores.append(float(max(0.0, (p - p0) / (w - p0))))
    return scores


def evaluate(design_strain):
    try:
        design = _validate(design_strain(problem_statement()))
    except Exception:
        design = None
    dev_scores = _score_design(design, DEVELOPMENT_DRAWS) if design else [0.0] * len(DEVELOPMENT_DRAWS)
    hold_scores = _score_design(design, HELDOUT_DRAWS) if design else [0.0] * len(HELDOUT_DRAWS)
    return {
        "combined_score": float(np.mean(dev_scores)),
        "valid": 1.0 if design is not None else 0.0,
        "feasibility_rate": 1.0 if design is not None else 0.0,
        "development_scores": dev_scores,
        "robustness_score": float(np.mean(hold_scores)),
        "heldout_scores": hold_scores,
        "wildtype_product_flux_anchor": "recomputed per draw",
        "raw_score": float(np.mean(dev_scores)),
        "per_draw": [{"split": "development", "seed": seed, "score": score}
                     for seed, score in zip(DEVELOPMENT_DRAWS, dev_scores)]
                    + [{"split": "heldout", "seed": seed, "score": score}
                       for seed, score in zip(HELDOUT_DRAWS, hold_scores)],
    }
