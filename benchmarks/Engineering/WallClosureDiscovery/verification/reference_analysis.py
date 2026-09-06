"""Reference: fit the law and the instrument together, and abstain on the width of the answer.

Deliberately below the ceiling. The fit is a grid search refined once, the nuisances are handled by
a linear projection rather than a proper marginalisation, and the abstention thresholds are round
numbers. What it has that the baseline does not is the two reasons to say nothing, and they are
different reasons:

  * **the residuals are bad** - no single closure explains the profiles, which is the `inconsistent`
    world and the easy half;
  * **the answer is too wide** - the profiles are explained perfectly by a whole interval of
    `kappa`, and the members of that interval disagree at the held-out Reynolds numbers. The
    residuals here look *excellent*. This is the `degenerate_parameters` world, and it is the one
    the data-driven closure literature is actually about.

Fitting the two per-profile nuisances is not a refinement, it is the difference between an answer
and a wrong answer: measured on this world, a fit that ignores the unknown wall position and
friction-velocity calibration returns `kappa = 0.501` against a truth of `0.410`, because the
systematics have nowhere to go except into the parameter being estimated.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np

# A kappa interval wider than this cannot pin the held-out profiles: the measured sensitivity is
# about 17 in centreline velocity per unit kappa, against a tolerance near 1.3.
KAPPA_WIDTH_LIMIT = 0.048
RESIDUAL_LIMIT = 0.60


def _predict(kappa, a_plus, y, re_tau):
    length = kappa * y * (1.0 - np.exp(-y / a_plus))
    stress = np.clip(1.0 - y / re_tau, 0.0, None)
    gradient = 2.0 * stress / (1.0 + np.sqrt(1.0 + 4.0 * length ** 2 * stress))
    return np.concatenate([[0.0], np.cumsum(np.diff(y) * 0.5 * (gradient[1:] + gradient[:-1]))])


def _chi_square(kappa, a_plus, readings):
    """Chi-square with the wall position and the calibration projected out per profile.

    Returned unreduced, and the caller divides where it wants a goodness-of-fit. Mixing the two was
    the first version's bug: an admissible set defined by `reduced + 1` is `unreduced + 72` on
    these profiles, which admits every kappa in the grid and made the reference abstain on all
    twenty-four cases including the answerable ones.
    """
    total, points = 0.0, 0
    for reading in readings:
        y = np.asarray(reading["y_plus"], dtype=float)
        observed = np.asarray(reading["u_plus"], dtype=float)
        sigma = max(float(reading["noise_sigma"]), 1e-9)
        predicted = _predict(kappa, a_plus, y, float(reading["re_tau"]))
        # A calibration scales the profile and a wall shift moves it, which to first order is a
        # multiple of its gradient. Projecting both out is what stops them from being absorbed
        # into kappa.
        design = np.column_stack([predicted, np.gradient(predicted, y)])
        coefficients, *_ = np.linalg.lstsq(design, observed, rcond=None)
        total += float(np.sum((design @ coefficients - observed) ** 2)) / sigma ** 2
        points += y.size
    return total, max(points, 1)


def build_closure(problem, observe):
    readings = [observe(re_tau) for re_tau in problem["sampled_re_tau"]]
    kappas = np.linspace(0.32, 0.54, 45)
    a_pluses = np.linspace(15.0, 40.0, 45)
    grid = [[_chi_square(k, a, readings) for a in a_pluses] for k in kappas]
    surface = np.array([[cell[0] for cell in row] for row in grid])
    points = grid[0][0][1]
    flat = int(np.argmin(surface))
    best_kappa = kappas[flat // surface.shape[1]]
    best_a = a_pluses[flat % surface.shape[1]]
    best = float(surface.min())

    # Delta chi-square of 4 is the two-sigma region for one parameter of interest, profiled over
    # the other. Everything in it is a closure the data cannot reject.
    admissible = kappas[np.any(surface <= best + 4.0, axis=1)]
    width = float(admissible.max() - admissible.min()) if admissible.size else 1.0

    if best / points > RESIDUAL_LIMIT:
        # Nothing in the family explains the profiles together.
        return {"abstain": True, "mixing_length": None, "confidence": 0.0}
    if width > KAPPA_WIDTH_LIMIT:
        # Everything in the family explains them equally, and the members disagree where it counts.
        return {"abstain": True, "mixing_length": None, "confidence": 0.0}

    kappa_ratio = Fraction(float(best_kappa)).limit_denominator(2000)
    a_ratio = Fraction(float(best_a)).limit_denominator(2000)
    formula = ["mul",
               ["const", kappa_ratio.numerator, kappa_ratio.denominator],
               ["mul", ["var", "y"],
                ["sub", ["const", 1, 1],
                 ["exp", ["neg", ["div", ["var", "y"],
                                  ["const", a_ratio.numerator, a_ratio.denominator]]]]]]]
    confidence = float(min(1.0, KAPPA_WIDTH_LIMIT / max(width, 1e-6) / 2.0))
    return {"abstain": False, "mixing_length": formula, "confidence": confidence}
