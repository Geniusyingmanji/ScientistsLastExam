"""Hidden oracle for AffineLoopRankingCertificate.

The product is not a trace of one execution. It is a linear ranking function
with Farkas multipliers that prove every guard-satisfying integer state
descends by a uniform rational amount.
"""
from __future__ import annotations

from fractions import Fraction

DIFFICULTY = 1
MAX_NUMERATOR = 10**6
MAX_DENOMINATOR = 10**6
# Clip scale, not a published record. A token delta on e_1 scores near zero;
# putting the whole 1-norm on the fastest coordinate of cut3 proves delta = 4
# and clips at 1.
DELTA_UNIT = Fraction(3, 1)


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


def _vector(raw, name, dimension):
    if not isinstance(raw, (list, tuple)) or len(raw) != dimension:
        raise ValueError("%s must be a length-%d vector" % (name, dimension))
    return [_fraction(item, "%s[%d]" % (name, index)) for index, item in enumerate(raw)]


def _matrix(raw, name, rows, cols):
    if not isinstance(raw, (list, tuple)) or len(raw) != rows:
        raise ValueError("%s must be a %dx%d matrix" % (name, rows, cols))
    return [_vector(row, "%s[%d]" % (name, index), cols) for index, row in enumerate(raw)]


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _matvec_left(matrix, vector):
    """r |-> A^T r, i.e. coordinate j is sum_k matrix[k][j] * vector[k]."""
    cols = len(matrix[0])
    return [
        sum(matrix[k][j] * vector[k] for k in range(len(vector)))
        for j in range(cols)
    ]


def _one_norm(vector):
    return sum(abs(item) for item in vector)


def _farkas(linear, constant, guards, lambdas):
    if len(lambdas) != len(guards):
        raise ValueError("lambda count must match the guard count")
    acc = [Fraction(0)] * len(linear)
    offset = Fraction(0)
    for lam, guard in zip(lambdas, guards):
        if lam < 0:
            return False
        slope, intercept = guard
        for index in range(len(linear)):
            acc[index] += lam * slope[index]
        offset += lam * intercept
    return acc == list(linear) and constant - offset >= 0


def _parse_guards(raw, dimension):
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("guards must be a nonempty list")
    parsed = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("guards[%d] must be a mapping" % index)
        slope = _vector(item.get("g"), "guards[%d].g" % index, dimension)
        intercept = _fraction(item.get("d"), "guards[%d].d" % index)
        parsed.append((slope, intercept))
    return parsed


def _axis_guard(dimension, index):
    slope = [_ratio(1 if j == index else 0) for j in range(dimension)]
    return {"g": slope, "d": _ratio(-1)}


def _identity(dimension):
    return [
        [_ratio(1 if i == j else 0) for j in range(dimension)]
        for i in range(dimension)
    ]


INSTANCES = (
    {
        "name": "cut_x",
        "dimension": 2,
        "guards": [_axis_guard(2, 0), _axis_guard(2, 1)],
        "A": _identity(2),
        "b": [_ratio(-2), _ratio(-1)],
    },
    {
        "name": "cut_y",
        "dimension": 2,
        "guards": [_axis_guard(2, 0), _axis_guard(2, 1)],
        "A": _identity(2),
        "b": [_ratio(-1), _ratio(-3)],
    },
    {
        "name": "skew",
        "dimension": 2,
        "guards": [
            _axis_guard(2, 0),
            {"g": [_ratio(2), _ratio(1)], "d": _ratio(-3)},
        ],
        "A": _identity(2),
        "b": [_ratio(-1), _ratio(1)],
    },
    {
        "name": "cut3",
        "dimension": 3,
        "guards": [_axis_guard(3, 0), _axis_guard(3, 1), _axis_guard(3, 2)],
        "A": _identity(3),
        "b": [_ratio(-4), _ratio(-1), _ratio(-1)],
    },
)


def public_instance(instance):
    return {
        "name": instance["name"],
        "dimension": instance["dimension"],
        "guards": instance["guards"],
        "A": instance["A"],
        "b": instance["b"],
        "max_numerator": MAX_NUMERATOR,
        "max_denominator": MAX_DENOMINATOR,
    }


def _validate(submission, dimension, n_guards):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    ranking = _vector(submission.get("r"), "r", dimension)
    shift = _fraction(submission.get("s"), "s")
    delta = _fraction(submission.get("delta"), "delta")
    if delta <= 0:
        raise ValueError("delta must be positive")
    if _one_norm(ranking) != 1:
        raise ValueError("r must have exact 1-norm 1")
    nonneg = _vector(submission.get("nonneg_lambdas"), "nonneg_lambdas", n_guards)
    decrease = _vector(submission.get("decrease_lambdas"), "decrease_lambdas", n_guards)
    return ranking, shift, delta, nonneg, decrease


def certificate_holds(guards, update_a, update_b, ranking, shift, delta, nonneg, decrease):
    if not _farkas(ranking, shift, guards, nonneg):
        return False, "nonnegativity"
    linear_dec = [
        ranking[j] - _matvec_left(update_a, ranking)[j]
        for j in range(len(ranking))
    ]
    constant_dec = -_dot(ranking, update_b) - delta
    if not _farkas(linear_dec, constant_dec, guards, decrease):
        return False, "decrease"
    return True, None


def _score_instance(build, instance):
    published = {
        "name": instance["name"],
        "valid": False,
        "proven_delta": None,
        "instance_score": 0.0,
    }
    try:
        dimension = int(instance["dimension"])
        guards = _parse_guards(instance["guards"], dimension)
        update_a = _matrix(instance["A"], "A", dimension, dimension)
        update_b = _vector(instance["b"], "b", dimension)
        ranking, shift, delta, nonneg, decrease = _validate(
            build(public_instance(instance)), dimension, len(guards)
        )
        holds, reason = certificate_holds(
            guards, update_a, update_b, ranking, shift, delta, nonneg, decrease
        )
        if not holds:
            raise ValueError("Farkas certificate fails on %s" % reason)
        score = min(float(delta / DELTA_UNIT), 1.0)
        published.update({
            "valid": True,
            "proven_delta": [delta.numerator, delta.denominator],
            "instance_score": round(score, 6),
        })
    except Exception as exc:  # noqa: BLE001
        published["reason"] = "%s: %s" % (type(exc).__name__, exc)
    return published


def evaluate(build_ranking):
    rows = [_score_instance(build_ranking, instance) for instance in INSTANCES]
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
