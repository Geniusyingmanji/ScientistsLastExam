"""Deterministic active volcanic deformation mechanism oracle."""

from __future__ import annotations

import hashlib
import math

import numpy as np

BOUNDS_M = (-5000.0, 5000.0)
BUDGET_UNITS = 18
MECHANISMS = ("mogi", "sill", "dike")
PARAMETER_BOUNDS = np.asarray([
    [-3500.0, 3500.0], [-3500.0, 3500.0], [500.0, 5000.0],
    [5.0e7, 1.2e9], [500.0, 3500.0],
])
LOOK_VECTOR = np.asarray((0.42, -0.18, 0.889), dtype=float)
LOOK_VECTOR /= np.linalg.norm(LOOK_VECTOR)

DEVELOPMENT_SPECS = (
    (62011, "supported", "mogi"), (62017, "supported", "sill"),
    (62029, "supported", "dike"), (62039, "supported", "mogi"),
    (62047, "null", "null"), (62053, "misspecified", "multi_source"),
)
HELDOUT_SPECS = (
    (72007, "supported", "sill"), (72019, "supported", "dike"),
    (72031, "supported", "mogi"), (72043, "null", "null"),
    (72053, "misspecified", "rheology"),
)


def model_library():
    return {
        "mechanisms": list(MECHANISMS),
        "parameter_names": ["x_center_m", "y_center_m", "depth_m", "strength", "horizontal_scale_m"],
        "parameter_bounds": PARAMETER_BOUNDS.copy(),
        "equations": {
            "mogi": "u = strength * [dx,dy,depth] / (dx^2+dy^2+depth^2)^(3/2)",
            "sill": "uz=(strength/1e9) exp(-r^2/(2 scale^2)); ur=0.25 uz r/scale",
            "dike": "ux=(strength/1e9) exp(-y'^2/(2 scale^2)) tanh(x'/scale); uz=0.55 abs(ux)",
        },
    }


def forward_displacement(mechanism, parameters, stations_xy_m):
    stations = np.asarray(stations_xy_m, dtype=float).reshape((-1, 2))
    x0, y0, depth, strength, scale = np.asarray(parameters, dtype=float)
    dx = stations[:, 0] - x0
    dy = stations[:, 1] - y0
    radius = np.sqrt(dx * dx + dy * dy) + 1e-12
    if mechanism == "mogi":
        denominator = (dx * dx + dy * dy + depth * depth) ** 1.5
        return strength * np.column_stack((dx, dy, np.full(len(stations), depth))) / denominator[:, None]
    amplitude = strength / 1.0e9
    if mechanism == "sill":
        vertical = amplitude * np.exp(-0.5 * (radius / scale) ** 2) * (1500.0 / depth)
        radial = 0.25 * vertical * radius / scale
        return np.column_stack((radial * dx / radius, radial * dy / radius, vertical))
    if mechanism == "dike":
        along = (dx + 0.35 * dy) / math.sqrt(1.0 + 0.35 ** 2)
        across = (dy - 0.35 * dx) / math.sqrt(1.0 + 0.35 ** 2)
        horizontal = amplitude * np.exp(-0.5 * (across / scale) ** 2) * np.tanh(along / scale)
        return np.column_stack((0.94 * horizontal, 0.34 * horizontal, 0.55 * np.abs(horizontal)))
    raise ValueError("unknown mechanism")


def _parameters(seed):
    rng = np.random.default_rng(int(seed))
    lo, hi = PARAMETER_BOUNDS[:, 0], PARAMETER_BOUNDS[:, 1]
    values = lo + rng.uniform(size=5) * (hi - lo)
    values[4] = rng.uniform(800.0, 2600.0)
    return values


def _world(spec):
    seed, kind, mechanism = spec
    parameters = _parameters(seed)
    return {"seed": seed, "kind": kind, "mechanism": mechanism, "parameters": parameters,
            "noise_gnss": 0.0035, "noise_insar": 0.006}


def _field(world, stations):
    if world["kind"] == "null":
        return np.zeros((len(stations), 3), dtype=float)
    if world["kind"] == "supported":
        return forward_displacement(world["mechanism"], world["parameters"], stations)
    first = forward_displacement("mogi", world["parameters"], stations)
    second_params = world["parameters"].copy()
    second_params[:2] *= -0.7
    second_params[2] *= 1.35
    second_params[3] *= -0.55
    second = forward_displacement("sill", second_params, stations)
    field = first + second
    if world["mechanism"] == "rheology":
        field = np.sign(field) * np.sqrt(np.abs(field) * 0.08)
    return field


class _Survey:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def measure(self, stations_xy_m, modality="gnss"):
        stations = np.asarray(stations_xy_m, dtype=float)
        if stations.ndim != 2 or stations.shape[1] != 2 or not 3 <= len(stations) <= 20:
            self.violated = True
            raise ValueError("stations_xy_m must have shape (3-20,2)")
        if np.any(~np.isfinite(stations)) or np.any(stations < BOUNDS_M[0]) or np.any(stations > BOUNDS_M[1]):
            self.violated = True
            raise ValueError("station outside survey bounds")
        if len(np.unique(stations, axis=0)) != len(stations):
            self.violated = True
            raise ValueError("stations must be unique")
        if modality not in {"gnss", "insar"}:
            self.violated = True
            raise ValueError("modality must be gnss or insar")
        cost = 1 + int(math.ceil(len(stations) / 5.0))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("survey budget exceeded")
        self.used += cost
        self.calls += 1
        clean = _field(self.world, stations)
        sigma = self.world["noise_gnss"] if modality == "gnss" else self.world["noise_insar"]
        payload = np.asarray(stations, dtype="<f8").tobytes() + modality.encode()
        digest = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
        rng = np.random.default_rng(self.world["seed"] + digest + 1009 * self.calls)
        if modality == "gnss":
            observed = clean + rng.normal(0.0, sigma, clean.shape)
            look = []
        else:
            observed = clean @ LOOK_VECTOR + rng.normal(0.0, sigma, len(stations))
            look = LOOK_VECTOR.copy()
        return {"stations_xy_m": stations.copy(), "modality": modality,
                "displacement_m": observed, "noise_std_m": sigma,
                "look_vector": look, "budget_cost": cost}


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    probabilities = submission.get("mechanism_probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(MECHANISMS):
        raise ValueError("mechanism_probabilities has wrong keys")
    probs = np.asarray([probabilities[name] for name in MECHANISMS], dtype=float)
    if np.any(~np.isfinite(probs)) or np.any(probs < 0.0) or not np.isclose(np.sum(probs), 1.0, atol=1e-6):
        raise ValueError("mechanism probabilities must be nonnegative and sum to one")
    parameters = np.asarray(submission.get("parameters"), dtype=float)
    if bool(abstain):
        if parameters.size:
            raise ValueError("abstention requires empty parameters")
        return probs, None, confidence, True
    if parameters.shape != (5,) or np.any(~np.isfinite(parameters)):
        raise ValueError("parameters must be a finite length-5 row")
    if np.any(parameters < PARAMETER_BOUNDS[:, 0]) or np.any(parameters > PARAMETER_BOUNDS[:, 1]):
        raise ValueError("parameters outside public bounds")
    return probs, parameters, confidence, False


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "class_probability": 0.0, "parameter_score": 0.0,
            "prediction_score": 0.0, "reduced_chi_square": 1e12, "brier_score": 2.0,
            "confidence_score": 0.0, "false_discovery": False, "correct_refusal": False,
            "survey_cost": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    survey = _Survey(world)
    try:
        submission = candidate(BOUNDS_M, model_library(), survey.measure, BUDGET_UNITS)
        probs, parameters, confidence, abstain = _validate(submission)
        if survey.violated:
            raise ValueError("survey contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            truth_index = MECHANISMS.index(world["mechanism"])
            class_probability = float(probs[truth_index])
            scale = PARAMETER_BOUNDS[:, 1] - PARAMETER_BOUNDS[:, 0]
            parameter_error = float(np.sqrt(np.mean(((parameters - world["parameters"]) / scale) ** 2)))
            parameter_score = float(math.exp(-8.0 * parameter_error))
            axis = np.linspace(-4700.0, 4700.0, 9)
            sealed = np.asarray([(x, y) for x in axis for y in axis if (int(x + y) // 100) % 3 == 0])
            truth = _field(world, sealed)
            predicted = forward_displacement(MECHANISMS[int(np.argmax(probs))], parameters, sealed)
            sigma = world["noise_gnss"]
            chi2 = float(np.mean(((predicted - truth) / sigma) ** 2))
            prediction_score = float(1.0 / (1.0 + math.sqrt(chi2) / 150.0))
            mechanism = float((class_probability * parameter_score * prediction_score) ** (1.0 / 3.0))
        elif supported:
            class_probability = parameter_score = prediction_score = mechanism = 0.0
            chi2 = 1e12
        else:
            correct = bool(abstain)
            class_probability = parameter_score = prediction_score = mechanism = 1.0 if correct else 0.0
            chi2 = 0.0 if correct else 1e12
        target = np.zeros(3)
        if supported:
            target[MECHANISMS.index(world["mechanism"])] = 1.0
        brier = float(np.sum((probs - target) ** 2))
        target_confidence = 1.0 if supported and not abstain else 0.0
        row.update({"valid": True, "abstained": abstain, "mechanism_score": mechanism,
                    "class_probability": class_probability, "parameter_score": parameter_score,
                    "prediction_score": prediction_score, "reduced_chi_square": chi2,
                    "brier_score": brier,
                    "confidence_score": 1.0 - (confidence - target_confidence) ** 2,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "survey_cost": survey.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw, "valid_count": sum(r["valid"] for r in rows),
        "class_probability": float(np.mean([r["class_probability"] for r in supported])),
        "parameter_score": float(np.mean([r["parameter_score"] for r in supported])),
        "prediction_score": float(np.mean([r["prediction_score"] for r in supported])),
        "brier": float(np.mean([r["brier_score"] for r in rows])),
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(infer_deformation_source):
    development = [_evaluate_world(infer_deformation_source, spec, "development", i)
                   for i, spec in enumerate(DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(infer_deformation_source, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_class_probability": dev["class_probability"],
        "development_parameter_score": dev["parameter_score"],
        "development_prediction_score": dev["prediction_score"],
        "development_brier_score": dev["brier"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "discovery_attempt_count": dev["attempt_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_prediction_score": hold["prediction_score"],
        "heldout_brier_score": hold["brier"],
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "heldout_discovery_coverage": hold["attempt_count"] / hold["supported_count"],
        "per_world": development + heldout,
    }
