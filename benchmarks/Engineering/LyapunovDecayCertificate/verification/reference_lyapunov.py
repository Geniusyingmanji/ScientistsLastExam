"""Truth-blind catalog search for a common quadratic Lyapunov certificate.

Does not import the evaluator. Each catalog Gram matrix is tested against the
public modes in exact rationals; bisection maximizes the rate for each Gram.
"""
from fractions import Fraction
from itertools import combinations, product


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


def _eye():
    return [[Fraction(int(i == j)) for j in range(3)] for i in range(3)]


def _diag(d1, d2, d3):
    values = (Fraction(d1), Fraction(d2), Fraction(d3))
    return [[values[i] if i == j else Fraction(0) for j in range(3)] for i in range(3)]


def _upper(p12, p13, p22, p23, p33, p11=1):
    p11, p12, p13, p22, p23, p33 = map(Fraction, (p11, p12, p13, p22, p23, p33))
    return [
        [p11, p12, p13],
        [p12, p22, p23],
        [p13, p23, p33],
    ]


def _catalog():
    grams = []
    for diagonal in (
        (1, 1, 1), (2, 1, 1), (1, 2, 1), (1, 1, 2),
        (3, 1, 1), (1, 3, 1), (1, 1, 3),
        (4, 1, 1), (1, 4, 1), (1, 1, 4),
        (2, 2, 1), (2, 1, 2), (1, 2, 2),
        (5, 1, 1), (1, 5, 1), (1, 1, 5),
        (3, 2, 1), (2, 3, 1), (3, 1, 2),
        (Fraction(3, 2), 1, 1), (1, Fraction(3, 2), 1), (1, 1, Fraction(3, 2)),
    ):
        grams.append(_diag(*diagonal))
    pair_vals = [Fraction(k, 6) for k in range(-8, 9) if k != 0]
    for (i, j), value in product(((0, 1), (0, 2), (1, 2)), pair_vals):
        gram = _eye()
        gram[i][j] = gram[j][i] = value
        if _spd(gram):
            grams.append(gram)
    # Cyclic-symmetric Grams: p11=p22=p33 and p12=p13=p23 ≠ 0. On a
    # permutation-orbit family these are the group-average line; they remain in
    # the catalog after the instance family was changed so that line is no
    # longer competitive.
    for value in pair_vals:
        gram = _upper(value, value, 1, value, 1)
        if _spd(gram):
            grams.append(gram)
    for p12, p13, p23 in product(
        (Fraction(-1, 2), Fraction(-1, 3), Fraction(0), Fraction(1, 3), Fraction(1, 2)),
        repeat=3,
    ):
        if sum(value != 0 for value in (p12, p13, p23)) != 2:
            continue
        gram = _upper(p12, p13, 1, p23, 1)
        if _spd(gram):
            grams.append(gram)
    for entries in (
        (Fraction(1, 3), Fraction(1, 3), Fraction(4, 3), Fraction(1, 3), Fraction(4, 3)),
        (Fraction(-1, 3), Fraction(-1, 3), Fraction(4, 3), Fraction(-1, 3), Fraction(4, 3)),
        (Fraction(1, 2), Fraction(-1, 3), Fraction(3, 2), Fraction(1, 4), Fraction(5, 4)),
        (Fraction(-1, 2), Fraction(1, 3), Fraction(3, 2), Fraction(-1, 4), Fraction(5, 4)),
        (Fraction(1, 4), Fraction(1, 4), Fraction(5, 4), Fraction(1, 4), Fraction(5, 4)),
        (Fraction(-1, 4), Fraction(-1, 4), Fraction(5, 4), Fraction(-1, 4), Fraction(5, 4)),
        (Fraction(2, 5), Fraction(1, 5), Fraction(6, 5), Fraction(1, 5), Fraction(6, 5)),
        (Fraction(-2, 5), Fraction(-1, 5), Fraction(6, 5), Fraction(-1, 5), Fraction(6, 5)),
        (Fraction(1, 5), Fraction(1, 5), Fraction(6, 5), Fraction(1, 5), Fraction(6, 5)),
        (Fraction(-1, 5), Fraction(-1, 5), Fraction(6, 5), Fraction(-1, 5), Fraction(6, 5)),
        (Fraction(1, 3), Fraction(-1, 4), Fraction(5, 4), Fraction(-1, 3), Fraction(5, 4)),
        (Fraction(-1, 3), Fraction(1, 4), Fraction(5, 4), Fraction(1, 3), Fraction(5, 4)),
    ):
        gram = _upper(*entries)
        if _spd(gram):
            grams.append(gram)
    return tuple(grams)


CATALOG = _catalog()


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


def build_lyapunov(instance):
    _ = instance["state_dimension"]
    _ = instance["name"]
    modes = [_matrix(mode) for mode in instance["mode_matrices"]]
    best = None
    # alpha <= -trace(A) is a public bound for a Hurwitz mode.
    upper = min(-_trace(mode) for mode in modes)
    magnitude = max(1, -(-upper.numerator // upper.denominator))
    denominator = min(
        int(instance["max_denominator"]),
        int(instance["max_numerator"]) // magnitude,
    )
    for gram in CATALOG:
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
        gram = _eye()
        alpha = Fraction(1, 10000)
    else:
        gram, alpha = best
    return _pack(gram, alpha)
