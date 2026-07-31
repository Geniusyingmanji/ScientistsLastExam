#!/usr/bin/env python3
"""Calibrate GravityInversion-v2 with independent physics and truth-blind fitting."""

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
from numpy.polynomial.legendre import leggauss
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/EarthScience/GravityInversion"
sys.path.insert(0, str(ROOT))
G_CONST = 6.67430e-11

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("gravity_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load GravityInversion-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _always_abstain(profile_bounds, depth_bounds, measure, budget_units):
    del depth_bounds, budget_units
    measure(np.linspace(profile_bounds[0], profile_bounds[1], 8), 500.0)
    return {"bodies": [], "confidence": 0.0, "abstain": True}


def _unpack(vector, n_bodies):
    bodies = np.asarray(vector, dtype=float).reshape(n_bodies, 5).copy()
    # The optimization coordinate has a continuous sign branch away from zero; adding a
    # 50 kg/m3 offset guarantees every returned density satisfies the public magnitude bound.
    bodies[:, 4] = np.where(
        bodies[:, 4] >= 0.0, 50.0 + bodies[:, 4], -50.0 + bodies[:, 4]
    )
    return bodies


def _public_rectangle_field(bodies, station_x, observation_height=0.0):
    """Independent implementation of the forward equation printed in Task.md."""
    x = np.asarray(station_x, dtype=float).ravel()
    values = np.zeros(len(x), dtype=float)

    def primitive(horizontal, depth):
        return (
            depth * np.arctan2(horizontal, depth)
            + 0.5 * horizontal * np.log(depth**2 + horizontal**2)
        )

    for body in np.asarray(bodies, dtype=float).reshape((-1, 5)):
        xc, zc, width, height, density = body
        left = xc - 0.5 * width - x
        right = xc + 0.5 * width - x
        top = zc - 0.5 * height + float(observation_height)
        bottom = zc + 0.5 * height + float(observation_height)
        values += 2.0 * G_CONST * density * (
            primitive(right, bottom) - primitive(right, top)
            - primitive(left, bottom) + primitive(left, top)
        ) * 1.0e5
    return values


def _classical_fit(profile_bounds, measure):
    """Return the best truth-blind BIC body fit and its reduced chi-square."""
    stations = np.linspace(profile_bounds[0], profile_bounds[1], 20)
    records = [measure(stations, height) for height in (0.0, 800.0, 1500.0)]
    x = np.concatenate([row["station_x_m"] for row in records])
    height = np.concatenate([
        np.full(len(row["station_x_m"]), row["observation_height_m"])
        for row in records
    ])
    observed = np.concatenate([row["gravity_mgal"] for row in records])
    noise = np.concatenate([row["noise_std_mgal"] for row in records])
    if float(np.sqrt(np.mean(observed**2))) < 3.0 * float(np.mean(noise)):
        return np.empty((0, 5)), None

    def prediction(vector, n_bodies):
        bodies = _unpack(vector, n_bodies)
        values = np.empty(len(observed))
        for level in np.unique(height):
            selected = height == level
            values[selected] = _public_rectangle_field(
                bodies, x[selected], float(level)
            )
        return values

    best = None
    rng = np.random.default_rng(121)
    for n_bodies in range(1, 5):
        lower = np.tile((300.0, 300.0, 200.0, 150.0, -750.0), n_bodies)
        upper = np.tile((9700.0, 4500.0, 3500.0, 1800.0, 750.0), n_bodies)
        for _ in range(3):
            initial = []
            for _body in range(n_bodies):
                initial.extend((
                    rng.uniform(900.0, 9100.0),
                    rng.uniform(500.0, 4000.0),
                    rng.uniform(400.0, 2500.0),
                    rng.uniform(250.0, 1400.0),
                    rng.choice((-1.0, 1.0)) * rng.uniform(50.0, 650.0),
                ))
            fit = least_squares(
                lambda vector: (prediction(vector, n_bodies) - observed) / noise,
                np.asarray(initial),
                bounds=(lower, upper),
                max_nfev=500,
                x_scale="jac",
                ftol=5e-7,
                xtol=5e-7,
                gtol=5e-7,
            )
            reduced_chi2 = float(np.mean(
                ((prediction(fit.x, n_bodies) - observed) / noise) ** 2
            ))
            bic = (
                len(observed) * math.log(max(reduced_chi2, 1e-8))
                + 5 * n_bodies * math.log(len(observed))
            )
            if best is None or bic < best[0]:
                best = (bic, reduced_chi2, _unpack(fit.x, n_bodies))
    _bic, reduced_chi2, bodies = best
    return bodies, reduced_chi2


def classical_discover_bodies(profile_bounds, depth_bounds, measure, budget_units):
    """Generic multi-height BIC fit; no hidden template, seed or world label is used."""
    del depth_bounds, budget_units
    bodies, reduced_chi2 = _classical_fit(profile_bounds, measure)
    if reduced_chi2 is None:
        return {"bodies": [], "confidence": 0.0, "abstain": True}
    abstain = bool(reduced_chi2 > 3.5)
    return {
        "bodies": [] if abstain else bodies,
        "confidence": (
            0.0 if abstain
            else float(np.clip(1.0 - reduced_chi2 / 3.5, 0.0, 1.0))
        ),
        "abstain": abstain,
    }


def _independent_rectangle_field(body, station_x, height):
    nodes, weights = leggauss(40)
    xc, zc, width, body_height, density = np.asarray(body, dtype=float)
    source_x = xc + 0.5 * width * nodes
    source_z = zc + 0.5 * body_height * nodes
    horizontal = (
        np.asarray(station_x, dtype=float)[:, None, None]
        - source_x[None, :, None]
    )
    vertical = source_z[None, None, :] + float(height)
    integrand = vertical / (horizontal**2 + vertical**2)
    integral = (
        np.sum(
            weights[None, :, None] * weights[None, None, :] * integrand,
            axis=(1, 2),
        )
        * 0.25 * width * body_height
    )
    return 2.0 * G_CONST * density * integral * 1.0e5


def _identifiability_record(oracle, world, split, world_index):
    stations = np.linspace(0.0, 10000.0, 20)
    heights = (0.0, 800.0, 1500.0)
    scales = np.asarray((1000.0, 1000.0, 1000.0, 500.0, 300.0))
    truth = (world["bodies"] / scales).ravel()

    def observation(vector):
        bodies = vector.reshape((-1, 5)) * scales
        return np.concatenate([
            oracle.rectangle_field(bodies, stations, height)
            for height in heights
        ]) / world["noise"]

    jacobian = np.empty((len(observation(truth)), len(truth)))
    for column in range(len(truth)):
        step = 1e-5
        upper = truth.copy()
        lower = truth.copy()
        upper[column] += step
        lower[column] -= step
        jacobian[:, column] = (
            observation(upper) - observation(lower)
        ) / (2.0 * step)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian, tol=singular[0] * 1e-8))
    condition = float(singular[0] / singular[-1])
    return {
        "split": split,
        "world_index": world_index,
        "active_parameter_count": len(truth),
        "jacobian_shape": list(jacobian.shape),
        "jacobian_rank": rank,
        "condition_number": condition,
        "minimum_singular_value": float(singular[-1]),
        "survey_budget_units": 18,
        "passed": rank == len(truth) and condition < 1e5,
    }


def calibrate():
    oracle = _load_oracle()
    baseline = oracle.evaluate(_always_abstain)
    classical = oracle.evaluate(classical_discover_bodies)

    exact_checks = []
    identifiability = []
    signal_checks = []
    misspecified_resolvability = []
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for index, spec in enumerate(specs):
            world = oracle._world(spec)
            if world["kind"] == "in_library":
                mechanism = oracle._body_matching_metrics(
                    world, world["bodies"], False
                )
                interpolation = oracle._prediction_score(
                    world, world["bodies"], False
                )
                extrapolation = oracle._prediction_score(
                    world, world["bodies"], True
                )
                identifiability.append(
                    _identifiability_record(oracle, world, split, index)
                )
                exact_passed = (
                    mechanism["mechanism_score"] == 1.0
                    and interpolation == 1.0 and extrapolation == 1.0
                )
            else:
                empty = np.empty((0, 5))
                mechanism = oracle._body_matching_metrics(world, empty, True)
                interpolation = oracle._prediction_score(world, empty, False)
                extrapolation = oracle._prediction_score(world, empty, True)
                exact_passed = mechanism["mechanism_score"] == 1.0
            exact_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "mechanism_score": mechanism["mechanism_score"],
                "interpolation_prediction_score": interpolation,
                "extrapolation_prediction_score": extrapolation,
                "passed": exact_passed,
            })

            stations = np.linspace(0.0, 10000.0, 101)
            field = oracle._world_field(world, stations, 0.0)
            signal_rms = float(np.sqrt(np.mean(field**2)))
            ratio = signal_rms / world["noise"]
            signal_checks.append({
                "split": split,
                "world_index": index,
                "kind": world["kind"],
                "signal_rms_mgal": signal_rms,
                "noise_std_mgal": world["noise"],
                "signal_to_noise_ratio": ratio,
                "passed": (
                    ratio == 0.0 if world["kind"] == "null" else ratio > 10.0
                ),
            })

            if world["kind"] == "misspecified":
                row = next(
                    item for item in classical["per_world"]
                    if item["split"] == split and item["world_index"] == index
                )
                diagnostic_survey = oracle._Survey(world)
                _diagnostic_bodies, reduced_chi2 = _classical_fit(
                    oracle.PROFILE_BOUNDS_M, diagnostic_survey.measure
                )
                misspecified_resolvability.append({
                    "split": split,
                    "world_index": index,
                    "best_at_most_four_body_reduced_chi2": reduced_chi2,
                    "refusal_threshold_reduced_chi2": 3.5,
                    "classical_abstained": row["abstained"],
                    "classical_false_discovery": row["false_discovery"],
                    "classical_observed_fit_score": row["observed_fit_score"],
                    "passed": bool(
                        reduced_chi2 is not None and reduced_chi2 > 3.5
                        and row["abstained"] and not row["false_discovery"]
                    ),
                })

    rng = np.random.default_rng(7721)
    quadrature_checks = []
    for index in range(20):
        body = np.asarray((
            rng.uniform(2000.0, 8000.0),
            rng.uniform(800.0, 3500.0),
            rng.uniform(300.0, 1500.0),
            rng.uniform(200.0, 700.0),
            rng.choice((-1.0, 1.0)) * rng.uniform(100.0, 700.0),
        ))
        stations = rng.uniform(-1000.0, 11000.0, size=20)
        height = float(rng.uniform(0.0, 2000.0))
        analytic = oracle.rectangle_field([body], stations, height)
        independent = _independent_rectangle_field(body, stations, height)
        maximum_error = float(np.max(np.abs(analytic - independent)))
        quadrature_checks.append({
            "case": index,
            "maximum_absolute_error_mgal": maximum_error,
            "passed": maximum_error < 2e-10,
        })

    difficulty_passed = bool(
        0.3 <= classical["combined_score"] <= 0.85
        and 0.25 <= classical["robustness_score"] <= 0.85
        and classical["development_prediction_score"]
        > classical["combined_score"] + 0.10
        and classical["development_false_discovery_rate"] == 0.0
        and classical["heldout_false_discovery_rate"] == 0.0
    )
    execution_passed = bool(
        baseline["combined_score"] == 0.0
        and baseline["robustness_score"] == 0.0
        and baseline["valid"] == 1.0
        and classical["valid"] == 1.0
        and classical["heldout_feasibility_rate"] == 1.0
        and difficulty_passed
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in identifiability)
        and all(row["passed"] for row in signal_checks)
        and all(row["passed"] for row in misspecified_resolvability)
        and all(row["passed"] for row in quadrature_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_FIELD_OR_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "always_abstain_baseline": baseline,
        "truth_blind_classical_fit": classical,
        "exact_body_or_refusal_checks": exact_checks,
        "multiheight_identifiability_checks": identifiability,
        "signal_to_noise_checks": signal_checks,
        "misspecified_resolvability_checks": misspecified_resolvability,
        "independent_quadrature_checks": quadrature_checks,
        "difficulty_gate": {
            "classical_development_interval": [0.3, 0.85],
            "classical_heldout_interval": [0.25, 0.85],
            "minimum_prediction_mechanism_gap": 0.10,
            "maximum_false_discovery_rate": 0.0,
            "passed": difficulty_passed,
        },
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
