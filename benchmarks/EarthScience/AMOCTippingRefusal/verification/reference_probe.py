"""Truth-blind reference for AMOCTippingRefusal.

Plus/minus probes at offset 0 test hysteresis at the present freshwater. If the two
held integrations end on opposite sides of zero, a fold is supported and a continued
run is used to read a collapse year. Otherwise the fingerprint is treated as
unsupported (red noise or a unique restored attractor).
"""
from __future__ import annotations


def _end(series):
    return float(series["amoc"][-1])


def interpret_amoc(problem, probe):
    duration_hold = min(60, int(problem["max_duration_years"]))
    try:
        plus = probe(0.0, duration_hold, "plus")
        minus = probe(0.0, duration_hold, "minus")
    except Exception:
        return {"abstain": True, "confidence": 0.2}
    if _end(plus) * _end(minus) >= 0.0 or abs(_end(plus) - _end(minus)) < 0.9:
        return {"abstain": True, "confidence": 0.85}
    duration_fwd = min(100, int(problem["max_duration_years"]))
    try:
        fwd = probe(0.0, duration_fwd, "continue")
    except Exception:
        return {"abstain": True, "confidence": 0.4}
    years = list(fwd["years"])
    amoc = list(fwd["amoc"])
    collapse = None
    for prev_y, prev, year, value in zip(years[:-1], amoc[:-1], years[1:], amoc[1:]):
        if prev > 0.0 and value <= 0.0:
            collapse = float(year)
            break
    if collapse is None:
        # Fold supported but not crossed in the probe window: report the last year as a
        # lower bound rather than inventing a date. The evaluator still requires a year
        # in-window, so decline rather than guess.
        return {"abstain": True, "confidence": 0.55}
    return {
        "abstain": False,
        "has_tipping": True,
        "collapse_year": collapse,
        "confidence": 0.88,
    }
