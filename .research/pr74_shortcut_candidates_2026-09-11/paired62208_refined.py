"""Standalone stress-grid red team using public observations only.

RAW matches the ordinary four-dimensional nodal-plane angular-search family.
PAIRED additionally averages public double-couple observations, fuses repeated
measurements and spends re-analysis on ambiguous events. Its stronger results
must also be disclosed. Neither variant imports the reference or evaluator.
"""
import itertools
import numpy as np

GRID_SHAPE = (12, 8, 12, 6)
PAIRED = False
QUERY_POLICY = "first"
SIGNED = True
LOCAL_ROUNDS = 0
THRESHOLD_DEG = 25.0
LAST_DIAGNOSTICS = {}


def plane_geometry(plane):
    strike, dip, rake = np.deg2rad(plane)
    n = np.array([-np.sin(dip) * np.sin(strike), -np.sin(dip) * np.cos(strike), np.cos(dip)])
    s = (np.cos(rake) * np.array([np.cos(strike), -np.sin(strike), 0.0])
         + np.sin(rake) * np.array([np.cos(dip) * np.sin(strike),
                                    np.cos(dip) * np.cos(strike), np.sin(dip)]))
    return n, s


def read_planes(events):
    pairs = np.array([[plane_geometry(event[key]) for key in ("plane_a", "plane_b")]
                      for event in events])
    return pairs[:, :, 0], pairs[:, :, 1]


def moment_mean(events):
    n, s = read_planes(events)
    return (n[:, :, :, None] * s[:, :, None, :] + s[:, :, :, None] * n[:, :, None, :]).mean(axis=1)


def denoised_planes(moments, events):
    _, eig = np.linalg.eigh(moments)
    directions = np.stack([(eig[:, :, 2] + eig[:, :, 0]) / np.sqrt(2),
                           (eig[:, :, 2] - eig[:, :, 0]) / np.sqrt(2)], axis=1)
    observed, _ = read_planes(events)
    result_n, result_s = [], []
    for i in range(len(events)):
        a, b = directions[i]
        if abs(a @ observed[i, 0]) < abs(b @ observed[i, 0]):
            a, b = b, a
        normals, slips = np.array([a, b]), np.array([b, a])
        for j in (0, 1):
            if normals[j] @ observed[i, j] < 0:
                normals[j] *= -1
                slips[j] *= -1
        result_n.append(normals)
        result_s.append(slips)
    return np.array(result_n), np.array(result_s)


def tensors_from_points(points):
    t, p, a = np.deg2rad(points[:, :3]).T
    axis1 = np.array([np.cos(p) * np.cos(t), np.cos(p) * np.sin(t), np.sin(p)]).T
    perpendicular = np.array([-np.sin(t), np.cos(t), np.zeros_like(t)]).T
    axis3 = np.cos(a)[:, None] * perpendicular + np.sin(a)[:, None] * np.cross(axis1, perpendicular)
    axis2 = np.cross(axis3, axis1)
    tensors = np.einsum("gi,gj->gij", axis1, axis1)
    tensors += (1 - points[:, 3])[:, None, None] * np.einsum("gi,gj->gij", axis2, axis2)
    return tensors, axis1, axis3


def angular_errors(tensors, normals, slips):
    traction = np.einsum("gij,epj->gepi", tensors, normals)
    tangential = traction - np.sum(traction * normals[None], axis=-1)[..., None] * normals[None]
    cosine = np.sum(tangential * slips[None], axis=-1) / np.maximum(np.linalg.norm(tangential, axis=-1), 1e-12)
    if not SIGNED:
        cosine = np.abs(cosine)
    return np.degrees(np.arccos(np.clip(cosine, -1, 1)))


def infer_stress_orientation(problem, reanalyze, budget_units):
    global LAST_DIAGNOSTICS
    original_events = list(problem["events"])
    events = [dict(event) for event in sorted(original_events, key=lambda event: event["id"])]
    coarse = float(problem["noise_sigma_deg"])
    fine = float(problem["reanalysis_sigma_deg"])
    uncertainty = np.full(len(events), coarse)
    moments = moment_mean(events)
    grid = np.array(list(itertools.product(
        np.linspace(0, 360, GRID_SHAPE[0], endpoint=False), np.linspace(0, 90, GRID_SHAPE[1]),
        np.linspace(0, 180, GRID_SHAPE[2], endpoint=False), np.linspace(.05, .95, GRID_SHAPE[3]))))

    def fit():
        normals, slips = denoised_planes(moments, events) if PAIRED else read_planes(events)
        weights = (coarse / uncertainty) ** 2

        def search(points):
            best = (float("inf"), None, None)
            for begin in range(0, len(points), 256):
                batch = points[begin:begin + 256]
                angles = angular_errors(tensors_from_points(batch)[0], normals, slips)
                minimum = angles.min(axis=2)
                objective = np.mean(minimum ** 2 * weights[None], axis=1) if PAIRED else minimum.mean(axis=1)
                index = int(np.argmin(objective))
                if objective[index] < best[0]:
                    best = (float(objective[index]), batch[index].copy(), angles[index])
            return best

        best = search(grid)
        step = np.array([360 / GRID_SHAPE[0], 90 / (GRID_SHAPE[1] - 1),
                         180 / GRID_SHAPE[2], .9 / (GRID_SHAPE[3] - 1)])
        offsets = np.array(list(itertools.product((-1, 0, 1), repeat=4)))
        for _ in range(LOCAL_ROUNDS):
            step *= .5
            points = best[1] + offsets * step
            points[:, 1] = np.clip(points[:, 1], -90, 90)
            points[:, 3] = np.clip(points[:, 3], 0, 1)
            proposal = search(points)
            if proposal[0] < best[0]:
                best = proposal
        return best[1], best[2]

    count = min(int(budget_units), len(events))
    if QUERY_POLICY == "first":
        indices = np.arange(count)
    else:
        _, angles = fit()
        if QUERY_POLICY == "worst":
            priority = -angles.min(axis=1)
        elif QUERY_POLICY == "ambiguous":
            priority = np.abs(angles[:, 0] - angles[:, 1])
        else:
            raise ValueError("unknown query policy")
        indices = np.argsort(priority, kind="stable")[:count]
    queried = []
    for i in indices:
        update = dict(reanalyze(events[i]["id"]))
        precision = 1 / coarse ** 2 + 1 / fine ** 2
        moments[i] = (moments[i] / coarse ** 2 + moment_mean([update])[0] / fine ** 2) / precision
        uncertainty[i] = precision ** -.5
        events[i] = update
        queried.append(update["id"])
    points, angles = fit()
    mean = float(angles.min(axis=1).mean())
    LAST_DIAGNOSTICS = {"mean_residual_deg": mean, "queried_ids": queried,
                        "parameters": points.tolist(), "angles_deg": angles.tolist()}
    if mean > THRESHOLD_DEG:
        return {"sigma1": None, "sigma3": None, "R": None, "plane_assignments": None,
                "abstain": True, "confidence": .1}
    _, one, three = tensors_from_points(points[None])

    def axis(v):
        return [float(np.degrees(np.arctan2(v[1], v[0])) % 360) % 360.0,
                float(np.degrees(np.arcsin(np.clip(v[2], -1, 1))))]

    choices = {e["id"]: int(pick) for e, pick in zip(events, angles.argmin(axis=1))}
    return {"sigma1": axis(one[0]), "sigma3": axis(three[0]), "R": float(points[3]),
            "plane_assignments": [choices[e["id"]] for e in original_events],
            "abstain": False, "confidence": .75}

# Frozen published paired62208_refined configuration; no parameter search.
GRID_SHAPE = (24, 12, 24, 9)
PAIRED = True
QUERY_POLICY = "ambiguous"
SIGNED = True
LOCAL_ROUNDS = 3
THRESHOLD_DEG = 25.0
