"""Coarse C-alpha geometry; evaluates public constraints, never hidden RMSD."""
from copy import deepcopy
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse.csgraph import shortest_path


def _world(index):
    rng = np.random.default_rng(45810 + index)
    n = 24+4*index
    theta = np.cumsum(rng.uniform(1.55, 1.85, n))
    raw = np.column_stack([2.3*np.cos(theta), 2.3*np.sin(theta), np.arange(n)*1.5])
    # Slowly bend the helical axis; normalize each C-alpha step to 3.8 A.
    raw[:, 0] += 5*np.sin(np.arange(n)/7)
    delta = np.diff(raw, axis=0); delta *= 3.8/np.linalg.norm(delta, axis=1)[:, None]
    xyz = np.vstack([np.zeros(3), np.cumsum(delta, axis=0)])
    xyz -= xyz.mean(axis=0)
    bonds = [dict(atoms=[i, i+1], bounds=[3.76, 3.84]) for i in range(n-1)]
    angles, centers = [], []
    for i in range(n-2):
        a, b = xyz[i]-xyz[i+1], xyz[i+2]-xyz[i+1]
        cosine = float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))
        angles.append(dict(atoms=[i, i+1, i+2], cosine_bounds=[max(-1., cosine-.06), min(1., cosine+.06)]))
    for i in range(n-3):
        volume = float(np.linalg.det(xyz[i+1:i+4]-xyz[i])/3.8**3)
        if abs(volume) > .08:
            centers.append(dict(atoms=list(range(i, i+4)), sign=1 if volume > 0 else -1, minimum_volume=abs(volume)*.65))
    pairs = [(i, j) for i in range(n) for j in range(i+3, n)]
    chosen = rng.choice(len(pairs), n*2, replace=False)
    restraints = []
    for k in sorted(chosen):
        i, j = pairs[k]; d = float(np.linalg.norm(xyz[i]-xyz[j]))
        restraints.append(dict(atoms=[i, j], bounds=[d-.3, d+.3]))
    return dict(atom_ids=[f"CA{i}" for i in range(n)], representation="synthetic_C_alpha_backbone",
                bonds=bonds, angle_bounds=angles, stereocenters=centers, distance_restraints=restraints,
                excluded_volume_radii=[1.2]*n, coordinate_bounds=[-250., 250.],
                loss_weights=dict(bonds=4., angles=2., distances=1., sterics=4., chirality=2.)), xyz


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


def baseline(problem):
    n = len(problem["atom_ids"])
    return {"coordinates": np.column_stack([3.8*(np.arange(n)-(n-1)/2), np.zeros((n, 2))]).tolist()}


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


def _score_output(index, problem, output):
    if not isinstance(output, dict) or set(output) != {"coordinates"}:
        return 0., False
    coords = output["coordinates"]
    if not isinstance(coords, list) or len(coords) != len(problem["atom_ids"]):
        return 0., False
    for row in coords:
        if not isinstance(row, list) or len(row) != 3 or any(type(v) not in (int, float) or not np.isfinite(v) or not -250 <= v <= 250 for v in row):
            return 0., False
    if coords == baseline(problem)["coordinates"]:
        return 0., True
    base = loss(problem, baseline(problem)["coordinates"])
    quality = 1/(1+loss(problem, coords)/0.2)
    floor = 1/(1+base/0.2)
    return float(np.clip((quality-floor)/(1-floor), 0, 1)), True


def evaluate(build_conformation):
    rows = []
    for index in range(4):
        p, _ = _world(index)
        try:
            out = build_conformation(deepcopy(p))
            score, valid = _score_output(index, p, out)
            raw = loss(p, out["coordinates"]) if valid else 0.
        except Exception:
            score, valid, raw = 0., False, 0.
        rows.append(dict(score=score, valid=valid, constraint_loss=raw))
    return dict(combined_score=float(np.mean([r["score"] for r in rows[:2]])), valid=float(all(r["valid"] for r in rows)),
                heldout_score=float(np.mean([r["score"] for r in rows[2:]])), per_instance=rows)
