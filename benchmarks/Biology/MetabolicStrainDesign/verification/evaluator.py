"""Frozen oracle for MetabolicStrainDesign (hidden from the agent).

Flux-balance analysis on a public reaction network with sealed enzyme capacities:
choose enzyme knockouts and overexpression multipliers to maximize product flux
under a biomass viability gate. Two couplings make the edit decision a joint
optimization rather than a lookup: enzymes are pleiotropic (each editable enzyme
catalyzes up to three reactions, so a knockout removes several fluxes at once),
and overexpression draws on a shared engineering budget (the sum of multipliers
minus one is capped). The wild-type and witness anchors are recomputed by the same
solver per sealed draw — no literal anchors are stored, and draws are chosen so
the witness design strictly beats the wild type.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

REACTIONS = (
    "uptake", "pgi", "glycolysis", "pdh", "biosynthesis", "biomass",
    "product", "overflow", "respiration", "secretion",
    "alt_transamination", "alt_reduction", "alt_product",
    "shunt_dehydrogenase", "shunt_secretion",
    "glyoxylate_bypass", "glyoxylate_secretion",
)
INTERNAL_METABOLITES = ("g6p", "pep", "pyr", "accoa", "precursor", "redox",
                        "alt_inter", "glyoxylate")
STOICHIOMETRY = {
    "g6p": {"uptake": 1, "pgi": -1},
    "pep": {"pgi": 1, "glycolysis": -1},
    "pyr": {"glycolysis": 1, "pdh": -1, "overflow": -1,
            "alt_transamination": -0.6},
    "accoa": {"pdh": 1, "biosynthesis": -1, "product": -1, "respiration": -1,
              "alt_reduction": -0.8, "glyoxylate_bypass": -1},
    "precursor": {"biosynthesis": 1, "biomass": -1, "secretion": -1},
    "redox": {"glycolysis": 1, "respiration": -2, "shunt_dehydrogenase": -1},
    "alt_inter": {"alt_transamination": 1, "alt_reduction": 1, "alt_product": -1},
    "glyoxylate": {"glyoxylate_bypass": 1, "glyoxylate_secretion": -1,
                   "alt_product": 0.4},
}
NOMINAL_CAPACITY = {
    "uptake": 10.0, "pgi": 12.0, "glycolysis": 12.0, "pdh": 9.0,
    "biosynthesis": 8.0, "biomass": 8.0, "product": 3.0, "overflow": 9.0,
    "respiration": 7.0, "secretion": 6.0,
    "alt_transamination": 5.0, "alt_reduction": 4.0, "alt_product": 3.5,
    "shunt_dehydrogenase": 4.0, "shunt_secretion": 5.0,
    "glyoxylate_bypass": 4.0, "glyoxylate_secretion": 4.5,
}
# Pleiotropic editable enzymes: an edit acts on every reaction the enzyme
# catalyzes — knockouts remove several fluxes at once, overexpressions scale them.
ENZYMES = {
    "E_overflow": ("overflow", "shunt_secretion"),
    "E_pdh": ("pdh",),
    "E_product": ("product", "alt_product"),
    "E_secretion": ("secretion", "glyoxylate_secretion"),
    "E_alt": ("alt_transamination", "alt_reduction"),
    "E_bypass": ("glyoxylate_bypass", "shunt_dehydrogenase"),
}
MAX_ENZYME_EDITS = 3
OVEREXPRESSION_RANGE = (1.0, 4.0)
ENGINEERING_BUDGET = 3.0  # sum of (multiplier - 1) over overexpressed enzymes
BIOMASS_FRACTION = 0.5

DEVELOPMENT_DRAWS = (21101, 21107, 21113)
HELDOUT_DRAWS = (22103, 22109, 22115)

# Frozen witness design (truth-blind greedy over stratified public draws,
# verification/reference_solver.py, seed 0). Its fluxes are recomputed by the
# evaluator at scoring time.
WITNESS_DESIGN = {
    "knockouts": [],
    "overexpressions": {"E_bypass": 2.0, "E_product": 2.0},
}


def problem_statement():
    return {
        "reactions": list(REACTIONS),
        "stoichiometry": {name: dict(row) for name, row in STOICHIOMETRY.items()},
        "nominal_capacity": dict(NOMINAL_CAPACITY),
        "enzymes": {name: list(rows) for name, rows in ENZYMES.items()},
        "max_enzyme_edits": MAX_ENZYME_EDITS,
        "overexpression_range": list(OVEREXPRESSION_RANGE),
        "engineering_budget": ENGINEERING_BUDGET,
        "biomass_fraction_gate": BIOMASS_FRACTION,
        "capacity_note": (
            "true enzyme capacities deviate from nominal by up to 35 percent and "
            "are sealed; enzymes are pleiotropic — an edit acts on every reaction "
            "the enzyme catalyzes; overexpression draws on the shared engineering "
            "budget"
        ),
    }


def _capacities(seed):
    rng = np.random.default_rng(int(seed))
    factors = rng.uniform(0.65, 1.35, size=len(REACTIONS))
    return {name: NOMINAL_CAPACITY[name] * float(factor)
            for name, factor in zip(REACTIONS, factors)}


def _applied_capacities(capacities, design):
    applied = dict(capacities)
    for enzyme in design["knockouts"]:
        for reaction in ENZYMES[enzyme]:
            applied[reaction] = 0.0
    for enzyme, multiplier in design["overexpressions"].items():
        for reaction in ENZYMES[enzyme]:
            applied[reaction] = min(applied[reaction] * float(multiplier),
                                    4.0 * NOMINAL_CAPACITY[reaction])
    return applied


def solve_fluxes(capacities, demand_biomass):
    """Maximize product flux at steady state under a fixed biomass demand."""
    names = list(REACTIONS)
    rows = [[STOICHIOMETRY[m].get(name, 0.0) for name in names]
            for m in INTERNAL_METABOLITES]
    objective = np.zeros(len(names))
    objective[names.index("product")] = -1.0
    # The viability gate is an equality: the strain must run biomass at the demand.
    bounds = [(0.0, capacities[name]) for name in names]
    bounds[names.index("biomass")] = (demand_biomass, demand_biomass)
    result = linprog(objective, A_eq=np.asarray(rows), b_eq=np.zeros(len(rows)),
                     bounds=bounds, method="highs")
    if not result.success:
        return None
    return {name: float(value) for name, value in zip(names, result.x)}


def _max_biomass(capacities):
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
    return float(-result.fun)


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    knockouts = submission.get("knockouts")
    if not isinstance(knockouts, (list, tuple)) or \
            any(k not in ENZYMES for k in knockouts):
        raise ValueError("knockouts must name known enzymes")
    if len(set(knockouts)) != len(knockouts):
        raise ValueError("knockouts must be unique")
    over = submission.get("overexpressions")
    if not isinstance(over, dict) or any(name not in ENZYMES for name in over):
        raise ValueError("overexpressions must name known enzymes")
    if set(knockouts) & set(over):
        raise ValueError("an enzyme cannot be both knocked out and overexpressed")
    if len(knockouts) + len(over) > MAX_ENZYME_EDITS:
        raise ValueError("enzyme edits exceed the public budget")
    spent = 0.0
    multipliers = {}
    for name, multiplier in over.items():
        value = float(multiplier)
        if not (OVEREXPRESSION_RANGE[0] - 1e-9) <= value \
                <= (OVEREXPRESSION_RANGE[1] + 1e-9):
            raise ValueError("multipliers must lie in the public range")
        spent += value - 1.0
        multipliers[name] = value
    if spent > ENGINEERING_BUDGET + 1e-9:
        raise ValueError("overexpression exceeds the shared engineering budget")
    return {"knockouts": list(knockouts), "overexpressions": multipliers}


def _score_design(design, seeds):
    scores = []
    for seed in seeds:
        capacities = _capacities(seed)
        demand = BIOMASS_FRACTION * _max_biomass(capacities)
        if demand is None:
            scores.append(0.0)
            continue
        wildtype = solve_fluxes(_applied_capacities(
            capacities, {"knockouts": [], "overexpressions": {}}), demand)
        witness = solve_fluxes(_applied_capacities(capacities, WITNESS_DESIGN),
                               demand)
        engineered = solve_fluxes(_applied_capacities(capacities, design), demand)
        if wildtype is None or witness is None or engineered is None:
            scores.append(0.0)
            continue
        p0, w, p = wildtype["product"], witness["product"], engineered["product"]
        if w - p0 <= 1e-9:
            # Degenerate anchor: excluded by draw selection; defensive zero so a
            # degenerate draw can never hand out a free point.
            scores.append(0.0)
            continue
        if engineered["biomass"] + 1e-9 < demand:
            scores.append(0.0)
            continue
        scores.append(float(max(0.0, (p - p0) / (w - p0))))
    return scores


def evaluate(design_strain):
    try:
        design = _validate(design_strain(problem_statement()))
    except Exception:
        design = None
    dev_scores = _score_design(design, DEVELOPMENT_DRAWS) if design \
        else [0.0] * len(DEVELOPMENT_DRAWS)
    hold_scores = _score_design(design, HELDOUT_DRAWS) if design \
        else [0.0] * len(HELDOUT_DRAWS)
    return {
        "combined_score": float(np.mean(dev_scores)),
        "valid": 1.0 if design is not None else 0.0,
        "feasibility_rate": 1.0 if design is not None else 0.0,
        "development_scores": dev_scores,
        "robustness_score": float(np.mean(hold_scores)),
        "heldout_scores": hold_scores,
        "raw_score": float(np.mean(dev_scores)),
        "per_draw": [{"split": "development", "seed": seed, "score": score}
                     for seed, score in zip(DEVELOPMENT_DRAWS, dev_scores)]
                    + [{"split": "heldout", "seed": seed, "score": score}
                       for seed, score in zip(HELDOUT_DRAWS, hold_scores)],
    }
