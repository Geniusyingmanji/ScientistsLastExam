"""Search for an exactly-certifiable Cohn-Elkies certificate by structural parametrisation.

The tail hypothesis is made automatic rather than checked. Writing

    -f(R + s) = q0(s)^2 + s*q1(s)^2

with q0, q1 arbitrary rational polynomials means `f <= 0` on `[R, infinity)` holds by construction,
with a certificate that is already in hand. That determines `f`, hence its Laguerre coefficients,
hence the transform - and only `fhat >= 0` is left to establish, by one exact extraction.

Searching the coefficients of `f` directly instead finds nothing: 4000 random draws produced not one
candidate that even passed a numerical screen, because the feasible set is a thin sliver. Searching
`(q0, q1, R)` puts every draw inside half of it.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from extract import extract
from lp_algebra import laguerre, poly_add, poly_eval, poly_mul, poly_scale, poly_shift


def forward_from_tail(q0, q1, radius):
    """P(w) = -[q0(w-R)^2 + (w-R) q1(w-R)^2], plus the tail certificate in s."""
    shift = [-radius, Fraction(1)]
    left = _compose(q0, shift)
    right = _compose(q1, shift)
    tail = poly_add(poly_mul(left, left), poly_mul(shift, poly_mul(right, right)))
    return poly_scale(tail, Fraction(-1))


def _compose(poly, inner):
    out: list = []
    for coefficient in reversed(poly):
        out = poly_add(poly_mul(out, inner), [coefficient])
    return out


def laguerre_expand(poly, dimension, degree):
    """Exact coordinates of a polynomial in the Laguerre basis."""
    alpha = Fraction(dimension, 2) - 1
    rows = [laguerre(k, alpha) for k in range(degree + 1)]
    work = list(poly) + [Fraction(0)] * (degree + 1 - len(poly))
    coefficients = [Fraction(0)] * (degree + 1)
    for k in range(degree, -1, -1):
        value = work[k] / rows[k][k]
        coefficients[k] = value
        for i, entry in enumerate(rows[k]):
            work[i] -= value * entry
    if any(v != 0 for v in work[:degree + 1]):
        raise ValueError("Laguerre expansion left a residue")
    return coefficients, rows


def evaluate_candidate(dimension, q0, q1, radius, screen_top=400.0, screen_points=4000):
    forward = forward_from_tail(q0, q1, radius)
    degree = len(forward) - 1
    if degree < 0:
        return None
    at_zero = poly_eval(forward, Fraction(0))
    if at_zero <= 0:
        return None
    coefficients, rows = laguerre_expand(forward, dimension, degree)
    transform: list = []
    for index, (row, value) in enumerate(zip(rows, coefficients)):
        transform = poly_add(transform, poly_scale(row, value * (-1) ** index))
    transform_zero = poly_eval(transform, Fraction(0))
    if transform_zero <= 0:
        return None
    bound = ((float(radius) / (2.0 * math.pi)) ** (dimension / 2.0)) / (2.0 ** dimension) \
        * float(at_zero / transform_zero)
    grid = np.linspace(0.0, screen_top, screen_points)
    values = np.polyval(np.array([float(v) for v in transform])[::-1], grid)
    if float(values.min()) < -1e-12:
        return None
    if len(transform) > 1 and transform[-1] < 0:
        return None
    return bound, coefficients, forward, transform


def certify(dimension, q0, q1, radius):
    got = evaluate_candidate(dimension, q0, q1, radius)
    if got is None:
        return None
    bound, coefficients, forward, transform = got
    positive = extract(transform)
    if positive is None:
        return None
    return bound, coefficients, radius, positive, (q0, q1)
