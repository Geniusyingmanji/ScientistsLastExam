"""Trusted active laboratory for sparse controlled dynamical-law discovery."""

from __future__ import annotations

import hashlib
import math

import numpy as np


N_STATES = 2
TERM_NAMES = (
    "1", "x", "y", "u", "x^2", "x*y", "y^2", "x^3", "x^2*y",
    "x*y^2", "y^3", "x*u", "y*u",
)
N_TERMS = len(TERM_NAMES)
DT = 0.04
BUDGET_UNITS = 24
MIN_STEPS = 8
MAX_STEPS = 64
STEPS_PER_UNIT = 16

# (seed, template, observation noise, world kind)
DEVELOPMENT_SPECS = (
    (31013, 0, 0.0030, "in_library"),
    (31019, 1, 0.0030, "in_library"),
    (31033, 2, 0.0035, "in_library"),
    (31039, 3, 0.0035, "in_library"),
    (31051, 4, 0.0040, "in_library"),
    (31069, 0, 0.0030, "null"),
    (31081, 0, 0.0035, "misspecified"),
)
VALIDATION_SPECS = (
    (41011, 4, 0.0060, "in_library"),
    (41017, 2, 0.0065, "in_library"),
    (41023, 1, 0.0070, "in_library"),
    (41039, 3, 0.0075, "in_library"),
    (41047, 0, 0.0060, "null"),
    (41051, 0, 0.0070, "misspecified"),
)

CONFIRMATION_CONTEXT_SCHEMA_VERSION = 1
CONFIRMATION_GENERATOR = "active_law_fresh_v1"
CONFIRMATION_WORLD_COUNT = 7
_STATIC_WORLD_SEEDS = {
    int(spec[0]) for spec in DEVELOPMENT_SPECS + VALIDATION_SPECS
}


def _library(state, control):
    x, y = np.asarray(state, dtype=float)
    u = float(control)
    return np.array([
        1.0, x, y, u, x * x, x * y, y * y, x**3, x * x * y,
        x * y * y, y**3, x * u, y * u,
    ], dtype=float)


def _make_coefficients(seed, template):
    rng = np.random.default_rng(int(seed))
    coefficients = np.zeros((N_TERMS, N_STATES), dtype=float)
    if template == 0:  # damped Duffing oscillator
        coefficients[2, 0] = 1.0
        coefficients[1, 1] = -1.00
        coefficients[2, 1] = -0.28
        coefficients[3, 1] = 0.72
        coefficients[7, 1] = -0.20
    elif template == 1:  # controlled Van der Pol regime
        coefficients[2, 0] = 1.0
        coefficients[1, 1] = -1.00
        coefficients[2, 1] = 0.38
        coefficients[3, 1] = 0.60
        coefficients[8, 1] = -0.38
    elif template == 2:  # cross-coupled stable cubic system
        coefficients[1, 0] = -0.58
        coefficients[2, 0] = 0.82
        coefficients[3, 0] = 0.48
        coefficients[5, 0] = 0.10
        coefficients[7, 0] = -0.13
        coefficients[1, 1] = -0.76
        coefficients[2, 1] = -0.67
        coefficients[3, 1] = -0.31
        coefficients[10, 1] = -0.11
    elif template == 3:  # asymmetric quadratic response
        coefficients[1, 0] = -0.73
        coefficients[3, 0] = 0.78
        coefficients[5, 0] = -0.24
        coefficients[2, 1] = -0.91
        coefficients[3, 1] = 0.42
        coefficients[4, 1] = 0.27
        coefficients[7, 1] = -0.12
    elif template == 4:  # state-dependent actuation
        coefficients[1, 0] = -0.52
        coefficients[2, 0] = 0.51
        coefficients[3, 0] = 0.38
        coefficients[7, 0] = -0.14
        coefficients[11, 0] = 0.24
        coefficients[1, 1] = -0.43
        coefficients[2, 1] = -0.79
        coefficients[3, 1] = 0.66
        coefficients[10, 1] = -0.12
        coefficients[12, 1] = -0.19
    else:
        raise ValueError("unknown world template")
    active = np.abs(coefficients) > 0.0
    coefficients[active] *= rng.uniform(0.84, 1.16, size=int(np.sum(active)))
    return coefficients


def _world(spec):
    seed, template, noise, kind = spec
    coefficients = (
        np.zeros((N_TERMS, N_STATES), dtype=float)
        if kind == "null" else _make_coefficients(seed, template)
    )
    return {
        "seed": int(seed),
        "template": int(template),
        "noise": float(noise),
        "kind": str(kind),
        "coefficients": coefficients,
    }


def _validate_confirmation_context(context):
    required = {
        "schema_version", "purpose", "task_id", "generator", "panel_id",
        "master_seed", "world_count",
    }
    if not isinstance(context, dict) or set(context) != required:
        raise ValueError("invalid ActiveLaw confirmation context fields")
    if context["schema_version"] != CONFIRMATION_CONTEXT_SCHEMA_VERSION:
        raise ValueError("unsupported ActiveLaw confirmation context schema")
    if context["purpose"] != "fresh_confirmation":
        raise ValueError("invalid ActiveLaw confirmation purpose")
    if context["task_id"] != "DynamicalSystems/ActiveLawDiscovery":
        raise ValueError("ActiveLaw confirmation task mismatch")
    if context["generator"] != CONFIRMATION_GENERATOR:
        raise ValueError("ActiveLaw confirmation generator mismatch")
    panel_id = context["panel_id"]
    if (
        not isinstance(panel_id, str)
        or not 1 <= len(panel_id) <= 64
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
               for character in panel_id)
    ):
        raise ValueError("invalid ActiveLaw confirmation panel_id")
    seed = context["master_seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63:
        raise ValueError("invalid ActiveLaw confirmation master_seed")
    if context["world_count"] != CONFIRMATION_WORLD_COUNT:
        raise ValueError("ActiveLaw confirmation world_count mismatch")
    return panel_id, int(seed)


def _confirmation_specs(context):
    """Generate a balanced, answer-disjoint procedural confirmation panel."""
    _, master_seed = _validate_confirmation_context(context)
    rng = np.random.default_rng(np.random.SeedSequence([
        master_seed & 0xFFFFFFFF,
        (master_seed >> 32) & 0xFFFFFFFF,
        0xA17E1A9,
    ]))
    kinds = np.asarray(
        ["in_library"] * 5 + ["null", "misspecified"], dtype=object
    )[rng.permutation(CONFIRMATION_WORLD_COUNT)]
    in_library_templates = iter(int(value) for value in rng.permutation(5))
    used_seeds = set(_STATIC_WORLD_SEEDS)
    specs = []
    for kind_value in kinds:
        kind = str(kind_value)
        if kind == "in_library":
            template = next(in_library_templates)
        elif kind == "misspecified":
            template = int(rng.integers(0, 5))
        else:
            template = 0
        while True:
            world_seed = int(rng.integers(10_000_000, 2_147_000_000))
            if world_seed not in used_seeds:
                used_seeds.add(world_seed)
                break
        noise = int(rng.integers(40, 81)) * 1.0e-4
        specs.append((world_seed, template, noise, kind))
    return tuple(specs)


def _derivative(world, state, control):
    value = _library(state, control) @ world["coefficients"]
    if world["kind"] == "misspecified":
        x, y = np.asarray(state, dtype=float)
        value = value.copy()
        value[0] += 0.36 * np.sin(2.7 * y)
        value[1] += 0.58 * np.sin(3.1 * x) / (1.0 + 0.35 * x * x)
    return np.asarray(value, dtype=float)


def _rk4_step(world, state, control, dt=DT):
    state = np.asarray(state, dtype=float)
    k1 = _derivative(world, state, control)
    k2 = _derivative(world, state + 0.5 * dt * k1, control)
    k3 = _derivative(world, state + 0.5 * dt * k2, control)
    k4 = _derivative(world, state + dt * k3, control)
    output = state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if np.any(~np.isfinite(output)) or np.max(np.abs(output)) > 25.0:
        raise RuntimeError("experiment left the stable laboratory envelope")
    return output


def _simulate(world, initial_state, controls):
    controls = np.asarray(controls, dtype=float)
    states = np.empty((len(controls) + 1, N_STATES), dtype=float)
    states[0] = np.asarray(initial_state, dtype=float)
    for index, control in enumerate(controls):
        states[index + 1] = _rk4_step(world, states[index], float(control))
    return states


def _query_seed(world_seed, call_index, initial_state, controls):
    payload = np.concatenate((
        np.asarray(initial_state, dtype="<f8").ravel(),
        np.asarray(controls, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    payload_words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in payload_words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def experiment(self, initial_state, controls, n_steps):
        if isinstance(n_steps, bool):
            raise ValueError("n_steps must be an integer")
        steps = int(n_steps)
        if steps != n_steps or not MIN_STEPS <= steps <= MAX_STEPS:
            raise ValueError("n_steps outside the allowed range")
        initial = np.asarray(initial_state, dtype=float)
        if initial.shape != (N_STATES,) or np.any(~np.isfinite(initial)):
            raise ValueError("initial_state must contain two finite values")
        if np.any(initial < -2.0) or np.any(initial > 2.0):
            raise ValueError("initial_state outside [-2,2]")
        control_array = np.asarray(controls, dtype=float)
        if control_array.ndim == 0:
            control_array = np.full(steps, float(control_array), dtype=float)
        else:
            control_array = control_array.ravel()
        if control_array.shape != (steps,) or np.any(~np.isfinite(control_array)):
            raise ValueError("controls must be one finite scalar or an n_steps array")
        if np.any(control_array < -1.5) or np.any(control_array > 1.5):
            raise ValueError("controls outside [-1.5,1.5]")
        cost = int(math.ceil(steps / STEPS_PER_UNIT))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("experimental budget exceeded")
        self.used += cost
        self.calls += 1
        states = _simulate(self.world, initial, control_array)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, initial, control_array
        ))
        observed = states + rng.normal(
            scale=self.world["noise"], size=states.shape
        )
        return {
            "time": np.arange(steps + 1, dtype=float) * DT,
            "states": observed,
            "controls": control_array.copy(),
        }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dict")
    coefficients = np.asarray(submission.get("coefficients"), dtype=float)
    expected = (N_TERMS, N_STATES)
    if coefficients.shape != expected or np.any(~np.isfinite(coefficients)):
        raise ValueError("coefficients must be a finite (n_terms,n_states) matrix")
    coefficients = np.clip(coefficients, -4.0, 4.0)
    support_value = submission.get("support")
    if support_value is None:
        support = np.abs(coefficients) >= 0.05
    else:
        support_array = np.asarray(support_value, dtype=float)
        if support_array.shape != expected or np.any(~np.isfinite(support_array)):
            raise ValueError("support must be a finite (n_terms,n_states) matrix")
        support = support_array >= 0.5
    coefficients = np.where(support, coefficients, 0.0)
    confidence = float(submission.get("confidence", 0.5))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    abstain = bool(submission.get("abstain", False))
    if abstain:
        coefficients = np.zeros(expected, dtype=float)
        support = np.zeros(expected, dtype=bool)
    return coefficients, support.astype(bool), confidence, abstain


def _mechanism_metrics(world, estimate, predicted_support, abstain):
    kind = world["kind"]
    if kind in {"null", "misspecified"}:
        correct = bool(abstain and not np.any(predicted_support))
        return {
            "edge_f1": 1.0 if correct else 0.0,
            "coefficient_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_abstention": correct,
            "false_discovery": not correct,
        }
    truth = world["coefficients"]
    true_support = np.abs(truth) > 1e-12
    if abstain:
        predicted_support = np.zeros_like(true_support)
        estimate = np.zeros_like(truth)
    tp = int(np.sum(true_support & predicted_support))
    fp = int(np.sum(~true_support & predicted_support))
    fn = int(np.sum(true_support & ~predicted_support))
    if tp == 0:
        edge_f1 = 0.0
    else:
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        edge_f1 = 2.0 * precision * recall / (precision + recall)
    relative_error = np.abs(estimate[true_support] - truth[true_support]) / np.maximum(
        np.abs(truth[true_support]), 0.20
    )
    coefficient_credit = np.clip(1.0 - relative_error, 0.0, 1.0)
    # A missed true term must receive zero coefficient credit even when its magnitude is below
    # the numerical error floor.  Otherwise always-abstain would score above its normalization
    # baseline merely because a small omitted coefficient is close to zero.
    coefficient_credit = np.where(
        predicted_support[true_support], coefficient_credit, 0.0
    )
    coefficient_score = float(np.mean(coefficient_credit))
    mechanism_score = 0.55 * edge_f1 + 0.45 * coefficient_score
    return {
        "edge_f1": float(edge_f1),
        "coefficient_score": coefficient_score,
        "mechanism_score": float(mechanism_score),
        "correct_abstention": False,
        "false_discovery": False,
    }


def _estimated_step(coefficients, state, control):
    def derivative(value):
        return _library(value, control) @ coefficients
    k1 = derivative(state)
    k2 = derivative(state + 0.5 * DT * k1)
    k3 = derivative(state + 0.5 * DT * k2)
    k4 = derivative(state + DT * k3)
    output = state + DT * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
    if np.any(~np.isfinite(output)) or np.max(np.abs(output)) > 50.0:
        raise RuntimeError("submitted law is unstable")
    return output


def _prediction_score(world, coefficients):
    if world["kind"] not in {"in_library", "null"}:
        return None
    rng = np.random.default_rng(world["seed"] + 900001)
    squared_errors = []
    baseline_errors = []
    for _ in range(5):
        initial = rng.uniform(-1.8, 1.8, size=N_STATES)
        controls = np.repeat(rng.uniform(-1.3, 1.3, size=4), 12)
        truth = _simulate(world, initial, controls)
        predicted = np.empty_like(truth)
        predicted[0] = initial
        try:
            for index, control in enumerate(controls):
                predicted[index + 1] = _estimated_step(
                    coefficients, predicted[index], float(control)
                )
        except Exception:
            return 0.0
        zero = np.repeat(initial[None, :], len(controls) + 1, axis=0)
        squared_errors.append(float(np.mean((predicted - truth) ** 2)))
        baseline_errors.append(float(np.mean((zero - truth) ** 2)))
    rmse = math.sqrt(float(np.mean(squared_errors)))
    baseline_rmse = max(0.05, math.sqrt(float(np.mean(baseline_errors))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _evaluate_world(discover_law, spec, split, index):
    world = _world(spec)
    laboratory = _Laboratory(world)
    try:
        submission = discover_law(
            N_STATES, TERM_NAMES, laboratory.experiment, BUDGET_UNITS
        )
        coefficients, support, confidence, abstain = _validate_submission(submission)
        if laboratory.violated:
            raise RuntimeError("experimental budget exceeded")
        mechanism = _mechanism_metrics(world, coefficients, support, abstain)
        prediction = _prediction_score(world, coefficients)
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "edge_f1": round(mechanism["edge_f1"], 6),
            "coefficient_score": round(mechanism["coefficient_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "rollout_prediction_score": (
                None if prediction is None else round(prediction, 6)
            ),
            "correct_abstention": mechanism["correct_abstention"],
            "false_discovery": mechanism["false_discovery"],
            "abstained": abstain,
            "confidence": round(confidence, 6),
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }
    except Exception as exc:
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "mechanism_score": 0.0,
            "rollout_prediction_score": 0.0,
            "correct_abstention": False,
            "false_discovery": False,
            "experiment_calls": laboratory.calls,
            "experiment_budget_units": laboratory.used,
        }


def _split_metrics(records, exception_count):
    raw_mechanism = float(np.mean([row["mechanism_score"] for row in records]))
    abstention_baseline = exception_count / len(records)
    normalized = float(np.clip(
        (raw_mechanism - abstention_baseline) / (1.0 - abstention_baseline),
        0.0, 1.0,
    ))
    predictions = [
        row["rollout_prediction_score"] for row in records
        if row["kind"] in {"in_library", "null"}
    ]
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw_mechanism,
        "prediction": float(np.mean(predictions)),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "false_discoveries": sum(bool(row["false_discovery"]) for row in records),
        "correct_abstentions": sum(bool(row["correct_abstention"]) for row in records),
    }


def _evaluate_specs(discover_law, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(discover_law, "reset_session"):
            discover_law.reset_session()
        records.append(_evaluate_world(discover_law, spec, split, index))
    return records


def evaluate(discover_law):
    development = _evaluate_specs(
        discover_law, DEVELOPMENT_SPECS, "development"
    )
    validation = _evaluate_specs(
        discover_law, VALIDATION_SPECS, "validation", reset_before_first=True
    )
    dev_exception_count = sum(spec[3] != "in_library" for spec in DEVELOPMENT_SPECS)
    val_exception_count = sum(spec[3] != "in_library" for spec in VALIDATION_SPECS)
    dev = _split_metrics(development, dev_exception_count)
    val = _split_metrics(validation, val_exception_count)
    all_records = development + validation
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] == len(development) else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw_mechanism"],
        "development_prediction_score": dev["prediction"],
        "robustness_score": val["normalized_mechanism"],
        "validation_prediction_score": val["prediction"],
        "development_validation_gap": (
            dev["normalized_mechanism"] - val["normalized_mechanism"]
        ),
        "validation_feasibility_rate": val["valid_count"] / len(validation),
        "development_false_discoveries": dev["false_discoveries"],
        "validation_false_discoveries": val["false_discoveries"],
        "development_correct_abstentions": dev["correct_abstentions"],
        "validation_correct_abstentions": val["correct_abstentions"],
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in all_records
        ])),
        "mean_experiment_budget_units": float(np.mean([
            row["experiment_budget_units"] for row in all_records
        ])),
        "per_world": all_records,
    }


def evaluate_with_context(discover_law, context):
    """Evaluate a frozen method once on a fresh trusted confirmation panel."""
    panel_id, _ = _validate_confirmation_context(context)
    specs = _confirmation_specs(context)
    records = _evaluate_specs(discover_law, specs, "confirmation")
    exception_count = sum(spec[3] != "in_library" for spec in specs)
    metrics = _split_metrics(records, exception_count)
    valid = metrics["valid_count"] == len(records)
    return {
        "combined_score": metrics["normalized_mechanism"] if valid else 0.0,
        "raw_score": metrics["normalized_mechanism"] if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": metrics["valid_count"] / len(records),
        "confirmation_panel_id": panel_id,
        "confirmation_generator": CONFIRMATION_GENERATOR,
        "confirmation_world_count": len(records),
        "confirmation_normalized_mechanism_score": metrics["normalized_mechanism"],
        "confirmation_raw_mechanism_score": metrics["raw_mechanism"],
        "confirmation_prediction_score": metrics["prediction"],
        "confirmation_false_discoveries": metrics["false_discoveries"],
        "confirmation_correct_abstentions": metrics["correct_abstentions"],
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in records
        ])),
        "mean_experiment_budget_units": float(np.mean([
            row["experiment_budget_units"] for row in records
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": metrics["valid_count"] / len(records),
        "per_confirmation_world": records,
    }
