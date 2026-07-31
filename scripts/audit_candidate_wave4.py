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
from frontier_science.registry import find_task  # noqa: E402


def _oracle(task_id: str):
    path = find_task(task_id, include_uncertified=True).task_dir / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location(
        "wave4_audit_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_module(task_id: str):
    path = find_task(task_id, include_uncertified=True).task_dir / "solution.py"
    spec = importlib.util.spec_from_file_location(
        "wave4_candidate_" + task_id.replace("/", "_"), path
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
    source = (find_task(
        "FluidMechanics/StokesShapeDrag", include_uncertified=True
    ).task_dir / "verification/evaluator.py").read_text(
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
    calibration_path = ROOT / "scripts/calibrate_convection_diffusion_v2.py"
    spec = importlib.util.spec_from_file_location(
        "wave4_convection_diffusion_calibration", calibration_path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load ConvectionDiffusionOpt-v2 calibration")
    calibration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calibration)
    baseline = oracle.evaluate(calibration._always_abstain)
    classical = oracle.evaluate(calibration._classical_policy(oracle, True))
    one_experiment = oracle.evaluate(
        calibration._classical_policy(oracle, False)
    )
    reference = oracle.evaluate(calibration._ReferencePolicy(oracle))
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda *_args: {
            "parameters": np.full(5, np.nan),
            "source_positions": np.full((4, 2), np.nan),
            "source_strengths": np.full(4, np.nan),
            "confidence": np.nan,
            "abstain": False,
        })
    return {
        "task": "HeatTransfer/ConvectionDiffusionOpt",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 interface exposed neither target observations nor an experiment "
            "callback, forcing candidates to guess one embedded field, while non-finite "
            "sources received full score"
        ),
        "resolved_defect": (
            "v2 supplies a visible target plus a charged calibration callback over eleven "
            "development/held-out homogeneous, null and heterogeneous worlds; it separately "
            "scores five-parameter mechanism recovery, diagnostic prediction, four-source "
            "design, four physical shifts, transfer, refusal and false discovery"
        ),
        "development_world_count": len(oracle.DEVELOPMENT_SPECS),
        "heldout_world_count": len(oracle.HELDOUT_SPECS),
        "shift_count": len(oracle.SHIFT_SPECS),
        "experiment_budget_units": oracle.EXPERIMENT_BUDGET_UNITS,
        "baseline_score": float(baseline["combined_score"]),
        "classical_score": float(classical["combined_score"]),
        "classical_heldout_score": float(classical["heldout_policy_score"]),
        "classical_robustness": float(classical["robustness_score"]),
        "one_experiment_score": float(one_experiment["combined_score"]),
        "one_experiment_heldout_score": float(
            one_experiment["heldout_policy_score"]
        ),
        "reference_score": float(reference["combined_score"]),
        "reference_robustness": float(reference["robustness_score"]),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": bool(
            oracle.CONVECTION_DIFFUSION_V2
            and len(oracle.DEVELOPMENT_SPECS) == 6
            and len(oracle.HELDOUT_SPECS) == 5
            and len(oracle.SHIFT_SPECS) == 4
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and 0.80 < classical["combined_score"] < 0.97
            and 0.80 < classical["heldout_policy_score"] < 0.97
            and classical["robustness_score"] > 0.80
            and classical["development_mean_budget_units"]
            == oracle.EXPERIMENT_BUDGET_UNITS
            and classical["development_false_discovery_rate"] == 0.0
            and classical["heldout_false_discovery_rate"] == 0.0
            and one_experiment["combined_score"] < 1.0e-8
            and one_experiment["heldout_policy_score"] < 1.0e-8
            and reference["combined_score"] == 1.0
            and reference["robustness_score"] == 1.0
            and reference["heldout_policy_score"] == 1.0
            and reference["heldout_robustness_score"] == 1.0
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
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
    baseline = oracle.evaluate(oracle._weak_baseline_design)
    nominal = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=False)
    )
    robust = oracle.evaluate(
        lambda problem: oracle.reference_policy(problem, robust=True)
    )
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda problem: {
            "passive_thicknesses_mm": np.full(
                (problem["archive_size"], problem["n_layers"]), np.nan
            ),
            "active_thicknesses_mm": np.full(
                (problem["archive_size"], problem["n_layers"]), np.nan
            ),
        })
    return {
        "task": "ParticlePhysics/CalorimeterDesign",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 fixed 30-layer, 10 GeV oracle documented a 3.8 percent "
            "uniform baseline that actually contained only 10.7 radiation lengths, "
            "returned 100 percent resolution and let non-finite layers score one"
        ),
        "resolved_defect": (
            "v2 returns three cost-conditioned design curves over six changing layer/"
            "energy/noise/material regimes, uses normalized gamma-profile integrals "
            "and explicit resolution components, finite fail-closed depth/mass/length/"
            "cost envelopes, same-model nominal and worst-shift witnesses, interleaved "
            "held-out regimes and five sealed fabrication/calibration shifts"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "archive_size": int(oracle.ARCHIVE_SIZE),
        "shift_count": len(oracle.SHIFT_SPECS),
        "energy_range_gev": [
            min(min(row["problem"]["energies_gev"])
                for row in oracle.INSTANCES),
            max(max(row["problem"]["energies_gev"])
                for row in oracle.INSTANCES),
        ],
        "baseline_score": float(baseline["combined_score"]),
        "baseline_mean_resolution": float(
            baseline["development_mean_resolution"]
        ),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_heldout_score": float(
            nominal["heldout_policy_score"]
        ),
        "nominal_reference_robustness": float(
            nominal["robustness_score"]
        ),
        "nominal_reference_shift_geometry_feasibility_rate": float(
            nominal["development_shift_geometry_feasibility_rate"]
        ),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_heldout_score": float(
            robust["heldout_policy_score"]
        ),
        "robust_reference_robustness": float(
            robust["robustness_score"]
        ),
        "robust_reference_heldout_robustness": float(
            robust["heldout_robustness_score"]
        ),
        "robust_reference_shift_geometry_feasibility_rate": float(
            robust["development_shift_geometry_feasibility_rate"]
        ),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": (
            oracle.CALORIMETER_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and oracle.ARCHIVE_SIZE == 3
            and len(oracle.SHIFT_SPECS) == 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["robustness_score"] == 0.0
            and 0.08 < baseline["development_mean_resolution"] < 0.09
            and nominal["valid"] == 1.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and nominal["robustness_score"] == 0.0
            and nominal["development_shift_geometry_feasibility_rate"] < 0.60
            and 0.70 < robust["combined_score"] < 0.90
            and 0.65 < robust["heldout_policy_score"] < 0.90
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and robust["development_shift_geometry_feasibility_rate"] == 1.0
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
    }


def _hartree_fock():
    oracle = _oracle("QuantumChemistry/HartreeFockSCF")
    baseline_module = _candidate_module("QuantumChemistry/HartreeFockSCF")
    baseline = oracle.evaluate(baseline_module.solve_restricted_hf)
    reference = oracle.evaluate(oracle.reference_policy)
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(lambda problem: np.full(
            (
                len(problem["overlap"]),
                int(problem["occupied_orbital_count"]),
            ),
            np.nan,
        ))
    baseline_rows = {row["name"]: row for row in baseline["per_instance"]}
    reference_rows = {row["name"]: row for row in reference["per_instance"]}
    development_hard = baseline_rows[
        "dev_h8_ring_symmetry_breaking_sto3g"
    ]
    heldout_hard = baseline_rows[
        "heldout_h4_ring_symmetry_breaking_sto3g"
    ]
    return {
        "task": "QuantumChemistry/HartreeFockSCF",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed two-coefficient H2 toy used inconsistent hand-entered integrals, "
            "placed its baseline at the complete grid minimum, normalized against an "
            "unreachable energy and awarded full score to non-finite orbitals"
        ),
        "resolved_defect": (
            "v2 uses seven reproducible finite-basis closed-shell Hamiltonians, a finite "
            "occupied-space artifact, independently recomputed RHF equations, a valid "
            "single-start DIIS zero point, internally stable multistart witnesses, a "
            "different-size held-out symmetry-breaking ring and separate physical-shift, "
            "representation-invariance and occupied-virtual stability axes"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_raw_score": float(baseline["raw_score"]),
        "baseline_robustness": float(baseline["robustness_score"]),
        "baseline_development_stability_rate": float(
            baseline["development_stability_rate"]
        ),
        "baseline_heldout_stability_rate": float(
            baseline["heldout_stability_rate"]
        ),
        "reference_score": float(reference["combined_score"]),
        "reference_robustness": float(reference["robustness_score"]),
        "reference_heldout_score": float(reference["heldout_policy_score"]),
        "reference_heldout_robustness": float(
            reference["heldout_robustness_score"]
        ),
        "development_hard_energy_gap_hartree": float(
            development_hard["energy_error_hartree"]
        ),
        "development_hard_baseline_minimum_curvature": float(
            development_hard["minimum_stability_curvature"]
        ),
        "development_hard_reference_minimum_curvature": float(
            reference_rows["dev_h8_ring_symmetry_breaking_sto3g"][
                "minimum_stability_curvature"
            ]
        ),
        "heldout_hard_energy_gap_hartree": float(
            heldout_hard["energy_error_hartree"]
        ),
        "heldout_hard_baseline_minimum_curvature": float(
            heldout_hard["minimum_stability_curvature"]
        ),
        "heldout_hard_reference_minimum_curvature": float(
            reference_rows["heldout_h4_ring_symmetry_breaking_sto3g"][
                "minimum_stability_curvature"
            ]
        ),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": bool(
            oracle.HARTREE_FOCK_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 3
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["robustness_score"] == 0.0
            and baseline["development_stability_rate"] == 0.75
            and baseline["heldout_stability_rate"] < 1.0
            and development_hard["energy_error_hartree"] > 0.03
            and development_hard["minimum_stability_curvature"] < -0.20
            and heldout_hard["energy_error_hartree"] > 0.05
            and heldout_hard["minimum_stability_curvature"] < -0.20
            and reference["valid"] == 1.0
            and reference["combined_score"] > 0.999
            and reference["robustness_score"] > 0.999
            and reference["heldout_policy_score"] > 0.99
            and reference["heldout_robustness_score"] > 0.99
            and reference["development_stability_rate"] == 1.0
            and reference["heldout_stability_rate"] == 1.0
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
    }


def _mosfet():
    oracle = _oracle("Semiconductor/MOSFETDoping")

    def policy(kind):
        def design(problem):
            for instance in oracle.INSTANCES:
                if instance["problem"] == problem:
                    if kind == "baseline":
                        return oracle._baseline_archive(problem)
                    return oracle._reference_archive(instance, kind)
            raise ValueError("unknown MOSFET problem")
        return design

    baseline = oracle.evaluate(policy("baseline"))
    nominal = oracle.evaluate(policy("nominal"))
    robust = oracle.evaluate(policy("robust"))
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(
            lambda _problem: np.full((oracle.MIN_ARCHIVE_SIZE, 6), np.nan)
        )
    return {
        "task": "Semiconductor/MOSFETDoping",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed v1 contract labeled 1e15--1e20 concentrations as per-m3, placing "
            "its entire range roughly six orders below semiconductor doping scales, and "
            "normalized one clipped barrier proxy against an unrelated Ion/Ioff anchor"
        ),
        "resolved_defect": (
            "v2 uses log10 cm^-3 Gaussian background/source/drain pockets, four development "
            "and two held-out devices, screened-Poisson drain coupling, MOS electrostatics, "
            "Caughey-Thomas mobility, charge-sheet currents, random-dopant variation, hard "
            "process/device gates, Pareto hypervolume and six sealed operation/process shifts"
        ),
        "model_scope": "transparent reduced-order compact nMOS model; not TCAD",
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "shift_count": len(oracle.SHIFT_SPECS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_heldout_score": float(baseline["heldout_policy_score"]),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_heldout_score": float(nominal["heldout_policy_score"]),
        "nominal_reference_robustness": float(nominal["robustness_score"]),
        "nominal_reference_shift_feasibility_rate": float(
            nominal["development_shift_feasibility_rate"]
        ),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_heldout_score": float(robust["heldout_policy_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "robust_reference_heldout_robustness": float(
            robust["heldout_robustness_score"]
        ),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": bool(
            oracle.MOSFET_DOPING_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and len(oracle.SHIFT_SPECS) == 6
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["heldout_policy_score"] == 0.0
            and nominal["valid"] == 1.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and nominal["robustness_score"] < 0.05
            and nominal["development_shift_feasibility_rate"] < 0.90
            and robust["valid"] == 1.0
            and 0.85 < robust["combined_score"] < 0.98
            and 0.80 < robust["heldout_policy_score"] < 0.98
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and robust["development_shift_feasibility_rate"] == 1.0
            and robust["heldout_shift_feasibility_rate"] == 1.0
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
    }


def _rankine():
    oracle = _oracle("Thermodynamics/RankineCycleOpt")

    def policy(kind):
        def design(problem):
            for instance in oracle.INSTANCES:
                if instance["problem"] == problem:
                    if kind == "baseline":
                        return oracle._baseline_archive(problem)
                    return oracle._reference_archive(instance, kind)
            raise ValueError("unknown Rankine problem")
        return design

    baseline = oracle.evaluate(policy("baseline"))
    nominal = oracle.evaluate(policy("nominal"))
    robust = oracle.evaluate(policy("robust"))
    with np.errstate(all="ignore"):
        nonfinite = oracle.evaluate(
            lambda _problem: np.full((oracle.MIN_ARCHIVE_SIZE, 4), np.nan)
        )
    maximum_residual = max(
        row.get("maximum_front_energy_balance_residual_kj_kg", 0.0)
        for result in (baseline, nominal, robust)
        for row in result["per_instance"]
    )
    return {
        "task": "Thermodynamics/RankineCycleOpt",
        "admission": "candidate",
        "superseded_v1_defect": (
            "the removed polynomial steam surrogate assigned zero efficiency to its public "
            "baseline and below 6.6 percent on a broad feasible grid while normalizing "
            "against an unrelated 46 percent anchor"
        ),
        "resolved_defect": (
            "v2 uses self-contained IAPWS-IF97 Regions 1, 2 and 4, six varying operating "
            "regimes, hard moisture/material/energy-balance gates, condition-aware "
            "efficiency-versus-specific-work Pareto archives, fixed-seed Sobol witnesses "
            "and five sealed weather/degradation/material shifts"
        ),
        "instance_count": len(oracle.INSTANCES),
        "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
        "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
        "shift_count": len(oracle.SHIFT_SPECS),
        "baseline_score": float(baseline["combined_score"]),
        "baseline_mean_front_efficiency": float(
            baseline["development_mean_front_efficiency"]
        ),
        "baseline_mean_front_specific_net_work_kj_kg": float(
            baseline["development_mean_front_specific_net_work_kj_kg"]
        ),
        "nominal_reference_score": float(nominal["combined_score"]),
        "nominal_reference_heldout_score": float(nominal["heldout_policy_score"]),
        "nominal_reference_shift_feasibility_rate": float(
            nominal["development_shift_feasibility_rate"]
        ),
        "robust_reference_score": float(robust["combined_score"]),
        "robust_reference_robustness": float(robust["robustness_score"]),
        "robust_reference_heldout_robustness": float(
            robust["heldout_robustness_score"]
        ),
        "maximum_front_energy_balance_residual_kj_kg": float(maximum_residual),
        "nonfinite_task_score": float(nonfinite["combined_score"]),
        "nonfinite_task_valid": bool(nonfinite["valid"]),
        "rebuild_passed": True,
        "passed": bool(
            oracle.RANKINE_V2
            and len(oracle.DEVELOPMENT_INSTANCES) == 4
            and len(oracle.HELDOUT_INSTANCES) == 2
            and len(oracle.SHIFT_SPECS) == 5
            and baseline["valid"] == 1.0
            and baseline["combined_score"] == 0.0
            and baseline["robustness_score"] == 0.0
            and baseline["development_shift_feasibility_rate"] == 1.0
            and 0.35 < baseline["development_mean_front_efficiency"] < 0.43
            and 1300.0
            < baseline["development_mean_front_specific_net_work_kj_kg"]
            < 1700.0
            and nominal["valid"] == 1.0
            and nominal["combined_score"] > 0.999999
            and nominal["heldout_policy_score"] > 0.999999
            and nominal["development_shift_feasibility_rate"] < 0.80
            and robust["valid"] == 1.0
            and 0.40 < robust["combined_score"] < 0.60
            and robust["robustness_score"] > 0.999999
            and robust["heldout_robustness_score"] > 0.999999
            and robust["development_shift_feasibility_rate"] == 1.0
            and maximum_residual <= 2.0e-8
            and nonfinite["combined_score"] == 0.0
            and nonfinite["raw_score"] == 0.0
            and not bool(nonfinite["valid"])
        ),
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
            "recommended_candidate_count": sum(
                row["admission"] == "candidate" for row in records
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
