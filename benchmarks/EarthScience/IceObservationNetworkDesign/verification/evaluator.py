"""Deterministic linear-Gaussian ice-sheet observation-system simulation experiment."""

from __future__ import annotations

import math

import numpy as np

STATE_DIM = 6
N_OBSERVATIONS = 28
ENSEMBLE_SIZE = 24
OBS_TYPES = ("velocity", "elevation", "thickness", "grounding_line", "basal_radar")
DEVELOPMENT_SEEDS = (17011, 17021, 17033, 17047)
HELDOUT_SEEDS = (27011, 27023)
SHIFTS = (
    {"sensitivity": 0.84, "noise": 1.25, "dynamics": 1.08},
    {"sensitivity": 1.12, "noise": 1.15, "dynamics": 0.90},
    {"sensitivity": 0.92, "noise": 1.45, "dynamics": 1.18},
)


def _world(seed):
    rng = np.random.default_rng(int(seed))
    raw = rng.normal(size=(STATE_DIM, STATE_DIM))
    prior = raw @ raw.T
    scale = np.sqrt(np.diag(prior))
    prior = prior / np.outer(scale, scale)
    prior += 0.35 * np.eye(STATE_DIM)
    catalog = []
    proxy_h = np.zeros((N_OBSERVATIONS, STATE_DIM))
    for index in range(N_OBSERVATIONS):
        obs_type = OBS_TYPES[index % len(OBS_TYPES)]
        x = ((7 * index + seed % 11) % N_OBSERVATIONS) / (N_OBSERVATIONS - 1)
        y = ((11 * index + seed % 7) % N_OBSERVATIONS) / (N_OBSERVATIONS - 1)
        year = float((index % 4) * 5)
        cost = 1 + (index % len(OBS_TYPES)) // 2
        noise = (0.11 + 0.025 * (index % 5)) * (1.0 + 0.25 * y)
        row = rng.normal(0.0, 0.18, STATE_DIM)
        row[index % STATE_DIM] += 0.85 + 0.35 * x
        row[(index + 2) % STATE_DIM] += 0.30 * (1.0 - y)
        proxy_h[index] = row
        catalog.append({"index": index, "observation_type": obs_type,
                        "x_normalized": float(x), "y_normalized": float(y),
                        "year": year, "cost_units": int(cost), "noise_std": float(noise)})
    forecast = np.asarray(((780.0, -260.0, 190.0, 120.0, 70.0, -45.0),
                           (28.0, 42.0, -18.0, 35.0, 24.0, 12.0),
                           (0.078, 0.112, -0.045, 0.092, 0.061, 0.025)))
    exact_h = proxy_h.copy()
    exact_h *= (0.88 + 0.24 * np.asarray([row["y_normalized"] for row in catalog]))[:, None]
    exact_h += 0.045 * np.roll(proxy_h, 1, axis=1)
    exact_forecast = forecast + np.asarray(((35.0, -20.0, 12.0, 0.0, 8.0, -5.0),
                                            (1.5, -2.0, 0.5, 2.2, -0.8, 0.6),
                                            (0.006, -0.004, 0.002, 0.003, 0.0, 0.001)))
    return {"seed": seed, "prior": prior, "catalog": catalog, "proxy_h": proxy_h,
            "exact_h": exact_h, "forecast": forecast, "exact_forecast": exact_forecast}


def _public_problem(world):
    return {
        "observation_catalog": [dict(row) for row in world["catalog"]],
        "proxy_sensitivity": world["proxy_h"].copy(),
        "prior_covariance": world["prior"].copy(),
        "forecast_matrix": world["forecast"].copy(),
        "forecast_names": ["grounding_line_position", "twenty_year_mass_loss", "sea_level_equivalent"],
        "forecast_units": ["m", "Gt", "mm"],
        "budget_units": 18,
        "selection_size_bounds": np.asarray((3, 10), dtype=int),
        "archive_size_bounds": np.asarray((4, 16), dtype=int),
    }


def _validate(submission, problem):
    if not isinstance(submission, dict) or set(submission) != {"plans"}:
        raise ValueError("submission must contain only plans")
    plans = submission["plans"]
    if not isinstance(plans, (list, tuple)):
        raise ValueError("plans must be a list")
    alo, ahi = map(int, problem["archive_size_bounds"])
    if not alo <= len(plans) <= ahi:
        raise ValueError("archive size outside bounds")
    output, seen = [], set()
    costs = np.asarray([row["cost_units"] for row in problem["observation_catalog"]], dtype=float)
    slo, shi = map(int, problem["selection_size_bounds"])
    for plan in plans:
        indices = np.asarray(plan)
        if indices.ndim != 1 or not slo <= len(indices) <= shi or np.any(indices != indices.astype(int)):
            raise ValueError("each plan must be a one-dimensional integer selection")
        indices = indices.astype(int)
        if len(np.unique(indices)) != len(indices) or np.any(indices < 0) or np.any(indices >= len(costs)):
            raise ValueError("observation indices must be unique and in range")
        if float(np.sum(costs[indices])) > problem["budget_units"] + 1e-9:
            raise ValueError("observation plan exceeds budget")
        fingerprint = tuple(sorted(int(value) for value in indices))
        if fingerprint in seen:
            raise ValueError("plans must be unique")
        seen.add(fingerprint)
        output.append(np.asarray(fingerprint, dtype=int))
    return output


def _crps_normal(mean, std, truth):
    z = (truth - mean) / std
    phi = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + np.asarray([
        math.erf(float(value) / math.sqrt(2.0)) for value in np.ravel(z)
    ]).reshape(np.shape(z)))
    return std * (z * (2.0 * cdf - 1.0) + 2.0 * phi - 1.0 / math.sqrt(math.pi))


def _plan_metrics(world, indices, shift=None):
    shift = shift or {"sensitivity": 1.0, "noise": 1.0, "dynamics": 1.0}
    prior = world["prior"]
    hp = world["proxy_h"][indices]
    he = world["exact_h"][indices] * shift["sensitivity"]
    noise = np.asarray([world["catalog"][i]["noise_std"] for i in indices]) * shift["noise"]
    covariance = hp @ prior @ hp.T + np.diag(noise ** 2)
    gain = prior @ hp.T @ np.linalg.inv(covariance)
    posterior = prior - gain @ hp @ prior
    posterior = 0.5 * (posterior + posterior.T) + 1e-10 * np.eye(STATE_DIM)
    g_proxy = world["forecast"]
    g_exact = world["exact_forecast"] * shift["dynamics"]
    predictive_std = np.sqrt(np.maximum(np.diag(g_proxy @ posterior @ g_proxy.T), 1e-12))
    rng = np.random.default_rng(world["seed"] + 7919 * sum(int(i) + 1 for i in indices)
                                + int(100 * shift["noise"]))
    truth_states = rng.multivariate_normal(np.zeros(STATE_DIM), prior, size=ENSEMBLE_SIZE)
    errors, crps_values = [], []
    for state in truth_states:
        observation = he @ state + rng.normal(0.0, noise)
        estimate = gain @ observation
        truth_forecast = g_exact @ state
        predicted_forecast = g_proxy @ estimate
        errors.append(predicted_forecast - truth_forecast)
        crps_values.append(_crps_normal(predicted_forecast, predictive_std, truth_forecast))
    errors = np.asarray(errors)
    rmse = np.sqrt(np.mean(errors ** 2, axis=0))
    crps = float(np.mean(np.asarray(crps_values) / np.asarray((1000.0, 100.0, 0.3))))
    sign, logdet = np.linalg.slogdet(posterior)
    cost = float(sum(world["catalog"][int(i)]["cost_units"] for i in indices))
    prior_std = np.sqrt(np.diag(g_exact @ prior @ g_exact.T))
    forecast_skill = float(np.clip(1.0 - np.mean(rmse / prior_std), 0.0, 1.0))
    return {"rmse": rmse, "mean_normalized_crps": crps,
            "posterior_trace": float(np.trace(posterior)),
            "posterior_logdet": float(logdet if sign > 0 else 1e6),
            "cost_units": cost, "forecast_skill": forecast_skill}


def _hypervolume(world, plans, shift=None):
    points, rows = [], []
    for plan in plans:
        metrics = _plan_metrics(world, plan, shift)
        rows.append(metrics)
        cost_quality = float(np.clip(1.0 - metrics["cost_units"] / 18.0, 0.0, 1.0))
        points.append((metrics["forecast_skill"], cost_quality))
    nondominated = [p for p in points if not any(q[0] >= p[0] and q[1] >= p[1]
                                                 and (q[0] > p[0] or q[1] > p[1]) for q in points)]
    area, previous = 0.0, 0.0
    for skill, cost_quality in sorted(set(nondominated)):
        area += max(0.0, skill - previous) * cost_quality
        previous = max(previous, skill)
    return float(area), rows


def _baseline_archive(world):
    catalog = sorted(world["catalog"], key=lambda row: (row["cost_units"], row["x_normalized"], row["index"]))
    return [np.asarray([row["index"] for row in catalog[offset:offset + 3]], dtype=int) for offset in range(4)]


def _reference_archive(world):
    problem = _public_problem(world)
    hp, prior, g = problem["proxy_sensitivity"], problem["prior_covariance"], problem["forecast_matrix"]
    costs = np.asarray([row["cost_units"] for row in problem["observation_catalog"]])
    plans = []
    for target_cost in (7, 9, 11, 13, 15, 16, 17, 18):
        selected = []
        while len(selected) < 10:
            best = None
            for index in range(len(costs)):
                if index in selected or np.sum(costs[selected]) + costs[index] > target_cost:
                    continue
                trial = selected + [index]
                h = hp[trial]
                r = np.diag([problem["observation_catalog"][i]["noise_std"] ** 2 for i in trial])
                post = prior - prior @ h.T @ np.linalg.inv(h @ prior @ h.T + r) @ h @ prior
                objective = float(np.trace(g @ post @ g.T))
                if best is None or objective < best[0]:
                    best = (objective, index)
            if best is None:
                break
            selected.append(best[1])
        if len(selected) >= 3:
            plans.append(np.asarray(sorted(selected), dtype=int))
    unique = []
    for plan in plans:
        if not any(np.array_equal(plan, old) for old in unique):
            unique.append(plan)
    return unique[:16]


def _normalize(value, baseline, reference):
    if reference <= baseline + 1e-12:
        return 0.0
    return float(np.clip((value - baseline) / (reference - baseline), 0.0, 1.0))


def _evaluate_problem(candidate, seed, split, index):
    world = _world(seed)
    problem = _public_problem(world)
    try:
        plans = _validate(candidate(problem), problem)
        exact_hv, rows = _hypervolume(world, plans)
        proxy_world = dict(world)
        proxy_world["exact_h"] = world["proxy_h"]
        proxy_world["exact_forecast"] = world["forecast"]
        proxy_hv, _ = _hypervolume(proxy_world, plans)
        baseline_hv, _ = _hypervolume(world, _baseline_archive(world))
        reference_plans = _reference_archive(world)
        reference_hv, _ = _hypervolume(world, reference_plans)
        shifted = [_hypervolume(world, plans, shift)[0] for shift in SHIFTS]
        baseline_shifted = [_hypervolume(world, _baseline_archive(world), shift)[0] for shift in SHIFTS]
        reference_shifted = [_hypervolume(world, reference_plans, shift)[0] for shift in SHIFTS]
        robust_scores = [_normalize(v, b, r) for v, b, r in zip(shifted, baseline_shifted, reference_shifted)]
        best = min(rows, key=lambda row: np.mean(row["rmse"] / np.asarray((1000.0, 100.0, 0.3))))
        return {"split": split, "problem_index": index, "valid": True,
                "score": _normalize(exact_hv, baseline_hv, reference_hv),
                "robustness_score": min(robust_scores), "raw_exact_hypervolume": exact_hv,
                "raw_proxy_hypervolume": proxy_hv,
                "grounding_line_rmse_m": float(best["rmse"][0]),
                "mass_loss_rmse_gt": float(best["rmse"][1]),
                "sea_level_rmse_mm": float(best["rmse"][2]),
                "mean_normalized_crps": best["mean_normalized_crps"],
                "posterior_trace": best["posterior_trace"], "posterior_logdet": best["posterior_logdet"]}
    except Exception:
        return {"split": split, "problem_index": index, "valid": False, "score": 0.0,
                "robustness_score": 0.0, "raw_exact_hypervolume": 0.0,
                "raw_proxy_hypervolume": 0.0, "grounding_line_rmse_m": 1e12,
                "mass_loss_rmse_gt": 1e12, "sea_level_rmse_mm": 1e12,
                "mean_normalized_crps": 1e12, "posterior_trace": 1e12, "posterior_logdet": 1e12}


def evaluate(design_ice_observation_network):
    development = [_evaluate_problem(design_ice_observation_network, seed, "development", i)
                   for i, seed in enumerate(DEVELOPMENT_SEEDS)]
    heldout = [_evaluate_problem(design_ice_observation_network, seed, "heldout", i)
               for i, seed in enumerate(HELDOUT_SEEDS)]
    dev_valid, hold_valid = all(r["valid"] for r in development), all(r["valid"] for r in heldout)
    return {
        "combined_score": float(np.mean([r["score"] for r in development])) if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": float(np.mean([r["valid"] for r in development])),
        "robustness_score": float(np.mean([r["robustness_score"] for r in development])) if dev_valid else 0.0,
        "development_exact_hypervolume": float(np.mean([r["raw_exact_hypervolume"] for r in development])),
        "development_proxy_hypervolume": float(np.mean([r["raw_proxy_hypervolume"] for r in development])),
        "development_grounding_line_rmse_m": float(np.mean([r["grounding_line_rmse_m"] for r in development])),
        "development_mass_loss_rmse_gt": float(np.mean([r["mass_loss_rmse_gt"] for r in development])),
        "development_sea_level_rmse_mm": float(np.mean([r["sea_level_rmse_mm"] for r in development])),
        "development_mean_normalized_crps": float(np.mean([r["mean_normalized_crps"] for r in development])),
        "heldout_score": float(np.mean([r["score"] for r in heldout])) if hold_valid else 0.0,
        "heldout_feasibility_rate": float(np.mean([r["valid"] for r in heldout])),
        "heldout_robustness_score": float(np.mean([r["robustness_score"] for r in heldout])) if hold_valid else 0.0,
        "per_problem": development + heldout,
    }
