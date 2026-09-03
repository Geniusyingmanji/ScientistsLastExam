"""Weak but valid baseline for ForcedSignalAttribution.

It does what a first look invites: average the field over regions, regress that series on the
fingerprint's own regional mean by ordinary least squares, and read the t-statistic as if the
years were independent. Averaging over regions throws away the pattern that separates the forced
response from the leading mode of variability; red internal variability makes the white-noise
interval far too narrow, so unforced records get "detected"; and it never asks whether what is
left looks like the model's variability, so a wrong fingerprint or a quiet model is published as a
result. It spends no control years at all.
"""
from __future__ import annotations

import numpy as np


def attribute(problem, run_control):
    observations = np.asarray(problem["observations"], dtype=float)
    fingerprint = np.asarray(problem["fingerprint"], dtype=float)
    series = observations.mean(axis=1)
    forced = fingerprint.mean(axis=1)
    design = np.column_stack([forced, np.ones_like(forced)])
    coefficients = np.linalg.lstsq(design, series, rcond=None)[0]
    beta = float(coefficients[0])
    residual = series - design @ coefficients
    dof = max(1, len(series) - 2)
    variance = float(residual @ residual) / dof * float(np.linalg.inv(design.T @ design)[0, 0])
    sigma = float(np.sqrt(max(variance, 1e-18)))
    low, high = beta - 1.645 * sigma, beta + 1.645 * sigma
    return {"detected": bool(low > 0.0), "scaling_factor": beta, "interval": [low, high],
            "abstain": False, "confidence": 0.9}
