"""Truth-blind marginal-likelihood reference for OccupancyDetectionDesign."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize


def _sigmoid(values):
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30.0, 30.0)))


def _fit(rows, descriptors, model):
    by_site = {}
    for row in rows:
        by_site.setdefault(int(row["site_id"]), []).append(row)
    site_ids = np.array(sorted(by_site), dtype=int)
    lookup = {int(row["site_id"]): row for row in descriptors}
    x = np.array([lookup[int(i)]["habitat_covariate"] for i in site_ids])
    pos = np.array([lookup[int(i)]["transect_position"] for i in site_ids])
    access = np.array([lookup[int(i)]["accessibility_index"] for i in site_ids])
    x2 = x * x - float(np.mean(x * x))
    spatial = np.sin(2.0 * math.pi * pos)

    def nll(theta):
        eta = theta[0] + theta[1] * x
        if model == "quadratic":
            eta = eta + theta[2] * x2
            rapid_logit, intensive_logit = theta[3], theta[4]
        elif model == "spatial":
            eta = eta + theta[2] * spatial
            rapid_logit, intensive_logit = theta[3], theta[4]
        else:
            rapid_logit, intensive_logit = theta[2], theta[3]
        psi = _sigmoid(eta)
        total = 0.0
        for j, site_id in enumerate(site_ids):
            product = 1.0
            any_detection = False
            for row in by_site[int(site_id)]:
                base = rapid_logit if row["method"] == "rapid" else intensive_logit
                p = float(_sigmoid(base + 0.45 * access[j]))
                y = bool(row["detected"])
                any_detection = any_detection or y
                product *= p if y else (1.0 - p)
            probability = psi[j] * product if any_detection else (1.0 - psi[j]) + psi[j] * product
            total -= math.log(max(probability, 1.0e-12))
        return total

    size = 5 if model != "linear" else 4
    bounds = [(-4.0, 4.0), (-4.0, 4.0)]
    if size == 5:
        bounds.append((-4.0, 4.0))
    bounds.extend([(-4.0, 3.0), (-3.0, 4.0)])
    starts = [np.zeros(size), np.linspace(-0.3, 0.3, size), np.linspace(0.4, -0.4, size)]
    fits = [minimize(nll, start, method="L-BFGS-B", bounds=bounds) for start in starts]
    best = min(fits, key=lambda fit: float(fit.fun))
    return np.asarray(best.x, dtype=float), float(best.fun), len(site_ids)


def infer_with_policy(problem, survey, use_intensive=True, site_limit=24,
                      test_nonlinearity=True, force_claim=False, blend=0.50,
                      effect_cutoff=0.25):
    descriptors = list(problem["site_descriptors"])
    if site_limit < len(descriptors):
        ordered = sorted(descriptors, key=lambda row: row["habitat_covariate"])
        indices = np.linspace(0, len(ordered) - 1, site_limit).round().astype(int)
        descriptors = [ordered[int(i)] for i in indices]
    rows = [survey(row["site_id"], "rapid") for row in descriptors]
    if use_intensive:
        remaining = problem["survey_budget_units"] - len(rows)
        intensive_count = min(len(descriptors), remaining // problem["survey_methods"]["intensive"])
        ordered = sorted(descriptors, key=lambda row: (row["transect_position"] + row["habitat_covariate"] * 0.17))
        indices = np.linspace(0, len(ordered) - 1, intensive_count).round().astype(int)
        rows.extend(survey(ordered[int(i)]["site_id"], "intensive") for i in indices)

    remaining = problem["survey_budget_units"] - sum(row["budget_cost"] for row in rows)
    if remaining:
        ordered = sorted(descriptors, key=lambda row: (row["habitat_covariate"], row["transect_position"]))
        repeat_indices = np.linspace(0, len(ordered) - 1, min(len(ordered), remaining)).round().astype(int)
        rows.extend(survey(ordered[int(i)]["site_id"], "rapid") for i in repeat_indices)

    linear, linear_nll, n_sites = _fit(rows, problem["site_descriptors"], "linear")
    best_alt_bic = float("inf")
    if test_nonlinearity:
        for model in ("quadratic", "spatial"):
            _params, alt_nll, _ = _fit(rows, problem["site_descriptors"], model)
            best_alt_bic = min(best_alt_bic, 2.0 * alt_nll + 5.0 * math.log(n_sites))
    linear_bic = 2.0 * linear_nll + 4.0 * math.log(n_sites)
    evidence = [row["query_id"] for row in rows]
    if test_nonlinearity and not force_claim and best_alt_bic + 2.0 < linear_bic:
        return {"confidence": 0.80, "evidence_query_ids": evidence, "abstain": True}

    by_site = {}
    for row in rows:
        by_site.setdefault(int(row["site_id"]), []).append(bool(row["detected"]))
    lookup = {int(row["site_id"]): row for row in problem["site_descriptors"]}
    measured_ids = sorted(by_site)
    measured_x = np.array([lookup[site_id]["habitat_covariate"] for site_id in measured_ids])
    detected = np.array([float(any(by_site[site_id])) for site_id in measured_ids])
    raw_slope = float(np.sum((measured_x - np.mean(measured_x)) * (detected - np.mean(detected)))
                      / np.sum((measured_x - np.mean(measured_x)) ** 2))
    beta = float(blend * linear[1] + (1.0 - blend) * 4.0 * raw_slope)
    if beta > effect_cutoff:
        effect = "positive"
    elif beta < -effect_cutoff:
        effect = "negative"
    else:
        effect = "none"
    habitat = np.array([row["habitat_covariate"] for row in problem["site_descriptors"]])
    likelihood_prevalence = float(np.mean(_sigmoid(linear[0] + linear[1] * habitat)))
    prevalence = float(blend * likelihood_prevalence + (1.0 - blend) * np.mean(detected))
    return {
        "effect": effect,
        "habitat_effect": beta,
        "mean_occupancy": prevalence,
        "confidence": 0.82,
        "evidence_query_ids": evidence,
        "abstain": False,
    }


def infer_occupancy(problem, survey):
    return infer_with_policy(problem, survey)
