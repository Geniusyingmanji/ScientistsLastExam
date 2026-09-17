"""Frozen development-selected member of the declared threshold shortcut grid."""
import numpy as np


def infer_transient(problem, observe):
    sample_count = 12
    times = [float(value) for value in problem["candidate_times"][:sample_count]]
    rows = [observe(time, detector) for detector in ("H1", "L1") for time in times]
    h1 = np.asarray([row["strain"] for row in rows[:sample_count]], dtype=float)
    l1 = np.asarray([row["strain"] for row in rows[sample_count:]], dtype=float)
    difference = np.abs(h1 - l1)
    peak = int(np.argmax(difference))
    scale = float(np.sqrt(np.mean((0.5 * (h1 + l1)) ** 2)))
    evidence = [row["query_id"] for row in rows]
    if scale < 0.08:
        return {"abstain": True, "confidence": 0.6, "evidence_query_ids": evidence}
    if float(difference[peak]) > 0.25:
        model, slope, event_time = "glitch", 0.0, times[peak]
    else:
        rough_change = float(abs(np.mean(np.diff(h1[:sample_count // 2]))
                                 - np.mean(np.diff(h1[sample_count // 2:]))))
        model = "chirp" if rough_change > 0.02 else "line"
        slope, event_time = (0.02 if model == "chirp" else 0.0), 9.0
    return {
        "abstain": False,
        "model": model,
        "initial_frequency": 0.11,
        "frequency_slope": slope,
        "event_time": event_time,
        "amplitude": float(np.clip(np.sqrt(2) * scale, 0, 1)),
        "confidence": 0.65,
        "evidence_query_ids": evidence,
    }
