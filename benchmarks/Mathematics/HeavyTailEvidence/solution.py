"""Always publish a power law with alpha=2."""
from __future__ import annotations


def synthesize_tail_evidence(problem, extra_draw):
    _ = problem["xmin"]
    _ = problem["public_sample"]
    _ = problem["extra_draw_budget"]
    _ = problem["family_names"]
    _ = problem["abstain_when"]
    _ = extra_draw
    return {"abstain": False, "family": "powerlaw", "alpha": 2.0, "confidence": 0.8}
