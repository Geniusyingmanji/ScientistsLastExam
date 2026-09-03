"""Initial baseline for CapSetFrontier (the {0,1}^n hypercube).

The set of all 0/1 vectors is always a valid cap of size 2^n, far from the records in
dimensions 7, 8 and 9. Edit this file to build a bigger cap — product constructions,
Hill caps, FunSearch-style evolutionary search, or better.
"""
import itertools


def build_capset(n: int):
    """Return a list of vectors in {0,1,2}^n forming a cap set (no 3 distinct collinear)."""
    return [list(v) for v in itertools.product([0, 1], repeat=n)]
