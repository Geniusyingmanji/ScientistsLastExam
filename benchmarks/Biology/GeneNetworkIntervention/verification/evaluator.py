"""Trusted active laboratory for dynamic gene-network intervention discovery.

The public model is a four-gene, bounded nonlinear regulatory system.  A
candidate chooses CRISPRi/a-like perturbation time courses, estimates a signed
network and kinetic parameters, and proposes a sparse intervention that
increases a protected phenotype readout.  Null and latent-regulator worlds
require abstention.  Hidden prediction and intervention-transfer panels are
kept separate from the development selection score.

This is a synthetic systems-biology benchmark.  It does not model a named cell
line and its results are not experimental evidence about a biological network.
"""

from __future__ import annotations

import hashlib
import itertools
import math

import numpy as np


GENE_NETWORK_V1 = True

GENE_NAMES = ("regulator_a", "regulator_b", "regulator_c", "phenotype")
N_GENES = len(GENE_NAMES)
ACTIONABLE_INDICES = (0, 1, 2)
READOUT_INDEX = 3

DT = 0.10
MIN_STEPS = 20
MAX_STEPS = 80
STEPS_PER_BUDGET_UNIT = 20
EXPERIMENT_BUDGET_UNITS = 24
MAX_EXPERIMENT_TARGETS = 2
MAX_PLAN_TARGETS = 2
INTERVENTION_BOUND = 2.0

WEIGHT_BOUNDS = (-2.8, 2.8)
BIAS_BOUNDS = (-1.2, 0.6)
DECAY_BOUNDS = (0.35, 1.10)
WEIGHT_SUPPORT_THRESHOLD = 0.12

PHENOTYPE_OBJECTIVE = {
    "readout_index": READOUT_INDEX,
    "actionable_indices": ACTIONABLE_INDICES,
    "intervention_bounds": (-INTERVENTION_BOUND, INTERVENTION_BOUND),
    "max_intervention_targets": MAX_PLAN_TARGETS,
    "weight_bounds": WEIGHT_BOUNDS,
    "bias_bounds": BIAS_BOUNDS,
    "decay_bounds": DECAY_BOUNDS,
    "objective": "increase protected phenotype readout with regulator-disruption and dose penalties",
    "regulator_disruption_penalty": 0.30,
    "dose_penalty": 0.025,
}

# seed, topology template, world kind, expression-noise standard deviation
DEVELOPMENT_SPECS = (
    (73101, 0, "in_library", 0.0040),
    (73103, 1, "in_library", 0.0040),
    (73109, 2, "in_library", 0.0045),
    (73117, 3, "in_library", 0.0045),
    (73121, 0, "null", 0.0040),
    (73133, 4, "hidden_regulator", 0.0045),
)
HELDOUT_SPECS = (
    (83101, 4, "in_library", 0.0060),
    (83107, 5, "in_library", 0.0065),
    (83117, 2, "in_library", 0.0070),
    (83123, 0, "null", 0.0060),
    (83137, 1, "hidden_regulator", 0.0070),
)


def _sigmoid(value):
    value = np.clip(np.asarray(value, dtype=float), -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-value))


def _template_weights(template):
    """Return a sparse signed source-by-target regulatory topology."""
    weights = np.zeros((N_GENES, N_GENES), dtype=float)
    edges = {
        0: ((0, 1, 1.45), (0, 2, -1.15), (1, 3, 1.80),
            (2, 3, -1.35), (3, 1, -0.70)),
        1: ((0, 3, -1.55), (1, 0, 1.20), (1, 2, -0.90),
            (2, 3, 1.75), (3, 1, -0.65)),
        2: ((0, 1, -1.30), (0, 2, 0.95), (1, 3, -1.75),
            (2, 3, 1.50), (3, 0, -0.75)),
        3: ((0, 2, -1.50), (0, 3, 0.65), (1, 3, 1.45),
            (2, 3, -1.70), (3, 1, -0.65)),
        4: ((0, 1, 1.35), (0, 3, -0.85), (1, 2, 1.25),
            (2, 3, 1.70), (3, 0, -0.60)),
        5: ((0, 3, 1.55), (1, 3, -1.45), (2, 1, 1.10),
            (3, 2, -0.75), (0, 2, 0.65)),
    }
    if int(template) not in edges:
        raise ValueError("unknown topology template")
    for source, target, value in edges[int(template)]:
        weights[source, target] = value
    return weights


def _world(spec):
    seed, template, kind, noise = spec
    seed = int(seed)
    kind = str(kind)
    rng = np.random.default_rng(seed)
    if kind == "null":
        weights = np.zeros((N_GENES, N_GENES), dtype=float)
    else:
        weights = _template_weights(template)
        active = np.abs(weights) > 0.0
        weights[active] *= rng.uniform(0.86, 1.14, size=int(np.sum(active)))
    biases = rng.uniform(-0.70, 0.12, size=N_GENES)
    # Keep the unperturbed phenotype away from saturation so indirect control is useful.
    biases[READOUT_INDEX] = rng.uniform(-0.82, -0.38)
    decays = rng.uniform(0.48, 0.92, size=N_GENES)
    transfer_weight_scale = rng.uniform(0.88, 1.12, size=N_GENES)
    transfer_decay_scale = rng.uniform(0.86, 1.14, size=N_GENES)
    transfer_efficiency = rng.uniform(0.72, 1.18, size=N_GENES)
    world = {
        "seed": seed,
        "template": int(template),
        "kind": kind,
        "noise": float(noise),
        "weights": weights,
        "biases": biases,
        "decays": decays,
        "transfer_weight_scale": transfer_weight_scale,
        "transfer_decay_scale": transfer_decay_scale,
        "transfer_efficiency": transfer_efficiency,
    }
    if kind == "hidden_regulator":
        # The latent regulator has both incoming and outgoing connections.  Its effect is
        # deliberately slow and also responds to perturbations on observed regulators.  The
        # resulting delayed cross-target response cannot be represented by the public
        # memoryless four-gene family, but trajectories remain bounded and smooth.
        world.update({
            "hidden_bias": float(rng.uniform(-0.45, 0.15)),
            "hidden_decay": float(rng.uniform(0.18, 0.22)),
            "observed_to_hidden": rng.choice((-1.0, 1.0), size=N_GENES)
            * rng.uniform(0.35, 0.75, size=N_GENES),
            "intervention_to_hidden": np.asarray((6.00, -4.80, 5.40, -3.60))
            * rng.uniform(0.90, 1.10, size=N_GENES),
            "hidden_to_observed": np.asarray((0.0, 6.60, -5.80, 7.20))
            * rng.uniform(0.90, 1.10, size=N_GENES),
        })
    return world


def _effective_parameters(world, shifted):
    weights = np.asarray(world["weights"], dtype=float)
    decays = np.asarray(world["decays"], dtype=float)
    efficiency = np.ones(N_GENES, dtype=float)
    if shifted:
        weights = weights * np.asarray(world["transfer_weight_scale"])[None, :]
        decays = decays * np.asarray(world["transfer_decay_scale"])
        efficiency = np.asarray(world["transfer_efficiency"], dtype=float)
    return weights, decays, efficiency


def _derivative(world, state, intervention, shifted=False):
    state = np.asarray(state, dtype=float)
    observed = state[:N_GENES]
    intervention = np.asarray(intervention, dtype=float)
    weights, decays, efficiency = _effective_parameters(world, shifted)
    regulatory_input = (
        np.asarray(world["biases"], dtype=float)
        + (2.0 * observed - 1.0) @ weights
        + efficiency * intervention
    )
    if world["kind"] == "hidden_regulator":
        latent = float(state[N_GENES])
        regulatory_input = regulatory_input + (
            np.asarray(world["hidden_to_observed"]) * (2.0 * latent - 1.0)
        )
    observed_derivative = decays * (_sigmoid(regulatory_input) - observed)
    if world["kind"] != "hidden_regulator":
        return observed_derivative
    latent_input = (
        float(world["hidden_bias"])
        + float((2.0 * observed - 1.0) @ np.asarray(world["observed_to_hidden"]))
        + float(intervention @ np.asarray(world["intervention_to_hidden"]))
    )
    latent_derivative = float(world["hidden_decay"]) * (
        float(_sigmoid(latent_input)) - float(state[N_GENES])
    )
    return np.concatenate((observed_derivative, (latent_derivative,)))


def _rk4_step(world, state, intervention, shifted=False):
    state = np.asarray(state, dtype=float)
    intervention = np.asarray(intervention, dtype=float)
    k1 = _derivative(world, state, intervention, shifted)
    k2 = _derivative(world, state + 0.5 * DT * k1, intervention, shifted)
    k3 = _derivative(world, state + 0.5 * DT * k2, intervention, shifted)
    k4 = _derivative(world, state + DT * k3, intervention, shifted)
    output = state + DT * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if np.any(~np.isfinite(output)) or np.any(output < -0.02) or np.any(output > 1.02):
        raise RuntimeError("gene-expression trajectory left the bounded laboratory envelope")
    return np.clip(output, 0.0, 1.0)


def _steady_state(world, shifted=False):
    size = N_GENES + (1 if world["kind"] == "hidden_regulator" else 0)
    state = np.full(size, 0.5, dtype=float)
    zero = np.zeros(N_GENES, dtype=float)
    for _ in range(800):
        updated = _rk4_step(world, state, zero, shifted)
        if np.max(np.abs(updated - state)) < 1.0e-11:
            state = updated
            break
        state = updated
    return state


def _simulate(world, interventions, initial_state=None, shifted=False):
    controls = np.asarray(interventions, dtype=float)
    if controls.ndim != 2 or controls.shape[1] != N_GENES:
        raise ValueError("interventions must have shape (n_steps,n_genes)")
    state = (
        _steady_state(world, shifted) if initial_state is None
        else np.asarray(initial_state, dtype=float).copy()
    )
    expected = N_GENES + (1 if world["kind"] == "hidden_regulator" else 0)
    if state.shape != (expected,):
        raise ValueError("invalid initial state")
    states = np.empty((len(controls) + 1, expected), dtype=float)
    states[0] = state
    for index, control in enumerate(controls):
        state = _rk4_step(world, state, control, shifted)
        states[index + 1] = state
    return states[:, :N_GENES]


def _query_seed(world_seed, call_index, interventions):
    payload = np.asarray(interventions, dtype="<f8").tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4")
    sequence = np.random.SeedSequence(
        [int(world_seed), int(call_index), *[int(value) for value in words]]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _Laboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.failure = None

    def _fail(self, code, message):
        if self.failure is None:
            self.failure = str(code)
        raise ValueError(str(message))

    def perturb(self, intervention, n_steps):
        if isinstance(n_steps, (bool, np.bool_)):
            self._fail("invalid_experiment", "n_steps must be an integer")
        try:
            steps = int(n_steps)
        except Exception:
            self._fail("invalid_experiment", "n_steps must be an integer")
        if steps != n_steps or not MIN_STEPS <= steps <= MAX_STEPS:
            self._fail("invalid_experiment", "n_steps outside the allowed range")
        try:
            raw_controls = np.asarray(intervention)
            if np.issubdtype(raw_controls.dtype, np.bool_) or np.iscomplexobj(raw_controls):
                self._fail(
                    "invalid_experiment",
                    "intervention must be real-valued and non-boolean",
                )
            controls = np.asarray(intervention, dtype=float)
        except Exception:
            self._fail("invalid_experiment", "intervention must be numeric")
        if controls.shape == (N_GENES,):
            controls = np.repeat(controls[None, :], steps, axis=0)
        if controls.shape != (steps, N_GENES) or np.any(~np.isfinite(controls)):
            self._fail(
                "invalid_experiment",
                "intervention must be a finite gene vector or (n_steps,n_genes) matrix",
            )
        if np.any(np.abs(controls) > INTERVENTION_BOUND + 1.0e-12):
            self._fail("invalid_experiment", "intervention outside CRISPRi/a bounds")
        active_by_step = np.sum(np.abs(controls) > 1.0e-10, axis=1)
        active_genes = np.any(np.abs(controls) > 1.0e-10, axis=0)
        if active_genes[READOUT_INDEX]:
            self._fail(
                "invalid_experiment", "the protected phenotype gene cannot be perturbed"
            )
        if np.any(active_by_step > MAX_EXPERIMENT_TARGETS) or int(np.sum(active_genes)) > MAX_EXPERIMENT_TARGETS:
            self._fail("invalid_experiment", "too many perturbed genes")
        cost = int(math.ceil(steps / STEPS_PER_BUDGET_UNIT)) + int(np.sum(active_genes))
        if self.used + cost > EXPERIMENT_BUDGET_UNITS:
            self._fail("budget_exceeded", "experimental budget exceeded")
        self.used += cost
        self.calls += 1
        states = _simulate(self.world, controls, shifted=False)
        rng = np.random.default_rng(
            _query_seed(self.world["seed"], self.calls, controls)
        )
        observed = states + rng.normal(
            scale=float(self.world["noise"]), size=states.shape
        )
        return {
            "time": np.arange(steps + 1, dtype=float) * DT,
            "expression": np.clip(observed, 0.0, 1.0),
            "intervention": controls.copy(),
        }


def _strict_bool(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(name + " must be boolean")
    return bool(value)


def _finite_real_array(value, name):
    raw = np.asarray(value)
    if np.issubdtype(raw.dtype, np.bool_) or np.iscomplexobj(raw):
        raise ValueError(name + " must be real-valued and non-boolean")
    try:
        array = np.asarray(value, dtype=float)
    except Exception as exc:
        raise ValueError(name + " must be numeric") from exc
    if np.any(~np.isfinite(array)):
        raise ValueError(name + " must be finite")
    return array


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dict")
    weights = _finite_real_array(submission.get("weights"), "weights")
    biases = _finite_real_array(submission.get("biases"), "biases")
    decays = _finite_real_array(submission.get("decay_rates"), "decay_rates")
    plan = _finite_real_array(submission.get("intervention"), "intervention")
    if weights.shape != (N_GENES, N_GENES):
        raise ValueError("weights must be a finite (n_genes,n_genes) matrix")
    if biases.shape != (N_GENES,):
        raise ValueError("biases must contain one finite value per gene")
    if decays.shape != (N_GENES,):
        raise ValueError("decay_rates must contain one finite value per gene")
    if plan.shape != (N_GENES,):
        raise ValueError("intervention must contain one finite value per gene")
    if np.any(weights < WEIGHT_BOUNDS[0]) or np.any(weights > WEIGHT_BOUNDS[1]):
        raise ValueError("weights outside public bounds")
    if np.max(np.abs(np.diag(weights))) > 1.0e-10:
        raise ValueError("self-regulation is outside the public model")
    if np.any(biases < BIAS_BOUNDS[0]) or np.any(biases > BIAS_BOUNDS[1]):
        raise ValueError("biases outside public bounds")
    if np.any(decays < DECAY_BOUNDS[0]) or np.any(decays > DECAY_BOUNDS[1]):
        raise ValueError("decay_rates outside public bounds")
    support_value = submission.get("support")
    if support_value is None:
        support = np.abs(weights) >= WEIGHT_SUPPORT_THRESHOLD
    else:
        support_array = _finite_real_array(support_value, "support")
        if support_array.shape != weights.shape:
            raise ValueError("support must be a finite (n_genes,n_genes) matrix")
        support = support_array >= 0.5
    if np.any(np.diag(support)):
        raise ValueError("support cannot contain self-regulation")
    weights = np.where(support, weights, 0.0)
    if np.any(np.abs(plan) > INTERVENTION_BOUND + 1.0e-12):
        raise ValueError("intervention outside public bounds")
    if abs(float(plan[READOUT_INDEX])) > 1.0e-10:
        raise ValueError("the protected phenotype gene cannot be directly perturbed")
    if int(np.sum(np.abs(plan) > 1.0e-10)) > MAX_PLAN_TARGETS:
        raise ValueError("intervention targets too many genes")
    confidence = float(submission.get("confidence", 0.5))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    abstain = _strict_bool(submission.get("abstain", False), "abstain")
    if abstain:
        weights = np.zeros_like(weights)
        support = np.zeros_like(support, dtype=bool)
        plan = np.zeros_like(plan)
    return weights, support.astype(bool), biases, decays, plan, confidence, abstain


def _mechanism_metrics(world, weights, support, biases, decays, abstain):
    if world["kind"] != "in_library":
        correct = bool(abstain and not np.any(support))
        value = 1.0 if correct else 0.0
        return {
            "signed_edge_f1": value,
            "weight_quality": value,
            "bias_quality": value,
            "decay_quality": value,
            "mechanism_quality": value,
            "correct_refusal": correct,
            "false_discovery": not abstain,
        }
    if abstain:
        return {
            "signed_edge_f1": 0.0,
            "weight_quality": 0.0,
            "bias_quality": 0.0,
            "decay_quality": 0.0,
            "mechanism_quality": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
        }
    truth = np.asarray(world["weights"], dtype=float)
    truth_support = np.abs(truth) > 1.0e-12
    signed_correct = truth_support & support & (np.sign(truth) == np.sign(weights))
    tp = int(np.sum(signed_correct))
    fp = int(np.sum(support)) - tp
    fn = int(np.sum(truth_support)) - tp
    signed_edge_f1 = 0.0 if tp == 0 else 2.0 * tp / (2.0 * tp + fp + fn)
    relative_error = np.abs(weights[truth_support] - truth[truth_support]) / np.maximum(
        np.abs(truth[truth_support]), 0.35
    )
    weight_credit = np.clip(1.0 - relative_error, 0.0, 1.0)
    weight_credit = np.where(signed_correct[truth_support], weight_credit, 0.0)
    weight_quality = float(np.mean(weight_credit))
    bias_scale = BIAS_BOUNDS[1] - BIAS_BOUNDS[0]
    decay_scale = DECAY_BOUNDS[1] - DECAY_BOUNDS[0]
    bias_quality = float(np.mean(np.clip(
        1.0 - np.abs(biases - world["biases"]) / (0.25 * bias_scale), 0.0, 1.0
    )))
    decay_quality = float(np.mean(np.clip(
        1.0 - np.abs(decays - world["decays"]) / (0.25 * decay_scale), 0.0, 1.0
    )))
    mechanism = (
        0.45 * signed_edge_f1 + 0.30 * weight_quality
        + 0.15 * bias_quality + 0.10 * decay_quality
    )
    return {
        "signed_edge_f1": float(signed_edge_f1),
        "weight_quality": weight_quality,
        "bias_quality": bias_quality,
        "decay_quality": decay_quality,
        "mechanism_quality": float(mechanism),
        "correct_refusal": False,
        "false_discovery": False,
    }


def _estimated_derivative(state, intervention, weights, biases, decays):
    regulatory_input = biases + (2.0 * state - 1.0) @ weights + intervention
    return decays * (_sigmoid(regulatory_input) - state)


def _estimated_step(state, intervention, weights, biases, decays):
    k1 = _estimated_derivative(state, intervention, weights, biases, decays)
    k2 = _estimated_derivative(
        state + 0.5 * DT * k1, intervention, weights, biases, decays
    )
    k3 = _estimated_derivative(
        state + 0.5 * DT * k2, intervention, weights, biases, decays
    )
    k4 = _estimated_derivative(
        state + DT * k3, intervention, weights, biases, decays
    )
    output = state + DT * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if np.any(~np.isfinite(output)) or np.any(output < -0.10) or np.any(output > 1.10):
        raise RuntimeError("submitted model is unstable")
    return np.clip(output, 0.0, 1.0)


def _sealed_schedules(seed):
    rng = np.random.default_rng(int(seed) + 190001)
    schedules = []
    for index in range(5):
        controls = np.zeros((64, N_GENES), dtype=float)
        targets = rng.choice(ACTIONABLE_INDICES, size=2, replace=False)
        levels = rng.uniform(-1.75, 1.75, size=(4, 2))
        levels += 0.10 * np.sin(index + np.arange(4))[:, None]
        for block in range(4):
            controls[16 * block:16 * (block + 1), targets] = np.clip(
                levels[block], -INTERVENTION_BOUND, INTERVENTION_BOUND
            )
        schedules.append(controls)
    return schedules


def _prediction_score(world, weights, biases, decays):
    if world["kind"] != "in_library":
        return None
    initial = _steady_state(world, shifted=False)[:N_GENES]
    errors = []
    persistence_errors = []
    for controls in _sealed_schedules(world["seed"]):
        truth = _simulate(world, controls, initial_state=initial, shifted=False)
        predicted = np.empty_like(truth)
        predicted[0] = initial
        try:
            for index, control in enumerate(controls):
                predicted[index + 1] = _estimated_step(
                    predicted[index], control, weights, biases, decays
                )
        except Exception:
            return 0.0
        persistence = np.repeat(initial[None, :], len(truth), axis=0)
        errors.append(float(np.mean((predicted - truth) ** 2)))
        persistence_errors.append(float(np.mean((persistence - truth) ** 2)))
    rmse = math.sqrt(float(np.mean(errors)))
    baseline_rmse = max(0.025, math.sqrt(float(np.mean(persistence_errors))))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def _phenotype_utility(world, plan, shifted=False):
    plan = np.asarray(plan, dtype=float)
    controls = np.repeat(plan[None, :], 80, axis=0)
    baseline = _steady_state(world, shifted=shifted)[:N_GENES]
    trajectory = _simulate(
        world, controls, initial_state=(
            _steady_state(world, shifted=shifted)
        ), shifted=shifted,
    )
    terminal = np.mean(trajectory[-10:], axis=0)
    readout_gain = float(terminal[READOUT_INDEX] - baseline[READOUT_INDEX])
    off_target = float(np.mean(np.abs(
        terminal[list(ACTIONABLE_INDICES)] - baseline[list(ACTIONABLE_INDICES)]
    )))
    dose = float(np.sum(np.abs(plan[list(ACTIONABLE_INDICES)])))
    return readout_gain - PHENOTYPE_OBJECTIVE["regulator_disruption_penalty"] * off_target - PHENOTYPE_OBJECTIVE["dose_penalty"] * dose


def _batch_phenotype_utilities(world, plans, shifted=False):
    """Vectorized equivalent of ``_phenotype_utility`` for normalization plans."""
    plans = np.asarray(plans, dtype=float)
    if plans.ndim != 2 or plans.shape[1] != N_GENES:
        raise ValueError("plans must have shape (n_plans,n_genes)")
    if world["kind"] != "in_library":
        raise ValueError("intervention normalization is defined only in-library")
    weights, decays, efficiency = _effective_parameters(world, shifted)
    baseline = _steady_state(world, shifted=shifted)[:N_GENES]
    states = np.repeat(baseline[None, :], len(plans), axis=0)

    def derivative(values):
        regulatory_input = (
            np.asarray(world["biases"])[None, :]
            + (2.0 * values - 1.0) @ weights
            + efficiency[None, :] * plans
        )
        return decays[None, :] * (_sigmoid(regulatory_input) - values)

    terminal_sum = np.zeros_like(states)
    for step in range(80):
        k1 = derivative(states)
        k2 = derivative(states + 0.5 * DT * k1)
        k3 = derivative(states + 0.5 * DT * k2)
        k4 = derivative(states + DT * k3)
        states = np.clip(
            states + DT * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0,
            0.0, 1.0,
        )
        if step >= 70:
            terminal_sum += states
    terminal = terminal_sum / 10.0
    readout_gain = terminal[:, READOUT_INDEX] - baseline[READOUT_INDEX]
    off_target = np.mean(np.abs(
        terminal[:, list(ACTIONABLE_INDICES)]
        - baseline[None, list(ACTIONABLE_INDICES)]
    ), axis=1)
    dose = np.sum(np.abs(plans[:, list(ACTIONABLE_INDICES)]), axis=1)
    return (
        readout_gain
        - PHENOTYPE_OBJECTIVE["regulator_disruption_penalty"] * off_target
        - PHENOTYPE_OBJECTIVE["dose_penalty"] * dose
    )


def _plan_grid():
    levels = (-2.0, -4.0 / 3.0, -2.0 / 3.0, 2.0 / 3.0, 4.0 / 3.0, 2.0)
    yield np.zeros(N_GENES, dtype=float)
    for size in (1, 2):
        for targets in itertools.combinations(ACTIONABLE_INDICES, size):
            for values in itertools.product(levels, repeat=size):
                plan = np.zeros(N_GENES, dtype=float)
                plan[list(targets)] = values
                yield plan


_PLAN_CACHE = {}


def _reference_plan(world, shifted=False):
    key = (int(world["seed"]), bool(shifted))
    if key not in _PLAN_CACHE:
        plans = np.asarray(list(_plan_grid()), dtype=float)
        values = _batch_phenotype_utilities(world, plans, shifted=shifted)
        best_index = int(np.argmax(values))
        best_plan = plans[best_index].copy()
        best_value = float(values[best_index])
        _PLAN_CACHE[key] = (best_plan, best_value)
    plan, value = _PLAN_CACHE[key]
    return plan.copy(), float(value)


def _decision_score(world, plan, shifted=False):
    if world["kind"] != "in_library":
        return None
    _, best = _reference_plan(world, shifted=shifted)
    if best <= 1.0e-8:
        return 0.0
    value = _phenotype_utility(world, plan, shifted=shifted)
    return float(np.clip(value / best, 0.0, 1.0))


def _invalid_record(split, index, kind, failure_kind, laboratory):
    return {
        "split": str(split),
        "world_index": int(index),
        "kind": str(kind),
        "valid": False,
        "failure_kind": str(failure_kind),
        "mechanism_quality": 0.0,
        "prediction_quality": 0.0,
        "decision_quality": 0.0,
        "transfer_decision_quality": 0.0,
        "joint_quality": 0.0,
        "transfer_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "abstained": False,
        "confidence": 0.0,
        "confidence_score": 0.0,
        "experiment_calls": int(laboratory.calls),
        "experiment_budget_units": int(laboratory.used),
    }


def _evaluate_world(discover_gene_network, spec, split, index):
    world = _world(spec)
    laboratory = _Laboratory(world)
    stage = "candidate_execution"
    try:
        submission = discover_gene_network(
            tuple(GENE_NAMES), laboratory.perturb, dict(PHENOTYPE_OBJECTIVE),
            EXPERIMENT_BUDGET_UNITS,
        )
        if laboratory.failure is not None:
            raise ValueError(laboratory.failure)
        stage = "submission_validation"
        weights, support, biases, decays, plan, confidence, abstain = (
            _validate_submission(submission)
        )
        stage = "trusted_scoring"
        mechanism = _mechanism_metrics(
            world, weights, support, biases, decays, abstain
        )
        if world["kind"] == "in_library" and not abstain:
            prediction = _prediction_score(world, weights, biases, decays)
            decision = _decision_score(world, plan, shifted=False)
            transfer = _decision_score(world, plan, shifted=True)
        elif mechanism["correct_refusal"]:
            prediction = decision = transfer = 1.0
        else:
            prediction = decision = transfer = 0.0
        joint = float((
            mechanism["mechanism_quality"] * prediction * decision
        ) ** (1.0 / 3.0))
        transfer_joint = float((
            mechanism["mechanism_quality"] * prediction * transfer
        ) ** (1.0 / 3.0))
        confidence_score = 1.0 - (confidence - joint) ** 2
        return {
            "split": str(split),
            "world_index": int(index),
            "kind": str(world["kind"]),
            "valid": True,
            "signed_edge_f1": round(mechanism["signed_edge_f1"], 6),
            "weight_quality": round(mechanism["weight_quality"], 6),
            "bias_quality": round(mechanism["bias_quality"], 6),
            "decay_quality": round(mechanism["decay_quality"], 6),
            "mechanism_quality": round(mechanism["mechanism_quality"], 6),
            "prediction_quality": round(float(prediction), 6),
            "decision_quality": round(float(decision), 6),
            "transfer_decision_quality": round(float(transfer), 6),
            "joint_quality": round(joint, 6),
            "transfer_joint_quality": round(transfer_joint, 6),
            "correct_refusal": bool(mechanism["correct_refusal"]),
            "false_discovery": bool(mechanism["false_discovery"]),
            "abstained": bool(abstain),
            "confidence": round(float(confidence), 6),
            "confidence_score": round(float(confidence_score), 6),
            "experiment_calls": int(laboratory.calls),
            "experiment_budget_units": int(laboratory.used),
            "intervention_target_count": int(np.sum(np.abs(plan) > 1.0e-10)),
        }
    except Exception:
        if laboratory.failure is not None:
            failure_kind = laboratory.failure
        elif stage == "submission_validation":
            failure_kind = "invalid_submission"
        elif stage == "trusted_scoring":
            failure_kind = "trusted_scoring_failure"
        else:
            failure_kind = "candidate_execution_failure"
        return _invalid_record(
            split, index, world["kind"], failure_kind, laboratory
        )


def _normalized_mean(records, field):
    unsupported = sum(row["kind"] != "in_library" for row in records)
    baseline = unsupported / len(records)
    raw = float(np.mean([float(row[field]) for row in records]))
    return float(np.clip((raw - baseline) / max(1.0e-12, 1.0 - baseline), 0.0, 1.0))


def _split_metrics(records):
    supported = sum(row["kind"] == "in_library" for row in records)
    claims = sum(not bool(row["abstained"]) for row in records if row["valid"])
    false_discoveries = sum(bool(row["false_discovery"]) for row in records)
    unsupported = len(records) - supported
    return {
        "joint": _normalized_mean(records, "joint_quality"),
        "transfer_joint": _normalized_mean(records, "transfer_joint_quality"),
        "mechanism": _normalized_mean(records, "mechanism_quality"),
        "prediction": _normalized_mean(records, "prediction_quality"),
        "decision": _normalized_mean(records, "decision_quality"),
        "transfer_decision": _normalized_mean(records, "transfer_decision_quality"),
        "valid_rate": float(np.mean([bool(row["valid"]) for row in records])),
        "supported_claim_coverage": sum(
            row["kind"] == "in_library" and row["valid"] and not row["abstained"]
            for row in records
        ) / supported,
        "unsupported_refusal_rate": sum(
            bool(row["correct_refusal"]) for row in records
        ) / unsupported,
        "false_discovery_rate": false_discoveries / max(claims, 1),
        "mean_confidence_score": float(np.mean([
            float(row["confidence_score"]) for row in records
        ])),
        "mean_experiment_calls": float(np.mean([
            int(row["experiment_calls"]) for row in records
        ])),
        "mean_budget_units": float(np.mean([
            int(row["experiment_budget_units"]) for row in records
        ])),
    }


def evaluate(discover_gene_network):
    development = []
    heldout = []
    rows = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(rows):
        if call_index and hasattr(discover_gene_network, "reset_session"):
            discover_gene_network.reset_session()
        record = _evaluate_world(discover_gene_network, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    result = {
        "combined_score": dev["joint"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_rate"],
        "raw_score": dev["joint"] if development_valid else 0.0,
        "development_mechanism_score": dev["mechanism"],
        "development_prediction_score": dev["prediction"],
        "development_decision_utility": dev["decision"],
        "robustness_score": dev["transfer_joint"],
        "development_transfer_utility": dev["transfer_decision"],
        "development_robustness_gap": dev["joint"] - dev["transfer_joint"],
        "heldout_policy_score": held["joint"] if heldout_valid else 0.0,
        "heldout_mechanism_score": held["mechanism"],
        "heldout_prediction_score": held["prediction"],
        "heldout_decision_utility": held["decision"],
        "heldout_robustness_score": held["transfer_joint"] if heldout_valid else 0.0,
        "heldout_transfer_utility": held["transfer_decision"],
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_unsupported_refusal_rate": dev["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_confidence_score": dev["mean_confidence_score"],
        "heldout_confidence_score": held["mean_confidence_score"],
        "development_mean_experiment_calls": dev["mean_experiment_calls"],
        "heldout_mean_experiment_calls": held["mean_experiment_calls"],
        "development_mean_budget_units": dev["mean_budget_units"],
        "heldout_mean_budget_units": held["mean_budget_units"],
        "heldout_feasibility_rate": held["valid_rate"],
        "candidate_world_call_count": len(rows),
        "candidate_world_valid_rate": float(np.mean([
            bool(row["valid"]) for row in development + heldout
        ])),
        "per_world": development + heldout,
    }
    if not development_valid:
        failures = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(failures)
    return result


def _truth_submission(world):
    """Internal invariant-test witness; never passed to candidate code."""
    if world["kind"] != "in_library":
        return {
            "weights": np.zeros((N_GENES, N_GENES)),
            "support": np.zeros((N_GENES, N_GENES)),
            "biases": np.full(N_GENES, -0.3),
            "decay_rates": np.full(N_GENES, 0.6),
            "intervention": np.zeros(N_GENES),
            "confidence": 1.0,
            "abstain": True,
        }
    plan, _ = _reference_plan(world, shifted=False)
    return {
        "weights": np.asarray(world["weights"]).copy(),
        "support": (np.abs(world["weights"]) > 0.0).astype(int),
        "biases": np.asarray(world["biases"]).copy(),
        "decay_rates": np.asarray(world["decays"]).copy(),
        "intervention": plan,
        "confidence": 1.0,
        "abstain": False,
    }
