"""Truth-blind reference for LDMismatchFineMapping.

It buys in-sample LD rows in two phases. First it chases the residual: the row of the strongest
variant, then the row of the variant whose z-score is least explained by the variants already
modelled, until nothing is left unexplained or only one row per modelled variant remains. Then
it buys resolution rows: for each modelled variant, weakest first, the row of its closest
unbought proxy by the exact correlation in the modelled variant's own row, so that a
near-duplicate of any modelled variant, however weak that variant is, is bought and can be
compared with it; whatever is left buys the variants with the largest predicted z-score. On the
bought variants it fits every configuration of at most three causal variants by the
summary-statistic likelihood, z_B ~ N(R_BS lambda_S, R_BB), and chooses by the extended BIC. It
declines when swapping any modelled variant for another bought variant costs less than a fixed
margin of fit, because then the data do not say which of the two is causal. Effects are the
joint estimates converted to per-allele units with the published standard errors.

What it does not do, on purpose: it never uses the reference panel's correlations once a row is
bought, it does not average over configurations, it converts joint estimates with the marginal
standard error, and its margin is a fixed number rather than a calibrated test. Those are the
places it leaves room.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

MAX_CAUSAL = 3
RESOLUTION_ROWS = 1      # rows reserved per modelled variant for its closest proxy
CHASE_T = 3.0            # the chase stops when no unbought variant is this far from the model
RESOLVE_MARGIN = 3.0     # declines when a swap costs less than this in the extended BIC score
BIC_PENALTY = None       # extended BIC: log(n_gwas) + 2 log(n_variants) by default


def _configs(candidates):
    for k in range(1, MAX_CAUSAL + 1):
        for s in itertools.combinations(candidates, k):
            yield list(s)


def _fit(z, R, bought, config):
    """Joint estimate lambda = R_SS^-1 z_S and the residual chi-square of the other bought
    variants, with the Schur-complement covariance of those residuals given lambda."""
    S = list(config)
    inv = np.linalg.inv(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)))
    lam = inv @ z[S]
    rest = [b for b in bought if b not in S]
    if not rest:
        return lam, 0.0
    resid = z[rest] - R[np.ix_(rest, S)] @ lam
    C = R[np.ix_(rest, rest)] - R[np.ix_(rest, S)] @ inv @ R[np.ix_(S, rest)]
    C = C + 1e-6 * np.eye(len(rest))
    return lam, float(resid @ np.linalg.solve(C, resid))


def _score(z, R, bought, config, penalty):
    lam, chi = _fit(z, R, bought, config)
    return chi + penalty * len(config), lam


def _best_config(z, R, bought, penalty):
    best = None
    for config in _configs(bought):
        score, lam = _score(z, R, bought, config, penalty)
        if best is None or score < best[0]:
            best = (score, config, lam)
    return best


def _residual_t(z, R, config, lam):
    """Standardised residual of every variant given the configuration, using only the rows of
    the configuration variants, which are bought and therefore exact."""
    S = list(config)
    inv = np.linalg.inv(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)))
    pred = R[:, S] @ lam
    var = np.maximum(1.0 - np.einsum("is,st,it->i", R[:, S], inv, R[:, S]), 0.05)
    t = (z - pred) / np.sqrt(var)
    t[S] = 0.0
    return t


def _swap_margin(z, R, bought, config, score, penalty):
    """The smallest increase in score from replacing one modelled variant by another bought
    variant. Small means the data do not say which of the two is causal."""
    margin = math.inf
    for i, v in enumerate(config):
        for j in bought:
            if j in config:
                continue
            alt = list(config)
            alt[i] = j
            alt_score, _lam = _score(z, R, bought, alt, penalty)
            margin = min(margin, alt_score - score)
    return margin


def fine_map(problem, ld_row):
    z = np.asarray(problem["z"], dtype=float)
    se = np.asarray(problem["standard_error"], dtype=float)
    n = int(problem["n_gwas"])
    budget = int(problem["row_budget"])
    n_var = len(z)
    R = np.asarray(problem["reference_ld"], dtype=float).copy()
    penalty = (math.log(n) + 2.0 * math.log(n_var)) if BIC_PENALTY is None else BIC_PENALTY
    bought = []

    def buy(v):
        row = np.asarray(ld_row(int(v)), dtype=float)
        R[v, :] = row
        R[:, v] = row
        bought.append(int(v))

    buy(int(np.argmax(np.abs(z))))
    # phase one: chase the residual, keeping one row per modelled variant in reserve
    while True:
        _s, config, lam = _best_config(z, R, bought, penalty)
        if len(bought) >= budget - RESOLUTION_ROWS * len(config):
            break
        t = _residual_t(z, R, config, lam)
        t[bought] = 0.0
        nxt = int(np.argmax(np.abs(t)))
        if abs(t[nxt]) < CHASE_T:
            break
        buy(nxt)
    # phase two: resolution rows. For each modelled variant, weakest first, its closest unbought
    # proxy by the exact correlation in its own row: that is where a near-duplicate is, and a
    # weak variant's duplicate is not among the variants the model predicts most strongly.
    _s, config, lam = _best_config(z, R, bought, penalty)
    for s in sorted(config, key=lambda v: abs(z[v])):
        if len(bought) >= budget:
            break
        closeness = np.abs(R[:, s])
        closeness[bought] = -1.0
        buy(int(np.argmax(closeness)))
    # whatever remains: the variants the model predicts most strongly, ranked by the predicted
    # z-score and not the observed one, so that they are chosen for their correlation with the
    # model and not for their noise
    predicted = np.abs(R[:, list(config)] @ lam)
    for v in np.argsort(-predicted):
        if len(bought) >= budget:
            break
        v = int(v)
        if v not in bought:
            buy(v)
    score, config, lam = _best_config(z, R, bought, penalty)
    margin = _swap_margin(z, R, bought, config, score, penalty)
    fine_map.last = (config, margin, list(bought))
    if margin < RESOLVE_MARGIN:
        return {"verdict": "unresolved", "confidence": 0.8}
    effects = [float(lam[i] * se[v]) for i, v in enumerate(config)]
    return {"verdict": "typed", "causal": [int(v) for v in config], "effects": effects,
            "confidence": 0.8}
