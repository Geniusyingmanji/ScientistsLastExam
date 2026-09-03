"""Weak but valid baseline for HiddenCouplingNetwork.

It does what the equation invites at first sight: treat the steady-state relation as a linear
system in x, drive the network with random patterns, and solve for every coefficient at once by
least squares. With fewer experiments than units the system is underdetermined, the minimum-norm
solution smears each true coupling over many units, and the nonlinearity it ignored shows up as
extra small coefficients - so it publishes a dense, mostly wrong graph. It never declines, so a
network with unmeasured units gets published too.
"""
from __future__ import annotations

import numpy as np


def discover_couplings(problem, run_experiment):
    n = int(problem["units"])
    budget = int(problem["experiment_budget"])
    amplitude = float(problem["drive_bound"])
    rng = np.random.default_rng(0)
    drives, states = [], []
    for _ in range(budget):
        u = amplitude * rng.choice([-1.0, 0.0, 1.0], size=n)
        try:
            states.append(np.asarray(run_experiment(u), dtype=float))
        except Exception:
            break
        drives.append(u)
    if not states:
        return {"edges": [], "abstain": False, "confidence": 0.5}
    U, X = np.asarray(drives), np.asarray(states)
    edges = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        design = np.column_stack([X[:, others], U[:, i]])          # linear in x, not tanh(x)
        beta = np.linalg.lstsq(design, X[:, i], rcond=None)[0]      # underdetermined: min-norm
        for column, coefficient in zip(others, beta[:-1]):
            if abs(coefficient) > 0.1:
                edges.append([int(column), int(i), 1.0 if coefficient > 0 else -1.0])
    return {"edges": edges[: 4 * n], "abstain": False, "confidence": 0.9}
