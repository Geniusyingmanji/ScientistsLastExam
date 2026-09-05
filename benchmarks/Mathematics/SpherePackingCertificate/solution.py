"""Baseline: the two-term certificate, written out in closed form.

Keep only the first two Laguerre terms. With `c = (n/2 + 2, 1)` the two polynomials collapse to

    f  ->  P(w) = (n + 2) - w          non-positive exactly where w >= n + 2
    fhat ->  Q(w) = w + 2              non-negative everywhere on [0, infinity)

so both hypotheses hold by inspection and both certificates are one line each: `-P(R + s) = s`
gives `sigma1 = [(1, 1)]`, and `Q = 2 + w` gives `sigma0 = [(2, 1)]`, `sigma1 = [(1, 1)]`. The
support radius `R = n + 2` is the optimum of the resulting bound over this two-parameter family:
minimising `((n + e)/(2*pi))^(n/2) * (n + e)/(2^n * e)` over `e` gives `e = 2`.

This is what the method gives with no work at all, and it is the zero of the scale.
"""
from fractions import Fraction


def build_certificate(instance):
    dimension = instance["dimension"]
    # Laguerre coefficients (c_0, c_1); L_0 = 1 and L_1(w) = 1 + alpha - w = n/2 - w.
    coefficients = [Fraction(dimension, 2) + 2, Fraction(1)]
    threshold = Fraction(dimension + 2)
    one = [[1, 1]]
    return {
        "threshold": [threshold.numerator, threshold.denominator],
        "coefficients": [[c.numerator, c.denominator] for c in coefficients],
        # Q(w) = w + 2
        "transform_nonnegative": {"sigma0": [{"weight": [2, 1], "poly": one}],
                                  "sigma1": [{"weight": [1, 1], "poly": one}]},
        # -P(R + s) = s
        "tail_nonpositive": {"sigma0": [], "sigma1": [{"weight": [1, 1], "poly": one}]},
    }
