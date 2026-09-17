"""Deterministic active pumping-test oracle."""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any

import numpy as np
from scipy.special import exp1

RADII_M = (12.0, 25.0, 55.0, 110.0, 220.0)
TIMES_S = (90.0, 300.0, 900.0, 2700.0, 9000.0, 28800.0, 86400.0)
PREDICTION_CONTEXTS = (
    (18.0, 450.0), (18.0, 14400.0), (40.0, 1200.0), (40.0, 50000.0),
    (85.0, 3600.0), (85.0, 70000.0), (175.0, 12000.0), (175.0, 110000.0),
)
Q_M3_S = 0.018
BUDGET = 24
RADIUS_SETUP_COST = 6
MEASUREMENT_COST = 1
MIN_EVIDENCE = 6
MAX_EVIDENCE = BUDGET
DIAGNOSES = ("confined", "leaky_aquifer", "recharge_boundary", "dual_porosity", "undetermined")
PARAMETER_BOUNDS = {
    "transmissivity_m2_s": (2.0e-4, 2.0e-2),
    "storativity": (2.0e-5, 2.0e-2),
}


def theis_drawdown(transmissivity, storativity, radius_m, time_s):
    transmissivity = np.asarray(transmissivity, dtype=float)
    radius_m = np.asarray(radius_m, dtype=float)
    time_s = np.asarray(time_s, dtype=float)
    u = radius_m * radius_m * float(storativity) / (4.0 * transmissivity * time_s)
    return Q_M3_S * exp1(u) / (4.0 * math.pi * transmissivity)


def _curve(world, radius, time):
    base = theis_drawdown(world["T"], world["S"], radius, time)
    kind = world["kind"]
    if kind == "confined":
        return base
    if kind == "leaky_aquifer":
        return base * np.exp(-np.asarray(radius, dtype=float) / world["leakage_length"])
    if kind == "recharge_boundary":
        image_radius = np.sqrt(np.asarray(radius, dtype=float) ** 2 + (2.0 * world["boundary_distance"]) ** 2)
        return np.maximum(0.0, base - theis_drawdown(world["T"], world["S"], image_radius, time))
    slow = theis_drawdown(world["T"], world["S"] * world["storage_ratio"], radius,
                          np.asarray(time, dtype=float) / world["delay"])
    return world["fast_weight"] * base + (1.0 - world["fast_weight"]) * slow


def _worlds(split):
    development = split == "development"
    seed0 = 31100 if development else 71900
    rng = random.Random(seed0 + 193)
    supported_count = 12 if development else 9
    unsupported_per_family = 4 if development else 3

    def aquifer_parameters():
        return (
            10.0 ** rng.uniform(math.log10(4.0e-4), math.log10(9.0e-3)),
            10.0 ** rng.uniform(math.log10(6.0e-5), math.log10(7.0e-3)),
        )

    params = []
    for _ in range(supported_count):
        transmissivity, storativity = aquifer_parameters()
        params.append(("confined", transmissivity, storativity, {}))
    for _ in range(unsupported_per_family):
        transmissivity, storativity = aquifer_parameters()
        params.append(("leaky_aquifer", transmissivity, storativity, {
            "leakage_length": rng.uniform(380.0, 650.0),
        }))
        transmissivity, storativity = aquifer_parameters()
        params.append(("recharge_boundary", transmissivity, storativity, {
            "boundary_distance": rng.uniform(320.0, 600.0),
        }))
        transmissivity, storativity = aquifer_parameters()
        params.append(("dual_porosity", transmissivity, storativity, {
            "storage_ratio": rng.uniform(3.5, 10.0),
            "delay": rng.uniform(2.2, 5.5),
            "fast_weight": rng.uniform(0.68, 0.88),
        }))
    worlds = [{"kind": k, "T": t, "S": s, "seed": seed0 + i, "query_ids": [],
               "spent": 0, "violated": False, "used_radii": set(),
               "coordinate_repeats": {}, **extra}
              for i, (k, t, s, extra) in enumerate(params)]
    random.Random(seed0 + 8071).shuffle(worlds)
    return worlds


def public_problem():
    return {
        "schema_version": 1,
        "pumping_rate_m3_s": Q_M3_S,
        "observation_radii_m": list(RADII_M),
        "observation_times_s": list(TIMES_S),
        "measurement_budget_units": BUDGET,
        "minimum_evidence_measurements": MIN_EVIDENCE,
        "parameter_bounds": {key: list(value) for key, value in PARAMETER_BOUNDS.items()},
        "prediction_contexts": [{"radius_m": r, "time_s": t} for r, t in PREDICTION_CONTEXTS],
        "diagnosis_values": list(DIAGNOSES),
        "supported_model": "Theis confined-aquifer radial-flow model",
        "measurement_model": (
            "the first observation at each distinct radius costs seven units: six radius-setup "
            "units plus one measurement unit; later observations at that radius cost one unit; "
            "Gaussian noise is deterministic by coordinate and repeat index"
        ),
        "abstain_when": "use a named refusal for a resolved unsupported family, otherwise undetermined",
    }


def _measure(world, radius, time):
    try:
        radius = float(radius)
        time = float(time)
    except Exception as exc:
        world["violated"] = True
        raise ValueError("radius and time must be numeric") from exc
    if radius not in RADII_M or time not in TIMES_S:
        world["violated"] = True
        raise ValueError("measurement coordinate is not listed")
    radius_index = RADII_M.index(radius)
    time_index = TIMES_S.index(time)
    setup_cost = 0 if radius in world["used_radii"] else RADIUS_SETUP_COST
    cost = setup_cost + MEASUREMENT_COST
    if world["spent"] + cost > BUDGET:
        world["violated"] = True
        raise RuntimeError("measurement budget exceeded")
    coordinate = (radius_index, time_index)
    repeat_index = world["coordinate_repeats"].get(coordinate, 0)
    world["coordinate_repeats"][coordinate] = repeat_index + 1
    world["used_radii"].add(radius)
    world["spent"] += cost
    sigma = 0.024 + 0.000020 * radius
    rng = random.Random(
        world["seed"] * 1009 + radius_index * 10007 + time_index * 1000003
        + repeat_index * 100000007
    )
    value = max(0.0, float(_curve(world, radius, time)) + rng.gauss(0.0, sigma))
    identity = "aquifer-v2:%d:%d:%d" % (radius_index, time_index, repeat_index)
    qid = hashlib.blake2s(identity.encode("ascii"), digest_size=12).hexdigest()
    world["query_ids"].append(qid)
    return {"measurement_id": qid, "radius_m": radius, "time_s": time,
            "drawdown_m": value, "drawdown_standard_error_m": sigma,
            "cost_units": cost, "spent_units": world["spent"]}


def _validate(submission, problem, world):
    required = {"diagnosis", "transmissivity_m2_s", "storativity", "predicted_drawdown_m",
                "confidence", "abstain", "evidence_measurement_ids"}
    if not isinstance(submission, dict) or set(submission) != required:
        raise ValueError("submission must contain exactly the documented keys")
    diagnosis = submission["diagnosis"]
    abstain = submission["abstain"]
    if diagnosis not in DIAGNOSES or type(abstain) is not bool:
        raise ValueError("invalid diagnosis or abstain")
    if (diagnosis == "confined") != (not abstain):
        raise ValueError("diagnosis and abstain disagree")
    values = {}
    for key, bounds in PARAMETER_BOUNDS.items():
        value = float(submission[key])
        if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise ValueError("parameter outside bounds")
        values[key] = value
    pred = np.asarray(submission["predicted_drawdown_m"], dtype=float)
    if pred.shape != (len(PREDICTION_CONTEXTS),) or not np.all(np.isfinite(pred)) or np.any(pred < 0.0):
        raise ValueError("invalid predictions")
    confidence = float(submission["confidence"])
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("invalid confidence")
    ids = submission["evidence_measurement_ids"]
    minimum = 1 if diagnosis == "undetermined" else MIN_EVIDENCE
    if (not isinstance(ids, list) or len(ids) < minimum or len(ids) > MAX_EVIDENCE
            or len(ids) != len(set(ids))):
        raise ValueError("insufficient unique evidence")
    if not set(ids).issubset(set(world["query_ids"])):
        raise ValueError("fabricated evidence")
    if world["violated"]:
        raise ValueError("measurement contract was violated")
    return {**values, "predicted_drawdown_m": pred, "diagnosis": diagnosis,
            "abstain": abstain, "confidence": confidence}


def _score(world, result):
    target = world["kind"]
    correct_mechanism = result["diagnosis"] == target
    attempted = result["diagnosis"] != "undetermined"
    false_discovery = attempted and not correct_mechanism
    correct_refusal = target != "confined" and correct_mechanism and result["abstain"]
    if target == "confined" and not result["abstain"]:
        t_score = float(np.clip(
            1.0 - abs(math.log(result["transmissivity_m2_s"] / world["T"])) / 0.22,
            0.0, 1.0,
        ))
        s_score = float(np.clip(
            1.0 - abs(math.log(result["storativity"] / world["S"])) / 0.30,
            0.0, 1.0,
        ))
        parameter = 0.60 * t_score + 0.40 * s_score
        truth = np.asarray([_curve(world, r, t) for r, t in PREDICTION_CONTEXTS])
        scale = 0.012 + 0.040 * np.maximum(truth, 0.05)
        prediction = float(np.clip(
            1.0 - float(np.mean(np.abs(result["predicted_drawdown_m"] - truth) / scale)),
            0.0, 1.0,
        ))
        science = float(correct_mechanism) * parameter * (0.70 + 0.30 * prediction)
    elif correct_refusal:
        parameter = 0.0
        truth = np.asarray([_curve(world, r, t) for r, t in PREDICTION_CONTEXTS])
        scale = 0.012 + 0.040 * np.maximum(truth, 0.05)
        prediction = float(np.clip(
            1.0 - float(np.mean(np.abs(result["predicted_drawdown_m"] - truth) / scale)),
            0.0, 1.0,
        ))
        science = prediction
    else:
        parameter = prediction = science = 0.0
    combined = science
    return {"science_score": science, "parameter_recovery_score": parameter,
            "prediction_score": prediction, "combined_score": combined,
            "correct_mechanism": correct_mechanism, "attempted": attempted,
            "false_discovery": false_discovery, "correct_refusal": correct_refusal,
            "abstained": result["abstain"], "valid": True}


def _invalid_metrics(reason="candidate_invalid"):
    result = {"combined_score": 0.0, "valid": 0.0, "raw_score": 0.0,
              "robustness_score": 0.0, "error_message": reason}
    for split in ("development", "heldout"):
        for key in ("combined_score", "mechanism_score", "false_discovery_rate",
                    "correct_refusal_rate", "discovery_coverage", "attempted_discovery_rate",
                    "parameter_recovery_score", "prediction_score",
                    "unsupported_prediction_score"):
            result[split + "_" + key] = 0.0
        for key in ("mechanism_correct_count", "mechanism_total_count", "false_discovery_count",
                    "claim_count", "correct_refusal_count", "unsupported_world_count",
                    "supported_discovery_count", "supported_world_count", "attempted_discovery_count",
                    "world_count"):
            result[split + "_" + key] = 0
    return result


def _summary(rows):
    supported = [row for row in rows if row["kind"] == "confined"]
    unsupported = [row for row in rows if row["kind"] != "confined"]
    claims = [row for row in rows if row["attempted"]]
    supported_quality = float(np.mean([row["combined_score"] for row in supported]))
    unsupported_quality = float(np.mean([row["combined_score"] for row in unsupported]))
    correct_refusal_rate = sum(row["correct_refusal"] for row in unsupported) / len(unsupported)
    return {
        "combined_score": supported_quality * unsupported_quality,
        "mechanism_score": float(np.mean([row["correct_mechanism"] for row in rows])),
        "mechanism_correct_count": sum(row["correct_mechanism"] for row in rows),
        "mechanism_total_count": len(rows),
        "false_discovery_rate": sum(row["false_discovery"] for row in rows) / len(claims) if claims else 0.0,
        "false_discovery_count": sum(row["false_discovery"] for row in rows),
        "claim_count": len(claims),
        "correct_refusal_rate": correct_refusal_rate,
        "correct_refusal_count": sum(row["correct_refusal"] for row in unsupported),
        "unsupported_world_count": len(unsupported),
        "discovery_coverage": sum(not row["abstained"] for row in supported) / len(supported),
        "supported_discovery_count": sum(not row["abstained"] for row in supported),
        "supported_world_count": len(supported),
        "attempted_discovery_rate": len(claims) / len(rows),
        "attempted_discovery_count": len(claims), "world_count": len(rows),
        "parameter_recovery_score": float(np.mean([row["parameter_recovery_score"] for row in supported])),
        "prediction_score": float(np.mean([row["prediction_score"] for row in supported])),
        "unsupported_prediction_score": unsupported_quality,
    }


def evaluate(candidate) -> dict[str, Any]:
    all_rows = []
    for split in ("development", "heldout"):
        split_rows = []
        for world in _worlds(split):
            problem = public_problem()
            try:
                reset = getattr(candidate, "reset_session", None)
                if callable(reset):
                    reset()
                submission = candidate(problem, lambda r, t, w=world: _measure(w, r, t))
                result = _validate(submission, problem, world)
                row = {"kind": world["kind"], **_score(world, result)}
            except Exception as exc:
                detail = str(exc).replace("\n", " ").strip()[:200]
                reason = "candidate_invalid:%s" % type(exc).__name__
                if detail:
                    reason += ":" + detail
                return _invalid_metrics(reason)
            split_rows.append(row)
        all_rows.append((split, split_rows))
    metrics = {"valid": 1.0, "error_message": None}
    for split, rows in all_rows:
        summary = _summary(rows)
        for key, value in summary.items():
            metrics[split + "_" + key] = value
    metrics["combined_score"] = metrics["development_combined_score"]
    metrics["raw_score"] = metrics["combined_score"]
    metrics["robustness_score"] = metrics["heldout_combined_score"]
    return metrics
