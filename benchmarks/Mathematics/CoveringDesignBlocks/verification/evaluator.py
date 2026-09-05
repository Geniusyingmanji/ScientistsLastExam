"""Frozen oracle for CoveringDesignBlocks (hidden from the agent).

The covering design C(13,7,4): a collection of 7-element blocks of {0,...,12} such that
every 4-element subset is contained in at least one block. The objective is to use as few
blocks as possible. The La Jolla Covering Repository's explicit best-known cover uses 30
blocks (28 <= C(13,7,4) <= 30); this is a lower-bound-style record without a matching
achievability proof at 28, so real headroom exists between the naive baseline, this
reference, and the published witness.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

V, K, T = 13, 7, 4
BASELINE = 73  # a weak randomized greedy (see references/known_best.md), measured
SOTA_REF = 30  # La Jolla Covering Repository explicit 30-block cover
MAX_BLOCKS = 500  # generous headroom below BASELINE, bounds the coverage check cost


def _normalized_block_count_score(value: float, baseline: float, sota: float) -> float:
    """0 at baseline, 1 at sota, unbounded beyond. Fewer blocks is better here, the mirror
    image of this codebase's usual `_normalized` convention -- named differently on purpose,
    matching Mathematics/NarrowAdmissibleTuple's `_normalized_diameter_score`."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - value) / denom))


def evaluate(construct_blocks) -> dict:
    try:
        raw = construct_blocks()
    except Exception as exc:  # noqa: BLE001
        return {"combined_score": 0.0, "valid": 0.0, "reason": "raised: %s" % exc}
    if isinstance(raw, dict):
        raw = raw.get("blocks")
    try:
        blocks = [tuple(int(x) for x in b) for b in raw]
    except Exception as exc:  # noqa: BLE001
        return {"combined_score": 0.0, "valid": 0.0, "reason": "not a list of blocks: %s" % exc}
    if not blocks:
        return {"combined_score": 0.0, "valid": 0.0, "reason": "expected at least one block"}
    if len(blocks) > MAX_BLOCKS:
        return {"combined_score": 0.0, "valid": 0.0, "reason": "more than %d blocks" % MAX_BLOCKS}
    for b in blocks:
        if len(b) != K:
            return {"combined_score": 0.0, "valid": 0.0, "reason": "each block must have length %d" % K}
        if len(set(b)) != K:
            return {"combined_score": 0.0, "valid": 0.0, "reason": "block entries must be distinct"}
        if any(x < 0 or x >= V for x in b):
            return {"combined_score": 0.0, "valid": 0.0, "reason": "block entries must be in 0..%d" % (V - 1)}
    covered = set()
    for b in blocks:
        for quad in combinations(sorted(b), T):
            covered.add(quad)
    all_quads = set(combinations(range(V), T))
    if not all_quads.issubset(covered):
        missing = next(iter(all_quads - covered))
        return {"combined_score": 0.0, "valid": 0.0,
                "reason": "4-subset %s is not covered by any block" % (missing,)}
    m = len(blocks)
    score = _normalized_block_count_score(float(m), float(BASELINE), float(SOTA_REF))
    return {
        "combined_score": score,
        "valid": 1.0,
        "num_blocks": m,
        "sota_ref": SOTA_REF,
        "beat_sota": bool(score > 1.0),
    }
