"""Baseline: read the spectrum as if it were first order, which it is not.

Take the n strongest peaks as the shifts and report no couplings. Valid by construction and
deliberately weak: it ignores multiplet structure entirely.
"""


def infer_spin_system(observation):
    peaks = sorted(observation["peaks"], key=lambda p: -p[1])[: observation["spins"]]
    shifts = sorted(float(f) for f, _ in peaks)
    n = observation["spins"]
    return {"shifts": shifts, "couplings": [[0.0] * n for _ in range(n)]}
