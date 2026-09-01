"""Weak but valid baseline for DiscrepantMeasurements.

It does what a table invites: takes the inverse-variance weighted mean of the published values,
quotes the usual uncertainty on it, and declares the set consistent. It never buys a split test,
so it cannot know whether any group is internally sound, and it never declines, so it publishes a
single world average even where two methods disagree and no single number is defensible.
"""
from __future__ import annotations


def synthesize_evidence(problem, split_test):
    table = problem["measurements"]
    weight_total = 0.0
    weighted_sum = 0.0
    for row in table:
        sigma = float(row["quoted_sigma"])
        if sigma <= 0.0:
            continue
        weight = 1.0 / (sigma * sigma)
        weight_total += weight
        weighted_sum += weight * float(row["value"])
    if weight_total <= 0.0:
        return {"abstain": True, "confidence": 0.0}
    mean = weighted_sum / weight_total
    return {
        "best_value": mean,
        "uncertainty": weight_total ** -0.5,
        "diagnosis": "consistent",
        "confidence": 0.9,
        "abstain": False,
    }
