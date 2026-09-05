"""Reference: fit, test each species against its own uncertainty, and refuse on three grounds.

Deliberately below the ceiling. The allocation is a single fixed split rather than an optimised
design, the fit is ordinary least squares on the log-depth rather than a proper likelihood, and the
significance is read off the linear covariance rather than from a profile. What it does have that
the baseline does not is a reason to say nothing:

  * **no signal** - if no band's departure from a featureless spectrum clears its own uncertainty,
    the system is not decidable at this budget, which is the muted and faint regimes;
  * **degeneracy** - if the fit cannot separate the two members of the confusable group, naming
    either is a claim the data does not support, which is the situation the K2-18 b reanalyses
    describe;
  * **weak individual detection** - a species whose fitted amplitude does not clear its own
    uncertainty is not reported, which is what keeps the false discovery rate down.

The first two are the ones the baseline lacks entirely, and they are the whole difference between
zero and a score.
"""
from __future__ import annotations

import numpy as np

SIGNIFICANCE = 2.5
SYSTEM_SIGNIFICANCE = 4.0
DEGENERACY_CORRELATION = 0.9


def analyze(problem, observe):
    catalogue = list(problem["species_catalogue"])
    confusable = [name for name in problem.get("known_confusable_group", [])
                  if name in catalogue]
    bands = len(problem["band_edges_um"]) - 1
    budget = int(problem["budget_transits"])

    # One fixed split: everything on the bands, weighted towards the wider ones, which carry more
    # points and therefore average down faster. Choosing the split by information gain is left open.
    edges = np.asarray(problem["band_edges_um"], dtype=float)
    widths = np.diff(edges)
    share = widths / widths.sum()
    allocation = np.floor(share * budget).astype(int)
    while int(allocation.sum()) < budget:
        allocation[int(np.argmax(share * budget - allocation))] += 1
    reading = observe([int(v) for v in allocation])

    wavelengths = np.asarray(problem["wavelength_um"], dtype=float)
    sections = np.asarray(problem["cross_sections"], dtype=float)
    rows, values, sigmas = [], [], []
    for band in reading["bands"]:
        if band["depth"] is None or band["uncertainty"] is None:
            continue
        index = band["band_index"]
        mask = (wavelengths >= edges[index]) & (wavelengths < edges[index + 1])
        if not mask.any():
            continue
        rows.append(sections[:, mask].mean(axis=1))
        values.append(float(band["depth"]))
        sigmas.append(float(band["uncertainty"]))
    if len(rows) < len(catalogue) + 1:
        return {"abstain": True, "species": {}, "confidence": 0.0}

    design = np.column_stack([np.asarray(rows), np.ones(len(rows))])
    target = np.asarray(values)
    weights = 1.0 / np.asarray(sigmas)
    scaled = design * weights[:, None]
    scaled_target = target * weights

    # Is there any signal at all? Compare the fit against a featureless spectrum.
    fit, residual, rank, _sv = np.linalg.lstsq(scaled, scaled_target, rcond=None)
    flat = np.column_stack([np.ones(len(rows))]) * weights[:, None]
    flat_fit, *_ = np.linalg.lstsq(flat, scaled_target, rcond=None)
    improvement = float(np.sum((scaled_target - flat @ flat_fit) ** 2)
                        - np.sum((scaled_target - scaled @ fit) ** 2))
    if improvement < SYSTEM_SIGNIFICANCE ** 2:
        return {"abstain": True, "species": {}, "confidence": 0.0}

    try:
        covariance = np.linalg.inv(scaled.T @ scaled)
    except np.linalg.LinAlgError:
        return {"abstain": True, "species": {}, "confidence": 0.0}
    errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))

    # Degeneracy: if the two confusable amplitudes are anti-correlated near -1 in the fit, the data
    # constrains their sum and not either one.
    if len(confusable) == 2:
        a, b = (catalogue.index(name) for name in confusable)
        denominator = errors[a] * errors[b]
        if denominator > 0:
            correlation = float(covariance[a, b] / denominator)
            if abs(correlation) > DEGENERACY_CORRELATION:
                combined = fit[a] + fit[b]
                spread = math_sqrt(covariance[a, a] + covariance[b, b] + 2 * covariance[a, b])
                if spread > 0 and combined / spread > SIGNIFICANCE:
                    # Something is there and the data cannot say which. That is the refusal case.
                    return {"abstain": True, "species": {}, "confidence": 0.0}

    species = {}
    strengths = []
    for index, name in enumerate(catalogue):
        if name in confusable:
            species[name] = False
            continue
        error = errors[index]
        ratio = float(fit[index] / error) if error > 0 else 0.0
        species[name] = bool(ratio > SIGNIFICANCE)
        if species[name]:
            strengths.append(ratio)
    confidence = float(min(1.0, min(strengths) / (2.0 * SIGNIFICANCE))) if strengths else 0.2
    return {"abstain": False, "species": species, "confidence": confidence}


def math_sqrt(value):
    return float(np.sqrt(max(0.0, value)))
