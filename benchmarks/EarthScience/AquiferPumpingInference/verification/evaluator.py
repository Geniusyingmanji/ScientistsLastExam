"""Deterministic active pumping-test oracle."""
from __future__ import annotations

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
MIN_EVIDENCE = 12
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
    if split == "development":
        params = (
            ("confined", 0.0011, 0.00035, {}), ("confined", 0.0035, 0.0014, {}),
            ("confined", 0.00062, 0.00011, {}), ("confined", 0.0070, 0.0040, {}),
            ("confined", 0.0020, 0.0075, {}),
            ("leaky_aquifer", 0.0016, 0.0007, {"leakage_length": 145.0}),
            ("recharge_boundary", 0.0028, 0.0011, {"boundary_distance": 115.0}),
            ("dual_porosity", 0.0013, 0.00032, {"storage_ratio": 18.0, "delay": 5.0, "fast_weight": 0.62}),
        )
        seed0 = 31100
    else:
        params = (
            ("confined", 0.00085, 0.00022, {}), ("confined", 0.0048, 0.0022, {}),
            ("confined", 0.00145, 0.0050, {}), ("confined", 0.0090, 0.0008, {}),
            ("confined", 0.0025, 0.000075, {}),
            ("leaky_aquifer", 0.0022, 0.0010, {"leakage_length": 105.0}),
            ("recharge_boundary", 0.0012, 0.00042, {"boundary_distance": 165.0}),
            ("dual_porosity", 0.0038, 0.0008, {"storage_ratio": 12.0, "delay": 7.0, "fast_weight": 0.55}),
        )
        seed0 = 71900
    return [{"kind": k, "T": t, "S": s, "seed": seed0 + i, "query_ids": [],
             "spent": 0, "violated": False, **extra}
            for i, (k, t, s, extra) in enumerate(params)]


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
        "measurement_model": "one unit per drawdown observation; independent deterministic Gaussian noise",
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
    if world["spent"] >= BUDGET:
        world["violated"] = True
        raise RuntimeError("measurement budget exceeded")
    call = world["spent"]
    world["spent"] += 1
    sigma = 0.012 + 0.000015 * radius
    rng = random.Random(world["seed"] * 1009 + call * 9176 + RADII_M.index(radius) * 101 + TIMES_S.index(time))
    value = max(0.0, float(_curve(world, radius, time)) + rng.gauss(0.0, sigma))
    qid = "aq-%d-%02d" % (world["seed"], call)
    world["query_ids"].append(qid)
    return {"measurement_id": qid, "radius_m": radius, "time_s": time,
            "drawdown_m": value, "drawdown_standard_error_m": sigma,
            "cost_units": 1, "spent_units": world["spent"]}


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
    if not isinstance(ids, list) or len(ids) < minimum or len(ids) != len(set(ids)):
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
        t_score = math.exp(-abs(math.log(result["transmissivity_m2_s"] / world["T"])) / 0.55)
        s_score = math.exp(-abs(math.log(result["storativity"] / world["S"])) / 0.70)
        parameter = 0.60 * t_score + 0.40 * s_score
        truth = np.asarray([_curve(world, r, t) for r, t in PREDICTION_CONTEXTS])
        scale = 0.025 + 0.05 * np.maximum(truth, 0.05)
        prediction = math.exp(-float(np.mean(np.abs(result["predicted_drawdown_m"] - truth) / scale)))
        science = 0.55 * parameter + 0.30 * prediction + 0.15 * float(correct_mechanism)
    elif correct_refusal:
        parameter = prediction = 0.0
        science = 1.0
    else:
        parameter = prediction = science = 0.0
    calibration = max(0.0, 1.0 - abs(result["confidence"] - science))
    combined = science * (0.92 + 0.08 * calibration)
    return {"science_score": science, "parameter_recovery_score": parameter,
            "prediction_score": prediction, "combined_score": combined,
            "correct_mechanism": correct_mechanism, "attempted": attempted,
            "false_discovery": false_discovery, "correct_refusal": correct_refusal,
            "abstained": result["abstain"], "valid": True}


def _invalid_metrics():
    result = {"combined_score": 0.0, "valid": 0.0, "raw_score": 0.0}
    for split in ("development", "heldout"):
        for key in ("combined_score", "mechanism_score", "false_discovery_rate",
                    "correct_refusal_rate", "discovery_coverage", "attempted_discovery_rate"):
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
    return {
        "combined_score": float(np.mean([row["combined_score"] for row in rows])),
        "mechanism_score": float(np.mean([row["correct_mechanism"] for row in rows])),
        "mechanism_correct_count": sum(row["correct_mechanism"] for row in rows),
        "mechanism_total_count": len(rows),
        "false_discovery_rate": sum(row["false_discovery"] for row in rows) / len(claims) if claims else 0.0,
        "false_discovery_count": sum(row["false_discovery"] for row in rows),
        "claim_count": len(claims),
        "correct_refusal_rate": sum(row["correct_refusal"] for row in unsupported) / len(unsupported),
        "correct_refusal_count": sum(row["correct_refusal"] for row in unsupported),
        "unsupported_world_count": len(unsupported),
        "discovery_coverage": sum(not row["abstained"] for row in supported) / len(supported),
        "supported_discovery_count": sum(not row["abstained"] for row in supported),
        "supported_world_count": len(supported),
        "attempted_discovery_rate": len(claims) / len(rows),
        "attempted_discovery_count": len(claims), "world_count": len(rows),
        "parameter_recovery_score": float(np.mean([row["parameter_recovery_score"] for row in supported])),
        "prediction_score": float(np.mean([row["prediction_score"] for row in supported])),
    }


def evaluate(candidate) -> dict[str, Any]:
    all_rows = []
    for split in ("development", "heldout"):
        split_rows = []
        for world in _worlds(split):
            problem = public_problem()
            try:
                submission = candidate(problem, lambda r, t, w=world: _measure(w, r, t))
                result = _validate(submission, problem, world)
                row = {"kind": world["kind"], **_score(world, result)}
            except Exception:
                return _invalid_metrics()
            split_rows.append(row)
        all_rows.append((split, split_rows))
    metrics = {"valid": 1.0}
    for split, rows in all_rows:
        summary = _summary(rows)
        for key, value in summary.items():
            metrics[split + "_" + key] = value
    metrics["combined_score"] = metrics["development_combined_score"]
    metrics["raw_score"] = metrics["combined_score"]
    metrics["robustness_score"] = metrics["heldout_combined_score"]
    return metrics


def reference_anchor():
    return {"development_score": 1.0, "heldout_score": 1.0}
