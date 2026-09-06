"""Evidence gate for a replayed adaptive conservative PDE method result."""
from __future__ import annotations

import math

CELL_ID = "conservative-scalar-law-method"
CONSERVATION_TOLERANCE = 1.0e-10


def make_frontier_record(canonical_id, raw_utility, max_conservation_error, valid):
    if not valid:
        return None
    if not isinstance(canonical_id, str) or not canonical_id.startswith("sha256:"):
        return None
    values = (raw_utility, max_conservation_error)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        return None
    if not all(math.isfinite(float(value)) for value in values):
        return None
    if float(max_conservation_error) > CONSERVATION_TOLERANCE:
        return None
    return {
        "cell_id": CELL_ID,
        "canonical_id": canonical_id,
        "value": float(raw_utility),
    }
