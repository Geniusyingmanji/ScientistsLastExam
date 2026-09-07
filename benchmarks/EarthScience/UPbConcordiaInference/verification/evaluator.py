"""Deterministic oracle for active zircon U-Pb concordia inference."""
from __future__ import annotations

import math

import numpy as np

LAMBDA_235 = 9.8485e-10
LAMBDA_238 = 1.55125e-10
GRAIN_COUNT = 24
BUDGET = 18
AGE_BOUNDS = (450.0, 2850.0)
LOSS_BOUNDS = (40.0, 950.0)
CRYST_TOLERANCE = 15.0
LOSS_TOLERANCE = 25.0
PRECISIONS = {
    "screen": {"cost": 1, "relative_sigma": 0.0100},
    "analytical": {"cost": 3, "relative_sigma": 0.0025},
}


def _concordia(age_myr):
    years = float(age_myr) * 1.0e6
    return np.array([
        math.expm1(LAMBDA_235 * years),
        math.expm1(LAMBDA_238 * years),
    ])


def _descriptors(seed):
    rng = np.random.default_rng((seed, 101))
    position = (np.arange(GRAIN_COUNT) + rng.uniform(0.05, 0.95, GRAIN_COUNT)) / GRAIN_COUNT
    rng.shuffle(position)
    uranium = rng.lognormal(math.log(310.0), 0.38, GRAIN_COUNT)
    quality = np.clip(0.55 + 0.0010 * uranium + rng.normal(0.0, 0.08, GRAIN_COUNT), 0.45, 1.15)
    return [
        {
            "grain_id": int(i),
            "domain_position": round(float(position[i]), 5),
            "uranium_ppm": round(float(uranium[i]), 2),
            "expected_signal_quality": round(float(quality[i]), 4),
        }
        for i in range(GRAIN_COUNT)
    ]


def _make_world(spec):
    seed = int(spec["seed"])
    rng = np.random.default_rng(seed)
    kind = spec["kind"]
    crystallization = float(rng.uniform(1250.0, 2600.0))
    loss = None
    second_loss = None
    if kind in {"lead_loss", "multi_event"}:
        loss = float(rng.uniform(120.0, min(850.0, crystallization - 550.0)))
    if kind == "multi_event":
        second_loss = float(min(loss + rng.uniform(320.0, 620.0), crystallization - 260.0))

    descriptors = _descriptors(seed)
    clean = []
    old = _concordia(crystallization)
    for descriptor in descriptors:
        position = descriptor["domain_position"]
        local_rng = np.random.default_rng((seed, 211, descriptor["grain_id"]))
        if kind == "concordant":
            age = crystallization + local_rng.normal(0.0, 3.0)
            point = _concordia(age)
        else:
            retained = float(np.clip(0.06 + 0.88 * position + local_rng.normal(0.0, 0.025), 0.03, 0.97))
            active_loss = loss
            if kind == "multi_event" and descriptor["domain_position"] >= 0.5:
                active_loss = second_loss
            point = retained * old + (1.0 - retained) * _concordia(active_loss)
        clean.append(point)
    return {
        "kind": kind,
        "seed": seed,
        "crystallization_age_myr": crystallization,
        "lead_loss_age_myr": loss,
        "second_loss_age_myr": second_loss,
        "descriptors": descriptors,
        "clean": clean,
    }


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.measured = set()
        self.violated = False

    def __call__(self, grain_id, precision):
        if isinstance(grain_id, bool) or not isinstance(grain_id, (int, np.integer)):
            raise ValueError("grain_id must be an integer")
        grain_id = int(grain_id)
        if not 0 <= grain_id < GRAIN_COUNT:
            raise ValueError("grain_id is outside the published grain list")
        if not isinstance(precision, str) or precision not in PRECISIONS:
            raise ValueError("precision must be screen or analytical")
        if grain_id in self.measured:
            raise ValueError("each grain may be measured only once")
        cost = PRECISIONS[precision]["cost"]
        if self.used + cost > BUDGET:
            self.violated = True
            raise RuntimeError("measurement budget exceeded")
        self.used += cost
        self.calls += 1
        self.measured.add(grain_id)

        descriptor = self.world["descriptors"][grain_id]
        clean = self.world["clean"][grain_id]
        base = PRECISIONS[precision]["relative_sigma"] / descriptor["expected_signal_quality"]
        sigma_x = max(0.0015, base * clean[0])
        sigma_y = max(0.00045, base * clean[1])
        rho = 0.32
        covariance = np.array([
            [sigma_x * sigma_x, rho * sigma_x * sigma_y],
            [rho * sigma_x * sigma_y, sigma_y * sigma_y],
        ])
        rng = np.random.default_rng((self.world["seed"], 307, grain_id, self.calls))
        observed = rng.multivariate_normal(clean, covariance)
        return {
            "query_id": "q%02d" % self.calls,
            "grain_id": grain_id,
            "pb207_u235": float(observed[0]),
            "pb206_u238": float(observed[1]),
            "sigma_pb207_u235": float(sigma_x),
            "sigma_pb206_u238": float(sigma_y),
            "correlation": rho,
            "precision": precision,
            "budget_cost": cost,
            "budget_used": self.used,
        }


PUBLIC_PROBLEM = {
    "grain_descriptors": None,
    "measurement_budget_units": BUDGET,
    "decay_constants_per_year": {"u235": LAMBDA_235, "u238": LAMBDA_238},
    "age_bounds_myr": list(AGE_BOUNDS),
    "lead_loss_age_bounds_myr": list(LOSS_BOUNDS),
    "crystallization_age_tolerance_myr": CRYST_TOLERANCE,
    "lead_loss_age_tolerance_myr": LOSS_TOLERANCE,
    "precision_options": {
        key: {"cost": value["cost"], "relative_sigma_at_quality_one": value["relative_sigma"]}
        for key, value in PRECISIONS.items()
    },
    "concordia_model": "x(t)=exp(lambda_u235*t)-1 is 207Pb*/235U and y(t)=exp(lambda_u238*t)-1 is 206Pb*/238U, with t in years",
    "supported_histories": ["concordant", "lead_loss"],
    "measurement_model": "measure(grain_id, precision) measures one previously unmeasured grain; uncertainty scales inversely with expected_signal_quality and the requested precision",
    "forecast_or_validation_description": "reported ages must explain all cited measurements as one concordia age or one straight discordia whose two concordia intercepts are the crystallization and lead-loss ages",
    "abstain_when": "measurements resolve a history outside the supported family, including multiple lead-loss episodes or inherited-component mixtures",
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
    if not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) for v in evidence):
        raise ValueError("evidence_query_ids must be a non-empty list of query ids")
    if len(evidence) != len(set(evidence)) or not set(evidence).issubset(query_ids):
        raise ValueError("evidence_query_ids must name distinct measurements made in this world")
    if abstain:
        return {"abstain": True, "confidence": confidence, "evidence": evidence}
    history = submission.get("history")
    if history not in {"concordant", "lead_loss"}:
        raise ValueError("history must be concordant or lead_loss")
    crystallization = float(submission.get("crystallization_age_myr", float("nan")))
    if not math.isfinite(crystallization) or not AGE_BOUNDS[0] <= crystallization <= AGE_BOUNDS[1]:
        raise ValueError("crystallization_age_myr is outside age_bounds_myr")
    result = {"abstain": False, "history": history, "crystallization": crystallization,
              "confidence": confidence, "evidence": evidence}
    if history == "lead_loss":
        loss = float(submission.get("lead_loss_age_myr", float("nan")))
        if not math.isfinite(loss) or not LOSS_BOUNDS[0] <= loss <= LOSS_BOUNDS[1]:
            raise ValueError("lead_loss_age_myr is outside lead_loss_age_bounds_myr")
        if loss >= crystallization:
            raise ValueError("lead_loss_age_myr must be younger than crystallization_age_myr")
        result["loss"] = loss
    return result


def _score_world(world, claim):
    row = {
        "history_correct": False,
        "crystallization_age_score": 0.0,
        "lead_loss_age_score": 0.0,
        "mechanism_score": 0.0,
        "false_discovery": False,
        "correct_refusal": False,
    }
    kind = world["kind"]
    if kind == "multi_event":
        row["correct_refusal"] = bool(claim["abstain"])
        row["false_discovery"] = not claim["abstain"]
        row["mechanism_score"] = 1.0 if claim["abstain"] else 0.0
        return row
    if claim["abstain"]:
        return row
    history_correct = claim["history"] == kind
    row["history_correct"] = history_correct
    row["false_discovery"] = not history_correct
    if not history_correct:
        return row
    cryst = max(0.0, 1.0 - abs(claim["crystallization"] - world["crystallization_age_myr"]) / CRYST_TOLERANCE)
    row["crystallization_age_score"] = cryst
    if kind == "concordant":
        row["mechanism_score"] = 0.40 + 0.60 * cryst
    else:
        loss = max(0.0, 1.0 - abs(claim["loss"] - world["lead_loss_age_myr"]) / LOSS_TOLERANCE)
        row["lead_loss_age_score"] = loss
        row["mechanism_score"] = 0.30 + 0.40 * cryst + 0.30 * loss
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "lead_loss", "seed": 731001},
    {"kind": "concordant", "seed": 731002},
    {"kind": "lead_loss", "seed": 731003},
    {"kind": "lead_loss", "seed": 731004},
    {"kind": "multi_event", "seed": 731005},
    {"kind": "lead_loss", "seed": 731006},
    {"kind": "concordant", "seed": 731007},
    {"kind": "lead_loss", "seed": 731008},
    {"kind": "multi_event", "seed": 731009},
    {"kind": "lead_loss", "seed": 731010},
)

HELDOUT_WORLDS = (
    {"kind": "lead_loss", "seed": 842001},
    {"kind": "concordant", "seed": 842002},
    {"kind": "lead_loss", "seed": 842003},
    {"kind": "multi_event", "seed": 842004},
    {"kind": "lead_loss", "seed": 842005},
    {"kind": "lead_loss", "seed": 842006},
    {"kind": "concordant", "seed": 842007},
    {"kind": "multi_event", "seed": 842008},
    {"kind": "lead_loss", "seed": 842009},
)


def _evaluate_world(candidate, spec, split, index):
    world = _make_world(spec)
    laboratory = _Laboratory(world)
    problem = dict(PUBLIC_PROBLEM)
    problem["grain_descriptors"] = [dict(value) for value in world["descriptors"]]
    base = {"split": split, "world_index": index, "kind": world["kind"],
            "true_crystallization_age_myr": round(world["crystallization_age_myr"], 6),
            "true_lead_loss_age_myr": None if world["lead_loss_age_myr"] is None else round(world["lead_loss_age_myr"], 6)}
    try:
        submission = candidate(problem, laboratory)
        query_ids = {"q%02d" % i for i in range(1, laboratory.calls + 1)}
        claim = _validate_submission(submission, query_ids)
        if laboratory.violated:
            raise RuntimeError("measurement budget exceeded")
        metrics = _score_world(world, claim)
        row = dict(base)
        row.update(metrics)
        target = metrics["mechanism_score"]
        row.update({
            "valid": True,
            "abstained": claim["abstain"],
            "claimed_history": claim.get("history"),
            "confidence": claim["confidence"],
            "confidence_calibration_score": 1.0 - (claim["confidence"] - target) ** 2,
            "budget_used": laboratory.used,
            "measurements": laboratory.calls,
            "evidence_count": len(claim["evidence"]),
        })
        return row
    except Exception as exc:  # noqa: BLE001 - malformed candidates score invalid
        row = dict(base)
        row.update({
            "history_correct": False, "crystallization_age_score": 0.0,
            "lead_loss_age_score": 0.0, "mechanism_score": 0.0,
            "false_discovery": False, "correct_refusal": False,
            "valid": False, "abstained": True, "claimed_history": None,
            "confidence": 0.0, "confidence_calibration_score": 0.0,
            "budget_used": laboratory.used, "measurements": laboratory.calls,
            "evidence_count": 0, "reason": "%s: %s" % (type(exc).__name__, exc),
        })
        return row


def _summary(rows):
    supported = [row for row in rows if row["kind"] != "multi_event"]
    lead_loss = [row for row in rows if row["kind"] == "lead_loss"]
    unsupported = [row for row in rows if row["kind"] == "multi_event"]
    claims = [row for row in rows if not row["abstained"]]
    raw = float(np.mean([row["mechanism_score"] for row in rows]))
    abstain_anchor = len(unsupported) / len(rows)
    normalized = float(np.clip((raw - abstain_anchor) / (1.0 - abstain_anchor), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "history_accuracy": float(np.mean([row["history_correct"] for row in supported])),
        "crystallization_age_score": float(np.mean([row["crystallization_age_score"] for row in supported])),
        "lead_loss_age_score": float(np.mean([row["lead_loss_age_score"] for row in lead_loss])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in claims])) if claims else 0.0,
        "false_discovery_count": sum(bool(row["false_discovery"]) for row in claims),
        "claim_count": len(claims),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "refusal_count": sum(bool(row["correct_refusal"]) for row in unsupported),
        "unsupported_count": len(unsupported),
        "discovery_coverage": float(np.mean([not row["abstained"] for row in supported])),
        "covered_supported_count": sum(not row["abstained"] for row in supported),
        "supported_count": len(supported),
        "confidence_calibration": float(np.mean([row["confidence_calibration_score"] for row in rows])),
        "mean_budget_used": float(np.mean([row["budget_used"] for row in rows])),
        "valid_count": sum(bool(row["valid"]) for row in rows),
        "world_count": len(rows),
    }


def evaluate(infer_upb_history):
    development = [_evaluate_world(infer_upb_history, spec, "development", i)
                   for i, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(infer_upb_history, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_WORLDS)]
    dev = _summary(development)
    held = _summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_history_accuracy": dev["history_accuracy"],
        "development_crystallization_age_score": dev["crystallization_age_score"],
        "development_lead_loss_age_score": dev["lead_loss_age_score"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_false_discovery_denominator": dev["claim_count"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_correct_refusal_denominator": dev["unsupported_count"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_discovery_coverage_denominator": dev["supported_count"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_budget_used": dev["mean_budget_used"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_history_accuracy": held["history_accuracy"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
