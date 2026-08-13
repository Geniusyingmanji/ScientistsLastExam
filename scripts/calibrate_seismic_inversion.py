#!/usr/bin/env python3
"""Calibrate SeismicInversion with a public-input-only least-squares reference."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402

TASK = ROOT / "benchmarks/EarthScience/SeismicInversion"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("seismic_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load seismic oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_forward(velocities, offsets, thickness=400.0):
    velocities = np.asarray(velocities, dtype=float)
    offsets = np.asarray(offsets, dtype=float)
    intercepts = np.zeros(len(velocities), dtype=float)
    for layer in range(1, len(velocities)):
        intercepts[layer] = 2.0 * thickness * float(np.sum(np.sqrt(
            np.maximum(
                1.0 / velocities[:layer] ** 2 - 1.0 / velocities[layer] ** 2,
                0.0,
            )
        )))
    return np.min(
        intercepts[:, None] + offsets[None, :] / velocities[:, None], axis=0
    )


def _decode(log_increments):
    return 1400.0 + np.cumsum(np.exp(log_increments))


def invert_public(travel_times, source_positions, receiver_positions, n_layers):
    """Reference inversion using only values passed through the task contract."""
    times = np.asarray(travel_times, dtype=float)
    offsets = np.abs(
        np.asarray(receiver_positions, dtype=float)
        - np.asarray(source_positions, dtype=float)
    )
    starts = []
    for lower, upper in (
        (1600.0, 5200.0),
        (1800.0, 6200.0),
        (2000.0, 6800.0),
        (1500.0, 4500.0),
        (2200.0, 6500.0),
    ):
        profile = np.linspace(lower, upper, n_layers)
        increments = np.clip(
            np.diff(np.concatenate(([1400.0], profile))), 10.001, 1799.999
        )
        starts.append(np.log(increments))

    order = np.argsort(offsets)
    ordered_offsets = offsets[order]
    ordered_times = times[order]
    for fraction in (0.15, 0.25):
        count = max(5, int(fraction * len(offsets)))
        slope = np.polyfit(ordered_offsets[:count], ordered_times[:count], 1)[0]
        surface = np.clip(1.0 / max(slope, 1e-8), 1500.0, 2400.0)
        profile = np.linspace(
            surface, min(6900.0, surface + 850.0 * (n_layers - 1)), n_layers
        )
        increments = np.clip(
            np.diff(np.concatenate(([1400.0], profile))), 10.001, 1799.999
        )
        starts.append(np.log(increments))

    best = None
    for start in starts:
        result = least_squares(
            lambda z: (_public_forward(_decode(z), offsets) - times) / 0.00075,
            start,
            bounds=(np.log(10.0), np.log(1800.0)),
            max_nfev=3000,
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
        )
        if best is None or result.cost < best.cost:
            best = result
    return _decode(best.x)


def calibrate() -> dict:
    oracle = _load_oracle()
    metrics = oracle.evaluate(invert_public)
    rank_checks = []
    for sc in oracle.SCENARIOS:
        columns = []
        for layer in range(sc["n_layers"]):
            step = 1e-3 * sc["true_v"][layer]
            upper = sc["true_v"].copy()
            lower = sc["true_v"].copy()
            upper[layer] += step
            lower[layer] -= step
            columns.append((
                _public_forward(upper, sc["offsets"])
                - _public_forward(lower, sc["offsets"])
            ) / (2.0 * step))
        singular = np.linalg.svd(np.column_stack(columns), compute_uv=False)
        rank_checks.append({
            "seed": sc["seed"],
            "n_layers": sc["n_layers"],
            "jacobian_rank": int(np.sum(singular > 1e-12)),
            "condition_number": float(singular[0] / singular[-1]),
        })
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reference_solver": "public-input multistart nonlinear least squares",
        "metrics": metrics,
        "identifiability": rank_checks,
    }
    execution_passed = bool(
        metrics.get("valid") == 1.0
        and metrics.get("development_score", 0.0) > 0.99
        and metrics.get("mechanism_score", 0.0) > 0.99
        and metrics.get("holdout_prediction_score", 0.0) > 0.99
        and all(row["jacobian_rank"] == row["n_layers"] for row in rank_checks)
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
