"""Deterministic chronoamperometric law oracle.

A redox system answers potential steps with current transients. Six published
current-law families are public; the hidden world holds one family and its bounded
parameters, or a mechanism outside the family (fractional-diffusion anomalous
transport, an unmodelled linear baseline drift) that must be refused rather than
forced onto the nearest family.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.special import erfc

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"noise": 0.015, "drift_strength": 1.0},
    2: {"noise": 0.028, "drift_strength": 1.5},
    3: {"noise": 0.045, "drift_strength": 2.2},
}

FAMILIES = ("cottrell", "bounded", "catalytic", "kinetic", "adsorption", "surface")
PARAMETER_BOUNDS = np.asarray([
    [0.2, 5.0], [0.05, 3.0], [0.05, 2.0],
])
POTENTIAL_BOUNDS = (0.1, 1.0)
STEP_COST = 1
BUDGET_UNITS = 6

# Experimental design is part of the scientific task. A supported-world discovery
# that consumes the full budget receives a 50% evidence-efficiency penalty; the
# shipped reference uses three of six steps. Refusal credit is kept separate and
# unweighted so acquiring evidence is not perversely worse than blind abstention.
MAX_EVIDENCE_COST_PENALTY = 0.50
TIME_GRID = np.geomspace(0.002, 8.0, 28)
SEALED_POTENTIAL = 0.6
SEALED_TIME = np.asarray((12.0, 20.0))

_BASE_DEVELOPMENT_SPECS = (
    (12011, "supported", "cottrell"), (12017, "supported", "bounded"),
    (12023, "supported", "catalytic"), (12029, "supported", "kinetic"),
    (12031, "supported", "adsorption"), (12037, "supported", "surface"),
    (12041, "anomalous", "anomalous"), (12047, "drift", "catalytic"),
)
HELDOUT_SPECS = (
    (13007, "supported", "catalytic"), (13013, "supported", "surface"),
    (13019, "supported", "kinetic"), (13023, "anomalous", "anomalous"),
    (13029, "drift", "surface"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def amplitude_factor(potential):
    """Public Nernstian amplitude response of the step potential."""
    return 1.0 - math.exp(-3.0 * potential)


def current_law(family, parameters, potential, t):
    """Public closed forms. `parameters` is the padded three-vector (a, b, c)."""
    a, b, c = (float(parameters[0]), float(parameters[1] or 0.0),
               float(parameters[2] or 0.0))
    phi = amplitude_factor(potential)
    t = np.asarray(t, dtype=float)
    if family == "cottrell":
        return a * phi * t ** -0.5
    if family == "bounded":
        return a * phi * t ** -0.5 * np.tanh(b * t ** -0.5)
    if family == "catalytic":
        return a * phi * t ** -0.5 * np.exp(b * b * t) * erfc(b * np.sqrt(t))
    if family == "kinetic":
        return a * phi * (1.0 - np.exp(-b * math.exp(1.5 * potential) * t))
    if family == "adsorption":
        return a * phi * b * np.exp(-b * t)
    if family == "surface":
        return a * phi * np.exp(-b * t) + c * phi * t ** -0.5
    raise ValueError("unknown family")


def _sample_parameters(rng):
    low, high = PARAMETER_BOUNDS[:, 0], PARAMETER_BOUNDS[:, 1]
    return rng.uniform(low, high)


def _world(spec):
    seed, kind, family = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    parameters = _sample_parameters(rng)
    return {"seed": int(seed), "kind": kind, "family": family,
            "parameters": parameters, "noise": profile["noise"],
            "drift_strength": profile["drift_strength"]}


def problem_statement(world):
    del world
    return {
        "families": list(FAMILIES),
        "current_laws": {
            "cottrell": "i = a*phi(E)*t^-1/2",
            "bounded": "i = a*phi(E)*t^-1/2*tanh(b*t^-1/2)",
            "catalytic": "i = a*phi(E)*t^-1/2*exp(b^2*t)*erfc(b*sqrt(t))",
            "kinetic": "i = a*phi(E)*(1-exp(-b*exp(1.5*E)*t))",
            "adsorption": "i = a*phi(E)*b*exp(-b*t)",
            "surface": "i = a*phi(E)*exp(-b*t)+c*phi(E)*t^-1/2",
        },
        "amplitude_factor": "phi(E) = 1 - exp(-3*E)",
        "parameter_bounds": PARAMETER_BOUNDS.copy(),
        "potential_bounds": list(POTENTIAL_BOUNDS),
        "time_grid_s": TIME_GRID.copy(),
        "step_cost": STEP_COST,
        "budget_units": BUDGET_UNITS,
        "noise_note": "Gaussian noise scales with the largest transient current of each step",
        "refusal_note": (
            "transport outside the six families (for example fractional-diffusion "
            "t^-1/3 decay) and superposed linear baseline drift are not expressible "
            "by any family and must be refused"
        ),
    }


def _true_current(world, potential):
    if world["kind"] == "anomalous":
        a = world["parameters"][0]
        return a * amplitude_factor(potential) * TIME_GRID ** (-1.0 / 3.0)
    values = current_law(world["family"], world["parameters"], potential, TIME_GRID)
    if world["kind"] == "drift":
        values = values + 0.08 * world["drift_strength"] * TIME_GRID
    return values


class _Potentiostat:
    """Charged interface: potential steps return current transients."""

    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def step(self, potential):
        try:
            value = float(potential)
            if not math.isfinite(value) or not POTENTIAL_BOUNDS[0] <= value <= POTENTIAL_BOUNDS[1]:
                self.violated = True
                raise ValueError("potential outside allowed bounds")
            if self.used + STEP_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("step budget exceeded")
            self.used += STEP_COST
            self.calls += 1
            rng = np.random.default_rng(
                self.world["seed"] + int(value * 1e6) + 131 * self.calls)
            clean = _true_current(self.world, value)
            sigma = self.world["noise"] * float(np.abs(clean).max()) + 0.003
            observed = clean + rng.normal(0.0, sigma, clean.shape)
            return {"potential": value, "time_s": TIME_GRID.copy(),
                    "current": observed, "noise_std": sigma,
                    "budget_cost": STEP_COST}
        except Exception:
            self.violated = True
            raise


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    probabilities = submission.get("family_probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(FAMILIES):
        raise ValueError("family_probabilities must cover exactly the six families")
    probs = np.asarray([probabilities[name] for name in FAMILIES], dtype=float)
    if np.any(~np.isfinite(probs)) or np.any(probs < 0.0) or \
            not np.isclose(probs.sum(), 1.0, atol=1e-6):
        raise ValueError("family probabilities must be nonnegative and sum to one")
    if bool(abstain):
        if submission.get("parameters") is not None:
            raise ValueError("abstention requires empty parameters")
        return probs, None, confidence, True
    parameters = np.asarray(submission.get("parameters"), dtype=float).reshape(-1)
    if parameters.shape != (3,) or np.any(~np.isfinite(parameters)):
        raise ValueError("parameters must be a finite length-3 row")
    # Only the slots the claimed family actually uses are bounded; inactive padding
    # entries are free so two-parameter families remain expressible.
    active = _active_count(FAMILIES[int(np.argmax(probs))])
    if np.any(parameters[:active] < PARAMETER_BOUNDS[:active, 0] - 1e-9) or \
            np.any(parameters[:active] > PARAMETER_BOUNDS[:active, 1] + 1e-9):
        raise ValueError("active parameters outside public bounds")
    return probs, parameters, confidence, False


def _active_count(family):
    return {"cottrell": 1, "bounded": 2, "catalytic": 2, "kinetic": 2,
            "adsorption": 2, "surface": 3}[family]


def _parameter_score(family, proposed, truth):
    active = _active_count(family)
    span = PARAMETER_BOUNDS[:active, 1] - PARAMETER_BOUNDS[:active, 0]
    error = (proposed[:active] - np.asarray(truth, dtype=float)[:active]) / span
    return float(math.exp(-6.0 * math.sqrt(float(np.mean(error ** 2)))))


def _prediction_score(world, family, parameters):
    predicted = current_law(family, parameters, SEALED_POTENTIAL, SEALED_TIME)
    truth = _sealed_truth(world)
    scale = float(np.abs(truth).max())
    error = float(np.abs(predicted - truth).max())
    return float(math.exp(-4.0 * error / max(scale, 1e-9)))


def _sealed_truth(world):
    if world["kind"] == "anomalous":
        a = world["parameters"][0]
        return a * amplitude_factor(SEALED_POTENTIAL) * SEALED_TIME ** (-1.0 / 3.0)
    return current_law(world["family"], world["parameters"], SEALED_POTENTIAL,
                       SEALED_TIME)


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "intrinsic_mechanism_score": 0.0,
            "evidence_efficiency_score": 0.0, "class_probability": 0.0,
            "parameter_score": 0.0, "prediction_score": 0.0,
            "false_discovery": False, "correct_refusal": False,
            "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    instrument = _Potentiostat(world)
    try:
        submission = candidate(problem_statement(world), instrument.step,
                               BUDGET_UNITS)
        probs, parameters, confidence, abstain = _validate(submission)
        if instrument.violated:
            raise ValueError("potentiostat contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            truth_index = FAMILIES.index(world["family"])
            class_probability = float(probs[truth_index])
            parameter_score = _parameter_score(world["family"], parameters, world["parameters"])
            chosen = FAMILIES[int(np.argmax(probs))]
            prediction_score = _prediction_score(world, chosen, parameters)
            mechanism = float((max(class_probability, 1e-9) * max(parameter_score, 1e-9)
                               * max(prediction_score, 1e-9)) ** (1.0 / 3.0))
        elif supported:
            class_probability = parameter_score = prediction_score = mechanism = 0.0
        else:
            correct = bool(abstain)
            class_probability = parameter_score = prediction_score = mechanism = \
                1.0 if correct else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        evidence_efficiency = 1.0 - MAX_EVIDENCE_COST_PENALTY * (
            instrument.used / BUDGET_UNITS)
        scored_mechanism = mechanism * evidence_efficiency if supported else mechanism
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": scored_mechanism,
                    "intrinsic_mechanism_score": mechanism,
                    "evidence_efficiency_score": evidence_efficiency,
                    "class_probability": class_probability,
                    "parameter_score": parameter_score,
                    "prediction_score": prediction_score,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": instrument.used})
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
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "evidence_efficiency": float(np.mean([r["evidence_efficiency_score"] for r in rows])),
        "class_probability": float(np.mean([r["class_probability"] for r in supported])) if supported else 0.0,
        "parameter_score": float(np.mean([r["parameter_score"] for r in supported])) if supported else 0.0,
        "prediction_score": float(np.mean([r["prediction_score"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(identify_current_law):
    development = [_evaluate_world(identify_current_law, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(identify_current_law, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_evidence_efficiency_score": dev["evidence_efficiency"],
        "development_class_probability": dev["class_probability"],
        "development_parameter_score": dev["parameter_score"],
        "development_prediction_score": dev["prediction_score"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_evidence_efficiency_score": hold["evidence_efficiency"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }
