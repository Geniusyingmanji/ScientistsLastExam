"""Truth-blind reference for PTAHellingsDowns.

Fits four public spatial kernels to the pair table by least squares. Hellings-Downs is
claimed only when it is the unique best kernel by a margin; a monopole, dipole, or
uncorrelated process is refused. Bootstraps are unused leftover headroom.
"""
from __future__ import annotations

import math


def _orf_hd(theta):
    x = 0.5 * (1.0 - math.cos(theta))
    x = min(1.0, max(x, 1e-15))
    return 0.5 - 0.25 * x + 1.5 * x * math.log(x)


def interpret_correlations(problem, bootstrap):
    del bootstrap
    theta = [float(t) for t in problem["theta_rad"]]
    rho = [float(r) for r in problem["rho"]]
    templates = {
        "hellings_downs": [_orf_hd(t) for t in theta],
        "monopole": [1.0] * len(theta),
        "dipole": [math.cos(t) for t in theta],
        "uncorrelated": [0.0] * len(theta),
    }
    sse = {}
    for name, pred in templates.items():
        sse[name] = sum((a - b) ** 2 for a, b in zip(rho, pred))
    ranked = sorted(sse, key=lambda k: sse[k])
    best, second = ranked[0], ranked[1]
    if best != "hellings_downs" or sse[second] < sse[best] * 1.15 + 0.02:
        return {"abstain": True, "confidence": 0.8}
    return {
        "abstain": False,
        "kernel": "hellings_downs",
        "confidence": 0.9,
    }
