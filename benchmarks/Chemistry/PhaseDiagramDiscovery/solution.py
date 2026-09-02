"""Weak but valid baseline for PhaseDiagramDiscovery.

It does what the instrument invites: synthesize a uniform grid, call every distinct-looking
pattern a phase, and draw boundaries at the midpoints between grid points. It never decomposes a
pattern as a mixture, so every two-phase field becomes a "new compound"; it never replicates, so
impurity peaks enter signatures; and it never declines, so a trapped system gets published as an
equilibrium diagram.
"""
from __future__ import annotations


def _strong_peaks(pattern, floor=0.15):
    return sorted(p["two_theta"] for p in pattern if p["intensity"] >= floor)


def _same(peaks_a, peaks_b, tol=0.5):
    if not peaks_a or not peaks_b:
        return not peaks_a and not peaks_b
    hits = sum(1 for a in peaks_a if any(abs(a - b) <= tol for b in peaks_b))
    return hits >= 0.7 * max(len(peaks_a), len(peaks_b))


def discover_phases(problem, synthesize):
    budget = int(problem["synthesis_budget_calls"])
    count = min(13, budget)
    grid = [i / (count - 1) for i in range(count)]
    patterns = []
    for x in grid:
        try:
            patterns.append((x, _strong_peaks(synthesize(x))))
        except Exception:
            break
    if not patterns:
        return {"abstain": True, "confidence": 0.0}
    clusters = [[patterns[0]]]
    for x, peaks in patterns[1:]:
        if _same(peaks, clusters[-1][-1][1]):
            clusters[-1].append((x, peaks))
        else:
            clusters.append([(x, peaks)])
    phases = []
    for index, cluster in enumerate(clusters):
        xs = [x for x, _peaks in cluster]
        lo = 0.0 if index == 0 else (clusters[index - 1][-1][0] + xs[0]) / 2.0
        hi = 1.0 if index == len(clusters) - 1 else (xs[-1] + clusters[index + 1][0][0]) / 2.0
        peaks = sorted(set(round(p, 1) for _x, pk in cluster for p in pk))[:12]
        if peaks:
            phases.append({"composition_range": [lo, hi], "peak_two_thetas": peaks})
    if not phases:
        return {"abstain": True, "confidence": 0.0}
    return {"phases": phases[:6], "confidence": 0.9, "abstain": False}
