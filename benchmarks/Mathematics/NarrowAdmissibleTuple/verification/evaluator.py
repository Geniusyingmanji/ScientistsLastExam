"""Frozen oracle for NarrowAdmissibleTuple (hidden from the agent).

A finite set of k distinct integers H = {h_1, ..., h_k} is an admissible k-tuple if, for every
prime p, the residues {h_i mod p} do not cover all p residue classes. (For p > k this holds
automatically, since k values cannot cover p > k classes, so only primes p <= k need checking --
an exact, finite, deterministic computation.) The Maynard-Tao theorem (2013-2014) says that for k
large enough (given a supportable level of distribution), any admissible k-tuple contains at least
two primes infinitely often; the diameter (max - min) of the tuple used then upper-bounds a prime
gap that recurs infinitely often. This is the exact combinatorial object the Polymath8b project
computed and published: the admissible 50-tuple of diameter 246 is precisely what gives
"there are infinitely many primes p, q with p - q <= 246" (arXiv:1409.8361).

The score is uncapped relative to that published record: a valid k-tuple with a smaller diameter
than the cited witness is a real, checkable, exact improvement on a still-open problem, not a
benchmark artifact -- exactly as it would be if submitted to the Polymath8 tracking page.
"""
from __future__ import annotations

import numpy as np

# k -> (naive-sieve baseline diameter, published/tracked best-known diameter, citation)
# See references/known_best.md for exactly which of these are direct primary-source quotes
# versus a secondary-source figure this task could not independently verify in a primary source.
SIZES = {
    50: {"baseline": 310, "sota_ref": 246},
    54: {"baseline": 346, "sota_ref": 270},
}
MAX_DIAMETER_SEARCH = 200_000  # reject absurdly large diameters without expensive prime work


def _sieve_primes_upto(n: int) -> list[int]:
    if n < 2:
        return []
    is_p = [True] * (n + 1)
    is_p[0] = is_p[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_p[i]:
            for j in range(i * i, n + 1, i):
                is_p[j] = False
    return [i for i in range(2, n + 1) if is_p[i]]


def is_admissible(tup: list[int], k: int) -> tuple[bool, int | None]:
    """Check every prime p <= k; return (True, None) or (False, offending_prime)."""
    primes = _sieve_primes_upto(k)
    for p in primes:
        residues = set(x % p for x in tup)
        if len(residues) >= p:
            return False, p
    return True, None


def _normalized_diameter_score(diameter: float, baseline: float, sota: float) -> float:
    """0 at the baseline diameter, 1 at the published sota diameter, unbounded beyond it.

    Diameter is lower-is-better here, the mirror image of this codebase's usual `_normalized`
    convention (higher value, baseline < sota) -- named differently on purpose so a generic
    cross-task check for `_normalized(value, baseline, sota)` with higher-is-better semantics does
    not mistake this inverted convention for that one."""
    denom = baseline - sota
    if denom <= 0:
        return 0.0
    return float(max(0.0, (baseline - diameter) / denom))


def score_size(k: int, ref: dict, construct_tuple) -> dict:
    try:
        raw = construct_tuple(k)
    except Exception as exc:  # noqa: BLE001
        return {"k": k, "valid": False, "reason": "raised: %s" % exc, "score": 0.0}
    try:
        tup = [int(x) for x in raw]
    except Exception as exc:  # noqa: BLE001
        return {"k": k, "valid": False, "reason": "not a list of integers: %s" % exc, "score": 0.0}
    if len(tup) != k:
        return {"k": k, "valid": False, "reason": "expected exactly %d integers, got %d" % (k, len(tup)), "score": 0.0}
    if len(set(tup)) != k:
        return {"k": k, "valid": False, "reason": "tuple entries must be distinct", "score": 0.0}
    diameter = max(tup) - min(tup)
    if diameter <= 0 or diameter > MAX_DIAMETER_SEARCH:
        return {"k": k, "valid": False, "reason": "diameter out of accepted range", "score": 0.0}
    ok, bad_prime = is_admissible(tup, k)
    if not ok:
        return {
            "k": k, "valid": False,
            "reason": "not admissible: residues mod %d cover all %d classes" % (bad_prime, bad_prime),
            "diameter": diameter, "score": 0.0,
        }
    base, sota = ref["baseline"], ref["sota_ref"]
    return {
        "k": k, "valid": True, "diameter": diameter, "sota_ref": sota,
        "score": _normalized_diameter_score(float(diameter), float(base), float(sota)),
    }


def evaluate(construct_tuple) -> dict:
    per = [score_size(k, ref, construct_tuple) for k, ref in SIZES.items()]
    scores = [r["score"] for r in per]
    n_valid = sum(1 for r in per if r.get("valid"))
    return {
        "combined_score": float(np.mean(scores)) if scores else 0.0,
        "valid": 1.0 if n_valid == len(SIZES) else 0.0,
        "feasibility_rate": n_valid / len(SIZES),
        "beat_sota": bool(any(r.get("score", 0.0) > 1.0 for r in per)),
        "per_size": per,
    }
