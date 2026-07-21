#!/usr/bin/env python3
"""Reproduce admission-blocking defects in the second candidate tranche."""

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
        "wave2_" + task_id.replace("/", "_"), path
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % task_id)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _room_audit():
    oracle = _oracle("Acoustics/RoomImpulseResponse")

    def high_order(room, source, mic, fs, _max_order, absorption):
        return oracle.image_source_rir(room, source, mic, fs, 15, absorption)

    crashed, error = False, None
    try:
        oracle.evaluate(high_order)
    except Exception as exc:
        crashed = True
        error = "%s: %s" % (type(exc).__name__, exc)
    return {
        "task": "Acoustics/RoomImpulseResponse",
        "admission": "quarantine",
        "defect": "a reference-length candidate crashes when compared with the shorter order-zero baseline",
        "exact_reference_candidate_crashed": crashed,
        "error": error,
        "passed": crashed and "broadcast" in str(error),
    }


def _low_thrust_audit():
    oracle = _oracle("Astrodynamics/LowThrustTransfer")
    scenario = oracle.SCENARIOS[0]
    dt = scenario["t_final"] / scenario["n_steps"]
    period = 2 * np.pi * np.sqrt(np.linalg.norm(scenario["r0"]) ** 3 / oracle.MU)
    thrust = np.zeros((scenario["n_steps"], 3), dtype=float)
    position, velocity, ok = oracle.propagate(
        scenario["r0"], scenario["v0"], thrust, dt
    )
    initial_energy = np.dot(scenario["v0"], scenario["v0"]) / 2 - oracle.MU / np.linalg.norm(scenario["r0"])
    final_energy = np.dot(velocity, velocity) / 2 - oracle.MU / np.linalg.norm(position)
    relative_drift = float((final_energy - initial_energy) / abs(initial_energy))
    return {
        "task": "Astrodynamics/LowThrustTransfer",
        "admission": "quarantine",
        "defect": "one Euler step spans nearly half a LEO orbit and the unforced orbit gains nonphysical energy",
        "propagation_returned_ok": bool(ok),
        "dt_seconds": float(dt),
        "initial_orbit_period_seconds": float(period),
        "dt_over_period": float(dt / period),
        "unforced_relative_energy_drift": relative_drift,
        "unforced_final_radius_m": float(np.linalg.norm(position)),
        "passed": bool(ok and dt / period > 0.4 and relative_drift > 1.0),
    }


def _pendulum_acceleration(oracle, theta):
    sine, cosine = np.sin(theta), np.cos(theta)
    return (oracle.G * sine) / (
        oracle.L
        * (4 / 3 - oracle.M_PEND * cosine**2 / (oracle.M_CART + oracle.M_PEND))
    )


def _pendulum_audit():
    oracle = _oracle("ControlTheory/InvertedPendulumSwingUp")
    step = 1e-6
    derivative_zero = float(
        (_pendulum_acceleration(oracle, step) - _pendulum_acceleration(oracle, -step))
        / (2 * step)
    )
    derivative_pi = float((
        _pendulum_acceleration(oracle, np.pi + step)
        - _pendulum_acceleration(oracle, np.pi - step)
    ) / (2 * step))
    return {
        "task": "ControlTheory/InvertedPendulumSwingUp",
        "admission": "quarantine",
        "defect": "the dynamics make theta=0 unstable and theta=pi stable, opposite to the public down/upright labels and reward",
        "d_theta_acceleration_at_zero": derivative_zero,
        "d_theta_acceleration_at_pi": derivative_pi,
        "passed": derivative_zero > 0.0 and derivative_pi < 0.0,
    }


def _interpolation_matrix(points, grid):
    matrix = np.zeros((len(points), len(grid)), dtype=float)
    for row, value in enumerate(points):
        if value <= grid[0]:
            matrix[row, 0] = 1.0
        elif value >= grid[-1]:
            matrix[row, -1] = 1.0
        else:
            left = int(np.searchsorted(grid, value) - 1)
            weight = (value - grid[left]) / (grid[left + 1] - grid[left])
            matrix[row, left] = 1.0 - weight
            matrix[row, left + 1] = weight
    return matrix


def _cavity_audit():
    oracle = _oracle("FluidDynamics/LidDrivenCavity")
    size = oracle.INSTANCES[0]["N"]
    grid = np.linspace(0.0, 1.0, size)
    u_map = _interpolation_matrix(oracle.GHIA_RE100_U[:, 0], grid)
    v_map = _interpolation_matrix(oracle.GHIA_RE100_V[:, 0], grid)
    u_profile = np.linalg.lstsq(u_map, oracle.GHIA_RE100_U[:, 1], rcond=None)[0]
    v_profile = np.linalg.lstsq(v_map, oracle.GHIA_RE100_V[:, 1], rcond=None)[0]

    def profile_injection(_reynolds, n):
        u = np.zeros((n, n), dtype=float)
        v = np.zeros((n, n), dtype=float)
        pressure = np.zeros((n, n), dtype=float)
        u[:, n // 2] = u_profile
        v[n // 2, :] = v_profile
        return u, v, pressure

    metrics = oracle.evaluate(profile_injection)
    return {
        "task": "FluidDynamics/LidDrivenCavity",
        "admission": "quarantine",
        "defect": "centerline-only scoring accepts fields that violate boundary conditions and never solve Navier-Stokes",
        "profile_injection_score": float(metrics["combined_score"]),
        "top_wall_max_error": 1.0,
        "pressure_is_unchecked": True,
        "passed": metrics["combined_score"] > 0.99,
    }


def _alloy_audit():
    task = ROOT / "benchmarks/MaterialsScience/AlloyHardnessOptimization"
    source = (task / "verification/evaluator.py").read_text(encoding="utf-8")
    has_dataset = any((task / name).is_file() for name in (
        "data.csv", "data.npz", "dataset.csv", "dataset.npz"
    ))
    return {
        "task": "MaterialsScience/AlloyHardnessOptimization",
        "admission": "quarantine",
        "defect": "the claimed experimental-data surrogate is a hand-written pseudo-physical polynomial with no dataset artifact",
        "oracle_self_labels_pseudo_physical": "pseudo-physical" in source,
        "dataset_artifact_present": has_dataset,
        "passed": "pseudo-physical" in source and not has_dataset,
    }


def _diffraction_audit():
    oracle = _oracle("Optics/DiffractionGratingDesign")

    def analytic_phase_ramp(wavelength, _period, index, order, grooves):
        return (np.arange(grooves) * order % grooves) / grooves * wavelength / index

    metrics = oracle.evaluate(analytic_phase_ramp)
    return {
        "task": "Optics/DiffractionGratingDesign",
        "admission": "quarantine",
        "defect": "the oracle is a scalar phase FFT, not RCWA, and a disclosed analytic phase ramp gives unit efficiency",
        "analytic_phase_ramp_score": float(metrics["combined_score"]),
        "efficiencies": [float(row["efficiency"]) for row in metrics["per_scenario"]],
        "passed": metrics["combined_score"] == 1.0,
    }


def _heat_exchanger_audit():
    oracle = _oracle("Thermodynamics/HeatExchangerDesign")
    pass_spreads = []
    for scenario in oracle.SCENARIOS:
        hot = scenario["m_hot"] * scenario["cp_hot"]
        cold = scenario["m_cold"] * scenario["cp_cold"]
        minimum, maximum = min(hot, cold), max(hot, cold)
        ratio = minimum / maximum
        ntu = scenario["U"] * scenario["max_area"] / minimum
        values = [oracle._effectiveness_ntu(ntu, ratio, n) for n in (1, 2, 3, 4, 8, 16)]
        pass_spreads.append(float(max(values) - min(values)))

    def maximum_area(*args):
        return args[-1], 1

    metrics = oracle.evaluate(maximum_area)
    return {
        "task": "Thermodynamics/HeatExchangerDesign",
        "admission": "quarantine",
        "defect": "effectiveness is monotone in unconstrained area and the implemented pass formula is pass-count invariant",
        "pass_count_effectiveness_spreads": pass_spreads,
        "maximum_area_score": float(metrics["combined_score"]),
        "passed": max(pass_spreads) < 1e-12 and metrics["combined_score"] > 0.7,
    }


def audit() -> dict:
    records = [
        _room_audit(), _low_thrust_audit(), _pendulum_audit(), _cavity_audit(),
        _alloy_audit(), _diffraction_audit(), _heat_exchanger_audit(),
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
