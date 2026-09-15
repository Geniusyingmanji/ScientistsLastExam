"""Truth-blind reference policy for active microlensing characterization."""
from __future__ import annotations

import math

import numpy as np


def _point_feature(times, t0, scale, u0):
    u = np.sqrt(u0 * u0 + ((times - t0) / scale) ** 2)
    return (u * u + 2.0) / (u * np.sqrt(u * u + 4.0)) - 1.0


def _point_duration(scale, u0):
    peak = float(_point_feature(np.asarray([0.0]), 0.0, 1.0, u0)[0])
    target = 0.5 * peak
    lower, upper = u0, 10.0
    for _ in range(60):
        middle = 0.5 * (lower + upper)
        value = float(_point_feature(np.asarray([middle]), 0.0, 1.0, 0.0)[0])
        if value > target:
            lower = middle
        else:
            upper = middle
    return 2.0 * scale * math.sqrt((0.5 * (lower + upper)) ** 2 - u0 * u0)


def _fit_point(times, flux, *, keep=80, robust=False):
    """Profile the bounded source fraction over a physical point-lens grid."""
    target = flux - 1.0
    candidates = []
    for t0 in np.linspace(-8.0, 8.0, 65):
        scales = np.linspace(2.0, 24.0, 89)[:, None, None]
        impact = np.linspace(0.15, 1.05, 19)[None, :, None]
        u = np.sqrt(impact * impact + ((times[None, None, :] - t0) / scales) ** 2)
        feature = (u * u + 2.0) / (u * np.sqrt(u * u + 4.0)) - 1.0
        denom = np.sum(feature * feature, axis=2)
        source = np.clip(np.sum(feature * target, axis=2) / denom, 0.08, 1.0)
        residual = target - source[:, :, None] * feature
        squared = residual * residual
        sse = np.sum(squared, axis=2)
        rank_score = (np.sum(np.sort(squared, axis=2)[:, :, :-3], axis=2)
                      if robust else sse)
        flat = np.argpartition(rank_score.ravel(), min(keep, sse.size) - 1)[:keep]
        for index in flat:
            i, j = np.unravel_index(index, sse.shape)
            candidates.append((float(rank_score[i, j]), float(sse[i, j]), float(t0),
                               float(scales[i, 0, 0]), float(impact[0, j, 0]),
                               float(source[i, j]), feature[i, j].copy()))
    candidates.sort(key=lambda row: row[0])
    return [(row[1], *row[2:]) for row in candidates[:keep]]


def _fit_binary(times, flux, point_candidates):
    """Jointly profile source fraction and a positive localized anomaly."""
    target = flux - 1.0
    centers = np.linspace(-14.0, 14.0, 57)
    widths = np.linspace(0.55, 3.25, 19)
    grid_center, grid_width = np.meshgrid(centers, widths, indexing="ij")
    gaussians = np.exp(-0.5 * ((times[None, None, :] - grid_center[:, :, None]) /
                              grid_width[:, :, None]) ** 2).reshape(-1, len(times))
    gg = np.sum(gaussians * gaussians, axis=1)
    gy = gaussians @ target
    best = None
    for _, t0, scale, u0, _, feature in point_candidates:
        ff = float(feature @ feature)
        fy = float(feature @ target)
        fg = gaussians @ feature
        determinant = np.maximum(ff * gg - fg * fg, 1e-12)
        source = np.clip((fy * gg - gy * fg) / determinant, 0.08, 1.0)
        anomaly = np.clip((gy * ff - fy * fg) / determinant, 0.0, 0.8)
        prediction = source[:, None] * feature + anomaly[:, None] * gaussians
        residual = target - prediction
        sse = np.sum(residual * residual, axis=1)
        index = int(np.argmin(sse))
        row = (float(sse[index]), t0, scale, u0, float(source[index]),
               float(grid_center.ravel()[index]), float(grid_width.ravel()[index]),
               float(anomaly[index]))
        if best is None or row[0] < best[0]:
            best = row
    return best


def _fit_sinusoid(times, flux):
    target = flux - 1.0
    best = None
    for period in np.linspace(2.0, 24.0, 441):
        omega = 2.0 * math.pi / period
        design = np.column_stack((np.sin(omega * times), np.cos(omega * times)))
        coef, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
        residual = target - design @ coef
        sse = float(residual @ residual)
        if best is None or sse < best[0]:
            amplitude = float(np.hypot(coef[0], coef[1]))
            phase = math.atan2(-float(coef[1]), float(coef[0])) / omega
            peak = phase + 0.25 * period
            peak -= round(peak / period) * period
            best = (sse, float(period), amplitude, float(peak))
    return best


def _bic(sse, observations, parameters):
    return observations * math.log(max(sse / observations, 1e-12)) + parameters * math.log(observations)


def _infer(problem, observe, *, collect_g=False, refuse=True, cadence_step=1):
    allowed = [float(value) for value in problem["candidate_times"]]
    chosen = allowed[:-1:cadence_step]
    rows = [observe(time, "r") for time in chosen]
    if collect_g:
        remaining = problem["observation_budget_units"] - len(rows)
        for time in allowed[:remaining]:
            rows.append(observe(time, "g"))
    times = np.asarray([row["time"] for row in rows if row["band"] == "r"], dtype=float)
    flux = np.asarray([row["flux"] for row in rows if row["band"] == "r"], dtype=float)
    evidence = [row["query_id"] for row in rows]

    point_candidates = _fit_point(times, flux)
    point = point_candidates[0]
    binary = _fit_binary(times, flux, _fit_point(times, flux, robust=True))
    variable = _fit_sinusoid(times, flux)
    fits = {
        "point_lens": (_bic(point[0], len(times), 4), point[0]),
        "binary_lens": (_bic(binary[0], len(times), 7), binary[0]),
        "variable_source": (_bic(variable[0], len(times), 3), variable[0]),
    }
    ranked = sorted(fits, key=lambda label: fits[label][0])
    model = ranked[0]
    best_sse = fits[model][1]
    residual_rms = math.sqrt(best_sse / len(times))
    if refuse and residual_rms > 0.060:
        return {"abstain": True, "confidence": 0.88, "evidence_query_ids": evidence}

    margin = fits[ranked[1]][0] - fits[ranked[0]][0]
    confidence = float(np.clip(0.72 + 0.025 * margin, 0.72, 0.90))
    if model == "point_lens":
        timescale, amplitude, feature_time = _point_duration(point[2], point[3]), 0.0, point[1]
    elif model == "binary_lens":
        timescale = _point_duration(binary[2], binary[3])
        amplitude, feature_time = binary[7], binary[5]
    else:
        timescale, amplitude, feature_time = variable[1], variable[2], variable[3]
    return {
        "abstain": False,
        "model": model,
        "timescale_days": float(np.clip(timescale, 2.0, 24.0)),
        "amplitude": float(np.clip(amplitude, 0.0, 1.0)),
        "feature_time_days": float(np.clip(feature_time, -24.0, 24.0)),
        "confidence": confidence,
        "evidence_query_ids": evidence,
    }


def infer_microlensing(problem, observe):
    return _infer(problem, observe)
