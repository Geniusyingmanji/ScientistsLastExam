"""Trusted procedural environment for the uncalibrated audit-design pilot.

Do not copy this module or its seeds into a candidate workspace. The episode
runner owns budget enforcement, isolation and immutable claim commitment.
"""
from __future__ import annotations

import math
import sys

import numpy as np


TASK_ID = "CausalDiscovery/SurvivorshipAuditDesign"
BUDGET_UNITS = 12000
WEIGHTS = (0.10, 0.20, 0.30, 0.40)
EQUIVALENCE_MARGIN = 0.20
CONFIRMATION_N = 4096


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a JSON number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(name + " outside finite numeric range") from exc
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return value


def _interval(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(name + " must be a two-element list")
    lower, upper = [_number(x, name) for x in value]
    if lower > upper:
        raise ValueError(name + " must have ordered endpoints")
    return lower, upper


def _effect_class(effect):
    if effect > EQUIVALENCE_MARGIN:
        return "positive"
    if effect < -EQUIVALENCE_MARGIN:
        return "negative"
    return "negligible"


def _interval_supports(effect_class, interval):
    lower, upper = interval
    if effect_class == "positive":
        return lower > EQUIVALENCE_MARGIN
    if effect_class == "negative":
        return upper < -EQUIVALENCE_MARGIN
    return lower >= -EQUIVALENCE_MARGIN and upper <= EQUIVALENCE_MARGIN


class SurvivorshipAuditEnvironment:
    task_id = TASK_ID
    budget_units = BUDGET_UNITS

    def __init__(self, seed):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        # Each private triplet shares nuisance parameters and sample streams.
        # Treatment effects change while return indicators are exactly matched.
        # The triplet construction is an operator diagnostic, not candidate data.
        self._family_seed, self._variant = divmod(seed, 3)
        rng = np.random.default_rng([self._family_seed, 711])
        self._mu = rng.uniform(-0.8, 0.8, 4)
        self._beta = rng.uniform(0.8, 1.4, 4)
        self._curvature = rng.uniform(0.2, 0.5, 4)
        self._heterogeneity = rng.uniform(-0.6, 0.6, 4)
        self._selection_intercept = rng.uniform(-1.2, -0.5, 4)
        self._selection_y = rng.uniform(0.8, 1.3, 4)
        self._selection_c = rng.uniform(-0.4, 0.4, 4)
        self._selection_t = rng.uniform(-1.8, 1.8, 4)
        subgroup = rng.normal(0.0, 0.8, 4)
        subgroup -= np.dot(WEIGHTS, subgroup)
        magnitude = float(rng.uniform(0.65, 1.10))
        self._population_effect = (magnitude, 0.0, -magnitude)[self._variant]
        self._effects = subgroup + self._population_effect
        self._calls = 0

    def public_problem(self):
        return {
            "task_id": self.task_id,
            "version": "episode-pilot-v1",
            "budget_units": self.budget_units,
            "strata": [0, 1, 2, 3],
            "target_population": "deployment",
            "target_weights": list(WEIGHTS),
            "treatment_levels": [0, 1],
            "equivalence_margin": EQUIVALENCE_MARGIN,
            "interval_confidence": 0.95,
            "action_schemas": {
                "trial": {
                    "required": ["stratum", "treatment", "n", "audit_n"],
                    "additional_arguments": False,
                    "stratum": {"type": "integer", "minimum": 0, "maximum": 3},
                    "treatment": {"type": "integer", "enum": [0, 1]},
                    "n": {"type": "integer", "minimum": 32, "maximum": 512},
                    "audit_n": {"type": "integer", "minimum": 0, "maximum": "n"},
                    "cost_units": "n + 4 * audit_n; reserved audit slots are charged even when fewer people are missing",
                }
            },
            "sampling": (
                "Each trial draws a fresh randomized-treatment cohort within the requested stratum. "
                "Only selected survivors return routinely. An independent uniform sample without replacement "
                "of min(audit_n, n_missing) nonreturners is followed up with complete ascertainment. "
                "The audit probability and all counts are returned. No observational treatment assignment is used."
            ),
            "selection_assumptions": (
                "Selection depends on outcome, unmeasured prognostic variables, treatment directly, "
                "and stratum. A difference in return rates does not identify an outcome effect. "
                "Outcome response and selection may differ between strata. Random follow-up within "
                "nonreturners has no additional missingness."
            ),
            "estimand": "sum(target_weights[k] * (E[Y|do(T=1),k] - E[Y|do(T=0),k]))",
            "claim_schema": {
                "abstention": {"abstain": True, "confidence": "finite number in [0,1]"},
                "discovery_required": [
                    "abstain", "confidence", "effect_class", "population_effect",
                    "population_interval", "stratum_effects", "stratum_intervals",
                ],
                "abstain": "boolean",
                "confidence": "0.95 for a nonabstaining claim (nominal interval coverage)",
                "effect_class": ["positive", "negative", "negligible"],
                "population_effect": "finite JSON number for deployment population",
                "population_interval": "ordered pair of finite JSON numbers, nominal 95% interval",
                "stratum_effects": "four finite JSON numbers in stratum order",
                "stratum_intervals": "four ordered pairs of finite JSON numbers, marginal 95% intervals",
                "additional_fields": False,
            },
            "confirmation_protocol": {
                "n_per_stratum_and_arm": CONFIRMATION_N,
                "selection": "none: a new complete-outcome randomized trial in each stratum",
                "cost": "operator-reserved, unavailable during exploration, outside the 12000-unit exploration budget",
                "release": "only after immutable claim commitment; summaries are observations, not ground truth",
            },
            "metrics": (
                "Population effect class, continuous estimation error, interval coverage/width, "
                "subgroup error, false nonzero-effect claims, abstention, and fresh confirmation are separate. "
                "A supported claim needs its point estimates inside its intervals and its population "
                "point equal to the weighted subgroup points within absolute tolerance 1e-6. "
                "All pilot worlds are identifiable with audits; correct refusal for intrinsically "
                "nonidentifiable worlds is unmeasured, with denominator zero."
            ),
        }

    def action_cost(self, tool, arguments):
        if tool != "trial" or not isinstance(arguments, dict):
            raise ValueError("expected trial and an argument mapping")
        if set(arguments) != {"stratum", "treatment", "n", "audit_n"}:
            raise ValueError("trial requires exactly stratum, treatment, n, audit_n")
        for key, value in arguments.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(key + " must be an integer")
        if arguments["stratum"] not in (0, 1, 2, 3):
            raise ValueError("stratum outside [0,3]")
        if arguments["treatment"] not in (0, 1):
            raise ValueError("treatment must be 0 or 1")
        if not 32 <= arguments["n"] <= 512:
            raise ValueError("n outside [32,512]")
        if not 0 <= arguments["audit_n"] <= arguments["n"]:
            raise ValueError("audit_n outside [0,n]")
        return arguments["n"] + 4 * arguments["audit_n"]

    def _cohort(self, rng, stratum, treatment, n):
        c = rng.normal(size=n)
        # E[C] = E[C^2 - 1] = 0: stratum average treatment effect is exact.
        baseline = (self._mu[stratum] + self._beta[stratum] * c
                    + self._curvature[stratum] * (c * c - 1.0))
        residual_y = baseline + self._heterogeneity[stratum] * c * treatment + rng.normal(0, 0.4, n)
        y = residual_y + self._effects[stratum] * treatment
        # Algebraically this is a logit in Y, C, T with an unrestricted direct
        # T coefficient. Computing with residual_y pins paired return indicators.
        logit = (self._selection_intercept[stratum]
                 + self._selection_y[stratum] * (residual_y - self._mu[stratum])
                 + self._selection_c[stratum] * c + self._selection_t[stratum] * treatment)
        returned = rng.random(n) < 1.0 / (1.0 + np.exp(-np.clip(logit, -40, 40)))
        return y, returned

    def experiment(self, tool, arguments):
        self.action_cost(tool, arguments)
        self._calls += 1
        rng = np.random.default_rng([self._family_seed, 811, self._calls])
        k, treatment, n = arguments["stratum"], arguments["treatment"], arguments["n"]
        outcomes, returned = self._cohort(rng, k, treatment, n)
        missing = np.flatnonzero(~returned)
        audit_count = min(arguments["audit_n"], len(missing))
        selected = rng.choice(missing, size=audit_count, replace=False)
        return {
            "stratum": k,
            "treatment": treatment,
            "n_enrolled": n,
            "n_returned": int(returned.sum()),
            "n_missing": len(missing),
            "audit_requested": arguments["audit_n"],
            "n_audited": audit_count,
            "audit_inclusion_probability": (audit_count / len(missing)) if len(missing) else None,
            "survivor_outcomes": outcomes[returned].tolist(),
            "audited_outcomes": outcomes[selected].tolist(),
        }

    def validate_claim(self, claim):
        if not isinstance(claim, dict) or not isinstance(claim.get("abstain"), bool):
            raise ValueError("claim requires a boolean abstain")
        confidence = _number(claim.get("confidence"), "confidence")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence outside [0,1]")
        if claim["abstain"]:
            if set(claim) != {"abstain", "confidence"}:
                raise ValueError("abstention accepts only abstain and confidence")
            return
        required = {"abstain", "confidence", "effect_class", "population_effect", "population_interval",
                    "stratum_effects", "stratum_intervals"}
        if set(claim) != required:
            raise ValueError("nonabstaining claim has missing or unknown fields")
        if confidence != 0.95:
            raise ValueError("discovery intervals must have nominal confidence 0.95")
        if claim["effect_class"] not in ("positive", "negative", "negligible"):
            raise ValueError("unknown effect_class")
        _number(claim["population_effect"], "population_effect")
        _interval(claim["population_interval"], "population_interval")
        if not isinstance(claim["stratum_effects"], list) or len(claim["stratum_effects"]) != 4:
            raise ValueError("stratum_effects must contain four numbers")
        if not isinstance(claim["stratum_intervals"], list) or len(claim["stratum_intervals"]) != 4:
            raise ValueError("stratum_intervals must contain four intervals")
        for effect in claim["stratum_effects"]:
            _number(effect, "stratum_effect")
        for interval in claim["stratum_intervals"]:
            _interval(interval, "stratum_interval")

    def confirm(self, claim):
        self.validate_claim(claim)
        cells = []
        effects, variances = [], []
        for k in range(4):
            means, mean_variances = [], []
            for treatment in (0, 1):
                rng = np.random.default_rng([self._family_seed, 991, k, treatment])
                outcomes, _ = self._cohort(rng, k, treatment, CONFIRMATION_N)
                mean = float(np.mean(outcomes))
                variance = float(np.var(outcomes, ddof=1))
                cells.append({"stratum": k, "treatment": treatment, "n": CONFIRMATION_N,
                              "mean_outcome": mean, "sample_variance": variance})
                means.append(mean)
                mean_variances.append(variance / CONFIRMATION_N)
            effects.append(means[1] - means[0])
            variances.append(sum(mean_variances))
        return {
            "protocol": "complete-outcome-stratified-rct-v1",
            "cells": cells,
            "stratum_effects": effects,
            "stratum_standard_errors": [math.sqrt(v) for v in variances],
            "population_effect": float(np.dot(WEIGHTS, effects)),
            "population_standard_error": math.sqrt(float(np.dot(np.square(WEIGHTS), variances))),
        }

    def evaluate(self, claim, confirmation):
        """Trusted-only metrics; never send the result back to the proposing agent."""
        self.validate_claim(claim)
        # The runner supplies its own confirmation artifact, not candidate text.
        # Reject a substituted/corrupted artifact rather than grading fake data.
        if confirmation != self.confirm(claim):
            raise ValueError("confirmation does not match the reserved observation stream")
        abstained = claim["abstain"]
        truth_class = _effect_class(self._population_effect)
        is_null = truth_class == "negligible"
        claimed_nonzero = not abstained and claim["effect_class"] != "negligible"
        false_claim = claimed_nonzero and claim["effect_class"] != truth_class
        metrics = {
            "task_id": self.task_id,
            "valid": True,
            "mechanism_recovery": 0.0,
            "mechanism_recovery_numerator": 0,
            "mechanism_recovery_denominator": 1,
            "effect_estimation_score": 0.0,
            "population_absolute_error": None,
            "population_estimation_denominator": int(not abstained),
            "population_interval_coverage": None,
            "population_interval_coverage_numerator": 0,
            "population_interval_width": None,
            "population_interval_denominator": int(not abstained),
            "stratum_effect_rmse": None,
            "stratum_estimation_denominator": 4 * int(not abstained),
            "stratum_interval_coverage_numerator": 0,
            "stratum_interval_coverage_denominator": 4 * int(not abstained),
            "false_discovery_rate": float(false_claim) if claimed_nonzero else None,
            "false_discovery_numerator": int(false_claim),
            "false_discovery_denominator": int(claimed_nonzero),
            "null_false_positive_rate": float(claimed_nonzero) if is_null else None,
            "null_false_positive_numerator": int(is_null and claimed_nonzero),
            "null_false_positive_denominator": int(is_null),
            "correct_refusal_rate": None,
            "correct_refusal_numerator": 0,
            "correct_refusal_denominator": 0,
            "abstention_rate": float(abstained),
            "abstention_numerator": int(abstained),
            "abstention_denominator": 1,
            "discovery_coverage": float(not abstained),
            "discovery_coverage_numerator": int(not abstained),
            "discovery_coverage_denominator": 1,
            "confirmation_success": None,
            "confirmation_success_numerator": 0,
            "confirmation_success_denominator": int(not abstained),
            "confirmation_prediction_absolute_error": None,
            "population_stratum_consistency_error": None,
            "interval_supports_claim": None,
            "claim_self_consistent": None,
        }
        if abstained:
            return metrics
        error = abs(claim["population_effect"] - self._population_effect)
        supports = _interval_supports(claim["effect_class"], claim["population_interval"])
        lower, upper = claim["population_interval"]
        consistency_error = min(sys.float_info.max, abs(claim["population_effect"] - float(np.dot(WEIGHTS, claim["stratum_effects"]))))
        coherent = (consistency_error <= 1e-6 and lower <= claim["population_effect"] <= upper
                    and all(lo <= effect <= hi for effect, (lo, hi)
                            in zip(claim["stratum_effects"], claim["stratum_intervals"])))
        correct = claim["effect_class"] == truth_class and supports and coherent
        measured = confirmation["population_effect"]
        se = confirmation["population_standard_error"]
        confirmation_interval = (measured - 1.96 * se, measured + 1.96 * se)
        confirmed = (supports and coherent and _interval_supports(claim["effect_class"], confirmation_interval)
                     and lower <= measured <= upper)
        metrics.update({
            "mechanism_recovery": float(correct),
            "mechanism_recovery_numerator": int(correct),
            "effect_estimation_score": max(0.0, 1.0 - error / 0.5),
            "population_absolute_error": error,
            "population_interval_coverage": float(lower <= self._population_effect <= upper),
            "population_interval_coverage_numerator": int(lower <= self._population_effect <= upper),
            "population_interval_width": min(sys.float_info.max, upper - lower),
            "stratum_effect_rmse": math.hypot(*[(float(estimate) - float(truth)) / 2.0
                                               for estimate, truth in zip(claim["stratum_effects"], self._effects)]),
            "stratum_interval_coverage_numerator": sum(int(lo <= truth <= hi) for (lo, hi), truth
                                                        in zip(claim["stratum_intervals"], self._effects)),
            "confirmation_success": float(confirmed),
            "confirmation_success_numerator": int(confirmed),
            "confirmation_prediction_absolute_error": abs(claim["population_effect"] - measured),
            "population_stratum_consistency_error": consistency_error,
            "interval_supports_claim": supports,
            "claim_self_consistent": coherent,
        })
        return metrics


def create_environment(seed: int):
    return SurvivorshipAuditEnvironment(seed)
