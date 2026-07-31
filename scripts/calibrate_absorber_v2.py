#!/usr/bin/env python3
"""Calibrate BroadbandAbsorber-v2 physics, anchors and robustness axes."""

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
from scipy.optimize import differential_evolution
from scipy.special import jv


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/BroadbandAbsorber"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


NOMINAL_MAXITER = 45
ROBUST_MAXITER = 55
POPULATION_SIZE = 12
OPTIMIZER_TOLERANCE = 2.0e-7


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "absorber_v2_calibration_oracle", path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load BroadbandAbsorber-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manufactured_design(design, sign):
    shifted = np.asarray(design, dtype=float).copy()
    if not sign:
        return shifted
    phase = 2.0 * np.pi * (np.arange(len(shifted)) + 0.37) / len(shifted)
    sign = float(sign)
    shifted[:, 0] *= 1.0 + sign * 0.035 * np.sin(phase)
    shifted[:, 1] += sign * 0.00025 * np.cos(phase + 0.4)
    shifted[:, 2] *= 1.0 + sign * 0.030 * np.sin(phase + 1.1)
    return shifted


def _shift_geometry_feasible(design, problem):
    geometry = np.asarray(design, dtype=float)
    return bool(
        np.all(np.isfinite(geometry))
        and np.all(geometry > 0.0)
        and np.all(
            geometry[:, 2] < 0.45 * float(problem["cell_side_m"])
        )
        and np.all(
            geometry[:, 0] + geometry[:, 1]
            <= float(problem["maximum_total_depth_m"]) + 1e-12
        )
    )


def _independent_impedance(design, problem, shift=None, exact=True):
    """Reimplement the public equations without importing oracle helpers."""
    geometry = np.asarray(design, dtype=float)
    density = float(problem["air_density_kg_m3"])
    sound_speed = float(problem["sound_speed_m_s"])
    viscosity = float(problem["dynamic_viscosity_pa_s"])
    incidence_angle_deg = 0.0
    if shift is not None:
        geometry = _manufactured_design(
            geometry, int(shift["manufacturing_sign"])
        )
        density *= float(shift["density_scale"])
        sound_speed *= float(shift["sound_speed_scale"])
        viscosity *= float(shift["viscosity_scale"])
        incidence_angle_deg = float(shift["incidence_angle_deg"])

    depth, neck_length, neck_radius = geometry.T
    frequency = np.geomspace(
        float(problem["frequency_band_hz"][0]),
        float(problem["frequency_band_hz"][1]),
        int(problem["frequency_sample_count"]),
    )
    omega = 2.0 * np.pi * frequency[:, None]
    wavenumber = omega / sound_speed
    opening_fraction = (
        np.pi * neck_radius**2 / float(problem["cell_side_m"]) ** 2
    )
    effective_length = neck_length + 1.70 * neck_radius

    if exact:
        argument = neck_radius[None, :] * np.sqrt(
            -1j * omega * density / viscosity
        )
        correction = 1.0 - 2.0 * jv(1, argument) / (
            argument * jv(0, argument)
        )
        dynamic_density = density / correction
        neck = (
            1j * omega * dynamic_density * effective_length[None, :]
            + 0.5 * density * sound_speed
            * (wavenumber * neck_radius[None, :]) ** 2
        )
        cavity = -1j * density * sound_speed / np.tan(
            wavenumber * depth[None, :]
        )
    else:
        resistance = 8.0 * viscosity * effective_length / neck_radius**2
        neck = resistance[None, :] + (
            1j * omega * density * effective_length[None, :]
        )
        cavity = -1j * density * sound_speed**2 / (
            omega * depth[None, :]
        )
    cells = neck / opening_fraction[None, :] + cavity
    panel = 1.0 / np.mean(1.0 / cells, axis=1)
    normal_impedance = density * sound_speed / math.cos(
        math.radians(incidence_angle_deg)
    )
    reflection = (panel - normal_impedance) / (panel + normal_impedance)
    absorption = np.clip(1.0 - np.abs(reflection) ** 2, 0.0, 1.0)
    return {
        "frequency_hz": frequency,
        "cell_impedance": cells,
        "panel_impedance": panel,
        "absorption": absorption,
    }


def _utility(absorption, threshold=0.50):
    absorption = np.asarray(absorption, dtype=float)
    return float(
        0.55 * np.mean(absorption)
        + 0.30 * np.quantile(absorption, 0.20)
        + 0.15 * np.mean(absorption >= float(threshold))
    )


def _family_design(problem, parameters):
    low_multiplier, high_multiplier, radius_value, length_value = map(
        float, parameters
    )
    count = int(problem["n_resonators"])
    low, high = map(float, problem["frequency_band_hz"])
    targets = np.geomspace(
        low * low_multiplier, high * high_multiplier, count
    )
    radius = np.full(count, radius_value, dtype=float)
    length = np.full(count, length_value, dtype=float)
    opening = np.pi * radius**2 / float(problem["cell_side_m"]) ** 2
    effective_length = length + 1.70 * radius
    depth = opening * float(problem["sound_speed_m_s"]) ** 2 / (
        (2.0 * np.pi * targets) ** 2 * effective_length
    )
    depth = np.clip(
        depth,
        float(problem["cavity_depth_bounds_m"][0]),
        float(problem["maximum_total_depth_m"]) - length - 0.002,
    )
    return np.column_stack((depth, length, radius))


def _parameter_bounds(problem):
    return (
        (0.60, 1.40),
        (0.65, 1.50),
        tuple(map(float, problem["neck_radius_bounds_m"])),
        tuple(map(float, problem["neck_length_bounds_m"])),
    )


def _independent_nominal_utility(problem, parameters):
    design = _family_design(problem, parameters)
    return _utility(_independent_impedance(design, problem)["absorption"])


def _independent_robust_utility(oracle, problem, parameters):
    design = _family_design(problem, parameters)
    utilities = []
    for shift in oracle.SHIFT_SPECS:
        realized = _manufactured_design(
            design, shift["manufacturing_sign"]
        )
        utilities.append(
            _utility(_independent_impedance(
                design, problem, shift=shift
            )["absorption"])
            if _shift_geometry_feasible(realized, problem)
            else 0.0
        )
    return min(utilities)


def _recalibrate_family(oracle, instance, index, robust):
    problem = instance["problem"]
    objective = (
        (lambda values: -_independent_robust_utility(
            oracle, problem, values
        ))
        if robust
        else (lambda values: -_independent_nominal_utility(problem, values))
    )
    seed = (200 if robust else 100) + int(index)
    maximum_iterations = ROBUST_MAXITER if robust else NOMINAL_MAXITER
    result = differential_evolution(
        objective,
        _parameter_bounds(problem),
        seed=seed,
        popsize=POPULATION_SIZE,
        maxiter=maximum_iterations,
        polish=True,
        tol=OPTIMIZER_TOLERANCE,
        workers=1,
    )
    return {
        "seed": seed,
        "maximum_iterations": maximum_iterations,
        "success": bool(result.success),
        "message": str(result.message),
        "function_evaluations": int(result.nfev),
        "parameters": [float(value) for value in result.x],
        "utility": float(-result.fun),
    }


def _independent_record(oracle, instance, index):
    problem = instance["problem"]
    baseline = instance["baseline_design"]
    nominal = instance["nominal_reference_design"]
    robust = instance["robust_reference_design"]
    checks = []
    maximum_absorption_error = 0.0
    maximum_impedance_relative_error = 0.0
    minimum_cell_resistance = math.inf
    minimum_panel_resistance = math.inf
    for design_name, design in (
        ("baseline", baseline),
        ("nominal_reference", nominal),
        ("robust_reference", robust),
    ):
        for shift_index, shift in enumerate((None,) + tuple(oracle.SHIFT_SPECS)):
            independent = _independent_impedance(
                design, problem, shift=shift
            )
            frequency, absorption, panel, cells = oracle._absorption_spectrum(
                design, problem, shift=shift
            )
            absorption_error = float(np.max(np.abs(
                independent["absorption"] - absorption
            )))
            impedance_error = float(np.max(
                np.abs(independent["cell_impedance"] - cells)
                / np.maximum(np.abs(cells), 1.0)
            ))
            maximum_absorption_error = max(
                maximum_absorption_error, absorption_error
            )
            maximum_impedance_relative_error = max(
                maximum_impedance_relative_error, impedance_error
            )
            minimum_cell_resistance = min(
                minimum_cell_resistance,
                float(np.min(independent["cell_impedance"].real)),
            )
            minimum_panel_resistance = min(
                minimum_panel_resistance,
                float(np.min(independent["panel_impedance"].real)),
            )
            checks.append({
                "design": design_name,
                "shift": "nominal" if shift is None else shift["name"],
                "frequency_grid_exact": bool(np.array_equal(
                    independent["frequency_hz"], frequency
                )),
                "maximum_absorption_error": absorption_error,
                "maximum_cell_impedance_relative_error": impedance_error,
                "minimum_cell_resistance_pa_s_m": float(np.min(
                    independent["cell_impedance"].real
                )),
                "minimum_panel_resistance_pa_s_m": float(np.min(
                    independent["panel_impedance"].real
                )),
                "geometry_feasible": _shift_geometry_feasible(
                    design if shift is None else _manufactured_design(
                        design, shift["manufacturing_sign"]
                    ),
                    problem,
                ),
            })

    recalibrated_nominal = _recalibrate_family(
        oracle, instance, index, robust=False
    )
    recalibrated_robust = _recalibrate_family(
        oracle, instance, index, robust=True
    )
    declared_nominal_utility = _independent_nominal_utility(
        problem, instance["nominal_reference_parameters"]
    )
    declared_robust_utility = _independent_robust_utility(
        oracle, problem, instance["robust_reference_parameters"]
    )
    nominal_utility_gap = (
        recalibrated_nominal["utility"] - declared_nominal_utility
    )
    robust_utility_gap = (
        recalibrated_robust["utility"] - declared_robust_utility
    )
    baseline_nominal_utility = _utility(
        _independent_impedance(baseline, problem)["absorption"]
    )
    baseline_robust_utility = min(
        (
            _utility(_independent_impedance(
                baseline, problem, shift=shift
            )["absorption"])
            if _shift_geometry_feasible(
                _manufactured_design(
                    baseline, shift["manufacturing_sign"]
                ),
                problem,
            )
            else 0.0
        )
        for shift in oracle.SHIFT_SPECS
    )
    nominal_proxy_utility = _utility(
        _independent_impedance(nominal, problem, exact=False)["absorption"]
    )
    passed = bool(
        maximum_absorption_error <= 2.0e-12
        and maximum_impedance_relative_error <= 2.0e-12
        and minimum_cell_resistance >= -1.0e-9
        and minimum_panel_resistance >= -1.0e-9
        and all(row["geometry_feasible"] for row in checks)
        and declared_nominal_utility > baseline_nominal_utility + 0.25
        and declared_robust_utility > baseline_robust_utility + 0.25
        and nominal_utility_gap <= 2.0e-5
        and robust_utility_gap <= 2.0e-5
    )
    return {
        "name": instance["name"],
        "split": instance["split"],
        "n_resonators": int(problem["n_resonators"]),
        "frequency_band_hz": list(problem["frequency_band_hz"]),
        "maximum_total_depth_m": problem["maximum_total_depth_m"],
        "baseline_nominal_utility": baseline_nominal_utility,
        "baseline_robust_utility": baseline_robust_utility,
        "declared_nominal_parameters": list(
            instance["nominal_reference_parameters"]
        ),
        "declared_nominal_utility": declared_nominal_utility,
        "recalibrated_nominal": recalibrated_nominal,
        "recalibrated_minus_declared_nominal_utility": nominal_utility_gap,
        "declared_robust_parameters": list(
            instance["robust_reference_parameters"]
        ),
        "declared_robust_utility": declared_robust_utility,
        "recalibrated_robust": recalibrated_robust,
        "recalibrated_minus_declared_robust_utility": robust_utility_gap,
        "nominal_reference_proxy_utility": nominal_proxy_utility,
        "nominal_reference_proxy_minus_distributed_utility": (
            nominal_proxy_utility - declared_nominal_utility
        ),
        "maximum_absorption_error": maximum_absorption_error,
        "maximum_cell_impedance_relative_error": (
            maximum_impedance_relative_error
        ),
        "minimum_cell_resistance_pa_s_m": minimum_cell_resistance,
        "minimum_panel_resistance_pa_s_m": minimum_panel_resistance,
        "equation_checks": checks,
        "passed": passed,
    }


def _compact(metrics):
    scalar_keys = (
        "combined_score",
        "valid",
        "feasibility_rate",
        "raw_score",
        "robustness_score",
        "development_validation_gap",
        "heldout_policy_score",
        "heldout_robustness_score",
        "heldout_feasibility_rate",
        "development_proxy_utility",
        "heldout_proxy_utility",
        "development_exact_utility",
        "heldout_exact_utility",
        "development_mean_absorption",
        "heldout_mean_absorption",
        "development_twentieth_percentile_absorption",
        "heldout_twentieth_percentile_absorption",
        "development_coverage_above_half",
        "heldout_coverage_above_half",
        "candidate_instance_call_count",
        "candidate_instance_valid_rate",
        "error_message",
    )
    return {key: metrics.get(key) for key in scalar_keys if key in metrics}


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    baseline_replay = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    nonfinite = oracle.evaluate(lambda problem: np.full(
        (problem["n_resonators"], 3), np.nan
    ))
    wrong_shape = oracle.evaluate(lambda problem: np.zeros(
        (problem["n_resonators"] - 1, 3)
    ))
    out_of_bounds = oracle.evaluate(lambda problem: np.column_stack((
        np.full(problem["n_resonators"], 0.001),
        np.full(problem["n_resonators"], 0.010),
        np.full(problem["n_resonators"], 0.003),
    )))
    depth_violation = oracle.evaluate(lambda problem: np.column_stack((
        np.full(
            problem["n_resonators"],
            problem["maximum_total_depth_m"] - 0.003,
        ),
        np.full(problem["n_resonators"], 0.010),
        np.full(problem["n_resonators"], 0.003),
    )))
    independent = [
        _independent_record(oracle, instance, index)
        for index, instance in enumerate(oracle.INSTANCES)
    ]
    deterministic = bool(
        json.dumps(baseline, sort_keys=True, allow_nan=False)
        == json.dumps(baseline_replay, sort_keys=True, allow_nan=False)
    )
    invalid = (nonfinite, wrong_shape, out_of_bounds, depth_violation)
    proxy_gaps = [
        row["nominal_reference_proxy_minus_distributed_utility"]
        for row in independent
    ]
    difficulty_passed = bool(
        0.05 < baseline["development_exact_utility"] < 0.10
        and 0.05 < baseline["heldout_exact_utility"] < 0.10
        and nominal["combined_score"] > 0.999999
        and nominal["heldout_policy_score"] > 0.999999
        and nominal["robustness_score"] > 0.90
        and nominal["heldout_robustness_score"] > 0.90
        and robust["robustness_score"] > 0.999999
        and robust["heldout_robustness_score"] > 0.999999
        and robust["combined_score"] > 0.90
        and robust["heldout_policy_score"] > 0.90
        and max(proxy_gaps) < -0.25
    )
    execution_passed = bool(
        oracle.ABSORBER_V2
        and len(oracle.DEVELOPMENT_INSTANCES) == 4
        and len(oracle.HELDOUT_INSTANCES) == 2
        and len(oracle.SHIFT_SPECS) == 5
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["valid"] == 1.0
        and robust["valid"] == 1.0
        and deterministic
        and all(
            row["valid"] == 0.0
            and row["combined_score"] == 0.0
            and row["raw_score"] == 0.0
            for row in invalid
        )
        and all(row["passed"] for row in independent)
        and difficulty_passed
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "REDUCED_ORDER_ACOUSTIC_ABSORBER_TASK_CALIBRATION_NOT_"
            "THERMOVISCOUS_FEA_IMPEDANCE_TUBE_OR_PRODUCT_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "task_dimensions": {
            "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "frequency_samples_per_instance": oracle.FREQUENCY_SAMPLES,
            "resonator_count_range": [
                min(row["problem"]["n_resonators"] for row in oracle.INSTANCES),
                max(row["problem"]["n_resonators"] for row in oracle.INSTANCES),
            ],
            "frequency_range_hz": [
                min(row["problem"]["frequency_band_hz"][0] for row in oracle.INSTANCES),
                max(row["problem"]["frequency_band_hz"][1] for row in oracle.INSTANCES),
            ],
            "maximum_total_depth_range_m": [
                min(row["problem"]["maximum_total_depth_m"] for row in oracle.INSTANCES),
                max(row["problem"]["maximum_total_depth_m"] for row in oracle.INSTANCES),
            ],
        },
        "reference_method": {
            "family": (
                "log-spaced target frequencies with common neck radius and length; "
                "cavity depths follow the public low-frequency resonance relation"
            ),
            "parameter_bounds": {
                "low_frequency_multiplier": [0.60, 1.40],
                "high_frequency_multiplier": [0.65, 1.50],
                "neck_radius_m": "instance public bounds",
                "neck_length_m": "instance public bounds",
            },
            "optimizer": "SciPy differential_evolution plus polish",
            "nominal_seeds": [100 + index for index in range(len(oracle.INSTANCES))],
            "robust_seeds": [200 + index for index in range(len(oracle.INSTANCES))],
            "population_size_multiplier": POPULATION_SIZE,
            "nominal_maximum_iterations": NOMINAL_MAXITER,
            "robust_maximum_iterations": ROBUST_MAXITER,
            "tolerance": OPTIMIZER_TOLERANCE,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "weak_baseline": _compact(baseline),
        "nominal_reference_policy": _compact(nominal),
        "robust_reference_policy": _compact(robust),
        "invalid_artifact_checks": {
            "nonfinite": _compact(nonfinite),
            "wrong_shape": _compact(wrong_shape),
            "out_of_bounds": _compact(out_of_bounds),
            "depth_violation": _compact(depth_violation),
        },
        "independent_equation_and_reference_checks": independent,
        "determinism_check": {
            "exact_json_replay": deterministic,
            "passed": deterministic,
        },
        "difficulty_gate": {
            "baseline_development_exact_utility_interval": [0.05, 0.10],
            "baseline_heldout_exact_utility_interval": [0.05, 0.10],
            "required_nominal_reference_score": 0.999999,
            "minimum_cross_robustness_score": 0.90,
            "minimum_distributed_minus_proxy_gap": 0.25,
            "passed": difficulty_passed,
        },
        "limitations": [
            "The locally reacting reduced-order model omits thermal boundary-layer loss, inter-cell coupling, structural elasticity, grazing flow, nonlinear response and detailed fabrication constraints.",
            "The public low-frequency proxy is intentionally cheaper and disagrees strongly with the distributed dynamic-density model; it is a diagnostic, not experimental truth.",
            "The fixed nominal and robust witnesses are strong reproducible members of a four-parameter family, not certificates of global optimality.",
            "The deterministic development and held-out instances are repository-visible; server-held procedural bands and independent domain review remain pending.",
            "Engineering or product claims require thermoviscous finite-element and impedance-tube replication.",
            "Task calibration does not measure GPT-5.5, feedback causality, population performance or autonomous scientific discovery.",
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
