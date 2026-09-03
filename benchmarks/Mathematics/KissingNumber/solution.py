"""Initial baseline for KissingNumber (the 2d coordinate axes).

The vectors ±e_i are pairwise orthogonal or antipodal, so they form a valid kissing
configuration of size 2d, far from the Cohn-table records. Edit this file to emit a
larger configuration — root lattices, spherical codes, energy minimisation, or better.
"""


def build_kissing(d: int):
    """Return a list of nonzero length-d vectors with pairwise angle at least 60°."""
    vecs = []
    for i in range(d):
        e = [0] * d
        e[i] = 1
        vecs.append(list(e))
        em = [0] * d
        em[i] = -1
        vecs.append(em)
    return vecs
