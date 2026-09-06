"""Hidden oracle for LyapunovDecayCertificate.

The product is not a controller. It is a common quadratic Lyapunov certificate
for a switched linear system, and the score is the decay rate the certificate
proves in exact rational arithmetic.
"""
from __future__ import annotations

from fractions import Fraction

DIFFICULTY = 1
MAX_NUMERATOR = 10**6
MAX_DENOMINATOR = 10**6
# Clip scale. Not a published record: a development unit chosen so that the
# identity certificate at the shipped token rate scores exactly zero and a
# sheared quadratic that proves alpha = 1/2 scores about 2/3.
ALPHA_UNIT = Fraction(3, 4)


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


def _matrix(raw, name):
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError("%s must be a 2x2 matrix" % name)
    rows = []
    for i, row in enumerate(raw):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError("%s row %d is not length 2" % (name, i))
        rows.append([
            _fraction(row[0], "%s[%d][0]" % (name, i)),
            _fraction(row[1], "%s[%d][1]" % (name, i)),
        ])
    return rows


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


def _parse_modes(raw):
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("mode_matrices must be a nonempty list")
    return [_matrix(item, "mode_matrices[%d]" % index) for index, item in enumerate(raw)]


INSTANCES = (
    {
        "name": "shear",
        "mode_matrices": [
            [[_ratio(-4), _ratio(21, 10)], [_ratio(0), _ratio(-3, 10)]],
        ],
    },
    {
        "name": "pair",
        "mode_matrices": [
            [[_ratio(-4), _ratio(21, 10)], [_ratio(0), _ratio(-3, 10)]],
            [[_ratio(-3, 10), _ratio(0)], [_ratio(21, 10), _ratio(-4)]],
        ],
    },
    {
        "name": "three",
        "mode_matrices": [
            [[_ratio(-4), _ratio(21, 10)], [_ratio(0), _ratio(-3, 10)]],
            [[_ratio(-3, 10), _ratio(0)], [_ratio(21, 10), _ratio(-4)]],
            [[_ratio(-2), _ratio(4, 5)], [_ratio(-1, 5), _ratio(-3, 5)]],
        ],
    },
    {
        "name": "mid",
        "mode_matrices": [
            [[_ratio(-3), _ratio(17, 10)], [_ratio(0), _ratio(-2, 5)]],
            [[_ratio(-2, 5), _ratio(0)], [_ratio(17, 10), _ratio(-3)]],
        ],
    },
)


def public_instance(instance):
    return {
        "name": instance["name"],
        "mode_matrices": instance["mode_matrices"],
        "state_dimension": 2,
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
    }


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    p11 = _fraction(submission.get("p11"), "p11")
    p12 = _fraction(submission.get("p12"), "p12")
    p22 = _fraction(submission.get("p22"), "p22")
    alpha = _fraction(submission.get("alpha"), "alpha")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    gram = [[p11, p12], [p12, p22]]
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
