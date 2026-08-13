#!/usr/bin/env python3
"""Calibrate Pendulum-v2 with a public nominal energy-shaping/LQR controller."""

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

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402

TASK = ROOT / "benchmarks/Engineering/InvertedPendulumSwingUp"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("pendulum_v2_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load pendulum oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_controller(state, _time, _dt):
    """Nominal energy shaping plus a precomputed nominal continuous-time LQR gain."""
    x, x_dot, theta, theta_dot = np.asarray(state, dtype=float)
    upright_error = float((theta - np.pi + np.pi) % (2 * np.pi) - np.pi)
    mass, length = 0.1, 1.0
    inertia = 4.0 / 3.0 * mass * length**2
    energy = 0.5 * inertia * theta_dot**2 - mass * 9.81 * length * np.cos(theta)
    target_energy = mass * 9.81 * length
    lqr_gain = np.array([
        -2.23606798, -5.11564912, -56.10669145, -20.05635487
    ])
    if abs(upright_error) < 0.9 and abs(theta_dot) < 4.0:
        return float(-lqr_gain @ np.array([x, x_dot, upright_error, theta_dot]))
    return float(
        3.0 * (target_energy - energy) * theta_dot * np.cos(theta)
        - 0.8 * x - 1.0 * x_dot
    )


def zero_controller(_state, _time, _dt):
    return 0.0


def calibrate() -> dict:
    oracle = _load_oracle()
    baseline = oracle.evaluate(zero_controller)
    reference = oracle.evaluate(reference_controller)
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reference_solver": "public nominal energy shaping plus LQR",
        "baseline_metrics": baseline,
        "reference_metrics": reference,
    }
    execution_passed = bool(
        baseline.get("valid") == 1.0
        and baseline.get("development_score", 1.0) < 1e-3
        and reference.get("valid") == 1.0
        and reference.get("development_score", 0.0) > 0.80
        and reference.get("mean_balanced_fraction", 0.0) > 0.95
        and 0.10 < reference.get("robustness_score", 0.0) < 0.80
    )
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
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
