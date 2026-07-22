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

from calibrate_reaction_mechanism_v2 import (
    _always_abstain as reaction_always_abstain,
    _identifiability_record as reaction_identifiability_record,
    classical_discover_mechanism,
)
from calibrate_gravity_v2 import (
    _always_abstain as gravity_always_abstain,
    _identifiability_record as gravity_identifiability_record,
    classical_discover_bodies,
)
from calibrate_ocean_current_v2 import (
    _always_abstain as ocean_always_abstain,
    _clean_plan_records as ocean_clean_plan_records,
    _fit_observations as ocean_fit_observations,
    _nonlinear_library_fit as ocean_nonlinear_library_fit,
    _trajectory_identifiability as ocean_identifiability_record,
    classical_discover_currents,
)

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
    baseline = oracle.evaluate(reaction_always_abstain)
    classical = oracle.evaluate(classical_discover_mechanism)
    rank_checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                rank_checks.append(reaction_identifiability_record(
                    oracle, world, split, index
                ))
    passed = bool(
        baseline["combined_score"] == 0.0
        and 0.3 <= classical["combined_score"] <= 0.8
        and classical["development_prediction_score"]
        > classical["combined_score"] + 0.15
        and classical["development_false_discovery_rate"] >= 0.5
        and all(row["passed"] for row in rank_checks)
    )
    return {
        "task": "ChemicalKinetics/ReactionMechanismFitting",
        "admission": "candidate",
        "resolved_defect": "v2 replaces effectively complete full-state trajectories with charged partial-species active assays, sparse topology and Arrhenius rate-curve recovery, null/model-inadequacy refusal and held-out topologies",
        "always_abstain_score": float(baseline["combined_score"]),
        "classical_mechanism_score": float(classical["combined_score"]),
        "classical_prediction_score": float(
            classical["development_prediction_score"]
        ),
        "classical_false_discovery_rate": float(
            classical["development_false_discovery_rate"]
        ),
        "full_rank_in_library_worlds": sum(row["passed"] for row in rank_checks),
        "in_library_world_count": len(rank_checks),
        "passed": passed,
    }


def _gravity():
    oracle = _oracle("Geophysics/GravityInversion")
    baseline = oracle.evaluate(gravity_always_abstain)
    classical = oracle.evaluate(classical_discover_bodies)
    rank_checks = []
    signals = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                rank_checks.append(gravity_identifiability_record(
                    oracle, world, split, index
                ))
                field = oracle._world_field(
                    world, np.linspace(0.0, 10000.0, 101), 0.0
                )
                signals.append(float(np.sqrt(np.mean(field**2))) / world["noise"])
    passed = bool(
        baseline["combined_score"] == 0.0
        and 0.3 <= classical["combined_score"] <= 0.85
        and classical["development_prediction_score"]
        > classical["combined_score"] + 0.10
        and classical["development_false_discovery_rate"] == 0.0
        and all(row["passed"] for row in rank_checks)
        and min(signals) > 10.0
    )
    return {
        "task": "Geophysics/GravityInversion",
        "admission": "candidate",
        "resolved_defect": "v2 replaces two noise-dominated duplicate grids with charged multi-height survey design, seven procedural rectangular-body topologies, null and observationally resolvable out-of-library worlds, external-field-equivalent matching and held-out noise shifts",
        "always_abstain_score": float(baseline["combined_score"]),
        "classical_mechanism_score": float(classical["combined_score"]),
        "classical_prediction_score": float(
            classical["development_prediction_score"]
        ),
        "classical_false_discovery_rate": float(
            classical["development_false_discovery_rate"]
        ),
        "minimum_in_library_signal_to_noise_ratio": min(signals),
        "full_rank_in_library_worlds": sum(row["passed"] for row in rank_checks),
        "in_library_world_count": len(rank_checks),
        "passed": passed,
    }


def _ocean():
    oracle = _oracle("Oceanography/OceanCurrentInversion")
    baseline = oracle.evaluate(ocean_always_abstain)
    classical = oracle.evaluate(classical_discover_currents)
    rank_checks = []
    misspecified_checks = []
    noise_label_blind_checks = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        supported_noise = {
            float(spec[2]) for spec in specs if spec[3] == "in_library"
        }
        unsupported_noise = {
            float(spec[2]) for spec in specs if spec[3] != "in_library"
        }
        noise_label_blind_checks.append({
            "split": split,
            "supported_noise_std_m": sorted(supported_noise),
            "unsupported_noise_std_m": sorted(unsupported_noise),
            "passed": unsupported_noise.issubset(supported_noise),
        })
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                rank_checks.append(ocean_identifiability_record(
                    oracle, world, split, index
                ))
            elif world["kind"] == "misspecified":
                linear_fit = ocean_fit_observations(
                    oracle.MODE_SPECIFICATIONS,
                    ocean_clean_plan_records(oracle, world),
                )
                nonlinear_best, _start_fits = ocean_nonlinear_library_fit(
                    oracle, world
                )
                nonlinear_values = [
                    item["reduced_chi2"] for item in _start_fits
                ]
                nonlinear_spread = max(nonlinear_values) - min(
                    nonlinear_values
                )
                misspecified_checks.append({
                    "split": split,
                    "approximate_velocity_residual_per_dof": (
                        linear_fit["approximate_velocity_residual_per_dof"]
                    ),
                    "nonlinear_trajectory_reduced_chi2": (
                        nonlinear_best["reduced_chi2"]
                    ),
                    "passed": bool(
                        linear_fit[
                            "approximate_velocity_residual_per_dof"
                        ] > 3.0
                        and nonlinear_best["reduced_chi2"] > 3.0
                        and nonlinear_spread < 1e-5
                        and all(item["success"] for item in _start_fits)
                        and all(
                            item["minimum_boundary_margin_m"] > 0.0
                            for item in _start_fits
                        )
                    ),
                })
    passed = bool(
        oracle.N_MODES == 30
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and 0.35 <= classical["combined_score"] <= 0.85
        and 0.20 <= classical["robustness_score"] <= 0.75
        and classical["combined_score"]
        > classical["robustness_score"] + 0.15
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and all(row["passed"] for row in rank_checks)
        and all(row["passed"] for row in misspecified_checks)
        and all(row["passed"] for row in noise_label_blind_checks)
    )
    return {
        "task": "Oceanography/OceanCurrentInversion",
        "admission": "candidate",
        "resolved_defect": "v2 replaces the sub-metre fixed-field inversion with charged release-position/phase/time design, a thirty-mode divergence-free current library, null and resolvable out-of-library refusal, trajectory/field extrapolation and shifted-noise held-out worlds",
        "public_mode_count": oracle.N_MODES,
        "always_abstain_score": float(baseline["combined_score"]),
        "classical_mechanism_score": float(classical["combined_score"]),
        "classical_heldout_mechanism_score": float(
            classical["robustness_score"]
        ),
        "classical_development_false_discovery_rate": float(
            classical["development_false_discovery_rate"]
        ),
        "classical_heldout_false_discovery_rate": float(
            classical["heldout_false_discovery_rate"]
        ),
        "full_rank_in_library_worlds": sum(
            row["passed"] for row in rank_checks
        ),
        "in_library_world_count": len(rank_checks),
        "noise_label_blind_checks": noise_label_blind_checks,
        "minimum_misspecified_approximate_velocity_residual_per_dof": min(
            row["approximate_velocity_residual_per_dof"]
            for row in misspecified_checks
        ),
        "minimum_misspecified_nonlinear_trajectory_reduced_chi2": min(
            row["nonlinear_trajectory_reduced_chi2"]
            for row in misspecified_checks
        ),
        "passed": passed,
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
            "passed_check_count": sum(bool(row["passed"]) for row in records),
            "recommended_quarantine_count": sum(row["admission"] == "quarantine" for row in records),
            "recommended_candidate_count": sum(row["admission"] == "candidate" for row in records),
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
