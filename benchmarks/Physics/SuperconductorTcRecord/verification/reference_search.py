"""Truth-blind reference for SuperconductorTcRecord.

Reads only `problem` and the `probe` callback; never touches the hidden evaluator module. Applies
the given Allen-Dynes formula itself to each probe's (lambda_hat, omega_log_k_hat) -- exactly the
computation a candidate is expected to do. Screens every feasible family with one probe at its
historical-proxy pressure (a moderate 215 GPa placeholder when no proxy pressure is quoted),
discards anything the probe flags as not dynamically_stable, then climbs in pressure from the
best-screened family (since higher pressure tends to raise Tc within a stable window here) until
a probe fails to improve or reports instability, backing off by half each time that happens. This
is a budget-respecting witness, not an exhaustive scan of the continuous pressure axis: it can
stop short of a family's true stability-window edge, leaving room for a finer search to score
higher.
"""
from __future__ import annotations

import math

MU_STAR = 0.10
_DEFAULT_SCREEN_PRESSURE_GPA = 215.0  # "no quoted proxy pressure, but a similar hydride regime"


def _allen_dynes_tc(lam, omega_log_k, mu_star=MU_STAR):
    denom = lam - mu_star * (1.0 + 0.62 * lam)
    if denom <= 1e-9 or omega_log_k <= 0.0:
        return 0.0
    return (omega_log_k / 1.2) * math.exp(-1.04 * (1.0 + lam) / denom)


def design_superconductor(problem, probe):
    families = list(problem["families"])
    proxy = dict(problem["historical_proxy"])
    ceiling = float(problem["apparatus_pressure_ceiling_gpa"])
    budget = int(problem["probe_budget_calls"])

    calls_used = 0

    def do_probe(family, pressure_gpa):
        nonlocal calls_used
        pressure_gpa = max(0.0, min(pressure_gpa, ceiling))
        result = probe(family, pressure_gpa)
        calls_used += 1
        if not result["dynamically_stable"]:
            return -1.0, pressure_gpa
        tc = _allen_dynes_tc(result["lambda_hat"], result["omega_log_k_hat"])
        return tc, pressure_gpa

    # Stage 1: replicate-averaged screening. A single noisy probe cannot reliably separate two
    # families whose proxy pressures are within noise distance of each other, so this spends two
    # probes per family on the top few candidates by historical-proxy Tc (a family with no quoted
    # number ranks by the same placeholder used as its screening pressure), skipping MgB2 -- no
    # hydride proxy is ever remotely close to its 39 K, so a probe there is not informative.
    def priority(family):
        info = proxy[family]
        return info["tc_range_k"][1] if info["tc_range_k"] is not None else _DEFAULT_SCREEN_PRESSURE_GPA

    ranked = sorted((f for f in families if f != "MgB2boride"), key=priority, reverse=True)
    best_family, best_pressure, best_tc = None, 0.0, -1.0
    for family in ranked:
        if calls_used > budget - 2:
            break
        info = proxy[family]
        screen_pressure = info["pressure_gpa"] if info["pressure_gpa"] is not None else _DEFAULT_SCREEN_PRESSURE_GPA
        readings = []
        for _ in range(2):
            tc, pressure_gpa = do_probe(family, screen_pressure)
            readings.append(tc)
        mean_tc = sum(readings) / len(readings)
        if mean_tc > best_tc:
            best_tc, best_family, best_pressure = mean_tc, family, screen_pressure
    if best_family is None and "MgB2boride" in families and calls_used < budget:
        tc, pressure_gpa = do_probe("MgB2boride", 0.0)
        best_tc, best_family, best_pressure = tc, "MgB2boride", pressure_gpa

    if best_family is None:
        return {"family": families[0], "pressure_gpa": 0.0, "predicted_tc_k": 0.0, "confidence": 0.1}

    # Stage 2: climb in pressure (Tc tends to rise toward a family's stability-window edge here);
    # back off by half whenever a step fails to improve or reports instability.
    step = 20.0
    while calls_used < budget and step >= 2.0:
        candidate = best_pressure + step
        if candidate > ceiling:
            step /= 2.0
            continue
        tc, pressure_gpa = do_probe(best_family, candidate)
        if tc > best_tc:
            best_tc, best_pressure = tc, pressure_gpa
        else:
            step /= 2.0

    return {
        "family": best_family,
        "pressure_gpa": best_pressure,
        "predicted_tc_k": max(0.0, float(best_tc)),
        "confidence": 0.6,
    }
