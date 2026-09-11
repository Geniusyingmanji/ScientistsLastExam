"""Weak valid baseline: one low-energy scan, claims the molecule does not fragment.

It asserts a fragmentation tree consisting of the intact precursor ion only. The
measurement is legal and charged, but the claim ignores every fragment the instrument
already showed, so the recovery score sits at the floor.
"""

from __future__ import annotations


def recover_fragmentation_tree(problem, acquire, zoom, budget_units):
    del zoom, budget_units
    acquire(20.0)
    return {
        "nodes": [float(problem["precursor_mz"])],
        "edges": [],
        "abstain": False,
        "confidence": 0.9,
    }
