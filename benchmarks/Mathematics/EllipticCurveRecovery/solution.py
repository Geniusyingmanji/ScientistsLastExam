"""Weak valid baseline: counts points at one small prime and guesses (a, b) = (0, 1)
everywhere, never refusing."""

from __future__ import annotations


def recover_curve(problem, count_points, budget_units):
    del budget_units
    count_points(11)
    return {"a": 0, "b": 1, "abstain": False, "confidence": 0.5}
