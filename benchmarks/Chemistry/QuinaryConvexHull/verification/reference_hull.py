"""Truth-blind reference for QuinaryConvexHull.

Reserves replicate calls to test whether energies reproduce, then relaxes the public catalog
and keeps only non-unary vertices of the lower convex envelope. E_f < 0 is not the stable set.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import ConvexHull


def recover_hull(problem, relax):
    catalog = list(problem["catalog"])
    n_atoms = int(problem["n_atoms"])
    elements = list(problem["elements"])
    budget = int(problem["relax_budget_calls"])

    def composition(name):
        counts = []
        rest = name
        for el in elements:
            if not rest.startswith(el):
                raise ValueError(name)
            rest = rest[len(el):]
            digits = ""
            while rest and rest[0].isdigit():
                digits += rest[0]
                rest = rest[1:]
            counts.append(int(digits))
        return np.array(counts, dtype=float) / float(n_atoms)

    unaries = []
    others = []
    for name in catalog:
        x = composition(name)
        if float(np.max(x)) >= 1.0 - 1e-12:
            unaries.append(name)
        else:
            others.append(name)

    energies = {}
    calls = 0
    reserved = 4

    def take(name):
        nonlocal calls
        if name in energies or calls + reserved >= budget:
            return
        energies[name] = float(relax(name))
        calls += 1

    for name in unaries + others:
        take(name)

    replicates = []
    probe = (others[:2] + unaries[:2])[:4]
    for name in probe:
        if calls >= budget or name not in energies:
            break
        replicates.append(abs(float(relax(name)) - energies[name]))
        calls += 1
    if replicates and max(replicates) > 0.018:
        return {"abstain": True, "confidence": 0.85}

    names = [name for name in catalog if name in energies]
    if len(names) < 8:
        return {"abstain": True, "confidence": 0.3}
    comps = np.vstack([composition(name) for name in names])
    evec = np.array([energies[name] for name in names], dtype=float)
    # HiGHS initializes a native worker pool even in nominal single-thread mode, while the
    # candidate sandbox correctly forbids clone(). Qhull computes the same finite lower envelope
    # in-process: lower facets have a negative coefficient on the energy coordinate.
    points = np.column_stack([comps[:, :4], evec])
    hull = ConvexHull(points)
    lower_facets = hull.simplices[hull.equations[:, -2] < -1e-10]
    lower_vertices = set(int(index) for index in lower_facets.ravel())
    claimed = [
        name for i, name in enumerate(names)
        if i in lower_vertices and name not in unaries
    ]
    return {
        "abstain": False,
        "stable": claimed,
        "confidence": 0.88,
    }
