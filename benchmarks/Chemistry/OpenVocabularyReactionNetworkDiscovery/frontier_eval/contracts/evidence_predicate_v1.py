"""Evidence gate for an exactly oracle-verified reaction edge."""
from __future__ import annotations

import math

CELL_ID = "verified-open-vocabulary-reaction-edge"


def make_frontier_record(canonical_id, claimed_barrier, oracle_barrier):
    if not isinstance(canonical_id, str) or ":sha256:" not in canonical_id:
        return None
    if not all(isinstance(value, (int, float)) and math.isfinite(value)
               for value in (claimed_barrier, oracle_barrier)):
        return None
    if abs(float(claimed_barrier) - float(oracle_barrier)) > 1.0e-9:
        return None
    return {"cell_id": CELL_ID, "canonical_id": canonical_id}
