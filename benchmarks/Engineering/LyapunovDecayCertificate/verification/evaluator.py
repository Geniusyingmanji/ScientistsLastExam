"""Hidden oracle for LyapunovDecayCertificate.

The product is not a controller. It is a common quadratic Lyapunov certificate
for a switched linear system, and the score is the decay rate the certificate
proves in exact rational arithmetic.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from itertools import combinations

DIFFICULTY = 1
STATE_DIMENSION = 3
MAX_NUMERATOR = 10**6
MAX_DENOMINATOR = 10**6
# Clip scale. Not a published record: a development unit chosen so that the
# identity certificate at the shipped token rate scores exactly zero and a
# sheared quadratic that proves alpha = 1/2 scores about 2/3.
ALPHA_UNIT = Fraction(3, 4)
GRAM_KEYS = (
    ("p11", 0, 0),
    ("p12", 0, 1),
    ("p13", 0, 2),
    ("p22", 1, 1),
    ("p23", 1, 2),
    ("p33", 2, 2),
)


def _ratio(numerator, denominator=1):
    return [int(numerator), int(denominator)]


def _fraction(value, name):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("%s must be an exact integer ratio, not a float" % name)
    if isinstance(value, int):
        result = Fraction(value, 1)
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        numerator, denominator = value
        if isinstance(numerator, bool) or isinstance(denominator, bool):
            raise ValueError("%s entries must be integers" % name)
        if not isinstance(numerator, int) or not isinstance(denominator, int):
            raise ValueError("%s must be [numerator, denominator] integers" % name)
        if denominator == 0:
            raise ValueError("%s has a zero denominator" % name)
        result = Fraction(numerator, denominator)
    else:
        raise ValueError("%s is not an integer or [numerator, denominator] pair" % name)
    if abs(result.numerator) > MAX_NUMERATOR or abs(result.denominator) > MAX_DENOMINATOR:
        raise ValueError("%s exceeds the public magnitude cap" % name)
    return result


def _matrix(raw, name, dimension):
    if not isinstance(raw, (list, tuple)) or len(raw) != dimension:
        raise ValueError("%s must be a %dx%d matrix" % (name, dimension, dimension))
    rows = []
    for i, row in enumerate(raw):
        if not isinstance(row, (list, tuple)) or len(row) != dimension:
            raise ValueError("%s row %d is not length %d" % (name, i, dimension))
        rows.append([
            _fraction(entry, "%s[%d][%d]" % (name, i, j))
            for j, entry in enumerate(row)
        ])
    return rows


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


def _parse_modes(raw):
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("mode_matrices must be a nonempty list")
    return [
        _matrix(item, "mode_matrices[%d]" % index, STATE_DIMENSION)
        for index, item in enumerate(raw)
    ]


def _cell(numerator, denominator=1):
    return _ratio(numerator, denominator)


def _row(*entries):
    return [_cell(*entry) if isinstance(entry, tuple) else _cell(entry) for entry in entries]


# Four switched plants. Each mode is a rational Hurwitz matrix, and the modes of
# one instance are pairwise non-conjugate under the symmetric group (distinct
# characteristic polynomials). They are not a permutation orbit of one matrix:
# C3 averaging does not collapse the common Gram to a cyclic line.
INSTANCES = (
    {
        "name": "plant",
        "mode_matrices": [
            [_row((-1, 5), (4, 5), 0), _row((-2, 5), -1, 0), _row(0, 0, -2)],
            [_row(-2, 0, 0), _row(0, (-1, 4), (3, 4)), _row(0, (-2, 5), -1)],
            [_row(-1, 0, (2, 3)), _row(0, (-3, 2), 0), _row((-1, 3), 0, (-1, 6))],
        ],
    },
    {
        "name": "cascade",
        "mode_matrices": [
            [_row((-1, 4), (5, 6), (1, 5)), _row((-1, 4), -1, (2, 5)), _row(0, 0, (-3, 2))],
            [_row(-1, 0, 0), _row((3, 5), (-1, 5), 0), _row((1, 6), (1, 3), -2)],
            [_row((-3, 2), (1, 8), 0), _row((-1, 4), (-1, 4), (3, 5)), _row(0, (-1, 5), -1)],
            [_row(-2, 0, (3, 5)), _row(0, (-5, 4), 0), _row((-1, 6), (1, 4), (-1, 5))],
        ],
    },
    {
        "name": "mixed",
        "mode_matrices": [
            [_row((-1, 6), (3, 4), 0), _row((-1, 4), -1, 0), _row(0, 0, (-5, 2))],
            [_row((-5, 2), 0, 0), _row(0, (-1, 5), (2, 3)), _row(0, (-1, 4), -1)],
            [_row(-1, 0, (5, 8)), _row(0, -2, 0), _row((-1, 4), 0, (-1, 7))],
        ],
    },
    {
        "name": "sparse",
        "mode_matrices": [
            [_row((-1, 7), (3, 5), 0), _row((-1, 4), -1, 0), _row(0, 0, -2)],
            [_row(-2, 0, 0), _row(0, (-1, 8), (2, 3)), _row(0, (-1, 4), (-5, 4))],
            [_row((-5, 4), 0, (3, 5)), _row(0, -2, 0), _row((-1, 4), 0, (-1, 9))],
        ],
    },
)


def public_instance(instance):
    return {
        "name": instance["name"],
        "mode_matrices": deepcopy(instance["mode_matrices"]),
        "state_dimension": STATE_DIMENSION,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
    }


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    gram = [[Fraction(0) for _ in range(STATE_DIMENSION)] for _ in range(STATE_DIMENSION)]
    for key, row, col in GRAM_KEYS:
        value = _fraction(submission.get(key), key)
        gram[row][col] = value
        gram[col][row] = value
    alpha = _fraction(submission.get("alpha"), "alpha")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    if not _spd(gram):
        raise ValueError("P is not positive definite")
    return gram, alpha


def certificate_holds(modes, gram, alpha):
    for index, mode in enumerate(modes):
        derivative = _add(
            _add(_mul(_transpose(mode), gram), _mul(gram, mode)),
            _scale(gram, alpha),
        )
        if not _nsd(derivative):
            return False, index
    return True, None


BASELINE_ALPHA = Fraction(1, 10000)


def _score_instance(build, instance):
    published = {
        "name": instance["name"],
        "valid": False,
        "proven_alpha": None,
        "instance_score": 0.0,
    }
    try:
        modes = _parse_modes(instance["mode_matrices"])
        gram, alpha = _validate(build(public_instance(instance)))
        holds, bad_mode = certificate_holds(modes, gram, alpha)
        if not holds:
            raise ValueError("Vdot + alpha V is not negative semidefinite on mode %s" % bad_mode)
        score = min(max(0.0, float((alpha - BASELINE_ALPHA) / ALPHA_UNIT)), 1.0)
        published.update({
            "valid": True,
            "proven_alpha": [alpha.numerator, alpha.denominator],
            "instance_score": round(score, 6),
        })
    except Exception as exc:  # noqa: BLE001
        published["reason"] = "%s: %s" % (type(exc).__name__, exc)
    return published


def evaluate(build_lyapunov):
    rows = [_score_instance(build_lyapunov, instance) for instance in INSTANCES]
    valid = [row for row in rows if row["valid"]]
    combined = sum(row["instance_score"] for row in rows) / len(rows)
    return {
        "combined_score": float(combined),
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": len(valid) / len(rows),
        "raw_score": float(combined),
        "instances_with_a_valid_certificate": len(valid),
        "per_instance": rows,
    }
