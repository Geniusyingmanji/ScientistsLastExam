"""Truth-blind dual-channel reference policy for transient waveform inference."""
from __future__ import annotations

import math
import numpy as np


def _fit_grid(t, y):
    best = (float("inf"), 0.0, 0.0, 0.0)
    for f0 in np.linspace(.04, .18, 29):
        for slope in np.linspace(0.0, .05, 26):
            phase = 2 * math.pi * (f0 * t + .5 * slope * t * t)
            x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
            coef, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
            error = float(np.mean((y - x @ coef) ** 2))
            candidate = (error, float(f0), float(slope), float(np.hypot(coef[1], coef[2])))
            if candidate[0] < best[0]:
                best = candidate
    f_step, s_step = .005, .002
    for _ in range(3):
        local = best
        for f0 in np.linspace(max(.04, best[1] - f_step), min(.18, best[1] + f_step), 9):
            for slope in np.linspace(max(0.0, best[2] - s_step), min(.05, best[2] + s_step), 9):
                phase = 2 * math.pi * (f0 * t + .5 * slope * t * t)
                x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
                coef, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
                error = float(np.mean((y - x @ coef) ** 2))
                candidate = (error, float(f0), float(slope), float(np.hypot(coef[1], coef[2])))
                if candidate[0] < local[0]:
                    local = candidate
        best = local
        f_step /= 4
        s_step /= 4
    return best


def _event_time(t, y, noise):
    energy = np.maximum(y * y - noise * noise, 0.0)
    total = float(np.sum(energy))
    return float(np.sum(t * energy) / total) if total else 9.0


def _reference_times(problem):
    available = [float(value) for value in problem["candidate_times"]]
    h_indices = np.rint(np.linspace(0, len(available) - 1, 14)).astype(int)
    l_indices = np.rint(np.linspace(0, len(available) - 1, 10)).astype(int)
    return ([available[int(index)] for index in h_indices],
            [available[int(index)] for index in l_indices])


def infer_transient(problem, observe):
    h_times, l_times = _reference_times(problem)
    h_rows = [observe(time, "H1") for time in h_times]
    l_rows = [observe(time, "L1") for time in l_times]
    rows = h_rows + l_rows
    h = np.asarray([row["strain"] for row in h_rows], dtype=float)
    l = np.asarray([row["strain"] for row in l_rows], dtype=float)
    ht = np.asarray(h_times, dtype=float)
    noise = float(rows[0]["uncertainty"])
    evidence = [row["query_id"] for row in rows]

    h_power = math.sqrt(max(float(np.var(h)) - noise * noise, 0.0))
    l_power = math.sqrt(max(float(np.var(l)) - noise * noise, 0.0))
    if h_power < .09:
        return {"abstain": True, "confidence": .70, "evidence_query_ids": evidence}

    fit = _fit_grid(ht, h)
    if l_power / max(h_power, 1e-12) < .48:
        model, frequency, slope = "glitch", .11, 0.0
        event_time = _event_time(ht, h, noise)
    else:
        model = "chirp" if fit[2] >= .002 else "line"
        frequency = fit[1]
        slope = fit[2] if model == "chirp" else 0.0
        event_time = 9.0
    return {
        "abstain": False,
        "model": model,
        "initial_frequency": float(np.clip(frequency, .04, .18)),
        "frequency_slope": float(np.clip(slope, 0.0, .05)),
        "event_time": float(np.clip(event_time, 0.0, 18.0)),
        "amplitude": float(np.clip(fit[3], 0.0, 1.0)),
        "confidence": .80,
        "evidence_query_ids": evidence,
    }
