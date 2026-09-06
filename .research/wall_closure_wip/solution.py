"""Baseline: fit the two-parameter law to whatever was observed, and never abstain.

Sample every Reynolds number available, fit `kappa` and `A+` in the damped mixing length by a
coarse grid search against the observed profiles, and submit the result. This is the honest
textbook procedure and it is exactly what the criticism of data-driven closure is about: it has no
way to notice that the flows it saw never reached the wall distances where the rest of the closure
lives, and no way to notice that no single closure explains them.

It scores zero, on the axis that matters: the refusal rate is zero by construction.
"""
from fractions import Fraction

import numpy as np


def analyze_profiles(readings):
    """Coarse grid search over (kappa, A+) against the observed mean profiles."""
    best = None
    for kappa in np.linspace(0.34, 0.48, 15):
        for a_plus in np.linspace(18.0, 34.0, 17):
            total = 0.0
            for reading in readings:
                y = np.asarray(reading["y_plus"])
                observed = np.asarray(reading["u_plus"])
                length = kappa * y * (1.0 - np.exp(-y / a_plus))
                stress = np.clip(1.0 - y / reading["re_tau"], 0.0, None)
                gradient = 2.0 * stress / (1.0 + np.sqrt(1.0 + 4.0 * length ** 2 * stress))
                predicted = np.concatenate(
                    [[0.0], np.cumsum(np.diff(y) * 0.5 * (gradient[1:] + gradient[:-1]))])
                total += float(np.sum((predicted - observed) ** 2))
            if best is None or total < best[0]:
                best = (total, kappa, a_plus)
    return best[1], best[2]


def build_closure(problem, observe):
    readings = [observe(re_tau) for re_tau in problem["sampled_re_tau"]]
    kappa, a_plus = analyze_profiles(readings)
    kappa_ratio = Fraction(kappa).limit_denominator(1000)
    a_ratio = Fraction(a_plus).limit_denominator(1000)
    formula = ["mul",
               ["const", kappa_ratio.numerator, kappa_ratio.denominator],
               ["mul", ["var", "y"],
                ["sub", ["const", 1, 1],
                 ["exp", ["neg", ["div", ["var", "y"],
                                  ["const", a_ratio.numerator, a_ratio.denominator]]]]]]]
    return {"abstain": False, "mixing_length": formula, "confidence": 0.6}
