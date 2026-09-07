"""Truth-blind weighted concordia/discordia reference for UPbConcordiaInference."""
from __future__ import annotations

import math

import numpy as np


def _curve(age_myr, lambdas):
    years = age_myr * 1.0e6
    return np.array([math.expm1(lambdas["u235"] * years), math.expm1(lambdas["u238"] * years)])


def _single_fit(points, sigmas, lambdas, bounds):
    best = (float("inf"), None)
    for step in (20.0, 2.0, 0.2):
        if best[1] is None:
            lo, hi = bounds
        else:
            lo, hi = max(bounds[0], best[1] - 2.0 * step * 10.0), min(bounds[1], best[1] + 2.0 * step * 10.0)
        for age in np.arange(lo, hi + 0.5 * step, step):
            objective = float(np.sum(((points - _curve(age, lambdas)) / sigmas) ** 2))
            if objective < best[0]:
                best = (objective, float(age))
    return best[1], float(best[0] / max(1, 2 * len(points) - 1))


def _discordia_fit(points, sigmas, lambdas, age_bounds, loss_bounds):
    count = len(points)
    best = (float("inf"), None, None)

    def visit(old_values, young_values):
        nonlocal best
        for old in old_values:
            old_point = _curve(old, lambdas)
            for young in young_values:
                if young + 100.0 >= old:
                    continue
                young_point = _curve(young, lambdas)
                direction = old_point - young_point
                weighted_direction = direction / sigmas
                weighted_offset = (points - young_point) / sigmas
                alpha = np.sum(weighted_offset * weighted_direction, axis=1) / np.sum(weighted_direction ** 2, axis=1)
                alpha = np.clip(alpha, 0.0, 1.0)
                predicted = young_point + alpha[:, None] * direction
                objective = float(np.sum(((points - predicted) / sigmas) ** 2))
                if objective < best[0]:
                    best = (objective, float(old), float(young))

    visit(np.arange(age_bounds[0], age_bounds[1] + 10.0, 20.0),
          np.arange(loss_bounds[0], loss_bounds[1] + 10.0, 20.0))
    for step, radius in ((2.0, 30.0), (0.2, 3.0)):
        old_values = np.arange(max(age_bounds[0], best[1] - radius),
                               min(age_bounds[1], best[1] + radius) + step / 2.0, step)
        young_values = np.arange(max(loss_bounds[0], best[2] - radius),
                                 min(loss_bounds[1], best[2] + radius) + step / 2.0, step)
        visit(old_values, young_values)
    dof = max(1, 2 * count - (count + 2))
    return best[1], best[2], best[0] / dof


def _interpret(problem, rows, use_uncertainties=True, refuse=True, round_to=None):
    descriptors = problem["grain_descriptors"]
    position_by_id = {row["grain_id"]: row["domain_position"] for row in descriptors}
    rows.sort(key=lambda row: position_by_id[row["grain_id"]])
    points = np.array([[row["pb207_u235"], row["pb206_u238"]] for row in rows])
    if use_uncertainties:
        sigmas = np.array([[row["sigma_pb207_u235"], row["sigma_pb206_u238"]] for row in rows])
    else:
        sigmas = np.ones_like(points)
    lambdas = problem["decay_constants_per_year"]
    single_age, single_reduced = _single_fit(points, sigmas, lambdas, problem["age_bounds_myr"])
    old, young, discordia_reduced = _discordia_fit(
        points, sigmas, lambdas, problem["age_bounds_myr"], problem["lead_loss_age_bounds_myr"])
    evidence = [row["query_id"] for row in rows]
    if round_to:
        single_age = round(single_age / round_to) * round_to
        old = round(old / round_to) * round_to
        young = round(young / round_to) * round_to

    if single_reduced < 8.0:
        return {"history": "concordant", "crystallization_age_myr": single_age,
                "confidence": 0.88, "evidence_query_ids": evidence, "abstain": False}
    if refuse and discordia_reduced > 8.0:
        return {"confidence": 0.82, "evidence_query_ids": evidence, "abstain": True}
    return {"history": "lead_loss", "crystallization_age_myr": old,
            "lead_loss_age_myr": young, "confidence": 0.84,
            "evidence_query_ids": evidence, "abstain": False}


def infer_with_policy(problem, measure, count=6, precision="analytical", selection="span",
                      use_uncertainties=True, refuse=True, round_to=None):
    descriptors = sorted(problem["grain_descriptors"], key=lambda row: row["domain_position"])
    if selection == "span":
        indices = np.linspace(0, len(descriptors) - 1, count).round().astype(int)
    elif selection == "stratified_quality":
        bins = np.array_split(np.arange(len(descriptors)), count)
        indices = [max(group, key=lambda i: descriptors[int(i)]["expected_signal_quality"])
                   for group in bins]
    elif selection == "quality":
        chosen = sorted(descriptors, key=lambda row: -row["expected_signal_quality"])[:count]
        indices = [descriptors.index(row) for row in chosen]
    else:
        indices = np.arange(count)
    rows = [measure(int(descriptors[i]["grain_id"]), precision) for i in indices]
    return _interpret(problem, rows, use_uncertainties=use_uncertainties, refuse=refuse,
                      round_to=round_to)


def infer_upb_history(problem, measure):
    # Six highest-signal analytical measurements use exactly 18 units. Position remains public so
    # a stronger candidate can trade endpoint leverage against precision instead of copying this.
    return infer_with_policy(problem, measure, selection="quality")
