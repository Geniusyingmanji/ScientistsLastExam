"""Truth-blind reference policy for transient waveform inference."""
from __future__ import annotations
import math
import numpy as np

def _fit_grid(t, y):
    best = (float("inf"), 0.0, 0.0, 0.0, 0.0)
    for f0 in np.linspace(.04, .18, 29):
        for slope in np.linspace(0.0, .04, 21):
            phase = 2 * math.pi * (f0 * t + .5 * slope * t * t)
            x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
            coef, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
            err = float(np.mean((y - x @ coef) ** 2))
            amp = float(np.hypot(coef[1], coef[2]))
            if err < best[0]: best = (err, f0, slope, amp, float(np.arctan2(coef[2], coef[1])))
    f_step, s_step = .14 / 28, .04 / 20
    for _ in range(3):
        local = best
        for f0 in np.linspace(max(.04, best[1] - f_step), min(.18, best[1] + f_step), 9):
            for slope in np.linspace(max(0.0, best[2] - s_step), min(.05, best[2] + s_step), 9):
                phase = 2 * math.pi * (f0 * t + .5 * slope * t * t)
                x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
                coef, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
                err = float(np.mean((y - x @ coef) ** 2))
                if err < local[0]: local = (err, f0, slope, float(np.hypot(coef[1], coef[2])), float(np.arctan2(coef[2], coef[1])))
        best = local
        f_step /= 4; s_step /= 4
    return best

def infer_transient(problem, observe):
    times = [float(t) for t in problem["candidate_times"][:12]]
    rows = [observe(t, "H1") for t in times]
    rows += [observe(t, "L1") for t in times]
    h = np.array([r["strain"] for r in rows[:12]], dtype=float)
    l = np.array([r["strain"] for r in rows[12:]], dtype=float)
    t = np.array(times, dtype=float)
    fit = _fit_grid(t, h)
    # A chirp fit must improve on the constant-frequency subgrid.
    line_err, line_frequency = float("inf"), 0.11
    for f0 in np.linspace(.04, .18, 29):
        phase = 2 * math.pi * f0 * t
        x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
        c, _, _, _ = np.linalg.lstsq(x, h, rcond=None)
        error = float(np.mean((h - x @ c) ** 2))
        if error < line_err:
            line_err, line_frequency = error, float(f0)
    line_step = .14 / 28
    for _ in range(3):
        local_error, local_frequency = line_err, line_frequency
        for f0 in np.linspace(max(.04, line_frequency - line_step), min(.18, line_frequency + line_step), 9):
            phase = 2 * math.pi * f0 * t
            x = np.column_stack([np.ones(len(t)), np.sin(phase), np.cos(phase)])
            coef, _, _, _ = np.linalg.lstsq(x, h, rcond=None)
            error = float(np.mean((h - x @ coef) ** 2))
            if error < local_error:
                local_error, local_frequency = error, float(f0)
        line_err, line_frequency = local_error, local_frequency
        line_step /= 4
    diff = np.abs(h - l)
    peak = int(np.argmax(diff))
    if (float(diff[peak]) > .38 and float(np.max(np.abs(h))) > .45
            and float(np.median(np.abs(l))) < .18):
        amp = float(np.clip(np.max(np.abs(h)), 0.0, 1.0))
        return {"abstain": False, "model": "glitch", "initial_frequency": .11, "frequency_slope": 0.0,
                "event_time": float(t[peak]), "amplitude": amp, "confidence": .82,
                "evidence_query_ids": [r["query_id"] for r in rows]}
    if fit[0] > .006 or fit[3] < .35:
        return {"abstain": True, "confidence": .70, "evidence_query_ids": [r["query_id"] for r in rows]}
    if fit[0] < line_err * .72:
        model, frequency, slope, conf = "chirp", fit[1], fit[2], .78
    else:
        model, frequency, slope, conf = "line", line_frequency, 0.0, .76
    return {"abstain": False, "model": model, "initial_frequency": float(np.clip(frequency, .04, .18)), "frequency_slope": float(np.clip(slope, 0, .05)),
            "event_time": 9.0, "amplitude": float(np.clip(fit[3], 0, 1)),
            "confidence": conf, "evidence_query_ids": [r["query_id"] for r in rows]}
