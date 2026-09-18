"""Truth-blind two-phase sampling witness and intentionally cheap controls.

Only public problem fields and charged observations are used. These are method
diagnostics, not evidence that the pilot meets frontier-model difficulty gates.
"""
from __future__ import annotations

import math

import numpy as np


def audit_mean(observation):
    """Estimate the randomized cohort mean with uniform nonresponse follow-up.

    Estimate phase-one population variance by expansion and add the phase-two
    finite-population sampling variance. This is an asymptotic variance estimate;
    nominal 95% coverage still needs calibration across independent worlds.
    """
    n = observation["n_enrolled"]
    returned = np.asarray(observation["survivor_outcomes"], dtype=float)
    audited = np.asarray(observation["audited_outcomes"], dtype=float)
    missing = observation["n_missing"]
    if missing and len(audited) < 2:
        raise ValueError("at least two random follow-ups required to estimate audit uncertainty")
    if not missing:
        return float(np.mean(returned)), float(np.var(returned, ddof=1) / n)
    mean = (float(np.sum(returned)) + missing * float(np.mean(audited))) / n
    second = (float(np.sum(returned ** 2)) + missing * float(np.mean(audited ** 2))) / n
    variance = max(0.0, second - mean * mean) / (n - 1)
    fraction = len(audited) / missing
    variance += (missing / n) ** 2 * (1.0 - fraction) * float(np.var(audited, ddof=1)) / len(audited)
    return mean, variance


def _make_claim(problem, effects, variances, abstain_uncertain=True):
    weights = np.asarray(problem["target_weights"], dtype=float)
    effect = float(np.dot(weights, effects))
    se = math.sqrt(float(np.dot(weights ** 2, variances)))
    interval = [effect - 1.96 * se, effect + 1.96 * se]
    margin = problem["equivalence_margin"]
    if interval[0] > margin:
        effect_class = "positive"
    elif interval[1] < -margin:
        effect_class = "negative"
    elif interval[0] >= -margin and interval[1] <= margin:
        effect_class = "negligible"
    elif abstain_uncertain:
        return {"abstain": True, "confidence": 0.95}
    else:
        effect_class = "positive" if effect > margin else "negative" if effect < -margin else "negligible"
    return {
        "abstain": False,
        "confidence": 0.95,
        "effect_class": effect_class,
        "population_effect": effect,
        "population_interval": interval,
        "stratum_effects": [float(value) for value in effects],
        "stratum_intervals": [[float(value - 1.96 * math.sqrt(var)), float(value + 1.96 * math.sqrt(var))]
                              for value, var in zip(effects, variances)],
    }


def propose(problem, experiment):
    """Fixed balanced design: eight cells, 512 enrollments + 240 audit slots each."""
    effects, variances = [], []
    for stratum in problem["strata"]:
        cells = []
        for treatment in problem["treatment_levels"]:
            observation = experiment("trial", {"stratum": stratum, "treatment": treatment,
                                               "n": 512, "audit_n": 240})
            cells.append(audit_mean(observation))
        effects.append(cells[1][0] - cells[0][0])
        variances.append(cells[1][1] + cells[0][1])
    return _make_claim(problem, effects, variances)


def no_query(problem, experiment):
    del experiment
    return _make_claim(problem, [1.0] * 4, [0.01] * 4, abstain_uncertain=False)


def _pooled_trial(experiment, stratum, treatment, cohort_sizes):
    pooled = {"n_enrolled": 0, "n_returned": 0, "survivor_outcomes": []}
    for n in cohort_sizes:
        observation = experiment("trial", {"stratum": stratum, "treatment": treatment,
                                           "n": n, "audit_n": 0})
        pooled["n_enrolled"] += observation["n_enrolled"]
        pooled["n_returned"] += observation["n_returned"]
        pooled["survivor_outcomes"].extend(observation["survivor_outcomes"])
    return pooled


def survival_contrast(problem, experiment, cohort_sizes=(512,)):
    """Old shortcut: use only two endpoint return rates, now within each stratum."""
    effects, variances = [], []
    for stratum in problem["strata"]:
        proportions = []
        for treatment in problem["treatment_levels"]:
            observation = _pooled_trial(experiment, stratum, treatment, cohort_sizes)
            proportions.append(observation["n_returned"] / observation["n_enrolled"])
        effects.append(4.0 * (proportions[1] - proportions[0]))
        variances.append(16.0 * sum(p * (1.0 - p) / sum(cohort_sizes) for p in proportions))
    return _make_claim(problem, effects, variances, abstain_uncertain=False)


def survivors_only(problem, experiment, cohort_sizes=(512,)):
    effects, variances = [], []
    for stratum in problem["strata"]:
        cells = []
        for treatment in problem["treatment_levels"]:
            observation = _pooled_trial(experiment, stratum, treatment, cohort_sizes)
            outcomes = np.asarray(observation["survivor_outcomes"], dtype=float)
            if len(outcomes) < 2:
                return {"abstain": True, "confidence": 0.95}
            cells.append((float(np.mean(outcomes)), float(np.var(outcomes, ddof=1) / len(outcomes))))
        effects.append(cells[1][0] - cells[0][0])
        variances.append(cells[1][1] + cells[0][1])
    return _make_claim(problem, effects, variances, abstain_uncertain=False)


def survival_contrast_matched_budget(problem, experiment):
    return survival_contrast(problem, experiment, cohort_sizes=(512, 512, 448))


def survivors_only_matched_budget(problem, experiment):
    return survivors_only(problem, experiment, cohort_sizes=(512, 512, 448))


def abstain(problem, experiment):
    del problem, experiment
    return {"abstain": True, "confidence": 0.0}


solve = propose
POLICIES = {
    "reference": solve,
    "no_query": no_query,
    "abstain": abstain,
    "survival_contrast": survival_contrast,
    "survivors_only": survivors_only,
    "survival_contrast_matched_budget": survival_contrast_matched_budget,
    "survivors_only_matched_budget": survivors_only_matched_budget,
}
