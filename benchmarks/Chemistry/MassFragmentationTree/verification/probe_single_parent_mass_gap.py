"""Shortcut probe: cluster every raw peak and choose one locally matching parent."""
from __future__ import annotations


def recover_fragmentation_tree(problem, acquire, zoom, budget_units):
    del zoom, budget_units
    tolerance = float(problem["mass_tolerance_da"])
    precursor = float(problem["precursor_mz"])
    spectra = [acquire(energy) for energy in (18.0, 35.0, 52.0)]

    raw = sorted(float(peak["mz"])
                 for spectrum in spectra for peak in spectrum["peaks"])
    groups = []
    for mz in raw:
        if groups and mz - groups[-1][-1] <= 2.0 * tolerance:
            groups[-1].append(mz)
        else:
            groups.append([mz])
    nodes = [sum(group) / len(group) for group in groups]

    root_seen = any(abs(node - precursor) <= 2.0 * tolerance for node in nodes)
    nearby_root = any(2.0 * tolerance < abs(node - precursor) <= 1.5
                      for node in nodes)
    if not root_seen or nearby_root:
        return {"nodes": [], "edges": [], "abstain": True, "confidence": 0.7}

    losses = {name: float(spec["neutral_mass"])
              for name, spec in problem["loss_library"].items()}
    edges = []
    for child in sorted(nodes, reverse=True):
        options = []
        for parent in nodes:
            if parent <= child:
                continue
            for name, loss in losses.items():
                error = abs((parent - child) - loss)
                if error <= 3.0 * tolerance:
                    options.append((error, parent, name))
        if options:
            _, parent, name = min(options)
            edges.append([parent, child, name])
    return {"nodes": nodes, "edges": edges, "abstain": False,
            "confidence": 0.6}
