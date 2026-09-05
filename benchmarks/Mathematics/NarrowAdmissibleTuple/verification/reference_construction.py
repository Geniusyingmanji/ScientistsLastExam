"""Truth-blind reference construction for NarrowAdmissibleTuple.

Sieves a symmetric window of candidate integers: for each prime p <= k, removes whichever
residue class mod p currently has the fewest surviving candidates (a greedy min-impact rule --
the residue that costs the least density to forbid), doubling the window and retrying if fewer
than k candidates survive. Repeats this with a handful of randomized tie-breaks and prime
orderings, keeping the tightest surviving window of k integers found across all restarts. This is
a real, standard sieve construction technique for this problem, not an exhaustive search: it
reliably beats the naive baseline but does not reach the true optimum, leaving headroom for a
smarter search (better tie-breaking, local swaps after construction, a different sieve order).
"""
from __future__ import annotations

import random


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


def construct_tuple(k: int, restarts: int = 25, window_radius: int = 400, seed: int = 0):
    rng = random.Random(seed)
    primes = _primes_upto(k)
    best = None
    for trial in range(restarts):
        window = window_radius
        while True:
            candidates = set(range(-window, window + 1))
            order = list(primes)
            if trial > 0:
                rng.shuffle(order)
            for p in order:
                buckets: dict[int, list[int]] = {}
                for x in candidates:
                    buckets.setdefault(x % p, []).append(x)
                min_len = min(len(v) for v in buckets.values())
                near_min = [r for r, v in buckets.items() if len(v) <= min_len + max(1, min_len // 10)]
                worst_r = rng.choice(near_min)
                for x in buckets[worst_r]:
                    candidates.discard(x)
            survivors = sorted(candidates)
            if len(survivors) >= k:
                for i in range(len(survivors) - k + 1):
                    span = survivors[i + k - 1] - survivors[i]
                    if best is None or span < best[0]:
                        best = (span, survivors[i:i + k])
                break
            window *= 2
    return best[1]
