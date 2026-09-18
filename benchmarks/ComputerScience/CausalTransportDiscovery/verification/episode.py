"""Private simulator for transport of heterogeneous dose-response curves.

Synthetic construction pilot, not an empirical expert-difficulty claim.
The trusted session owns budget accounting and immutable final commitment.
"""
from __future__ import annotations

import copy
import math

import numpy as np


TASK_ID = "CausalDiscovery/CausalTransportDiscovery"
CELLS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
SITES = ("bridge-a", "bridge-b", "bridge-c", "bridge-d")
MODIFIERS = ("X", "Z", "X:Z")
LIMIT = 0.35
BUDGET = 12000


def basis(dose):
    d = np.asarray(dose, dtype=float)
    return np.stack((3 * d * (1 - d) ** 2, 3 * d * d * (1 - d), d ** 3), axis=-1)


def ratio(numerator, denominator):
    numerator, denominator = int(numerator), int(denominator)
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def number(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite public-range number")
    if not lower <= value <= upper or not math.isfinite(value):
        raise ValueError("number outside public range")


def integer(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError("integer outside public range")


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("unexpected object fields")


class TransportEnvironment:
    task_id = TASK_ID
    budget_units = BUDGET

    def __init__(self, seed):
        integer(seed, 0, 2 ** 63 - 1)
        self._seed = seed
        self._family, self._variant = divmod(seed, 2)
        # Access is independent of effect coefficients and recruitment labels.
        nuisance = np.random.default_rng([self._family, 501])
        self._blocked = 1 if self._family % 3 == 0 else None
        self._site_probabilities = {}
        for x in (-1, 1):
            probabilities = nuisance.uniform(0.06, 0.94, 4)
            enriched = int(nuisance.integers(4))
            # Availability of a useful discordant bridge is guaranteed, but its
            # identity and all other enrichments vary independently of effects.
            probabilities[enriched] = nuisance.uniform(0.80, 0.97) if x == -1 else nuisance.uniform(0.03, 0.20)
            for site, p in zip(SITES, probabilities):
                self._site_probabilities[(site, x)] = float(p)
        self._target_weights = nuisance.dirichlet(np.ones(4), size=3)
        coefficients_rng = np.random.default_rng([self._family, 601])
        base = coefficients_rng.uniform(-0.07, 0.07, 3)
        terms = coefficients_rng.uniform(-0.15, 0.15, (3, 3))
        mask = coefficients_rng.integers(0, 2, 3)
        terms *= mask[:, None]
        coefficients = np.array([base + x * terms[0] + z * terms[1] + x * z * terms[2]
                                 for x, z in CELLS])
        coefficients *= min(1.0, 0.28 / max(0.001, float(np.abs(coefficients).max())))
        # Paired worlds differ only in the discordant (-1,+1) cell. Every source
        # experiment and, when that cell is inaccessible, every available tool
        # has exactly the same distribution and shared noise in the pair.
        if self._blocked is not None:
            shifted = coefficients_rng.uniform(-0.30, 0.30, 3)
            coefficients[1] = shifted if self._variant == 0 else -shifted
        elif self._variant:
            # Swapping the two discordant curves exchanges X and Z modifiers,
            # preserving source curves and a diversity of actual modifier sets.
            coefficients[[1, 2]] = coefficients[[2, 1]]
        self._coefficients = coefficients
        self._calls = 0

    def public_problem(self):
        return {
            "task_id": self.task_id, "contract_version": "transport-dose-pilot-v1",
            "budget_units": self.budget_units,
            "cells": [list(cell) for cell in CELLS], "sites": ["source"] + list(SITES),
            "source_support": [[-1, -1], [1, 1]],
            "bridge_accessible_cells": [list(cell) for i, cell in enumerate(CELLS) if i != self._blocked],
            "target_populations": [{"id": "target-" + str(i), "cell_weights": row.tolist()}
                                   for i, row in enumerate(self._target_weights)],
            "response_model": {
                "outcome": "Bernoulli; P(Y=1|X,Z,do(d)) = 0.5 + sum_j theta[X,Z,j] * B_j(d)",
                "dose": [0.0, 1.0], "basis": ["3*d*(1-d)^2", "3*d^2*(1-d)", "d^3"],
                "coefficient_bounds": [-LIMIT, LIMIT],
                "control_mean": 0.5,
                "transport_assumption": "Cell response curves are site-invariant; sites change the X,Z mixture only.",
                "modifier_semantics": "X, Z, X:Z are Hadamard contrasts of four cell coefficient vectors; recover effect heterogeneity, not a microscopic causal mechanism.",
                "modifiers": list(MODIFIERS),
                "modifier_resolution": {"negligible_curve_rms": 0.02, "meaningful_curve_rms": 0.05,
                                        "between": "unresolved; no mandatory unique label", "grid": "101 uniform doses in [0,1]"},
            },
            "sampling": (
                "X is measured freely and is selected as a recruitment stratum, not manipulated. "
                "Z is a pre-treatment binary biomarker. Source has Z=X. Bridge enrollment draws Z "
                "from an unknown site/X-dependent distribution, restricted to accessible cells. "
                "Dose is randomized; all enrolled outcomes are observed. Biomarker assay slots "
                "sample individuals uniformly without replacement, independently of their outcomes. "
                "Assayed Z and Y are paired. Surveys reveal biomarker enrichment before intervention."
            ),
            "tools": {
                "survey": {"keys": ["site", "x", "n"], "n": [8, 256], "cost": "4*n",
                           "returns": "site,x,n,z_values; target recruitment distribution, not deployment weights"},
                "trial": {"keys": ["site", "x", "dose", "n", "assay_n"], "n": [8, 256],
                          "assay_n": "integer 0..n", "cost": "n+3*assay_n",
                          "returns": "site,x,dose,n,assay_probability,records:[{y,z}]; unassayed z is null"},
            },
            "claim_schema": {
                "keys": ["decision", "curves", "modifiers"], "decision": ["discover", "partial", "abstain"],
                "curves": "four cell-ordered objects: estimated:boolean, coefficients:3 numbers or null, intervals:3 ordered endpoint pairs, covariance:3x3 symmetric positive-semidefinite matrix or null",
                "coefficient_limits": [-LIMIT, LIMIT], "nominal_interval_coverage": 0.95,
                "unestimated": "coefficients=null, covariance=null and each interval=[-0.35,0.35]; contributes no discovery credit",
                "modifiers": "unique subset of X,Z,X:Z, or null if not claimed; full set is not obligatory",
                "abstain": "curves=[] and modifiers=null",
                "partial": "some cell curves are unestimated; do not infer a global modifier set from incomplete cell support",
            },
            "confirmation": {
                "protocol": "fresh-complete-rcts-at-new-doses-and-target-mixtures",
                "new_doses": "five private doses sampled in [0.08,1], after commitment",
                "new_populations": 3, "n_per_cell_and_dose": 2048,
                "cost": "operator-reserved complete measurements; outside exploration budget",
                "limitation": "same response family; original synthetic model, no external clinical validation",
                "joint_success": "Full support only: target-dose RMSE<=0.025, all15 target-dose truths covered by nominal95% intervals, mean interval width<=0.10, and every resolved modifier decision correct. Thresholds are a declared synthetic precision target, not a clinical guideline.",
            },
            "identifiability": (
                "Source data never identify either discordant response curve. An inaccessible discordant "
                "cell can have any coefficient in [-0.35,0.35] without changing any available observation. "
                "Report those coefficient bounds and induced target-population bounds; no unique answer is required."
            ),
        }

    def action_cost(self, tool, arguments):
        if tool not in ("survey", "trial"):
            raise ValueError("unknown tool")
        exact_keys(arguments, ["site", "x", "n"] if tool == "survey" else
                   ["site", "x", "dose", "n", "assay_n"])
        if arguments["site"] not in ("source",) + SITES:
            raise ValueError("unknown recruitment site")
        integer(arguments["x"], -1, 1)
        if arguments["x"] == 0:
            raise ValueError("x must be -1 or +1")
        integer(arguments["n"], 8, 256)
        if tool == "survey":
            return 4 * arguments["n"]
        number(arguments["dose"], 0.0, 1.0)
        integer(arguments["assay_n"], 0, arguments["n"])
        return arguments["n"] + 3 * arguments["assay_n"]

    def _biomarkers(self, rng, site, x, n):
        if site == "source":
            return np.full(n, x, dtype=int)
        if self._blocked == 1 and x == -1:
            return np.full(n, -1, dtype=int)
        return np.where(rng.random(n) < self._site_probabilities[(site, x)], 1, -1)

    def experiment(self, tool, arguments):
        self.action_cost(tool, arguments)
        self._calls += 1
        rng = np.random.default_rng([self._family, 701, self._calls])
        n, x, site = arguments["n"], arguments["x"], arguments["site"]
        z = self._biomarkers(rng, site, x, n)
        if tool == "survey":
            return {"site": site, "x": x, "n": n, "z_values": z.tolist()}
        cell_indices = ((x + 1) + (z + 1) // 2).astype(int)
        means = 0.5 + self._coefficients[cell_indices].dot(basis(arguments["dose"]))
        outcomes = rng.random(n) < means
        selected = set(rng.choice(n, arguments["assay_n"], replace=False).tolist())
        return {"site": site, "x": x, "dose": arguments["dose"], "n": n,
                "assay_probability": arguments["assay_n"] / n,
                "records": [{"y": int(y), "z": int(value) if i in selected else None}
                            for i, (y, value) in enumerate(zip(outcomes, z))]}

    def validate_claim(self, claim):
        exact_keys(claim, ["decision", "curves", "modifiers"])
        if claim["decision"] not in ("discover", "partial", "abstain"):
            raise ValueError("invalid claim decision")
        modifiers = claim["modifiers"]
        if modifiers is not None:
            if (not isinstance(modifiers, list) or any(m not in MODIFIERS for m in modifiers)
                    or len(set(modifiers)) != len(modifiers)):
                raise ValueError("invalid modifier set")
        if claim["decision"] == "abstain":
            if claim["curves"] != [] or modifiers is not None:
                raise ValueError("abstention has no curves or modifier assertion")
            return
        if not isinstance(claim["curves"], list) or len(claim["curves"]) != 4:
            raise ValueError("four curves are required")
        for curve in claim["curves"]:
            exact_keys(curve, ["estimated", "coefficients", "intervals", "covariance"])
            if not isinstance(curve["estimated"], bool):
                raise ValueError("estimated must be boolean")
            intervals = curve["intervals"]
            if not isinstance(intervals, list) or len(intervals) != 3:
                raise ValueError("three coefficient intervals required")
            for interval in intervals:
                if not isinstance(interval, list) or len(interval) != 2:
                    raise ValueError("two endpoints required")
                for endpoint in interval:
                    number(endpoint, -LIMIT, LIMIT)
                if interval[0] > interval[1]:
                    raise ValueError("unordered interval")
            if curve["estimated"]:
                values = curve["coefficients"]
                if not isinstance(values, list) or len(values) != 3:
                    raise ValueError("three coefficients required")
                for value in values:
                    number(value, -LIMIT, LIMIT)
                covariance = curve["covariance"]
                if not isinstance(covariance, list) or len(covariance) != 3:
                    raise ValueError("3x3 covariance required")
                for row in covariance:
                    if not isinstance(row, list) or len(row) != 3:
                        raise ValueError("3x3 covariance required")
                    for value in row:
                        number(value, -1, 1)
                matrix = np.array(covariance)
                if not np.allclose(matrix, matrix.T, atol=1e-10, rtol=0) or np.linalg.eigvalsh(matrix).min() < -1e-10:
                    raise ValueError("covariance must be symmetric positive semidefinite")
            elif curve["coefficients"] is not None or curve["covariance"] is not None or intervals != [[-LIMIT, LIMIT]] * 3:
                raise ValueError("unestimated curves use full identification bounds")
        if claim["decision"] == "discover" and not all(c["estimated"] for c in claim["curves"]):
            raise ValueError("full discovery needs four estimated curves")
        if claim["decision"] == "partial" and all(c["estimated"] for c in claim["curves"]):
            raise ValueError("partial claim needs at least one unestimated curve")

    def confirm(self, claim):
        self.validate_claim(claim)
        rng = np.random.default_rng([self._family, 801])
        doses = np.sort(rng.uniform(0.08, 1.0, 5))
        weights = rng.dirichlet(np.ones(4), size=3)
        means = 0.5 + self._coefficients.dot(basis(doses).T)
        observed = rng.binomial(2048, means) / 2048.0
        return {"protocol": "fresh-complete-rcts-at-new-doses-and-target-mixtures",
                "doses": doses.tolist(), "population_weights": weights.tolist(),
                "n_per_cell_and_dose": 2048, "cell_observed_means": observed.tolist()}

    def evaluate(self, claim, confirmation):
        self.validate_claim(claim)
        if confirmation != self.confirm(claim):
            raise ValueError("substituted confirmation")
        abstained = claim["decision"] == "abstain"
        curves = claim["curves"] if not abstained else []
        accessible = [i for i in range(4) if i != self._blocked]
        estimated = [i for i, curve in enumerate(curves) if curve["estimated"]]
        supported = [i for i in estimated if i in accessible]
        b = basis(confirmation["doses"])
        errors, observed_errors, coverages, widths, interval_scores = [], [], [], [], []
        for i in supported:
            curve = curves[i]
            errors.extend((b.dot(np.array(curve["coefficients"]) - self._coefficients[i]) ** 2).tolist())
            observed_errors.extend((0.5 + b.dot(curve["coefficients"])
                                    - np.array(confirmation["cell_observed_means"])[i]) ** 2)
            for (lo, hi), truth in zip(curve["intervals"], self._coefficients[i]):
                widths.append(hi - lo)
                coverages.append(lo <= truth <= hi)
                interval_scores.append(hi - lo + 40 * max(lo - truth, 0, truth - hi))
        actual_modifier_vectors = np.array([[x, z, x * z] for x, z in CELLS]).T.dot(self._coefficients) / 4
        actual_modifiers = {m for m, vector in zip(MODIFIERS, actual_modifier_vectors) if np.linalg.norm(vector) > 1e-8}
        signal = np.sqrt(np.mean(actual_modifier_vectors.dot(basis(np.linspace(0, 1, 101)).T) ** 2, axis=1))
        active = {m for m, size in zip(MODIFIERS, signal) if size >= 0.05}
        negligible = {m for m, size in zip(MODIFIERS, signal) if size <= 0.02}
        resolved = active | negligible
        modifier_claim = claim["modifiers"] is not None
        claimed = set(claim["modifiers"] or [])
        unique_modifier_supported = self._blocked is None
        correct_modifiers = modifier_claim and unique_modifier_supported and claimed == actual_modifiers
        resolved_correct = sum((m in claimed) == (m in active) for m in resolved) if modifier_claim and unique_modifier_supported else 0
        metrics = {
            "valid": True,
            "mechanism_recovery": ratio(resolved_correct, len(resolved) if unique_modifier_supported else 0),
            "exact_generator_mask_recovery_diagnostic": ratio(int(correct_modifiers), int(unique_modifier_supported)),
            "false_discovery_rate": ratio(len(claimed & negligible) if unique_modifier_supported else 0,
                                          len(claimed & resolved) if unique_modifier_supported else 0),
            "modifier_omission_rate": ratio(len(active - claimed) if modifier_claim and unique_modifier_supported else 0,
                                           len(active) if modifier_claim and unique_modifier_supported else 0),
            "unresolved_modifier_claim_count": len(claimed - resolved) if unique_modifier_supported else 0,
            "unsupported_modifier_set_claim_rate": ratio(int(modifier_claim and not unique_modifier_supported),
                                                          int(not unique_modifier_supported)),
            "discovery_coverage": ratio(len(supported), len(accessible)),
            "claimed_curve_coverage": ratio(len(supported), len(accessible)),
            "unsupported_point_claim_rate": ratio(int(self._blocked in estimated) if self._blocked is not None else 0,
                                                   int(self._blocked is not None)),
            "correct_refusal_rate": ratio(int(not abstained and self._blocked is not None and self._blocked not in estimated),
                                          int(self._blocked is not None)),
            "abstention_rate": ratio(int(abstained), 1),
            "curve_rmse": math.sqrt(float(np.mean(errors))) if errors else None,
            "confirmation_observed_rmse": math.sqrt(float(np.mean(observed_errors))) if observed_errors else None,
            "curve_prediction_count": len(errors),
            "coefficient_interval_coverage": ratio(sum(coverages), len(coverages)),
            "mean_coefficient_interval_width": float(np.mean(widths)) if widths else None,
            "mean_coefficient_interval_score": float(np.mean(interval_scores)) if interval_scores else None,
            "population_prediction_rmse": None,
            "population_bound_coverage": ratio(0, 0),
            "mean_population_bound_width": None,
            "joint_success": ratio(0, int(self._blocked is None)),
            "evidence_kind": "new_doses_and_population_mixtures_same_synthetic_response_family",
        }
        if not abstained:
            predicted = np.array([curve["coefficients"] if curve["estimated"] else [0.0] * 3 for curve in curves])
            lower = np.array([[pair[0] for pair in curve["intervals"]] for curve in curves])
            upper = np.array([[pair[1] for pair in curve["intervals"]] for curve in curves])
            weights = np.array(confirmation["population_weights"])
            truth = weights.dot(self._coefficients).dot(b.T)
            centers = weights.dot(predicted).dot(b.T)
            variance = np.zeros_like(centers)
            for i in estimated:
                covariance = np.array(curves[i]["covariance"])
                cell_variance = np.maximum(0, np.einsum("ij,jk,ik->i", b, covariance, b))
                variance += weights[:, i:i + 1] ** 2 * cell_variance[None, :]
            se = np.sqrt(variance)
            unestimated = [i for i in range(4) if i not in estimated]
            missing_lower = weights[:, unestimated].dot(lower[unestimated]).dot(b.T) if unestimated else 0.0
            missing_upper = weights[:, unestimated].dot(upper[unestimated]).dot(b.T) if unestimated else 0.0
            lo, hi = centers - 1.96 * se + missing_lower, centers + 1.96 * se + missing_upper
            metrics["population_bound_coverage"] = ratio(int(np.sum((lo <= truth) & (truth <= hi))), truth.size)
            metrics["mean_population_bound_width"] = float(np.mean(hi - lo))
            if len(estimated) == 4 and self._blocked is None:
                metrics["population_prediction_rmse"] = math.sqrt(float(np.mean((weights.dot(predicted).dot(b.T) - truth) ** 2)))
                joint = (metrics["population_prediction_rmse"] <= 0.025
                         and bool(np.all((lo <= truth) & (truth <= hi)))
                         and metrics["mean_population_bound_width"] <= 0.10
                         and modifier_claim and resolved_correct == len(resolved))
                metrics["joint_success"] = ratio(int(joint), 1)
        return metrics


def create_environment(seed):
    return TransportEnvironment(seed)
