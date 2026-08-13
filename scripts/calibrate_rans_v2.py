#!/usr/bin/env python3
"""Rebuild and audit the RANSCalibration-v2 DNS closure witnesses."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/RANSCalibration"
VERIFICATION = TASK / "verification"
sys.path.insert(0, str(ROOT))

from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


CALIBRATION_SEED = 260724
MAXIMUM_ITERATIONS = 400
POPULATION_SIZE = 16
RELATIVE_PARAMETER_STEP = 1.0e-5


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_oracle():
    sys.path.insert(0, str(VERIFICATION))
    try:
        spec = importlib.util.spec_from_file_location(
            "rans_v2_calibration_oracle", VERIFICATION / "evaluator.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load RANSCalibration-v2 oracle")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _nominal_loss(oracle, parameters, re_values):
    return float(np.mean([
        oracle._profile_metrics(parameters, re_tau)["raw_loss"]
        for re_tau in re_values
    ]))


def _robust_loss(oracle, parameters, re_values):
    factors = (1.0,) + tuple(1.0 + shift for shift in oracle.SHIFT_FACTORS)
    return float(max(
        oracle._profile_metrics(parameters, re_tau, factor)["raw_loss"]
        for re_tau in re_values for factor in factors
    ))


def _optimizer_record(oracle, objective, expected, seed):
    bounds = [tuple(row) for row in oracle.PARAMETER_BOUNDS]
    result = differential_evolution(
        objective,
        bounds,
        seed=seed,
        popsize=POPULATION_SIZE,
        maxiter=MAXIMUM_ITERATIONS,
        tol=1.0e-10,
        polish=True,
        workers=1,
        updating="immediate",
    )
    expected_loss = float(objective(expected))
    observed_loss = float(result.fun)
    return {
        "seed": int(seed),
        "optimizer": "scipy.optimize.differential_evolution",
        "population_size_multiplier": POPULATION_SIZE,
        "maximum_iterations": MAXIMUM_ITERATIONS,
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "success": bool(result.success),
        "message": str(result.message),
        "committed_parameters": [float(value) for value in expected],
        "committed_loss": expected_loss,
        "rebuilt_parameters": [float(value) for value in result.x],
        "rebuilt_loss": observed_loss,
        "committed_minus_rebuilt_loss": expected_loss - observed_loss,
        # Flat minimax corners can move parameters while preserving the loss.
        # The executable literal is accepted only when an independent global
        # screen cannot improve its declared objective materially.
        "passed": bool(expected_loss <= observed_loss + 2.0e-7),
    }


def _sensitivity_record(oracle):
    parameters = oracle.NOMINAL_REFERENCE_PARAMETERS.copy()

    def observation_vector(values):
        output = []
        for re_tau in oracle.DEVELOPMENT_RE_TAU:
            row = oracle.DNS_PROFILES[re_tau]
            indices = oracle.SAMPLE_INDICES[re_tau]
            mean_u, _mean_shear, reynolds_shear = oracle.closure_profiles(
                values, re_tau, row["y_plus"]
            )
            output.extend((mean_u[indices] / oracle.VELOCITY_SCALE).tolist())
            output.extend(
                (reynolds_shear[indices] / oracle.SHEAR_SCALE).tolist()
            )
        return np.asarray(output, dtype=float)

    jacobian = np.empty((len(observation_vector(parameters)), 4), dtype=float)
    ranges = oracle.PARAMETER_BOUNDS[:, 1] - oracle.PARAMETER_BOUNDS[:, 0]
    for index in range(4):
        step = ranges[index] * RELATIVE_PARAMETER_STEP
        upper, lower = parameters.copy(), parameters.copy()
        upper[index] += step
        lower[index] -= step
        jacobian[:, index] = (
            observation_vector(upper) - observation_vector(lower)
        ) / (2.0 * step)
    scaled = jacobian * ranges[np.newaxis, :]
    singular = np.linalg.svd(scaled, compute_uv=False)
    rank = int(np.linalg.matrix_rank(scaled, tol=singular[0] * 1.0e-9))
    return {
        "observation_count": int(jacobian.shape[0]),
        "parameter_count": int(jacobian.shape[1]),
        "parameter_scaled_singular_values": [float(value) for value in singular],
        "parameter_scaled_condition_number": float(singular[0] / singular[-1]),
        "jacobian_rank": rank,
        "passed": bool(rank == 4 and singular[0] / singular[-1] < 100.0),
    }


def build_report(rebuild=True):
    oracle = _load_oracle()
    data_document = json.loads(
        oracle.DATA_PATH.read_text(encoding="utf-8")
    )
    source = data_document["source"]
    data_checks = {
        "aggregate_sha256": _sha256(oracle.DATA_PATH),
        "expected_aggregate_sha256": oracle.DATA_SHA256,
        "doi": source.get("doi"),
        "concept_doi": source.get("concept_doi"),
        "license": source.get("license"),
        "authors": source.get("authors"),
        "re_tau": sorted(int(value) for value in data_document["profiles"]),
        "source_file_hash_groups": len(source.get("source_file_sha256", {})),
    }
    data_checks["passed"] = bool(
        data_checks["aggregate_sha256"] == oracle.DATA_SHA256
        and data_checks["doi"] == "10.5281/zenodo.5749302"
        and data_checks["concept_doi"] == "10.5281/zenodo.4916024"
        and data_checks["license"] == "CC-BY-4.0"
        and data_checks["re_tau"] == [180, 395, 590, 950]
        and data_checks["source_file_hash_groups"] == 4
        and len(data_checks["authors"]) == 4
    )

    baseline = oracle.evaluate(oracle.standard_closure)
    nominal = oracle.evaluate(oracle.reference_closure)
    robust = oracle.evaluate(oracle.robust_reference_closure)
    sensitivity = _sensitivity_record(oracle)
    invalid = {
        "wrong_length": oracle.evaluate(lambda: np.zeros(3)),
        "wrong_keys": oracle.evaluate(lambda: {
            "kappa": 0.41, "A_plus": 26.0,
            "outer_linear": 0.0, "extra": 0.0,
        }),
        "nonfinite": oracle.evaluate(lambda: np.full(4, np.nan)),
        "boolean": oracle.evaluate(lambda: [True, 26.0, 0.0, 0.0]),
        "complex": oracle.evaluate(lambda: np.ones(4) + 1j),
        "out_of_bounds": oracle.evaluate(lambda: [0.1, 26.0, 0.0, 0.0]),
    }
    invalid_passed = all(
        row["valid"] == 0.0
        and row["combined_score"] == 0.0
        and row["raw_score"] == 0.0
        for row in invalid.values()
    )
    physics_passed = all(
        row["physics_gate_passed"]
        and max(item["momentum_residual"] for item in row["per_condition"])
        <= 3.0e-15
        and min(item["minimum_mean_shear_plus"] for item in row["per_condition"])
        >= 0.0
        and min(item["minimum_eddy_shear_plus"] for item in row["per_condition"])
        >= 0.0
        for row in (baseline, nominal, robust)
    )
    witness_passed = bool(
        baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["heldout_policy_score"] == 0.0
        and baseline["heldout_robustness_score"] == 0.0
        and nominal["combined_score"] > 0.999999
        and 0.80 < nominal["robustness_score"] < 0.95
        and 0.35 < nominal["heldout_policy_score"] < 0.70
        and 0.20 < nominal["heldout_robustness_score"] < 0.60
        and robust["robustness_score"] > 0.999999
        and robust["combined_score"] > 0.90
        and robust["heldout_policy_score"] < nominal["heldout_policy_score"]
        and robust["heldout_robustness_score"] < 0.05
    )

    optimizer_checks = []
    if rebuild:
        optimizer_checks = [
            _optimizer_record(
                oracle,
                lambda values: _nominal_loss(
                    oracle, values, oracle.DEVELOPMENT_RE_TAU
                ),
                oracle.NOMINAL_REFERENCE_PARAMETERS,
                CALIBRATION_SEED,
            ),
            _optimizer_record(
                oracle,
                lambda values: _robust_loss(
                    oracle, values, oracle.DEVELOPMENT_RE_TAU
                ),
                oracle.ROBUST_REFERENCE_PARAMETERS,
                CALIBRATION_SEED + 1,
            ),
            _optimizer_record(
                oracle,
                lambda values: _nominal_loss(
                    oracle, values, oracle.HELDOUT_RE_TAU
                ),
                oracle.HELDOUT_NOMINAL_REFERENCE_PARAMETERS,
                CALIBRATION_SEED + 2,
            ),
            _optimizer_record(
                oracle,
                lambda values: _robust_loss(
                    oracle, values, oracle.HELDOUT_RE_TAU
                ),
                oracle.HELDOUT_ROBUST_REFERENCE_PARAMETERS,
                CALIBRATION_SEED + 3,
            ),
        ]
    optimizer_passed = bool(
        rebuild and len(optimizer_checks) == 4
        and all(row["passed"] for row in optimizer_checks)
    )
    execution_passed = bool(
        oracle.RANS_CALIBRATION_V2
        and tuple(oracle.DEVELOPMENT_RE_TAU) == (180, 395)
        and tuple(oracle.HELDOUT_RE_TAU) == (590, 950)
        and data_checks["passed"]
        and sensitivity["passed"]
        and invalid_passed
        and physics_passed
        and witness_passed
        and optimizer_passed
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "ALGEBRAIC_CHANNEL_CLOSURE_TASK_CALIBRATION_NOT_GENERAL_RANS_"
            "SEPARATED_FLOW_EXPERIMENT_OR_DISCOVERY_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Turbulence/RANSCalibration",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                VERIFICATION / "closure_model.py",
                VERIFICATION / "evaluator.py", oracle.DATA_PATH,
            )
        },
        "data_provenance_checks": data_checks,
        "identifiability": sensitivity,
        "witness_metrics": {
            "baseline": baseline,
            "nominal": nominal,
            "robust": robust,
        },
        "invalid_artifact_checks": invalid,
        "invalid_artifact_checks_passed": invalid_passed,
        "physics_checks_passed": physics_passed,
        "witness_checks_passed": witness_passed,
        "optimizer_rebuild_checks": optimizer_checks,
        "optimizer_rebuild_checks_passed": optimizer_passed,
        "limitations": [
            "The four-parameter algebraic closure does not solve k-epsilon, Reynolds-stress or other turbulence transport equations.",
            "Only fully developed plane-channel mean velocity and Reynolds shear are scored; spectra, higher moments, anisotropy and transient dynamics are absent.",
            "Re_tau 590 and 950 test Reynolds-number transfer within the same flow family, not geometry or separated-flow generalization.",
            "Fixed public DNS profiles require server-held flow families and independent CFD review for population claims.",
            "Task calibration does not measure GPT-5.5, feedback causality, universal closure validity or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(rebuild=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "passed": report["passed"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
