"""Deterministic oracle for occupancy inference with imperfect detection."""
from __future__ import annotations

import math

import numpy as np

SITE_COUNT = 48
BUDGET = 84
MAX_VISITS = 3
EFFECT_BOUNDS = (-4.0, 4.0)
EFFECT_TOLERANCE = 1.0
OCCUPANCY_TOLERANCE = 0.18
METHODS = {
    "rapid": {"cost": 1, "detection_boost": -0.50},
    "intensive": {"cost": 2, "detection_boost": 1.50},
}


def _sigmoid(value):
    value = float(np.clip(value, -30.0, 30.0))
    return 1.0 / (1.0 + math.exp(-value))


def _make_world(spec):
    seed = int(spec["seed"])
    rng = np.random.default_rng(seed)
    habitat = np.linspace(-1.6, 1.6, SITE_COUNT)
    rng.shuffle(habitat)
    position = (np.arange(SITE_COUNT) + 0.5) / SITE_COUNT
    accessibility = rng.uniform(-1.0, 1.0, SITE_COUNT)
    kind = spec["kind"]
    alpha = float(spec["alpha"])
    beta = float(spec.get("beta", 0.0))
    gamma = float(spec.get("gamma", 0.0))
    eta = alpha + beta * habitat
    if kind == "quadratic":
        eta += gamma * (habitat * habitat - float(np.mean(habitat * habitat)))
    elif kind == "spatial":
        eta += gamma * np.sin(2.0 * math.pi * position)
    psi = np.array([_sigmoid(v) for v in eta])
    occupied = rng.random(SITE_COUNT) < psi
    descriptors = [
        {
            "site_id": int(i),
            "habitat_covariate": round(float(habitat[i]), 6),
            "transect_position": round(float(position[i]), 6),
            "accessibility_index": round(float(accessibility[i]), 6),
        }
        for i in range(SITE_COUNT)
    ]
    return {
        "kind": kind,
        "seed": seed,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "psi": psi,
        "occupied": occupied,
        "descriptors": descriptors,
        "detection_intercept": float(spec["detection_intercept"]),
    }


class _Survey:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.visits = {}
        self.violated = False

    def _reject(self, message, exc_type=ValueError):
        self.violated = True
        raise exc_type(message)

    def __call__(self, site_id, method):
        if isinstance(site_id, bool) or not isinstance(site_id, (int, np.integer)):
            self._reject("site_id must be an integer")
        site_id = int(site_id)
        if not 0 <= site_id < SITE_COUNT:
            self._reject("site_id is outside site_descriptors")
        if not isinstance(method, str) or method not in METHODS:
            self._reject("method must be rapid or intensive")
        visit = self.visits.get(site_id, 0) + 1
        if visit > MAX_VISITS:
            self._reject("maximum visits per site exceeded")
        cost = METHODS[method]["cost"]
        if self.used + cost > BUDGET:
            self._reject("survey budget exceeded", RuntimeError)
        self.used += cost
        self.calls += 1
        self.visits[site_id] = visit
        descriptor = self.world["descriptors"][site_id]
        logit_p = (
            self.world["detection_intercept"]
            + METHODS[method]["detection_boost"]
            + 0.45 * descriptor["accessibility_index"]
        )
        probability = _sigmoid(logit_p) if self.world["occupied"][site_id] else 0.0
        method_code = 1 if method == "rapid" else 2
        rng = np.random.default_rng((self.world["seed"], 503, site_id, visit, method_code))
        detected = bool(rng.random() < probability)
        return {
            "query_id": "q%02d" % self.calls,
            "site_id": site_id,
            "method": method,
            "detected": detected,
            "visit_number": visit,
            "budget_cost": cost,
            "budget_used": self.used,
        }


PUBLIC_PROBLEM = {
    "site_descriptors": None,
    "survey_budget_units": BUDGET,
    "max_visits_per_site": MAX_VISITS,
    "survey_methods": {
        key: {"cost": value["cost"]} for key, value in METHODS.items()
    },
    "habitat_effect_bounds": list(EFFECT_BOUNDS),
    "supported_effects": ["positive", "negative", "none"],
    "effect_tolerance": EFFECT_TOLERANCE,
    "mean_occupancy_tolerance": OCCUPANCY_TOLERANCE,
    "evidence_requirement": "cite at least four distinct query_id values from surveys made in the current world",
    "occupancy_model": "supported worlds use logit(psi_i)=alpha+beta*habitat_covariate_i; occupancy is latent and detections are conditionally independent given occupancy",
    "detection_model": "detection depends on survey method and accessibility_index; an unoccupied site cannot be detected in the supported family",
    "abstain_when": "the survey histories resolve nonlinear habitat response or spatial occupancy structure outside the supported linear-logit family",
}


def _validate_submission(submission, query_ids):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0, 1]")
    evidence = submission.get("evidence_query_ids", [])
    if not isinstance(evidence, list) or len(evidence) < 4:
        raise ValueError("evidence_query_ids must contain at least four ids")
    if any(not isinstance(value, str) for value in evidence):
        raise ValueError("evidence_query_ids must contain strings")
    if len(evidence) != len(set(evidence)) or not set(evidence).issubset(query_ids):
        raise ValueError("evidence_query_ids must cite distinct current-world surveys")
    if abstain:
        return {"abstain": True, "confidence": confidence, "evidence": evidence}
    effect = submission.get("effect")
    if effect not in {"positive", "negative", "none"}:
        raise ValueError("effect must be positive, negative or none")
    beta = float(submission.get("habitat_effect", float("nan")))
    prevalence = float(submission.get("mean_occupancy", float("nan")))
    if not math.isfinite(beta) or not EFFECT_BOUNDS[0] <= beta <= EFFECT_BOUNDS[1]:
        raise ValueError("habitat_effect is outside habitat_effect_bounds")
    if not math.isfinite(prevalence) or not 0.0 <= prevalence <= 1.0:
        raise ValueError("mean_occupancy must be finite and in [0, 1]")
    return {
        "abstain": False,
        "effect": effect,
        "beta": beta,
        "prevalence": prevalence,
        "confidence": confidence,
        "evidence": evidence,
    }


def _true_effect(beta):
    if beta > 0.25:
        return "positive"
    if beta < -0.25:
        return "negative"
    return "none"


def _score_world(world, claim):
    unsupported = world["kind"] in {"quadratic", "spatial"}
    row = {
        "effect_correct": False,
        "habitat_effect_score": 0.0,
        "mean_occupancy_score": 0.0,
        "mechanism_score": 0.0,
        "false_discovery": False,
        "correct_refusal": False,
    }
    if unsupported:
        row["correct_refusal"] = bool(claim["abstain"])
        row["false_discovery"] = not claim["abstain"]
        row["mechanism_score"] = 1.0 if claim["abstain"] else 0.0
        return row
    if claim["abstain"]:
        return row
    effect_correct = claim["effect"] == _true_effect(world["beta"])
    row["effect_correct"] = effect_correct
    row["false_discovery"] = not effect_correct
    if not effect_correct:
        return row
    beta_score = max(0.0, 1.0 - abs(claim["beta"] - world["beta"]) / EFFECT_TOLERANCE)
    prevalence = float(np.mean(world["psi"]))
    prevalence_score = max(0.0, 1.0 - abs(claim["prevalence"] - prevalence) / OCCUPANCY_TOLERANCE)
    row["habitat_effect_score"] = beta_score
    row["mean_occupancy_score"] = prevalence_score
    row["mechanism_score"] = 0.45 + 0.35 * beta_score + 0.20 * prevalence_score
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "linear", "seed": 92101, "alpha": -0.25, "beta": 1.55, "detection_intercept": -0.10},
    {"kind": "linear", "seed": 92102, "alpha": 0.10, "beta": 2.00, "detection_intercept": -0.35},
    {"kind": "linear", "seed": 92103, "alpha": -0.10, "beta": -1.65, "detection_intercept": 0.15},
    {"kind": "linear", "seed": 92104, "alpha": 0.20, "beta": -2.10, "detection_intercept": -0.25},
    {"kind": "linear", "seed": 92105, "alpha": -0.45, "beta": 0.00, "detection_intercept": 0.10},
    {"kind": "linear", "seed": 92106, "alpha": 0.30, "beta": 0.00, "detection_intercept": -0.30},
    {"kind": "quadratic", "seed": 92107, "alpha": -0.65, "gamma": 2.80, "detection_intercept": 0.05},
    {"kind": "quadratic", "seed": 92108, "alpha": 0.35, "gamma": -2.80, "detection_intercept": -0.20},
    {"kind": "spatial", "seed": 92109, "alpha": -0.20, "gamma": 2.75, "detection_intercept": 0.10},
    {"kind": "spatial", "seed": 92110, "alpha": 0.05, "gamma": -2.75, "detection_intercept": -0.25},
)

HELDOUT_WORLDS = (
    {"kind": "linear", "seed": 93201, "alpha": -0.35, "beta": 1.35, "detection_intercept": -0.40},
    {"kind": "linear", "seed": 93202, "alpha": 0.25, "beta": 2.25, "detection_intercept": 0.05},
    {"kind": "linear", "seed": 93203, "alpha": -0.20, "beta": -1.40, "detection_intercept": -0.15},
    {"kind": "linear", "seed": 93204, "alpha": 0.05, "beta": -2.30, "detection_intercept": -0.40},
    {"kind": "linear", "seed": 93205, "alpha": -0.15, "beta": 0.00, "detection_intercept": 0.00},
    {"kind": "quadratic", "seed": 93206, "alpha": -0.55, "gamma": 3.10, "detection_intercept": -0.20},
    {"kind": "quadratic", "seed": 93207, "alpha": 0.20, "gamma": -3.10, "detection_intercept": 0.00},
    {"kind": "spatial", "seed": 93208, "alpha": -0.10, "gamma": 3.00, "detection_intercept": -0.30},
    {"kind": "spatial", "seed": 93209, "alpha": 0.15, "gamma": -3.00, "detection_intercept": 0.05},
)


def _evaluate_world(candidate, spec, split, index):
    world = _make_world(spec)
    survey = _Survey(world)
    problem = dict(PUBLIC_PROBLEM)
    problem["site_descriptors"] = [dict(value) for value in world["descriptors"]]
    base = {
        "split": split,
        "world_index": index,
        "kind": world["kind"],
        "true_effect": _true_effect(world["beta"]) if world["kind"] == "linear" else "unsupported",
        "true_habitat_effect": world["beta"],
        "true_mean_occupancy": float(np.mean(world["psi"])),
    }
    try:
        submission = candidate(problem, survey)
        query_ids = {"q%02d" % value for value in range(1, survey.calls + 1)}
        claim = _validate_submission(submission, query_ids)
        if survey.violated:
            raise RuntimeError("survey contract or budget was violated")
        metrics = _score_world(world, claim)
        row = dict(base)
        row.update(metrics)
        target = metrics["mechanism_score"]
        row.update({
            "valid": True,
            "abstained": claim["abstain"],
            "claimed_effect": claim.get("effect"),
            "confidence": claim["confidence"],
            "confidence_calibration_score": 1.0 - (claim["confidence"] - target) ** 2,
            "budget_used": survey.used,
            "surveys": survey.calls,
            "surveyed_sites": len(survey.visits),
            "evidence_count": len(claim["evidence"]),
        })
        return row
    except Exception as exc:  # noqa: BLE001 - malformed candidates score invalid
        row = dict(base)
        row.update({
            "effect_correct": False,
            "habitat_effect_score": 0.0,
            "mean_occupancy_score": 0.0,
            "mechanism_score": 0.0,
            "false_discovery": False,
            "correct_refusal": False,
            "valid": False,
            "abstained": True,
            "claimed_effect": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "budget_used": survey.used,
            "surveys": survey.calls,
            "surveyed_sites": len(survey.visits),
            "evidence_count": 0,
            "reason": "%s: %s" % (type(exc).__name__, exc),
        })
        return row


def _summary(rows):
    supported = [row for row in rows if row["kind"] == "linear"]
    unsupported = [row for row in rows if row["kind"] != "linear"]
    claims = [row for row in rows if not row["abstained"]]
    raw = float(np.mean([row["mechanism_score"] for row in rows]))
    abstain_anchor = len(unsupported) / len(rows)
    normalized = float(np.clip((raw - abstain_anchor) / (1.0 - abstain_anchor), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "effect_accuracy": float(np.mean([row["effect_correct"] for row in supported])),
        "habitat_effect_score": float(np.mean([row["habitat_effect_score"] for row in supported])),
        "mean_occupancy_score": float(np.mean([row["mean_occupancy_score"] for row in supported])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in claims])) if claims else 0.0,
        "claim_count": len(claims),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "unsupported_count": len(unsupported),
        "discovery_coverage": float(np.mean([not row["abstained"] for row in supported])),
        "supported_count": len(supported),
        "attempted_discovery": 1.0 if claims else 0.0,
        "confidence_calibration": float(np.mean([row["confidence_calibration_score"] for row in rows])),
        "mean_budget_used": float(np.mean([row["budget_used"] for row in rows])),
        "valid_count": sum(bool(row["valid"]) for row in rows),
        "world_count": len(rows),
    }


def evaluate(infer_occupancy):
    development = [_evaluate_world(infer_occupancy, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(infer_occupancy, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _summary(development)
    held = _summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_effect_accuracy": dev["effect_accuracy"],
        "development_habitat_effect_score": dev["habitat_effect_score"],
        "development_mean_occupancy_score": dev["mean_occupancy_score"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_false_discovery_denominator": dev["claim_count"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_correct_refusal_denominator": dev["unsupported_count"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_discovery_coverage_denominator": dev["supported_count"],
        "development_attempted_discovery": dev["attempted_discovery"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_budget_used": dev["mean_budget_used"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_effect_accuracy": held["effect_accuracy"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
