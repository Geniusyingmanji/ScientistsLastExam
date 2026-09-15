"""Public baseline and conversion tools for approximate four-basis designs.

Candidate entrypoint: build_bases(problem) -> {"bases": [three matrices]}.
Each row-major matrix stores Gaussian integers as [real, imaginary] pairs;
its columns must already be nonzero and exactly orthogonal. I is implicit.
The oracle does NOT run these helpers or repair submitted rays.
"""

import math


def gaussian_integer_gram_schmidt(matrix):
    """Exactly orthogonalize integer-pair columns; return primitive integer rays.

    Apply v <- ||u||² v - u <u,v>, dividing every component by their gcd
    after each projection. Reject linearly dependent inputs. This helper is
    public candidate code, not part of the trusted oracle's validation.
    """
    if type(matrix) is not list or not matrix or len(matrix) > 6:
        raise ValueError("expected square matrix of dimension at most six")
    d = len(matrix)
    for row in matrix:
        if type(row) is not list or len(row) != d:
            raise ValueError("expected square matrix")
        for entry in row:
            if (type(entry) is not list or len(entry) != 2 or
                    any(type(x) is not int for x in entry)):
                raise ValueError("expected Gaussian-integer pairs")
    columns = []
    for j in range(d):
        v = [list(matrix[i][j]) for i in range(d)]
        for u in columns:
            n = sum(a*a+b*b for a,b in u)
            re = sum(a*c+b*e for (a,b),(c,e) in zip(u,v))
            im = sum(a*e-b*c for (a,b),(c,e) in zip(u,v))
            v = [[n*c-(a*re-b*im), n*e-(a*im+b*re)] for (a,b),(c,e) in zip(u,v)]
            common = math.gcd(*(x for pair in v for x in pair))
            if common == 0:
                raise ValueError("linearly dependent columns")
            v = [[a//common,b//common] for a,b in v]
        common = math.gcd(*(x for pair in v for x in pair))
        if common == 0:
            raise ValueError("zero column")
        columns.append([[a//common,b//common] for a,b in v])
    return [[columns[j][i] for j in range(d)] for i in range(d)]


def numerical_to_integer_rays(matrix, bits=32):
    """Round each complex coordinate at 2**bits, then exact Gram–Schmidt.

    Higher precision and conversion may exceed the oracle's 384-bit cap; the
    caller must select precision accordingly. Rounding can destroy rank.
    """
    if type(bits) is not int or not 1 <= bits <= 128:
        raise ValueError("bits must be an integer in [1,128]")
    scale = 1 << bits
    rounded = []
    for row in matrix:
        out = []
        for value in row:
            z = complex(value)
            if not math.isfinite(z.real) or not math.isfinite(z.imag):
                raise ValueError("nonfinite numerical coordinate")
            out.append([round(scale*z.real), round(scale*z.imag)])
        rounded.append(out)
    return gaussian_integer_gram_schmidt(rounded)


def build_bases(problem):
    """Free ASD=0 baseline: all four bases are I."""
    d = problem["dimension"]
    return {"bases": [[[[int(i == j),0] for j in range(d)] for i in range(d)]
                      for _ in range(problem["num_bases"]-1)]}
