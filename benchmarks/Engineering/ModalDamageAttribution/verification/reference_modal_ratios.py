"""Truth-blind reference for ModalDamageAttribution: work in frequency ratios, search the declared
damage family directly, and refuse when nothing in the family explains the pattern.

Reads only the public problem (which includes the validated healthy model) and the budgeted
campaign. The idea it is built on: temperature multiplies every spring by one common factor, so it
scales every eigenvalue equally and cancels exactly from the ratios f_k / f_1. Working in ratios
removes the confound outright, including the part that lives outside the commissioning band where
the temperature law is not what the baseline suggests.

    baseline    the healthy ratios come from the commissioning campaign, which measured the real
                structure, and not from the published model, which is a few per cent away from it.
    days        buy the highest-excitation days. Noise scales as 1 / sqrt(excitation), and the
                ratios need no temperature spread, so signal is the only thing worth paying for.
    family      re-solve the eigenproblem for every internal element and every severity on a grid,
                and keep the ratio pattern each one produces. This is the declared damage family,
                enumerated rather than linearised.
    decision    a shift too small to see is a healthy structure; the best member of the family is
                the answer when its residual is small relative to the shift; a residual that stays
                large no matter which member is tried is a support change, and is declined.

Deliberately not at the ceiling. Three things are left: the days are averaged with equal weight
although their noise differs threefold, so an inverse-variance average would be strictly better;
the decision is a pair of thresholds rather than a comparison of how well each hypothesis explains
the data under a stated noise model; and the search is over a grid in the severity while the
residual is smooth in it. A frontier draw took all three (see references/known_best.md) and still
left a quarter of the scale unclaimed.
"""
from __future__ import annotations

import math

import numpy as np

DETECTION_THRESHOLD = 0.008       # max ratio shift below this is a healthy structure
REFUSAL_RELATIVE_RESIDUAL = 0.30  # residual, relative to the shift, that no family member explains
SEVERITY_GRID = np.arange(0.02, 0.91, 0.01)


def _frequencies(masses, springs, mode_count):
    n = len(masses)
    stiffness = np.zeros((n, n))
    for i in range(n):
        stiffness[i, i] = springs[i] + springs[i + 1]
        if i + 1 < n:
            stiffness[i, i + 1] = -springs[i + 1]
            stiffness[i + 1, i] = -springs[i + 1]
    root_inverse = np.diag(1.0 / np.sqrt(masses))
    values = np.linalg.eigvalsh(root_inverse @ stiffness @ root_inverse)
    return np.sqrt(np.clip(values, 1e-12, None))[:mode_count] / (2.0 * math.pi)


def attribute_damage(problem, measure):
    masses = np.asarray(problem["nominal_masses"], dtype=float)
    springs = np.asarray(problem["nominal_springs"], dtype=float)
    modes = int(problem["mode_count"])
    budget = int(problem["measurement_budget_days"])
    calendar = problem["calendar"]

    # The published model carries a few per cent of error, and the commissioning campaign measured
    # the real structure. So the healthy ratios come from the campaign, not from the model; the
    # model is kept only for the shape of each damage pattern, where a common error largely
    # cancels between the damaged and healthy solutions of the same model.
    commissioning = np.array(
        [np.asarray(row["frequencies_hz"], dtype=float) for row in problem["commissioning_baseline"]])
    healthy_ratios = np.mean(commissioning / commissioning[:, :1], axis=0)
    model_healthy = _frequencies(masses, springs, modes)
    model_ratios = model_healthy / model_healthy[0]

    order = sorted(range(len(calendar)), key=lambda d: -calendar[d]["excitation_quality"])
    observed = []
    for day in order[:budget]:
        try:
            reading = measure(day)
        except Exception:
            break
        frequencies = np.asarray(reading["frequencies_hz"], dtype=float)
        if frequencies.shape != (modes,) or not np.all(np.isfinite(frequencies)) or frequencies[0] <= 0:
            continue
        observed.append(frequencies / frequencies[0])
    if not observed:
        return {"abstain": True, "confidence": 0.2}
    shift = np.mean(np.asarray(observed), axis=0) / healthy_ratios - 1.0
    magnitude = float(np.linalg.norm(shift))

    if float(np.max(np.abs(shift))) < DETECTION_THRESHOLD:
        return {"damaged": False, "abstain": False, "confidence": 0.75}

    best = (float("inf"), None, None)
    for element in range(1, len(masses)):
        for severity in SEVERITY_GRID:
            trial = springs.copy()
            trial[element] *= 1.0 - float(severity)
            frequencies = _frequencies(masses, trial, modes)
            pattern = (frequencies / frequencies[0]) / model_ratios - 1.0
            residual = float(np.linalg.norm(shift - pattern))
            if residual < best[0]:
                best = (residual, element, float(severity))
    residual, element, severity = best
    if residual / max(1e-12, magnitude) > REFUSAL_RELATIVE_RESIDUAL:
        return {"abstain": True, "confidence": 0.7}
    return {"damaged": True, "element": int(element), "severity": severity,
            "abstain": False, "confidence": 0.75}
