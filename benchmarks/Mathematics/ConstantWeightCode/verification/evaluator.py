"""Frozen oracle for ConstantWeightCode (hidden from the agent).

A(29,8,5): the maximum number of 5-element subsets ("blocks") of {0,...,28} such that no
two blocks share more than one point (equivalently, no unordered pair {i,j} appears in more
than one block -- this is exactly the constant-weight binary code of length 29, weight 5,
minimum Hamming distance >= 8). Best-known published lower bound 36 (Bluskov, 2018), upper
bound 39 -- a real, not-yet-closed gap.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

N, W = 29, 5
BASELINE = 5  # a trivial disjoint partition into 5-subsets, see solution.py
SOTA_REF = 36  # Bluskov (2018), Electron. Notes Discrete Math. 65, 31-36
MAX_BLOCKS = 200  # generous headroom above SOTA_REF, bounds the pairwise check cost


def _normalized(value: float, baseline: float, sota: float) -> float:
    denom = sota - baseline
    if denom <= 0:
        return 0.0
    return float(max(0.0, (value - baseline) / denom))


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
    if len(blocks) > MAX_BLOCKS:
        return {"combined_score": 0.0, "valid": 0.0, "reason": "more than %d blocks" % MAX_BLOCKS}
    for b in blocks:
        if len(b) != W:
            return {"combined_score": 0.0, "valid": 0.0, "reason": "each block must have length %d" % W}
        if len(set(b)) != W:
            return {"combined_score": 0.0, "valid": 0.0, "reason": "block entries must be distinct"}
        if any(x < 0 or x >= N for x in b):
            return {"combined_score": 0.0, "valid": 0.0, "reason": "block entries must be in 0..%d" % (N - 1)}
    seen_pairs = set()
    for b in blocks:
        for pair in combinations(sorted(b), 2):
            if pair in seen_pairs:
                return {"combined_score": 0.0, "valid": 0.0,
                        "reason": "pair %s appears in more than one block" % (pair,)}
            seen_pairs.add(pair)
    m = len(blocks)
    score = _normalized(float(m), float(BASELINE), float(SOTA_REF))
    return {
        "combined_score": score,
        "valid": 1.0,
        "num_blocks": m,
        "sota_ref": SOTA_REF,
        "beat_sota": bool(score > 1.0),
    }
