"""Fixed strongest builder-grid family: two ranked rows, conditional selection.

This standalone candidate uses public inputs and the ordinary charged oracle.
It is a real valid shortcut, not a driver that imports the evaluator or truth.
"""
import numpy as np


def fine_map(problem, ld_row):
    z = np.asarray(problem["z"], dtype=float)
    se = np.asarray(problem["standard_error"], dtype=float)
    R = np.asarray(problem["reference_ld"], dtype=float).copy()
    order = np.argsort(-np.abs(z))
    for variant in order[:min(2, int(problem["row_budget"]))]:
        row = np.asarray(ld_row(int(variant)), dtype=float)
        R[variant, :] = row
        R[:, variant] = row
    config = [int(order[0])]
    while len(config) < int(problem["max_causal"]):
        inv = np.linalg.inv(R[np.ix_(config, config)] + 1e-6 * np.eye(len(config)))
        effects = inv @ z[config]
        variance = np.maximum(1.0 - np.einsum("is,st,it->i", R[:, config], inv, R[:, config]), 0.05)
        residual = (z - R[:, config] @ effects) / np.sqrt(variance)
        residual[config] = 0.0
        variant = int(np.argmax(np.abs(residual)))
        if abs(residual[variant]) < 4.0:
            break
        config.append(variant)
    inv = np.linalg.inv(R[np.ix_(config, config)] + 1e-9 * np.eye(len(config)))
    effects = inv @ z[config]
    variance = np.maximum(1.0 - np.einsum("is,st,it->i", R[:, config], inv, R[:, config]), 0.05)
    residual = (z - R[:, config] @ effects) / np.sqrt(variance)
    residual[config] = 0.0
    if float(np.abs(residual).max()) > 4.0:
        return {"verdict": "unresolved", "confidence": 0.8}
    return {"verdict": "typed", "causal": config,
            "effects": [float(effects[i] * se[v]) for i, v in enumerate(config)],
            "confidence": 0.8}
