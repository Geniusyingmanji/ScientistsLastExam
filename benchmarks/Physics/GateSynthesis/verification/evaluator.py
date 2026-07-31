"""Trusted oracle for nominal and hardware-shifted quantum gate synthesis."""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import expm


I2 = np.eye(2, dtype=complex)
X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
Y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)


def _kron(left, right):
    return np.kron(left, right)


HADAMARD = (X + Z) / math.sqrt(2.0)
SQRT_X = expm(-1.0j * math.pi * X / 4.0)
SQRT_Y = expm(-1.0j * math.pi * Y / 4.0)
CNOT = np.array([
    [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]
], dtype=complex)
CZ = np.diag([1.0, 1.0, 1.0, -1.0]).astype(complex)
XX_ENTANGLER = expm(-1.0j * math.pi * _kron(X, X) / 4.0)


def _single_instance(name, target, split, drift_scale, control_scale, detuning_sign):
    return {
        "name": name,
        "split": split,
        "drift": drift_scale * Z,
        "controls": np.asarray([control_scale * X, control_scale * Y]),
        "target": np.asarray(target, dtype=complex),
        "n_steps": 12,
        "dt": 0.12,
        "amplitude_limit": 5.0,
        "detuning": detuning_sign * 0.055 * Z,
    }


def _two_qubit_instance(name, target, split, coupling, detuning_1, detuning_2):
    return {
        "name": name,
        "split": split,
        "drift": (
            coupling * _kron(Z, Z)
            + detuning_1 * _kron(Z, I2)
            + detuning_2 * _kron(I2, Z)
        ),
        "controls": np.asarray([
            0.5 * _kron(X, I2), 0.5 * _kron(Y, I2),
            0.5 * _kron(I2, X), 0.5 * _kron(I2, Y),
        ]),
        "target": np.asarray(target, dtype=complex),
        "n_steps": 20,
        "dt": 0.12,
        "amplitude_limit": 5.0,
        "detuning": 0.04 * (_kron(Z, I2) - 0.7 * _kron(I2, Z)),
    }


# The execution order deliberately interleaves development and held-out targets. Candidate
# state cannot identify a split from call count, and every call exposes the full nominal plant.
INSTANCES = (
    _single_instance("dev_hadamard", HADAMARD, "development", 0.20, 0.50, 1.0),
    _two_qubit_instance("heldout_xx", XX_ENTANGLER, "heldout", 0.50, -0.06, 0.04),
    _two_qubit_instance("dev_cnot", CNOT, "development", 0.55, 0.08, -0.05),
    _single_instance("heldout_sqrt_y", SQRT_Y, "heldout", 0.27, 0.46, -1.0),
    _single_instance("dev_sqrt_x", SQRT_X, "development", -0.23, 0.53, -1.0),
    _two_qubit_instance("dev_cz", CZ, "development", 0.58, -0.04, 0.07),
)
DEVELOPMENT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "development")
HELDOUT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "heldout")


def _is_hermitian(matrix, tolerance=1e-12):
    matrix = np.asarray(matrix, dtype=complex)
    return bool(np.allclose(matrix, matrix.conj().T, atol=tolerance, rtol=0.0))


def _validate_instances():
    names = set()
    for instance in INSTANCES:
        drift = instance["drift"]
        controls = instance["controls"]
        target = instance["target"]
        dimension = drift.shape[0]
        if instance["name"] in names:
            raise ValueError("duplicate quantum-control instance name")
        names.add(instance["name"])
        if drift.shape != (dimension, dimension) or controls.ndim != 3:
            raise ValueError("invalid Hamiltonian shape")
        if controls.shape[1:] != (dimension, dimension):
            raise ValueError("invalid control-Hamiltonian shape")
        if target.shape != (dimension, dimension):
            raise ValueError("invalid target shape")
        if not _is_hermitian(drift) or not all(_is_hermitian(row) for row in controls):
            raise ValueError("Hamiltonians must be Hermitian")
        if not np.allclose(target.conj().T @ target, np.eye(dimension), atol=1e-12):
            raise ValueError("target must be unitary")


_validate_instances()


def _propagate(drift, controls, amplitudes, dt):
    drift = np.asarray(drift, dtype=complex)
    controls = np.asarray(controls, dtype=complex)
    amplitudes = np.asarray(amplitudes, dtype=float)
    unitary = np.eye(drift.shape[0], dtype=complex)
    for row in amplitudes:
        hamiltonian = drift + np.tensordot(row, controls, axes=(0, 0))
        unitary = expm(-1.0j * hamiltonian * float(dt)) @ unitary
    return unitary


def _process_fidelity(target, achieved):
    dimension = target.shape[0]
    overlap = np.trace(target.conj().T @ achieved)
    fidelity = float(abs(overlap) ** 2 / dimension**2)
    return float(np.clip(fidelity, 0.0, 1.0))


def _low_pass(amplitudes):
    amplitudes = np.asarray(amplitudes, dtype=float)
    padded = np.pad(amplitudes, ((1, 1), (0, 0)), mode="edge")
    return 0.18 * padded[:-2] + 0.64 * padded[1:-1] + 0.18 * padded[2:]


def _normalized_score(fidelity, baseline_fidelity):
    denominator = max(1e-12, 1.0 - float(baseline_fidelity))
    return float(np.clip((float(fidelity) - float(baseline_fidelity)) / denominator, 0.0, 1.0))


def _variant_scores(instance, amplitudes):
    zero = np.zeros_like(amplitudes)
    variants = (
        ("nominal", 1.00, 0.0, False),
        ("underdrive_plus_detuning", 0.94, 1.0, True),
        ("overdrive_minus_detuning", 1.06, -1.0, True),
        ("positive_detuning", 1.00, 1.0, False),
        ("negative_detuning", 1.00, -1.0, False),
    )
    records = []
    for name, amplitude_scale, detuning_scale, filtered in variants:
        pulse = amplitudes * amplitude_scale
        zero_pulse = zero.copy()
        if filtered:
            pulse = _low_pass(pulse)
            zero_pulse = _low_pass(zero_pulse)
        drift = instance["drift"] + detuning_scale * instance["detuning"]
        achieved = _propagate(drift, instance["controls"], pulse, instance["dt"])
        baseline = _propagate(drift, instance["controls"], zero_pulse, instance["dt"])
        fidelity = _process_fidelity(instance["target"], achieved)
        baseline_fidelity = _process_fidelity(instance["target"], baseline)
        records.append({
            "variant": name,
            "process_fidelity": fidelity,
            "baseline_process_fidelity": baseline_fidelity,
            "score": _normalized_score(fidelity, baseline_fidelity),
        })
    return records


def _validate_pulse(value, instance):
    amplitudes = np.asarray(value, dtype=float)
    expected = (instance["n_steps"], len(instance["controls"]))
    if amplitudes.shape != expected:
        raise ValueError("pulse shape %r does not match %r" % (amplitudes.shape, expected))
    if np.any(~np.isfinite(amplitudes)):
        raise ValueError("pulse contains non-finite amplitudes")
    limit = float(instance["amplitude_limit"])
    if np.any(np.abs(amplitudes) > limit + 1e-12):
        raise ValueError("pulse amplitude exceeds the public hardware limit")
    return amplitudes


def _score_instance(design_pulse, instance):
    try:
        returned = design_pulse(
            instance["drift"].copy(),
            instance["controls"].copy(),
            instance["target"].copy(),
            instance["n_steps"],
            instance["dt"],
            instance["amplitude_limit"],
        )
        amplitudes = _validate_pulse(returned, instance)
        variants = _variant_scores(instance, amplitudes)
        nominal = variants[0]
        robust_score = float(min(row["score"] for row in variants[1:]))
        robust_fidelity = float(min(row["process_fidelity"] for row in variants[1:]))
        differences = np.diff(amplitudes, axis=0)
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": nominal["score"],
            "nominal_process_fidelity": nominal["process_fidelity"],
            "baseline_process_fidelity": nominal["baseline_process_fidelity"],
            "robustness_score": robust_score,
            "worst_shifted_process_fidelity": robust_fidelity,
            "pulse_rms": float(np.sqrt(np.mean(amplitudes**2))),
            "pulse_max_slew": float(np.max(np.abs(differences))) if len(differences) else 0.0,
            "per_variant": variants,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "nominal_process_fidelity": 0.0,
            "baseline_process_fidelity": 0.0,
            "robustness_score": 0.0,
            "worst_shifted_process_fidelity": 0.0,
        }


def evaluate(design_pulse):
    records = [_score_instance(design_pulse, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_score = float(np.mean([row["score"] for row in development]))
    development_robustness = float(np.mean([
        row["robustness_score"] for row in development
    ]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    heldout_robustness = float(np.mean([row["robustness_score"] for row in heldout]))
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    return {
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "development_score": development_score,
        "robustness_score": development_robustness,
        "development_validation_gap": development_score - development_robustness,
        "heldout_policy_score": heldout_score,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "mean_nominal_process_fidelity": float(np.mean([
            row["nominal_process_fidelity"] for row in development
        ])),
        "mean_worst_shifted_process_fidelity": float(np.mean([
            row["worst_shifted_process_fidelity"] for row in development
        ])),
        "per_instance": records,
    }
