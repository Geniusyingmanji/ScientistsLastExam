#!/usr/bin/env python3
"""Calibrate DistillationColumnDesign-v2 witnesses and stage balances.

The fixed-seed search produces feasible mixed-integer witnesses; it is deliberately not
presented as a global-optimality certificate.  An independent bounded least-squares MESH
implementation checks the trusted tridiagonal Newton solver under every stored shift.
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
from scipy.optimize import differential_evolution, least_squares


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Chemistry/DistillationColumnDesign"
sys.path.insert(0, str(ROOT))

from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


NOMINAL_SEED_BASE = 4100
ROBUST_SEED_BASE = 5100
NOMINAL_MAXIMUM_ITERATIONS = 35
ROBUST_MAXIMUM_ITERATIONS = 55
NOMINAL_POPULATION_MULTIPLIER = 10
ROBUST_POPULATION_MULTIPLIER = 12
OPTIMIZER_TOLERANCE = 1.0e-8
REFERENCE_REFLUX_GUARD = 1.01
NOMINAL_VIOLATION_SCALE = 0.005
ROBUST_VIOLATION_SCALE = 0.0025


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "distillation_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load DistillationColumnDesign-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode_search_point(values, problem):
    tray_count = int(np.clip(
        np.rint(values[0]), *problem["tray_count_bounds"]
    ))
    feed_stage = int(np.clip(
        np.rint(1.0 + values[1] * (tray_count - 1)), 1, tray_count
    ))
    return {
        "tray_count": tray_count,
        "feed_stage": feed_stage,
        "reflux_ratio": float(values[2]),
        "distillate_fraction": float(values[3]),
        "feed_split_gain": float(values[4]),
    }


def _search_bounds(problem):
    return (
        tuple(problem["tray_count_bounds"]),
        (0.0, 1.0),
        tuple(problem["reflux_ratio_bounds"]),
        tuple(problem["distillate_fraction_bounds"]),
        tuple(problem["feed_split_gain_bounds"]),
    )


def _constraint_violations(metrics, problem, scale):
    return (
        max(
            0.0,
            float(problem["minimum_distillate_light_mole_fraction"])
            - float(metrics["distillate_light_mole_fraction"]),
        ) / scale,
        max(
            0.0,
            float(metrics["bottoms_light_mole_fraction"])
            - float(problem["maximum_bottoms_light_mole_fraction"]),
        ) / scale,
        max(
            0.0,
            float(problem["minimum_light_recovery"])
            - float(metrics["light_recovery"]),
        ) / scale,
        max(
            0.0,
            float(problem["minimum_heavy_recovery"])
            - float(metrics["heavy_recovery"]),
        ) / scale,
    )


def _constraint_margin(metrics, problem):
    return min(
        float(metrics["distillate_light_mole_fraction"])
        - float(problem["minimum_distillate_light_mole_fraction"]),
        float(problem["maximum_bottoms_light_mole_fraction"])
        - float(metrics["bottoms_light_mole_fraction"]),
        float(metrics["light_recovery"])
        - float(problem["minimum_light_recovery"]),
        float(metrics["heavy_recovery"])
        - float(problem["minimum_heavy_recovery"]),
    )


def _search_reference(oracle, instance, index, robust):
    problem = instance["problem"]
    baseline_cost = float(instance["baseline_nominal"]["annualized_cost"])
    evaluations = 0

    def objective(values):
        nonlocal evaluations
        evaluations += 1
        design = _decode_search_point(values, problem)
        try:
            rows = [oracle._solve_column(design, problem)]
            if robust:
                rows.extend(
                    oracle._shifted_metrics(design, problem, shift)
                    for shift in oracle.SHIFT_SPECS
                )
        except Exception:
            return 1.0e5
        scale = (
            ROBUST_VIOLATION_SCALE if robust else NOMINAL_VIOLATION_SCALE
        )
        violation = sum(
            sum(_constraint_violations(row, problem, scale)) for row in rows
        )
        cost_ratio = rows[0]["annualized_cost"] / baseline_cost
        if violation <= 1.0e-10:
            return float(cost_ratio)
        return float((10.0 if robust else 5.0) + violation + 0.01 * cost_ratio)

    seed = (ROBUST_SEED_BASE if robust else NOMINAL_SEED_BASE) + index
    maximum_iterations = (
        ROBUST_MAXIMUM_ITERATIONS if robust
        else NOMINAL_MAXIMUM_ITERATIONS
    )
    population = (
        ROBUST_POPULATION_MULTIPLIER if robust
        else NOMINAL_POPULATION_MULTIPLIER
    )
    result = differential_evolution(
        objective,
        _search_bounds(problem),
        seed=seed,
        popsize=population,
        maxiter=maximum_iterations,
        tol=OPTIMIZER_TOLERANCE,
        polish=False,
        workers=1,
        updating="immediate",
        init="sobol",
    )
    unguarded = _decode_search_point(result.x, problem)
    guarded = dict(unguarded)
    guarded["reflux_ratio"] *= REFERENCE_REFLUX_GUARD
    if not robust:
        # Gain is flat in the nominal objective.  Canonicalize it to the public
        # material-balance slope instead of retaining an optimizer accident.
        guarded["feed_split_gain"] = 1.0 / max(
            float(problem["minimum_distillate_light_mole_fraction"])
            - float(problem["maximum_bottoms_light_mole_fraction"]),
            0.20,
        )
    unguarded_nominal = oracle._solve_column(unguarded, problem)
    guarded_nominal = oracle._solve_column(guarded, problem)
    guarded_shifts = (
        [
            oracle._shifted_metrics(guarded, problem, shift)
            for shift in oracle.SHIFT_SPECS
        ]
        if robust else []
    )
    return {
        "seed": seed,
        "maximum_iterations": maximum_iterations,
        "population_multiplier": population,
        "function_evaluations": evaluations,
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "optimizer_objective": float(result.fun),
        "unguarded_design": unguarded,
        "unguarded_nominal_cost": float(
            unguarded_nominal["annualized_cost"]
        ),
        "guarded_design": guarded,
        "guarded_nominal_cost": float(guarded_nominal["annualized_cost"]),
        "guarded_nominal_feasible": bool(
            guarded_nominal["process_feasible"]
        ),
        "guarded_all_shifts_feasible": bool(
            all(row["process_feasible"] for row in guarded_shifts)
        ) if robust else None,
        "guarded_minimum_constraint_margin": float(min(
            _constraint_margin(row, problem)
            for row in [guarded_nominal] + guarded_shifts
        )),
    }


def _equilibrium(value, relative_volatility):
    value = np.asarray(value, dtype=float)
    alpha = float(relative_volatility)
    return alpha * value / (1.0 + (alpha - 1.0) * value)


def _independent_stage_solution(design, problem, shift=None):
    """Solve independently without importing oracle equation/Jacobian helpers."""
    shift = shift or {
        "name": "nominal",
        "relative_volatility_scale": 1.0,
        "feed_composition_delta": 0.0,
        "feed_liquid_fraction_delta": 0.0,
        "reflux_ratio_scale": 1.0,
    }
    tray_count = int(design["tray_count"])
    feed_stage = int(design["feed_stage"])
    alpha = (
        float(problem["relative_volatility"])
        * float(shift["relative_volatility_scale"])
    )
    feed = float(np.clip(
        float(problem["feed_light_mole_fraction"])
        + float(shift["feed_composition_delta"]),
        0.05, 0.95,
    ))
    quality = float(np.clip(
        float(problem["feed_liquid_fraction"])
        + float(shift["feed_liquid_fraction_delta"]),
        0.05, 1.0,
    ))
    distillate = (
        float(design["distillate_fraction"])
        + float(design["feed_split_gain"])
        * (feed - float(problem["feed_light_mole_fraction"]))
    )
    bottoms = 1.0 - distillate
    reflux = (
        float(design["reflux_ratio"])
        * float(shift["reflux_ratio_scale"])
    )
    rectifying_liquid = reflux * distillate
    rectifying_vapour = (reflux + 1.0) * distillate
    stripping_liquid = rectifying_liquid + quality
    stripping_vapour = rectifying_vapour - (1.0 - quality)
    if min(
        distillate, bottoms, rectifying_liquid, rectifying_vapour,
        stripping_liquid, stripping_vapour,
    ) <= 1.0e-10:
        raise ValueError("independent model found nonpositive flow")

    def residual(liquid):
        vapour = _equilibrium(liquid, alpha)
        values = []
        for zero_index in range(tray_count):
            stage = zero_index + 1
            if stage < feed_stage:
                liquid_in = (
                    vapour[0] if stage == 1 else liquid[zero_index - 1]
                )
                values.append(
                    rectifying_liquid * liquid_in
                    + rectifying_vapour * vapour[zero_index + 1]
                    - rectifying_liquid * liquid[zero_index]
                    - rectifying_vapour * vapour[zero_index]
                )
            elif stage == feed_stage:
                liquid_in = (
                    vapour[0] if stage == 1 else liquid[zero_index - 1]
                )
                values.append(
                    rectifying_liquid * liquid_in
                    + stripping_vapour * vapour[zero_index + 1]
                    + feed
                    - stripping_liquid * liquid[zero_index]
                    - rectifying_vapour * vapour[zero_index]
                )
            else:
                values.append(
                    stripping_liquid * liquid[zero_index - 1]
                    + stripping_vapour * vapour[zero_index + 1]
                    - stripping_liquid * liquid[zero_index]
                    - stripping_vapour * vapour[zero_index]
                )
        values.append(
            stripping_liquid * liquid[tray_count - 1]
            - stripping_vapour * vapour[tray_count]
            - bottoms * liquid[tray_count]
        )
        return np.asarray(values, dtype=float)

    top = float(problem["minimum_distillate_light_mole_fraction"])
    bottom = float(problem["maximum_bottoms_light_mole_fraction"])
    starts = (
        np.linspace(min(0.98, top + 0.01), max(0.005, bottom - 0.01),
                    tray_count + 1),
        np.linspace(0.80, 0.10, tray_count + 1),
        np.full(tray_count + 1, feed),
    )
    best = None
    for start in starts:
        fit = least_squares(
            residual,
            start,
            bounds=(1.0e-10, 1.0 - 1.0e-10),
            xtol=1.0e-13,
            ftol=1.0e-13,
            gtol=1.0e-13,
            max_nfev=2000,
        )
        maximum_residual = float(np.max(np.abs(residual(fit.x))))
        if best is None or maximum_residual < best[0]:
            best = (maximum_residual, fit.x.copy(), int(fit.nfev))
    if best is None or best[0] > 1.0e-9:
        raise ValueError("independent least-squares stage solve failed")
    maximum_residual, liquid, evaluations = best
    vapour = _equilibrium(liquid, alpha)
    distillate_composition = float(vapour[0])
    bottoms_composition = float(liquid[-1])
    overall_residual = abs(
        feed
        - distillate * distillate_composition
        - bottoms * bottoms_composition
    )
    light_recovery = distillate * distillate_composition / feed
    heavy_recovery = bottoms * (1.0 - bottoms_composition) / (1.0 - feed)
    annualized_cost = (
        float(problem["annualized_fixed_cost"])
        + float(problem["annualized_cost_per_tray"]) * tray_count
        + float(problem["annualized_cost_per_vapour_flow"])
        * max(rectifying_vapour, stripping_vapour)
    )
    return {
        "distillate_light_mole_fraction": distillate_composition,
        "bottoms_light_mole_fraction": bottoms_composition,
        "light_recovery": float(light_recovery),
        "heavy_recovery": float(heavy_recovery),
        "annualized_cost": float(annualized_cost),
        "maximum_stage_balance_residual": maximum_residual,
        "overall_component_balance_residual": float(overall_residual),
        "least_squares_function_evaluations": evaluations,
    }


def _oracle_metrics(oracle, design, problem, shift):
    if shift is None:
        return oracle._solve_column(design, problem)
    return oracle._shifted_metrics(design, problem, shift)


def _independent_checks(oracle, instance):
    checks = []
    maximum_composition_error = 0.0
    maximum_recovery_error = 0.0
    maximum_cost_error = 0.0
    maximum_stage_residual = 0.0
    maximum_overall_residual = 0.0
    designs = (
        ("nominal_reference", instance["nominal_reference_design"]),
        ("robust_reference", instance["robust_reference_design"]),
    )
    conditions = (("nominal", None),) + tuple(
        (shift["name"], shift) for shift in oracle.SHIFT_SPECS
    )
    for design_name, design in designs:
        for condition_name, shift in conditions:
            independent = _independent_stage_solution(
                design, instance["problem"], shift
            )
            trusted = _oracle_metrics(
                oracle, design, instance["problem"], shift
            )
            composition_error = max(
                abs(
                    independent["distillate_light_mole_fraction"]
                    - trusted["distillate_light_mole_fraction"]
                ),
                abs(
                    independent["bottoms_light_mole_fraction"]
                    - trusted["bottoms_light_mole_fraction"]
                ),
            )
            recovery_error = max(
                abs(independent["light_recovery"] - trusted["light_recovery"]),
                abs(independent["heavy_recovery"] - trusted["heavy_recovery"]),
            )
            cost_error = abs(
                independent["annualized_cost"] - trusted["annualized_cost"]
            )
            maximum_composition_error = max(
                maximum_composition_error, composition_error
            )
            maximum_recovery_error = max(
                maximum_recovery_error, recovery_error
            )
            maximum_cost_error = max(maximum_cost_error, cost_error)
            maximum_stage_residual = max(
                maximum_stage_residual,
                independent["maximum_stage_balance_residual"],
            )
            maximum_overall_residual = max(
                maximum_overall_residual,
                independent["overall_component_balance_residual"],
            )
            checks.append({
                "design": design_name,
                "condition": condition_name,
                "maximum_product_composition_error": composition_error,
                "maximum_recovery_error": recovery_error,
                "annualized_cost_error": cost_error,
                **independent,
            })
    passed = bool(
        maximum_composition_error <= 2.0e-8
        and maximum_recovery_error <= 2.0e-8
        and maximum_cost_error <= 1.0e-7
        and maximum_stage_residual <= 1.0e-9
        and maximum_overall_residual <= 2.0e-8
    )
    return {
        "checks": checks,
        "maximum_product_composition_error": maximum_composition_error,
        "maximum_recovery_error": maximum_recovery_error,
        "maximum_annualized_cost_error": maximum_cost_error,
        "maximum_independent_stage_balance_residual": maximum_stage_residual,
        "maximum_independent_overall_balance_residual": maximum_overall_residual,
        "passed": passed,
    }


def _compact(metrics):
    keys = (
        "combined_score", "valid", "feasibility_rate", "raw_score",
        "robustness_score", "heldout_policy_score",
        "heldout_robustness_score", "heldout_feasibility_rate",
        "development_shift_feasibility_rate",
        "heldout_shift_feasibility_rate",
        "development_mean_annualized_cost",
        "heldout_mean_annualized_cost", "candidate_instance_call_count",
        "candidate_instance_valid_rate", "error_message",
    )
    return {key: metrics[key] for key in keys if key in metrics}


def _invalid_artifact_checks(oracle):
    def baseline(problem):
        return oracle._baseline_design(problem)

    factories = {
        "missing_field": lambda problem: {
            key: value for key, value in baseline(problem).items()
            if key != "feed_split_gain"
        },
        "nonfinite": lambda problem: {
            **baseline(problem), "reflux_ratio": math.nan,
        },
        "boolean_integer": lambda problem: {
            **baseline(problem), "tray_count": True,
        },
        "nonintegral_stage": lambda problem: {
            **baseline(problem), "feed_stage": 2.5,
        },
        "out_of_bounds": lambda problem: {
            **baseline(problem), "reflux_ratio": 20.0,
        },
    }
    return {
        name: _compact(oracle.evaluate(factory))
        for name, factory in factories.items()
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(oracle._baseline_design)
    baseline_replay = oracle.evaluate(oracle._baseline_design)
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    searches = []
    independent = []
    reference_gates = []
    for index, instance in enumerate(oracle.INSTANCES):
        nominal_search = _search_reference(
            oracle, instance, index, robust=False
        )
        robust_search = _search_reference(
            oracle, instance, index, robust=True
        )
        searches.append({
            "name": instance["name"],
            "split": instance["split"],
            "nominal": nominal_search,
            "robust": robust_search,
        })
        independent_record = _independent_checks(oracle, instance)
        independent.append({
            "name": instance["name"],
            "split": instance["split"],
            **independent_record,
        })
        problem = instance["problem"]
        baseline_cost = instance["baseline_nominal"]["annualized_cost"]
        nominal_cost = instance["nominal_reference"]["annualized_cost"]
        robust_cost = instance["robust_reference"]["annualized_cost"]
        robust_shifts = [
            oracle._shifted_metrics(
                instance["robust_reference_design"], problem, shift
            )
            for shift in oracle.SHIFT_SPECS
        ]
        nominal_topology_matches = all(
            nominal_search["guarded_design"][key]
            == instance["nominal_reference_design"][key]
            for key in ("tray_count", "feed_stage")
        )
        robust_topology_matches = all(
            robust_search["guarded_design"][key]
            == instance["robust_reference_design"][key]
            for key in ("tray_count", "feed_stage")
        )
        nominal_cost_relative_error = abs(
            nominal_search["guarded_nominal_cost"] - nominal_cost
        ) / nominal_cost
        robust_cost_relative_error = abs(
            robust_search["guarded_nominal_cost"] - robust_cost
        ) / robust_cost
        minimum_robust_margin = min(
            _constraint_margin(instance["robust_reference"], problem),
            *(
                _constraint_margin(row, problem) for row in robust_shifts
            ),
        )
        baseline_balance_passed = bool(
            instance["baseline_nominal"][
                "maximum_stage_balance_residual"
            ] <= oracle.BALANCE_TOLERANCE
            and instance["baseline_nominal"][
                "overall_component_balance_residual"
            ] <= oracle.BALANCE_TOLERANCE
        )
        passed = bool(
            instance["baseline_nominal"]["process_feasible"]
            and baseline_balance_passed
            and instance["nominal_reference"]["process_feasible"]
            and instance["robust_reference"]["process_feasible"]
            and all(row["process_feasible"] for row in robust_shifts)
            and baseline_cost > nominal_cost
            and baseline_cost > robust_cost
            and nominal_topology_matches
            and robust_topology_matches
            and nominal_cost_relative_error <= 2.0e-10
            and robust_cost_relative_error <= 2.0e-10
            and minimum_robust_margin >= 5.0e-4
        )
        reference_gates.append({
            "name": instance["name"],
            "baseline_cost": baseline_cost,
            "nominal_reference_cost": nominal_cost,
            "robust_reference_cost": robust_cost,
            "nominal_reference_cost_fraction_of_baseline": (
                nominal_cost / baseline_cost
            ),
            "robust_reference_cost_fraction_of_baseline": (
                robust_cost / baseline_cost
            ),
            "nominal_reproduced_topology": nominal_topology_matches,
            "robust_reproduced_topology": robust_topology_matches,
            "nominal_reproduced_cost_relative_error": (
                nominal_cost_relative_error
            ),
            "robust_reproduced_cost_relative_error": (
                robust_cost_relative_error
            ),
            "minimum_robust_constraint_margin": minimum_robust_margin,
            "baseline_maximum_stage_balance_residual": instance[
                "baseline_nominal"
            ]["maximum_stage_balance_residual"],
            "baseline_overall_component_balance_residual": instance[
                "baseline_nominal"
            ]["overall_component_balance_residual"],
            "baseline_balance_passed": baseline_balance_passed,
            "passed": passed,
        })

    invalid = _invalid_artifact_checks(oracle)
    deterministic = bool(
        json.dumps(baseline, sort_keys=True, allow_nan=False)
        == json.dumps(baseline_replay, sort_keys=True, allow_nan=False)
    )
    difficulty_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["combined_score"] > 0.999999
        and nominal["heldout_policy_score"] > 0.999999
        and nominal["development_shift_feasibility_rate"] <= 0.25
        and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and robust["combined_score"] >= 0.90
        and robust["heldout_policy_score"] >= 0.85
    )
    execution_passed = bool(
        oracle.DISTILLATION_V2
        and len(oracle.DEVELOPMENT_INSTANCES) == 4
        and len(oracle.HELDOUT_INSTANCES) == 2
        and len(oracle.SHIFT_SPECS) == 5
        and baseline["valid"] == 1.0
        and nominal["valid"] == 1.0
        and robust["valid"] == 1.0
        and deterministic
        and all(
            row.get("valid") == 0.0
            and row.get("combined_score") == 0.0
            and row.get("raw_score") == 0.0
            for row in invalid.values()
        )
        and all(row["passed"] for row in independent)
        and all(row["passed"] for row in reference_gates)
        and difficulty_passed
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "REDUCED_ORDER_BINARY_EQUILIBRIUM_STAGE_TASK_CALIBRATION_NOT_"
            "RATE_BASED_SIMULATOR_PILOT_COLUMN_OR_PLANT_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "task_dimensions": {
            "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "tray_count_range": [
                min(row["problem"]["tray_count_bounds"][0]
                    for row in oracle.INSTANCES),
                max(row["problem"]["tray_count_bounds"][1]
                    for row in oracle.INSTANCES),
            ],
        },
        "reference_method": {
            "optimizer": "SciPy differential_evolution",
            "encoding": (
                "rounded tray count plus fractional feed position and continuous "
                "reflux, distillate fraction and feed-forward split gain"
            ),
            "initial_population": "scrambled fixed-seed Sobol",
            "nominal_seed_base": NOMINAL_SEED_BASE,
            "robust_seed_base": ROBUST_SEED_BASE,
            "nominal_maximum_iterations": NOMINAL_MAXIMUM_ITERATIONS,
            "robust_maximum_iterations": ROBUST_MAXIMUM_ITERATIONS,
            "nominal_population_multiplier": NOMINAL_POPULATION_MULTIPLIER,
            "robust_population_multiplier": ROBUST_POPULATION_MULTIPLIER,
            "tolerance": OPTIMIZER_TOLERANCE,
            "stored_reflux_guard_factor": REFERENCE_REFLUX_GUARD,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "weak_baseline": _compact(baseline),
        "nominal_reference_policy": _compact(nominal),
        "robust_reference_policy": _compact(robust),
        "reference_search_reproduction": searches,
        "reference_gates": reference_gates,
        "independent_least_squares_mesh_checks": independent,
        "invalid_artifact_checks": invalid,
        "determinism_check": {
            "exact_json_replay": deterministic,
            "passed": deterministic,
        },
        "difficulty_gate": {
            "nominal_reference_score_required": 0.999999,
            "robust_reference_score_required": 0.999999,
            "minimum_robust_cross_nominal_score": 0.90,
            "maximum_nominal_reference_development_shift_feasibility": 0.25,
            "passed": difficulty_passed,
        },
        "limitations": [
            "The binary constant-relative-volatility, constant-molar-overflow model omits multicomponent and non-ideal thermodynamics, pressure drop, tray efficiency and hydraulics.",
            "Fixed-seed differential-evolution results are replayable feasible witnesses, not global-optimality certificates.",
            "Repository-visible procedural regimes require future server-held mixtures and specifications before population claims.",
            "Independent validation here re-solves the same documented reduced-order MESH equations; engineering claims require a separately configured rate-based simulator and experimental or plant data.",
            "Task calibration does not measure GPT-5.5, feedback causality, autonomous discovery or scientific population performance.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
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
