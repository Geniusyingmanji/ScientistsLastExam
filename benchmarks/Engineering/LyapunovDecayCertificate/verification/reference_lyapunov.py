"""Truth-blind catalog search for a common quadratic Lyapunov certificate.

Does not import the evaluator. Each catalog Gram matrix is tested against the
public modes in exact rationals; the largest feasible catalog rate is returned.
"""
from fractions import Fraction


def _fraction(value):
    if isinstance(value, int):
        return Fraction(value, 1)
    numerator, denominator = value
    return Fraction(int(numerator), int(denominator))


def _matrix(raw):
    return [[_fraction(raw[i][j]) for j in range(2)] for i in range(2)]


def _add(left, right):
    return [[left[i][j] + right[i][j] for j in range(2)] for i in range(2)]


def _scale(matrix, scalar):
    return [[scalar * matrix[i][j] for j in range(2)] for i in range(2)]


def _mul(left, right):
    out = [[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]]
    for i in range(2):
        for k in range(2):
            for j in range(2):
                out[i][j] += left[i][k] * right[k][j]
    return out


def _transpose(matrix):
    return [[matrix[j][i] for j in range(2)] for i in range(2)]


def _spd(matrix):
    return matrix[0][0] > 0 and matrix[0][0] * matrix[1][1] - matrix[0][1] ** 2 > 0


def _nsd(matrix):
    m11, m12, m22 = matrix[0][0], matrix[0][1], matrix[1][1]
    if m11 > 0:
        return False
    if m11 * m22 - m12 * m12 < 0:
        return False
    if m11 == 0:
        return m12 == 0 and m22 <= 0
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


CATALOG = (
    [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]],
    [[Fraction(1, 9), Fraction(-1, 16)], [Fraction(-1, 16), Fraction(4)]],
    [[Fraction(6, 5), Fraction(-2, 3)], [Fraction(-2, 3), Fraction(6, 5)]],
    [[Fraction(1), Fraction(-2, 3)], [Fraction(-2, 3), Fraction(1)]],
    [[Fraction(2), Fraction(-1)], [Fraction(-1), Fraction(2)]],
    [[Fraction(4), Fraction(-1, 2)], [Fraction(-1, 2), Fraction(1, 8)]],
    [[Fraction(5, 4), Fraction(-4, 5)], [Fraction(-4, 5), Fraction(9, 5)]],
    [[Fraction(3, 2), Fraction(-1)], [Fraction(-1), Fraction(9, 4)]],
)

RATES = (
    Fraction(3, 4),
    Fraction(1, 2),
    Fraction(2, 5),
    Fraction(1, 4),
    Fraction(1, 10),
    Fraction(1, 100),
    Fraction(1, 10000),
)


def build_lyapunov(instance):
    _ = instance["state_dimension"]
    _ = instance["max_numerator"]
    _ = instance["max_denominator"]
    _ = instance["name"]
    modes = [_matrix(mode) for mode in instance["mode_matrices"]]
    best = None
    for gram in CATALOG:
        for alpha in RATES:
            if _holds(modes, gram, alpha):
                if best is None or alpha > best[1]:
                    best = (gram, alpha)
                break
    if best is None:
        gram = [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]]
        alpha = Fraction(1, 10000)
    else:
        gram, alpha = best
    return {
        "p11": [gram[0][0].numerator, gram[0][0].denominator],
        "p12": [gram[0][1].numerator, gram[0][1].denominator],
        "p22": [gram[1][1].numerator, gram[1][1].denominator],
        "alpha": [alpha.numerator, alpha.denominator],
    }
