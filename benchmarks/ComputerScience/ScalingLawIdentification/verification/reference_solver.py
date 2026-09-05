"""Truth-blind reference witness: log-shape regression with branch and jitter tests.

Sizes {16, 64, 256, 256, 1024} are profiled (the repeated mid size estimates the
mod-3 branches of a branching runtime; the repeated mid size estimates the
noise floor); each class is fitted by one-parameter regression in log space,
and two refusal tests guard the unmodellable worlds: a split fit on sizes
congruent to 1 mod 3 versus the rest must agree in shape, and the
repeat-estimated noise floor must sit near the published three percent. It
deliberately lacks adaptive size ladders and information-criterion averaging.
"""

from __future__ import annotations

import math

import numpy as np

SIZES = (16, 32, 64, 128, 256, 256, 1024)
JITTER_GATE = 0.15


def _shape(name, size):
    log_size = math.log2(max(size, 2))
    return {"constant": 1.0, "logarithmic": log_size, "linear": float(size),
            "linearithmic": size * log_size, "quadratic": float(size) ** 2,
            "exponential": 2.0 ** (size / 8.0)}[name]


def identify_scaling_law(problem, time_run, budget_units):
    del budget_units
    runs = [time_run(size) for size in SIZES]
    sizes = np.asarray([run["size"] for run in runs], dtype=float)
    times = np.asarray([run["runtime_ms"] for run in runs], dtype=float)

    # Jitter test: the repeated size exposes the multiplicative noise floor.
    repeated_sizes = {int(s) for s in sizes if list(sizes).count(s) >= 2}
    repeated = [t for s, t in zip(sizes, times) if int(s) in repeated_sizes]
    if len(repeated) >= 2:
        jitter = abs(math.log(repeated[0] / repeated[1])) / math.sqrt(2.0)
        if jitter > JITTER_GATE:
            return {"class_probabilities": {name: 1.0 / len(problem["classes"])
                                            for name in problem["classes"]},
                    "scale": None, "abstain": True, "confidence": 0.8}

    def fit(mask):
        best = None
        logs = np.log(times[mask])
        for name in problem["classes"]:
            shapes = np.asarray([_shape(name, int(s)) for s in sizes[mask]])
            scales = np.log(shapes)
            if float(np.ptp(scales)) < 1e-12:
                # Constant class: no shape column to regress on.
                level = float(np.mean(logs))
                residual = float(np.mean((logs - level) ** 2))
                candidate = (residual, name, math.exp(level), 1.0)
            else:
                design = np.column_stack([np.ones(int(mask.sum())), scales])
                coefficients, *_ = np.linalg.lstsq(design, logs, rcond=None)
                exponent = coefficients[1]
                penalty = (exponent - 1.0) ** 2 * 50.0
                residual = float(np.mean((logs - design @ coefficients) ** 2)) + penalty
                candidate = (residual, name, math.exp(coefficients[0]), exponent)
            if best is None or candidate[0] < best[0]:
                best = candidate
        return best

    best = fit(np.ones(len(sizes), dtype=bool))
    branch_mask = np.asarray([int(s) % 3 == 1 for s in sizes])
    other_mask = ~branch_mask
    if branch_mask.sum() >= 2 and other_mask.sum() >= 2:
        fit_branch = fit(branch_mask)
        fit_other = fit(other_mask)
        if (fit_branch[1] != fit_other[1]
                and fit_branch[0] < 0.25 * best[0]
                and fit_other[0] < 0.25 * best[0]):
            return {"class_probabilities": {name: 1.0 / len(problem["classes"])
                                            for name in problem["classes"]},
                    "scale": None, "abstain": True, "confidence": 0.75}

    probabilities = {name: 0.02 for name in problem["classes"]}
    probabilities[best[1]] = 1.0 - 0.02 * (len(problem["classes"]) - 1)
    return {"class_probabilities": probabilities, "scale": best[2],
            "abstain": False, "confidence": 0.75}
