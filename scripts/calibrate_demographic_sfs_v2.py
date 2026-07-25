#!/usr/bin/env python3
"""Calibrate DemographicSFS-v2 with independent coalescent calculations."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/PopulationGenetics/DemographicSFS"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


REFERENCE_DESIGN = ((20, 4), (48, 3), (64, 2))
UNDERINFORMATIVE_DESIGN = ((12, 1),)
EQUAL_BUDGET_SMALL_SAMPLE_DESIGN = ((12, 4),) * 8
REFUSAL_REDUCED_DEVIANCE = 2.25


def _file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("demographic_sfs_v2_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _always_abstain(parameter_names, *_args):
    return {
        "parameters": np.zeros(len(parameter_names), dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }


def _poisson_residual(observed, expected):
    observed = np.asarray(observed, dtype=float)
    expected = np.maximum(np.asarray(expected, dtype=float), 1.0e-15)
    term = 2.0 * expected
    positive = observed > 0.0
    term = np.asarray(term, dtype=float)
    term[positive] = 2.0 * (
        expected[positive] - observed[positive]
        + observed[positive] * np.log(observed[positive] / expected[positive])
    )
    return np.sign(observed - expected) * np.sqrt(np.maximum(term, 0.0))


def _fit_records(oracle, records, parameter_bounds):
    bounds = np.asarray(parameter_bounds, dtype=float)
    lower, upper = bounds[:, 0], bounds[:, 1]
    starts = (
        0.5 * (lower + upper),
        np.asarray((0.45, 2.0, 0.09, 0.40)),
        np.asarray((2.2, 0.45, 0.08, 0.36)),
    )

    def residual(parameters):
        values = []
        for record in records:
            expected = (
                float(record["expected_count_scale"])
                * oracle.public_expected_sfs(record["n_sample"], parameters)
            )
            values.append(_poisson_residual(
                record["unfolded_sfs_counts"], expected
            ))
        return np.concatenate(values)

    best = None
    for initial in starts:
        fit = least_squares(
            residual, initial, bounds=(lower, upper), x_scale="jac",
            max_nfev=900, ftol=1.0e-10, xtol=1.0e-10, gtol=1.0e-10,
        )
        deviance = float(np.sum(fit.fun * fit.fun))
        if best is None or deviance < best[0]:
            best = deviance, fit
    deviance, fit = best
    degrees_of_freedom = len(fit.fun) - len(fit.x)
    singular = np.linalg.svd(fit.jac * fit.x[None, :], compute_uv=False)
    return {
        "parameters": fit.x.copy(),
        "deviance": deviance,
        "degrees_of_freedom": int(degrees_of_freedom),
        "reduced_deviance": deviance / max(degrees_of_freedom, 1),
        "log_jacobian_rank": int(np.linalg.matrix_rank(
            fit.jac * fit.x[None, :]
        )),
        "log_jacobian_condition_number": float(singular[0] / singular[-1]),
        "success": bool(fit.success),
        "n_function_evaluations": int(fit.nfev),
    }


def _confidence(reduced_deviance, degrees_of_freedom):
    standard_error = math.sqrt(2.0 / max(int(degrees_of_freedom), 1))
    return float(np.clip(
        abs(float(reduced_deviance) - REFUSAL_REDUCED_DEVIANCE)
        / max(3.0 * standard_error, 1.0e-12), 0.0, 1.0
    ))


def _classical_policy(oracle, design):
    def infer_demography(
        parameter_names, parameter_bounds, allowed_sample_sizes, sequence,
        budget_units,
    ):
        del parameter_names, allowed_sample_sizes, budget_units
        records = [sequence(n_sample, replicates) for n_sample, replicates in design]
        fit = _fit_records(oracle, records, parameter_bounds)
        total_count = float(sum(np.sum(record["unfolded_sfs_counts"]) for record in records))
        abstain = bool(
            total_count < 5.0
            or fit["reduced_deviance"] > REFUSAL_REDUCED_DEVIANCE
        )
        return {
            "parameters": fit["parameters"],
            "confidence": _confidence(
                fit["reduced_deviance"], fit["degrees_of_freedom"]
            ),
            "abstain": abstain,
        }
    return infer_demography


class _ExactReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.call_index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(self.oracle.HELDOUT_SPECS)
        world = self.oracle._world(specs[self.call_index])
        self.call_index += 1
        return self.oracle._reference_submission(world)


def _independent_ode_sfs(oracle, n_sample, sizes, epoch_ends):
    """Independent occupancy integration using solve_ivp, not matrix exponentials."""
    generator, descendants = oracle._coalescent_matrices(n_sample)
    state_count = len(generator)
    initial = np.zeros(2 * state_count, dtype=float)
    initial[0] = 1.0
    state = initial
    start = 0.0
    finite_ends = list(epoch_ends)
    # At the last finite epoch, a tail of 30 maximum population-size units makes
    # residual transient mass negligible for k=2 (exp(-30)).
    final_end = (finite_ends[-1] if finite_ends else 0.0) + 30.0 * max(sizes)
    ends = finite_ends + [final_end]
    for size, end in zip(sizes, ends):
        transition_generator = generator / float(size)

        def derivative(_time, value):
            probability = value[:state_count]
            return np.concatenate((
                probability @ transition_generator,
                probability,
            ))

        solution = solve_ivp(
            derivative, (start, end), state, method="DOP853",
            rtol=2.0e-11, atol=2.0e-13,
        )
        state = solution.y[:, -1]
        start = end
    occupancy = state[state_count:]
    return 0.5 * occupancy @ descendants


def _physics_checks(oracle):
    checks = []
    cases = (
        (12, (1.0,), ()),
        (20, (0.55, 1.8, 1.0), (0.10, 0.42)),
        (32, (2.4, 0.45, 1.0), (0.07, 0.36)),
        (48, (0.42, 2.1, 0.38, 1.0), (0.04, 0.12, 0.40)),
    )
    for index, (n_sample, sizes, epoch_ends) in enumerate(cases):
        evaluator = oracle.expected_sfs_piecewise(n_sample, sizes, epoch_ends)
        independent = _independent_ode_sfs(
            oracle, n_sample, sizes, epoch_ends
        )
        error = float(np.max(np.abs(evaluator - independent)))
        checks.append({
            "case": index,
            "n_sample": n_sample,
            "maximum_absolute_error": error,
            "passed": error < 2.0e-10,
        })
    constant_checks = []
    for n_sample in (3, 12, 32, 64):
        expected = oracle.expected_sfs_piecewise(n_sample, (1.0,), ())
        analytic = 1.0 / np.arange(1, n_sample, dtype=float)
        error = float(np.max(np.abs(expected - analytic)))
        constant_checks.append({
            "n_sample": n_sample,
            "maximum_absolute_error": error,
            "passed": error < 2.0e-14,
        })
    return checks, constant_checks


def _identifiability_record(oracle, world, split, index):
    truth = np.asarray(world["parameters"], dtype=float)
    columns = []
    for parameter_index in range(len(truth)):
        step = truth[parameter_index] * 1.0e-5
        upper, lower = truth.copy(), truth.copy()
        upper[parameter_index] += step
        lower[parameter_index] -= step
        values = []
        for n_sample, replicates in REFERENCE_DESIGN:
            scale = oracle.THETA_PER_PANEL * replicates
            expected = scale * oracle.public_expected_sfs(n_sample, truth)
            derivative = scale * (
                oracle.public_expected_sfs(n_sample, upper)
                - oracle.public_expected_sfs(n_sample, lower)
            ) / (2.0 * step)
            values.extend(derivative / np.sqrt(np.maximum(expected, 1.0)))
        columns.append(values)
    jacobian = np.asarray(columns, dtype=float).T * truth[None, :]
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1.0e-10))
    return {
        "split": split,
        "world_index": int(index),
        "log_parameter_jacobian_shape": list(jacobian.shape),
        "log_parameter_jacobian_rank": rank,
        "condition_number": float(singular[0] / singular[-1]),
        "minimum_singular_value": float(singular[-1]),
        "passed": bool(rank == len(truth) and singular[-1] > 0.08),
    }


def _clean_misspecification_record(oracle, world, split, index):
    records = []
    for n_sample, replicates in REFERENCE_DESIGN:
        records.append({
            "n_sample": n_sample,
            "unfolded_sfs_counts": (
                oracle.THETA_PER_PANEL * replicates
                * oracle._clean_sfs(world, n_sample)
            ),
            "expected_count_scale": oracle.THETA_PER_PANEL * replicates,
        })
    fit = _fit_records(oracle, records, oracle.PARAMETER_BOUNDS)
    expected_noisy_reduced_deviance = 1.0 + fit["reduced_deviance"]
    return {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "best_public_parameters": fit["parameters"].tolist(),
        "clean_structural_reduced_deviance": float(fit["reduced_deviance"]),
        "expected_noisy_reduced_deviance": float(expected_noisy_reduced_deviance),
        "refusal_threshold": REFUSAL_REDUCED_DEVIANCE,
        "fit_success": fit["success"],
        "passed": bool(
            fit["success"]
            and expected_noisy_reduced_deviance > REFUSAL_REDUCED_DEVIANCE
        ),
    }


def _near_equivalence_limits(oracle):
    """Record complex histories that finite SFS panels cannot safely reject."""
    synthetic = (
        ("four_epoch", {
            n_sample: oracle.expected_sfs_piecewise(
                n_sample, (0.24, 3.60, 0.31, 1.0),
                (0.032, 0.092, 0.330),
            ) for n_sample, _ in REFERENCE_DESIGN
        }),
        ("population_mixture", {
            n_sample: (
                0.53 * oracle.expected_sfs_piecewise(
                    n_sample, (0.24, 3.45, 1.0), (0.045, 0.300)
                )
                + 0.47 * oracle.expected_sfs_piecewise(
                    n_sample, (3.55, 0.28, 1.0), (0.040, 0.310)
                )
            ) for n_sample, _ in REFERENCE_DESIGN
        }),
    )
    records = []
    for kind, spectra in synthetic:
        fit_records = []
        for n_sample, replicates in REFERENCE_DESIGN:
            fit_records.append({
                "n_sample": n_sample,
                "unfolded_sfs_counts": (
                    oracle.THETA_PER_PANEL * replicates * spectra[n_sample]
                ),
                "expected_count_scale": oracle.THETA_PER_PANEL * replicates,
            })
        fit = _fit_records(oracle, fit_records, oracle.PARAMETER_BOUNDS)
        records.append({
            "kind": kind,
            "best_three_epoch_parameters": fit["parameters"].tolist(),
            "clean_structural_reduced_deviance": float(fit["reduced_deviance"]),
            "refusal_threshold": REFUSAL_REDUCED_DEVIANCE,
            "indistinguishable_under_registered_threshold": bool(
                1.0 + fit["reduced_deviance"] < REFUSAL_REDUCED_DEVIANCE
            ),
        })
    return records


def _exact_checks(oracle):
    records = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            returned = oracle._reference_submission(world)
            parameters, _confidence_value, abstain = oracle._validate_submission(returned)
            if world["kind"] == "in_library":
                mechanism = oracle._mechanism_score(parameters, world["parameters"])
                observed = oracle._sfs_prediction_score(
                    world, parameters, oracle.ALLOWED_SAMPLE_SIZES
                )
                predicted = oracle._sfs_prediction_score(
                    world, parameters, oracle.HELDOUT_SAMPLE_SIZES
                )
                passed = mechanism == observed == predicted == 1.0 and not abstain
            elif world["kind"] == "constant":
                mechanism = 1.0 if not abstain else 0.0
                observed = oracle._sfs_prediction_score(
                    world, parameters, oracle.ALLOWED_SAMPLE_SIZES
                )
                predicted = oracle._sfs_prediction_score(
                    world, parameters, oracle.HELDOUT_SAMPLE_SIZES
                )
                passed = (
                    not abstain and mechanism == 1.0
                    and observed > 1.0 - 1.0e-12
                    and predicted > 1.0 - 1.0e-12
                )
            else:
                mechanism = observed = predicted = 1.0 if abstain else 0.0
                passed = abstain
            records.append({
                "split": split,
                "world_index": int(index),
                "kind": world["kind"],
                "mechanism_score": float(mechanism),
                "observed_sfs_fit_score": float(observed),
                "heldout_sample_size_prediction_score": float(predicted),
                "passed": bool(passed),
            })
    return records


def _determinism_check(oracle):
    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    first, second = oracle._SFSLaboratory(world), oracle._SFSLaboratory(world)
    one = first.observe(20, 4)
    fresh = second.observe(20, 4)
    repeated = first.observe(20, 4)
    result = {
        "same_query_same_fresh_lab": bool(np.array_equal(
            one["unfolded_sfs_counts"], fresh["unfolded_sfs_counts"]
        )),
        "same_query_repeated_call_is_independent": bool(not np.array_equal(
            one["unfolded_sfs_counts"], repeated["unfolded_sfs_counts"]
        )),
        "first_call_cost": int(one["budget_cost"]),
        "two_call_budget_used": int(first.used),
    }
    result["passed"] = bool(
        result["same_query_same_fresh_lab"]
        and result["same_query_repeated_call_is_independent"]
        and result["first_call_cost"] == 2
        and result["two_call_budget_used"] == 4
    )
    return result


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(_classical_policy(oracle, REFERENCE_DESIGN))
    underinformative = oracle.evaluate(
        _classical_policy(oracle, UNDERINFORMATIVE_DESIGN)
    )
    equal_budget_small_sample = oracle.evaluate(
        _classical_policy(oracle, EQUAL_BUDGET_SMALL_SAMPLE_DESIGN)
    )
    reference = oracle.evaluate(_ExactReferencePolicy(oracle))
    exact = _exact_checks(oracle)
    identifiability, misspecified = [], []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                identifiability.append(_identifiability_record(
                    oracle, world, split, index
                ))
            elif world["kind"] not in {"constant"}:
                misspecified.append(_clean_misspecification_record(
                    oracle, world, split, index
                ))
    ode_checks, constant_checks = _physics_checks(oracle)
    determinism = _determinism_check(oracle)
    near_equivalence = _near_equivalence_limits(oracle)

    difficulty_passed = bool(
        classical["combined_score"] > 0.05
        and classical["heldout_policy_score"] > 0.05
        and classical["development_supported_claim_coverage"] > 0.0
        and classical["heldout_supported_claim_coverage"] > 0.0
        and classical["development_unsupported_refusal_rate"] == 1.0
        and classical["heldout_unsupported_refusal_rate"] == 1.0
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
        and classical["development_mean_budget_used"] == 8.0
        and classical["heldout_mean_budget_used"] == 8.0
        and underinformative["development_mean_budget_used"] == 1.0
        and underinformative["heldout_mean_budget_used"] == 1.0
        and classical["combined_score"] > underinformative["combined_score"]
        and equal_budget_small_sample["development_mean_budget_used"] == 8.0
        and equal_budget_small_sample["heldout_mean_budget_used"] == 8.0
        and classical["combined_score"]
        > equal_budget_small_sample["combined_score"] + 0.15
        and classical["heldout_policy_score"]
        > equal_budget_small_sample["heldout_policy_score"] + 0.08
        and equal_budget_small_sample["development_supported_claim_coverage"] == 1.0
        and equal_budget_small_sample["heldout_supported_claim_coverage"] == 1.0
        and equal_budget_small_sample["development_unsupported_refusal_rate"] == 1.0
        and equal_budget_small_sample["heldout_unsupported_refusal_rate"] == 1.0
        and equal_budget_small_sample["development_false_discovery_rate"] == 0.0
        and equal_budget_small_sample["heldout_false_discovery_rate"] == 0.0
    )
    execution_passed = bool(
        oracle.DEMOGRAPHIC_SFS_V2
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["heldout_policy_score"] == 0.0
        and classical["valid"] == 1.0
        and classical["heldout_feasibility_rate"] == 1.0
        and underinformative["valid"] == 1.0
        and equal_budget_small_sample["valid"] == 1.0
        and equal_budget_small_sample["heldout_feasibility_rate"] == 1.0
        and reference["valid"] == 1.0
        and reference["combined_score"] == 1.0
        and reference["heldout_policy_score"] == 1.0
        and reference["robustness_score"] == 1.0
        and reference["heldout_robustness_score"] == 1.0
        and difficulty_passed
        and all(row["passed"] for row in exact)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in misspecified)
        and all(row["passed"] for row in ode_checks)
        and all(row["passed"] for row in constant_checks)
        and determinism["passed"]
        and all(
            row["indistinguishable_under_registered_threshold"]
            for row in near_equivalence
        )
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_FINITE_LOCUS_COALESCENT_TASK_CALIBRATION_NOT_REAL_"
            "POPULATION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "parameter_count": len(oracle.PARAMETER_NAMES),
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "allowed_sample_sizes": list(oracle.ALLOWED_SAMPLE_SIZES),
            "heldout_sample_sizes": list(oracle.HELDOUT_SAMPLE_SIZES),
            "sequencing_budget_units": oracle.SEQUENCING_BUDGET_UNITS,
            "theta_per_panel": oracle.THETA_PER_PANEL,
        },
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _file_sha256(path)
            for path in (
                TASK / "Task.md",
                TASK / "TASK_CARD.yaml",
                TASK / "solution.py",
                TASK / "verification/evaluator.py",
                TASK / "frontier_eval/metadata.yaml",
                TASK / "frontier_eval/constraints.txt",
                TASK / "frontier_eval/entrypoint.txt",
                TASK / "frontier_eval/run_eval.py",
                Path(__file__).resolve(),
            )
        },
        "always_abstain_baseline": baseline,
        "truth_blind_multisample_fit": classical,
        "underinformative_single_spectrum_fit": underinformative,
        "equal_budget_repeated_small_sample_fit": equal_budget_small_sample,
        "exact_reference": reference,
        "exact_parameter_or_refusal_checks": exact,
        "identifiability_checks": identifiability,
        "misspecified_resolvability_checks": misspecified,
        "finite_sfs_near_equivalence_limits": near_equivalence,
        "physics_checks": {
            "independent_ode_occupancy": ode_checks,
            "constant_size_theta_over_i_identity": constant_checks,
        },
        "determinism_and_budget_check": determinism,
        "difficulty_gate": {
            "reference_design": [list(value) for value in REFERENCE_DESIGN],
            "underinformative_design": [list(value) for value in UNDERINFORMATIVE_DESIGN],
            "equal_budget_small_sample_design": [
                list(value) for value in EQUAL_BUDGET_SMALL_SAMPLE_DESIGN
            ],
            "refusal_reduced_deviance": REFUSAL_REDUCED_DEVIANCE,
            "required_full_design_budget": 8,
            "required_underinformative_budget": 1,
            "minimum_multisample_minus_equal_budget_development_gap": 0.15,
            "minimum_multisample_minus_equal_budget_heldout_gap": 0.08,
            "passed": difficulty_passed,
        },
        "citation_validation": {
            "validated_sources": ["Crossref", "PubMed", "Semantic Scholar", "PMC"],
            "identifiers": [
                "10.1371/journal.pgen.1000695",
                "10.1534/genetics.117.200493",
                "10.1016/j.tpb.2008.01.001",
                "10.1214/14-AOS1264",
                "10.1073/pnas.1503717112",
            ],
            "passed": True,
        },
        "limitations": [
            "This is a synthetic neutral panmictic coalescent task, not inference about any real population.",
            "The ancestral size and aggregate mutation scale are fixed; arbitrary histories remain non-identifiable from the SFS.",
            "Independent Poisson loci omit linkage, recombination, selection, migration, structure, ascertainment and ancestral-state error.",
            "Task calibration does not measure GPT-5.5, feedback causality, population capability or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate()
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
