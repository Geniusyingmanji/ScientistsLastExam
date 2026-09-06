"""Exact ASD of already-orthogonal Gaussian-integer rays (standard library only).

This finite representation scores approximate four-basis designs. It excludes
even three exact MUB including I in dimension six; see scientific_basis.md.
No submitted basis is rounded, normalized numerically, or orthogonalized here.
"""

import json
from fractions import Fraction
from functools import lru_cache
from math import isqrt
from pathlib import Path


PROBLEM = {"dimension": 6, "num_bases": 4, "max_coordinate_bits": 384}
_FIXTURE = Path(__file__).resolve().parents[1] / "references/raynal_rays.json"


def _identity(d):
    return [[[int(i == j), 0] for j in range(d)] for i in range(d)]


def _inner(a, b):
    return (sum(x*u + y*v for (x,y),(u,v) in zip(a,b)),
            sum(x*v - y*u for (x,y),(u,v) in zip(a,b)))


def _read_bases(bases, dimension, max_coordinate_bits):
    # Complete structural/coordinate pass precedes every multiplication.
    if type(dimension) is not int or not 2 <= dimension <= 6:
        raise ValueError("unsupported dimension")
    if type(max_coordinate_bits) is not int or not 1 <= max_coordinate_bits <= 384:
        raise ValueError("unsupported coordinate budget")
    if type(bases) is not list or not 2 <= len(bases) <= 7:
        raise ValueError("invalid basis count")
    for basis in bases:
        if type(basis) is not list or len(basis) != dimension:
            raise ValueError("invalid matrix shape")
        for row in basis:
            if type(row) is not list or len(row) != dimension:
                raise ValueError("invalid matrix shape")
            for entry in row:
                if type(entry) is not list or len(entry) != 2:
                    raise ValueError("entries must be integer pairs")
                for value in entry:
                    if type(value) is not int or value.bit_length() > max_coordinate_bits:
                        raise ValueError("coordinate type or bit limit")
    result = []
    for basis in bases:
        columns = [tuple(tuple(basis[i][j]) for i in range(dimension)) for j in range(dimension)]
        norms = [sum(x*x + y*y for x,y in col) for col in columns]
        if any(n == 0 for n in norms):
            raise ValueError("zero column")
        for j in range(dimension):
            for k in range(j):
                if _inner(columns[j], columns[k]) != (0, 0):
                    raise ValueError("columns are not exactly orthogonal")
        result.append((columns, norms))
    return result


def _probabilities(a, b):
    ac, an = a
    bc, bn = b
    result = []
    for i, u in enumerate(ac):
        row = []
        for j, v in enumerate(bc):
            re, im = _inner(u, v)
            row.append(Fraction(re*re + im*im, an[i]*bn[j]))
        result.append(row)
    return result


def overlap_probabilities(a, b, dimension=6, max_coordinate_bits=384):
    """Exact transition probabilities; validate both actual submitted bases."""
    left, right = _read_bases([a,b], dimension, max_coordinate_bits)
    return _probabilities(left, right)


def score_bases(bases, dimension=6, max_coordinate_bits=384):
    """Pure metric for a COMPLETE list, including I when it is a scored basis.

    SSE=sum_(a<b,i,j)(p_abij-1/d)^2; ASD=1-SSE/(C(k,2)*(d-1)).
    Returns Fractions, with no floating tolerance or feasibility penalty.
    """
    parsed = _read_bases(bases, dimension, max_coordinate_bits)
    target = Fraction(1, dimension)
    sse = Fraction(0)
    for a in range(len(parsed)):
        for b in range(a + 1, len(parsed)):
            sse += sum((p-target)**2 for row in _probabilities(parsed[a], parsed[b]) for p in row)
    scale = (len(parsed)*(len(parsed)-1)//2) * (dimension-1)
    return {"sse": sse, "asd": 1-sse/scale}


def _dyadic_cuberoot_floor(value, scale):
    """Largest integer m with (m/scale)^3 <= positive rational value."""
    low, high = 0, scale
    target = value.numerator * scale**3
    while high**3 * value.denominator <= target:
        high *= 2
    while low + 1 < high:
        mid = (low+high)//2
        if mid**3 * value.denominator <= target:
            low = mid
        else:
            high = mid
    return low


@lru_cache(maxsize=1)
def published_asd_interval():
    """Certified rational enclosure of Raynal et al. Eq.(22), not an optimum bound."""
    scale = 1 << 80
    root = isqrt(3*scale*scale)
    sqrt_lo, sqrt_hi = Fraction(root,scale), Fraction(root+1,scale)
    y_lo, y_hi = 21*sqrt_lo-36, 21*sqrt_hi-36
    if not 0 < y_lo < y_hi:
        raise ArithmeticError("cube-root enclosure domain")
    r_lo = Fraction(_dyadic_cuberoot_floor(y_lo,scale), scale)
    r_hi = Fraction(_dyadic_cuberoot_floor(y_hi,scale)+1, scale)
    if not 0 < r_lo < r_hi:
        raise ArithmeticError("reciprocal enclosure domain")
    # s(r)=(3/r+16-r)/28 decreases on r>0.
    s_lo, s_hi = (3/r_hi+16-r_hi)/28, (3/r_lo+16-r_lo)/28
    if not 0 < s_lo < s_hi < 1:
        raise ArithmeticError("ASD monotonicity domain")
    # (71-12*(1-s)^2)/70 increases on s<1.
    return ((71-12*(1-s_lo)**2)/70, (71-12*(1-s_hi)**2)/70)


@lru_cache(maxsize=1)
def reference_asd():
    """Immutable trusted data only; never import mutable candidate/helper code."""
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    if type(payload) is not dict or type(payload.get("bases")) is not list or len(payload["bases"]) != 3:
        raise ValueError("invalid trusted reference fixture")
    metric = score_bases([_identity(6)] + payload["bases"])
    if not 0 < metric["asd"] < published_asd_interval()[1]:
        raise ValueError("trusted reference outside anchor domain")
    return metric["asd"]


def _exact(value):
    # Hex strings avoid CPython's decimal-integer digit cap without global changes.
    return {"numerator_hex": hex(value.numerator), "denominator_hex": hex(value.denominator)}


def evaluate(build_bases):
    """One public d=6 instance. Candidate computation is bounded by the runner.

    The uncapped score is candidate ASD / fixed rational reference ASD. Only
    candidate ASD strictly above the algebraic reference's rational upper bound
    triggers beyond_published_reference; fixture precision gains do not suffice.
    """
    anchor = reference_asd()
    lower, upper = published_asd_interval()
    failure = None
    try:
        submission = build_bases(dict(PROBLEM))
    except Exception:
        failure = "candidate raised an exception"
    if failure is None:
        try:
            if type(submission) is not dict:
                raise ValueError("submission must be a mapping")
            bases = submission.get("bases")
            if type(bases) is not list or len(bases) != 3:
                raise ValueError("exactly three explicit bases required")
            metric = score_bases([_identity(6)] + bases)
        except ValueError as exc:
            failure = str(exc)  # Only fixed messages from our parser, never candidate text.
    valid = failure is None
    asd = metric["asd"] if valid else Fraction(0)
    sse = metric["sse"] if valid else None
    score, excess = asd/anchor, max(Fraction(0), asd-upper)
    return {
        "combined_score": float(score), "raw_score": float(asd),
        "valid": float(valid), "feasibility_rate": float(valid),
        "asd": float(asd), "sse": float(sse) if valid else None,
        "asd_exact": _exact(asd), "sse_exact": _exact(sse) if valid else None,
        "normalized_score_exact": _exact(score),
        "reference_asd": float(anchor), "reference_asd_exact": _exact(anchor),
        "published_asd_lower_exact": _exact(lower), "published_asd_upper_exact": _exact(upper),
        "beyond_rational_fixture": bool(valid and asd > anchor),
        "beyond_published_reference": bool(valid and asd > upper),
        "frontier_excess_lower_bound": float(excess),
        "frontier_excess_lower_bound_exact": _exact(excess),
        "reason": failure,
    }
