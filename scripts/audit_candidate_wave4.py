#!/usr/bin/env python3
"""Reproduce scientific-admission failures in the final unscreened candidate tranche."""

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _oracle(task_id: str):
    path = ROOT / "benchmarks" / task_id / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "wave4_audit_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _acoustic_absorber():
    oracle = _oracle("AcousticMetamaterials/BroadbandAbsorber")
    baseline = oracle.evaluate(
        lambda problem: oracle._weak_baseline_design(problem)
    )
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda problem: np.full(
            (problem["n_resonators"], 3), np.nan
        ))
    return {
        "task": "AcousticMetamaterials/BroadbandAbsorber",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 oracle mixed volume-flow and surface impedance, clipped invalid "
            "geometry, evaluated one fixed eight-cell band and normalized against an "
            "unrelated 0.92 literature value"
        ),
        "resolved_defect": (
            "v2 uses six varying bands/counts/thicknesses, finite fail-closed geometry, "
            "Stinson circular-tube dynamic density, equal-area surface admittance, "
            "same-model replayable nominal/robust witnesses and separate proxy, held-out, "
            "angle, air-property and manufacturing metrics"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "shift_count": len(oracle.SHIFT_SPECS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_exact_utility": float(baseline["development_exact_utility"]),
        "baseline_robustness": float(baseline["robustness_score"]),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_robustness": float(nominal["robustness_score"]),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": (
            oracle.ABSORBER_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and len(oracle.SHIFT_SPECS) >= 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["robustness_score"] == 0.0
            and 0.05 < baseline["development_exact_utility"] < 0.10
            and nominal["valid"] == 1.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and nominal["robustness_score"] > 0.90
            and robust["valid"] == 1.0
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and robust["combined_score"] > 0.90
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
    }


def _prosthetic_joint():
    oracle = _oracle("Biomechanics/ProstheticJointDesign")
    baseline_parameters = np.array([30.0] * 4 + [50.0] * 4)
    upper_parameters = np.array([50.0] * 4 + [100.0] * 4)
    baseline_quality = oracle._evaluate_joint(baseline_parameters)
    upper_quality = oracle._evaluate_joint(upper_parameters)
    upper_metrics = oracle.evaluate(lambda _n: upper_parameters.copy())
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda n: np.full(n, np.nan))
    return {
        "task": "Biomechanics/ProstheticJointDesign",
        "admission": "quarantine",
        "defect": (
            "the hand-written rollback/conformity product is solved exactly by setting all "
            "radii to their upper bounds, which is defined to be twice baseline and full score; "
            "non-finite geometry also passes task-level validation"
        ),
        "baseline_joint_quality": float(baseline_quality),
        "upper_corner_joint_quality": float(upper_quality),
        "upper_to_baseline_ratio": float(upper_quality / baseline_quality),
        "upper_corner_score": float(upper_metrics["combined_score"]),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "passed": (
            abs(upper_quality / baseline_quality - 2.0) < 1e-12
            and upper_metrics["combined_score"] == 1.0
            and nonfinite["combined_score"] == 1.0
        ),
    }


def _distillation():
    oracle = _oracle("ChemicalProcess/DistillationColumnDesign")
    baseline = oracle.evaluate(oracle._baseline_design)
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda problem: {
            **oracle._baseline_design(problem), "reflux_ratio": np.nan,
        })
    maximum_stage_residual = max(
        row["baseline_nominal"]["maximum_stage_balance_residual"]
        for row in oracle.INSTANCES
    )
    maximum_overall_residual = max(
        row["baseline_nominal"]["overall_component_balance_residual"]
        for row in oracle.INSTANCES
    )
    return {
        "task": "ChemicalProcess/DistillationColumnDesign",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 tray calculation hard-coded distillate purity to 0.99, never "
            "accepted feed composition and lacked a feed-product material balance"
        ),
        "resolved_defect": (
            "v2 uses six varying binary separations, exact tray/feed-stage decisions, "
            "total-condenser/feed-stage/partial-reboiler light-component balances, product "
            "purity and recovery gates, fixed-seed nominal/robust witnesses, interleaved "
            "held-out regimes and five sealed operating shifts"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "shift_count": len(oracle.SHIFT_SPECS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_feasibility_rate": float(baseline["feasibility_rate"]),
        "maximum_baseline_stage_balance_residual": float(
            maximum_stage_residual
        ),
        "maximum_baseline_overall_balance_residual": float(
            maximum_overall_residual
        ),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_shift_feasibility_rate": float(
            nominal["development_shift_feasibility_rate"]
        ),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "robust_reference_heldout_robustness": float(
            robust["heldout_robustness_score"]
        ),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": (
            oracle.DISTILLATION_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and len(oracle.SHIFT_SPECS) == 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["feasibility_rate"] == 1.0
            and maximum_stage_residual <= oracle.BALANCE_TOLERANCE
            and maximum_overall_residual <= oracle.BALANCE_TOLERANCE
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and nominal["development_shift_feasibility_rate"] <= 0.25
            and robust["combined_score"] > 0.90
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and nonfinite["combined_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
    }


def _flame_speed():
    oracle = _oracle("Combustion/FlameSpeedOptimization")
    methane = oracle._flame_speed(np.array([1.0, 0.0, 0.0, 1.0, 0.0]))
    claimed_reference = oracle._flame_speed(np.array([0.2, 0.7, 0.1, 1.1, 0.0]))
    rng = np.random.default_rng(20260721)
    speeds = []
    for _ in range(2048):
        fuel = rng.dirichlet(np.ones(3))
        parameters = np.concatenate((fuel, [rng.uniform(0.5, 2.0), rng.uniform(0.0, 0.5)]))
        speeds.append(oracle._flame_speed(parameters))
    saturated_fraction = float(np.mean(np.asarray(speeds) >= 5.0))
    return {
        "task": "Combustion/FlameSpeedOptimization",
        "admission": "quarantine",
        "defect": (
            "the simplified algebraic formula clips both methane baseline and claimed "
            "H2-enriched reference at 5 m/s, leaving a zero normalization denominator; most "
            "random feasible mixtures also hit the same cap"
        ),
        "methane_baseline_speed_m_s": float(methane),
        "claimed_reference_speed_m_s": float(claimed_reference),
        "normalization_denominator": float(claimed_reference - methane),
        "sampled_cap_fraction": saturated_fraction,
        "passed": methane == 5.0 and claimed_reference == 5.0 and saturated_fraction > 0.75,
    }


def _stokes_drag():
    oracle = _oracle("FluidMechanics/StokesShapeDrag")
    circle = np.concatenate(([1.0], np.zeros(2 * oracle.N_MODES)))
    radius, theta = oracle._body_from_fourier(circle)
    circle_area = oracle._compute_area(radius, theta)
    circle_drag = oracle._compute_drag(radius, theta)
    source = (ROOT / "benchmarks/FluidMechanics/StokesShapeDrag/verification/evaluator.py").read_text(
        encoding="utf-8"
    )
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(
            lambda n_modes, _area: np.full(2 * n_modes + 1, np.nan)
        )
    return {
        "task": "FluidMechanics/StokesShapeDrag",
        "admission": "quarantine",
        "defect": (
            "the oracle does not solve Stokes flow: drag is only normalized perimeter. At "
            "fixed area the isoperimetric inequality makes the circle optimal, contradicting "
            "the declared 0.85 non-circular reference; non-finite shapes pass task validation"
        ),
        "oracle_explicitly_uses_perimeter_proxy": "C_D = perimeter / circle_perimeter" in source,
        "circle_area": float(circle_area),
        "circle_drag": float(circle_drag),
        "declared_reference_drag": 0.85,
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "passed": (
            "C_D = perimeter / circle_perimeter" in source
            and abs(circle_area - math.pi) < 1e-12
            and circle_drag > 0.99
            and nonfinite["combined_score"] == 1.0
        ),
    }


def _convection_diffusion():
    oracle = _oracle("HeatTransfer/ConvectionDiffusionOpt")
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda _nx, _ny, n_sources: {
            "positions": np.full((n_sources, 2), np.nan),
            "strengths": np.full(n_sources, np.nan),
        })
    return {
        "task": "HeatTransfer/ConvectionDiffusionOpt",
        "admission": "quarantine",
        "defect": (
            "the program receives only grid dimensions and source count, not the fixed hidden "
            "target field or an experiment callback, so the inverse-design claim requires "
            "guessing one embedded answer; non-finite sources pass task-level validity"
        ),
        "entrypoint_arguments": ["nx", "ny", "n_sources"],
        "entrypoint_receives_target_or_experiment": False,
        "hidden_target_instance_count": 1,
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "passed": nonfinite["combined_score"] == 1.0 and bool(nonfinite["valid"]),
    }


def _inventory():
    oracle = _oracle("InventoryManagement/MultiEchelonStock")
    service_levels = []
    costs = []
    for upstream_factory, upstream_warehouse in ((0, 0), (200, 0), (0, 200), (200, 200)):
        cost, service = oracle._simulate(
            np.array([upstream_factory, upstream_warehouse, 40.0])
        )
        costs.append(float(cost))
        service_levels.append(float(service))
    return {
        "task": "InventoryManagement/MultiEchelonStock",
        "admission": "quarantine",
        "defect": (
            "each stage receives its own previous orders without upstream fulfillment, so "
            "retailer service is exactly invariant to factory and warehouse stocks; the model "
            "does not implement a coupled multi-echelon supply chain"
        ),
        "upstream_stock_pairs": [[0, 0], [200, 0], [0, 200], [200, 200]],
        "service_levels_at_fixed_retailer_stock": service_levels,
        "costs_at_fixed_retailer_stock": costs,
        "service_level_range": max(service_levels) - min(service_levels),
        "passed": max(service_levels) - min(service_levels) == 0.0,
    }


def _calorimeter():
    oracle = _oracle("ParticlePhysics/CalorimeterDesign")
    passive = np.full(oracle.N_LAYERS, 2.0)
    active = np.full(oracle.N_LAYERS, 4.0)
    sigma, sampling = oracle._compute_resolution(passive, active)
    total_x0 = float(np.sum(passive) / oracle.X0_PB)
    metrics = oracle.evaluate(lambda n, _length: {
        "passive_thicknesses_mm": np.full(n, 2.0),
        "active_thicknesses_mm": np.full(n, 4.0),
    })
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda n, _length: {
            "passive_thicknesses_mm": np.full(n, np.nan),
            "active_thicknesses_mm": np.full(n, np.nan),
        })
    return {
        "task": "ParticlePhysics/CalorimeterDesign",
        "admission": "quarantine",
        "defect": (
            "the documented uniform baseline is claimed to have 3.8% resolution but contains "
            "only 10.7 radiation lengths, triggers the oracle's containment failure, and is "
            "actually scored as 100%; non-finite layers also receive full task score"
        ),
        "baseline_total_radiation_lengths": total_x0,
        "minimum_required_radiation_lengths": float(oracle.MIN_X0_TOTAL),
        "documented_baseline_sigma": 0.038,
        "oracle_baseline_sigma": float(sigma),
        "oracle_baseline_sampling_fraction": float(sampling),
        "baseline_marked_valid": bool(metrics["valid"]),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "passed": total_x0 < oracle.MIN_X0_TOTAL and sigma == 1.0 and nonfinite["combined_score"] == 1.0,
    }


def _hartree_fock():
    oracle = _oracle("QuantumChemistry/HartreeFockSCF")
    angles = np.linspace(0.0, 2.0 * math.pi, 20001)
    energies = np.asarray([
        oracle._hf_energy(np.array([math.cos(angle), math.sin(angle)]))
        for angle in angles
    ])
    grid_minimum = float(np.min(energies))
    baseline = float(oracle._hf_energy(np.array([1.0, 1.0])))
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda *_args: np.array([np.nan, np.nan]))
    return {
        "task": "QuantumChemistry/HartreeFockSCF",
        "admission": "quarantine",
        "defect": (
            "a dense scan of the complete two-coefficient projective orbital space finds the "
            "baseline is already the oracle minimum at +0.444915 Ha, while normalization "
            "claims an unreachable -1.1167 Ha H2/STO-3G energy; non-finite orbitals score one"
        ),
        "projective_grid_size": len(angles),
        "oracle_grid_minimum_hartree": grid_minimum,
        "oracle_baseline_hartree": baseline,
        "declared_exact_hf_hartree": float(oracle.E_HF_EXACT),
        "minimum_minus_baseline_hartree": grid_minimum - baseline,
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "passed": abs(grid_minimum - baseline) < 1e-10 and oracle.E_HF_EXACT < baseline - 1.0 and nonfinite["combined_score"] == 1.0,
    }


def _mosfet():
    oracle = _oracle("Semiconductor/MOSFETDoping")
    maximum = np.full(oracle.N_POINTS, 1e20)
    potential = oracle._solve_poisson(maximum)
    ratio = oracle._compute_ion_ioff_ratio(maximum)
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(
            lambda n_points, _length: np.full(n_points, np.nan)
        )
    return {
        "task": "Semiconductor/MOSFETDoping",
        "admission": "quarantine",
        "defect": (
            "the stated per-m3 doping bounds are six orders below realistic semiconductor "
            "scales, producing only 48 microvolts and Ion/Ioff 1.0019 even at the upper bound "
            "versus the unrelated 1e8 anchor; this unit/normalization defect is independent "
            "of the current fail-closed non-finite path"
        ),
        "upper_bound_doping_per_m3": 1e20,
        "upper_bound_max_potential_v": float(np.max(potential)),
        "upper_bound_ion_ioff_ratio": float(ratio),
        "declared_reference_ratio": 1e8,
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "passed": bool(
            np.max(potential) < 1e-3
            and ratio < 1.01
            and nonfinite["combined_score"] == 0.0
        ),
    }


def _rankine():
    oracle = _oracle("Thermodynamics/RankineCycleOpt")
    baseline = oracle._compute_efficiency(np.array([10.0, 500.0, 10.0, 0.0]))
    efficiencies = []
    best_parameters = None
    best = -math.inf
    for pressure in np.linspace(5.0, 30.0, 11):
        for temperature in np.linspace(400.0, 620.0, 12):
            for condenser in np.linspace(3.0, 15.0, 7):
                for reheat in (0.0, 0.5, 1.0):
                    parameters = [pressure, temperature, condenser, reheat]
                    efficiency = oracle._compute_efficiency(parameters)
                    efficiencies.append(efficiency)
                    if efficiency > best:
                        best = efficiency
                        best_parameters = parameters
    return {
        "task": "Thermodynamics/RankineCycleOpt",
        "admission": "quarantine",
        "defect": (
            "the polynomial steam surrogate assigns zero efficiency to its public baseline; "
            "a 2,772-point feasible grid reaches only 6.55%, far below the unrelated 46% "
            "ultra-supercritical anchor"
        ),
        "baseline_efficiency": float(baseline),
        "coarse_grid_size": len(efficiencies),
        "coarse_grid_max_efficiency": float(best),
        "coarse_grid_best_parameters": [float(value) for value in best_parameters],
        "declared_reference_efficiency": 0.46,
        "passed": baseline == 0.0 and best < 0.1,
    }


def _traffic():
    oracle = _oracle("Transportation/TrafficSignalTiming")
    travel_time = oracle.LINK_LENGTH / oracle.SPEED
    corner = oracle.evaluate(lambda n, cycle, _demands: {
        "green_times": np.full(n, cycle - 15.0),
        "offsets": np.arange(n) * travel_time,
    })
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda n, _cycle, _demands: {
            "green_times": np.full(n, np.nan),
            "offsets": np.full(n, np.nan),
        })
    return {
        "task": "Transportation/TrafficSignalTiming",
        "admission": "quarantine",
        "defect": (
            "the model has only one traffic direction and no conflicting phase or shared "
            "green-time constraint, so setting every signal to maximum green with travel-time "
            "offsets trivially clips to full score; non-finite timing also scores one"
        ),
        "all_max_green_ideal_offset_score": float(corner["combined_score"]),
        "all_max_green_total_delay": float(corner["total_delay"]),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "passed": corner["combined_score"] == 1.0 and nonfinite["combined_score"] == 1.0,
    }


def audit() -> dict:
    records = [
        _acoustic_absorber(),
        _prosthetic_joint(),
        _distillation(),
        _flame_speed(),
        _stokes_drag(),
        _convection_diffusion(),
        _inventory(),
        _calorimeter(),
        _hartree_fock(),
        _mosfet(),
        _rankine(),
        _traffic(),
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
            "resolved_rebuild_count": sum(
                bool(row.get("rebuild_passed")) for row in records
            ),
            "reproduced_defect_count": sum(
                bool(row["passed"]) and row["admission"] == "quarantine"
                for row in records
            ),
            "recommended_quarantine_count": sum(
                row["admission"] == "quarantine" for row in records
            ),
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
