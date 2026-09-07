"""Standalone input-only classical reference; no world generator or truth."""

from copy import deepcopy

import numpy as np

from scipy.integrate import solve_ivp

from scipy.optimize import least_squares

def isotopomers(problem, net, exchange, enrichment, times):
    pa, pb, pc = problem["pool_sizes"]
    def rhs(t, y):
        q = enrichment*(-np.expm1(-2*net*t/pa))
        monomer = np.array([1-q, q])
        source = np.outer(monomer, monomer).ravel()
        b, c = y[:4], y[4:]
        return np.r_[(net*source+exchange*c-(net+exchange)*b)/pb,
                     ((net+exchange)*b-(net+exchange)*c)/pc]
    initial = np.array([1., 0, 0, 0, 1., 0, 0, 0])
    result = solve_ivp(rhs, (0., max(times)), initial, t_eval=times, rtol=2e-8, atol=2e-10)
    if not result.success:
        raise RuntimeError("isotope integration failed")
    return result.y.T.reshape(-1, 2, 4)

def distributions(problem, net, exchange, enrichment, times):
    full = isotopomers(problem, net, exchange, enrichment, times)
    return np.stack([full[:, :, 0], full[:, :, 1]+full[:, :, 2], full[:, :, 3]], axis=2)

def reference(problem, trace):
    observation = trace("full", list(range(6)))
    data = np.asarray(observation["counts"])/10000
    if np.max(1-data[:, :, 0]) < .01:
        return dict(abstain=True, fluxes={}, confidence=.99)
    def residual(theta):
        prediction = distributions(problem, *theta, 1., problem["sampling_times"])
        # Marginal binomial standard deviations, floored for boundary cells.
        return ((prediction-data)/np.sqrt(np.maximum(data*(1-data), .002))).ravel()
    fits = [least_squares(residual, start, bounds=([.001, 0.], [1.2, 2.]), max_nfev=45)
            for start in ([.25, .3], [.6, 1.2], [1., .6])]
    best = min(fits, key=lambda fit: float(fit.fun@fit.fun))
    # Local rank check is a reference heuristic, not a general profile-likelihood proof.
    singular = np.linalg.svd(best.jac, compute_uv=False)
    if singular[-1]/singular[0] < 1e-3:
        return dict(abstain=True, fluxes={}, confidence=.8)
    return dict(abstain=False, fluxes=dict(net=float(best.x[0]), exchange_total=float(best.x[1])), confidence=.9)

infer_fluxes = reference
