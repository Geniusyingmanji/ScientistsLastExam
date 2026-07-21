"""Trusted oracle for budgeted intervention-based causal-mechanism recovery."""

from __future__ import annotations

import math

import numpy as np


N_VARIABLES = 7
BUDGET_UNITS = 28
SAMPLE_UNIT = 32
WORLD_SEEDS = (17011, 17027, 17041, 17053, 17077, 17093)
NULL_WORLD = len(WORLD_SEEDS) - 1


def _make_world(seed, null=False):
    """Create a deterministic DAG with a hidden, permuted topological order."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(N_VARIABLES)
    coefficients = np.zeros((N_VARIABLES, N_VARIABLES), dtype=float)
    if not null:
        # A sparse backbone prevents degenerate empty/near-empty draws. Extra skip edges make
        # total intervention effects differ from direct structural coefficients.
        for position in range(N_VARIABLES - 1):
            if position % 2 == 0 or rng.random() < 0.72:
                parent = int(order[position])
                child = int(order[position + 1])
                magnitude = rng.uniform(0.45, 1.10)
                coefficients[parent, child] = magnitude * rng.choice([-1.0, 1.0])
        for left in range(N_VARIABLES - 2):
            for right in range(left + 2, N_VARIABLES):
                if rng.random() < 0.22:
                    parent = int(order[left])
                    child = int(order[right])
                    magnitude = rng.uniform(0.35, 0.90)
                    coefficients[parent, child] = magnitude * rng.choice([-1.0, 1.0])
    noise_scales = rng.uniform(0.65, 1.25, size=N_VARIABLES)
    return coefficients, order, noise_scales


def _simulate(coefficients, order, noise_scales, n_samples, seed, intervention=None):
    rng = np.random.default_rng(seed)
    samples = np.zeros((n_samples, N_VARIABLES), dtype=float)
    noise = rng.normal(size=(n_samples, N_VARIABLES)) * noise_scales
    intervention_variable = None if intervention is None else int(intervention[0])
    intervention_value = None if intervention is None else float(intervention[1])
    for raw_node in order:
        node = int(raw_node)
        if node == intervention_variable:
            samples[:, node] = intervention_value
            continue
        parents = coefficients[:, node]
        samples[:, node] = noise[:, node] + samples @ parents
    return samples


class _Laboratory:
    def __init__(self, world_seed, coefficients, order, noise_scales):
        self.world_seed = int(world_seed)
        self.coefficients = coefficients
        self.order = order
        self.noise_scales = noise_scales
        self.used = 0
        self.calls = 0
        self.violated = False

    def _charge(self, n_samples, maximum):
        if isinstance(n_samples, bool):
            raise ValueError("n_samples must be an integer")
        value = int(n_samples)
        if value != n_samples or value < 8 or value > maximum:
            raise ValueError("n_samples outside the allowed range")
        cost = int(math.ceil(value / SAMPLE_UNIT))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("experimental budget exceeded")
        self.used += cost
        self.calls += 1
        return value

    def _query_seed(self, kind, variable=0, value=0.0):
        value_code = int(round((float(value) + 3.0) * 100000.0))
        sequence = np.random.SeedSequence([
            self.world_seed, self.calls, int(kind), int(variable), max(0, value_code)
        ])
        return int(sequence.generate_state(1, dtype=np.uint32)[0])

    def observe(self, n_samples):
        count = self._charge(n_samples, 256)
        seed = self._query_seed(0)
        return _simulate(
            self.coefficients, self.order, self.noise_scales, count, seed,
            intervention=None,
        )

    def intervene(self, variable, value, n_samples):
        if isinstance(variable, bool):
            raise ValueError("variable must be an integer index")
        index = int(variable)
        if index != variable or not 0 <= index < N_VARIABLES:
            raise ValueError("intervention variable outside the allowed range")
        level = float(value)
        if not math.isfinite(level) or not -3.0 <= level <= 3.0:
            raise ValueError("intervention value outside [-3,3]")
        count = self._charge(n_samples, 128)
        seed = self._query_seed(1, index, level)
        return _simulate(
            self.coefficients, self.order, self.noise_scales, count, seed,
            intervention=(index, level),
        )


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dict")
    abstain = bool(submission.get("abstain", False))
    adjacency = np.asarray(submission.get("adjacency"), dtype=float)
    coefficients = np.asarray(submission.get("coefficients"), dtype=float)
    expected = (N_VARIABLES, N_VARIABLES)
    if adjacency.shape != expected or coefficients.shape != expected:
        raise ValueError("adjacency and coefficients must both have shape (n,n)")
    if not np.all(np.isfinite(adjacency)) or not np.all(np.isfinite(coefficients)):
        raise ValueError("submission contains non-finite values")
    confidence = float(submission.get("confidence", 0.5))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if abstain:
        adjacency = np.zeros(expected, dtype=bool)
        coefficients = np.zeros(expected, dtype=float)
    else:
        adjacency = adjacency >= 0.5
        np.fill_diagonal(adjacency, False)
        coefficients = np.clip(coefficients, -3.0, 3.0)
        np.fill_diagonal(coefficients, 0.0)
        coefficients = np.where(adjacency, coefficients, 0.0)
    return adjacency.astype(bool), coefficients, confidence, abstain


def _mechanism_metrics(truth, predicted_adjacency, predicted_coefficients):
    true_adjacency = np.abs(truth) > 1e-12
    tp = int(np.sum(true_adjacency & predicted_adjacency))
    fp = int(np.sum(~true_adjacency & predicted_adjacency))
    fn = int(np.sum(true_adjacency & ~predicted_adjacency))
    if not np.any(true_adjacency) and not np.any(predicted_adjacency):
        edge_f1 = 1.0
    elif tp == 0:
        edge_f1 = 0.0
    else:
        precision = tp / (tp + fp)
        recall = tp / (tp + fn)
        edge_f1 = 2.0 * precision * recall / (precision + recall)

    if np.any(true_adjacency):
        relative_error = np.abs(
            predicted_coefficients[true_adjacency] - truth[true_adjacency]
        ) / np.abs(truth[true_adjacency])
        coefficient_score = float(np.mean(np.clip(1.0 - relative_error, 0.0, 1.0)))
    else:
        coefficient_score = 1.0 if not np.any(predicted_adjacency) else 0.0
    mechanism_score = 0.60 * edge_f1 + 0.40 * coefficient_score
    return float(edge_f1), coefficient_score, float(mechanism_score)


def _intervention_mean(coefficients, variable, value):
    remaining = [i for i in range(N_VARIABLES) if i != variable]
    block = coefficients[np.ix_(remaining, remaining)]
    system = np.eye(len(remaining)) - block.T
    if not np.all(np.isfinite(system)) or np.linalg.cond(system) > 1e8:
        raise np.linalg.LinAlgError("unstable submitted mechanism")
    rhs = coefficients[variable, remaining] * value
    mean = np.zeros(N_VARIABLES, dtype=float)
    mean[variable] = value
    mean[remaining] = np.linalg.solve(system, rhs)
    return mean


def _prediction_score(truth, estimate):
    errors = []
    zero_errors = []
    for variable in range(N_VARIABLES):
        for value in (-1.75, 1.25):
            expected = _intervention_mean(truth, variable, value)
            zero_prediction = np.zeros(N_VARIABLES, dtype=float)
            zero_prediction[variable] = value
            try:
                predicted = _intervention_mean(estimate, variable, value)
            except np.linalg.LinAlgError:
                return 0.0
            errors.append(float(np.mean((predicted - expected) ** 2)))
            zero_errors.append(float(np.mean((zero_prediction - expected) ** 2)))
    rmse = math.sqrt(float(np.mean(errors)))
    baseline_rmse = math.sqrt(float(np.mean(zero_errors)))
    if baseline_rmse < 1e-12:
        return float(math.exp(-rmse))
    return float(np.clip(1.0 - rmse / baseline_rmse, 0.0, 1.0))


def evaluate(discover_mechanism):
    world_results = []
    mechanism_scores = []
    prediction_scores = []
    valid_worlds = 0
    null_correct = False

    for world_index, seed in enumerate(WORLD_SEEDS):
        truth, order, noise_scales = _make_world(seed, null=world_index == NULL_WORLD)
        laboratory = _Laboratory(seed, truth, order, noise_scales)
        try:
            submission = discover_mechanism(
                N_VARIABLES, laboratory.observe, laboratory.intervene, BUDGET_UNITS
            )
            adjacency, coefficients, confidence, abstain = _validate_submission(submission)
            if laboratory.violated:
                raise RuntimeError("experimental budget exceeded")
            edge_f1, coefficient_score, mechanism_score = _mechanism_metrics(
                truth, adjacency, coefficients
            )
            prediction_score = _prediction_score(truth, coefficients)
            is_null = world_index == NULL_WORLD
            if is_null:
                null_correct = bool(not np.any(adjacency) and abstain)
            valid_worlds += 1
            mechanism_scores.append(mechanism_score)
            prediction_scores.append(prediction_score)
            world_results.append({
                "valid": True,
                "edge_f1": round(edge_f1, 6),
                "coefficient_score": round(coefficient_score, 6),
                "mechanism_score": round(mechanism_score, 6),
                "intervention_prediction_score": round(prediction_score, 6),
                "experiment_calls": laboratory.calls,
                "experiment_budget_units": laboratory.used,
                "abstained": abstain,
                "confidence": round(confidence, 6),
                "null_world": is_null,
            })
        except Exception as exc:
            mechanism_scores.append(0.0)
            prediction_scores.append(0.0)
            world_results.append({
                "valid": False,
                "reason": "%s: %s" % (type(exc).__name__, exc),
                "mechanism_score": 0.0,
                "intervention_prediction_score": 0.0,
                "experiment_calls": laboratory.calls,
                "experiment_budget_units": laboratory.used,
                "null_world": world_index == NULL_WORLD,
            })

    raw_mechanism = float(np.mean(mechanism_scores))
    # Always predicting the null graph solves only the explicitly included null world.
    no_claim_baseline = 1.0 / len(WORLD_SEEDS)
    combined = float(np.clip(
        (raw_mechanism - no_claim_baseline) / (1.0 - no_claim_baseline), 0.0, 1.0
    ))
    return {
        "combined_score": combined,
        "raw_score": raw_mechanism,
        "valid": 1.0 if valid_worlds == len(WORLD_SEEDS) else 0.0,
        "feasibility_rate": valid_worlds / len(WORLD_SEEDS),
        "mechanism_score": raw_mechanism,
        "intervention_prediction_score": float(np.mean(prediction_scores)),
        "null_abstention_correct": null_correct,
        "mean_experiment_calls": float(np.mean([r["experiment_calls"] for r in world_results])),
        "mean_experiment_budget_units": float(np.mean([
            r["experiment_budget_units"] for r in world_results
        ])),
        "per_world": world_results,
    }

