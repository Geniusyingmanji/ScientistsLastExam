"""Future-protocol diagnostics, deliberately disconnected from pilot scoring.

All tests concern fresh, fixed-size confirmation sensor samples. No simulator,
model API, current cohort, optimizer, Student-t shortcut, or reward change.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from statistics import NormalDist
import time

import numpy as np

PROTOCOL = "future-claim-diagnostics-0.1"
REPLICATES = 8
SLOTS = 3
ROOT_SEED = 20261003
NOISE_MODELS = ("gaussian", "zero_clipped_gaussian")
METHODS = ("known_gaussian", "sign_flip", "gaussian_lipschitz")


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be finite and positive")
    return float(value)


def raw_interval_loss(interval, outcome, *, alpha=0.1, scale=1.0):
    """Normalized interval loss for the future measured mean; never transformed."""
    scale = _positive(scale, "scale")
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0,1)")
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError("interval requires two endpoints")
    vals = (*interval, outcome)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vals):
        raise ValueError("endpoints and outcome must be finite real numbers")
    lower, upper = interval
    if lower > upper:
        raise ValueError("interval endpoints must be ordered")
    return (upper - lower + 2 / alpha * max(lower - outcome, outcome - upper, 0)) / scale


def _pairs(control, treatment):
    c, t = np.asarray(control, dtype=float), np.asarray(treatment, dtype=float)
    if c.shape != (REPLICATES,) or t.shape != c.shape or not np.isfinite(c).all() or not np.isfinite(t).all():
        raise ValueError("exactly eight finite readings per arm are required")
    return c, t


def _sign_flip_many(differences):
    """Exhaustive two-sided conditional randomization with conservative ties."""
    rows = np.asarray(differences, dtype=float).reshape(-1, REPLICATES)
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=REPLICATES)))
    result = np.empty(len(rows))
    for start in range(0, len(rows), 512):
        x = rows[start:start + 512]
        observed = np.abs(x.sum(axis=1))
        tolerance = 64 * np.finfo(float).eps * np.abs(x).sum(axis=1)
        permuted = np.abs(x @ signs.T)
        result[start:start + len(x)] = np.mean(permuted >= (observed - tolerance)[:, None], axis=1)
    return result


def slot_evidence(control, treatment, *, noise_model, sigma_control, sigma_treatment, method):
    """A separate nonzero endpoint, without interval/width/significance gating.

The caller must establish deterministic latent response, independent replicates
and arms, known Gaussian scales before the shared sensor transform, and a fixed
readout before confirmation. The function cannot verify those design facts.
"""
    c, t = _pairs(control, treatment)
    sc, st = _positive(sigma_control, "sigma_control"), _positive(sigma_treatment, "sigma_treatment")
    if noise_model not in NOISE_MODELS or method not in METHODS:
        raise ValueError("unsupported noise model or test")
    if noise_model == "zero_clipped_gaussian" and (np.any(c < 0) or np.any(t < 0)):
        raise ValueError("zero-clipped readings cannot be negative")
    d = t - c
    mean = float(d.mean())
    variance_proxy = (sc * sc + st * st) / REPLICATES
    if method == "known_gaussian":
        if noise_model != "gaussian":
            raise ValueError("exact Gaussian test is unavailable for clipped sensor readings")
        p = math.erfc(abs(mean) / math.sqrt(2 * variance_proxy))
        null = "zero expected measured difference; exact Gaussian known-variance null"
    elif method == "sign_flip":
        if sc != st:
            raise ValueError("sign-flip route requires identical arm sensor laws and scales")
        p = float(_sign_flip_many(d)[0])
        null = "identical arm response distributions under equal latent response and common sensor law"
    else:
        p = min(1.0, 2 * math.exp(-mean * mean / (2 * variance_proxy)))
        null = "zero expected measured difference; Gaussian Lipschitz concentration bound"
    return {"method": method, "noise_model": noise_model, "mean_difference": mean,
            "raw_p_value": p, "null": null, "replicates": REPLICATES,
            "requires_fresh_fixed_confirmation": True, "mechanism_certified": False}


def holm_three_slots(p_values, *, alpha=0.05):
    """Pad unfilled slots with 1; no independence assumption across valid p's."""
    if not isinstance(p_values, (list, tuple)) or len(p_values) > SLOTS:
        raise ValueError("at most three p-values required")
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0,1)")
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in p_values):
        raise ValueError("p-values must be finite and lie in [0,1]")
    values = list(map(float, p_values)) + [1.0] * (SLOTS - len(p_values))
    order = sorted(range(SLOTS), key=lambda i: (values[i], i))
    adjusted, maximum = [1.0] * SLOTS, 0.0
    for rank, index in enumerate(order):
        maximum = max(maximum, (SLOTS - rank) * values[index])
        adjusted[index] = min(1.0, maximum)
    return {"family_alpha": alpha, "family_capacity": SLOTS, "submitted_slots": len(p_values),
            "raw_p_values_padded": values, "holm_adjusted_p_values": adjusted,
            "rejected": [p <= alpha for p in adjusted],
            "assumption": "Each selected true-null p-value is conditionally super-uniform given exploration; confirmation is not used to select/retry tests."}


def _rate(count, denominator):
    if not denominator:
        return {"events": count, "denominator": denominator, "rate": None, "wilson_95": None}
    z = NormalDist().inv_cdf(0.975)
    p, den = count / denominator, 1 + z * z / denominator
    center = (p + z * z / (2 * denominator)) / den
    radius = z * math.sqrt(p * (1 - p) / denominator + z * z / (4 * denominator ** 2)) / den
    return {"events": int(count), "denominator": int(denominator), "rate": p,
            "wilson_95": [max(0., center - radius), min(1., center + radius)]}


def _holm_many(p):
    order = np.argsort(p, axis=1, kind="stable")
    sorted_p = np.take_along_axis(p, order, axis=1)
    sorted_adj = np.minimum(1., np.maximum.accumulate(sorted_p * [3, 2, 1], axis=1))
    adj = np.empty_like(p)
    np.put_along_axis(adj, order, sorted_adj, axis=1)
    return adj


def _draw(rng, episodes, candidates, mu, clipped, shift=0.0):
    c = mu + rng.normal(size=(episodes, candidates, REPLICATES))
    t = mu + rng.normal(size=c.shape)
    if shift:
        t[:, -1, :] += shift
    if clipped:
        c, t = np.maximum(c, 0), np.maximum(t, 0)
    return c, t


def _cell(noise_model, mu, selection, episodes, seed):
    rng = np.random.default_rng(seed)
    clipped = noise_model == "zero_clipped_gaussian"
    if selection in ("exploration_then_fresh", "confirmation_peeking_invalid"):
        c, t = _draw(rng, episodes, 12, mu, clipped)
        chosen = np.argsort(np.abs((t - c).mean(axis=2)), axis=1)[:, -SLOTS:]
        if selection == "exploration_then_fresh":
            c, t = _draw(rng, episodes, SLOTS, mu, clipped)
        else:
            idx = np.broadcast_to(chosen[:, :, None], (episodes, SLOTS, REPLICATES))
            c, t = np.take_along_axis(c, idx, axis=1), np.take_along_axis(t, idx, axis=1)
    else:
        c, t = _draw(rng, episodes, SLOTS, mu, clipped, 1.5 if selection == "two_null_one_alternative" else 0.)
    d, mean = t - c, (t - c).mean(axis=2)
    null = np.ones(SLOTS, dtype=bool)
    if selection == "two_null_one_alternative":
        null[-1] = False
    p_by_method = {"sign_flip": _sign_flip_many(d).reshape(episodes, SLOTS),
                   "gaussian_lipschitz": np.minimum(1., 2 * np.exp(-mean ** 2 / (2 * (2 / REPLICATES))))}
    if not clipped:
        p_by_method["known_gaussian"] = np.array([math.erfc(abs(x) / math.sqrt(4 / REPLICATES)) for x in mean.ravel()]).reshape(episodes, SLOTS)
    methods = {}
    for method, p in p_by_method.items():
        adjusted = _holm_many(p)
        methods[method] = {"null_slot_rejection_at_0.05": _rate(int(np.sum(p[:, null] <= .05)), int(episodes * null.sum())),
                           "episode_any_null_unadjusted": _rate(int(np.sum(np.any(p[:, null] <= .05, axis=1))), episodes),
                           "episode_any_null_holm": _rate(int(np.sum(np.any(adjusted[:, null] <= .05, axis=1))), episodes),
                           "alternative_power_holm": _rate(int(np.sum(adjusted[:, ~null] <= .05)), int(episodes * (~null).sum()))}
    se = d.std(axis=2, ddof=1) / math.sqrt(REPLICATES)
    return {"noise_model": noise_model, "latent_mean_over_sigma": mu, "selection": selection,
            "episodes": episodes, "seed_spawn_key": list(seed.spawn_key), "status": "complete",
            "validity_claim": selection != "confirmation_peeking_invalid", "methods": methods,
            "old_three_sample_se_gate_unvalidated": _rate(int(np.sum(np.abs(mean[:, null]) > np.maximum(3 * se[:, null], 1e-12))), int(episodes * null.sum())),
            "known_gaussian_route": "unsupported; not applied" if clipped else "exact under declared assumptions",
            "sensor_zero_fraction": float((np.sum(c == 0) + np.sum(t == 0)) / (c.size + t.size))}


def development_calibration(*, episodes=10000, seed=ROOT_SEED):
    """Bounded sensor-law reference Monte Carlo; fixed protocols and thresholds."""
    if type(episodes) is not int or not 1 <= episodes <= 10000 or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("episodes must be integer 1..10000 and seed uint32")
    started = time.monotonic()
    cells, failures = [], []
    protocols = ("fixed_null", "exploration_then_fresh", "confirmation_peeking_invalid", "two_null_one_alternative")
    sensors = (("gaussian", 0.), ("zero_clipped_gaussian", 0.), ("zero_clipped_gaussian", .5), ("zero_clipped_gaussian", 3.))
    for sensor_index, (noise, mu) in enumerate(sensors):
        for protocol_index, protocol in enumerate(protocols):
            cell_seed = np.random.SeedSequence(seed, spawn_key=(sensor_index, protocol_index))
            try:
                cells.append(_cell(noise, mu, protocol, episodes, cell_seed))
            except Exception as error:
                failures.append({"noise_model": noise, "mu": mu, "selection": protocol, "error_type": type(error).__name__, "error": str(error)[:600]})
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(100,)))
    y = rng.normal(scale=.5, size=100000)
    z = NormalDist().inv_cdf(.95)
    loss = []
    for factor in (.8, 1., 1.2):
        a = factor * z * .5
        expected = 2 * a + 40 * (.5 * math.exp(-.5 * (a / .5) ** 2) / math.sqrt(2 * math.pi) - a * (1 - NormalDist().cdf(a / .5)))
        observed = 2 * a + 20 * np.maximum(np.abs(y) - a, 0)
        loss.append({"half_width_over_sd": factor * z, "analytic_expected_raw_loss": expected,
                     "monte_carlo_mean_raw_loss": float(observed.mean()), "monte_carlo_standard_error": float(observed.std(ddof=1) / math.sqrt(len(y))), "draws": len(y)})
    return {"protocol": PROTOCOL, "operator_only": True, "enabled_in_runner": False,
            "scope": "synthetic sensor-law calibration only; not a rescore or world/model experiment",
            "seed": seed, "episodes_per_cell": episodes, "replicates_per_arm": REPLICATES, "alpha": .05,
            "planned_cells": 16, "completed_cells": len(cells), "failures": failures,
            "status": "complete" if not failures else "completed_with_failures", "cells": cells,
            "gaussian_interval_loss_fixed_grid": loss, "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "numpy_version": np.__version__, "elapsed_seconds": time.monotonic() - started,
            "limitations": ["Monte Carlo intervals describe finite reference simulations, not a mathematical proof.",
                            "No Student-t route for clipped observations; sign-flip requires exchangeable arm laws under the null.",
                            "Fresh adaptive selection is conditional on every chosen null satisfying test assumptions; confirmation peeking is deliberately invalid.",
                            "Unfilled slots retain p=1 in a capacity-three family; forecasting participation policy remains unresolved."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--episodes", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=ROOT_SEED)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise ValueError("refusing to overwrite a development diagnostic")
    report = development_calibration(episodes=args.episodes, seed=args.seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "completed_cells": report["completed_cells"], "failures": report["failures"], "output": str(output)}))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
