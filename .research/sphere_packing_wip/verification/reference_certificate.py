"""Reference: a Cohn-Elkies certificate found numerically and made exact.

Deliberately below the ceiling. The procedure is the obvious one - optimise the Laguerre
coefficients and the support radius numerically against a grid, round to rationals, and extract
exact sum-of-squares certificates for both hypotheses - and each step is beatable. Cohn and Elkies
themselves get their bounds by forcing double roots at chosen points and solving for the
coefficients by Newton iteration, which is a much better use of the same degree.
"""
from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
from scipy.optimize import linprog

from extract import extract
from lp_algebra import laguerre, poly_add, poly_eval, poly_scale, poly_shift


def _basis(dimension, degree):
    alpha = Fraction(dimension, 2) - 1
    return [laguerre(k, alpha) for k in range(degree + 1)]


def _combine(basis, coefficients, signs=False):
    total: list = []
    for index, (row, c) in enumerate(zip(basis, coefficients)):
        factor = c * ((-1) ** index if signs else 1)
        total = poly_add(total, poly_scale(row, factor))
    return total


def _linear_program(dimension, degree, threshold, grid_top=60.0, points=1200, margin=1e-4):
    """For a fixed support radius the Cohn-Elkies problem is linear in the coefficients.

    Both hypotheses are linear inequalities in `c`, the objective `f(0)` is linear, and the scale is
    free, so pinning `fhat(0) = 1` turns the whole thing into one linear program. This is the method
    Cohn and Elkies use; the outer search over the radius is the only nonlinear part. Discretising
    the two half-lines on a grid makes it a relaxation - the returned coefficients are checked
    exactly afterwards, and a grid miss shows up there as a failed extraction rather than as a
    wrong bound.
    """
    basis = np.array([[float(v) for v in row] + [0.0] * (degree - len(row) + 1)
                      for row in _basis(dimension, degree)])
    signs = np.array([(-1.0) ** k for k in range(degree + 1)])

    def powers(x):
        return np.vander(x, degree + 1, increasing=True)

    grid_q = np.linspace(0.0, grid_top, points)
    grid_p = np.linspace(float(threshold), grid_top, points)
    # value of the polynomial at a point, as a linear functional of c
    q_rows = powers(grid_q) @ basis.T * signs           # fhat(w_i) = sum_k (-1)^k c_k L_k(w_i)
    p_rows = powers(grid_p) @ basis.T                   # f(w_j)
    at_zero = powers(np.array([0.0])) @ basis.T         # f(0)
    transform_zero = at_zero * signs                    # fhat(0)

    inequality = np.vstack([-q_rows, p_rows])
    limits = np.concatenate([np.full(points, -margin), np.full(points, -margin)])
    result = linprog(c=at_zero[0], A_ub=inequality, b_ub=limits,
                     A_eq=transform_zero, b_eq=np.array([1.0]),
                     bounds=[(None, None)] * (degree + 1), method="highs")
    if not result.success or result.x is None:
        return None
    return result.x, float(result.fun)


def _truly_nonnegative(coefficients, lower):
    """Does this polynomial actually keep its sign on [lower, infinity)?

    The linear program only constrains a grid, and a high-degree polynomial oscillates between grid
    points. Left unchecked this produces bounds that are simply false: at degree 16 the grid
    relaxation returns 0.06237 in dimension 8, below the 0.0625 that the E8 lattice actually
    achieves, and 0.00066 in dimension 16 against a packing of 0.0625. Root isolation is the cheap
    filter; the exact certificate downstream is the one that cannot be fooled.
    """
    trimmed = np.trim_zeros(np.asarray(coefficients, dtype=float), "b")
    if trimmed.size == 0:
        return True
    if trimmed.size == 1:
        return trimmed[0] >= 0
    roots = np.roots(trimmed[::-1])
    real = roots[np.abs(roots.imag) < 1e-9].real
    interior = np.sort(real[real > lower + 1e-9])
    probes = [lower + 1e-6]
    previous = lower
    for root in interior:
        probes.append((previous + root) / 2.0)
        previous = root
    probes.append(previous + 1.0)
    values = np.polyval(trimmed[::-1], np.array(probes))
    return bool(np.all(values >= -1e-9))


def _search_radius(dimension, degree):
    """One-dimensional search over the support radius, minimising the resulting bound."""
    best = None
    lower = dimension / 2.0 + 1.0
    for threshold in np.linspace(lower, lower + 6.0 * math.sqrt(dimension), 40):
        found = _linear_program(dimension, degree, threshold)
        if found is None:
            continue
        _c, at_zero = found
        bound = ((threshold / (2.0 * math.pi)) ** (dimension / 2.0)) / (2.0 ** dimension) * at_zero
        if at_zero <= 0 or (best is not None and bound >= best[0]):
            continue
        basis = np.array([[float(v) for v in row] + [0.0] * (degree - len(row) + 1)
                          for row in _basis(dimension, degree)])
        signs = np.array([(-1.0) ** k for k in range(degree + 1)])
        coefficients = found[0]
        transform = basis.T @ (coefficients * signs)
        forward = basis.T @ coefficients
        if not _truly_nonnegative(transform, 0.0):
            continue
        if not _truly_nonnegative(-forward, threshold):
            continue
        best = (bound, coefficients, threshold)
    return best


def build_certificate(instance):
    dimension = instance["dimension"]
    for degree in (8, 10, 12, 6):
        found = _search_radius(dimension, degree)
        if found is None:
            continue
        _bound, coefficients, threshold = found
        for denominator in (10 ** 9, 10 ** 7, 10 ** 6):
            rational_c = [Fraction(round(v * denominator), denominator) for v in coefficients]
            rational_R = Fraction(round(threshold * denominator), denominator)
            basis = _basis(dimension, degree)
            forward = _combine(basis, rational_c)
            transform = _combine(basis, rational_c, signs=True)
            if poly_eval(forward, Fraction(0)) <= 0 or poly_eval(transform, Fraction(0)) <= 0:
                continue
            positive = extract(transform)
            if positive is None:
                continue
            tail = poly_scale(poly_shift(forward, rational_R), Fraction(-1))
            negative = extract(tail)
            if negative is None:
                continue
            return {
                "threshold": [rational_R.numerator, rational_R.denominator],
                "coefficients": [[c.numerator, c.denominator] for c in rational_c],
                "transform_nonnegative": _emit(positive),
                "tail_nonpositive": _emit(negative),
            }
    raise RuntimeError("no certificate found for dimension %d" % dimension)


def _emit(pair):
    sigma0, sigma1 = pair
    return {
        "sigma0": [{"weight": [w.numerator, w.denominator],
                    "poly": [[v.numerator, v.denominator] for v in vec]} for w, vec in sigma0],
        "sigma1": [{"weight": [w.numerator, w.denominator],
                    "poly": [[v.numerator, v.denominator] for v in vec]} for w, vec in sigma1],
    }
