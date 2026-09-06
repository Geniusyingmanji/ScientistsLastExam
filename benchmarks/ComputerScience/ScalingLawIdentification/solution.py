"""Weak valid baseline: one timing at the smallest size, uniform class
probabilities, mid-range scale, never refusing."""

from __future__ import annotations


def identify_scaling_law(problem, time_run, budget_units):
    del budget_units
    time_run(16)
    probabilities = {name: 1.0 / len(problem["classes"])
                     for name in problem["classes"]}
    return {"class_probabilities": probabilities, "scale": 100.0,
            "abstain": False, "confidence": 0.5}
