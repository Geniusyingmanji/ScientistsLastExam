"""Weak valid baseline: ships the trivial two-word library for each family.

It stops at the first compatible pair it finds — the smallest honest library anyone
can write down — and presents it as the design. The normalization anchors zero to
exactly this trivial construction.
"""

from __future__ import annotations

import numpy as np

BASES = np.asarray(("A", "C", "G", "T"))


def _pool(rng, family):
    length = family["length"]
    codes = rng.integers(0, 4, size=(4096, length)).astype(np.int8)
    gc = (codes == 1).sum(axis=1) + (codes == 2).sum(axis=1)
    return codes[gc == family["gc_count"]]


def _homopolymer_ok(codes, cap):
    changes = np.diff(codes, axis=1) != 0
    longest = np.ones(len(codes), dtype=np.int64)
    current = np.ones(len(codes), dtype=np.int64)
    for column in range(codes.shape[1] - 1):
        current = np.where(changes[:, column], 1, current + 1)
        longest = np.maximum(longest, current)
    return longest <= cap


def _max_dimer(left_row, right_row):
    """Watson-Crick complementary pairs over all shifted alignments of two rows."""
    length = left_row.shape[1]
    best = 0
    reverse_complement = (3 - right_row)[:, ::-1]
    for offset in range(-(length - 1), length):
        if offset >= 0:
            a = left_row[:, offset:]
            b = reverse_complement[:, :length - offset] if offset else reverse_complement
        else:
            a = left_row[:, :length + offset]
            b = reverse_complement[:, -offset:]
        best = max(best, int((a + b == 3).sum()))
    return best


def _compatible(codes, candidate, family):
    if _max_dimer(candidate, candidate) > family["max_crossdimer"]:
        return False  # self-dimer, checked even against an empty library
    if len(codes) and (codes != candidate).sum(axis=1).min() < family["min_hamming"]:
        return False
    for row in codes:
        if _max_dimer(candidate, row[None, :]) > family["max_crossdimer"]:
            return False
    return True


def _trivial_pair(family, codes):
    codes = codes[_homopolymer_ok(codes, family["max_homopolymer"])]
    first = None
    for candidate in codes:
        row = candidate[None, :]
        if first is None:
            if _compatible(np.empty((0, family["length"]), dtype=np.int8), row, family):
                first = row
        else:
            if _compatible(first, row, family):
                return ["".join(BASES[base] for base in row[0]),
                        "".join(BASES[base] for base in first[0])]
    return None


def build_codeword_library(problem):
    out = {}
    for family in problem["families"]:
        rng = np.random.default_rng(1234 + family["length"])
        out[family["family"]] = _trivial_pair(family, _pool(rng, family))
    return out

