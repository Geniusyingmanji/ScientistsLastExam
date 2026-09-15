"""Two-parameter block-diagonal Gram scan used as a checkpoint-12 probe.

P = [[1, b, 0], [b, d, 0], [0, 0, 1]] with exact rational bisection of alpha.
This is the 3-by-3 analogue of the 2-by-2 (b, d) grid that beat the previous
reference. It reads public modes only.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations

# These public exact-arithmetic helpers are embedded because candidate files
# are mounted individually; the sibling verification directory is not visible.
def _fraction(value):
    if isinstance(value, int):
        return Fraction(value, 1)
    numerator, denominator = value
    return Fraction(int(numerator), int(denominator))

def _matrix(raw):
    n = len(raw)
    return [[_fraction(raw[i][j]) for j in range(n)] for i in range(n)]

def _add(left, right):
    n = len(left)
    return [[left[i][j] + right[i][j] for j in range(n)] for i in range(n)]

def _scale(matrix, scalar):
    return [[scalar * value for value in row] for row in matrix]

def _mul(left, right):
    n = len(left)
    out = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for k in range(n):
            left_ik = left[i][k]
            if left_ik == 0:
                continue
            for j in range(n):
                out[i][j] += left_ik * right[k][j]
    return out

def _transpose(matrix):
    n = len(matrix)
    return [[matrix[j][i] for j in range(n)] for i in range(n)]

def _det(matrix):
    n = len(matrix)
    work = [row[:] for row in matrix]
    sign = Fraction(1)
    for i in range(n):
        pivot = next((row for row in range(i, n) if work[row][i] != 0), None)
        if pivot is None:
            return Fraction(0)
        if pivot != i:
            work[i], work[pivot] = work[pivot], work[i]
            sign = -sign
        sign *= work[i][i]
        inverse = 1 / work[i][i]
        for row in range(i + 1, n):
            if work[row][i] == 0:
                continue
            factor = work[row][i] * inverse
            for col in range(i, n):
                work[row][col] -= factor * work[i][col]
    return sign

def _principal(matrix, index):
    return [[matrix[i][j] for j in index] for i in index]

def _spd(matrix):
    n = len(matrix)
    for k in range(1, n + 1):
        if _det([row[:k] for row in matrix[:k]]) <= 0:
            return False
    return True

def _nsd(matrix):
    n = len(matrix)
    negated = [[-matrix[i][j] for j in range(n)] for i in range(n)]
    for k in range(1, n + 1):
        for index in combinations(range(n), k):
            if _det(_principal(negated, index)) < 0:
                return False
    return True

def _holds(modes, gram, alpha):
    if not _spd(gram):
        return False
    for mode in modes:
        derivative = _add(
            _add(_mul(_transpose(mode), gram), _mul(gram, mode)),
            _scale(gram, alpha),
        )
        if not _nsd(derivative):
            return False
    return True

def _upper(p12, p13, p22, p23, p33, p11=1):
    p11, p12, p13, p22, p23, p33 = map(Fraction, (p11, p12, p13, p22, p23, p33))
    return [
        [p11, p12, p13],
        [p12, p22, p23],
        [p13, p23, p33],
    ]

def _trace(matrix):
    return sum(matrix[i][i] for i in range(len(matrix)))

def _pack(gram, alpha):
    return {
        "p11": [gram[0][0].numerator, gram[0][0].denominator],
        "p12": [gram[0][1].numerator, gram[0][1].denominator],
        "p13": [gram[0][2].numerator, gram[0][2].denominator],
        "p22": [gram[1][1].numerator, gram[1][1].denominator],
        "p23": [gram[1][2].numerator, gram[1][2].denominator],
        "p33": [gram[2][2].numerator, gram[2][2].denominator],
        "alpha": [alpha.numerator, alpha.denominator],
    }

B_VALS = tuple(Fraction(k, 10) for k in range(-12, 13))
D_VALS = tuple(Fraction(k, 10) for k in range(2, 31))


def build_lyapunov(instance):
    modes = [_matrix(mode) for mode in instance["mode_matrices"]]
    upper = min(-_trace(mode) for mode in modes)
    denominator = min(50, int(instance.get("max_denominator", 50)))
    best = None
    for b in B_VALS:
        for d in D_VALS:
            gram = _upper(b, 0, d, 0, 1)
            if not _holds(modes, gram, Fraction(0)):
                continue
            low, high = 0, int(upper * denominator) + 1
            while high - low > 1:
                middle = (low + high) // 2
                if _holds(modes, gram, Fraction(middle, denominator)):
                    low = middle
                else:
                    high = middle
            alpha = Fraction(low, denominator)
            if alpha > 0 and (best is None or alpha > best[1]):
                best = (gram, alpha)
    if best is None:
        gram = _upper(0, 0, 1, 0, 1)
        alpha = Fraction(1, 10000)
    else:
        gram, alpha = best
    return _pack(gram, alpha)
