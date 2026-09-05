"""Deterministic classical-laminate oracle for stacking-sequence design.

The public contract fixes the laminate composition.  Candidates choose only the ply order.  The
trusted oracle assembles the extensional and bending matrices, evaluates a simply-supported
Navier buckling approximation and a Tsai-Hill first-ply reserve factor, then repeats the check
under sealed material and load shifts.  It is a screening model, not a certification analysis.
"""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
ANGLES = (-45, 0, 45, 90)
MAX_RUN = 3
_REFERENCE_CACHE = {}


INSTANCE_SPECS = (
    {"name": "dev_axial_long", "split": "development", "plies": 16, "half_counts": (2, 2, 2, 2),
     "a": 1.20, "b": 0.72, "loads": ((2.4e5, 0.55e5, 0.15e5), (1.8e5, 1.15e5, -0.22e5)),
     "material": (132e9, 9.2e9, 4.8e9, 0.29), "strength": (1.45e9, 1.05e9, 55e6, 185e6, 72e6)},
    {"name": "dev_biaxial_square", "split": "development", "plies": 20, "half_counts": (2, 3, 2, 3),
     "a": 0.92, "b": 0.92, "loads": ((1.65e5, 1.55e5, 0.28e5), (2.05e5, 0.75e5, -0.35e5)),
     "material": (145e9, 8.5e9, 5.2e9, 0.27), "strength": (1.60e9, 1.10e9, 48e6, 170e6, 68e6)},
    {"name": "dev_shear_panel", "split": "development", "plies": 24, "half_counts": (3, 3, 3, 3),
     "a": 1.05, "b": 0.66, "loads": ((1.25e5, 0.85e5, 0.62e5), (2.2e5, 0.35e5, -0.48e5)),
     "material": (126e9, 10.4e9, 5.0e9, 0.31), "strength": (1.35e9, 0.98e9, 62e6, 205e6, 78e6)},
    {"name": "dev_transverse", "split": "development", "plies": 16, "half_counts": (2, 2, 2, 2),
     "a": 0.78, "b": 1.18, "loads": ((0.45e5, 2.35e5, 0.18e5), (1.05e5, 1.72e5, -0.31e5)),
     "material": (138e9, 9.7e9, 4.5e9, 0.28), "strength": (1.52e9, 1.02e9, 58e6, 190e6, 70e6)},
    {"name": "heldout_orthotropic", "split": "heldout", "plies": 20, "half_counts": (2, 3, 2, 3),
     "a": 1.32, "b": 0.81, "loads": ((2.15e5, 0.82e5, 0.41e5), (1.40e5, 1.35e5, -0.25e5)),
     "material": (119e9, 11.2e9, 4.2e9, 0.30), "strength": (1.28e9, 0.92e9, 66e6, 215e6, 74e6)},
    {"name": "heldout_balanced_load", "split": "heldout", "plies": 24, "half_counts": (3, 3, 3, 3),
     "a": 0.86, "b": 1.04, "loads": ((1.55e5, 1.75e5, 0.36e5), (0.95e5, 2.10e5, -0.42e5)),
     "material": (151e9, 8.1e9, 5.5e9, 0.26), "strength": (1.70e9, 1.18e9, 45e6, 165e6, 65e6)},
)


def _problem(spec):
    counts = {str(a): int(c) * 2 for a, c in zip(ANGLES, spec["half_counts"])}
    e1, e2, g12, nu12 = spec["material"]
    xt, xc, yt, yc, s = spec["strength"]
    return {
        "ply_count": int(spec["plies"]), "allowed_angles_deg": list(ANGLES),
        "required_angle_counts": counts, "symmetric": True, "balanced": True,
        "maximum_consecutive_equal_plies": MAX_RUN, "ply_thickness_m": 0.000125,
        "panel_length_m": float(spec["a"]), "panel_width_m": float(spec["b"]),
        "load_cases_n_per_m": [list(row) for row in spec["loads"]],
        "material": {"e1_pa": e1, "e2_pa": e2, "g12_pa": g12, "nu12": nu12,
                     "xt_pa": xt, "xc_pa": xc, "yt_pa": yt, "yc_pa": yc, "s_pa": s},
        "model": "classical laminate A/D matrices; simply-supported Navier buckling modes 1..4; Tsai-Hill first-ply reserve",
    }


def _qbar(material, angle):
    e1, e2, g, nu12 = (float(material[k]) for k in ("e1_pa", "e2_pa", "g12_pa", "nu12"))
    nu21 = nu12 * e2 / e1
    d = 1.0 - nu12 * nu21
    q11, q22, q12, q66 = e1 / d, e2 / d, nu12 * e2 / d, g
    r = math.radians(angle); m, n = math.cos(r), math.sin(r)
    m2, n2, m4, n4 = m*m, n*n, m**4, n**4
    q16 = (q11-q12-2*q66)*m**3*n - (q22-q12-2*q66)*m*n**3
    q26 = (q11-q12-2*q66)*m*n**3 - (q22-q12-2*q66)*m**3*n
    return np.array([
        [q11*m4 + 2*(q12+2*q66)*m2*n2 + q22*n4,
         (q11+q22-4*q66)*m2*n2 + q12*(m4+n4), q16],
        [(q11+q22-4*q66)*m2*n2 + q12*(m4+n4),
         q11*n4 + 2*(q12+2*q66)*m2*n2 + q22*m4, q26],
        [q16, q26, (q11+q22-2*q12-2*q66)*m2*n2 + q66*(m4+n4)],
    ], dtype=float)


def _laminate(problem, sequence, material=None, loads=None):
    material = material or problem["material"]
    loads = loads or problem["load_cases_n_per_m"]
    t = float(problem["ply_thickness_m"]); h = len(sequence) * t
    edges = np.linspace(-0.5*h, 0.5*h, len(sequence)+1)
    a_mat = np.zeros((3, 3)); d_mat = np.zeros((3, 3)); qbars = []
    for k, angle in enumerate(sequence):
        q = _qbar(material, angle); qbars.append(q)
        a_mat += q * (edges[k+1]-edges[k])
        d_mat += q * (edges[k+1]**3-edges[k]**3) / 3.0
    a, b = float(problem["panel_length_m"]), float(problem["panel_width_m"])
    reserve = float("inf")
    for nx, ny, nxy in loads:
        best = float("inf")
        for mx in range(1, 5):
            for my in range(1, 5):
                x, y = mx*math.pi/a, my*math.pi/b
                numerator = d_mat[0,0]*x**4 + 2*(d_mat[0,1]+2*d_mat[2,2])*x*x*y*y + d_mat[1,1]*y**4
                denominator = max(nx*x*x + ny*y*y + 2*abs(nxy)*x*y, 1e-12)
                best = min(best, numerator / denominator)
        strain = np.linalg.solve(a_mat, np.asarray([nx, ny, nxy], dtype=float))
        failure_index = 0.0
        for angle, q in zip(sequence, qbars):
            sx, sy, txy = q @ strain
            r = math.radians(angle); m, n = math.cos(r), math.sin(r)
            s1 = m*m*sx+n*n*sy+2*m*n*txy
            s2 = n*n*sx+m*m*sy-2*m*n*txy
            t12 = -m*n*sx+m*n*sy+(m*m-n*n)*txy
            xallow = material["xt_pa"] if s1 >= 0 else material["xc_pa"]
            yallow = material["yt_pa"] if s2 >= 0 else material["yc_pa"]
            idx = (s1/xallow)**2 - (s1*s2)/(xallow*xallow) + (s2/yallow)**2 + (t12/material["s_pa"])**2
            failure_index = max(failure_index, float(idx))
        first_ply = 1.0 / math.sqrt(max(failure_index, 1e-18))
        reserve = min(reserve, best, first_ply)
    return float(reserve)


def _validate(problem, value):
    if isinstance(value, dict):
        value = value.get("ply_angles_deg")
    if not isinstance(value, (list, tuple)) or len(value) != int(problem["ply_count"]):
        raise ValueError("return exactly ply_count angles")
    sequence = []
    for item in value:
        number = float(item)
        if not math.isfinite(number) or number not in ANGLES:
            raise ValueError("illegal ply angle")
        sequence.append(int(number))
    expected = {int(k): int(v) for k, v in problem["required_angle_counts"].items()}
    if {a: sequence.count(a) for a in ANGLES} != expected:
        raise ValueError("angle counts changed")
    if sequence != list(reversed(sequence)):
        raise ValueError("laminate must be symmetric")
    if sequence.count(45) != sequence.count(-45):
        raise ValueError("laminate must be balanced")
    if max(len(list(group)) for _, group in __import__("itertools").groupby(sequence)) > MAX_RUN:
        raise ValueError("too many consecutive equal plies")
    return sequence


def _baseline(problem):
    half = []
    counts = {int(k): int(v)//2 for k, v in problem["required_angle_counts"].items()}
    order = (0, 45, -45, 90)
    while sum(counts.values()):
        for angle in order:
            if counts[angle]: half.append(angle); counts[angle] -= 1
    return half + half[::-1]


def _reference(problem):
    key = (problem["ply_count"], problem["panel_length_m"], problem["panel_width_m"],
           tuple(tuple(x) for x in problem["load_cases_n_per_m"]),
           tuple(sorted(problem["material"].items())))
    if key in _REFERENCE_CACHE:
        return list(_REFERENCE_CACHE[key])
    base = _baseline(problem); half = base[:len(base)//2]
    rng = np.random.default_rng(41073 + len(base))
    best, best_q = base, _laminate(problem, base)
    for _ in range(900):
        trial_half = list(rng.permutation(half)); trial = trial_half + trial_half[::-1]
        try:
            trial = _validate(problem, trial)
        except ValueError:
            continue
        q = _laminate(problem, trial)
        if q > best_q: best, best_q = trial, q
    _REFERENCE_CACHE[key] = tuple(best)
    return list(best)


def _shifted_quality(problem, sequence):
    material = copy.deepcopy(problem["material"])
    material["e2_pa"] *= 0.90; material["g12_pa"] *= 0.88
    material["yt_pa"] *= 0.92; material["s_pa"] *= 0.90
    loads = [[1.12*x, 1.08*y, 1.20*z] for x, y, z in problem["load_cases_n_per_m"]]
    return _laminate(problem, sequence, material=material, loads=loads)


def _score_instance(candidate, spec):
    problem = _problem(spec)
    baseline = _baseline(problem); reference = _reference(problem)
    low, high = _laminate(problem, baseline), _laminate(problem, reference)
    try:
        sequence = _validate(problem, candidate(copy.deepcopy(problem)))
        quality = _laminate(problem, sequence)
        robust = _shifted_quality(problem, sequence)
        score = (quality-low) / max(high-low, 1e-12)
        robust_low, robust_high = _shifted_quality(problem, baseline), _shifted_quality(problem, reference)
        robust_score = (robust-robust_low) / max(robust_high-robust_low, 1e-12)
        return {"name": spec["name"], "split": spec["split"], "valid": True,
                "score": float(score), "reserve_factor": quality,
                "robustness_score": float(robust_score), "robust_reserve_factor": robust}
    except Exception as exc:
        return {"name": spec["name"], "split": spec["split"], "valid": False,
                "score": 0.0, "reserve_factor": 0.0, "robustness_score": 0.0,
                "robust_reserve_factor": 0.0, "reason": f"{type(exc).__name__}: {exc}"}


def evaluate(design_laminate):
    rows = [_score_instance(design_laminate, spec) for spec in INSTANCE_SPECS]
    dev = [r for r in rows if r["split"] == "development"]
    held = [r for r in rows if r["split"] == "heldout"]
    return {
        "combined_score": float(np.mean([r["score"] for r in dev])),
        "valid": float(all(r["valid"] for r in dev)),
        "feasibility_rate": float(np.mean([r["valid"] for r in dev])),
        "robustness_score": float(np.mean([r["robustness_score"] for r in dev])),
        "heldout_policy_score": float(np.mean([r["score"] for r in held])),
        "heldout_robustness_score": float(np.mean([r["robustness_score"] for r in held])),
        "heldout_feasibility_rate": float(np.mean([r["valid"] for r in held])),
        "per_instance": rows,
    }
