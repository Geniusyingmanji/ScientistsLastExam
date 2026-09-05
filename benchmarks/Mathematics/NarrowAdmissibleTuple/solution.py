"""Initial baseline for NarrowAdmissibleTuple.

Avoids residue 0 modulo every prime p <= k and takes the first k non-negative integers that
survive all of those conditions. This is always admissible (residue 0 mod p is never used, so no
prime's residues can cover all p classes), but wastes a lot of room: it never tries to balance
which residue to avoid per prime, so the surviving integers are sparse and spread out far more
than necessary. Edit this file to do better -- a real sieve should choose which residue to forbid
per prime adaptively, then search for the tightest surviving window.
"""
from __future__ import annotations


def _primes_upto(n: int) -> list[int]:
    if n < 2:
        return []
    is_p = [True] * (n + 1)
    is_p[0] = is_p[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_p[i]:
            for j in range(i * i, n + 1, i):
                is_p[j] = False
    return [i for i in range(2, n + 1) if is_p[i]]


def construct_tuple(k: int):
    """Return a list of k distinct integers forming an admissible k-tuple."""
    primes = _primes_upto(k)
    tup = []
    x = 0
    while len(tup) < k:
        if all(x % p != 0 for p in primes):
            tup.append(x)
        x += 1
    return tup
