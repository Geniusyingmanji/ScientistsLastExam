"""Exact rational machinery for Cohn-Elkies sphere-packing certificates.

Everything that is *checked* is rational. Only the number finally reported involves pi.

The trick that makes this possible is the choice of variable. Cohn and Elkies work with radial
functions on R^n, and the Fourier eigenbasis for such functions is

    L_k^{(n/2 - 1)}(2*pi*|x|^2) * exp(-pi*|x|^2),   eigenvalue (-1)^k,

so a function built from that basis has an exactly known transform. Written in `|x|^2` the
polynomial coefficients carry powers of 2*pi and nothing is rational. Written in

    w = 2*pi*|x|^2

the Laguerre polynomials have rational coefficients, the transform is a sign flip on the
coefficients, and the support condition `|x| >= r` becomes `w >= R` with `R = 2*pi*r^2` a number
the submitter chooses. Choosing `R` rational makes every inequality that has to be verified a
statement about a rational polynomial on a rational half-line, which has an exact certificate.
"""
from __future__ import annotations

from fractions import Fraction


def laguerre(k: int, alpha: Fraction) -> list:
    """Coefficients of L_k^{(alpha)}(w) in ascending powers of w, exact for rational alpha.

    L_k^{(alpha)}(w) = sum_i (-1)^i * binom(k + alpha, k - i) * w^i / i!
    """
    out = []
    for i in range(k + 1):
        binomial = Fraction(1)
        for j in range(1, k - i + 1):
            binomial *= (alpha + i + j)
            binomial /= j
        factorial = Fraction(1)
        for j in range(1, i + 1):
            factorial *= j
        out.append((-1) ** i * binomial / factorial)
    return out


def poly_add(left: list, right: list) -> list:
    size = max(len(left), len(right))
    out = [Fraction(0)] * size
    for i, value in enumerate(left):
        out[i] += value
    for i, value in enumerate(right):
        out[i] += value
    return _trim(out)


def poly_scale(poly: list, factor) -> list:
    return _trim([factor * value for value in poly])


def poly_mul(left: list, right: list) -> list:
    if not left or not right:
        return []
    out = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        if a == 0:
            continue
        for j, b in enumerate(right):
            if b == 0:
                continue
            out[i + j] += a * b
    return _trim(out)


def poly_shift(poly: list, offset) -> list:
    """p(w) -> p(w + offset), by repeated synthetic division. Exact."""
    out = [Fraction(0)]
    for coefficient in reversed(poly):
        out = poly_add(poly_mul(out, [Fraction(offset), Fraction(1)]), [Fraction(coefficient)])
    return _trim(out)


def poly_eval(poly: list, point) -> Fraction:
    total = Fraction(0)
    for coefficient in reversed(poly):
        total = total * point + coefficient
    return total


def _trim(poly: list) -> list:
    while poly and poly[-1] == 0:
        poly.pop()
    return poly


def sum_of_squares(terms) -> list:
    """sum_k weight_k * q_k(w)^2 from [(weight, coefficients), ...]. Weights must be >= 0."""
    total: list = []
    for weight, polynomial in terms:
        if weight < 0:
            raise ValueError("a square carries a negative weight")
        if weight == 0:
            continue
        total = poly_add(total, poly_scale(poly_mul(polynomial, polynomial), weight))
    return total


def nonnegative_on_half_line(target: list, sigma0, sigma1) -> bool:
    """Verify `target(w) >= 0 for all w >= 0` from a Positivstellensatz certificate.

    A univariate polynomial is non-negative on [0, infinity) exactly when it can be written
    `sigma0(w) + w * sigma1(w)` with both parts sums of squares, so the certificate is complete:
    anything true has one, and anything with one is true. That is what makes this checkable rather
    than merely testable - no sampling, no tolerance, no root isolation.
    """
    reconstructed = poly_add(sum_of_squares(sigma0),
                             poly_mul([Fraction(0), Fraction(1)], sum_of_squares(sigma1)))
    return _trim(list(target)) == reconstructed
