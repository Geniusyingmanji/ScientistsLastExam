"""Weak valid baseline: select the public-proxy batch without spending assays."""

import itertools
import math

import numpy as np


def _diversity(rows, indices):
    values = np.asarray([
        (
            float(row["ratios"]["pc_in_cyclic_carbonates"]),
            float(row["ratios"]["salt_to_cyclic_carbonates"]),
        )
        for row in rows
    ])
    spans = np.ptp(values, axis=0)
    if np.any(spans <= 0.0):
        raise ValueError("degenerate electrolyte formulation space")
    distances = [
        np.mean(np.abs((values[left] - values[right]) / spans))
        for left, right in itertools.combinations(indices, 2)
    ]
    return float(np.mean(distances))


def design_electrolyte_batch(problem, assay):
    del assay
    rows = list(problem["candidate_formulations"])
    weights = np.asarray(problem["application_weights"], dtype=float)
    curves = np.asarray([row["proxy_conductivity_s_cm"] for row in rows])
    logs = np.log(curves)
    spans = np.ptp(logs, axis=0)
    if np.any(spans <= 0.0):
        raise ValueError("degenerate electrolyte proxy surface")
    normalized = (logs - np.min(logs, axis=0)) / spans
    quality = normalized @ weights

    best = None
    for indices in itertools.combinations(range(len(rows)), int(problem["batch_size"])):
        value = 0.90 * float(np.mean(quality[list(indices)]))
        value += 0.10 * _diversity(rows, indices)
        ids = tuple(rows[index]["id"] for index in indices)
        if (
            best is None
            or value > best[0] + 1.0e-15
            or (math.isclose(value, best[0], abs_tol=1.0e-15) and ids < best[1])
        ):
            best = (value, ids)
    return {"formulation_ids": list(best[1])}
