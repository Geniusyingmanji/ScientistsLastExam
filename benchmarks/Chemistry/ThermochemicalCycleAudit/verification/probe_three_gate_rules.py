"""No-query shortcut: three fixed gates over a weighted Hess-law adjustment."""
from __future__ import annotations

import math

import numpy as np

CONSISTENT_GATE = 2.5
DOMINANT_GATE = 6.0
DRIFT_GATE = 2.0


def _design(problem):
    species = list(problem["species"])
    rows, values, sigmas, ids, instruments = [], [], [], [], []
    for measurement in problem["measurements"]:
        vector = np.zeros(len(species))
        for name, coefficient in measurement["stoichiometry"].items():
            vector[species.index(name)] = coefficient
        rows.append(vector)
        values.append(measurement["value_kj_per_mol"])
        sigmas.append(measurement["sigma_kj_per_mol"])
        ids.append(measurement["id"])
        instruments.append(measurement["instrument"])
    return np.asarray(rows), np.asarray(values), np.asarray(sigmas), ids, instruments


def _fit(design, values, sigmas):
    weights = 1.0 / sigmas ** 2
    normal = design.T @ (design * weights[:, None])
    right = design.T @ (weights * values)
    enthalpies = np.linalg.lstsq(normal, right, rcond=None)[0]
    return enthalpies, values - design @ enthalpies


def _result(verdict, flagged, instrument, ids, design, enthalpies, confidence):
    return {
        "verdict": verdict,
        "flagged_measurements": flagged,
        "drift_instrument": instrument,
        "corrected_enthalpies": {name: float(value)
                                 for name, value in zip(ids, design @ enthalpies)},
        "confidence": confidence,
    }


def audit_thermochemical_cycle(problem, replicate, cross_check, budget_units):
    del replicate, cross_check, budget_units
    design, values, sigmas, ids, instruments = _design(problem)
    enthalpies, residuals = _fit(design, values, sigmas)
    dof = max(len(ids) - np.linalg.matrix_rank(design), 1)
    chi_square = float(np.sum((residuals / sigmas) ** 2) / dof)
    if chi_square < CONSISTENT_GATE:
        return _result("consistent", [], "", ids, design, enthalpies, 0.8)

    studentized = np.abs(residuals) / sigmas
    order = list(np.argsort(-studentized))
    top = order[0]
    ambiguous = set()
    for first in range(len(design)):
        for second in range(first + 1, len(design)):
            if np.array_equal(design[first], -design[second]):
                ambiguous.update((first, second))
    if top in ambiguous and set(order[:2]) == ambiguous:
        return _result("underdetermined", [], "", ids, design, enthalpies, 0.6)

    if studentized[top] >= DOMINANT_GATE:
        keep = np.ones(len(ids), dtype=bool)
        keep[top] = False
        repaired, _ = _fit(design[keep], values[keep], sigmas[keep])
        return _result("single_fault", [ids[top]], "", ids, design, repaired, 0.7)

    best_instrument, best_z = None, 0.0
    for instrument in sorted(set(instruments)):
        members = [index for index, name in enumerate(instruments)
                   if name == instrument and index not in ambiguous]
        if len(members) < 2:
            continue
        precision = float(np.sum(1.0 / sigmas[members] ** 2))
        mean_z = abs(float(np.sum(residuals[members] / sigmas[members] ** 2))
                     / math.sqrt(precision))
        if mean_z > best_z:
            best_instrument, best_z = instrument, mean_z
    if best_instrument is not None and best_z >= DRIFT_GATE:
        names = sorted(set(instruments))
        offsets = np.column_stack([
            np.asarray([1.0 if value == name else 0.0 for value in instruments])
            for name in names
        ])
        augmented = np.hstack([design, offsets])
        solution, _ = _fit(augmented, values, sigmas)
        return _result("instrument_drift",
                       [ids[index] for index, name in enumerate(instruments)
                        if name == best_instrument],
                       best_instrument, ids, design, solution[:len(problem["species"])], 0.7)

    return _result("single_fault", [ids[top]], "", ids, design, enthalpies, 0.6)
