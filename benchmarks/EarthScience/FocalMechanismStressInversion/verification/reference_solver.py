"""Truth-blind reference witness: Michael linear inversion with plane iteration.

Uses only the public catalog and the charged re-analysis budget. Alternates a
least-squares deviatoric-stress fit (shear traction projected onto the chosen planes)
with per-event nodal-plane swaps that reduce misfit; after a first pass it re-analyzes
the worst-misfit events within budget and refits. A bimodal or flat misfit tail
declares a mixed or incoherent catalog and refuses. It is a method witness, not
independent verification; it deliberately lacks bootstrapped confidence intervals,
gridded global search over the four-dimensional stress space, and multi-regime
clustering.
"""

from __future__ import annotations

import math

import numpy as np

MISFIT_TAIL_DEG = 35.0
MEAN_MISFIT_DEG = 18.0
TAIL_FRACTION = 0.18


def _normal_from_plane(strike, dip):
    tr, dp = math.radians(strike), math.radians(dip)
    return np.asarray((-math.sin(dp) * math.sin(tr),
                       -math.sin(dp) * math.cos(tr), math.cos(dp)))


def _slip_from_plane(strike, dip, rake):
    tr, dp, lam = math.radians(strike), math.radians(dip), math.radians(rake)
    return (math.cos(lam) * np.asarray((math.cos(tr), -math.sin(tr), 0.0))
            + math.sin(lam) * np.asarray((math.cos(dp) * math.sin(tr),
                                          math.cos(dp) * math.cos(tr), math.sin(dp))))


def _shear(tensor, normal):
    traction = tensor @ normal
    shear = traction - (traction @ normal) * normal
    magnitude = float(np.linalg.norm(shear))
    return shear / magnitude if magnitude > 1e-12 else shear


def _misfit_deg(tensor, normal, slip):
    shear = _shear(tensor, normal)
    norm = float(np.linalg.norm(shear))
    if norm < 1e-9:
        return 90.0
    cosine = float(np.clip(shear @ slip / norm, -1.0, 1.0))
    return math.degrees(math.acos(abs(cosine)))


def _solve_tensor(planes):
    """Weighted least squares on shear-parallel-to-slip for fixed plane choices."""
    matrix, target = [], []
    for normal, slip in planes:
        rows = np.zeros((3, 5))
        rows[0] = [normal[0], 0.0, normal[1], normal[2], 0.0]
        rows[1] = [0.0, normal[1], normal[0], 0.0, normal[2]]
        rows[2] = [-normal[2], -normal[2], 0.0, normal[0], normal[1]]
        projector = np.eye(3) - np.outer(normal, normal)
        matrix.append(projector @ rows)
        target.append(projector @ slip)
    matrix = np.vstack(matrix)
    target = np.concatenate(target)
    solution = np.linalg.lstsq(matrix, target, rcond=None)[0]
    return np.asarray([
        [solution[0], solution[2], solution[3]],
        [solution[2], solution[1], solution[4]],
        [solution[3], solution[4], -solution[0] - solution[1]]])


def _axes_and_ratio(tensor):
    eigenvalues, eigenvectors = np.linalg.eigh(tensor)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    sigma1 = eigenvectors[:, order[0]]
    sigma3 = eigenvectors[:, order[2]]
    span = eigenvalues[0] - eigenvalues[2]
    ratio = float(np.clip((eigenvalues[0] - eigenvalues[1]) / span, 0.0, 1.0)) \
        if span > 1e-12 else 0.5
    return sigma1, sigma3, ratio


def _angles(axis):
    norm = np.linalg.norm(axis)
    plunge = math.degrees(math.asin(max(-1.0, min(1.0, axis[2] / norm))))
    trend = math.degrees(math.atan2(axis[1], axis[0])) % 360.0
    return [float(trend), float(plunge)]


def _fit(events, choice):
    planes = [(normal, slip) for (normal, slip), pick in zip(events, choice)]
    tensor = _solve_tensor(planes)
    misfits = [_misfit_deg(tensor, normal, slip) for normal, slip in events]
    return tensor, misfits


def infer_stress_orientation(problem, reanalyze, budget_units):
    events = []
    for event in problem["events"]:
        events.append((_normal_from_plane(*event["plane_a"][:2]),
                       _slip_from_plane(*event["plane_a"]),
                       _normal_from_plane(*event["plane_b"][:2]),
                       _slip_from_plane(*event["plane_b"]),
                       event["id"]))

    rng = np.random.default_rng(1234)
    starts = [[0] * len(events), [1] * len(events)]
    for _ in range(6):
        starts.append([int(v) for v in rng.integers(0, 2, size=len(events))])

    def planes_for(choice):
        return [((normal_a if pick == 0 else normal_b),
                 (slip_a if pick == 0 else slip_b))
                for (normal_a, slip_a, normal_b, slip_b, _), pick
                in zip(events, choice)]

    def converge(choice, rounds):
        tensor, misfits = _fit(planes_for(choice), choice)
        for _ in range(rounds):
            changed = 0
            for index, (normal_a, slip_a, normal_b, slip_b, _) in enumerate(events):
                misfit_a = _misfit_deg(tensor, normal_a, slip_a)
                misfit_b = _misfit_deg(tensor, normal_b, slip_b)
                better = 0 if misfit_a <= misfit_b else 1
                if better != choice[index]:
                    choice[index] = better
                    changed += 1
            tensor, misfits = _fit(planes_for(choice), choice)
            if not changed:
                break
        return tensor, misfits

    best_choice, best_tensor, best_misfits = None, None, None
    for start in starts:
        choice = list(start)
        tensor, misfits = converge(choice, 8)
        if best_misfits is None or float(np.mean(misfits)) < float(np.mean(best_misfits)):
            best_choice, best_tensor, best_misfits = list(choice), tensor, misfits
    choice, tensor, misfits = list(best_choice), best_tensor, best_misfits

    # Spend the re-analysis budget on the worst-misfit events, then refit once.
    worst = sorted(range(len(events)), key=lambda i: -misfits[i])[:int(budget_units)]
    for index in worst:
        refreshed = reanalyze(events[index][4])
        events[index] = (
            _normal_from_plane(*refreshed["plane_a"][:2]),
            _slip_from_plane(*refreshed["plane_a"]),
            _normal_from_plane(*refreshed["plane_b"][:2]),
            _slip_from_plane(*refreshed["plane_b"]),
            events[index][4])
    tensor, misfits = converge(choice, 4)

    mean_misfit = float(np.mean(misfits))
    tail = float(np.mean([m > MISFIT_TAIL_DEG for m in misfits]))
    if mean_misfit > MEAN_MISFIT_DEG or tail > TAIL_FRACTION:
        return {"sigma1": None, "sigma3": None, "R": None,
                "plane_assignments": None, "abstain": True, "confidence": 0.8}

    sigma1, sigma3, ratio = _axes_and_ratio(tensor)
    return {
        "sigma1": _angles(sigma1), "sigma3": _angles(sigma3), "R": ratio,
        "plane_assignments": list(choice), "abstain": False, "confidence": 0.75,
    }
