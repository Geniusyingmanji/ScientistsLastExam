"""Baseline: spend the budget evenly, fit, claim anything that fits, never abstain.

This is the analysis the field's own critiques are about. It allocates transits uniformly, solves a
non-negative least squares fit of the species catalogue to the binned depths, and reports every
species whose fitted amplitude clears a fixed threshold. It has no notion that two species can be
indistinguishable, and no notion that a spectrum can fail to decide - so it names a member of the
confusable pair whenever the fit prefers one, and it never abstains.

It scores zero, and it scores zero on the axis that matters: the refusal rate is zero by
construction, so no amount of correct identification elsewhere rescues it.
"""
import numpy as np


def analyze(problem, observe):
    bands = len(problem["band_edges_um"]) - 1
    budget = problem["budget_transits"]
    each = budget // bands
    allocation = [each] * bands
    for index in range(budget - each * bands):
        allocation[index] += 1
    reading = observe(allocation)

    wavelengths = np.asarray(problem["wavelength_um"])
    sections = np.asarray(problem["cross_sections"])
    edges = problem["band_edges_um"]
    rows, values = [], []
    for band in reading["bands"]:
        if band["depth"] is None:
            continue
        index = band["band_index"]
        mask = (wavelengths >= edges[index]) & (wavelengths < edges[index + 1])
        rows.append(sections[:, mask].mean(axis=1))
        values.append(band["depth"])
    if not rows:
        return {"abstain": False, "species": {}, "confidence": 0.0}

    design = np.column_stack([np.asarray(rows), np.ones(len(rows))])
    target = np.asarray(values)
    fit, *_ = np.linalg.lstsq(design, target, rcond=None)
    amplitudes = fit[:len(problem["species_catalogue"])]
    cut = 0.15 * float(np.max(np.abs(amplitudes))) if amplitudes.size else 0.0
    species = {name: bool(amplitudes[i] > cut)
               for i, name in enumerate(problem["species_catalogue"])}
    return {"abstain": False, "species": species, "confidence": 0.5}
