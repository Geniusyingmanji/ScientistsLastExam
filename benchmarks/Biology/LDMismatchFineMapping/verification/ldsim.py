"""Haplotype, genotype and summary-statistic simulation for LDMismatchFineMapping.

Two populations share a founder panel of haplotypes but draw them with different weights and
different switch rates, so their linkage disequilibrium differs (a Li-Stephens mosaic). The GWAS
cohort is drawn from one population and the public reference panel from the other.
"""
from __future__ import annotations

import numpy as np

N_SNP = 60
N_FOUNDERS = 24
BLOCKS = (0, 20, 40, 60)          # recombination hotspots at the boundaries


CANDIDATE_SITES = 400
COMMON = (0.15, 0.85)


def founder_panel(rng, n_sites, weights):
    """Founder haplotypes from a random binary tree with mutations along its edges, so that
    nearby founders share alleles and LD arises from sharing. Of CANDIDATE_SITES sites, n_sites
    are kept at random among those whose allele frequency under `weights` is common; returns
    None when there are too few."""
    haps = np.zeros((1, CANDIDATE_SITES), dtype=np.int8)
    while haps.shape[0] < N_FOUNDERS:
        parent = int(rng.integers(0, haps.shape[0]))
        child = haps[parent].copy()
        flips = rng.random(CANDIDATE_SITES) < 0.08
        child[flips] = 1 - child[flips]
        haps = np.vstack([haps, child[None, :]])
    freq = weights @ haps
    common = np.where((freq > COMMON[0]) & (freq < COMMON[1]))[0]
    if len(common) < n_sites:
        return None
    keep = np.sort(rng.choice(common, n_sites, replace=False))
    return haps[:, keep]


def mosaic_haplotypes(rng, founders, weights, switch, n_haps):
    """Li-Stephens copying: each haplotype copies a founder, switching to a fresh founder drawn
    from `weights` with probability `switch` per site step and with probability 0.5 at block
    boundaries; copied alleles are read with a small error rate."""
    n_f, n_sites = founders.shape
    state = rng.choice(n_f, size=n_haps, p=weights)
    out = np.empty((n_haps, n_sites), dtype=np.int8)
    for s in range(n_sites):
        if s > 0:
            p = 0.5 if s in BLOCKS else switch
            jump = rng.random(n_haps) < p
            n_jump = int(jump.sum())
            if n_jump:
                state[jump] = rng.choice(n_f, size=n_jump, p=weights)
        out[:, s] = founders[state, s]
    err = rng.random(out.shape) < 0.01
    out[err] = 1 - out[err]
    return out


def genotypes(rng, founders, weights, switch, n_ind):
    haps = mosaic_haplotypes(rng, founders, weights, switch, 2 * n_ind)
    return (haps[0::2].astype(np.int16) + haps[1::2].astype(np.int16)).astype(np.float64)


def correlation(G):
    X = G - G.mean(axis=0, keepdims=True)
    sd = np.sqrt((X ** 2).mean(axis=0))
    sd[sd == 0] = 1.0
    X = X / sd
    return (X.T @ X) / X.shape[0]


def marginal_z(G, y):
    """Marginal association z-scores of every column of G with y (a linear regression each)."""
    X = G - G.mean(axis=0, keepdims=True)
    yc = y - y.mean()
    n = len(y)
    sxx = (X ** 2).sum(axis=0)
    sxx[sxx == 0] = 1.0
    beta = (X * yc[:, None]).sum(axis=0) / sxx
    resid_var = ((yc[:, None] - X * beta[None, :]) ** 2).sum(axis=0) / (n - 2)
    se = np.sqrt(resid_var / sxx)
    return beta / se, beta, se


def genotypes_from_haplotypes(haps):
    return (haps[0::2].astype(np.int16) + haps[1::2].astype(np.int16)).astype(np.float64)
