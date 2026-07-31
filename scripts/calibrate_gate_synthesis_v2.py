#!/usr/bin/env python3
"""Calibrate GateSynthesis-v2 with an independent nominal GRAPE witness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import expm_frechet
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Physics/GateSynthesis"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("gate_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load GateSynthesis-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _grape(drift, controls, target, n_steps, dt, amplitude_limit):
    drift = np.asarray(drift, dtype=complex)
    controls = np.asarray(controls, dtype=complex)
    target = np.asarray(target, dtype=complex)
    n_steps = int(n_steps)
    n_controls = len(controls)
    dimension = len(drift)
    # Seed from public numerical plant values, not task name, order or hidden split.
    seed = int(abs(np.sum(drift.real)) * 1e6 + n_steps * 1009 + dimension * 9173)
    rng = np.random.default_rng(seed)
    initial = rng.normal(0.0, 0.30, size=(n_steps, n_controls))

    def objective(flat):
        amplitudes = flat.reshape(n_steps, n_controls)
        propagators = []
        derivatives = []
        for step in range(n_steps):
            hamiltonian = drift + np.tensordot(
                amplitudes[step], controls, axes=(0, 0)
            )
            generator = -1.0j * hamiltonian * dt
            row = []
            propagator = None
            for control_index in range(n_controls):
                direction = -1.0j * controls[control_index] * dt
                if control_index == 0:
                    propagator, derivative = expm_frechet(
                        generator, direction, compute_expm=True
                    )
                else:
                    derivative = expm_frechet(
                        generator, direction, compute_expm=False
                    )
                row.append(derivative)
            propagators.append(propagator)
            derivatives.append(row)

        forward = [np.eye(dimension, dtype=complex)]
        for propagator in propagators:
            forward.append(propagator @ forward[-1])
        backward = [None] * (n_steps + 1)
        backward[n_steps] = np.eye(dimension, dtype=complex)
        for step in range(n_steps - 1, -1, -1):
            backward[step] = backward[step + 1] @ propagators[step]

        overlap = np.trace(target.conj().T @ forward[-1])
        fidelity = float(abs(overlap) ** 2 / dimension**2)
        gradient = np.zeros((n_steps, n_controls), dtype=float)
        for step in range(n_steps):
            for control_index in range(n_controls):
                derivative_overlap = np.trace(
                    target.conj().T
                    @ backward[step + 1]
                    @ derivatives[step][control_index]
                    @ forward[step]
                )
                gradient[step, control_index] = (
                    2.0 * np.real(np.conj(overlap) * derivative_overlap)
                    / dimension**2
                )
        return -fidelity, -gradient.ravel()

    result = minimize(
        objective,
        initial.ravel(),
        jac=True,
        method="L-BFGS-B",
        bounds=[(-amplitude_limit, amplitude_limit)] * initial.size,
        options={"maxiter": 320, "ftol": 1e-12, "gtol": 1e-8, "maxls": 30},
    )
    return result.x.reshape(n_steps, n_controls)


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(
        lambda _drift, controls, _target, n_steps, _dt, _limit: np.zeros(
            (n_steps, len(controls)), dtype=float
        )
    )
    reference = oracle.evaluate(_grape)
    invariant_checks = []
    for instance in oracle.INSTANCES:
        zero = np.zeros((instance["n_steps"], len(instance["controls"])))
        unitary = oracle._propagate(
            instance["drift"], instance["controls"], zero, instance["dt"]
        )
        invariant_checks.append({
            "name": instance["name"],
            "unitarity_error": float(np.max(np.abs(
                unitary.conj().T @ unitary - np.eye(len(unitary))
            ))),
            "global_phase_fidelity": oracle._process_fidelity(
                instance["target"], np.exp(0.37j) * instance["target"]
            ),
        })

    finite_rejection = oracle.evaluate(
        lambda _drift, controls, _target, n_steps, _dt, _limit: np.full(
            (n_steps, len(controls)), np.nan
        )
    )
    bound_rejection = oracle.evaluate(
        lambda _drift, controls, _target, n_steps, _dt, limit: np.full(
            (n_steps, len(controls)), limit + 1.0
        )
    )
    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["valid"] == 1.0
        and reference["valid"] == 1.0
        and reference["heldout_feasibility_rate"] == 1.0
        and reference["development_score"] > 0.98
        and reference["heldout_policy_score"] > 0.98
        and finite_rejection["valid"] == 0.0
        and bound_rejection["valid"] == 0.0
        and all(row["unitarity_error"] < 1e-11 for row in invariant_checks)
        and all(abs(row["global_phase_fidelity"] - 1.0) < 1e-12
                for row in invariant_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "baseline": baseline,
        "nominal_grape_reference": reference,
        "invariant_checks": invariant_checks,
        "nonfinite_rejection": finite_rejection,
        "out_of_bound_rejection": bound_rejection,
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
