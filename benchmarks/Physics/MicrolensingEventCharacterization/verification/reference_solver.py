"""Truth-blind reference policy for active microlensing characterization."""
from __future__ import annotations

import math

import numpy as np


def _point_feature(times, t0, scale, u0):
    u = np.sqrt(u0 * u0 + ((times - t0) / scale) ** 2)
    return (u * u + 2.0) / (u * np.sqrt(u * u + 4.0)) - 1.0


def _fit_point(times, flux):
    best = None
    for t0 in np.linspace(-6.0, 6.0, 25):
        for scale in np.linspace(3.0, 17.0, 29):
            for u0 in (0.18, 0.28, 0.40, 0.55, 0.75):
                feature = _point_feature(times, t0, scale, u0)
                design = np.column_stack([np.ones(len(times)), feature])
                coef, _, _, _ = np.linalg.lstsq(design, flux, rcond=None)
                err = float(np.mean((flux - design @ coef) ** 2))
                if best is None or err < best[0]:
                    best = (err, float(scale), feature, coef)
    return best


def _sinusoid(times, flux):
    best = (float("inf"), 0.0, 0.0)
    for period in (12.0, 15.0, 18.0, 21.0, 24.0):
        design = np.column_stack([np.ones(len(times)), np.sin(2.0 * math.pi * times / period),
                                   np.cos(2.0 * math.pi * times / period)])
        coef, _, _, _ = np.linalg.lstsq(design, flux, rcond=None)
        err = float(np.mean((flux - design @ coef) ** 2))
        amp = float(np.hypot(coef[1], coef[2]))
        if err < best[0]:
            best = (err, period, amp)
    return best


def infer_microlensing(problem, observe):
    times = np.asarray(problem["candidate_times"], dtype=float)
    chosen = list(times[::2])
    chosen += [float(x) for x in (-6.0, -2.0, 2.0, 6.0, 10.0, 14.0)]
    chosen = list(dict.fromkeys(round(x, 3) for x in chosen))[:18]
    rows = [observe(float(t), "r") for t in chosen]
    extra = [-18.0, -10.0, 0.0, 4.0, 8.0, 16.0]
    rows.extend(observe(float(t), "g") for t in extra)
    t = np.array([row["time"] for row in rows if row["band"] == "r"], dtype=float)
    y = np.array([row["flux"] for row in rows if row["band"] == "r"], dtype=float)
    point = _fit_point(t, y)
    sine_err, period, sine_amp = _sinusoid(t, y)
    residual = y - (point[3][0] + point[3][1] * point[2])
    anomaly = float(np.max(residual))
    point_excess = float(np.max(y) - np.median(y[np.abs(t) > 16.0]))
    evidence = [row["query_id"] for row in rows]
    if min(point[0], sine_err) > 0.0025 or (point_excess < 0.16 and sine_amp < 0.09):
        return {"abstain": True, "confidence": 0.72, "evidence_query_ids": evidence}
    if anomaly > 0.09 and point_excess > 0.20:
        model, amplitude, confidence = "binary_lens", float(np.clip(anomaly, 0.0, 1.0)), 0.78
        scale = point[1]
    elif point_excess > 0.20 and point[0] <= sine_err * 1.15:
        model, amplitude, confidence = "point_lens", 0.0, 0.80
        scale = point[1]
    else:
        model, amplitude, confidence = "variable_source", float(np.clip(sine_amp, 0.0, 1.0)), 0.74
        scale = period
    return {"abstain": False, "model": model, "timescale_days": float(np.clip(scale, 2.0, 20.0)),
            "amplitude": amplitude, "confidence": confidence, "evidence_query_ids": evidence}
