"""Active multi-height gravity survey for parametric source discovery.

Candidates choose station locations and observation heights under a charged survey budget,
then return a small collection of rectangular 2-D density bodies or explicitly refuse the
declared source library.  External-field prediction, signed-body recovery, null/model-
inadequacy refusal and held-out transfer are reported separately.  Raw pixel similarity is
deliberately not used because gravity inversion is non-unique.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.optimize import linear_sum_assignment


G_CONST = 6.67430e-11
PROFILE_BOUNDS_M = (0.0, 10000.0)
OBSERVATION_HEIGHT_BOUNDS_M = (0.0, 1500.0)
DEPTH_BOUNDS_M = (100.0, 5000.0)
MIN_SURVEY_POINTS = 4
MAX_SURVEY_POINTS = 24
SURVEY_BUDGET_UNITS = 24
MAX_BODIES = 4

X_CENTER_BOUNDS_M = (0.0, 10000.0)
Z_CENTER_BOUNDS_M = (200.0, 4700.0)
WIDTH_BOUNDS_M = (200.0, 3500.0)
BODY_HEIGHT_BOUNDS_M = (150.0, 1800.0)
DENSITY_ABS_BOUNDS_KG_M3 = (50.0, 800.0)


BASE_BODIES = (
    ((2700.0, 850.0, 1100.0, 500.0, 480.0),
     (7200.0, 2200.0, 1800.0, 900.0, -360.0)),
    ((2100.0, 1500.0, 1500.0, 800.0, 350.0),
     (6100.0, 2850.0, 2400.0, 1050.0, 280.0)),
    ((1800.0, 700.0, 700.0, 350.0, 550.0),
     (5000.0, 1800.0, 1200.0, 700.0, -420.0),
     (8100.0, 3300.0, 2100.0, 1000.0, 300.0)),
    ((4300.0, 3200.0, 2600.0, 1100.0, 420.0),
     (6200.0, 900.0, 800.0, 450.0, -500.0)),
    ((3300.0, 1250.0, 1800.0, 700.0, 400.0),
     (5350.0, 2450.0, 2000.0, 900.0, -350.0),
     (8200.0, 800.0, 800.0, 400.0, 500.0)),
    ((5600.0, 3600.0, 3000.0, 1200.0, -450.0),),
    ((1600.0, 2100.0, 1200.0, 800.0, -380.0),
     (4700.0, 650.0, 900.0, 300.0, 620.0),
     (7600.0, 2500.0, 1700.0, 1100.0, 330.0)),
)


# (seed, template, point-noise standard deviation in mGal, kind).
DEVELOPMENT_SPECS = (
    (73021, 0, 0.035, "in_library"),
    (73027, 1, 0.040, "in_library"),
    (73039, 2, 0.045, "in_library"),
    (73061, 3, 0.040, "in_library"),
    (73063, 0, 0.035, "null"),
    (73079, 0, 0.045, "misspecified"),
)
HELDOUT_SPECS = (
    (83003, 4, 0.060, "in_library"),
    (83009, 5, 0.065, "in_library"),
    (83023, 6, 0.070, "in_library"),
    (83047, 0, 0.060, "null"),
    (83059, 0, 0.075, "misspecified"),
)


def _make_bodies(seed, template):
    if not 0 <= int(template) < len(BASE_BODIES):
        raise ValueError("unknown body template")
    rng = np.random.default_rng(int(seed))
    bodies = np.asarray(BASE_BODIES[int(template)], dtype=float).copy()
    bodies[:, 0] += rng.uniform(-140.0, 140.0, size=len(bodies))
    bodies[:, 1] += rng.uniform(-90.0, 90.0, size=len(bodies))
    bodies[:, 2] *= rng.uniform(0.94, 1.06, size=len(bodies))
    bodies[:, 3] *= rng.uniform(0.94, 1.06, size=len(bodies))
    bodies[:, 4] *= rng.uniform(0.94, 1.06, size=len(bodies))
    return bodies


def _smooth_misspecified_cells(seed):
    """Return a resolvable seven-lobe field outside the at-most-four-body library."""
    rng = np.random.default_rng(int(seed) + 4049)
    x_centers = np.linspace(125.0, 9875.0, 40)
    z_centers = np.linspace(175.0, 3375.0, 24)
    dx = float(x_centers[1] - x_centers[0])
    dz = float(z_centers[1] - z_centers[0])
    xx, zz = np.meshgrid(x_centers, z_centers)
    density = np.zeros_like(xx)
    centers = np.linspace(850.0, 9150.0, 7)
    for index, center in enumerate(centers):
        center += rng.uniform(-65.0, 65.0)
        depth = 500.0 + 105.0 * (index % 3) + rng.uniform(-35.0, 35.0)
        sign = 1.0 if index % 2 == 0 else -1.0
        amplitude = sign * rng.uniform(430.0, 570.0)
        density += amplitude * np.exp(
            -0.5 * ((xx - center) / 250.0) ** 2
            -0.5 * ((zz - depth) / 190.0) ** 2
        )
    keep = np.abs(density) >= 2.0
    return np.column_stack((
        xx[keep], zz[keep], np.full(np.sum(keep), dx),
        np.full(np.sum(keep), dz), density[keep],
    ))


def _world(spec):
    seed, template, noise, kind = spec
    if kind == "in_library":
        bodies = _make_bodies(seed, template)
        cells = np.empty((0, 5), dtype=float)
    elif kind == "misspecified":
        bodies = np.empty((0, 5), dtype=float)
        cells = _smooth_misspecified_cells(seed)
    else:
        bodies = np.empty((0, 5), dtype=float)
        cells = np.empty((0, 5), dtype=float)
    return {
        "seed": int(seed),
        "template": int(template),
        "noise": float(noise),
        "kind": str(kind),
        "bodies": bodies,
        "cells": cells,
    }


def _primitive(horizontal_offset, depth):
    return (
        depth * np.arctan2(horizontal_offset, depth)
        + 0.5 * horizontal_offset * np.log(
            depth * depth + horizontal_offset * horizontal_offset
        )
    )


def rectangle_field(bodies, station_x_m, observation_height_m=0.0):
    """Vertical gravity of infinite-strike rectangular bodies in mGal.

    Each body row is `(x_center, z_center, width, height, density_contrast)` in SI units,
    with positive depth downward.  The expression analytically integrates the 2-D Newtonian
    kernel over each rectangle.
    """
    x = np.asarray(station_x_m, dtype=float).ravel()
    values = np.zeros(len(x), dtype=float)
    for body in np.asarray(bodies, dtype=float).reshape((-1, 5)):
        xc, zc, width, height, density = body
        x_left = xc - 0.5 * width
        x_right = xc + 0.5 * width
        z_top = zc - 0.5 * height + float(observation_height_m)
        z_bottom = zc + 0.5 * height + float(observation_height_m)
        right = x_right - x
        left = x_left - x
        integral = (
            _primitive(right, z_bottom) - _primitive(right, z_top)
            - _primitive(left, z_bottom) + _primitive(left, z_top)
        )
        values += 2.0 * G_CONST * density * integral * 1.0e5
    return values


def _world_field(world, station_x_m, observation_height_m):
    if world["kind"] == "in_library":
        return rectangle_field(world["bodies"], station_x_m, observation_height_m)
    if world["kind"] == "misspecified":
        return rectangle_field(world["cells"], station_x_m, observation_height_m)
    return np.zeros(len(np.asarray(station_x_m).ravel()), dtype=float)


def _query_seed(world_seed, call_index, station_x_m, observation_height_m):
    payload = np.concatenate((
        np.asarray((observation_height_m,), dtype="<f8"),
        np.asarray(station_x_m, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Survey:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.records = []

    def measure(self, station_x_m, observation_height_m=0.0):
        stations = np.asarray(station_x_m, dtype=float)
        if stations.ndim != 1 or not (
            MIN_SURVEY_POINTS <= len(stations) <= MAX_SURVEY_POINTS
        ):
            raise ValueError("station_x_m must contain 4-24 positions")
        if np.any(~np.isfinite(stations)) or np.any(
            stations < PROFILE_BOUNDS_M[0]
        ) or np.any(stations > PROFILE_BOUNDS_M[1]):
            raise ValueError("survey stations lie outside the public profile")
        if np.any(np.diff(stations) <= 0.0):
            raise ValueError("survey stations must be strictly increasing")
        height = float(observation_height_m)
        if not math.isfinite(height) or not (
            OBSERVATION_HEIGHT_BOUNDS_M[0]
            <= height <= OBSERVATION_HEIGHT_BOUNDS_M[1]
        ):
            raise ValueError("observation height outside the public bounds")
        cost = 1 + int(math.ceil(len(stations) / 4.0))
        if self.used + cost > SURVEY_BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("survey budget exceeded")
        self.used += cost
        self.calls += 1
        clean = _world_field(self.world, stations, height)
        noise_scale = float(self.world["noise"]) * (1.0 + 0.20 * height / 1500.0)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, stations, height
        ))
        observed = clean + rng.normal(scale=noise_scale, size=len(stations))
        record = {
            "station_x_m": stations.copy(),
            "observation_height_m": height,
            "gravity_mgal": observed,
            "noise_std_mgal": np.full(len(stations), noise_scale),
            "budget_cost": int(cost),
        }
        self.records.append(record)
        return {key: (value.copy() if isinstance(value, np.ndarray) else value)
                for key, value in record.items()}


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    bodies = np.asarray(submission.get("bodies"), dtype=float)
    if bodies.size == 0:
        bodies = np.empty((0, 5), dtype=float)
    if bodies.ndim != 2 or bodies.shape[1:] != (5,) or len(bodies) > MAX_BODIES:
        raise ValueError("bodies must have shape (0-4,5)")
    if np.any(~np.isfinite(bodies)):
        raise ValueError("body parameters must be finite")
    abstain = bool(submission["abstain"])
    if abstain:
        if len(bodies):
            raise ValueError("abstention requires an empty body list")
        return bodies, confidence, True
    if not len(bodies):
        raise ValueError("a non-abstaining claim needs at least one body")

    x, z, width, height, density = bodies.T
    if np.any(x < X_CENTER_BOUNDS_M[0]) or np.any(x > X_CENTER_BOUNDS_M[1]):
        raise ValueError("body x center outside public bounds")
    if np.any(z < Z_CENTER_BOUNDS_M[0]) or np.any(z > Z_CENTER_BOUNDS_M[1]):
        raise ValueError("body depth center outside public bounds")
    if np.any(width < WIDTH_BOUNDS_M[0]) or np.any(width > WIDTH_BOUNDS_M[1]):
        raise ValueError("body width outside public bounds")
    if np.any(height < BODY_HEIGHT_BOUNDS_M[0]) or np.any(
        height > BODY_HEIGHT_BOUNDS_M[1]
    ):
        raise ValueError("body height outside public bounds")
    if np.any(np.abs(density) < DENSITY_ABS_BOUNDS_KG_M3[0]) or np.any(
        np.abs(density) > DENSITY_ABS_BOUNDS_KG_M3[1]
    ):
        raise ValueError("density contrast outside public magnitude bounds")
    if np.any(x - 0.5 * width < PROFILE_BOUNDS_M[0]) or np.any(
        x + 0.5 * width > PROFILE_BOUNDS_M[1]
    ):
        raise ValueError("body extends outside the public profile")
    if np.any(z - 0.5 * height < DEPTH_BOUNDS_M[0]) or np.any(
        z + 0.5 * height > DEPTH_BOUNDS_M[1]
    ):
        raise ValueError("body extends outside the public depth range")
    return bodies.copy(), confidence, False


def _body_matching_metrics(world, predicted_bodies, abstain):
    if world["kind"] in {"null", "misspecified"}:
        correct = bool(abstain and len(predicted_bodies) == 0)
        return {
            "body_support_f1": 1.0 if correct else 0.0,
            "field_component_score": 1.0 if correct else 0.0,
            "mass_moment_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        }
    truth = world["bodies"]
    if abstain or not len(predicted_bodies):
        return {
            "body_support_f1": 0.0,
            "field_component_score": 0.0,
            "mass_moment_score": 0.0,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
        }

    signature_x = np.linspace(-1000.0, 11000.0, 73)
    signature_heights = (0.0, 650.0, 1800.0)
    true_fields = np.asarray([
        np.concatenate([
            rectangle_field([body], signature_x, height)
            for height in signature_heights
        ]) for body in truth
    ])
    predicted_fields = np.asarray([
        np.concatenate([
            rectangle_field([body], signature_x, height)
            for height in signature_heights
        ]) for body in predicted_bodies
    ])
    similarity = np.zeros((len(truth), len(predicted_bodies)))
    moments = np.zeros_like(similarity)
    for i, true_body in enumerate(truth):
        scale = max(0.08, float(np.sqrt(np.mean(true_fields[i] ** 2))))
        for j, predicted_body in enumerate(predicted_bodies):
            relative = float(np.sqrt(np.mean(
                (predicted_fields[j] - true_fields[i]) ** 2
            ))) / scale
            similarity[i, j] = math.exp(-0.5 * (relative / 0.42) ** 2)
            true_mass = true_body[2] * true_body[3] * true_body[4]
            predicted_mass = (
                predicted_body[2] * predicted_body[3] * predicted_body[4]
            )
            if true_mass * predicted_mass <= 0.0:
                moments[i, j] = 0.0
                continue
            error = (
                (math.log(abs(predicted_mass / true_mass)) / 0.50) ** 2
                + ((predicted_body[0] - true_body[0]) / 700.0) ** 2
                + ((predicted_body[1] - true_body[1]) / 800.0) ** 2
            )
            moments[i, j] = math.exp(-0.5 * error)
    rows, columns = linear_sum_assignment(-similarity)
    field_credit = float(np.sum(similarity[rows, columns]))
    precision = field_credit / len(predicted_bodies)
    recall = field_credit / len(truth)
    support_f1 = (
        0.0 if precision + recall == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )
    component_score = field_credit / len(truth)
    moment_score = float(np.mean(moments[rows, columns]))
    mechanism = 0.45 * support_f1 + 0.30 * component_score + 0.25 * moment_score
    return {
        "body_support_f1": float(support_f1),
        "field_component_score": float(component_score),
        "mass_moment_score": moment_score,
        "mechanism_score": float(mechanism),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _prediction_score(world, predicted_bodies, extrapolation):
    rng = np.random.default_rng(
        world["seed"] + (920003 if extrapolation else 910001)
    )
    if extrapolation:
        stations = np.sort(np.concatenate((
            rng.uniform(-1800.0, -100.0, size=18),
            rng.uniform(10100.0, 11800.0, size=18),
        )))
        heights = (2100.0, 3000.0)
    else:
        stations = np.sort(rng.uniform(0.0, 10000.0, size=44))
        heights = (250.0, 950.0)
    errors = []
    baseline = []
    for height in heights:
        truth = _world_field(world, stations, height)
        prediction = rectangle_field(predicted_bodies, stations, height)
        errors.extend((prediction - truth).tolist())
        baseline.extend(truth.tolist())
    rmse = float(np.sqrt(np.mean(np.asarray(errors) ** 2)))
    baseline_rmse = max(
        2.0 * float(world["noise"]),
        float(np.sqrt(np.mean(np.asarray(baseline) ** 2))),
    )
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _observed_fit_score(survey, predicted_bodies):
    if not survey.records:
        return 0.0
    errors = []
    baseline_errors = []
    for record in survey.records:
        prediction = rectangle_field(
            predicted_bodies, record["station_x_m"],
            record["observation_height_m"],
        )
        observed = record["gravity_mgal"]
        errors.extend((prediction - observed).tolist())
        baseline_errors.extend(observed.tolist())
    rmse = float(np.sqrt(np.mean(np.asarray(errors) ** 2)))
    baseline_rmse = max(
        2.0 * float(survey.world["noise"]),
        float(np.sqrt(np.mean(np.asarray(baseline_errors) ** 2))),
    )
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _reference_submission(world):
    if world["kind"] != "in_library":
        return {"bodies": [], "confidence": 0.0, "abstain": True}
    return {
        "bodies": world["bodies"].copy(),
        "confidence": 1.0,
        "abstain": False,
    }


def _evaluate_world(discover_bodies, spec, split, index):
    world = _world(spec)
    survey = _Survey(world)
    try:
        submission = discover_bodies(
            PROFILE_BOUNDS_M, DEPTH_BOUNDS_M, survey.measure,
            SURVEY_BUDGET_UNITS,
        )
        bodies, confidence, abstain = _validate_submission(submission)
        if survey.violated:
            raise RuntimeError("survey budget exceeded")
        mechanism = _body_matching_metrics(world, bodies, abstain)
        interpolation = _prediction_score(world, bodies, False)
        extrapolation = _prediction_score(world, bodies, True)
        observed_fit = 0.0 if abstain else _observed_fit_score(survey, bodies)
        target_confidence = (
            mechanism["mechanism_score"]
            if world["kind"] == "in_library" else 0.0
        )
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "body_support_f1": round(mechanism["body_support_f1"], 6),
            "field_component_score": round(
                mechanism["field_component_score"], 6
            ),
            "mass_moment_score": round(mechanism["mass_moment_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "observed_fit_score": round(observed_fit, 6),
            "interpolation_prediction_score": round(interpolation, 6),
            "extrapolation_prediction_score": round(extrapolation, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - target_confidence) ** 2, 6
            ),
            "correct_refusal": mechanism["correct_refusal"],
            "false_discovery": mechanism["false_discovery"],
            "abstained": abstain,
            "confidence": round(confidence, 6),
            "n_true_bodies": len(world["bodies"]),
            "n_predicted_bodies": len(bodies),
            "survey_calls": survey.calls,
            "survey_budget_units": survey.used,
            "survey_points": sum(len(row["station_x_m"]) for row in survey.records),
        }
    except Exception as exc:
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "body_support_f1": 0.0,
            "field_component_score": 0.0,
            "mass_moment_score": 0.0,
            "mechanism_score": 0.0,
            "observed_fit_score": 0.0,
            "interpolation_prediction_score": 0.0,
            "extrapolation_prediction_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "n_true_bodies": len(world["bodies"]),
            "n_predicted_bodies": 0,
            "survey_calls": survey.calls,
            "survey_budget_units": survey.used,
            "survey_points": sum(len(row["station_x_m"]) for row in survey.records),
        }


def _split_summary(records, unsupported_count):
    raw_mechanism = float(np.mean([row["mechanism_score"] for row in records]))
    always_abstain = unsupported_count / len(records)
    normalized = float(np.clip(
        (raw_mechanism - always_abstain) / (1.0 - always_abstain), 0.0, 1.0
    ))
    supported = [row for row in records if row["kind"] == "in_library"]
    unsupported = [row for row in records if row["kind"] != "in_library"]
    misspecified = [row for row in records if row["kind"] == "misspecified"]
    null = [row for row in records if row["kind"] == "null"]
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw_mechanism,
        "body_support_f1": float(np.mean([
            row["body_support_f1"] for row in supported
        ])),
        "field_component": float(np.mean([
            row["field_component_score"] for row in supported
        ])),
        "mass_moment": float(np.mean([
            row["mass_moment_score"] for row in supported
        ])),
        "observed_fit": float(np.mean([
            row["observed_fit_score"] for row in supported
        ])),
        "interpolation_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in supported
        ])),
        "extrapolation_prediction": float(np.mean([
            row["extrapolation_prediction_score"] for row in supported
        ])),
        "misspecified_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in misspecified
        ])),
        "null_prediction": float(np.mean([
            row["interpolation_prediction_score"] for row in null
        ])),
        "confidence_calibration": float(np.mean([
            row["confidence_calibration_score"] for row in records
        ])),
        "false_discovery_rate": float(np.mean([
            row["false_discovery"] for row in unsupported
        ])),
        "correct_refusal_rate": float(np.mean([
            row["correct_refusal"] for row in unsupported
        ])),
        "valid_count": sum(bool(row["valid"]) for row in records),
    }


def evaluate(discover_bodies):
    development = [
        _evaluate_world(discover_bodies, spec, "development", index)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ]
    heldout = [
        _evaluate_world(discover_bodies, spec, "heldout", index)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    dev = _split_summary(
        development,
        sum(spec[3] != "in_library" for spec in DEVELOPMENT_SPECS),
    )
    hold = _split_summary(
        heldout, sum(spec[3] != "in_library" for spec in HELDOUT_SPECS),
    )
    all_records = development + heldout
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized_mechanism"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "development_body_support_f1": dev["body_support_f1"],
        "development_field_component_score": dev["field_component"],
        "development_mass_moment_score": dev["mass_moment"],
        "development_observed_fit_score": dev["observed_fit"],
        "development_prediction_score": dev["interpolation_prediction"],
        "development_extrapolation_score": dev["extrapolation_prediction"],
        "development_misspecified_prediction_score": dev["misspecified_prediction"],
        "development_null_prediction_score": dev["null_prediction"],
        "development_confidence_calibration_score": dev["confidence_calibration"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "robustness_score": hold["normalized_mechanism"] if hold_valid else 0.0,
        "heldout_mechanism_score": hold["raw_mechanism"],
        "heldout_body_support_f1": hold["body_support_f1"],
        "heldout_field_component_score": hold["field_component"],
        "heldout_mass_moment_score": hold["mass_moment"],
        "heldout_observed_fit_score": hold["observed_fit"],
        "heldout_prediction_score": hold["interpolation_prediction"],
        "heldout_extrapolation_score": hold["extrapolation_prediction"],
        "heldout_misspecified_prediction_score": hold["misspecified_prediction"],
        "heldout_null_prediction_score": hold["null_prediction"],
        "heldout_confidence_calibration_score": hold["confidence_calibration"],
        "heldout_false_discovery_rate": hold["false_discovery_rate"],
        "heldout_correct_refusal_rate": hold["correct_refusal_rate"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "mean_survey_calls": float(np.mean([
            row["survey_calls"] for row in all_records
        ])),
        "mean_survey_budget_units": float(np.mean([
            row["survey_budget_units"] for row in all_records
        ])),
        "mean_survey_points": float(np.mean([
            row["survey_points"] for row in all_records
        ])),
        "per_world": all_records,
    }
