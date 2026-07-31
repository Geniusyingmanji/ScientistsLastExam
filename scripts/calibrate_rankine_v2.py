#!/usr/bin/env python3
"""Build and audit fixed-seed Rankine-v2 Pareto witnesses."""

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


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/RankineCycleOpt"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


IAPWS_VERSION = "1.5.4"
IAPWS_SDIST_SHA256 = (
    "9f0faa39a967d76fc5e5f95f61d922e135453192e02bf875d07242f13d6eaa55"
)
IF97_RELEASE_SHA256 = (
    "c92f887e989cbf074af1fa982083dc54195d57691eab4fbc950ef6098d4cf1f4"
)

# Twelve stable-liquid Region-1 points, twelve stable-vapor Region-2 points,
# and four Region-4 pressures evaluated at both saturated endpoints.  The
# states deliberately stay away from the Region-2/3 boundary so the independent
# package and this task exercise exactly the advertised Region-1/2/4 scope.
IAPWS_REGION1_GRID = (
    (300.0, 0.1), (320.0, 1.0), (350.0, 1.0),
    (300.0, 5.0), (400.0, 5.0), (500.0, 5.0),
    (300.0, 12.0), (400.0, 12.0), (500.0, 12.0),
    (550.0, 12.0), (450.0, 15.0), (580.0, 15.0),
)
IAPWS_REGION2_GRID = (
    (400.0, 0.01), (500.0, 0.01), (700.0, 0.01),
    (450.0, 0.1), (600.0, 0.1), (800.0, 0.1),
    (500.0, 1.0), (650.0, 1.0), (850.0, 1.0),
    (650.0, 12.0), (750.0, 12.0), (900.0, 12.0),
)
IAPWS_REGION4_PRESSURES = (0.01, 0.1, 1.0, 10.0)


def _load_oracle():
    verification = TASK / "verification"
    sys.path.insert(0, str(verification))
    try:
        spec = importlib.util.spec_from_file_location(
            "rankine_v2_calibration_oracle", verification / "evaluator.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load Rankine-v2 oracle")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _independent_iapws_check(oracle, require=False):
    if97 = sys.modules.get("if97")
    if if97 is None:
        raise RuntimeError("Rankine evaluator did not load its IF97 module")
    try:
        import iapws
        from iapws import IAPWS97
    except ImportError as exc:
        result = {
            "requested": bool(require),
            "performed": False,
            "required": bool(require),
            "package": "iapws",
            "expected_version": IAPWS_VERSION,
            "expected_sdist_sha256": IAPWS_SDIST_SHA256,
            "state_count": 0,
            "reason": "iapws==1.5.4 is not installed in this environment",
            "passed": not bool(require),
        }
        if require:
            result["import_error"] = type(exc).__name__
        return result

    observed_version = str(getattr(iapws, "__version__", "unknown"))
    keys = ("v", "h", "u", "s", "cp", "w")
    maximum_absolute_error = {key: 0.0 for key in keys}
    region_checks = []
    for region_name, grid, evaluator in (
        ("region1", IAPWS_REGION1_GRID, if97.region1),
        ("region2", IAPWS_REGION2_GRID, if97.region2),
    ):
        for temperature, pressure in grid:
            observed = evaluator(temperature, pressure)
            independent = IAPWS97(T=temperature, P=pressure)
            errors = {
                key: abs(float(observed[key]) - float(getattr(independent, key)))
                for key in keys
            }
            for key, value in errors.items():
                maximum_absolute_error[key] = max(
                    maximum_absolute_error[key], value
                )
            region_checks.append({
                "kind": region_name,
                "temperature_k": temperature,
                "pressure_mpa": pressure,
                "independent_region": int(independent.region),
                "maximum_absolute_property_error": max(errors.values()),
            })

    saturation_checks = []
    maximum_saturation_temperature_error = 0.0
    for pressure in IAPWS_REGION4_PRESSURES:
        observed = if97.saturation_state(pressure)
        for quality, phase in ((0, "liquid"), (1, "vapor")):
            independent = IAPWS97(P=pressure, x=quality)
            errors = {
                key: abs(
                    float(observed[phase][key])
                    - float(getattr(independent, key))
                )
                for key in ("v", "h", "u", "s")
            }
            for key, value in errors.items():
                maximum_absolute_error[key] = max(
                    maximum_absolute_error[key], value
                )
            temperature_error = abs(
                float(observed["T"]) - float(independent.T)
            )
            maximum_saturation_temperature_error = max(
                maximum_saturation_temperature_error, temperature_error
            )
            saturation_checks.append({
                "kind": "region4_saturated_" + phase,
                "pressure_mpa": pressure,
                "quality": quality,
                "independent_region": int(independent.region),
                "absolute_temperature_error_k": temperature_error,
                "maximum_absolute_property_error": max(errors.values()),
            })

    state_count = len(region_checks) + len(saturation_checks)
    passed = bool(
        observed_version == IAPWS_VERSION
        and state_count == 32
        and maximum_absolute_error["v"] <= 1.0e-12
        and maximum_absolute_error["h"] <= 2.0e-9
        and maximum_absolute_error["u"] <= 2.0e-9
        and maximum_absolute_error["s"] <= 2.0e-11
        and maximum_absolute_error["cp"] <= 2.0e-11
        and maximum_absolute_error["w"] <= 2.0e-8
        and maximum_saturation_temperature_error <= 2.0e-9
    )
    return {
        "requested": bool(require),
        "performed": True,
        "required": bool(require),
        "package": "iapws",
        "expected_version": IAPWS_VERSION,
        "observed_version": observed_version,
        "expected_sdist_sha256": IAPWS_SDIST_SHA256,
        "runtime_module_path": str(Path(iapws.__file__).resolve()),
        "state_count": state_count,
        "maximum_absolute_property_errors": maximum_absolute_error,
        "maximum_absolute_saturation_temperature_error_k": (
            maximum_saturation_temperature_error
        ),
        "region_checks": region_checks,
        "saturation_checks": saturation_checks,
        "passed": passed,
    }


def _shortlist(oracle, instance, nominal):
    problem = instance["problem"]
    feasible = [
        index for index, record in enumerate(nominal)
        if record["process_feasible"]
    ]
    selected = set(oracle._pareto_indices(nominal))
    qualities = {
        index: oracle._quality(problem, nominal[index]) for index in feasible
    }
    for weight in np.linspace(0.0, 1.0, 81):
        selected.update(sorted(
            feasible,
            key=lambda index: (
                weight * qualities[index][0]
                + (1.0 - weight) * qualities[index][1],
                qualities[index][0] + qualities[index][1],
                -index,
            ),
            reverse=True,
        )[:8])
    for criterion in (
        lambda point: point[0],
        lambda point: point[1],
        lambda point: point[0] * point[1],
        lambda point: min(point),
        lambda point: point[0] + point[1],
    ):
        selected.update(sorted(
            feasible,
            key=lambda index: (criterion(qualities[index]), -index),
            reverse=True,
        )[:24])
    return tuple(sorted(selected))


def _greedy_archive(oracle, problem, record_sets, allowed, robust):
    selected = []
    remaining = list(allowed)
    for _ in range(oracle.MAX_ARCHIVE_SIZE):
        best = None
        for index in remaining:
            take = selected + [index]
            hypervolumes = [
                oracle._hypervolume(problem, [records[row] for row in take])
                for records in record_sets
            ]
            if robust:
                objective = min(hypervolumes)
                secondary = sum(hypervolumes) / len(hypervolumes)
            else:
                objective = hypervolumes[0]
                secondary = sum(hypervolumes) / len(hypervolumes)
            key = (objective, secondary, hypervolumes[0], -index)
            if best is None or key > best[0]:
                best = (key, index)
        if best is None:
            raise RuntimeError("reference candidate set is exhausted")
        selected.append(best[1])
        remaining.remove(best[1])
    return tuple(selected)


def _calibrate_instance(oracle, instance, seed, power):
    problem = instance["problem"]
    pool = oracle._sobol_design_pool(problem, seed, power)
    nominal_pool = oracle._evaluate_archive(
        pool, instance["operating_condition"]
    )
    shifted_conditions = [
        oracle._shift_condition(instance["operating_condition"], shift)
        for shift in oracle.SHIFT_SPECS
    ]
    shortlist_indices = _shortlist(oracle, instance, nominal_pool)
    shortlist = pool[np.asarray(shortlist_indices, dtype=int)]
    nominal = [nominal_pool[index] for index in shortlist_indices]
    nominal_shifted = [
        oracle._evaluate_archive(shortlist, condition)
        for condition in shifted_conditions
    ]
    nominal_record_sets = [nominal] + nominal_shifted
    nominal_allowed = [
        index for index, row in enumerate(nominal) if row["process_feasible"]
    ]

    # A nominal Pareto shortlist is intentionally concentrated near material
    # limits and therefore contains too few shift-feasible designs.  Build the
    # robust witness from an independent, truth-blind structural prefilter over
    # the same frozen Sobol pool.  Moisture and cycle feasibility are still
    # decided by the full physical model below, not by this cheap prefilter.
    robust_pool_indices = [
        index for index, design in enumerate(pool)
        if all(
            float(design[0]) <= float(condition["max_boiler_pressure_mpa"]) + 1e-12
            and max(float(design[1]), float(design[3]))
            <= float(condition["max_steam_temperature_c"]) + 1e-12
            for condition in [instance["operating_condition"], *shifted_conditions]
        )
    ]
    robust_pool = pool[np.asarray(robust_pool_indices, dtype=int)]
    robust_nominal = [nominal_pool[index] for index in robust_pool_indices]
    robust_shifted = [
        oracle._evaluate_archive(robust_pool, condition)
        for condition in shifted_conditions
    ]
    robust_record_sets = [robust_nominal] + robust_shifted
    robust_allowed = [
        index for index, row in enumerate(robust_nominal)
        if row["process_feasible"]
        and all(records[index]["process_feasible"] for records in robust_shifted)
    ]
    nominal_local = _greedy_archive(
        oracle, problem, nominal_record_sets, nominal_allowed, robust=False
    )
    robust_local = _greedy_archive(
        oracle, problem, robust_record_sets, robust_allowed, robust=True
    )
    nominal_indices = tuple(shortlist_indices[index] for index in nominal_local)
    robust_indices = tuple(robust_pool_indices[index] for index in robust_local)
    nominal_archive = pool[np.asarray(nominal_indices, dtype=int)]
    robust_archive = pool[np.asarray(robust_indices, dtype=int)]
    baseline_archive = oracle._baseline_archive(problem)
    baseline_nominal = oracle._evaluate_archive(
        baseline_archive, instance["operating_condition"]
    )
    reference_nominal = oracle._evaluate_archive(
        nominal_archive, instance["operating_condition"]
    )
    baseline_shifted = [
        oracle._evaluate_archive(baseline_archive, condition)
        for condition in shifted_conditions
    ]
    reference_shifted = [
        oracle._evaluate_archive(robust_archive, condition)
        for condition in shifted_conditions
    ]
    anchors = {
        "baseline_nominal_hypervolume": oracle._hypervolume(
            problem, baseline_nominal
        ),
        "reference_nominal_hypervolume": oracle._hypervolume(
            problem, reference_nominal
        ),
        "baseline_shifted_hypervolumes": tuple(
            oracle._hypervolume(problem, records) for records in baseline_shifted
        ),
        "reference_shifted_hypervolumes": tuple(
            oracle._hypervolume(problem, records) for records in reference_shifted
        ),
    }
    maximum_residual = max(
        abs(float(record["energy_balance_residual_kj_kg"]))
        for records in (
            baseline_nominal, reference_nominal, *baseline_shifted,
            *reference_shifted,
        )
        for record in records
        if record["process_feasible"]
    )
    baseline_feasible = [
        sum(record["process_feasible"] for record in records)
        for records in (baseline_nominal, *baseline_shifted)
    ]
    reference_feasible = [
        sum(record["process_feasible"] for record in records)
        for records in (reference_nominal, *reference_shifted)
    ]
    nominal_gap = (
        anchors["reference_nominal_hypervolume"]
        - anchors["baseline_nominal_hypervolume"]
    )
    shifted_gaps = [
        reference - baseline
        for reference, baseline in zip(
            anchors["reference_shifted_hypervolumes"],
            anchors["baseline_shifted_hypervolumes"],
        )
    ]
    return {
        "name": instance["name"],
        "split": instance["split"],
        "seed": int(seed),
        "power": int(power),
        "pool_size": len(pool),
        "nominal_feasible_pool_count": sum(
            record["process_feasible"] for record in nominal_pool
        ),
        "shortlist_size": len(shortlist),
        "robust_structural_pool_count": len(robust_pool_indices),
        "robust_allowed_count": len(robust_allowed),
        "nominal_indices": nominal_indices,
        "robust_indices": robust_indices,
        "anchors": anchors,
        "baseline_feasible_counts": baseline_feasible,
        "reference_feasible_counts": reference_feasible,
        "maximum_energy_balance_residual_kj_kg": maximum_residual,
        "passed": bool(
            min(baseline_feasible) >= oracle.MIN_NOMINAL_FEASIBLE
            and min(reference_feasible) == oracle.MAX_ARCHIVE_SIZE
            and nominal_gap > 1.0e-4
            and min(shifted_gaps) > 1.0e-4
            and maximum_residual <= 2.0e-8
        ),
    }


def calibrate(power=11, require_independent_iapws=False):
    oracle = _load_oracle()
    rows = [
        _calibrate_instance(oracle, instance, 9321 + index, power)
        for index, instance in enumerate(oracle.INSTANCES)
    ]
    generated_sobol = {
        row["name"]: {
            "seed": row["seed"],
            "power": row["power"],
            "nominal": row["nominal_indices"],
            "robust": row["robust_indices"],
        }
        for row in rows
    }
    generated_anchors = {
        row["name"]: row["anchors"] for row in rows
    }

    def canonical(value):
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return tuple(canonical(item) for item in value)
        return value

    literals_match = bool(
        int(power) == 11
        and canonical(generated_sobol) == canonical(oracle.REFERENCE_SOBOL)
        and canonical(generated_anchors) == canonical(oracle.CALIBRATED_ANCHORS)
    )
    independent_iapws = _independent_iapws_check(
        oracle, require=bool(require_independent_iapws)
    )
    execution_passed = bool(
        all(row["passed"] for row in rows)
        and (literals_match if int(power) == 11 else True)
        and independent_iapws["passed"]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "IAPWS_IF97_REGION_1_2_4_SINGLE_REHEAT_PARETO_TASK_CALIBRATION_"
            "NOT_PLANT_DESIGN_ECONOMICS_EMISSIONS_TRANSIENT_OR_FIELD_VALIDATION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "task": "Thermodynamics/RankineCycleOpt",
        "if97_release_sha256": IF97_RELEASE_SHA256,
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _file_sha256(path)
            for path in (
                TASK / "verification/if97.py",
                TASK / "verification/cycle.py",
                TASK / "verification/evaluator.py",
                TASK / "solution.py",
                TASK / "Task.md",
                TASK / "TASK_CARD.yaml",
            )
        },
        "task_dimensions": {
            "development_instance_count": len(oracle.DEVELOPMENT_INSTANCES),
            "heldout_instance_count": len(oracle.HELDOUT_INSTANCES),
            "shift_count": len(oracle.SHIFT_SPECS),
            "sobol_power": int(power),
            "sobol_pool_size_per_instance": 2 ** int(power),
            "archive_size": oracle.MAX_ARCHIVE_SIZE,
        },
        "reference_method": (
            "fixed-seed scrambled Sobol nominal screen, exact shortlist evaluation, "
            "and greedy nominal/shift-robust hypervolume archives"
        ),
        "reference_claim": {
            "deterministic": True,
            "truth_blind_to_candidate": True,
            "global_optimality_claimed": False,
            "normalization_clips_better_feasible_candidates": True,
        },
        "instances": rows,
        "independent_iapws_1_5_4_check": independent_iapws,
        "reference_sobol_literal": generated_sobol,
        "anchors_literal": generated_anchors,
        "committed_literals_checked": int(power) == 11,
        "committed_literals_match": literals_match if int(power) == 11 else None,
        "limitations": [
            "The self-contained oracle implements only IF97 Regions 1, 2 and 4; Region 3 is deliberately unsupported and excluded by task bounds.",
            "The independent iapws check validates thermodynamic properties at 32 states, not the complete cycle implementation or a physical plant.",
            "The steady-state equilibrium model omits regeneration, combustion, capital cost, emissions, transient stress, water chemistry and detailed off-design component maps.",
            "The repository-visible deterministic regimes require server-held procedural conditions before leakage-resistant population claims.",
            "The Sobol/greedy reference archives are strong reproducible witnesses, not global Pareto-optimality certificates.",
            "Task calibration does not measure GPT-5.5, feedback causality, model-population performance or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--power", type=int, default=11)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-independent-iapws",
        action="store_true",
        help=(
            "require installed iapws==1.5.4 and validate a 32-state Region-1/2/4 "
            "grid; this remains an audit-only dependency"
        ),
    )
    args = parser.parse_args()
    report = calibrate(
        args.power,
        require_independent_iapws=args.require_independent_iapws,
    )
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
