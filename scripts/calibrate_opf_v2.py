#!/usr/bin/env python3
"""Calibrate OPF-v2 with independent nominal and N-1 secure convex QP policies."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/OptimalPowerFlow"
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("opf_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load OPF-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connected(n_bus, lines):
    reached = {0}
    for _ in range(int(n_bus)):
        for left, right in lines:
            if int(left) in reached:
                reached.add(int(right))
            if int(right) in reached:
                reached.add(int(left))
    return len(reached) == int(n_bus)


def _flow_map(n_bus, generator_buses, demand, lines, susceptances):
    lines = np.asarray(lines, dtype=int)
    susceptances = np.asarray(susceptances, dtype=float)
    generator_buses = np.asarray(generator_buses, dtype=int)
    demand = np.asarray(demand, dtype=float)
    bus = np.zeros((n_bus, n_bus), dtype=float)
    for (left, right), value in zip(lines, susceptances):
        bus[left, left] += value
        bus[right, right] += value
        bus[left, right] -= value
        bus[right, left] -= value
    reduced_inverse = np.linalg.inv(bus[1:, 1:])

    def flow(generation):
        injection = -demand.copy()
        for generator_bus, output in zip(generator_buses, generation):
            injection[generator_bus] += output
        injection[0] -= np.sum(injection)
        angles = np.zeros(n_bus)
        angles[1:] = reduced_inverse @ injection[1:]
        return susceptances * (
            angles[lines[:, 0]] - angles[lines[:, 1]]
        )

    offset = flow(np.zeros(len(generator_buses)))
    columns = []
    for generator_index in range(len(generator_buses)):
        unit = np.zeros(len(generator_buses))
        unit[generator_index] = 1.0
        columns.append(flow(unit) - offset)
    return np.column_stack(columns), offset


def _solve_policy(security):
    def solve_opf(n_bus, generator_buses, demand, p_min, p_max, cost_quadratic,
                  cost_linear, lines, susceptances, line_limits):
        generator_buses = np.asarray(generator_buses, dtype=int)
        demand = np.asarray(demand, dtype=float)
        p_min = np.asarray(p_min, dtype=float)
        p_max = np.asarray(p_max, dtype=float)
        cost_quadratic = np.asarray(cost_quadratic, dtype=float)
        cost_linear = np.asarray(cost_linear, dtype=float)
        lines = np.asarray(lines, dtype=int)
        susceptances = np.asarray(susceptances, dtype=float)
        line_limits = np.asarray(line_limits, dtype=float)

        matrices = []
        matrix, offset = _flow_map(
            n_bus, generator_buses, demand, lines, susceptances
        )
        matrices.append((matrix, offset, line_limits))
        if security:
            for outage in range(len(lines)):
                retained = np.arange(len(lines)) != outage
                outage_lines = lines[retained]
                if not _connected(n_bus, outage_lines):
                    continue
                matrix, offset = _flow_map(
                    n_bus, generator_buses, demand, outage_lines,
                    susceptances[retained],
                )
                matrices.append((matrix, offset, line_limits[retained]))

        stacked = np.vstack([row[0] for row in matrices])
        lower = np.concatenate([-row[2] - row[1] for row in matrices])
        upper = np.concatenate([row[2] - row[1] for row in matrices])
        total_demand = float(np.sum(demand))
        remaining = total_demand - float(np.sum(p_min))
        baseline = p_min + remaining * (p_max - p_min) / np.sum(p_max - p_min)
        constraints = [
            LinearConstraint(
                np.ones((1, len(generator_buses))),
                [total_demand], [total_demand],
            ),
            LinearConstraint(stacked, lower, upper),
        ]
        result = minimize(
            lambda generation: float(np.sum(
                cost_quadratic * generation**2 + cost_linear * generation
            )),
            baseline,
            jac=lambda generation: 2.0 * cost_quadratic * generation + cost_linear,
            method="SLSQP",
            bounds=Bounds(p_min, p_max),
            constraints=constraints,
            options={"ftol": 1e-12, "maxiter": 2000, "disp": False},
        )
        if not result.success:
            return baseline
        return np.asarray(result.x, dtype=float)
    return solve_opf


def _baseline(_n_bus, _generator_buses, demand, p_min, p_max, *_args):
    p_min = np.asarray(p_min, dtype=float)
    p_max = np.asarray(p_max, dtype=float)
    remaining = float(np.sum(demand) - np.sum(p_min))
    return p_min + remaining * (p_max - p_min) / np.sum(p_max - p_min)


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_baseline)
    nominal = oracle.evaluate(_solve_policy(security=False))
    secure = oracle.evaluate(_solve_policy(security=True))
    nonfinite = oracle.evaluate(
        lambda _n_bus, generator_buses, *_args: np.full(
            len(generator_buses), np.nan
        )
    )
    unbalanced = oracle.evaluate(
        lambda _n_bus, generator_buses, *_args: np.zeros(len(generator_buses))
    )

    reference_checks = []
    for instance in oracle.INSTANCES:
        baseline_metrics = oracle._dispatch_metrics(
            instance, instance["baseline_dispatch"]
        )
        nominal_metrics = oracle._dispatch_metrics(
            instance, instance["nominal_reference_dispatch"]
        )
        secure_metrics = oracle._dispatch_metrics(
            instance, instance["security_reference_dispatch"]
        )
        reference_checks.append({
            "name": instance["name"],
            "baseline_cost": instance["baseline_cost"],
            "nominal_reference_cost": instance["nominal_reference_cost"],
            "security_reference_cost": instance["security_reference_cost"],
            "baseline_contingency_max_loading": baseline_metrics[
                "contingency_max_loading_ratio"
            ],
            "nominal_contingency_max_loading": nominal_metrics[
                "contingency_max_loading_ratio"
            ],
            "security_contingency_max_loading": secure_metrics[
                "contingency_max_loading_ratio"
            ],
            "passed": bool(
                instance["nominal_reference_cost"]
                <= instance["security_reference_cost"] + 1e-7
                <= instance["baseline_cost"] + 1e-7
                and baseline_metrics["contingency_max_loading_ratio"] <= 1.0 + 1e-7
                and nominal_metrics["contingency_max_loading_ratio"] > 1.0 + 1e-3
                and secure_metrics["contingency_max_loading_ratio"] <= 1.0 + 1e-7
            ),
        })

    # Invalid evaluator paths must remain finite JSON evidence.
    json.dumps(nonfinite, allow_nan=False)
    json.dumps(unbalanced, allow_nan=False)
    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["valid"] == 1.0
        and baseline["mean_contingency_feasibility_rate"] == 1.0
        and nominal["combined_score"] > 0.999999
        and nominal["robustness_score"] < 0.25
        and secure["robustness_score"] > 0.999999
        and secure["combined_score"] > 0.05
        and nonfinite["valid"] == 0.0
        and unbalanced["valid"] == 0.0
        and all(row["passed"] for row in reference_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "baseline": baseline,
        "nominal_qp_reference": nominal,
        "security_constrained_qp_reference": secure,
        "nonfinite_rejection": nonfinite,
        "unbalanced_rejection": unbalanced,
        "reference_checks": reference_checks,
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
