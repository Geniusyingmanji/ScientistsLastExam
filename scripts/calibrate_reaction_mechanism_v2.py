#!/usr/bin/env python3
"""Calibrate ReactionMechanismFitting-v2 without using hidden-world labels."""

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
from scipy.linalg import expm
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/ChemicalKinetics/ReactionMechanismFitting"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402

R_GAS = 8.31446261815324


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("reaction_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load ReactionMechanismFitting-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _generator(rates, reaction_pairs, n_species):
    matrix = np.zeros((n_species, n_species), dtype=float)
    for rate, (source, target) in zip(rates, reaction_pairs):
        matrix[source, source] -= float(rate)
        matrix[target, source] += float(rate)
    return matrix


def classical_discover_mechanism(
    species_names, reaction_pairs, experiment, budget_units
):
    """Generic two-temperature sparse fit; intentionally lacks a misspecification test."""
    del budget_units
    n_species = len(species_names)
    n_reactions = len(reaction_pairs)
    times = np.asarray((0.0, 0.005, 0.015, 0.05, 0.15, 0.5, 2.0, 10.0))
    initial = np.asarray((0.52, 0.27, 0.14, 0.07))
    observed_species = np.asarray((1, 2))
    records = [
        experiment(345.0, initial, times, observed_species),
        experiment(465.0, initial, times, observed_species),
    ]

    def rates(vector, temperature):
        return np.exp(
            vector[:n_reactions]
            - vector[n_reactions:] * 10000.0 / (R_GAS * temperature)
        )

    def prediction(vector, record):
        matrix = _generator(
            rates(vector, float(record["temperature_k"])),
            reaction_pairs,
            n_species,
        )
        full = np.asarray([
            expm(matrix * float(time)) @ record["initial_concentrations"]
            for time in record["time_s"]
        ])
        return full[:, record["observed_species"]]

    def data_residual(vector):
        return np.concatenate([
            ((prediction(vector, record) - record["concentrations"]) / 0.005).ravel()
            for record in records
        ])

    def sparse_objective(vector):
        reference_rates = rates(vector, 405.0)
        sparsity = 0.7 * np.sqrt(reference_rates / (reference_rates + 0.025))
        return np.concatenate((data_residual(vector), sparsity))

    lower = np.concatenate((np.full(n_reactions, 5.0), np.full(n_reactions, 1.5)))
    upper = np.concatenate((np.full(n_reactions, 25.0), np.full(n_reactions, 9.0)))
    initial_vector = np.concatenate((
        np.full(n_reactions, 13.0), np.full(n_reactions, 4.5)
    ))
    fit = least_squares(
        sparse_objective,
        initial_vector,
        bounds=(lower, upper),
        max_nfev=300,
        x_scale="jac",
        xtol=2e-7,
        ftol=2e-7,
        gtol=2e-7,
    )
    support = rates(fit.x, 405.0) > 0.04
    active = np.flatnonzero(support)
    log_a = np.zeros(n_reactions)
    energy = np.zeros(n_reactions)

    if len(active):
        def unpack(reduced):
            vector = np.concatenate((
                np.full(n_reactions, 5.0), np.full(n_reactions, 9.0)
            ))
            vector[active] = reduced[:len(active)]
            vector[n_reactions + active] = reduced[len(active):]
            return vector

        reduced_initial = np.concatenate((
            fit.x[active], fit.x[n_reactions + active]
        ))
        reduced_lower = np.concatenate((
            np.full(len(active), 5.0), np.full(len(active), 1.5)
        ))
        reduced_upper = np.concatenate((
            np.full(len(active), 25.0), np.full(len(active), 9.0)
        ))
        refit = least_squares(
            lambda reduced: data_residual(unpack(reduced)),
            reduced_initial,
            bounds=(reduced_lower, reduced_upper),
            max_nfev=300,
            x_scale="jac",
            xtol=2e-8,
            ftol=2e-8,
            gtol=2e-8,
        )
        final = unpack(refit.x)
        log_a[active] = final[active]
        energy[active] = 10000.0 * final[n_reactions + active]
        residual = data_residual(final) * 0.005
    else:
        residual = data_residual(fit.x) * 0.005

    rmse = float(np.sqrt(np.mean(residual**2)))
    signal = float(np.sqrt(np.mean(np.concatenate([
        (record["concentrations"] - record["concentrations"][0]).ravel()
        for record in records
    ]) ** 2)))
    abstain = bool(signal < 0.012)
    return {
        "support": np.zeros(n_reactions, dtype=int) if abstain else support.astype(int),
        "log_pre_exponential": np.zeros(n_reactions) if abstain else log_a,
        "activation_energy_j_mol": np.zeros(n_reactions) if abstain else energy,
        "confidence": 0.0 if abstain else float(np.clip(1.0 - rmse / 0.012, 0.0, 1.0)),
        "abstain": abstain,
    }


def _always_abstain(species_names, reaction_pairs, experiment, budget_units):
    del budget_units
    n_species = len(species_names)
    n_reactions = len(reaction_pairs)
    experiment(
        405.0,
        np.full(n_species, 1.0 / n_species),
        np.asarray((0.0, 0.02, 0.08, 0.3, 1.0, 4.0)),
        [0],
    )
    return {
        "support": np.zeros(n_reactions, dtype=int),
        "log_pre_exponential": np.zeros(n_reactions),
        "activation_energy_j_mol": np.zeros(n_reactions),
        "confidence": 0.0,
        "abstain": True,
    }


def _identifiability_record(oracle, world, split, world_index):
    # This fixed truth-blind four-assay witness costs exactly 12 units.  It is not used by the
    # classical calibration policy; it proves that poor recovery is not forced by a rank defect.
    plan = (
        (340.0, (0.869340, 0.013857, 0.028699, 0.088104), (2,)),
        (383.3333333333333, (0.448655, 0.323744, 0.091540, 0.136061), (3,)),
        (426.6666666666667, (0.059858, 0.022165, 0.709448, 0.208529), (1,)),
        (470.0, (0.016988, 0.657827, 0.032028, 0.293157), (0,)),
    )
    times = np.asarray((0.0, 0.006, 0.02, 0.06, 0.18, 0.55, 1.8, 6.0))
    active = np.flatnonzero(world["support"])
    truth = np.concatenate((
        world["log_a"][active], world["activation_energy"][active] / 10000.0
    ))

    def observation(vector):
        log_a = world["log_a"].copy()
        energy = world["activation_energy"].copy()
        log_a[active] = vector[:len(active)]
        energy[active] = 10000.0 * vector[len(active):]
        values = []
        for temperature, initial, observed in plan:
            rates = oracle._rate_constants(
                log_a, energy, world["support"], temperature
            )
            simulated = oracle._linear_simulate(rates, np.asarray(initial), times)
            values.extend(simulated[:, observed].ravel())
        return np.asarray(values)

    jacobian = np.empty((len(observation(truth)), len(truth)))
    for column in range(len(truth)):
        step = 1e-4
        upper = truth.copy()
        lower = truth.copy()
        upper[column] += step
        lower[column] -= step
        jacobian[:, column] = (
            observation(upper) - observation(lower)
        ) / (2.0 * step)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1e-8))
    condition = float(singular[0] / singular[-1])
    return {
        "split": split,
        "world_index": world_index,
        "active_parameter_count": len(truth),
        "jacobian_shape": list(jacobian.shape),
        "jacobian_rank": rank,
        "condition_number": condition,
        "minimum_singular_value": float(singular[-1]),
        "assay_budget_units": 12,
        "passed": rank == len(truth) and condition < 1e5,
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(classical_discover_mechanism)

    exact_checks = []
    identifiability = []
    conservation = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                mechanism = oracle._mechanism_metrics(
                    world,
                    world["log_a"],
                    world["activation_energy"],
                    world["support"],
                    False,
                )
                interpolation = oracle._prediction_score(
                    world,
                    world["log_a"],
                    world["activation_energy"],
                    world["support"],
                    False,
                )
                extrapolation = oracle._prediction_score(
                    world,
                    world["log_a"],
                    world["activation_energy"],
                    world["support"],
                    True,
                )
                passed = (
                    mechanism["mechanism_score"] == 1.0
                    and interpolation == 1.0
                    and extrapolation == 1.0
                )
                identifiability.append(
                    _identifiability_record(oracle, world, split, index)
                )
            else:
                zeros = np.zeros(oracle.N_REACTIONS)
                mechanism = oracle._mechanism_metrics(
                    world, zeros, zeros, np.zeros(oracle.N_REACTIONS, dtype=bool), True
                )
                interpolation = oracle._prediction_score(
                    world, zeros, zeros, np.zeros(oracle.N_REACTIONS, dtype=bool), False
                )
                extrapolation = oracle._prediction_score(
                    world, zeros, zeros, np.zeros(oracle.N_REACTIONS, dtype=bool), True
                )
                passed = mechanism["mechanism_score"] == 1.0
            exact_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "mechanism_score": mechanism["mechanism_score"],
                "interpolation_prediction_score": interpolation,
                "extrapolation_prediction_score": extrapolation,
                "passed": passed,
            })

            rng = np.random.default_rng(world["seed"] + 9137)
            maximum_error = 0.0
            for _ in range(8):
                initial = rng.dirichlet(np.ones(oracle.N_SPECIES))
                times = np.sort(np.concatenate((
                    np.asarray((0.0,)), rng.uniform(0.001, 10.0, size=9)
                )))
                values = oracle._simulate(
                    world, float(rng.uniform(330.0, 480.0)), initial, times
                )
                maximum_error = max(
                    maximum_error,
                    float(np.max(np.abs(np.sum(values, axis=1) - 1.0))),
                )
            conservation.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "maximum_mass_balance_error": maximum_error,
                "passed": maximum_error < 2e-8,
            })

    # The key science-specific calibration: good interpolation can coexist with weak
    # mechanism recovery and false discovery under model misspecification.
    difficulty_passed = bool(
        0.3 <= classical["combined_score"] <= 0.8
        and 0.2 <= classical["robustness_score"] <= 0.8
        and classical["development_prediction_score"]
        > classical["combined_score"] + 0.15
        and classical["development_false_discovery_rate"] >= 0.5
    )
    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["valid"] == 1.0
        and classical["valid"] == 1.0
        and classical["heldout_feasibility_rate"] == 1.0
        and difficulty_passed
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in conservation)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_OR_WET_LAB_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "always_abstain_baseline": baseline,
        "truth_blind_classical_fit": classical,
        "exact_mechanism_or_refusal_checks": exact_checks,
        "four_assay_identifiability_checks": identifiability,
        "mass_conservation_checks": conservation,
        "difficulty_gate": {
            "classical_development_interval": [0.3, 0.8],
            "classical_heldout_interval": [0.2, 0.8],
            "minimum_prediction_mechanism_gap": 0.15,
            "minimum_development_false_discovery_rate": 0.5,
            "passed": difficulty_passed,
        },
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
