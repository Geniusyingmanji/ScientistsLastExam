"""Standalone input-only classical reference; no world generator or truth."""

from copy import deepcopy

import numpy as np

from scipy.linalg import expm

from scipy.special import gammaln

def transition(rates, dt):
    a, b = rates
    return expm(np.array([[-a, a], [b, -b]])*dt)

def _fit(traces, dt, initial):
    """Baum-Welch with independent stationary-start traces; no true labels."""
    efficiencies = np.array(initial, float)
    trans = transition([1., 1.], dt)
    total = 200*dt
    for _ in range(30):
        transitions, photons, occupancies = np.zeros((2, 2)), np.zeros((2, 2)), np.zeros(2)
        ll = 0.
        for counts in traces:
            means = total*np.array([1-efficiencies, efficiencies]).T
            log_emission = (counts[:, None, :]*np.log(means)[None] - means[None] - gammaln(counts[:, None, :]+1)).sum(axis=2)
            offset = log_emission.max(axis=1)
            emission = np.exp(log_emission-offset[:, None])
            forward, scales = np.zeros_like(emission), np.zeros(len(counts))
            stationary = np.array([trans[1, 0], trans[0, 1]])
            stationary /= stationary.sum()
            forward[0] = stationary*emission[0]
            scales[0] = forward[0].sum(); forward[0] /= scales[0]
            for t in range(1, len(counts)):
                forward[t] = (forward[t-1]@trans)*emission[t]
                scales[t] = forward[t].sum(); forward[t] /= scales[t]
            backward = np.ones_like(emission)
            for t in range(len(counts)-2, -1, -1):
                backward[t] = trans@(emission[t+1]*backward[t+1])/scales[t+1]
            gamma = forward*backward
            gamma /= gamma.sum(axis=1)[:, None]
            xi = forward[:-1, :, None]*trans[None]*emission[1:, None, :]*backward[1:, None, :]
            xi /= xi.sum(axis=(1, 2))[:, None, None]
            transitions += xi.sum(axis=0)
            photons += gamma.T@counts
            occupancies += gamma.sum(axis=0)
            ll += float(np.sum(np.log(scales)+offset))
        trans = np.clip(transitions/transitions.sum(axis=1)[:, None], 1e-6, 1-1e-6)
        efficiencies = np.clip(photons[:, 1]/photons.sum(axis=1), .05, .95)
    jump = np.clip(trans[0, 1]+trans[1, 0], 1e-6, .999999)
    rate_sum = -np.log1p(-jump)/dt
    rates = np.clip(rate_sum*np.array([trans[0, 1], trans[1, 0]])/jump, .1, 3.)
    return ll, rates.tolist(), efficiencies.tolist()

def reference(problem, observe):
    traces = [np.array(observe(.2, 400)["counts"], float) for _ in range(2)]
    counts = np.concatenate(traces)
    ratio = counts[:, 1]/np.maximum(1, counts.sum(axis=1))
    excess = float(np.var(ratio)-np.mean(ratio*(1-ratio)/np.maximum(1, counts.sum(axis=1)-1)))
    if excess < .015:
        return dict(abstain=True, rates=[], efficiencies=[], confidence=.95)
    best = max((_fit(traces, .2, init) for init in ((.2, .8), (.35, .65))), key=lambda x:x[0])
    return dict(abstain=False, rates=best[1], efficiencies=best[2], confidence=.9)

infer_kinetics = reference
