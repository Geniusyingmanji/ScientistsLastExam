"""Standalone input-only classical reference; no world generator or truth."""

from copy import deepcopy

from functools import lru_cache

import numpy as np

from scipy.optimize import least_squares

from scipy.sparse.csgraph import shortest_path

def residuals(problem, xyz):
    xyz = np.asarray(xyz).reshape(-1, 3)
    parts = {k: [] for k in problem["loss_weights"]}
    for key, rows in (("bonds", problem["bonds"]), ("distances", problem["distance_restraints"])):
        for row in rows:
            i, j = row["atoms"]; low, high = row["bounds"]
            d = np.linalg.norm(xyz[i]-xyz[j])
            parts[key].append(max(low-d, 0., d-high))
    for row in problem["angle_bounds"]:
        i, j, k = row["atoms"]
        a, b = xyz[i]-xyz[j], xyz[k]-xyz[j]
        denom = np.linalg.norm(a)*np.linalg.norm(b)
        cosine = float(a@b/max(denom, 1e-12))
        low, high = row["cosine_bounds"]
        parts["angles"].append(max(low-cosine, 0., cosine-high))
    for i in range(len(xyz)):
        for j in range(i+3, len(xyz)):
            parts["sterics"].append(max(0., problem["excluded_volume_radii"][i]+problem["excluded_volume_radii"][j]-np.linalg.norm(xyz[i]-xyz[j])))
    for row in problem["stereocenters"]:
        i, j, k, l = row["atoms"]
        volume = np.dot(xyz[j]-xyz[i], np.cross(xyz[k]-xyz[i], xyz[l]-xyz[i]))/3.8**3
        parts["chirality"].append(max(0., row["minimum_volume"]-row["sign"]*volume))
    return np.concatenate([np.asarray(parts[key])*np.sqrt(weight/max(1, len(parts[key])))
                           for key, weight in problem["loss_weights"].items()])

def loss(problem, xyz):
    r = residuals(problem, xyz)
    return float(r@r)

def reference(problem, max_nfev=45):
    n = len(problem["atom_ids"])
    distances = np.full((n, n), np.inf); np.fill_diagonal(distances, 0.)
    for row in problem["bonds"]+problem["distance_restraints"]:
        i, j = row["atoms"]; distances[i, j] = distances[j, i] = np.mean(row["bounds"])
    distances = shortest_path(distances, directed=False)
    center = np.eye(n)-np.ones((n, n))/n
    gram = -.5*center@(distances**2)@center
    values, vectors = np.linalg.eigh(gram)
    xyz = vectors[:, -3:]*np.sqrt(np.maximum(values[-3:], 0))
    reflected = xyz.copy(); reflected[:, 0] *= -1
    if loss(problem, reflected) < loss(problem, xyz):
        xyz = reflected
    fit = least_squares(lambda flat: residuals(problem, flat), xyz.ravel(), max_nfev=max_nfev,
                        ftol=1e-6, xtol=1e-6, gtol=1e-6)
    result = fit.x.reshape(-1, 3); result -= result.mean(axis=0)
    return {"coordinates": result.tolist()}

def build_conformation(problem):
    return reference(problem, max_nfev=120)
