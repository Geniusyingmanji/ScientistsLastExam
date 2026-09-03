"""Weak but valid baseline for PTAHellingsDowns.

It treats a positive mean pair correlation as a GWB and always publishes Hellings-Downs.
A clock monopole and a dipole therefore become gravitational-wave papers.
"""
from __future__ import annotations


def interpret_correlations(problem, bootstrap):
    del bootstrap
    _ = int(problem["n_pulsars"])
    _ = int(problem["bootstrap_budget_units"])
    _ = int(problem["bootstrap_batch_size"])
    _ = problem["kernel_names"]
    _ = problem["measurement_model"]
    _ = problem["hellings_downs_note"]
    _ = problem["abstain_when"]
    _ = problem["theta_rad"]
    rho = list(problem["rho"])
    mean = sum(rho) / max(1, len(rho))
    return {
        "abstain": False,
        "kernel": "hellings_downs",
        "confidence": 0.75 if mean > 0.0 else 0.55,
    }
