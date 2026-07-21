#!/usr/bin/env python3
"""Reproduce scientific-validity failures in the inverse/discovery candidate tranche."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _oracle(task_id: str):
    path = ROOT / "benchmarks" / task_id / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "inverse_audit_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _radiative_transfer():
    oracle = _oracle("AtmosphericScience/RadiativeTransferFit")
    truth = oracle._T_TRUE.copy()
    jacobian = np.zeros((oracle.N_CHANNELS, oracle.N_LAYERS), dtype=float)
    for layer in range(oracle.N_LAYERS):
        step = 0.1
        upper, lower = truth.copy(), truth.copy()
        upper[layer] += step
        lower[layer] -= step
        jacobian[:, layer] = (
            oracle._forward_model(upper) - oracle._forward_model(lower)
        ) / (2 * step)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    return {
        "task": "AtmosphericScience/RadiativeTransferFit",
        "admission": "quarantine",
        "defect": "ten radiances cannot identify a twenty-layer profile, yet selection directly rewards hidden fixed-profile RMSE rather than retrieval evidence",
        "jacobian_shape": list(jacobian.shape),
        "jacobian_rank": int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1e-10)),
        "condition_number_nonzero_block": float(singular[0] / singular[-1]),
        "observation_count": oracle.N_CHANNELS,
        "unknown_count": oracle.N_LAYERS,
        "passed": oracle.N_CHANNELS < oracle.N_LAYERS,
    }


def _chemical_kinetics():
    oracle = _oracle("ChemicalKinetics/ReactionMechanismFitting")
    oracle._gen_data()
    instant = {"A1": 1e20, "E1": 0.0, "A2": 1e20, "E2": 0.0}
    true_metrics = oracle.evaluate(lambda *_: dict(oracle._TRUE))
    instant_metrics = oracle.evaluate(lambda *_: instant)
    score_gap = abs(true_metrics["combined_score"] - instant_metrics["combined_score"])
    return {
        "task": "ChemicalKinetics/ReactionMechanismFitting",
        "admission": "quarantine",
        "defect": "all sampled reactions are effectively complete, so true Arrhenius parameters and an infinite-rate mechanism receive the same score",
        "true_parameter_score": float(true_metrics["combined_score"]),
        "infinite_rate_score": float(instant_metrics["combined_score"]),
        "absolute_score_gap": float(score_gap),
        "passed": score_gap < 1e-9,
    }


def _gravity():
    oracle = _oracle("Geophysics/GravityInversion")
    kernel, observation, truth = oracle.INSTANCES[0]
    signal = kernel @ truth
    signal_rms = float(np.sqrt(np.mean(signal**2)))
    ratio = signal_rms / oracle.NOISE_STD
    same_truth = bool(np.array_equal(oracle.INSTANCES[0][2], oracle.INSTANCES[1][2]))
    return {
        "task": "Geophysics/GravityInversion",
        "admission": "quarantine",
        "defect": "the synthetic gravity signal is far below declared noise and both instances reuse one fixed hidden body geometry",
        "kernel_shape": list(kernel.shape),
        "kernel_rank": int(np.linalg.matrix_rank(kernel)),
        "signal_rms": signal_rms,
        "noise_std": float(oracle.NOISE_STD),
        "signal_to_noise_ratio": ratio,
        "instances_share_exact_truth": same_truth,
        "passed": ratio < 0.1 and same_truth,
    }


def _ocean():
    oracle = _oracle("Oceanography/OceanCurrentInversion")
    clean = oracle._advect_drifters(oracle._U_TRUE, oracle._V_TRUE, oracle._INIT_POS)
    zero = oracle._advect_drifters(
        np.zeros((oracle.NX, oracle.NY)),
        np.zeros((oracle.NX, oracle.NY)),
        oracle._INIT_POS,
    )
    signal = float(np.sqrt(np.mean((clean - zero) ** 2)))
    noise = float(np.sqrt(np.mean((oracle._OBS_TRAJ - clean) ** 2)))
    truth_metrics = oracle.evaluate(
        lambda *_: {"u": oracle._U_TRUE, "v": oracle._V_TRUE}
    )
    return {
        "task": "Oceanography/OceanCurrentInversion",
        "admission": "quarantine",
        "defect": "streamfunction units make drifter displacement sub-metre while 1 km noise dominates, so even the true current scores approximately zero",
        "clean_signal_displacement_rms_m": signal,
        "noise_rms_m": noise,
        "noise_to_signal_ratio": noise / max(signal, 1e-30),
        "true_field_score": float(truth_metrics["combined_score"]),
        "passed": noise / max(signal, 1e-30) > 1000 and truth_metrics["combined_score"] < 1e-3,
    }


def _population_genetics():
    oracle = _oracle("PopulationGenetics/DemographicSFS")
    truth = oracle._TRUE_PARAMS.copy()
    jacobian = np.zeros((oracle.N_SAMPLE - 1, len(truth)), dtype=float)
    for index in range(len(truth)):
        step = max(1e-6, abs(truth[index]) * 1e-4)
        upper, lower = truth.copy(), truth.copy()
        upper[index] += step
        lower[index] -= step
        jacobian[:, index] = (
            oracle._expected_sfs_piecewise(upper)
            - oracle._expected_sfs_piecewise(lower)
        ) / (2 * step)
    alternative = np.array([1.0, 0.1, 100.0, 0.08, 0.001])
    identical = bool(np.array_equal(
        oracle._expected_sfs_piecewise(truth),
        oracle._expected_sfs_piecewise(alternative),
    ))
    return {
        "task": "PopulationGenetics/DemographicSFS",
        "admission": "quarantine",
        "defect": "the five-parameter surrogate has only two locally active columns and radically different current-size/time parameters produce identical SFS",
        "jacobian_rank": int(np.linalg.matrix_rank(jacobian)),
        "parameter_count": len(truth),
        "column_norms": [float(value) for value in np.linalg.norm(jacobian, axis=0)],
        "alternative_sfs_exactly_identical": identical,
        "passed": np.linalg.matrix_rank(jacobian) <= 2 and identical,
    }


def _rans():
    oracle = _oracle("Turbulence/RANSCalibration")
    keys = ["C_mu", "C_e1", "C_e2", "sigma_k", "sigma_e"]
    values = np.array([0.09, 1.44, 1.92, 1.0, 1.3])

    def profiles(vector):
        velocity, kinetic = oracle._predict_profiles(dict(zip(keys, vector)))
        return np.concatenate((velocity, kinetic))

    jacobian = np.zeros((2 * oracle.N_PTS, len(values)))
    for index in range(len(values)):
        step = 1e-5 * max(1.0, abs(values[index]))
        upper, lower = values.copy(), values.copy()
        upper[index] += step
        lower[index] -= step
        jacobian[:, index] = (profiles(upper) - profiles(lower)) / (2 * step)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1e-9))
    return {
        "task": "Turbulence/RANSCalibration",
        "admission": "quarantine",
        "defect": "the claimed DNS is an analytic log-law/TKE fit and the algebraic surrogate identifies at most three combinations of five constants",
        "jacobian_rank": rank,
        "parameter_count": len(values),
        "singular_values": [float(value) for value in singular],
        "passed": rank < len(values),
    }


def _waveform_inversion():
    oracle = _oracle("WavePropagation/SeismicWaveInversion")
    truth = oracle.evaluate(lambda _nx, _nz: oracle._V_TRUE)
    return {
        "task": "WavePropagation/SeismicWaveInversion",
        "admission": "quarantine",
        "defect": "the design function receives only grid dimensions, not observed waveforms or an experiment callback, so it can only guess one fixed hidden model",
        "entrypoint_receives_observations": False,
        "fixed_truth_score": float(truth["combined_score"]),
        "passed": truth["combined_score"] == 1.0,
    }


def audit() -> dict:
    records = [
        _radiative_transfer(), _chemical_kinetics(), _gravity(), _ocean(),
        _population_genetics(), _rans(), _waveform_inversion(),
    ]
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_ADMISSION_AUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "records": records,
        "summary": {
            "task_count": len(records),
            "reproduced_defect_count": sum(bool(row["passed"]) for row in records),
            "recommended_quarantine_count": sum(row["admission"] == "quarantine" for row in records),
        },
    }
    finalize_report_trust(report, all(row["passed"] for row in records))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
