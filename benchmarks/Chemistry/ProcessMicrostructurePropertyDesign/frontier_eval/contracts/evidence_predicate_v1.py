"""Evidence gate for a feasible evaluator-derived raw Pareto hypervolume."""
from __future__ import annotations

import math

CELL_ID = "process-property-pareto-hypervolume"


def make_frontier_record(canonical_id, raw_hypervolume, valid):
    if not valid:
        return None
    if not isinstance(canonical_id, str) or ":panel:sha256:" not in canonical_id:
        return None
    if not isinstance(raw_hypervolume, (int, float)) or not math.isfinite(raw_hypervolume):
        return None
    if raw_hypervolume < 0.0:
        return None
    return {
        "cell_id": CELL_ID,
        "canonical_id": canonical_id,
        "value": float(raw_hypervolume),
    }
