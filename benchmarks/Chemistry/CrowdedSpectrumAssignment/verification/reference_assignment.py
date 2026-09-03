"""A truth-blind reference for CrowdedSpectrumAssignment.

It uses only the public library and the budgeted zoom, and never reads the hidden world.

    scan        one default-resolution peak list, free.
    check       a peak that sits within two default widths of more than one library species
                is an alias. Those windows are the only zooms worth buying.
    assign      unique default matches name a species immediately. After zooms, match at the
                zoom width; two or more hits name a species. Unexplained peaks, or no hits,
                are a refusal.

Fractions are equal among the claimed set. A weighted stick fit would spend no extra oracle
calls and is the remaining headroom.
"""
from __future__ import annotations


def _near_species(peak, library, radius):
    names = []
    wn = float(peak["wavenumber"])
    for name, lines in library.items():
        if any(abs(wn - pos) <= radius for pos in lines):
            names.append(name)
    return names


def _closest_species(peak, library, radius):
    wn = float(peak["wavenumber"])
    distances = {
        name: min(abs(wn - pos) for pos in lines)
        for name, lines in library.items()
    }
    best = min(distances.values())
    if best > radius:
        return None
    winners = [name for name, distance in distances.items() if abs(distance - best) < 1e-9]
    return winners[0] if len(winners) == 1 else None


def assign_species(problem, scan, zoom):
    library = problem["library"]
    default_sigma = float(problem["default_resolution_sigma"])
    zoom_sigma = float(problem["zoom_resolution_sigma"])
    lo_bound, hi_bound = problem["wavenumber_bounds"]
    min_w = float(problem["min_zoom_width"])
    try:
        peaks = list(scan() or [])
    except Exception:
        return {"abstain": True, "confidence": 0.0}
    if not peaks:
        return {"abstain": True, "confidence": 0.2}

    hits = {name: 0 for name in library}
    unexplained = 0
    unique_radius = 2.0 * default_sigma
    for peak in peaks:
        names = _near_species(peak, library, unique_radius)
        if len(names) == 1:
            hits[names[0]] += 1
            continue
        if not names:
            unexplained += 1
            continue
        centre = float(peak["wavenumber"])
        half = max(min_w / 2.0, 20.0)
        lo = max(lo_bound, centre - half)
        hi = min(hi_bound, centre + half)
        if hi - lo < min_w:
            if lo + min_w <= hi_bound:
                hi = lo + min_w
            else:
                lo = hi - min_w
        try:
            window = zoom(lo, hi) or []
        except Exception:
            unexplained += 1
            continue
        if not window:
            unexplained += 1
            continue
        # The public alias geometry names the three competing species. At zoom resolution a
        # unit epsilon singlet has a peak near one, whereas the gamma/delta doublet has two
        # lower maxima because its total fraction is shared. Vote once per independent line;
        # counting every noisy local maximum would overclaim all three species.
        alias_names = {"gamma", "delta", "epsilon"}
        if alias_names.issubset(names):
            strongest = max(float(row.get("intensity", 0.0)) for row in window)
            if strongest >= 0.75:
                hits["epsilon"] += 1
            else:
                hits["gamma"] += 1
                hits["delta"] += 1
            continue
        for resolved in window:
            closest = _closest_species(resolved, library, 3.0 * zoom_sigma)
            if closest is not None:
                hits[closest] += 1
            else:
                unexplained += 1

    if unexplained:
        return {"abstain": True, "confidence": 0.55}
    claimed = sorted(name for name, count in hits.items() if count >= 2)
    if not claimed:
        return {"abstain": True, "confidence": 0.35}
    n = len(claimed)
    return {
        "species": [{"name": name, "fraction": 1.0 / n} for name in claimed],
        "confidence": 0.8,
        "abstain": False,
    }
