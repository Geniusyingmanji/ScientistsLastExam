"""Weak but valid baseline for EnzymeKineticsLaw.

It titrates substrate once with no inhibitor, reads Vmax off the highest point and Km off the
half-maximal point, and always reports Michaelis-Menten. It never varies the inhibitor, so it
cannot separate the three inhibition modes; it never checks residuals, so it claims a mechanism on
worlds that have none.
"""
from __future__ import annotations


def discover_kinetics(problem, assay):
    substrate_points = [1.0, 3.0, 10.0, 30.0, 100.0, 300.0]
    velocities = []
    for s in substrate_points:
        try:
            velocities.append((s, float(assay(s, 0.0))))
        except Exception:
            break
    if not velocities:
        return {"abstain": True, "confidence": 0.0}

    vmax = max(v for _, v in velocities)
    half = vmax / 2.0
    km = velocities[len(velocities) // 2][0]
    for s, v in velocities:
        if v >= half:
            km = s
            break
    return {
        "law": "michaelis_menten",
        "parameters": {"vmax": vmax, "km": km},
        "confidence": 0.5,
        "abstain": False,
    }
