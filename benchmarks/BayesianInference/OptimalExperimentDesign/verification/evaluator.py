"""Trusted oracle for procedural discrete D-optimal experimental design.

The submitted program receives a candidate grid and a local sensitivity/design matrix.  It
must allocate a finite number of measurements (repetitions are allowed).  Development and
shifted-validation families are evaluated separately; only development D-efficiency is the
selection metric.
"""

from __future__ import annotations

import math

import numpy as np


# A 1e-4 equivalence gap gives a documented <0.01% approximate-design certificate while
# keeping oracle cold-start below a few seconds on the largest procedural instance.
REFERENCE_TOLERANCE = 1e-4
MAX_REFERENCE_ITERATIONS = 5000


def _scaled_columns(matrix):
    """Whiten parameter columns without changing the D-optimal allocation.

    D-efficiency and the maximizing design are invariant under any nonsingular parameter
    transformation.  Whitening is essential for decay/saturation sensitivities whose raw
    information matrices otherwise exceed 1e13 condition number in double precision.
    """
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or np.any(~np.isfinite(matrix)):
        raise ValueError("sensitivity matrix must be finite and two-dimensional")
    left, singular, right = np.linalg.svd(matrix, full_matrices=False)
    del right
    if singular[-1] <= singular[0] * 1e-12:
        raise ValueError("sensitivity parameterization is numerically rank deficient")
    # U * sqrt(n) has identity uniform-design information.  It equals the original matrix
    # times an invertible right transform, so candidate experiment rows retain their meaning.
    return left * math.sqrt(matrix.shape[0])


def _legendre(n_points, n_parameters, warp=0.0):
    coordinate = np.linspace(-1.0, 1.0, int(n_points))
    physical = coordinate + float(warp) * (coordinate**3 - coordinate)
    matrix = np.polynomial.legendre.legvander(physical, int(n_parameters) - 1)
    return coordinate, _scaled_columns(matrix)


def _fourier(n_points, n_parameters, frequency_scale=1.0):
    coordinate = np.linspace(-1.0, 1.0, int(n_points))
    columns = [np.ones_like(coordinate)]
    harmonic = 1
    while len(columns) < int(n_parameters):
        columns.append(np.sin(math.pi * harmonic * frequency_scale * coordinate))
        if len(columns) < int(n_parameters):
            columns.append(np.cos(math.pi * harmonic * frequency_scale * coordinate))
        harmonic += 1
    return coordinate, _scaled_columns(np.column_stack(columns))


def _decay(n_points, rates, include_offset=True):
    coordinate = np.linspace(0.0, 4.0, int(n_points))
    columns = [np.ones_like(coordinate)] if include_offset else []
    for rate in rates:
        # Local sensitivities of exponential components to amplitude and rate.
        columns.append(np.exp(-float(rate) * coordinate))
        columns.append(-coordinate * np.exp(-float(rate) * coordinate))
    return coordinate, _scaled_columns(np.column_stack(columns))


def _saturation(n_points, constants):
    coordinate = np.geomspace(0.01, 30.0, int(n_points))
    columns = [np.ones_like(coordinate)]
    for constant in constants:
        denominator = float(constant) + coordinate
        columns.append(coordinate / denominator)
        columns.append(-coordinate / denominator**2)
    return coordinate, _scaled_columns(np.column_stack(columns))


def _information(matrix, weights):
    return matrix.T @ (np.asarray(weights, dtype=float)[:, None] * matrix)


def _logdet(information):
    sign, value = np.linalg.slogdet(np.asarray(information, dtype=float))
    if sign <= 0 or not np.isfinite(value):
        return -math.inf
    return float(value)


def _reference_design(matrix):
    """Compute an approximate-design upper reference using multiplicative updates.

    At convergence the Kiefer--Wolfowitz sensitivity bound is at most p(1+tol).  The
    resulting fractional design is a certified near-optimum: the exact optimum can exceed its
    determinant only within the stated equivalence tolerance.
    """
    matrix = np.asarray(matrix, dtype=float)
    n_points, n_parameters = matrix.shape
    weights = np.full(n_points, 1.0 / n_points, dtype=float)
    maximum_sensitivity = math.inf
    iterations = 0
    for iterations in range(1, MAX_REFERENCE_ITERATIONS + 1):
        information = _information(matrix, weights)
        try:
            inverse = np.linalg.inv(information)
        except np.linalg.LinAlgError as exc:
            raise ValueError("reference information matrix is singular") from exc
        sensitivity = np.einsum("ij,jk,ik->i", matrix, inverse, matrix)
        maximum_sensitivity = float(np.max(sensitivity))
        if maximum_sensitivity <= n_parameters * (1.0 + REFERENCE_TOLERANCE):
            break
        weights *= sensitivity / n_parameters
        weights /= np.sum(weights)
    information = _information(matrix, weights)
    return {
        "weights": weights,
        "logdet": _logdet(information),
        "iterations": iterations,
        "maximum_sensitivity": maximum_sensitivity,
        "equivalence_gap": maximum_sensitivity - n_parameters,
        "converged": maximum_sensitivity <= n_parameters * (1.0 + REFERENCE_TOLERANCE),
    }


def _make_instance(name, split, family, coordinate, matrix, n_measurements):
    coordinate = np.asarray(coordinate, dtype=float)
    matrix = np.asarray(matrix, dtype=float)
    if coordinate.ndim != 1 or matrix.ndim != 2 or matrix.shape[0] != len(coordinate):
        raise ValueError("invalid procedural instance")
    if matrix.shape[1] > int(n_measurements):
        raise ValueError("measurement budget cannot support full rank")
    if np.linalg.matrix_rank(matrix) != matrix.shape[1]:
        raise ValueError("procedural sensitivity matrix is rank deficient")
    reference = _reference_design(matrix)
    if not reference["converged"]:
        raise RuntimeError("D-optimal reference failed equivalence-theorem check")
    baseline_indices = np.arange(int(n_measurements), dtype=int)
    baseline = _allocation_metrics(matrix, baseline_indices, reference["logdet"])
    return {
        "name": str(name),
        "split": str(split),
        "family": str(family),
        "coordinate": coordinate,
        "matrix": matrix,
        "n_measurements": int(n_measurements),
        "reference": reference,
        "baseline_efficiency": baseline["efficiency"],
    }


def _allocation_metrics(matrix, indices, reference_logdet):
    matrix = np.asarray(matrix, dtype=float)
    indices = np.asarray(indices, dtype=int)
    empirical = matrix[indices].T @ matrix[indices] / len(indices)
    logdet = _logdet(empirical)
    n_parameters = matrix.shape[1]
    if not math.isfinite(logdet):
        efficiency = 0.0
    else:
        efficiency = float(math.exp((logdet - float(reference_logdet)) / n_parameters))
        # A converged approximate reference is within REFERENCE_TOLERANCE of the theoretical
        # optimum, not literally an exact upper value.  Permit only that certified numerical
        # slack; larger excess signals a broken reference.
        if efficiency > 1.0 + 2.0 * REFERENCE_TOLERANCE:
            raise RuntimeError("finite allocation exceeds certified D-optimal reference")
        efficiency = float(np.clip(efficiency, 0.0, 1.0))
    return {"logdet": logdet, "efficiency": efficiency}


def _instances():
    definitions = []
    definitions.append(("dev_legendre_5", "development", "legendre", *_legendre(121, 5), 14))
    definitions.append(("dev_legendre_8", "development", "legendre", *_legendre(181, 8, 0.08), 22))
    definitions.append(("dev_fourier_7", "development", "fourier", *_fourier(161, 7), 20))
    definitions.append(("dev_fourier_10", "development", "fourier", *_fourier(241, 10, 0.92), 28))
    definitions.append(("dev_decay_7", "development", "exponential_decay", *_decay(181, [0.24, 0.85, 2.4]), 20))
    definitions.append(("dev_saturation_7", "development", "saturation", *_saturation(181, [0.18, 1.7, 11.0]), 20))

    definitions.append(("val_legendre_11", "validation", "legendre_shift", *_legendre(277, 11, -0.13), 32))
    definitions.append(("val_fourier_12", "validation", "fourier_shift", *_fourier(293, 12, 1.17), 34))
    definitions.append(("val_decay_9", "validation", "decay_rate_shift", *_decay(251, [0.11, 0.38, 1.2, 3.6]), 28))
    definitions.append(("val_saturation_9", "validation", "scale_shift", *_saturation(257, [0.05, 0.42, 3.4, 22.0]), 28))
    return tuple(_make_instance(*definition) for definition in definitions)


INSTANCES = _instances()
DEVELOPMENT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "development")
VALIDATION_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "validation")


def _validate_indices(value, n_points, n_measurements):
    raw = np.asarray(value)
    if raw.shape != (int(n_measurements),):
        raise ValueError("return exactly n_measurements one-dimensional indices")
    if raw.dtype.kind not in "iu":
        numeric = np.asarray(raw, dtype=float)
        if not np.all(np.isfinite(numeric)) or not np.all(numeric == np.rint(numeric)):
            raise ValueError("experiment indices must be finite integers")
        raw = np.rint(numeric).astype(np.int64)
    else:
        raw = raw.astype(np.int64, copy=False)
    if np.any(raw < 0) or np.any(raw >= int(n_points)):
        raise ValueError("experiment index outside the candidate grid")
    return raw


def _score_instance(select_designs, instance):
    try:
        returned = select_designs(
            instance["coordinate"].copy(),
            instance["matrix"].copy(),
            instance["n_measurements"],
        )
        indices = _validate_indices(
            returned, len(instance["coordinate"]), instance["n_measurements"]
        )
        allocation = _allocation_metrics(
            instance["matrix"], indices, instance["reference"]["logdet"]
        )
        baseline = float(instance["baseline_efficiency"])
        denominator = max(1e-12, 1.0 - baseline)
        normalized = float(np.clip((allocation["efficiency"] - baseline) / denominator, 0.0, 1.0))
        return {
            "name": instance["name"],
            "family": instance["family"],
            "split": instance["split"],
            "valid": True,
            "score": normalized,
            "d_efficiency": allocation["efficiency"],
            "baseline_d_efficiency": baseline,
            "unique_designs": int(len(np.unique(indices))),
            "n_measurements": instance["n_measurements"],
            "n_parameters": int(instance["matrix"].shape[1]),
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "family": instance["family"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "d_efficiency": 0.0,
            "baseline_d_efficiency": float(instance["baseline_efficiency"]),
            "n_measurements": instance["n_measurements"],
            "n_parameters": int(instance["matrix"].shape[1]),
        }


def evaluate(select_designs):
    records = [_score_instance(select_designs, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    validation = [row for row in records if row["split"] == "validation"]
    development_score = float(np.mean([row["score"] for row in development]))
    validation_score = float(np.mean([row["score"] for row in validation]))
    development_valid = sum(bool(row["valid"]) for row in development)
    validation_valid = sum(bool(row["valid"]) for row in validation)
    return {
        # Only these development-derived fields enter the search-visible allowlist.
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        # All following fields are evaluator-only under the default-sealed metric protocol.
        "development_score": development_score,
        "robustness_score": validation_score,
        "development_validation_gap": development_score - validation_score,
        "validation_feasibility_rate": validation_valid / len(validation),
        "mean_development_d_efficiency": float(np.mean([
            row["d_efficiency"] for row in development
        ])),
        "mean_validation_d_efficiency": float(np.mean([
            row["d_efficiency"] for row in validation
        ])),
        "per_instance": records,
    }
