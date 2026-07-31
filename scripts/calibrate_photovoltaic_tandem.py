#!/usr/bin/env python3
"""Search and print PhotovoltaicTandemDesign-v1 reference witnesses."""

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
from scipy.optimize import brentq, differential_evolution


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Chemistry/PhotovoltaicTandemDesign"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)
from frontier_science.registry import find_task  # noqa: E402


def load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("pv_tandem_calibration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode(oracle, vector, count):
    gaps = np.sort(np.asarray(vector[:count], dtype=float))[::-1]
    depths = np.asarray(vector[count:], dtype=float)
    return {"bandgaps_ev": gaps, "optical_depths": depths}


def _valid(oracle, design, cap):
    gaps = design["bandgaps_ev"]
    depths = design["optical_depths"]
    cost = oracle.JUNCTION_OVERHEAD_COST * len(gaps) + np.sum(depths)
    return bool(
        cost <= float(cap) + 1.0e-10
        and (
            len(gaps) == 1
            or np.all(
                gaps[:-1] - gaps[1:]
                >= oracle.MINIMUM_BANDGAP_SEPARATION_EV
            )
        )
    )


def search_option(oracle, problem, option_index, robust, seed, maxiter, popsize):
    cap = float(problem["fabrication_budget_caps"][option_index])
    best = None
    for count in range(1, oracle.MAX_JUNCTIONS + 1):
        minimum = count * (
            oracle.JUNCTION_OVERHEAD_COST + oracle.OPTICAL_DEPTH_BOUNDS[0]
        )
        if minimum > cap:
            continue
        bounds = (
            [oracle.BANDGAP_BOUNDS_EV] * count
            + [oracle.OPTICAL_DEPTH_BOUNDS] * count
        )

        def objective(vector):
            design = _decode(oracle, vector, count)
            if not _valid(oracle, design, cap):
                return 10.0
            normalized = {
                "bandgaps_ev": design["bandgaps_ev"],
                "optical_depths": design["optical_depths"],
            }
            if robust:
                rows = oracle._shift_performances(problem, normalized)
                value = min(row["efficiency"] for row in rows.values())
            else:
                value = oracle._performance_for_design(problem, normalized)[
                    "efficiency"
                ]
            return -float(value)

        result = differential_evolution(
            objective,
            bounds,
            seed=int(seed + 101 * count),
            popsize=int(popsize),
            maxiter=int(maxiter),
            tol=1.0e-9,
            polish=True,
            workers=1,
            updating="immediate",
        )
        design = _decode(oracle, result.x, count)
        value = -float(result.fun)
        record = {
            "junction_count": count,
            "bandgaps_ev": [float(x) for x in design["bandgaps_ev"]],
            "optical_depths": [float(x) for x in design["optical_depths"]],
            "objective_efficiency": value,
            "function_evaluations": int(result.nfev),
        }
        if best is None or record["objective_efficiency"] > best[
            "objective_efficiency"
        ]:
            best = record
    if best is None:
        raise ValueError("no feasible photovoltaic reference")
    return best


def calibrate(maxiter=100, popsize=12):
    oracle = load_oracle()
    records = []
    for spec in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
        world = oracle._make_world(spec)
        problem = oracle._public_problem(world)
        row = {"seed": int(spec[0]), "nominal": [], "robust": []}
        for option in range(oracle.ARCHIVE_SIZE):
            print("seed=%d option=%d nominal" % (spec[0], option), flush=True)
            row["nominal"].append(search_option(
                oracle, problem, option, False,
                seed=int(spec[0]) * 10 + option,
                maxiter=maxiter, popsize=popsize,
            ))
            print("seed=%d option=%d robust" % (spec[0], option), flush=True)
            row["robust"].append(search_option(
                oracle, problem, option, True,
                seed=int(spec[0]) * 10 + option + 100000,
                maxiter=maxiter, popsize=popsize,
            ))
        records.append(row)
    return records


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _independent_ideal_efficiency(oracle, gaps_ev):
    """Reimplement infinite-absorber radiative detailed balance."""
    document = json.loads(oracle.DATA_PATH.read_text(encoding="utf-8"))
    rows = np.asarray(document["rows"], dtype=float)
    wavelength_nm = rows[:, 0]
    irradiance = rows[:, 2]
    wavelength_m = wavelength_nm * 1.0e-9
    h = 6.62607015e-34
    c = 299792458.0
    q = 1.602176634e-19
    k = 1.380649e-23
    energy_ev = 1239.8419843320026 / wavelength_nm
    photon_flux = irradiance / (energy_ev * q)
    exponent = (
        h * c / (wavelength_m * k * 300.0)
    )
    blackbody = (
        2.0 * math.pi * c / wavelength_m**4
        / np.expm1(np.clip(exponent, 0.0, 700.0)) * 1.0e-9
    )
    transmission = np.ones_like(wavelength_nm)
    short_circuit = []
    dark_current = []
    for gap in gaps_ev:
        absorptance = (energy_ev >= float(gap)).astype(float)
        accepted = transmission * absorptance
        short_circuit.append(
            q * float(np.trapz(photon_flux * accepted, wavelength_nm))
        )
        dark_current.append(
            q * float(np.trapz(blackbody * absorptance, wavelength_nm))
        )
        transmission *= 1.0 - absorptance
    short_circuit = np.asarray(short_circuit)
    dark_current = np.maximum(np.asarray(dark_current), 1.0e-300)
    thermal_voltage = k * 300.0 / q

    def derivative(current):
        voltage = thermal_voltage * np.sum(
            np.log1p((short_circuit - current) / dark_current)
        )
        voltage_slope = -thermal_voltage * np.sum(
            1.0 / (dark_current + short_circuit - current)
        )
        return float(voltage + current * voltage_slope)

    current = brentq(
        derivative,
        0.0,
        float(np.min(short_circuit)) * (1.0 - 1.0e-12),
        xtol=1.0e-12,
        rtol=1.0e-14,
    )
    voltage = thermal_voltage * np.sum(
        np.log1p((short_circuit - current) / dark_current)
    )
    return float(current * voltage) / float(np.trapz(irradiance, wavelength_nm))


def _reference_records(oracle):
    rows = []
    minimum_nominal = float("inf")
    minimum_robust = float("inf")
    for spec in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS:
        world = oracle._make_world(spec)
        problem = oracle._public_problem(world)
        baseline = oracle._validate_submission(
            oracle.baseline_policy(problem), problem
        )
        nominal = oracle._validate_submission(
            oracle._reference_submission(world, robust=False), problem
        )
        robust = oracle._validate_submission(
            oracle._reference_submission(world, robust=True), problem
        )
        options = []
        for option in range(oracle.ARCHIVE_SIZE):
            baseline_nominal = oracle._performance_for_design(
                problem, baseline[option]
            )["efficiency"]
            nominal_value = oracle._performance_for_design(
                problem, nominal[option]
            )["efficiency"]
            baseline_worst = min(
                row["efficiency"] for row in oracle._shift_performances(
                    problem, baseline[option]
                ).values()
            )
            robust_worst = min(
                row["efficiency"] for row in oracle._shift_performances(
                    problem, robust[option]
                ).values()
            )
            nominal_headroom = nominal_value - baseline_nominal
            robust_headroom = robust_worst - baseline_worst
            minimum_nominal = min(minimum_nominal, nominal_headroom)
            minimum_robust = min(minimum_robust, robust_headroom)
            options.append({
                "option_index": option,
                "fabrication_budget": problem["fabrication_budget_caps"][option],
                "nominal_junction_count": nominal[option]["junction_count"],
                "robust_junction_count": robust[option]["junction_count"],
                "baseline_nominal_efficiency": baseline_nominal,
                "nominal_reference_efficiency": nominal_value,
                "nominal_headroom": nominal_headroom,
                "baseline_worst_shift_efficiency": baseline_worst,
                "robust_reference_worst_shift_efficiency": robust_worst,
                "robust_headroom": robust_headroom,
            })
        rows.append({"world_seed": int(spec[0]), "options": options})
    return rows, minimum_nominal, minimum_robust


def audit():
    oracle = load_oracle()
    spec = find_task(
        "Photovoltaics/PhotovoltaicTandemDesign", include_uncertified=True
    )
    baseline = oracle.evaluate(oracle.baseline_policy)
    nominal = oracle.evaluate(oracle.nominal_reference_policy)
    robust = oracle.evaluate(oracle.robust_reference_policy)
    secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=120)
    references, minimum_nominal, minimum_robust = _reference_records(oracle)
    ideal_gaps = (
        (1.33720284,),
        (1.63179147, 0.96009112),
        (1.79229367, 1.20029685, 0.69869468),
        (2.00087736, 1.49345882, 1.11424413, 0.71512019),
    )
    ideal_limits = []
    maximum_independent_gap = 0.0
    for gaps in ideal_gaps:
        independent = _independent_ideal_efficiency(oracle, gaps)
        runtime = oracle._device_performance(
            oracle.BASE_WAVELENGTH_NM,
            oracle.BASE_GLOBAL_IRRADIANCE,
            300.0,
            gaps,
            [1.0e5] * len(gaps),
        )["efficiency"]
        maximum_independent_gap = max(
            maximum_independent_gap, abs(independent - runtime)
        )
        ideal_limits.append({
            "junction_count": len(gaps),
            "bandgaps_ev": list(gaps),
            "independent_efficiency": independent,
            "runtime_efficiency": runtime,
        })
    spectrum = json.loads(oracle.DATA_PATH.read_text(encoding="utf-8"))
    spectrum_power = float(np.trapz(
        np.asarray([row[2] for row in spectrum["rows"]]),
        np.asarray([row[0] for row in spectrum["rows"]]),
    ))
    visible = search_visible_metrics(secure)
    nominal_counts = {
        row["nominal_junction_count"]
        for world in references for row in world["options"]
    }
    nominal_counts_by_option = [set() for _ in range(oracle.ARCHIVE_SIZE)]
    robust_counts_by_option = [set() for _ in range(oracle.ARCHIVE_SIZE)]
    for world in references:
        for row in world["options"]:
            option = row["option_index"]
            nominal_counts_by_option[option].add(row["nominal_junction_count"])
            robust_counts_by_option[option].add(row["robust_junction_count"])
    execution_passed = bool(
        _sha256(oracle.DATA_PATH) == oracle.DATA_SHA256
        and len(spectrum["rows"]) == 2002
        and abs(spectrum_power - 1000.3706555734423) < 1.0e-10
        and maximum_independent_gap < 2.0e-10
        and minimum_nominal > 0.02
        and minimum_robust > 0.02
        and baseline["valid"] == 1.0
        and baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and nominal["combined_score"] == 1.0
        and nominal["heldout_policy_score"] == 1.0
        and robust["robustness_score"] == 1.0
        and robust["heldout_robustness_score"] == 1.0
        and robust["combined_score"] > 0.85
        and len(nominal_counts) >= 3
        and nominal_counts_by_option[0] == {1}
        and nominal_counts_by_option[1].issubset({2, 3})
        and 1 not in nominal_counts_by_option[1]
        and nominal_counts_by_option[2].issubset({3, 4})
        and 1 not in nominal_counts_by_option[2]
        and robust_counts_by_option == [{1}, {2}, {3}]
        and secure["valid"] == 1.0
        and secure["combined_score"] == 0.0
        and secure["candidate_instance_call_count"] == 8
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "DETERMINISTIC_REDUCED_ORDER_TANDEM_PHOTOVOLTAIC_OPTIMIZATION_"
            "CALIBRATION_NOT_DEVICE_MATERIAL_RECORD_EFFICIENCY_OR_EXPERIMENTAL_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Photovoltaics/PhotovoltaicTandemDesign",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                TASK / "verification/evaluator.py",
                TASK / "verification/astm_g173_v1.json",
                ROOT / "scripts/build_photovoltaic_spectrum_data.py",
            )
        },
        "spectrum_provenance": spectrum["source_provenance"],
        "spectrum_generated_sha256": _sha256(oracle.DATA_PATH),
        "spectrum_row_count": len(spectrum["rows"]),
        "spectrum_global_tilt_integral_w_m2": spectrum_power,
        "independent_ideal_limits": ideal_limits,
        "maximum_independent_runtime_efficiency_gap": maximum_independent_gap,
        "reference_method": {
            "optimizer": "SciPy differential_evolution plus polish",
            "search_space": "junction count one through four plus all band gaps and optical depths",
            "nominal_and_minimax_searched_separately": True,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "reference_records": references,
        "minimum_nominal_headroom": minimum_nominal,
        "minimum_robust_headroom": minimum_robust,
        "weak_baseline": baseline,
        "secure_sandbox_baseline": secure,
        "nominal_reference_policy": nominal,
        "robust_reference_policy": robust,
        "nominal_reference_junction_counts": sorted(nominal_counts),
        "nominal_reference_junction_counts_by_budget_option": [
            sorted(values) for values in nominal_counts_by_option
        ],
        "robust_reference_junction_counts_by_budget_option": [
            sorted(values) for values in robust_counts_by_option
        ],
        "metric_sealing": {"visible_metric_keys": sorted(visible)},
        "limitations": [
            "The deterministic reduced-order model is not a drift-diffusion, optical-transfer-matrix or multiphysics device simulation.",
            "It omits non-radiative recombination, transport, interfaces, tunnel junctions, luminescent coupling, resistance, thermal balance, actual materials and manufacturing yield.",
            "Fixed repository-visible spectra require server-held cohorts and contamination auditing.",
            "Reference designs are reproducible same-model search witnesses, not global optima or certified photovoltaic records.",
            "Engineering claims require higher-fidelity device simulation, manufacturability review and independent experimental validation.",
            "Task calibration does not measure GPT-5.5, feedback causality, population performance or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maxiter", type=int, default=100)
    parser.add_argument("--popsize", type=int, default=12)
    parser.add_argument(
        "--audit-only", action="store_true",
        help="audit the frozen witnesses without rerunning the expensive search",
    )
    args = parser.parse_args()
    records = audit() if args.audit_only else calibrate(args.maxiter, args.popsize)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(records, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print("Report: %s" % args.output.resolve())
    if args.audit_only:
        return 0 if records["execution_passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
