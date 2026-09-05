"""Truth-blind reference witness: residue-covering ladder with BIC class selection.

The ladder (16, 16, 16, 13, 27, 55, 62, 192) samples residue six mod seven four
times — a residue a purely geometric ladder (residues {1, 2, 4}) never hits —
carries one size at 192 where the quadratic and exponential shapes finally
separate by two orders of magnitude, and repeats one size three times for a
noise-floor estimate. Classes are compared by a BIC-style score (n log
mean-residual plus parameter count times log n); the branch test compares the
pooled residual-sum against the subset residual-sums by an F statistic and refuses
when both residue classes fit separate laws overwhelmingly better than any single
law; the jitter gate refuses when the repeat-estimated noise floor exceeds thirteen
percent. It deliberately lacks adaptive size selection and Bayesian noise handling.
"""

from __future__ import annotations

import math

import numpy as np

SIZES = (16, 16, 16, 13, 27, 55, 62, 192)
JITTER_GATE = 0.13
F_GATE = 25.0


def _shape(name, size):
    log_size = math.log2(max(size, 2))
    return {"constant": 1.0, "logarithmic": log_size, "linear": float(size),
            "linearithmic": size * log_size, "quadratic": float(size) ** 2,
            "exponential": 2.0 ** (size / 8.0)}[name]


def _fit_score(name, logs, shape_values):
    """Fixed-shape fit: only the scale is free, so the six classes stay distinct.

    A regression with a free slope would collapse every power-law class into one
    family (a linear-class fit with slope two is the quadratic law exactly), so
    the class is fixed by its published shape and the scale is the geometric mean
    of times-over-shape.
    """
    residuals = logs - np.log(np.asarray(shape_values, dtype=float))
    level = float(np.mean(residuals))
    residual = float(np.mean((residuals - level) ** 2))
    return (len(logs) * math.log(residual + 1e-12) + math.log(len(logs)),
            name, math.exp(level))


def _rss(name, logs, sizes):
    shapes = [_shape(name, int(s)) for s in sizes]
    residuals = logs - np.log(np.asarray(shapes, dtype=float))
    return float(np.sum((residuals - float(np.mean(residuals))) ** 2))


def identify_scaling_law(problem, time_run, budget_units):
    del budget_units
    runs = [time_run(size) for size in SIZES]
    sizes = np.asarray([run["size"] for run in runs], dtype=float)
    times = np.asarray([run["runtime_ms"] for run in runs], dtype=float)
    logs = np.log(times)

    # Jitter test: the repeated size exposes the multiplicative noise floor as
    # the mean pairwise log gap of the repeats.
    repeated_sizes = {int(s) for s in sizes if list(sizes).count(s) >= 3}
    repeats = [math.log(t) for s, t in zip(sizes, times) if int(s) in repeated_sizes]
    if len(repeats) >= 3:
        gaps = [abs(a - b) for i, a in enumerate(repeats)
                for b in repeats[i + 1:]]
        if gaps and float(np.mean(gaps)) > JITTER_GATE:
            return {"class_probabilities": {name: 1.0 / len(problem["classes"])
                                            for name in problem["classes"]},
                    "scale": None, "abstain": True, "confidence": 0.8}

    best = min(_fit_score(name, logs, [_shape(name, int(s)) for s in sizes])
               for name in problem["classes"])

    # Branch test, agnostic to the branch predicate: scan the plausible moduli
    # (three and seven), for each find the residue split that maximizes the F
    # statistic comparing the pooled single-law fit against separate laws, and
    # refuse when any split clears a Bonferroni-doubled gate. A purely geometric
    # ladder samples only residues {1, 2} mod three and {1, 2, 4} mod seven, so
    # whether it can see the branch at all depends on the modulus.
    rss_pooled = min(_rss(name, logs, sizes) for name in problem["classes"])
    best_f = 0.0
    for modulus in (3, 7):
        for pivot in range(modulus):
            branch_mask = np.asarray([int(s) % modulus == pivot for s in sizes])
            other_mask = ~branch_mask
            if branch_mask.sum() < 3 or other_mask.sum() < 3:
                continue
            branch_name = min(problem["classes"],
                              key=lambda name: _rss(name, logs[branch_mask],
                                                    sizes[branch_mask]))
            other_name = min(problem["classes"],
                             key=lambda name: _rss(name, logs[other_mask],
                                                   sizes[other_mask]))
            if branch_name == other_name:
                continue
            rss_split = (_rss(branch_name, logs[branch_mask], sizes[branch_mask])
                         + _rss(other_name, logs[other_mask], sizes[other_mask]))
            denominator = max(rss_split, 1e-12) / max(len(logs) - 4, 1)
            f_stat = max(rss_pooled - rss_split, 0.0) / 2.0 / max(denominator, 1e-12)
            best_f = max(best_f, f_stat)
    if best_f > 2.0 * F_GATE:
        return {"class_probabilities": {name: 1.0 / len(problem["classes"])
                                        for name in problem["classes"]},
                "scale": None, "abstain": True, "confidence": 0.75}

    probabilities = {name: 0.02 for name in problem["classes"]}
    probabilities[best[1]] = 1.0 - 0.02 * (len(problem["classes"]) - 1)
    return {"class_probabilities": probabilities, "scale": best[2],
            "abstain": False, "confidence": 0.75}
