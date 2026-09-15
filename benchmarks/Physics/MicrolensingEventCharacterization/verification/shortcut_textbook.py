"""Cheap fixed-source microlensing/sinusoid probe modeled on PR review feedback."""
from __future__ import annotations

import math

import numpy as np


def _point(times, t0, scale, impact):
    u = np.sqrt(impact * impact + ((times - t0) / scale) ** 2)
    return (u * u + 2.0) / (u * np.sqrt(u * u + 4.0)) - 1.0


def infer_microlensing(problem, observe):
    rows = [observe(float(time), "r") for time in problem["candidate_times"][:-1]]
    times = np.asarray([row["time"] for row in rows])
    flux = np.asarray([row["flux"] for row in rows])
    target = flux - 1.0
    point = None
    for t0 in np.linspace(-8.0, 8.0, 17):
        for scale in np.linspace(3.0, 23.0, 21):
            for impact in (0.25, 0.45, 0.70, 0.95):
                prediction = 0.42 * _point(times, t0, scale, impact)
                sse = float(np.sum((target - prediction) ** 2))
                if point is None or sse < point[0]:
                    point = (sse, scale, t0, prediction, impact)
    residual = target - point[3]
    anomaly_index = int(np.argmax(residual))
    anomaly = max(0.0, float(residual[anomaly_index]))
    binary_sse = float(np.sum((residual - anomaly * np.exp(
        -0.5 * ((times - times[anomaly_index]) / 1.4) ** 2)) ** 2))

    sine = None
    for period in np.linspace(4.0, 24.0, 81):
        omega = 2.0 * math.pi / period
        design = np.column_stack((np.sin(omega * times), np.cos(omega * times)))
        coef, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
        error = target - design @ coef
        sse = float(error @ error)
        if sine is None or sse < sine[0]:
            phase = math.atan2(-float(coef[1]), float(coef[0])) / omega
            peak = phase + 0.25 * period
            peak -= round(peak / period) * period
            sine = (sse, period, float(np.hypot(*coef)), peak)

    best_supported = min(point[0], binary_sse, sine[0])
    evidence = [row["query_id"] for row in rows]
    if math.sqrt(best_supported / len(times)) > 0.085:
        return {"abstain": True, "confidence": 0.72, "evidence_query_ids": evidence}
    if sine[0] < min(point[0], binary_sse) * 0.72:
        model, scale, amplitude, feature = "variable_source", sine[1], sine[2], sine[3]
    elif binary_sse < point[0] * 0.62 and anomaly > 0.09:
        model, scale, amplitude, feature = (
            "binary_lens", point[1], anomaly, float(times[anomaly_index]))
    else:
        model, scale, amplitude, feature = "point_lens", point[1], 0.0, point[2]
    if model != "variable_source":
        peak = float(_point(np.asarray([0.0]), 0.0, 1.0, point[4])[0])
        target, lower, upper = 0.5 * peak, point[4], 10.0
        for _ in range(50):
            middle = 0.5 * (lower + upper)
            if float(_point(np.asarray([middle]), 0.0, 1.0, 0.0)[0]) > target:
                lower = middle
            else:
                upper = middle
        scale = 2.0 * scale * math.sqrt((0.5 * (lower + upper)) ** 2 - point[4] ** 2)
    return {
        "abstain": False, "model": model,
        "timescale_days": float(np.clip(scale, 2.0, 24.0)),
        "amplitude": float(np.clip(amplitude, 0.0, 1.0)),
        "feature_time_days": float(np.clip(feature, -24.0, 24.0)),
        "confidence": 0.78, "evidence_query_ids": evidence,
    }
