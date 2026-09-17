"""Frozen development-selected five-slope lookup witness from PR48.

The factory below is copied without changes from calibrate.py at
f345d8f53b5df92d32d48180c614d269210f2847. The parameters are the author's
published development-only selection from 324 declared policies; heldout
outcomes were reported after selection. No new search or waveform fit runs here.
"""
import numpy as np

def lookup_morphology_policy(sample_count=14, refusal_rms=0.10, glitch_median=0.10,
                             half=14, slopes=(0.0, 0.006, 0.018, 0.028, 0.028), line_upto=1):
    """Maintainer's no-fit morphology family with a finite slope lookup table."""
    def infer(problem, observe):
        times = [float(value) for value in problem["candidate_times"][:sample_count]]
        rows = [observe(time, "H1") for time in times]
        h = np.asarray([row["strain"] for row in rows], dtype=float)
        evidence = [row["query_id"] for row in rows]
        if float(np.std(h)) < refusal_rms:
            return {"abstain": True, "confidence": 1.0, "evidence_query_ids": evidence}
        if float(np.median(np.abs(h))) < glitch_median:
            return {"abstain": False, "model": "glitch", "initial_frequency": 0.11,
                    "frequency_slope": 0.0, "event_time": times[int(np.argmax(h))],
                    "amplitude": float(np.clip(np.max(np.abs(h)), 0, 1)), "confidence": 1.0,
                    "evidence_query_ids": evidence}
        delta = (int(np.sum(np.diff(np.signbit(h[half:]))))
                 - int(np.sum(np.diff(np.signbit(h[:half])))))
        model = "line" if delta <= line_upto else "chirp"
        slope = 0.0 if model == "line" else slopes[min(len(slopes) - 1, max(0, delta))]
        return {"abstain": False, "model": model, "initial_frequency": 0.11,
                "frequency_slope": slope, "event_time": 9.0,
                "amplitude": float(np.clip(np.sqrt(2) * np.std(h), 0, 1)), "confidence": 1.0,
                "evidence_query_ids": evidence}
    return infer

infer_transient = lookup_morphology_policy(
    16, 0.08, 0.08, 7, (0.0, 0.006, 0.018, 0.028, 0.028), 1
)
