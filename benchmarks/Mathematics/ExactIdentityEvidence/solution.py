"""Weak valid baseline: refuses every claim without spending a cent.

It declares every relation undecidable — the coward's audit. Valid, exactly at the
passive floor, and worth nothing after normalization.
"""

from __future__ import annotations


def audit_identity_claims(problem, purchase, budget_units):
    del purchase, budget_units
    return {
        "verdicts": {claim["id"]: "undecidable" for claim in problem["claims"]},
        "coefficients": {},
        "confidence": 0.9,
    }
