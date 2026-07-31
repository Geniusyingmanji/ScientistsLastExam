#!/usr/bin/env python3
"""Calibrate GeneNetworkIntervention with a truth-blind systems-ID reference.

The reference sees only the public callback and contract.  It uses fixed
CRISPRi/a excitation, local nonlinear regression, observable residual checks
and a coarse intervention search.  Hidden truth is used only after evaluation
for invariant and headroom diagnostics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


TASK = ROOT / "benchmarks/Biology/GeneNetworkIntervention"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("gene_network_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load GeneNetworkIntervention oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sigmoid(value):
    value = np.clip(np.asarray(value, dtype=float), -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-value))


def _experiment_schedules(n_genes):
    schedules = []
    single_levels = np.asarray((-1.8, 1.8, -1.2, 1.2, -0.6, 0.6))
    for target in range(n_genes - 1):
        controls = np.zeros((60, n_genes), dtype=float)
        phase = np.roll(single_levels, target)
        for block, level in enumerate(phase):
            controls[10 * block:10 * (block + 1), target] = level
        schedules.append(controls)
    pair_specs = ((0, 1), (0, 2), (1, 2))
    pair_levels = (
        ((-1.6, 1.2), (1.5, -1.1), (-0.8, -1.5), (0.9, 1.6)),
        ((1.3, -1.7), (-1.5, 1.1), (0.7, 1.6), (-0.9, -1.2)),
        ((-1.1, -1.7), (1.6, 0.8), (1.2, -1.4), (-1.7, 1.3)),
    )
    for targets, levels in zip(pair_specs, pair_levels):
        controls = np.zeros((40, n_genes), dtype=float)
        for block, values in enumerate(levels):
            controls[10 * block:10 * (block + 1), list(targets)] = values
        schedules.append(controls)
    return schedules


def _derivative_rows(records):
    states = []
    controls = []
    derivatives = []
    groups = []
    for group, record in enumerate(records):
        time = np.asarray(record["time"], dtype=float)
        expression = np.asarray(record["expression"], dtype=float)
        intervention = np.asarray(record["intervention"], dtype=float)
        dt = float(np.median(np.diff(time)))
        n_steps = len(intervention)
        # Schedules are piecewise constant in ten-step blocks.  Differentiate each block
        # independently and discard its boundary points, avoiding filter leakage across
        # intervention changes.
        for start in range(0, n_steps, 10):
            stop = min(start + 10, n_steps)
            segment = expression[start:stop + 1]
            if len(segment) < 9:
                continue
            smooth = savgol_filter(segment, 7, 3, axis=0, mode="interp")
            derivative = savgol_filter(
                segment, 7, 3, deriv=1, delta=dt, axis=0, mode="interp"
            )
            for local in range(3, len(segment) - 3):
                states.append(smooth[local])
                controls.append(intervention[start + local])
                derivatives.append(derivative[local])
                groups.append(group)
    return (
        np.asarray(states), np.asarray(controls), np.asarray(derivatives),
        np.asarray(groups, dtype=int),
    )


def _fit_target(states, controls, derivatives, target, bias_bounds, decay_bounds):
    n_genes = states.shape[1]
    sources = [index for index in range(n_genes) if index != target]
    features = 2.0 * states[:, sources] - 1.0
    response = derivatives[:, target]
    intervention = controls[:, target]

    lower = np.asarray((bias_bounds[0], decay_bounds[0]) + (-2.8,) * len(sources))
    upper = np.asarray((bias_bounds[1], decay_bounds[1]) + (2.8,) * len(sources))
    initial = np.asarray((-0.3, 0.65) + (0.0,) * len(sources))

    def residual(parameters, active_sources=None):
        bias, decay = parameters[:2]
        weights = np.zeros(len(sources), dtype=float)
        if active_sources is None:
            weights[:] = parameters[2:]
        elif len(active_sources):
            weights[np.asarray(active_sources, dtype=int)] = parameters[2:]
        linear = bias + features @ weights + intervention
        predicted = decay * (_sigmoid(linear) - states[:, target])
        # Weak ridge regularization stabilizes nearly correlated regulators without
        # encoding a topology or preferred sign.
        penalty = 0.018 * weights
        return np.concatenate((predicted - response, penalty))

    first = least_squares(
        residual, initial, bounds=(lower, upper), max_nfev=3000,
        xtol=1e-11, ftol=1e-11, gtol=1e-11,
    )
    full_weights = np.asarray(first.x[2:], dtype=float)
    active = np.flatnonzero(np.abs(full_weights) >= 0.14)
    if len(active):
        reduced_initial = np.concatenate((first.x[:2], full_weights[active]))
        reduced_lower = np.concatenate((lower[:2], lower[2:][active]))
        reduced_upper = np.concatenate((upper[:2], upper[2:][active]))
        second = least_squares(
            lambda value: residual(value, active), reduced_initial,
            bounds=(reduced_lower, reduced_upper), max_nfev=3000,
            xtol=1e-11, ftol=1e-11, gtol=1e-11,
        )
        bias, decay = second.x[:2]
        weights = np.zeros(len(sources), dtype=float)
        weights[active] = second.x[2:]
    else:
        bias, decay = first.x[:2]
        weights = np.zeros(len(sources), dtype=float)
    predicted = decay * (
        _sigmoid(bias + features @ weights + intervention) - states[:, target]
    )
    return float(bias), float(decay), sources, weights, predicted


def _fit_network(states, controls, derivatives, row_mask=None):
    if row_mask is None:
        row_mask = np.ones(len(states), dtype=bool)
    states_fit = states[row_mask]
    controls_fit = controls[row_mask]
    derivatives_fit = derivatives[row_mask]
    n_genes = states.shape[1]
    weights = np.zeros((n_genes, n_genes), dtype=float)
    biases = np.zeros(n_genes, dtype=float)
    decays = np.zeros(n_genes, dtype=float)
    predictions = np.zeros_like(derivatives_fit)
    for target in range(n_genes):
        bias, decay, sources, values, predicted = _fit_target(
            states_fit, controls_fit, derivatives_fit, target,
            (-1.2, 0.6), (0.35, 1.10),
        )
        weights[sources, target] = values
        biases[target] = bias
        decays[target] = decay
        predictions[:, target] = predicted
    return weights, biases, decays, predictions


def _estimated_derivative(state, intervention, weights, biases, decays):
    return decays * (
        _sigmoid(biases + (2.0 * state - 1.0) @ weights + intervention) - state
    )


def _estimated_step(state, intervention, weights, biases, decays, dt=0.10):
    k1 = _estimated_derivative(state, intervention, weights, biases, decays)
    k2 = _estimated_derivative(
        state + 0.5 * dt * k1, intervention, weights, biases, decays
    )
    k3 = _estimated_derivative(
        state + 0.5 * dt * k2, intervention, weights, biases, decays
    )
    k4 = _estimated_derivative(state + dt * k3, intervention, weights, biases, decays)
    return np.clip(state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0, 0.0, 1.0)


def _estimated_steady(weights, biases, decays):
    state = np.full(len(biases), 0.5, dtype=float)
    zero = np.zeros(len(biases), dtype=float)
    for _ in range(800):
        updated = _estimated_step(state, zero, weights, biases, decays)
        if np.max(np.abs(updated - state)) < 1.0e-10:
            return updated
        state = updated
    return state


def _estimated_utility(plan, weights, biases, decays, objective):
    baseline = _estimated_steady(weights, biases, decays)
    state = baseline.copy()
    for _ in range(80):
        state = _estimated_step(state, plan, weights, biases, decays)
    readout = int(objective["readout_index"])
    actionable = list(objective["actionable_indices"])
    gain = float(state[readout] - baseline[readout])
    off_target = float(np.mean(np.abs(state[actionable] - baseline[actionable])))
    dose = float(np.sum(np.abs(plan[actionable])))
    return (
        gain - float(objective["regulator_disruption_penalty"]) * off_target
        - float(objective["dose_penalty"]) * dose
    )


def _choose_intervention(weights, biases, decays, objective):
    n_genes = len(biases)
    actionable = tuple(int(value) for value in objective["actionable_indices"])
    levels = (-2.0, -4.0 / 3.0, -2.0 / 3.0, 2.0 / 3.0, 4.0 / 3.0, 2.0)
    candidates = [np.zeros(n_genes, dtype=float)]
    import itertools
    for size in (1, 2):
        for targets in itertools.combinations(actionable, size):
            for values in itertools.product(levels, repeat=size):
                plan = np.zeros(n_genes, dtype=float)
                plan[list(targets)] = values
                candidates.append(plan)
    values = [
        _estimated_utility(plan, weights, biases, decays, objective)
        for plan in candidates
    ]
    return candidates[int(np.argmax(values))]


def reference_discover_gene_network(gene_names, perturb, phenotype_objective, budget_units):
    """Truth-blind nonlinear system identification and intervention design."""
    del budget_units
    n_genes = len(gene_names)
    records = [
        perturb(schedule, len(schedule))
        for schedule in _experiment_schedules(n_genes)
    ]
    states, controls, derivatives, groups = _derivative_rows(records)
    weights, biases, decays, fitted = _fit_network(states, controls, derivatives)
    residual = float(np.sqrt(np.mean((derivatives - fitted) ** 2)))
    signal = float(np.sqrt(np.mean(derivatives ** 2)))

    # Leave-one-experiment-out error is an observable model-family diagnostic.  It does not
    # use world identity or hidden parameters.
    heldout_errors = []
    for group in range(len(records)):
        train = groups != group
        test = ~train
        held_weights, held_biases, held_decays, _ = _fit_network(
            states, controls, derivatives, train
        )
        predictions = np.column_stack([
            _estimated_derivative(
                states[index], controls[index], held_weights, held_biases, held_decays
            )
            for index in np.flatnonzero(test)
        ]).T
        heldout_errors.append(float(np.sqrt(np.mean(
            (derivatives[test] - predictions) ** 2
        ))))
    cross_validated = float(np.mean(heldout_errors))
    worst_cross_validated = float(np.max(heldout_errors))
    relative_cv = cross_validated / max(signal, 0.025)
    edge_count = int(np.sum(np.abs(weights) >= 0.14))
    edge_norm = float(np.linalg.norm(weights))

    # The null gate is an observable cross-gene effect-size threshold.  The model-family
    # gate is an absolute derivative-prediction error in normalized-expression/time units;
    # it sits above the largest supported-world leave-one-experiment error in the frozen
    # calibration panel and below both delayed latent-regulator controls.
    null_evidence = edge_count == 0 or edge_norm < 1.70
    inadequate_family = worst_cross_validated > 0.055 and signal > 0.045
    abstain = bool(null_evidence or inadequate_family)
    support = np.abs(weights) >= 0.14
    plan = np.zeros(n_genes, dtype=float)
    if not abstain:
        plan = _choose_intervention(
            weights, biases, decays, phenotype_objective
        )
    else:
        weights = np.zeros_like(weights)
        support = np.zeros_like(support, dtype=bool)
    confidence = float(np.clip(
        1.0 - max(relative_cv - 0.08, 0.0) / 0.45, 0.0, 1.0
    ))
    if abstain:
        confidence = float(np.clip(max(relative_cv - 0.22, 0.0) / 0.45, 0.0, 1.0))
    return {
        "weights": weights,
        "support": support.astype(int),
        "biases": biases,
        "decay_rates": decays,
        "intervention": plan,
        "confidence": confidence,
        "abstain": abstain,
    }


def _always_abstain(gene_names, perturb, phenotype_objective, budget_units):
    del phenotype_objective, budget_units
    n_genes = len(gene_names)
    perturb(np.zeros(n_genes), 20)
    return {
        "weights": np.zeros((n_genes, n_genes)),
        "support": np.zeros((n_genes, n_genes)),
        "biases": np.full(n_genes, -0.3),
        "decay_rates": np.full(n_genes, 0.6),
        "intervention": np.zeros(n_genes),
        "confidence": 0.0,
        "abstain": True,
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    reference = oracle.evaluate(reference_discover_gene_network)

    exact_checks = []
    stability_checks = []
    minimum_reference_utility = math.inf
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            returned = oracle._truth_submission(world)
            values = oracle._validate_submission(returned)
            mechanism = oracle._mechanism_metrics(
                world, values[0], values[1], values[2], values[3], values[6]
            )
            prediction = (
                oracle._prediction_score(world, values[0], values[2], values[3])
                if world["kind"] == "in_library" else None
            )
            decision = (
                oracle._decision_score(world, values[4], shifted=False)
                if world["kind"] == "in_library" else None
            )
            if world["kind"] == "in_library":
                _, reference_utility = oracle._reference_plan(world, shifted=False)
                minimum_reference_utility = min(
                    minimum_reference_utility, reference_utility
                )
                passed = (
                    abs(mechanism["mechanism_quality"] - 1.0) < 1e-12
                    and abs(prediction - 1.0) < 1e-10
                    and decision > 0.999
                )
            else:
                passed = bool(mechanism["correct_refusal"])
            exact_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "mechanism_quality": mechanism["mechanism_quality"],
                "prediction_quality": prediction,
                "decision_quality": decision,
                "passed": passed,
            })

            rng = np.random.default_rng(world["seed"] + 71)
            stable = True
            maximum = 0.0
            for _ in range(12):
                controls = rng.uniform(-2.0, 2.0, size=(80, oracle.N_GENES))
                mask = rng.choice(oracle.N_GENES, size=2, replace=False)
                controls[:, [index for index in range(oracle.N_GENES) if index not in mask]] = 0.0
                try:
                    trajectory = oracle._simulate(world, controls)
                    maximum = max(maximum, float(np.max(np.abs(trajectory))))
                except Exception:
                    stable = False
                    break
            stability_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "maximum_absolute_expression": maximum,
                "passed": stable,
            })

    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["valid"] == 1.0
        and reference["valid"] == 1.0
        and reference["heldout_feasibility_rate"] == 1.0
        and reference["combined_score"] > 0.02
        and reference["combined_score"] < 0.98
        and reference["heldout_policy_score"] > 0.02
        and reference["development_supported_claim_coverage"] == 1.0
        and reference["heldout_supported_claim_coverage"] == 1.0
        and reference["development_unsupported_refusal_rate"] == 1.0
        and reference["heldout_unsupported_refusal_rate"] == 1.0
        and reference["development_false_discovery_rate"] == 0.0
        and reference["heldout_false_discovery_rate"] == 0.0
        and minimum_reference_utility > 0.01
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in stability_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SYNTHETIC_TASK_CALIBRATION_NOT_MODEL_PERFORMANCE_OR_BIOLOGICAL_DISCOVERY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "baseline": baseline,
        "truth_blind_nonlinear_reference": reference,
        "exact_or_refusal_checks": exact_checks,
        "stability_checks": stability_checks,
        "minimum_truth_only_reference_utility": minimum_reference_utility,
        "limitations": [
            "The worlds are synthetic four-gene ODEs, not a named cell line or biological dataset.",
            "The truth-only intervention grid is used only to calibrate score normalization and is unavailable to candidates.",
            "The classical reference is a deterministic headroom check, not a performance claim about an autonomous agent.",
            "External systems-biology review, server-held worlds, measurement/batch models and independent wet-lab validation remain required.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
