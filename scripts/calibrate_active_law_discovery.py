#!/usr/bin/env python3
"""Calibrate ActiveLawDiscovery with a generic sparse-system-identification reference."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/DynamicalSystems/ActiveLawDiscovery"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("active_law_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load ActiveLawDiscovery oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _features(states, controls):
    states = np.asarray(states, dtype=float)
    controls = np.asarray(controls, dtype=float)
    x = states[:, 0]
    y = states[:, 1]
    u = controls
    return np.column_stack([
        np.ones_like(x), x, y, u, x * x, x * y, y * y, x**3,
        x * x * y, x * y * y, y**3, x * u, y * u,
    ])


def _sparse_fit(design, derivatives, threshold=0.055):
    design = np.asarray(design, dtype=float)
    derivatives = np.asarray(derivatives, dtype=float)
    scales = np.sqrt(np.mean(design * design, axis=0))
    scales = np.maximum(scales, 1e-8)
    normalized = design / scales
    coefficients = np.linalg.lstsq(normalized, derivatives, rcond=1e-10)[0]
    for _ in range(12):
        physical = coefficients / scales[:, None]
        support = np.abs(physical) >= threshold
        updated = np.zeros_like(coefficients)
        for state in range(derivatives.shape[1]):
            active = support[:, state]
            if np.any(active):
                # A small ridge stabilizes nearly collinear polynomial columns without
                # encoding any hidden-world coefficient values.
                matrix = normalized[:, active]
                gram = matrix.T @ matrix + 2e-5 * np.eye(int(np.sum(active)))
                updated[active, state] = np.linalg.solve(
                    gram, matrix.T @ derivatives[:, state]
                )
        if np.array_equal(np.abs(updated / scales[:, None]) >= threshold, support):
            coefficients = updated
            break
        coefficients = updated
    physical = coefficients / scales[:, None]
    support = np.abs(physical) >= threshold
    return np.where(support, physical, 0.0), support


def reference_discover_law(n_states, term_names, experiment, budget_units):
    """Generic actively excited sparse-regression policy; no oracle constants are used."""
    del budget_units
    n_states = int(n_states)
    initials = np.array([
        [-1.65, -1.15], [-1.55, 1.40], [1.45, -1.55],
        [1.60, 1.20], [0.35, -0.85], [-0.80, 0.40],
    ])
    rng = np.random.default_rng(71309)
    experiments = []
    for index, initial in enumerate(initials):
        levels = rng.uniform(-1.4, 1.4, size=8)
        levels += 0.15 * np.sin(index + np.arange(8))
        controls = np.clip(np.repeat(levels, 8), -1.5, 1.5)
        experiments.append(experiment(initial, controls, len(controls)))

    designs = []
    derivatives = []
    groups = []
    for group, record in enumerate(experiments):
        time = np.asarray(record["time"], dtype=float)
        states = np.asarray(record["states"], dtype=float)
        controls = np.asarray(record["controls"], dtype=float)
        delta = float(np.median(np.diff(time)))
        smoothed = savgol_filter(states, 11, 3, axis=0, mode="interp")
        derivative = savgol_filter(
            states, 11, 3, deriv=1, delta=delta, axis=0, mode="interp"
        )
        # Match the derivative at pre-step states to the piecewise-constant control.
        interior = slice(5, len(controls) - 4)
        designs.append(_features(smoothed[:-1][interior], controls[interior]))
        derivatives.append(derivative[:-1][interior])
        groups.extend([group] * len(designs[-1]))
    design = np.vstack(designs)
    derivative = np.vstack(derivatives)
    groups = np.asarray(groups, dtype=int)

    # Fit on five trajectories and use the sixth to detect model-library inadequacy.
    train = groups < len(initials) - 1
    holdout = ~train
    coefficients, support = _sparse_fit(design[train], derivative[train])
    prediction = design[holdout] @ coefficients
    residual = float(np.sqrt(np.mean((derivative[holdout] - prediction) ** 2)))
    signal = float(np.sqrt(np.mean(derivative[holdout] ** 2)))
    relative_residual = residual / max(signal, 1e-8)

    # Null worlds have no derivative signal beyond observation noise. Misspecified worlds have
    # substantial structured held-out error. These thresholds are stated in observable units,
    # not keyed to any world seed or template.
    coefficient_norm = float(np.linalg.norm(coefficients))
    null_evidence = signal < 0.055 and coefficient_norm < 0.16
    inadequate_library = relative_residual > 0.34 and signal > 0.055
    abstain = bool(null_evidence or inadequate_library)
    confidence = float(np.clip(1.0 - relative_residual, 0.0, 1.0))
    if abstain:
        coefficients = np.zeros((len(term_names), n_states), dtype=float)
        support = np.zeros_like(coefficients, dtype=bool)
        confidence = float(np.clip(max(relative_residual - 0.25, 0.0), 0.0, 1.0))
    return {
        "coefficients": coefficients,
        "support": support.astype(int),
        "confidence": confidence,
        "abstain": abstain,
    }


def _always_abstain(n_states, term_names, experiment, budget_units):
    del budget_units
    experiment(np.zeros(int(n_states)), np.zeros(8), 8)
    shape = (len(term_names), int(n_states))
    return {
        "coefficients": np.zeros(shape),
        "support": np.zeros(shape),
        "confidence": 0.0,
        "abstain": True,
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    reference = oracle.evaluate(reference_discover_law)

    exact_checks = []
    stability_checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("validation", oracle.VALIDATION_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                support = np.abs(world["coefficients"]) > 0.0
                mechanism = oracle._mechanism_metrics(
                    world, world["coefficients"], support, False
                )
                prediction = oracle._prediction_score(world, world["coefficients"])
                exact_passed = (
                    mechanism["mechanism_score"] == 1.0 and prediction == 1.0
                )
            else:
                zeros = np.zeros_like(world["coefficients"])
                mechanism = oracle._mechanism_metrics(
                    world, zeros, np.zeros_like(zeros, dtype=bool), True
                )
                prediction = oracle._prediction_score(world, zeros)
                exact_passed = mechanism["mechanism_score"] == 1.0
            exact_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "mechanism_score": mechanism["mechanism_score"],
                "prediction_score": prediction,
                "passed": exact_passed,
            })

            rng = np.random.default_rng(world["seed"] + 8081)
            maximum = 0.0
            stable = True
            for _ in range(16):
                initial = rng.uniform(-2.0, 2.0, size=oracle.N_STATES)
                controls = rng.uniform(-1.5, 1.5, size=oracle.MAX_STEPS)
                try:
                    states = oracle._simulate(world, initial, controls)
                    maximum = max(maximum, float(np.max(np.abs(states))))
                except Exception:
                    stable = False
                    break
            stability_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "maximum_absolute_state": maximum,
                "passed": stable,
            })

    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["valid"] == 1.0
        and reference["valid"] == 1.0
        and reference["validation_feasibility_rate"] == 1.0
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in stability_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "baseline": baseline,
        "generic_sparse_reference": reference,
        "exact_or_abstention_checks": exact_checks,
        "stability_checks": stability_checks,
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
