"""Weak but valid baseline for CrowdedSpectrumAssignment.

It does what the default scan invites: treat every library species with a line near a strong
peak as present, split the mixture equally, never zoom, and never decline. Close pairs therefore
pull in epsilon as well as gamma and delta; contaminant lines pull in whoever is nearest; a
blank still publishes whoever the noise grazed.
"""
from __future__ import annotations


def assign_species(problem, scan, zoom):
    library = problem["library"]
    sigma = float(problem["default_resolution_sigma"])
    try:
        peaks = scan()
    except Exception:
        return {"abstain": True, "confidence": 0.0}
    if not peaks:
        # Still publishes: the failure mode the blank world exists to catch.
        names = list(library)[:2]
        return {"species": [{"name": n, "fraction": 1.0 / len(names)} for n in names],
                "confidence": 0.4, "abstain": False}
    hits = []
    for name, lines in library.items():
        if any(abs(peak["wavenumber"] - pos) <= 2.0 * sigma
               for peak in peaks for pos in lines):
            hits.append(name)
    hits = hits[: int(problem["max_claimed_species"])]
    if not hits:
        hits = list(library)[:1]
    n = len(hits)
    return {
        "species": [{"name": name, "fraction": 1.0 / n} for name in hits],
        "confidence": 0.85,
        "abstain": False,
    }
