"""Exact bounded compatibility oracle, independent of hidden world labels.

This trusted module recomputes evidence from the *actual* purchased transcript.
It is not delivered to the candidate. No reference-solver code is imported here.
"""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=256)
def count_table(p):
    residues = np.arange(p, dtype=np.int64)
    chi = np.full(p, -1, dtype=np.int16)
    chi[(residues * residues) % p] = 1
    chi[0] = 0
    result = np.full((p, p), p + 1, dtype=np.int32)
    for x in range(p):
        result += chi[(x**3 + residues[:, None] * x + residues[None, :]) % p]
    result.flags.writeable = False
    return result


def compatible_pairs(transcript, bound):
    """Enumerate all bounded lifts, pruning on exact observed counts.

    Two distinct primes suffice for efficient residue enumeration, not for a
    discovery certificate. Under two primes return None (uninformative).
    """
    return _compatible_cached(tuple(sorted(dict(transcript).items())), bound)


@lru_cache(maxsize=128)
def _compatible_cached(transcript, bound):
    reports = dict(transcript)
    if len(reports) < 2:
        return None
    ordered = sorted(reports, reverse=True)
    p = ordered[0]
    residues = np.argwhere(count_table(p) == reports[p])
    chunks = []
    for a, b in residues:
        av = np.arange(-bound + (int(a) + bound) % p, bound + 1, p)
        bv = np.arange(-bound + (int(b) + bound) % p, bound + 1, p)
        aa, bb = np.meshgrid(av, bv, indexing='ij')
        chunks.append(np.column_stack((aa.ravel(), bb.ravel())))
    pairs = np.concatenate(chunks) if chunks else np.empty((0, 2), dtype=np.int64)
    for q in ordered[1:]:
        pairs = pairs[count_table(q)[pairs[:, 0] % q, pairs[:, 1] % q] == reports[q]]
        if not len(pairs):
            break
    pairs.flags.writeable = False
    return pairs


def nonsingular(pairs):
    return pairs[4 * pairs[:, 0] ** 3 + 27 * pairs[:, 1] ** 2 != 0]
