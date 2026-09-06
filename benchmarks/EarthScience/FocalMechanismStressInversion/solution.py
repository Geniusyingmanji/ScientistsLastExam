"""Weak valid baseline: assumes every event slipped on its first-listed plane and fits
one stress tensor by unweighted least squares without any plane iteration, budget use
or regime check. It confidently reports a tensor on mixture and noise worlds too.
"""

from __future__ import annotations

import numpy as np


def _normal_from_plane(strike, dip):
    tr, dp = np.radians(strike), np.radians(dip)
    return np.asarray((-np.sin(dp) * np.sin(tr), -np.sin(dp) * np.cos(tr), np.cos(dp)))


def _slip_from_plane(strike, dip, rake):
    tr, dp, lam = np.radians(strike), np.radians(dip), np.radians(rake)
    return (np.cos(lam) * np.asarray((np.cos(tr), -np.sin(tr), 0.0))
            + np.sin(lam) * np.asarray((np.cos(dp) * np.sin(tr),
                                        np.cos(dp) * np.cos(tr), np.sin(dp))))


def infer_stress_orientation(problem, reanalyze, budget_units):
    del reanalyze, budget_units
    design_rows, slip_rows = [], []
    for event in problem["events"]:
        design_rows.append(_normal_from_plane(*event["plane_a"][:2]))
        slip_rows.append(_slip_from_plane(*event["plane_a"]))
    normals = np.asarray(design_rows)
    slips = np.asarray(slip_rows)
    # Unweighted Michael inversion on fixed (first-listed) planes.
    matrix = np.zeros((3 * len(normals), 5))
    target = np.zeros(3 * len(normals))
    for index, (normal, slip) in enumerate(zip(normals, slips)):
        # Shear of the deviatoric tensor parameterized by (s1, s2, s3, s4, s5).
        rows = np.zeros((3, 5))
        rows[0, 0] = normal[0]
        rows[0, 2] = normal[1]
        rows[0, 3] = normal[2]
        rows[1, 2] = normal[0]
        rows[1, 1] = normal[1]
        rows[1, 4] = normal[2]
        rows[2, 3] = normal[0]
        rows[2, 4] = normal[1]
        rows[2, 0] = -normal[2]
        rows[2, 1] = -normal[2]
        matrix[3 * index:3 * index + 3] = rows
        target[3 * index:3 * index + 3] = slip  # slip is already in-plane
    solution = np.linalg.lstsq(matrix, target, rcond=None)[0]
    tensor = np.asarray([
        [solution[0], solution[2], solution[3]],
        [solution[2], solution[1], solution[4]],
        [solution[3], solution[4], -solution[0] - solution[1]]])
    eigenvalues, eigenvectors = np.linalg.eigh(tensor)
    sigma1 = eigenvectors[:, np.argmax(eigenvalues)]
    sigma3 = eigenvectors[:, np.argmin(eigenvalues)]
    ordered = np.sort(eigenvalues)[::-1]
    span = ordered[0] - ordered[2]
    ratio = float(np.clip((ordered[0] - ordered[1]) / span, 0.0, 1.0)) if span > 1e-12 else 0.5

    def angles(axis):
        plunge = np.degrees(np.arcsin(np.clip(axis[2] / np.linalg.norm(axis), -1, 1)))
        trend = np.degrees(np.arctan2(axis[1], axis[0])) % 360.0
        return [float(trend), float(plunge)]

    return {
        "sigma1": angles(sigma1), "sigma3": angles(sigma3), "R": ratio,
        "plane_assignments": [0] * problem["event_count"],
        "abstain": False, "confidence": 0.8,
    }
