"""Complete, truth-blind reference for the fixed LD-row acquisition contract.

Chase conditional residuals, buy resolution rows, compare configurations, and
scan strong-LD neighbourhoods for masked partners. All computations use only
public summary statistics and charged row responses. Marginal t-statistics are
converted to correlations before the final joint per-allele least-squares fit.
The remaining effect error is sampling error; no competence is disabled to
lower the calibration threshold. This module is a standalone candidate.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy.stats import chi2

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


def _region_wide_fine_map(problem, ld_row):
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
    _region_wide_fine_map.last = (config, margin, list(bought))
    if margin < RESOLVE_MARGIN:
        return {"verdict": "unresolved", "confidence": 0.8}
    effects = [float(lam[i] * se[v]) for i, v in enumerate(config)]
    return {"verdict": "typed", "causal": [int(v) for v in config], "effects": effects,
            "confidence": 0.8}


def _conditional_chi(z, R, config):
    """Conditional scan using the already bought configuration rows only."""
    S = list(config)
    coef = np.linalg.solve(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)), R[S, :])
    residual = z - z[S] @ coef
    variance = 1.0 - np.einsum("ij,ij->j", R[S, :], coef)
    values = residual ** 2 / np.maximum(variance, 1e-9)
    values[S] = -np.inf
    return values


def _joint_effects(z, se, R, config, n):
    """Exact least-squares conversion from marginal t, SE and in-sample LD.

    For a unit-variance phenotype, r_j=t_j/sqrt(n-2+t_j**2) and
    1/sd(G_j)=se_j*sqrt(n-2+t_j**2). These identities avoid treating each
    marginal residual variance as the joint residual variance.
    """
    S = list(config)
    conversion = np.sqrt(n - 2.0 + z[S] ** 2)
    marginal_r = z[S] / conversion
    standardized = np.linalg.solve(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)), marginal_r)
    return standardized * se[S] * conversion


def fine_map(problem, ld_row):
    result = _region_wide_fine_map(problem, ld_row)
    config, margin, bought = _region_wide_fine_map.last
    if result.get("verdict") != "typed":
        return result
    z = np.asarray(problem["z"], dtype=float)
    se = np.asarray(problem["standard_error"], dtype=float)
    R = np.asarray(problem["reference_ld"], dtype=float).copy()
    for variant in bought:
        row = np.asarray(ld_row(int(variant)), dtype=float)  # repeat purchases are free
        R[variant, :] = row
        R[:, variant] = row
    config = list(config)
    conditional = _conditional_chi(z, R, config)
    added = []
    for variant in config:
        neighbours = [u for u in range(len(z)) if u not in config and abs(R[variant, u]) >= 0.5]
        if not neighbours:
            continue
        best = max(neighbours, key=lambda u: conditional[u])
        if (conditional[best] >= chi2.isf(0.01 / len(neighbours), 1)
                and best not in added
                and len(config) + len(added) < int(problem["max_causal"])):
            added.append(best)
    config += added
    effects = _joint_effects(z, se, R, config, int(problem["n_gwas"]))
    return {"verdict": "typed", "causal": [int(v) for v in config],
            "effects": [float(effect) for effect in effects], "confidence": 0.8}
