#!/usr/bin/env python3
"""Calibrate NMR-v2 references, fail-closed behavior and a classical fit baseline."""

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
from scipy.optimize import least_squares
from scipy.signal import find_peaks, peak_widths
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Chemistry/NMRSpectrumFitting"
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("nmr_v2_calibration_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load NMR-v2 oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _empty_result():
    return {
        "centers": [], "lorentzian_hwhm": [], "gaussian_sigma": [],
        "amplitudes": [], "lineshapes": [], "confidence": 0.0,
        "abstain": True,
    }


def _asymmetric_baseline(values, smoothness=2.0e6, asymmetry=0.015,
                         iterations=10):
    """Asymmetric least-squares baseline using only the supplied spectrum."""
    values = np.asarray(values, dtype=float)
    count = len(values)
    second_difference = diags(
        (np.ones(count - 2), -2.0 * np.ones(count - 2), np.ones(count - 2)),
        (0, 1, 2), shape=(count - 2, count), format="csc",
    )
    penalty = float(smoothness) * (second_difference.T @ second_difference)
    weights = np.ones(count, dtype=float)
    baseline = np.zeros(count, dtype=float)
    for _ in range(int(iterations)):
        baseline = spsolve(diags(weights, format="csc") + penalty, weights * values)
        weights = np.where(values > baseline, asymmetry, 1.0 - asymmetry)
    return np.asarray(baseline, dtype=float)


def classical_lorentzian_fit(x, spectrum):
    """Truth-blind classical baseline: AsLS, peak finding and robust joint fitting."""
    x = np.asarray(x, dtype=float)
    spectrum = np.asarray(spectrum, dtype=float)
    if x[0] > x[-1]:
        x = x[::-1].copy()
        spectrum = spectrum[::-1].copy()
    baseline = _asymmetric_baseline(spectrum)
    corrected = spectrum - baseline
    differences = np.diff(spectrum)
    noise = float(
        np.median(np.abs(differences - np.median(differences)))
        / (0.6744897501960817 * math.sqrt(2.0))
    )
    noise = max(noise, 1.0e-6)
    height = max(4.5 * noise, 0.08 * float(np.max(corrected)))
    prominence = max(3.5 * noise, 0.055 * float(np.ptp(spectrum)))
    peaks, properties = find_peaks(
        corrected, height=height, prominence=prominence, distance=3
    )
    if len(peaks) == 0 or float(np.max(corrected)) < 5.0 * noise:
        return _empty_result()
    if len(peaks) > 16:
        order = np.argsort(properties["prominences"])[-16:]
        peaks = np.sort(peaks[order])
    widths_samples = peak_widths(corrected, peaks, rel_height=0.5)[0]
    spacing = float(np.median(np.diff(x)))
    center0 = x[peaks]
    gamma0 = np.clip(0.5 * widths_samples * spacing, 0.004, 0.18)
    amplitude0 = np.clip(corrected[peaks], 0.05, 4.5)
    scaled_x = 2.0 * (x - np.mean(x)) / max(float(np.ptp(x)), 1.0e-12)

    def unpack(parameters):
        count = len(peaks)
        centers = parameters[:count]
        gamma = np.exp(parameters[count:2 * count])
        amplitudes = np.exp(parameters[2 * count:3 * count])
        polynomial = parameters[3 * count:]
        return centers, gamma, amplitudes, polynomial

    def residual(parameters):
        centers, gamma, amplitudes, polynomial = unpack(parameters)
        model = polynomial[0] + polynomial[1] * scaled_x + polynomial[2] * scaled_x**2
        for center, width, amplitude in zip(centers, gamma, amplitudes):
            model = model + amplitude * width**2 / ((x - center)**2 + width**2)
        return model - spectrum

    count = len(peaks)
    initial = np.concatenate((
        center0, np.log(gamma0), np.log(amplitude0),
        np.asarray((float(np.median(baseline)), 0.0, 0.0)),
    ))
    center_radius = np.maximum(2.5 * spacing, np.minimum(0.11, gamma0))
    lower = np.concatenate((
        np.maximum(x[0], center0 - center_radius),
        np.full(count, math.log(0.002)), np.full(count, math.log(0.01)),
        np.asarray((-1.0, -1.0, -1.0)),
    ))
    upper = np.concatenate((
        np.minimum(x[-1], center0 + center_radius),
        np.full(count, math.log(0.25)), np.full(count, math.log(5.0)),
        np.asarray((1.0, 1.0, 1.0)),
    ))
    optimized = least_squares(
        residual, initial, bounds=(lower, upper), loss="soft_l1",
        f_scale=max(2.0 * noise, 0.01), max_nfev=400,
    )
    centers, gamma, amplitudes, _ = unpack(optimized.x)
    order = np.argsort(centers)
    centers = centers[order]
    gamma = gamma[order]
    amplitudes = amplitudes[order]
    relative_residual = float(
        np.sqrt(np.mean(residual(optimized.x) ** 2))
        / max(np.sqrt(np.mean((spectrum - np.median(spectrum)) ** 2)), noise)
    )
    confidence = float(np.clip(1.0 - relative_residual, 0.05, 0.95))
    return {
        "centers": centers, "lorentzian_hwhm": gamma,
        "gaussian_sigma": np.zeros(count, dtype=float),
        "amplitudes": amplitudes, "lineshapes": ["lorentzian"] * count,
        "confidence": confidence, "abstain": False,
    }


def _exact_policy(oracle, reverse=False):
    def fit_spectrum(x, spectrum):
        matches = [
            instance for instance in oracle.INSTANCES
            if np.array_equal(np.asarray(x), instance["x"])
            and np.array_equal(np.asarray(spectrum), instance["spectrum"])
        ]
        if len(matches) != 1:
            raise ValueError("calibration witness could not identify public input")
        result = oracle._reference_result(matches[0])
        if reverse and not result["abstain"]:
            for key in (
                "centers", "lorentzian_hwhm", "gaussian_sigma", "amplitudes"
            ):
                result[key] = result[key][::-1].copy()
            result["lineshapes"] = list(reversed(result["lineshapes"]))
        return result
    return fit_spectrum


def _profile_checks(oracle):
    rows = []
    for gamma, sigma in ((0.04, 0.0), (0.0, 0.03), (0.045, 0.025)):
        approximate_fwhm = (
            0.5346 * (2.0 * gamma)
            + math.sqrt(
                0.2166 * (2.0 * gamma) ** 2
                + (2.354820045 * sigma) ** 2
            )
        )
        axis = np.linspace(-0.4, 0.4, 200001)
        profile = oracle._normalized_voigt(axis, 0.0, gamma, sigma)
        positive = axis >= 0.0
        half_index = int(np.argmin(abs(profile[positive] - 0.5)))
        numerical_fwhm = 2.0 * axis[positive][half_index]
        symmetry_error = float(np.max(abs(profile - profile[::-1])))
        unit_height_error = abs(float(oracle._normalized_voigt(
            np.asarray((0.0,)), 0.0, gamma, sigma
        )[0]) - 1.0)
        relative_fwhm_error = abs(
            numerical_fwhm - approximate_fwhm
        ) / numerical_fwhm
        rows.append({
            "lorentzian_hwhm": gamma, "gaussian_sigma": sigma,
            "numerical_fwhm": numerical_fwhm,
            "olivero_longbothum_approximate_fwhm": approximate_fwhm,
            "relative_fwhm_error": relative_fwhm_error,
            "symmetry_error": symmetry_error,
            "unit_height_error": unit_height_error,
            "passed": bool(
                relative_fwhm_error <= 3.0e-4
                and symmetry_error <= 1.0e-12
                and unit_height_error <= 1.0e-12
            ),
        })
    return rows


def calibrate():
    oracle = _load_oracle()
    exact = oracle.evaluate(_exact_policy(oracle))
    permuted = oracle.evaluate(_exact_policy(oracle, reverse=True))
    abstain = oracle.evaluate(lambda _x, _spectrum: _empty_result())
    classical = oracle.evaluate(classical_lorentzian_fit)
    nonfinite = oracle.evaluate(lambda _x, _spectrum: {
        "centers": [np.nan], "lorentzian_hwhm": [0.04],
        "gaussian_sigma": [0.0], "amplitudes": [1.0],
        "lineshapes": ["lorentzian"], "confidence": 1.0,
        "abstain": False,
    })
    inconsistent = oracle.evaluate(lambda _x, _spectrum: {
        "centers": [5.0], "lorentzian_hwhm": [0.04],
        "gaussian_sigma": [], "amplitudes": [1.0],
        "lineshapes": ["lorentzian"], "confidence": 1.0,
        "abstain": False,
    })
    invalid_abstention = oracle.evaluate(lambda _x, _spectrum: {
        "centers": [5.0], "lorentzian_hwhm": [0.04],
        "gaussian_sigma": [0.0], "amplitudes": [1.0],
        "lineshapes": ["lorentzian"], "confidence": 0.0,
        "abstain": True,
    })
    profile_checks = _profile_checks(oracle)
    execution_passed = bool(
        len(oracle.DEVELOPMENT_INSTANCES) == 6
        and len(oracle.HELDOUT_INSTANCES) == 4
        and exact["valid"] == 1.0
        and exact["combined_score"] > 1.0 - 1.0e-12
        and exact["robustness_score"] > 1.0 - 1.0e-12
        and exact["development_reconstruction_score"] > 1.0 - 1.0e-12
        and exact["heldout_reconstruction_score"] > 1.0 - 1.0e-12
        and permuted["combined_score"] == exact["combined_score"]
        and permuted["robustness_score"] == exact["robustness_score"]
        and abstain["valid"] == 1.0 and abstain["combined_score"] == 0.0
        and abstain["robustness_score"] == 0.0
        and classical["valid"] == 1.0
        and 0.05 < classical["combined_score"] < 0.95
        and all(
            row["valid"] == 0.0 and row["combined_score"] == 0.0
            for row in (nonfinite, inconsistent, invalid_abstention)
        )
        and all(row["passed"] for row in profile_checks)
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": "SCIENTIFIC_CALIBRATION_NOT_MODEL_PERFORMANCE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reference_method": {
            "description": (
                "Exact generative-parameter witness with order-invariant peak assignment, "
                "plus independent profile/FWHM checks; a truth-blind AsLS/peak-finding/"
                "Lorentzian least-squares policy is retained as a classical non-reference "
                "baseline."
            ),
            "global_optimality_claimed": False,
            "experimental_nmr_validation_claimed": False,
        },
        "exact_reference_policy": exact,
        "permuted_exact_reference_policy": permuted,
        "always_abstain_baseline": abstain,
        "classical_lorentzian_baseline": classical,
        "nonfinite_rejection": nonfinite,
        "inconsistent_shape_rejection": inconsistent,
        "invalid_abstention_rejection": invalid_abstention,
        "independent_profile_checks": profile_checks,
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
