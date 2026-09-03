"""Truth-blind reference for ComplexBoseLaw.

The cavity mixes nearby modes. Invert the mixed occupancy with the exact Bose map
x = log(1 + 1/n) ≈ C ω^α / T^β; mixing mostly renormalizes C. Occupancy that saturates
below 1 is Fermi; occupancy that does not move with T is blank. Both are refused.
"""
from __future__ import annotations

import math

import numpy as np


def _safe_measure(measure, omega, temperature):
    try:
        return float(measure(omega, temperature))
    except Exception:
        return None


def interpret_cavity(problem, measure):
    lo_w, hi_w = [float(x) for x in problem["omega_bounds"]]
    lo_t, hi_t = [float(x) for x in problem["temperature_bounds"]]
    omegas = [lo_w + (hi_w - lo_w) * x for x in (0.15, 0.38, 0.58, 0.78)]
    temps = [lo_t + (hi_t - lo_t) * x for x in (0.18, 0.42, 0.66, 0.90)]
    rows = []
    for omega in omegas:
        for temperature in temps:
            value = _safe_measure(measure, omega, temperature)
            if value is None:
                return {"abstain": True, "confidence": 0.2}
            rows.append((omega, temperature, value))

    t_span = []
    for omega in omegas:
        series = [v for w, _temperature, v in rows if w == omega]
        t_span.append(max(series) / max(1e-6, min(series)))
    if max(t_span) < 1.35:
        return {"abstain": True, "confidence": 0.75}

    if max(v for *_, v in rows) < 0.92:
        return {"abstain": True, "confidence": 0.8}

    logs = []
    for omega, temperature, value in rows:
        if value <= 0.08:
            continue
        expo = math.log(1.0 + 1.0 / value)
        if expo <= 1e-8:
            continue
        logs.append((math.log(omega), math.log(temperature), math.log(expo)))
    if len(logs) < 8:
        return {"abstain": True, "confidence": 0.35}

    design = np.column_stack([
        np.ones(len(logs)),
        np.array([row[0] for row in logs]),
        -np.array([row[1] for row in logs]),
    ])
    target = np.array([row[2] for row in logs])
    coef, _residuals, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank < 3:
        return {"abstain": True, "confidence": 0.3}
    log_c, alpha, beta = (float(x) for x in coef)
    C = math.exp(log_c)
    if not all(math.isfinite(v) and v > 0.05 for v in (C, alpha, beta)):
        return {"abstain": True, "confidence": 0.3}
    if alpha < 0.7 or alpha > 2.3 or beta < 0.8 or beta > 3.0:
        return {"abstain": True, "confidence": 0.45}
    return {
        "abstain": False,
        "family": "bose",
        "C": C,
        "alpha": alpha,
        "beta": beta,
        "confidence": 0.9,
    }
