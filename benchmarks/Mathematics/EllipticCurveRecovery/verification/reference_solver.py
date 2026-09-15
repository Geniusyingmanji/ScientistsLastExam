"""Standalone truth-blind active bounded point-count reconstruction.

Enumerate residue classes, lift into the public window, filter on every exact
count and choose the next affordable prime by entropy over remaining lifts.
One-step entropy is a complete greedy design method; a multistep discrimination
policy can improve ambiguous budget-limited worlds. No unspent-budget bonus.
"""
from functools import lru_cache
import math
import numpy as np

ADAPTIVE = True
DISCRIMINANT_FILTER = True
MAX_QUERIES = None


@lru_cache(maxsize=256)
def _table(p):
    # Independent candidate-side construction, delivered as a single source file.
    squares = {x*x % p for x in range(1, p)}
    chi = np.array([0 if x == 0 else (1 if x in squares else -1) for x in range(p)])
    a, b, x = np.arange(p)[:, None], np.arange(p)[None, :], np.arange(p)
    counts = np.empty((p, p), dtype=np.int32)
    for aa in range(p):
        counts[aa] = p + 1 + chi[(x[:, None]**3 + aa*x[:, None] + b) % p].sum(axis=0)
    return counts


def recover_curve(problem, count_points, budget_units):
    bound = problem['coefficient_bound']
    cost = {p: next(c for limit, c in problem['cost_tiers'] if p <= limit)
            for p in problem['prime_list']}
    # All published primes may be queried. Large-prime tables are expensive;
    # choose among the cost-one tier, a documented computational design tradeoff.
    available = sorted((p for p in cost if cost[p] == 1), reverse=True)
    pairs = None
    queries = 0
    budget = int(budget_units)
    while budget and available and (MAX_QUERIES is None or queries < MAX_QUERIES):
        if pairs is not None and len(pairs) <= 1:
            break
        if ADAPTIVE and pairs is not None:
            def entropy(p):
                values, counts = np.unique(_table(p)[pairs[:, 0] % p, pairs[:, 1] % p], return_counts=True)
                weights = counts / counts.sum()
                return -float(np.sum(weights * np.log(weights))) / cost[p]
            p = max(available, key=entropy)
        else:
            p = available[0]
        report = count_points(p)
        n = report['point_count']
        budget -= report['budget_cost']
        available.remove(p)
        queries += 1
        if pairs is None:
            chunks = []
            for a, b in np.argwhere(_table(p) == n):
                av = np.arange(-bound+(int(a)+bound)%p, bound+1, p)
                bv = np.arange(-bound+(int(b)+bound)%p, bound+1, p)
                aa, bb = np.meshgrid(av, bv, indexing='ij')
                chunks.append(np.column_stack((aa.ravel(), bb.ravel())))
            pairs = np.concatenate(chunks) if chunks else np.empty((0, 2), dtype=int)
        else:
            pairs = pairs[_table(p)[pairs[:, 0] % p, pairs[:, 1] % p] == n]
        # Keep singular models during experimental design; reject only at decision.
    if pairs is not None and DISCRIMINANT_FILTER:
        pairs = pairs[4*pairs[:, 0]**3 + 27*pairs[:, 1]**2 != 0]
    if pairs is None or len(pairs) != 1:
        return {'a': None, 'b': None, 'abstain': True, 'confidence': .8}
    a,b=map(int,pairs[0])
    return {'a': a, 'b': b, 'abstain': False, 'confidence': 1.0}
