"""Truth-blind reference witness: weighted network adjustment, drift test, pendant triage.

Uses only the public measurements and the charged laboratory. Weighted least squares
over the public species reconciles Hess closure; a dominant single outlier is tested by
drop-and-refit before any drift test, because least squares otherwise smears one giant
slip across the culprit's instrument class; a coherent per-class shift is confirmed by
one budgeted cross-check; a pendant-pair tension is either resolved by a cross-check or
declared underdetermined while still returning reconciled values.
"""

from __future__ import annotations

import math

import numpy as np

PENDANT = ("R12", "R13")
CONSISTENT_GATE = 2.5
DOMINANT_GATE = 6.0
DROP_REFIT_GATE = 2.2


def _design(problem, species):
    rows = []
    values, sigmas, ids, instruments = [], [], [], []
    for row in problem["measurements"]:
        vector = np.zeros(len(species))
        for name, coefficient in row["stoichiometry"].items():
            vector[species.index(name)] = coefficient
        rows.append(vector)
        values.append(row["value_kj_per_mol"])
        sigmas.append(row["sigma_kj_per_mol"])
        ids.append(row["id"])
        instruments.append(row["instrument"])
    return (np.asarray(rows), np.asarray(values), np.asarray(sigmas), ids, instruments)


def _weighted_fit(design, values, sigmas):
    weights = 1.0 / sigmas ** 2
    normal = design.T @ (design * weights[:, None])
    right = design.T @ (weights * values)
    enthalpies = np.linalg.lstsq(normal, right, rcond=None)[0]
    residuals = values - design @ enthalpies
    return enthalpies, residuals


def _result(verdict, flagged, instrument, ids, design, enthalpies, confidence):
    fitted = design @ enthalpies
    return {
        "verdict": verdict,
        "flagged_measurements": flagged,
        "drift_instrument": instrument,
        "corrected_enthalpies": {name: float(value)
                                 for name, value in zip(ids, fitted)},
        "confidence": confidence,
    }


def _chi_square(design, values, sigmas):
    _, residuals = _weighted_fit(design, values, sigmas)
    dof = max(len(values) - np.linalg.matrix_rank(design), 1)
    return float(np.sum((residuals / sigmas) ** 2) / dof)


def audit_thermochemical_cycle(problem, replicate, cross_check, budget_units):
    del budget_units
    species = problem["species"]
    design, values, sigmas, ids, instruments = _design(problem, species)
    dof = max(len(ids) - np.linalg.matrix_rank(design), 1)
    enthalpies, residuals = _weighted_fit(design, values, sigmas)
    chi_square = float(np.sum((residuals / sigmas) ** 2) / dof)
    if chi_square < CONSISTENT_GATE:
        return _result("consistent", [], "", ids, design, enthalpies, 0.85)

    studentized = np.abs(residuals) / sigmas
    order = list(np.argsort(-studentized))
    top = order[0]
    pendant_indices = [ids.index(name) for name in PENDANT]

    # Single-outlier triage: scan every non-ambiguous row by drop-and-refit rather
    # than assuming the largest residual is the culprit. Closure adjustment can smear
    # a giant slip onto a different row; the held-out networks exercise exactly that
    # failure. This runs before drift detection so one bad row cannot imitate a class.
    drop_candidates = []
    for candidate in range(len(ids)):
        if candidate in pendant_indices:
            continue
        keep = np.ones(len(ids), dtype=bool)
        keep[candidate] = False
        reduced = _chi_square(design[keep], values[keep], sigmas[keep])
        drop_candidates.append((reduced, candidate))
    reduced, culprit = min(drop_candidates)
    if (studentized[culprit] >= DOMINANT_GATE
            and reduced < max(DROP_REFIT_GATE, 0.25 * chi_square)):
        keep = np.ones(len(ids), dtype=bool)
        keep[culprit] = False
        enthalpies_drop, _ = _weighted_fit(design[keep], values[keep], sigmas[keep])
        return _result("single_fault", [ids[culprit]], "", ids, design,
                       enthalpies_drop, 0.75)

    # Pendant tension: the duplicate/reverse pair carries the largest residuals. One
    # cross-check resolves it; without that spend, honest attribution is impossible.
    if top in pendant_indices and set(order[:2]) == set(pendant_indices):
        report = cross_check(ids[top])
        delta = abs(report["value_kj_per_mol"] - values[top])
        scale = math.hypot(report["sigma_kj_per_mol"], sigmas[top])
        if delta > 2.5 * scale:
            culprit = top
        else:
            culprit = pendant_indices[1] if top == pendant_indices[0] else pendant_indices[0]
        keep = np.ones(len(ids), dtype=bool)
        keep[culprit] = False
        enthalpies_drop, _ = _weighted_fit(design[keep], values[keep], sigmas[keep])
        return _result("single_fault", [ids[culprit]], "", ids, design,
                       enthalpies_drop, 0.75)

    # Drift test: a class with two or more members shifted in the same direction
    # (individually large, or all same-signed with a strong aggregate).
    pendant_set = set(pendant_indices)
    best_drift, best_shifted = None, []
    for instrument in sorted(set(instruments)):
        members = [i for i, name in enumerate(instruments)
                   if name == instrument and i not in pendant_set]
        if len(members) < 2:
            continue
        positive = [i for i in members if residuals[i] / sigmas[i] > 2.5]
        negative = [i for i in members if residuals[i] / sigmas[i] < -2.5]
        shifted = positive if len(positive) >= len(negative) else negative
        if len(shifted) >= 2:
            candidate = shifted
        else:
            signs = [np.sign(residuals[i]) for i in members]
            if len(set(signs)) == 1:
                precision = float(np.sum(1.0 / sigmas[members] ** 2))
                mean_z = abs(float(np.sum(residuals[members] / sigmas[members] ** 2))
                             / math.sqrt(precision))
                candidate = members if mean_z >= 2.0 else []
            else:
                candidate = []
        if len(candidate) > len(best_shifted):
            best_drift, best_shifted = instrument, candidate
    if best_drift is not None:
        strong = sum(1 for i in best_shifted if abs(residuals[i]) / sigmas[i] > 2.5) >= 2
        confirmed = strong
        if not strong:
            probe = max(best_shifted, key=lambda i: abs(residuals[i]) / sigmas[i])
            report = cross_check(ids[probe])
            delta = abs(report["value_kj_per_mol"] - values[probe])
            scale = math.hypot(report["sigma_kj_per_mol"], sigmas[probe])
            confirmed = delta > 1.5 * scale
        if confirmed:
            offsets = np.zeros((len(ids), 3))
            for column, name in enumerate(sorted(set(instruments))):
                offsets[:, column] = [1.0 if row == name else 0.0
                                      for row in instruments]
            augmented = np.hstack([design, offsets])
            weights = 1.0 / sigmas ** 2
            normal = augmented.T @ (augmented * weights[:, None])
            right = augmented.T @ (weights * values)
            solution = np.linalg.lstsq(normal, right, rcond=None)[0]
            return _result("instrument_drift",
                           [ids[i] for i, name in enumerate(instruments)
                            if name == best_drift],
                           best_drift, ids, design, solution[:len(species)], 0.8)

    # Borderline single fault: sharpen the largest residual with one replicate.
    if top not in pendant_indices and studentized[top] >= 3.0:
        report = replicate(ids[top])
        blended = 0.5 * (values[top] + report["value_kj_per_mol"])
        _, fitted_residuals = _weighted_fit(design, values, sigmas)
        if abs(blended - (values[top] - fitted_residuals[top])) > 3.0 * sigmas[top]:
            keep = np.ones(len(ids), dtype=bool)
            keep[top] = False
            enthalpies_drop, _ = _weighted_fit(design[keep], values[keep], sigmas[keep])
            return _result("single_fault", [ids[top]], "", ids, design,
                           enthalpies_drop, 0.7)

    return _result("underdetermined", [], "", ids, design, enthalpies, 0.6)
