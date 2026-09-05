"""Weak valid baseline: names two fixed library minerals with uniform fractions.

The copy-paste composition claim -- quartz and calcite, fifty-fifty -- ignores the
pattern entirely and never refuses.
"""

from __future__ import annotations


def identify_minerals(problem, coarse_scan, slow_scan, budget_units):
    del coarse_scan, slow_scan, budget_units
    names = ["calcite", "quartz"]
    return {"minerals": names,
            "fractions": {name: 0.5 for name in names},
            "abstain": False, "confidence": 0.9}
