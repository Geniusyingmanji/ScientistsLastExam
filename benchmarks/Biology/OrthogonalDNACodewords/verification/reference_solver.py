"""Truth-blind reference witness: seeded greedy construction.

Deterministic: each restart draws a 40,000-word pool with the family's GC content
and homopolymer cap, shuffles it deterministically, and greedily accepts
compatible words in vectorized blocks; the best restart is kept. With
restarts=240, seed=0 it reaches 28 words (dna16) and 27 (dna12). The frozen
witness sizes (dna16 32, dna12 29) require an additional removal-repair phase
that the shipped reference deliberately omits, so the reference scores 0.896
against the witness anchor by design; see references/known_best.md.
"""

from __future__ import annotations

import numpy as np

MASTER_SEED = 0
POOL_SIZE = 40000
CHUNK = 256
DEFAULT_RESTARTS = 40
BASES = np.asarray(("A", "C", "G", "T"))


def _homopolymer_ok(codes, cap):
    changes = np.diff(codes, axis=1) != 0
    longest = np.ones(len(codes), dtype=np.int64)
    current = np.ones(len(codes), dtype=np.int64)
    for column in range(codes.shape[1] - 1):
        current = np.where(changes[:, column], 1, current + 1)
        longest = np.maximum(longest, current)
    return longest <= cap


def _candidate_pool(rng, family, pool_size):
    length = family["length"]
    codes = rng.integers(0, 4, size=(pool_size, length)).astype(np.int8)
    gc = (codes == 1).sum(axis=1) + (codes == 2).sum(axis=1)
    codes = codes[gc == family["gc_count"]]
    if len(codes) == 0:
        return codes
    return codes[_homopolymer_ok(codes, family["max_homopolymer"])]


def _compatible_mask(accepted, chunk, family):
    """Vectorized compatibility of every chunk row against the accepted library.

    A row must also pass the self-dimer cap against its own reverse complement —
    a constraint that exists even before the library holds any word.
    """
    mask = np.ones(len(chunk), dtype=bool)
    length = chunk.shape[1]
    self_reverse = (3 - chunk)[:, ::-1]
    for offset in range(-(length - 1), length):
        if offset >= 0:
            left = chunk[:, offset:]
            right = self_reverse[:, :length - offset] if offset else self_reverse
        else:
            left = chunk[:, :length + offset]
            right = self_reverse[:, -offset:]
        matches = (left + right == 3).sum(axis=1)
        mask &= matches <= family["max_crossdimer"]
    if len(accepted):
        hamming = (chunk[:, None, :] != accepted[None, :, :]).sum(axis=2).min(axis=1)
        mask &= hamming >= family["min_hamming"]
        reverse_complement = (3 - accepted)[:, ::-1]
        for offset in range(-(length - 1), length):
            if offset >= 0:
                left = chunk[:, offset:]
                right = reverse_complement[:, :length - offset] if offset else reverse_complement
            else:
                left = chunk[:, :length + offset]
                right = reverse_complement[:, -offset:]
            matches = (left[:, None, :] + right[None, :, :] == 3).sum(axis=2)
            mask &= matches.max(axis=1) <= family["max_crossdimer"]
    return mask


def _build(family, restarts, seed):
    accepted_rows = []
    master = np.random.default_rng(MASTER_SEED + 101 * int(seed))
    for _restart in range(int(restarts)):
        rng = np.random.default_rng(master.integers(1 << 31))
        pool = _candidate_pool(rng, family, POOL_SIZE)
        if len(pool) < 2:
            continue
        pool = pool[rng.permutation(len(pool))]
        accepted = np.empty((0, family["length"]), dtype=np.int8)
        for start in range(0, len(pool), CHUNK):
            chunk = pool[start:start + CHUNK]
            position = 0
            while position < len(chunk):
                mask = _compatible_mask(accepted, chunk[position:], family)
                hits = np.nonzero(mask)[0]
                if not len(hits):
                    break
                first = hits[0]
                accepted = np.concatenate((accepted, chunk[position + first][None, :]),
                                          axis=0)
                position += first + 1
        if len(accepted) > len(accepted_rows):
            accepted_rows = [row for row in accepted.tolist()]
        if len(accepted_rows) >= family["max_library"]:
            break
    codes = np.asarray(accepted_rows, dtype=np.int8)
    if not len(codes):
        return []
    return ["".join(BASES[base] for base in row) for row in codes.tolist()]


def build_codeword_library(problem, restarts=DEFAULT_RESTARTS, seed=0):
    return {family["family"]: _build(family, restarts, seed)
            for family in problem["families"]}
