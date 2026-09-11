"""Weak but valid baseline for LDMismatchFineMapping.

The everyday answer: clump the genome-wide significant variants by linkage disequilibrium in the
public reference panel, as PLINK does, and report one causal variant per clump, the strongest
one, with its marginal effect. Two variants are in the same clump when their reference-panel
r-squared exceeds 0.1. It buys nothing and never declines.

Three things are wrong with it. The reference panel's correlations are not the cohort's, so a
proxy whose reference r-squared falls below the clumping threshold becomes a second signal. A
masked variant has no marginal signal, so it is never a clump. And when the causal variant has a
near-duplicate the data cannot separate, one of the two is reported as causal anyway.
"""
from __future__ import annotations

import numpy as np

SIGNIFICANCE = 5.45      # z for p = 5e-8
CLUMP_R2 = 0.1


def fine_map(problem, ld_row):
    z = np.asarray(problem["z"], dtype=float)
    se = np.asarray(problem["standard_error"], dtype=float)
    R = np.asarray(problem["reference_ld"], dtype=float)
    order = [int(v) for v in np.argsort(-np.abs(z))]
    config = []
    for v in order:
        if abs(z[v]) < SIGNIFICANCE and config:
            break
        if all(R[v, c] ** 2 < CLUMP_R2 for c in config):
            config.append(v)
        if len(config) == int(problem["max_causal"]):
            break
    return {"verdict": "typed", "causal": config,
            "effects": [float(z[v] * se[v]) for v in config], "confidence": 0.9}
