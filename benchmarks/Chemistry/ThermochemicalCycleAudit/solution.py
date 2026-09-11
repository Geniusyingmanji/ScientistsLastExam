"""Weak valid baseline: trusts every reported value and calls the network consistent.

It rubber-stamps the data set: no reconciliation, no flags, no verdict beyond
"consistent", and the corrected enthalpies are the reported values verbatim. On
corrupted worlds this is exactly the confident over-acceptance the audit should catch.
"""

from __future__ import annotations


def audit_thermochemical_cycle(problem, replicate, cross_check, budget_units):
    del replicate, cross_check, budget_units
    return {
        "verdict": "consistent",
        "flagged_measurements": [],
        "drift_instrument": "",
        "corrected_enthalpies": {
            row["id"]: float(row["value_kj_per_mol"])
            for row in problem["measurements"]
        },
        "confidence": 0.9,
    }
