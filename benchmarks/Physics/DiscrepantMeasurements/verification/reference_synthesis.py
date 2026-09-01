"""A truth-blind reference for DiscrepantMeasurements.

It uses only the published table and the budgeted split test, and never reads the hidden world.

    interrogate always. A first version spent nothing when chi-square per degree of freedom was
                small, on the reasoning that a table which explains itself needs no investigation.
                That reasoning concedes the premise of the problem. A single unquoted systematic
                moves chi-square into the range an honest table already occupies - measured on
                this task, outlier worlds sit at 1.8-5.7 and sound ones at 0.4-1.9 - so declining
                to look is how a real defect gets published as a world average. It cost this
                reference four of sixteen worlds.

                Splits are bought in two kinds: the most deviant groups, because that is where a
                single unquoted systematic will be, and the most *typical* groups, because that is
                the only way to learn whether the understatement is global. Spending the whole
                budget on the deviant tail cannot separate the two - both make the tail split
                badly.
    conclude    one group inconsistent and the rest clean is that group's systematic: drop it and
                report the mean of the others. Inconsistency reaching the typical groups is a
                global understatement: keep the mean, inflate the uncertainty. Everything clean,
                with the two methods apart, is two populations and no single value.
"""
from __future__ import annotations

import math

import numpy as np

# Chi-square per degree of freedom below which the scatter corroborates the quoted errors. It is
# used to *confirm* a clean set of split tests, never to decide whether to run them.
CONSISTENT_CHI2 = 1.9

# Significance at which two methods are held to disagree.
POPULATION_SEPARATION_Z = 3.0

# Split-test z above which a group is held to be internally inconsistent.
SPLIT_INCONSISTENT_Z = 2.5


def _weighted(values, sigmas):
    weight = 1.0 / np.asarray(sigmas, dtype=float) ** 2
    mean = float(np.sum(np.asarray(values, dtype=float) * weight) / np.sum(weight))
    return mean, float(1.0 / math.sqrt(np.sum(weight)))


def synthesize_evidence(problem, split_test):
    table = problem["measurements"]
    values = np.array([row["value"] for row in table], dtype=float)
    sigmas = np.array([row["quoted_sigma"] for row in table], dtype=float)
    methods = [row["method"] for row in table]
    budget = int(problem["split_test_budget"])
    n = len(values)

    mean, unc = _weighted(values, sigmas)
    chi2 = float(np.sum(((values - mean) / sigmas) ** 2) / (n - 1))

    # Free from the table: do the two methods sit apart from each other?
    separation = 0.0
    names = sorted(set(methods))
    if len(names) == 2:
        groups = []
        for name in names:
            index = [i for i, m in enumerate(methods) if m == name]
            groups.append(_weighted(values[index], sigmas[index]))
        combined = math.hypot(groups[0][1], groups[1][1])
        if combined > 0:
            separation = abs(groups[0][0] - groups[1][0]) / combined

    # Bought: internal consistency, at both ends of the deviation ordering.
    deviation = np.abs(values - mean) / sigmas
    order = list(np.argsort(-deviation))
    deviant = order[: min(3, budget)]
    typical = [i for i in reversed(order) if i not in deviant][: budget - len(deviant)]

    z_by_group = {}
    for index in list(deviant) + list(typical):
        if len(z_by_group) >= budget:
            break
        try:
            report = split_test(int(index))
        except Exception:  # noqa: BLE001 - a refused split is not a failed analysis
            break
        gap = abs(report["first_half_value"] - report["second_half_value"])
        combined = report["half_quoted_sigma"] * math.sqrt(2.0)
        z_by_group[int(index)] = gap / combined if combined > 0 else 0.0

    inconsistent = [i for i, z in z_by_group.items() if z >= SPLIT_INCONSISTENT_Z]
    typical_bad = [i for i in inconsistent if i in typical]

    # Understatement reaching the typical groups, or more than one group carrying it, is global.
    if typical_bad or len(inconsistent) > 1:
        scale = float(np.median([max(z, 1.0) for z in z_by_group.values()]))
        return {"best_value": mean, "uncertainty": unc * max(scale, math.sqrt(max(chi2, 1.0))),
                "diagnosis": "underestimated", "confidence": 0.75, "abstain": False}

    if len(inconsistent) == 1:
        culprit = inconsistent[0]
        keep = [i for i in range(n) if i != culprit]
        clean_mean, clean_unc = _weighted(values[keep], sigmas[keep])
        return {"best_value": clean_mean, "uncertainty": clean_unc, "diagnosis": "outlier",
                "culprit_index": int(culprit), "confidence": 0.8, "abstain": False}

    # Every group internally sound. Either the methods disagree, or nothing is wrong.
    if separation >= POPULATION_SEPARATION_Z:
        return {"diagnosis": "two_populations", "confidence": 0.85, "abstain": True}
    if chi2 <= CONSISTENT_CHI2:
        return {"best_value": mean, "uncertainty": unc, "diagnosis": "consistent",
                "confidence": 0.9, "abstain": False}
    # Sound groups, no method split, and scatter the quoted errors cannot carry.
    return {"best_value": mean, "uncertainty": unc * math.sqrt(chi2),
            "diagnosis": "underestimated", "confidence": 0.5, "abstain": False}
