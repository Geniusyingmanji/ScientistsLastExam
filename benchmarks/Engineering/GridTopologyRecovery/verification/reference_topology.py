"""Truth-blind residual ranking over the public catalog."""
from __future__ import annotations

import numpy as np


def _angles(edges, injection, n_bus=5, slack=0):
    admittance = np.zeros((n_bus, n_bus), dtype=float)
    for i, j in edges:
        b = 4.0
        admittance[i, j] -= b
        admittance[j, i] -= b
        admittance[i, i] += b
        admittance[j, j] += b
    theta = np.zeros(n_bus, dtype=float)
    mask = [index for index in range(n_bus) if index != slack]
    reduced = admittance[np.ix_(mask, mask)]
    theta[mask] = np.linalg.solve(reduced, np.asarray(injection, dtype=float)[mask])
    return theta


def recover_topology(problem, measure):
    names = list(problem["catalog_names"])
    catalog = {
        name: tuple(tuple(edge) for edge in problem["catalog_edges"][name])
        for name in names
    }
    injections = [np.asarray(row, dtype=float) for row in problem["injection_patterns"]]
    n_bus = int(problem["bus_count"])
    slack = int(problem["slack_bus"])
    _ = problem["measure_budget_calls"]
    _ = problem["measurement_model"]
    _ = problem["abstain_when"]
    observed = {}
    for pattern in (0, 1):
        for bus in range(n_bus):
            if bus == slack:
                continue
            observed[(pattern, bus)] = float(measure(pattern, bus))

    residuals = []
    for name in names:
        err = 0.0
        for pattern, injection in enumerate(injections):
            theta = _angles(catalog[name], injection, n_bus=n_bus, slack=slack)
            for bus in range(n_bus):
                if bus == slack:
                    continue
                err += (theta[bus] - observed[(pattern, bus)]) ** 2
        residuals.append((err, name))
    residuals.sort()
    best, second = residuals[0][0], residuals[1][0]
    if second < 8.0 * max(best, 1e-12) or abs(second - best) < 5e-4:
        return {"abstain": True, "confidence": 0.82}
    return {"abstain": False, "catalog_name": residuals[0][1], "confidence": 0.76}
