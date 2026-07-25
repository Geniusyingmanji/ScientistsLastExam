"""Prospective evidence-synthesis oracle with lineage and confirmation, version 1.

The candidate receives registry and publication records from a procedural family of
randomized-study landscapes.  It must screen eligible trials, count each participant
lineage once, identify outcome-selective reports, fit a heterogeneous meta-regression,
commit a forecast and next-study design, and update after one fresh prospective study.
Screening, mechanism, uncertainty, design and confirmation remain separate metrics.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import math

import numpy as np


PROSPECTIVE_META_ANALYSIS_V1 = True

DEVELOPMENT_SPECS = (
    (8301, "linear_positive"),
    (8302, "linear_positive"),
    (8303, "linear_mixed"),
    (8304, "linear_mixed"),
    (8305, "linear_null"),
    (8306, "nonlinear"),
)
HELDOUT_SPECS = (
    (9301, "linear_positive"),
    (9302, "linear_mixed"),
    (9303, "linear_null"),
    (9304, "nonlinear"),
)

PRIMARY_ENDPOINT = "response_12w"
TARGET_POPULATION = "target_condition"
TARGET_COMPARATOR = "standard_care"
MIN_SAMPLE_SIZE = 80
SAMPLE_STEP = 20
STUDY_BUDGET = 360.0
EFFECT_BOUNDS = (-1.5, 1.5)
TAU_BOUNDS = (0.0, 0.5)
Z_90 = 1.6448536269514722

SITES = (
    {"site_id": "site_a", "moderator_value": -1.00,
     "cost_per_participant": 1.30, "maximum_sample_size": 240},
    {"site_id": "site_b", "moderator_value": -0.55,
     "cost_per_participant": 1.00, "maximum_sample_size": 320},
    {"site_id": "site_c", "moderator_value": 0.00,
     "cost_per_participant": 0.82, "maximum_sample_size": 400},
    {"site_id": "site_d", "moderator_value": 0.55,
     "cost_per_participant": 1.00, "maximum_sample_size": 320},
    {"site_id": "site_e", "moderator_value": 1.00,
     "cost_per_participant": 1.30, "maximum_sample_size": 240},
)

SCREENING_KEYS = {
    "included_registration_ids", "primary_record_ids", "duplicate_groups",
    "selective_report_ids",
}
MODEL_KEYS = {
    "intercept", "moderator_slope", "tau", "confidence", "abstain",
    "claim_beneficial",
}
FORECAST_KEYS = {"predicted_effect", "prediction_interval"}
COMMIT_KEYS = {
    "screening", "preconfirmation", "site_id", "sample_size", "forecast",
}
SUBMISSION_KEYS = {"confirmation_commit", "postconfirmation"}


def _token(prefix, *values):
    payload = "|".join(str(value) for value in values).encode("utf-8")
    return prefix + hashlib.sha256(payload).hexdigest()[:12]


def _truth_parameters(seed, kind):
    rng = np.random.default_rng(int(seed))
    if kind == "linear_positive":
        intercept = rng.uniform(0.24, 0.38)
        slope = rng.uniform(-0.13, 0.13)
        curvature = 0.0
    elif kind == "linear_mixed":
        intercept = rng.uniform(0.10, 0.22)
        slope = rng.choice((-1.0, 1.0)) * rng.uniform(0.24, 0.40)
        curvature = 0.0
    elif kind == "linear_null":
        intercept = rng.uniform(-0.035, 0.045)
        slope = rng.uniform(-0.055, 0.055)
        curvature = 0.0
    elif kind == "nonlinear":
        intercept = rng.uniform(0.08, 0.18)
        slope = rng.uniform(-0.10, 0.10)
        curvature = rng.choice((-1.0, 1.0)) * rng.uniform(0.42, 0.58)
    else:
        raise ValueError("unknown evidence world")
    return {
        "intercept": float(intercept),
        "moderator_slope": float(slope),
        "curvature": float(curvature),
        "tau": float(rng.uniform(0.075, 0.155)),
    }


def _mean_effect(truth, moderator):
    moderator = float(moderator)
    return float(
        truth["intercept"]
        + truth["moderator_slope"] * moderator
        + truth["curvature"] * (moderator * moderator - 1.0)
    )


def _standard_error(sample_size):
    return float(math.sqrt(4.0 / float(sample_size)))


def _eligible_record(record):
    return bool(
        record["randomized"]
        and record["population"] == TARGET_POPULATION
        and record["comparator"] == TARGET_COMPARATOR
        and record["preregistered_primary"] == PRIMARY_ENDPOINT
    )


def _make_world(spec):
    seed, kind = int(spec[0]), str(spec[1])
    truth = _truth_parameters(seed, kind)
    rng = np.random.default_rng(seed)
    moderators = np.linspace(-1.0, 1.0, 14)
    rng.shuffle(moderators)
    records = []
    eligible_trials = []
    all_trials = []

    for index in range(17):
        eligible = index < 14
        moderator = float(moderators[index] if eligible else rng.uniform(-1.0, 1.0))
        sample_size = int(rng.integers(4, 13) * 20)
        standard_error = _standard_error(sample_size)
        registration_id = _token("REG-", seed, index)
        registry_id = _token("REC-", seed, index, "registry")
        if eligible:
            population = TARGET_POPULATION
            comparator = TARGET_COMPARATOR
            randomized = True
            primary = PRIMARY_ENDPOINT
            true_mean = _mean_effect(truth, moderator)
        else:
            flaw = index % 3
            population = "adjacent_condition" if flaw == 0 else TARGET_POPULATION
            comparator = "active_comparator" if flaw == 1 else TARGET_COMPARATOR
            randomized = False if flaw == 2 else True
            primary = "response_6w" if flaw == 2 else PRIMARY_ENDPOINT
            true_mean = _mean_effect(truth, moderator) + rng.choice((-0.42, 0.42))
        study_deviation = rng.normal(0.0, truth["tau"])
        observed_primary = float(true_mean + study_deviation + rng.normal(0.0, standard_error))
        common = {
            "registration_id": registration_id,
            "population": population,
            "comparator": comparator,
            "randomized": bool(randomized),
            "preregistered_primary": primary,
            "moderator_value": moderator,
            "sample_size": sample_size,
        }
        registry = dict(common)
        registry.update({
            "record_id": registry_id,
            "record_type": "registry_result",
            "highlighted_outcome": primary,
            "outcomes": [{
                "name": primary,
                "effect": observed_primary,
                "standard_error": standard_error,
            }],
        })
        records.append(registry)
        trial = {
            "registration_id": registration_id,
            "registry_record_id": registry_id,
            "moderator_value": moderator,
            "sample_size": sample_size,
            "standard_error": standard_error,
            "observed_primary": observed_primary,
            "eligible": eligible,
        }
        all_trials.append(trial)
        if eligible:
            eligible_trials.append(trial)

        # Most trials generate a publication, and three lineages generate a second
        # article over the same participants.  Highlighting the largest z-score
        # creates an observable outcome-reporting trap without hiding the registry.
        publication_count = 0
        if eligible and index not in (2, 7, 12):
            publication_count = 2 if index in (0, 4, 8, 11) else 1
        elif not eligible and index != 15:
            publication_count = 1
        for article in range(publication_count):
            secondary_early = float(
                observed_primary + 0.10 + rng.normal(0.0, 1.05 * standard_error)
            )
            secondary_biomarker = float(
                observed_primary + 0.18 + rng.normal(0.0, 1.20 * standard_error)
            )
            outcomes = [
                {"name": primary, "effect": observed_primary,
                 "standard_error": standard_error},
                {"name": "early_response", "effect": secondary_early,
                 "standard_error": 1.05 * standard_error},
                {"name": "biomarker_response", "effect": secondary_biomarker,
                 "standard_error": 1.20 * standard_error},
            ]
            highlighted = max(
                outcomes, key=lambda row: row["effect"] / row["standard_error"]
            )["name"]
            publication = dict(common)
            publication.update({
                "record_id": _token("REC-", seed, index, "publication", article),
                "record_type": "publication",
                "article_role": "primary_article" if article == 0 else "followup_article",
                "highlighted_outcome": highlighted,
                "outcomes": outcomes,
            })
            records.append(publication)

    order = rng.permutation(len(records))
    records = [records[int(index)] for index in order]
    return {
        "seed": seed,
        "kind": kind,
        "truth": truth,
        "records": records,
        "eligible_trials": eligible_trials,
        "all_trials": all_trials,
        "decision_moderator": float(rng.choice((-0.75, -0.25, 0.25, 0.75))),
        "confirmation_noise_seed": seed * 7919 + 17,
    }


def _public_problem(world):
    return {
        "records": copy.deepcopy(world["records"]),
        "eligibility_criteria": {
            "population": TARGET_POPULATION,
            "comparator": TARGET_COMPARATOR,
            "randomized": True,
            "primary_endpoint": PRIMARY_ENDPOINT,
        },
        "effect_model": "effect = intercept + moderator_slope * moderator_value",
        "effect_bounds": list(EFFECT_BOUNDS),
        "tau_bounds": list(TAU_BOUNDS),
        "benefit_threshold": 0.10,
        "decision_moderator": world["decision_moderator"],
        "candidate_sites": copy.deepcopy(list(SITES)),
        "minimum_sample_size": MIN_SAMPLE_SIZE,
        "sample_size_step": SAMPLE_STEP,
        "study_budget": STUDY_BUDGET,
        "prediction_interval_level": 0.90,
    }


def _expected_screening(world):
    records = world["records"]
    eligible_registrations = {
        record["registration_id"] for record in records
        if record["record_type"] == "registry_result" and _eligible_record(record)
    }
    primary_records = {
        record["record_id"] for record in records
        if record["record_type"] == "registry_result" and _eligible_record(record)
    }
    by_registration = {}
    for record in records:
        by_registration.setdefault(record["registration_id"], []).append(record["record_id"])
    duplicate_groups = [
        tuple(sorted(group)) for group in by_registration.values() if len(group) > 1
    ]
    selective = {
        record["record_id"] for record in records
        if record["record_type"] == "publication"
        and record["highlighted_outcome"] != record["preregistered_primary"]
    }
    return {
        "included_registration_ids": eligible_registrations,
        "primary_record_ids": primary_records,
        "duplicate_groups": duplicate_groups,
        "selective_report_ids": selective,
    }


def _registry_rows(records):
    return [
        record for record in records
        if record["record_type"] == "registry_result" and _eligible_record(record)
    ]


def _fit_meta_regression(records, quadratic=False):
    rows = _registry_rows(records)
    if len(rows) < (5 if quadratic else 4):
        raise ValueError("too few independent eligible registry results")
    x = np.asarray([row["moderator_value"] for row in rows], dtype=float)
    y = np.asarray([row["outcomes"][0]["effect"] for row in rows], dtype=float)
    se = np.asarray([row["outcomes"][0]["standard_error"] for row in rows], dtype=float)
    columns = [np.ones_like(x), x]
    if quadratic:
        columns.append(x * x - 1.0)
    design = np.column_stack(columns)
    best = None
    for tau in np.linspace(0.0, TAU_BOUNDS[1], 251):
        variance = se * se + tau * tau
        weight = 1.0 / variance
        information = design.T @ (weight[:, None] * design)
        sign, logdet = np.linalg.slogdet(information)
        if sign <= 0:
            continue
        beta = np.linalg.solve(information, design.T @ (weight * y))
        residual = y - design @ beta
        objective = float(
            np.sum(np.log(variance)) + logdet + np.sum(weight * residual * residual)
        )
        if best is None or objective < best[0]:
            best = (objective, float(tau), beta, np.linalg.inv(information), residual, weight)
    if best is None:
        raise ValueError("meta-regression fit failed")
    objective, tau, beta, covariance, residual, weight = best
    return {
        "objective": objective,
        "tau": tau,
        "beta": beta,
        "covariance": covariance,
        "weighted_residual": float(np.sum(weight * residual * residual)),
        "n": len(rows),
    }


def _reference_screening(problem):
    records = list(problem["records"])
    eligible = [
        record for record in records
        if record["record_type"] == "registry_result" and _eligible_record(record)
    ]
    by_registration = {}
    for record in records:
        by_registration.setdefault(record["registration_id"], []).append(record["record_id"])
    return {
        "included_registration_ids": sorted(
            record["registration_id"] for record in eligible
        ),
        "primary_record_ids": sorted(record["record_id"] for record in eligible),
        "duplicate_groups": sorted(
            [sorted(group) for group in by_registration.values() if len(group) > 1]
        ),
        "selective_report_ids": sorted(
            record["record_id"] for record in records
            if record["record_type"] == "publication"
            and record["highlighted_outcome"] != record["preregistered_primary"]
        ),
    }


def _reference_pre_model(problem):
    linear = _fit_meta_regression(problem["records"], quadratic=False)
    quadratic = _fit_meta_regression(problem["records"], quadratic=True)
    quadratic_coefficient = float(quadratic["beta"][2])
    quadratic_se = math.sqrt(max(float(quadratic["covariance"][2, 2]), 1.0e-15))
    quadratic_z = abs(quadratic_coefficient) / quadratic_se
    # The quadratic coefficient is a registered lack-of-fit diagnostic, not a
    # candidate model extension.  The fixed threshold separates all current
    # procedural supported/nonlinear worlds without consulting their kind labels.
    abstain = bool(abs(quadratic_coefficient) > 0.30 and quadratic_z > 2.0)
    intercept, slope = (float(value) for value in linear["beta"][:2])
    target = intercept + slope * float(problem["decision_moderator"])
    target_vector = np.asarray((1.0, float(problem["decision_moderator"])))
    target_se = math.sqrt(max(float(
        target_vector @ linear["covariance"] @ target_vector
    ), 1.0e-15))
    if abstain:
        confidence = float(np.clip(0.55 + 0.07 * quadratic_z, 0.0, 0.98))
        claim_beneficial = False
    else:
        standardized = (target - problem["benefit_threshold"]) / target_se
        probability_beneficial = 0.5 * (
            1.0 + math.erf(standardized / math.sqrt(2.0))
        )
        claim_beneficial = bool(
            target - Z_90 * target_se > problem["benefit_threshold"]
        )
        # Confidence is attached to the declared decision, not generic confidence
        # in the fitted model.  A conservative non-claim near the threshold must
        # therefore have low confidence rather than inherit confidence from n.
        confidence = float(
            probability_beneficial
            if claim_beneficial else 1.0 - probability_beneficial
        )
    return {
        "intercept": intercept,
        "moderator_slope": slope,
        "tau": float(linear["tau"]),
        "confidence": confidence,
        "abstain": abstain,
        "claim_beneficial": claim_beneficial,
    }


def _candidate_site(problem, site_id):
    matches = [site for site in problem["candidate_sites"] if site["site_id"] == site_id]
    if len(matches) != 1:
        raise ValueError("unknown prospective site")
    return matches[0]


def _feasible_designs(problem):
    for site in problem["candidate_sites"]:
        maximum = min(
            int(site["maximum_sample_size"]),
            int(problem["study_budget"] // float(site["cost_per_participant"])),
        )
        maximum -= maximum % int(problem["sample_size_step"])
        for sample_size in range(
            int(problem["minimum_sample_size"]), maximum + 1,
            int(problem["sample_size_step"]),
        ):
            yield site, sample_size


def _information_utility(world, site, sample_size):
    tau = world["truth"]["tau"]
    design = np.asarray([
        [1.0, trial["moderator_value"]] for trial in world["eligible_trials"]
    ])
    weights = np.asarray([
        1.0 / (trial["standard_error"] ** 2 + tau ** 2)
        for trial in world["eligible_trials"]
    ])
    information = design.T @ (weights[:, None] * design) + np.eye(2) * 1.0e-9
    new_x = np.asarray((1.0, float(site["moderator_value"])))
    new_weight = 1.0 / (_standard_error(sample_size) ** 2 + tau ** 2)
    before = np.linalg.slogdet(information)[1]
    after = np.linalg.slogdet(information + new_weight * np.outer(new_x, new_x))[1]
    cost_fraction = (
        float(sample_size) * float(site["cost_per_participant"]) / STUDY_BUDGET
    )
    return float(after - before - 0.18 * cost_fraction)


def _design_score(world, problem, site_id, sample_size):
    utilities = []
    selected = None
    for site, size in _feasible_designs(problem):
        utility = _information_utility(world, site, size)
        utilities.append(utility)
        if site["site_id"] == site_id and size == sample_size:
            selected = utility
    if selected is None:
        raise ValueError("prospective study design is infeasible")
    low, high = min(utilities), max(utilities)
    if high <= low + 1.0e-15:
        return 1.0
    return float(np.clip((selected - low) / (high - low), 0.0, 1.0))


def _best_design(world, problem):
    choices = []
    for site, sample_size in _feasible_designs(problem):
        choices.append((
            _information_utility(world, site, sample_size),
            site["site_id"], sample_size,
        ))
    _, site_id, sample_size = max(choices, key=lambda row: (row[0], row[1], row[2]))
    return site_id, int(sample_size)


class _ProspectiveLaboratory:
    def __init__(self, world, problem):
        self.world = world
        self.problem = problem
        self.called = False
        self.failure = None
        self.commit = None
        self.result = None

    def confirm(self, commit):
        if self.called:
            self.failure = "only one prospective confirmation study is allowed"
            raise ValueError(self.failure)
        self.called = True
        try:
            normalized = _validate_commit(commit, self.problem)
            site = _candidate_site(self.problem, normalized["site_id"])
            sample_size = normalized["sample_size"]
            _design_score(self.world, self.problem, site["site_id"], sample_size)
        except Exception as exc:
            self.failure = str(exc)
            raise
        self.commit = normalized
        moderator = float(site["moderator_value"])
        standard_error = _standard_error(sample_size)
        mean = _mean_effect(self.world["truth"], moderator)
        payload = "%s|%s|%s" % (
            self.world["confirmation_noise_seed"], site["site_id"], sample_size
        )
        seed = int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        effect = float(
            mean
            + rng.normal(0.0, self.world["truth"]["tau"])
            + rng.normal(0.0, standard_error)
        )
        self.result = {
            "registration_id": _token(
                "FRESH-", self.world["seed"], site["site_id"], sample_size
            ),
            "site_id": site["site_id"],
            "moderator_value": moderator,
            "sample_size": sample_size,
            "primary_endpoint": PRIMARY_ENDPOINT,
            "effect": effect,
            "standard_error": standard_error,
        }
        return copy.deepcopy(self.result)


def _finite_number(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if low is not None and value < low:
        raise ValueError(name + " is below its public bound")
    if high is not None and value > high:
        raise ValueError(name + " is above its public bound")
    return value


def _validate_string_list(value, allowed, name):
    if not isinstance(value, (list, tuple)):
        raise ValueError(name + " must be a list")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(name + " must contain strings")
    if len(set(value)) != len(value):
        raise ValueError(name + " contains duplicates")
    if not set(value).issubset(allowed):
        raise ValueError(name + " contains an unknown identifier")
    return sorted(value)


def _validate_screening(value, problem):
    if not isinstance(value, dict) or set(value) != SCREENING_KEYS:
        raise ValueError("screening artifact has the wrong fields")
    records = problem["records"]
    record_ids = {record["record_id"] for record in records}
    registration_ids = {record["registration_id"] for record in records}
    groups = value["duplicate_groups"]
    if not isinstance(groups, (list, tuple)):
        raise ValueError("duplicate_groups must be a list")
    normalized_groups = []
    used = set()
    for group in groups:
        normalized = _validate_string_list(group, record_ids, "duplicate group")
        if len(normalized) < 2:
            raise ValueError("duplicate groups must contain at least two records")
        if used.intersection(normalized):
            raise ValueError("duplicate groups may not overlap")
        used.update(normalized)
        normalized_groups.append(normalized)
    return {
        "included_registration_ids": _validate_string_list(
            value["included_registration_ids"], registration_ids,
            "included_registration_ids",
        ),
        "primary_record_ids": _validate_string_list(
            value["primary_record_ids"], record_ids, "primary_record_ids"
        ),
        "duplicate_groups": sorted(normalized_groups),
        "selective_report_ids": _validate_string_list(
            value["selective_report_ids"], record_ids, "selective_report_ids"
        ),
    }


def _validate_model(value, name):
    if not isinstance(value, dict) or set(value) != MODEL_KEYS:
        raise ValueError(name + " has the wrong fields")
    if not isinstance(value["abstain"], (bool, np.bool_)):
        raise ValueError(name + ".abstain must be boolean")
    if not isinstance(value["claim_beneficial"], (bool, np.bool_)):
        raise ValueError(name + ".claim_beneficial must be boolean")
    abstain = bool(value["abstain"])
    claim = bool(value["claim_beneficial"])
    if abstain and claim:
        raise ValueError("an abstaining model cannot claim benefit")
    return {
        "intercept": _finite_number(
            value["intercept"], name + ".intercept", *EFFECT_BOUNDS
        ),
        "moderator_slope": _finite_number(
            value["moderator_slope"], name + ".moderator_slope", *EFFECT_BOUNDS
        ),
        "tau": _finite_number(value["tau"], name + ".tau", *TAU_BOUNDS),
        "confidence": _finite_number(
            value["confidence"], name + ".confidence", 0.0, 1.0
        ),
        "abstain": abstain,
        "claim_beneficial": claim,
    }


def _validate_forecast(value):
    if not isinstance(value, dict) or set(value) != FORECAST_KEYS:
        raise ValueError("forecast has the wrong fields")
    interval = value["prediction_interval"]
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError("prediction_interval must have two endpoints")
    low = _finite_number(interval[0], "prediction interval lower", *EFFECT_BOUNDS)
    high = _finite_number(interval[1], "prediction interval upper", *EFFECT_BOUNDS)
    if low >= high:
        raise ValueError("prediction interval must be ordered")
    predicted = _finite_number(value["predicted_effect"], "predicted_effect", *EFFECT_BOUNDS)
    return {"predicted_effect": predicted, "prediction_interval": [low, high]}


def _validate_commit(value, problem):
    if not isinstance(value, dict) or set(value) != COMMIT_KEYS:
        raise ValueError("confirmation commit has the wrong fields")
    if not isinstance(value["site_id"], str):
        raise ValueError("site_id must be a string")
    site = _candidate_site(problem, value["site_id"])
    sample_size = value["sample_size"]
    if isinstance(sample_size, bool) or not isinstance(sample_size, (int, np.integer)):
        raise ValueError("sample_size must be an integer")
    sample_size = int(sample_size)
    if sample_size < int(problem["minimum_sample_size"]):
        raise ValueError("sample_size is below the minimum")
    if sample_size % int(problem["sample_size_step"]):
        raise ValueError("sample_size is off the public grid")
    if sample_size > int(site["maximum_sample_size"]):
        raise ValueError("sample_size exceeds the site maximum")
    if sample_size * float(site["cost_per_participant"]) > float(problem["study_budget"]) + 1e-12:
        raise ValueError("prospective study exceeds budget")
    screening = _validate_screening(value["screening"], problem)
    pre = _validate_model(value["preconfirmation"], "preconfirmation")
    forecast = _validate_forecast(value["forecast"])
    if not pre["abstain"]:
        expected = pre["intercept"] + pre["moderator_slope"] * float(site["moderator_value"])
        if abs(forecast["predicted_effect"] - expected) > 1.0e-6:
            raise ValueError("forecast point is inconsistent with the committed model")
    return {
        "screening": screening,
        "preconfirmation": pre,
        "site_id": site["site_id"],
        "sample_size": sample_size,
        "forecast": forecast,
    }


def _validate_submission(value, problem, laboratory):
    if not isinstance(value, dict) or set(value) != SUBMISSION_KEYS:
        raise ValueError("submission has the wrong fields")
    commit = value["confirmation_commit"]
    if commit is None:
        if laboratory.called:
            raise ValueError("confirmation was run without returning its signed commit")
        normalized_commit = None
    else:
        if not laboratory.called or laboratory.commit is None:
            raise ValueError("returned commit was never submitted to confirmation")
        normalized_commit = _validate_commit(commit, problem)
        if normalized_commit != laboratory.commit:
            raise ValueError("returned commit differs from the pre-confirmation commit")
    post = _validate_model(value["postconfirmation"], "postconfirmation")
    if normalized_commit is None and not post["abstain"]:
        raise ValueError(
            "a non-abstaining scientific claim requires a pre-result commit and confirmation"
        )
    return normalized_commit, post


def _f1(predicted, expected):
    predicted, expected = set(predicted), set(expected)
    if not predicted and not expected:
        return 1.0
    if not predicted or not expected:
        return 0.0
    tp = len(predicted & expected)
    return float(2.0 * tp / (len(predicted) + len(expected)))


def _pairs(groups):
    return {
        tuple(sorted(pair))
        for group in groups
        for pair in itertools.combinations(group, 2)
    }


def _screening_metrics(screening, expected):
    if screening is None:
        return {
            "lineage_f1": 0.0, "primary_record_f1": 0.0,
            "duplicate_pair_f1": 0.0, "selective_report_f1": 0.0,
            "evidence_integrity_score": 0.0,
        }
    metrics = {
        "lineage_f1": _f1(
            screening["included_registration_ids"],
            expected["included_registration_ids"],
        ),
        "primary_record_f1": _f1(
            screening["primary_record_ids"], expected["primary_record_ids"]
        ),
        "duplicate_pair_f1": _f1(
            _pairs(screening["duplicate_groups"]), _pairs(expected["duplicate_groups"])
        ),
        "selective_report_f1": _f1(
            screening["selective_report_ids"], expected["selective_report_ids"]
        ),
    }
    metrics["evidence_integrity_score"] = float(np.mean(list(metrics.values())))
    return metrics


def _gaussian_score(error, tolerance):
    return float(math.exp(-0.5 * (float(error) / float(tolerance)) ** 2))


def _model_recovery(model, world):
    if model["abstain"]:
        return 0.0
    truth = world["truth"]
    return float(np.mean((
        _gaussian_score(model["intercept"] - truth["intercept"], 0.14),
        _gaussian_score(model["moderator_slope"] - truth["moderator_slope"], 0.18),
        _gaussian_score(model["tau"] - truth["tau"], 0.085),
    )))


def _prediction_score(model, world):
    if model["abstain"]:
        return 0.0
    moderators = np.asarray((-0.88, -0.35, 0.35, 0.88))
    predicted = model["intercept"] + model["moderator_slope"] * moderators
    truth = np.asarray([_mean_effect(world["truth"], value) for value in moderators])
    rmse = float(np.sqrt(np.mean((predicted - truth) ** 2)))
    return _gaussian_score(rmse, 0.18)


def _decision_score(model, world, problem):
    if model["abstain"]:
        return 0.0
    truth_benefit = bool(
        _mean_effect(world["truth"], problem["decision_moderator"])
        > problem["benefit_threshold"]
    )
    correct = float(model["claim_beneficial"] == truth_benefit)
    calibration = 1.0 - (model["confidence"] - correct) ** 2
    return float(0.70 * correct + 0.30 * calibration)


def _refusal_score(model):
    correct = float(model["abstain"] and not model["claim_beneficial"])
    calibration = 1.0 - (model["confidence"] - correct) ** 2
    return float(0.70 * correct + 0.30 * calibration)


def _forecast_metrics(commit, laboratory, world, problem):
    if commit is None or laboratory.result is None:
        return {
            "design_information_score": 0.0,
            "forecast_distribution_score": 0.0,
            "confirmation_point_score": 0.0,
            "confirmation_interval_covered": 0.0,
            "confirmation_call_count": 0,
        }
    site = _candidate_site(problem, commit["site_id"])
    sample_size = commit["sample_size"]
    mean = _mean_effect(world["truth"], site["moderator_value"])
    predictive_sd = math.sqrt(
        world["truth"]["tau"] ** 2 + _standard_error(sample_size) ** 2
    )
    oracle_interval = (mean - Z_90 * predictive_sd, mean + Z_90 * predictive_sd)
    forecast = commit["forecast"]
    point = _gaussian_score(forecast["predicted_effect"] - mean, 0.16)
    endpoint_error = float(np.mean(np.abs(
        np.asarray(forecast["prediction_interval"]) - np.asarray(oracle_interval)
    )))
    interval_distribution = _gaussian_score(endpoint_error, 0.22)
    observed = laboratory.result["effect"]
    low, high = forecast["prediction_interval"]
    return {
        "design_information_score": _design_score(
            world, problem, commit["site_id"], sample_size
        ),
        "forecast_distribution_score": float(0.5 * point + 0.5 * interval_distribution),
        "confirmation_point_score": _gaussian_score(
            forecast["predicted_effect"] - observed, predictive_sd
        ),
        "confirmation_interval_covered": float(low <= observed <= high),
        "confirmation_call_count": 1,
    }


def _score_world(world, submission, laboratory):
    problem = laboratory.problem
    expected = _expected_screening(world)
    try:
        commit, post = _validate_submission(submission, problem, laboratory)
        if laboratory.failure:
            raise ValueError(laboratory.failure)
    except Exception as exc:
        return {
            "valid": False,
            "reason": str(exc),
            "raw_quality": 0.0,
            "robust_quality": 0.0,
            "evidence_integrity_score": 0.0,
            "preconfirmation_mechanism_score": 0.0,
            "prediction_score": 0.0,
            "decision_or_refusal_score": 0.0,
            "forecast_distribution_score": 0.0,
            "design_information_score": 0.0,
            "postconfirmation_score": 0.0,
            "confirmation_point_score": 0.0,
            "confirmation_interval_covered": 0.0,
            "confirmation_call_count": int(laboratory.called),
            "false_discovery": 0.0,
            "supported_claim": 0.0,
            "correct_refusal": 0.0,
        }
    screening = None if commit is None else commit["screening"]
    pre = post if commit is None else commit["preconfirmation"]
    screen = _screening_metrics(screening, expected)
    forecast = _forecast_metrics(commit, laboratory, world, problem)
    unsupported = world["kind"] == "nonlinear"
    if unsupported:
        pre_science = _refusal_score(pre)
        post_science = _refusal_score(post)
        raw_quality = (
            0.25 * screen["evidence_integrity_score"]
            + 0.35 * pre_science
            + 0.15 * forecast["design_information_score"]
            + 0.10 * forecast["forecast_distribution_score"]
            + 0.15 * post_science
        )
        mechanism = 0.0
        prediction = 0.0
        false_discovery = float(not pre["abstain"])
        supported_claim = 0.0
        correct_refusal = float(pre["abstain"])
    else:
        mechanism = _model_recovery(pre, world)
        prediction = _prediction_score(pre, world)
        pre_science = _decision_score(pre, world, problem)
        # The post-confirmation artifact contains both a fitted mechanism and a
        # scientific decision.  Scoring only its coefficients would let an agent
        # attach an arbitrary high-confidence claim after seeing the fresh result.
        post_science = float(
            0.70 * _model_recovery(post, world)
            + 0.30 * _decision_score(post, world, problem)
        )
        raw_quality = (
            0.20 * screen["evidence_integrity_score"]
            + 0.20 * mechanism
            + 0.10 * prediction
            + 0.10 * pre_science
            + 0.10 * forecast["forecast_distribution_score"]
            + 0.10 * forecast["design_information_score"]
            + 0.20 * post_science
        )
        truth_benefit = bool(
            _mean_effect(world["truth"], problem["decision_moderator"])
            > problem["benefit_threshold"]
        )
        false_discovery = float(
            (not pre["abstain"]) and pre["claim_beneficial"] and not truth_benefit
        )
        supported_claim = float(not pre["abstain"])
        correct_refusal = 0.0
    robust_components = [
        screen["evidence_integrity_score"],
        pre_science,
        forecast["forecast_distribution_score"],
        forecast["design_information_score"],
        post_science,
    ]
    if not unsupported:
        robust_components.extend((mechanism, prediction))
    robust_quality = float(min(robust_components))
    return {
        "valid": True,
        "reason": "",
        "raw_quality": float(np.clip(raw_quality, 0.0, 1.0)),
        "robust_quality": robust_quality,
        **screen,
        "preconfirmation_mechanism_score": mechanism,
        "prediction_score": prediction,
        "decision_or_refusal_score": pre_science,
        "forecast_distribution_score": forecast["forecast_distribution_score"],
        "design_information_score": forecast["design_information_score"],
        "postconfirmation_score": post_science,
        "confirmation_point_score": forecast["confirmation_point_score"],
        "confirmation_interval_covered": forecast["confirmation_interval_covered"],
        "confirmation_call_count": forecast["confirmation_call_count"],
        "false_discovery": false_discovery,
        "supported_claim": supported_claim,
        "correct_refusal": correct_refusal,
        "world_kind": world["kind"],
    }


def _baseline_raw(specs):
    unsupported = sum(kind == "nonlinear" for _, kind in specs)
    # Always abstaining has no evidence/design/forecast, but receives calibrated
    # pre/post refusal credit in unsupported worlds: 0.35 + 0.15 = 0.50.
    return 0.50 * unsupported / len(specs)


def _aggregate(rows, specs):
    if not rows:
        raise ValueError("empty evidence split")
    raw = float(np.mean([row["raw_quality"] for row in rows]))
    baseline = _baseline_raw(specs)
    normalized = float(np.clip((raw - baseline) / (1.0 - baseline), 0.0, 1.0))
    supported = [row for row in rows if row.get("world_kind") != "nonlinear"]
    unsupported = [row for row in rows if row.get("world_kind") == "nonlinear"]
    mean = lambda key: float(np.mean([row[key] for row in rows]))
    supported_mean = lambda key: float(np.mean([
        row[key] for row in supported
    ])) if supported else 0.0
    return {
        "normalized_score": normalized,
        "raw_quality": raw,
        "robust_quality": float(min(row["robust_quality"] for row in rows)),
        "valid_rate": float(np.mean([row["valid"] for row in rows])),
        "evidence_integrity_score": mean("evidence_integrity_score"),
        "preconfirmation_mechanism_score": supported_mean("preconfirmation_mechanism_score"),
        "prediction_score": supported_mean("prediction_score"),
        "forecast_distribution_score": mean("forecast_distribution_score"),
        "design_information_score": mean("design_information_score"),
        "postconfirmation_score": mean("postconfirmation_score"),
        "confirmation_point_score": mean("confirmation_point_score"),
        "confirmation_interval_coverage": mean("confirmation_interval_covered"),
        "mean_confirmation_calls": mean("confirmation_call_count"),
        "false_discovery_rate": mean("false_discovery"),
        "supported_claim_coverage": float(np.mean([
            row["supported_claim"] for row in supported
        ])) if supported else 0.0,
        "unsupported_refusal_rate": float(np.mean([
            row["correct_refusal"] for row in unsupported
        ])) if unsupported else 1.0,
    }


def _evaluate_split(candidate, specs):
    rows = []
    for index, spec in enumerate(specs):
        if index and hasattr(candidate, "reset_session"):
            candidate.reset_session()
        world = _make_world(spec)
        problem = _public_problem(world)
        laboratory = _ProspectiveLaboratory(world, problem)
        try:
            submission = candidate(copy.deepcopy(problem), laboratory.confirm)
            row = _score_world(world, submission, laboratory)
        except Exception as exc:
            row = {
                "valid": False,
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "raw_quality": 0.0,
                "robust_quality": 0.0,
                "evidence_integrity_score": 0.0,
                "preconfirmation_mechanism_score": 0.0,
                "prediction_score": 0.0,
                "decision_or_refusal_score": 0.0,
                "forecast_distribution_score": 0.0,
                "design_information_score": 0.0,
                "postconfirmation_score": 0.0,
                "confirmation_point_score": 0.0,
                "confirmation_interval_covered": 0.0,
                "confirmation_call_count": int(laboratory.called),
                "false_discovery": 0.0,
                "supported_claim": 0.0,
                "correct_refusal": 0.0,
                "world_kind": world["kind"],
            }
        row["world_index"] = index
        rows.append(row)
    return rows


def evaluate(synthesize_evidence):
    development_rows = _evaluate_split(synthesize_evidence, DEVELOPMENT_SPECS)
    # The next split is a new scientific corpus too.  _evaluate_split resets
    # within a split, so explicitly replace the final development worker before
    # the first held-out corpus.
    if hasattr(synthesize_evidence, "reset_session"):
        synthesize_evidence.reset_session()
    heldout_rows = _evaluate_split(synthesize_evidence, HELDOUT_SPECS)
    development = _aggregate(development_rows, DEVELOPMENT_SPECS)
    heldout = _aggregate(heldout_rows, HELDOUT_SPECS)
    development_valid = development["valid_rate"] == 1.0
    heldout_valid = heldout["valid_rate"] == 1.0
    combined = development["normalized_score"] if development_valid else 0.0
    return {
        "combined_score": combined,
        "raw_score": combined,
        "valid": float(development_valid),
        "feasibility_rate": development["valid_rate"],
        "robustness_score": development["robust_quality"] if development_valid else 0.0,
        "heldout_policy_score": heldout["normalized_score"] if heldout_valid else 0.0,
        "heldout_robustness_score": heldout["robust_quality"] if heldout_valid else 0.0,
        "heldout_feasibility_rate": heldout["valid_rate"],
        "development_evidence_integrity_score": development["evidence_integrity_score"],
        "heldout_evidence_integrity_score": heldout["evidence_integrity_score"],
        "development_preconfirmation_mechanism_score": development["preconfirmation_mechanism_score"],
        "heldout_preconfirmation_mechanism_score": heldout["preconfirmation_mechanism_score"],
        "development_prediction_score": development["prediction_score"],
        "heldout_prediction_score": heldout["prediction_score"],
        "development_forecast_distribution_score": development["forecast_distribution_score"],
        "heldout_forecast_distribution_score": heldout["forecast_distribution_score"],
        "development_design_information_score": development["design_information_score"],
        "heldout_design_information_score": heldout["design_information_score"],
        "development_postconfirmation_score": development["postconfirmation_score"],
        "heldout_postconfirmation_score": heldout["postconfirmation_score"],
        "development_confirmation_point_score": development["confirmation_point_score"],
        "heldout_confirmation_point_score": heldout["confirmation_point_score"],
        "development_confirmation_interval_coverage": development["confirmation_interval_coverage"],
        "heldout_confirmation_interval_coverage": heldout["confirmation_interval_coverage"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "heldout_false_discovery_rate": heldout["false_discovery_rate"],
        "development_supported_claim_coverage": development["supported_claim_coverage"],
        "heldout_supported_claim_coverage": heldout["supported_claim_coverage"],
        "development_unsupported_refusal_rate": development["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": heldout["unsupported_refusal_rate"],
        "development_mean_confirmation_calls": development["mean_confirmation_calls"],
        "heldout_mean_confirmation_calls": heldout["mean_confirmation_calls"],
        "development_raw_quality": development["raw_quality"],
        "heldout_raw_quality": heldout["raw_quality"],
        "per_world": development_rows + heldout_rows,
    }


def _reference_update(problem, confirmation):
    records = copy.deepcopy(problem["records"])
    records.append({
        "record_id": confirmation["registration_id"] + "-registry",
        "registration_id": confirmation["registration_id"],
        "record_type": "registry_result",
        "population": TARGET_POPULATION,
        "comparator": TARGET_COMPARATOR,
        "randomized": True,
        "preregistered_primary": PRIMARY_ENDPOINT,
        "moderator_value": confirmation["moderator_value"],
        "sample_size": confirmation["sample_size"],
        "highlighted_outcome": PRIMARY_ENDPOINT,
        "outcomes": [{
            "name": PRIMARY_ENDPOINT,
            "effect": confirmation["effect"],
            "standard_error": confirmation["standard_error"],
        }],
    })
    updated_problem = dict(problem)
    updated_problem["records"] = records
    return _reference_pre_model(updated_problem)


def reference_policy(problem, confirm):
    screening = _reference_screening(problem)
    pre = _reference_pre_model(problem)
    # The public reference estimates tau and then enumerates the declared design
    # menu; it does not use the hidden world.  This intentionally differs from the
    # oracle-only best-design helper used by task calibration.
    rows = _registry_rows(problem["records"])
    x = np.asarray([row["moderator_value"] for row in rows])
    se = np.asarray([row["outcomes"][0]["standard_error"] for row in rows])
    design = np.column_stack((np.ones_like(x), x))
    weights = 1.0 / (se * se + pre["tau"] ** 2)
    information = design.T @ (weights[:, None] * design) + np.eye(2) * 1.0e-9
    choices = []
    for site, sample_size in _feasible_designs(problem):
        vector = np.asarray((1.0, site["moderator_value"]))
        weight = 1.0 / (_standard_error(sample_size) ** 2 + pre["tau"] ** 2)
        gain = (
            np.linalg.slogdet(information + weight * np.outer(vector, vector))[1]
            - np.linalg.slogdet(information)[1]
        )
        cost = sample_size * site["cost_per_participant"] / problem["study_budget"]
        choices.append((gain - 0.18 * cost, site["site_id"], sample_size))
    _, site_id, sample_size = max(choices, key=lambda row: (row[0], row[1], row[2]))
    site = _candidate_site(problem, site_id)
    if pre["abstain"]:
        quadratic = _fit_meta_regression(problem["records"], quadratic=True)
        vector = np.asarray((
            1.0, site["moderator_value"], site["moderator_value"] ** 2 - 1.0
        ))
        predicted = float(vector @ quadratic["beta"])
    else:
        predicted = pre["intercept"] + pre["moderator_slope"] * site["moderator_value"]
    predictive_sd = math.sqrt(pre["tau"] ** 2 + _standard_error(sample_size) ** 2)
    commit = {
        "screening": screening,
        "preconfirmation": pre,
        "site_id": site_id,
        "sample_size": int(sample_size),
        "forecast": {
            "predicted_effect": float(predicted),
            "prediction_interval": [
                float(max(EFFECT_BOUNDS[0], predicted - Z_90 * predictive_sd)),
                float(min(EFFECT_BOUNDS[1], predicted + Z_90 * predictive_sd)),
            ],
        },
    }
    confirmation = confirm(commit)
    post = _reference_update(problem, confirmation)
    return {"confirmation_commit": commit, "postconfirmation": post}


def _truth_policy(world, problem, confirm):
    expected = _expected_screening(world)
    screening = {
        "included_registration_ids": sorted(expected["included_registration_ids"]),
        "primary_record_ids": sorted(expected["primary_record_ids"]),
        "duplicate_groups": sorted([list(group) for group in expected["duplicate_groups"]]),
        "selective_report_ids": sorted(expected["selective_report_ids"]),
    }
    unsupported = world["kind"] == "nonlinear"
    target_effect = _mean_effect(world["truth"], problem["decision_moderator"])
    pre = {
        "intercept": world["truth"]["intercept"],
        "moderator_slope": world["truth"]["moderator_slope"],
        "tau": world["truth"]["tau"],
        "confidence": 1.0,
        "abstain": unsupported,
        "claim_beneficial": bool((not unsupported) and target_effect > problem["benefit_threshold"]),
    }
    site_id, sample_size = _best_design(world, problem)
    site = _candidate_site(problem, site_id)
    predicted = _mean_effect(world["truth"], site["moderator_value"])
    predictive_sd = math.sqrt(world["truth"]["tau"] ** 2 + _standard_error(sample_size) ** 2)
    commit = {
        "screening": screening,
        "preconfirmation": pre,
        "site_id": site_id,
        "sample_size": sample_size,
        "forecast": {
            "predicted_effect": predicted,
            "prediction_interval": [
                predicted - Z_90 * predictive_sd,
                predicted + Z_90 * predictive_sd,
            ],
        },
    }
    confirm(commit)
    return {"confirmation_commit": commit, "postconfirmation": dict(pre)}


def oracle_reference_policy(problem, confirm):
    # Match the supplied public problem to one registered fixed world.  This helper
    # is used only by trusted calibration and never exposed to candidate code.
    record_ids = {record["record_id"] for record in problem["records"]}
    for spec in DEVELOPMENT_SPECS + HELDOUT_SPECS:
        world = _make_world(spec)
        if record_ids == {record["record_id"] for record in world["records"]}:
            return _truth_policy(world, problem, confirm)
    raise ValueError("unknown prospective evidence world")


def weak_baseline(problem, confirm):
    del problem, confirm
    model = {
        "intercept": 0.0,
        "moderator_slope": 0.0,
        "tau": 0.0,
        "confidence": 1.0,
        "abstain": True,
        "claim_beneficial": False,
    }
    return {"confirmation_commit": None, "postconfirmation": model}
