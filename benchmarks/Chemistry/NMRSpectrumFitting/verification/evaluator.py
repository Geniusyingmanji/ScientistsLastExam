"""Trusted multi-spectrum NMR peak-mechanism and refusal oracle.

The candidate sees only a sampled one-dimensional spectrum.  Development and held-out
instances vary peak count, overlap, Lorentzian/Gaussian broadening, baseline drift, noise,
axis direction and range.  Null and phase-distorted spectra deliberately fall outside the
declared positive symmetric Voigt library and reward abstention rather than forced fitting.

Selection uses normalized development peak-mechanism/refusal quality.  Reconstruction,
confidence calibration, false discoveries and held-out shifted performance remain separate
trusted metrics.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.special import voigt_profile


MAX_PEAKS = 16
MIN_WIDTH = 0.002
MAX_LORENTZIAN_HWHM = 0.25
MAX_GAUSSIAN_SIGMA = 0.18
MAX_AMPLITUDE = 5.0


INSTANCE_SPECS = (
    {
        "name": "dev_resolved_lorentzian", "split": "development",
        "kind": "in_library", "seed": 101, "n_points": 768, "n_peaks": 5,
        "overlap_pairs": (), "shape_mode": "lorentzian", "noise_sigma": 0.018,
        "baseline_scale": 0.055, "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "dev_overlapping_lorentzian", "split": "development",
        "kind": "in_library", "seed": 211, "n_points": 896, "n_peaks": 7,
        "overlap_pairs": ((1, 2), (4, 5)), "shape_mode": "lorentzian",
        "noise_sigma": 0.026, "baseline_scale": 0.075,
        "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "dev_mixed_voigt", "split": "development",
        "kind": "in_library", "seed": 307, "n_points": 832, "n_peaks": 6,
        "overlap_pairs": ((2, 3),), "shape_mode": "mixed", "noise_sigma": 0.032,
        "baseline_scale": 0.090, "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "dev_dense_voigt", "split": "development",
        "kind": "in_library", "seed": 401, "n_points": 1024, "n_peaks": 9,
        "overlap_pairs": ((1, 2), (4, 5), (7, 8)), "shape_mode": "mixed",
        "noise_sigma": 0.040, "baseline_scale": 0.110,
        "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "dev_null", "split": "development", "kind": "null",
        "seed": 503, "n_points": 768, "n_peaks": 0, "overlap_pairs": (),
        "shape_mode": "none", "noise_sigma": 0.030, "baseline_scale": 0.100,
        "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "dev_phase_distorted", "split": "development",
        "kind": "misspecified", "seed": 601, "n_points": 896, "n_peaks": 5,
        "overlap_pairs": ((2, 3),), "shape_mode": "phase_distorted",
        "noise_sigma": 0.024, "baseline_scale": 0.060,
        "x_min": 0.0, "x_max": 10.0,
    },
    {
        "name": "heldout_low_snr_voigt", "split": "heldout",
        "kind": "in_library", "seed": 709, "n_points": 960, "n_peaks": 7,
        "overlap_pairs": ((1, 2), (5, 6)), "shape_mode": "mixed",
        "noise_sigma": 0.052, "baseline_scale": 0.125,
        "x_min": -0.5, "x_max": 10.5,
    },
    {
        "name": "heldout_descending_axis", "split": "heldout",
        "kind": "in_library", "seed": 809, "n_points": 864, "n_peaks": 6,
        "overlap_pairs": ((3, 4),), "shape_mode": "mixed",
        "noise_sigma": 0.036, "baseline_scale": 0.105,
        "x_min": 11.0, "x_max": -1.0,
    },
    {
        "name": "heldout_null", "split": "heldout", "kind": "null",
        "seed": 907, "n_points": 832, "n_peaks": 0, "overlap_pairs": (),
        "shape_mode": "none", "noise_sigma": 0.043, "baseline_scale": 0.130,
        "x_min": -0.5, "x_max": 10.5,
    },
    {
        "name": "heldout_phase_distorted", "split": "heldout",
        "kind": "misspecified", "seed": 1009, "n_points": 992, "n_peaks": 6,
        "overlap_pairs": ((1, 2), (4, 5)), "shape_mode": "phase_distorted",
        "noise_sigma": 0.038, "baseline_scale": 0.100,
        "x_min": -1.0, "x_max": 11.0,
    },
)


def _normalized_voigt(x, center, gamma, sigma):
    """Unit-height Voigt profile; gamma is Lorentzian HWHM and sigma Gaussian SD."""
    gamma = float(gamma)
    sigma = float(sigma)
    if gamma < 0.0 or sigma < 0.0 or max(gamma, sigma) < MIN_WIDTH:
        raise ValueError("each peak needs a positive Lorentzian or Gaussian width")
    values = voigt_profile(np.asarray(x, dtype=float) - float(center), sigma, gamma)
    peak = float(voigt_profile(0.0, sigma, gamma))
    if not np.isfinite(peak) or peak <= 0.0:
        raise ValueError("invalid Voigt normalization")
    return np.asarray(values / peak, dtype=float)


def _line_shape(gamma, sigma):
    if gamma >= MIN_WIDTH and sigma >= MIN_WIDTH:
        return "voigt"
    if gamma >= MIN_WIDTH:
        return "lorentzian"
    return "gaussian"


def _truth_parameters(spec, rng):
    n_peaks = int(spec["n_peaks"])
    low = min(float(spec["x_min"]), float(spec["x_max"])) + 0.75
    high = max(float(spec["x_min"]), float(spec["x_max"])) - 0.75
    centers = np.linspace(low, high, n_peaks + 2, dtype=float)[1:-1]
    centers += rng.uniform(-0.16, 0.16, n_peaks)
    gamma = rng.uniform(0.026, 0.072, n_peaks)
    sigma = np.zeros(n_peaks, dtype=float)
    if spec["shape_mode"] == "mixed":
        for index in range(n_peaks):
            mode = index % 3
            if mode == 1:
                sigma[index] = rng.uniform(0.010, 0.032)
            elif mode == 2:
                sigma[index] = rng.uniform(0.018, 0.045)
                gamma[index] = 0.0
    amplitudes = rng.uniform(0.65, 2.45, n_peaks)
    for left, right in spec["overlap_pairs"]:
        midpoint = 0.5 * (centers[left] + centers[right])
        separation = rng.uniform(0.055, 0.095)
        centers[left] = midpoint - separation / 2.0
        centers[right] = midpoint + separation / 2.0
        amplitudes[right] *= rng.uniform(0.55, 0.90)
    order = np.argsort(centers)
    centers = centers[order]
    gamma = gamma[order]
    sigma = sigma[order]
    amplitudes = amplitudes[order]
    return centers, gamma, sigma, amplitudes


def _baseline(x, spec, rng):
    x = np.asarray(x, dtype=float)
    scaled = 2.0 * (x - np.mean(x)) / max(float(np.ptp(x)), 1.0e-12)
    scale = float(spec["baseline_scale"])
    coefficients = rng.uniform(-1.0, 1.0, 3)
    baseline = scale * (
        0.55 + 0.32 * coefficients[0] * scaled
        + 0.24 * coefficients[1] * (scaled * scaled - 1.0 / 3.0)
        + 0.28 * coefficients[2] * np.sin(math.pi * (scaled + 1.0))
    )
    return np.asarray(baseline, dtype=float)


def _make_instance(spec):
    rng = np.random.default_rng(int(spec["seed"]))
    x = np.linspace(
        float(spec["x_min"]), float(spec["x_max"]), int(spec["n_points"])
    )
    baseline = _baseline(x, spec, rng)
    clean = np.zeros_like(x)
    centers = np.empty(0, dtype=float)
    gamma = np.empty(0, dtype=float)
    sigma = np.empty(0, dtype=float)
    amplitudes = np.empty(0, dtype=float)
    if spec["kind"] in {"in_library", "misspecified"}:
        centers, gamma, sigma, amplitudes = _truth_parameters(spec, rng)
        if spec["kind"] == "in_library":
            for c, g, s, a in zip(centers, gamma, sigma, amplitudes):
                clean += a * _normalized_voigt(x, c, g, s)
        else:
            # Absorptive plus dispersive Lorentzian components mimic phase error.  The
            # strong signed/asymmetric lobes cannot be represented by the declared positive
            # symmetric Voigt library and should trigger calibrated refusal.
            for index, (c, g, a) in enumerate(zip(centers, gamma, amplitudes)):
                delta = x - c
                absorptive = g * g / (delta * delta + g * g)
                dispersive = g * delta / (delta * delta + g * g)
                sign = -1.0 if index % 2 else 1.0
                clean += a * (absorptive + sign * 0.72 * dispersive)
    noise = rng.normal(0.0, float(spec["noise_sigma"]), len(x))
    spectrum = clean + baseline + noise
    return {
        "name": str(spec["name"]), "split": str(spec["split"]),
        "kind": str(spec["kind"]), "seed": int(spec["seed"]),
        "x": x, "spectrum": np.asarray(spectrum, dtype=float),
        "clean_spectrum": np.asarray(clean, dtype=float),
        "baseline": baseline, "noise_sigma": float(spec["noise_sigma"]),
        "centers": centers, "lorentzian_hwhm": gamma,
        "gaussian_sigma": sigma, "amplitudes": amplitudes,
        "lineshapes": tuple(_line_shape(g, s) for g, s in zip(gamma, sigma)),
    }


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "heldout"
)


def _reference_result(instance):
    if instance["kind"] != "in_library":
        return {
            "centers": [], "lorentzian_hwhm": [], "gaussian_sigma": [],
            "amplitudes": [], "lineshapes": [], "confidence": 0.0,
            "abstain": True,
        }
    return {
        "centers": instance["centers"].copy(),
        "lorentzian_hwhm": instance["lorentzian_hwhm"].copy(),
        "gaussian_sigma": instance["gaussian_sigma"].copy(),
        "amplitudes": instance["amplitudes"].copy(),
        "lineshapes": list(instance["lineshapes"]),
        "confidence": 1.0, "abstain": False,
    }


def _validate_result(result, instance):
    if not isinstance(result, dict):
        raise TypeError("fit_spectrum must return a dictionary")
    if not isinstance(result.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be a boolean")
    confidence = float(result.get("confidence"))
    if not np.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    fields = (
        "centers", "lorentzian_hwhm", "gaussian_sigma", "amplitudes"
    )
    arrays = {}
    for field in fields:
        value = np.asarray(result.get(field), dtype=float)
        if value.ndim != 1 or np.any(~np.isfinite(value)):
            raise ValueError("%s must be a finite one-dimensional array" % field)
        arrays[field] = value
    n_peaks = len(arrays["centers"])
    if any(len(arrays[field]) != n_peaks for field in fields):
        raise ValueError("peak parameter arrays must have equal length")
    lineshapes = result.get("lineshapes")
    if not isinstance(lineshapes, (list, tuple)) or len(lineshapes) != n_peaks:
        raise ValueError("lineshapes must contain one label per peak")
    lineshapes = tuple(str(value).lower() for value in lineshapes)
    if bool(result["abstain"]):
        if n_peaks != 0:
            raise ValueError("abstention requires empty peak arrays")
        return {
            **arrays, "lineshapes": lineshapes, "confidence": confidence,
            "abstain": True,
        }
    if n_peaks < 1 or n_peaks > MAX_PEAKS:
        raise ValueError("a non-abstaining fit needs 1-%d peaks" % MAX_PEAKS)
    lower = min(float(instance["x"][0]), float(instance["x"][-1]))
    upper = max(float(instance["x"][0]), float(instance["x"][-1]))
    if np.any(arrays["centers"] < lower) or np.any(arrays["centers"] > upper):
        raise ValueError("peak centers must lie on the supplied axis")
    gamma = arrays["lorentzian_hwhm"]
    sigma = arrays["gaussian_sigma"]
    amplitudes = arrays["amplitudes"]
    if np.any(gamma < 0.0) or np.any(gamma > MAX_LORENTZIAN_HWHM):
        raise ValueError("Lorentzian HWHM is outside public bounds")
    if np.any(sigma < 0.0) or np.any(sigma > MAX_GAUSSIAN_SIGMA):
        raise ValueError("Gaussian sigma is outside public bounds")
    if np.any((gamma > 0.0) & (gamma < MIN_WIDTH)) or np.any(
        (sigma > 0.0) & (sigma < MIN_WIDTH)
    ):
        raise ValueError("each nonzero width component must meet the public minimum")
    if np.any(np.maximum(gamma, sigma) < MIN_WIDTH):
        raise ValueError("each peak needs a resolvable positive width")
    if np.any(amplitudes <= 0.0) or np.any(amplitudes > MAX_AMPLITUDE):
        raise ValueError("amplitudes must be positive and within public bounds")
    expected = tuple(_line_shape(g, s) for g, s in zip(gamma, sigma))
    if lineshapes != expected:
        raise ValueError("lineshape labels disagree with the submitted widths")
    return {
        **arrays, "lineshapes": lineshapes, "confidence": confidence,
        "abstain": False,
    }


def _peak_quality_matrix(instance, fitted):
    truth_centers = instance["centers"]
    truth_gamma = instance["lorentzian_hwhm"]
    truth_sigma = instance["gaussian_sigma"]
    truth_amplitudes = instance["amplitudes"]
    fitted_centers = fitted["centers"]
    fitted_gamma = fitted["lorentzian_hwhm"]
    fitted_sigma = fitted["gaussian_sigma"]
    fitted_amplitudes = fitted["amplitudes"]
    step = abs(float(instance["x"][1] - instance["x"][0]))
    matrix = np.zeros((len(truth_centers), len(fitted_centers)), dtype=float)
    for i in range(len(truth_centers)):
        center_scale = max(2.0 * step, 0.5 * (2.0 * truth_gamma[i]
                                             + 2.355 * truth_sigma[i]))
        for j in range(len(fitted_centers)):
            center_error = abs(fitted_centers[j] - truth_centers[i])
            center_score = math.exp(-0.5 * (center_error / center_scale) ** 2)
            gamma_scale = max(0.012, truth_gamma[i])
            sigma_scale = max(0.009, truth_sigma[i])
            gamma_score = math.exp(-abs(fitted_gamma[j] - truth_gamma[i])
                                   / gamma_scale)
            sigma_score = math.exp(-abs(fitted_sigma[j] - truth_sigma[i])
                                   / sigma_scale)
            width_score = math.sqrt(gamma_score * sigma_score)
            amplitude_score = math.exp(-abs(math.log(
                fitted_amplitudes[j] / truth_amplitudes[i]
            )))
            matrix[i, j] = center_score * (
                0.45 + 0.30 * width_score + 0.25 * amplitude_score
            )
    return matrix


def _reconstruct(x, fitted):
    reconstructed = np.zeros_like(np.asarray(x, dtype=float))
    for center, gamma, sigma, amplitude in zip(
        fitted["centers"], fitted["lorentzian_hwhm"],
        fitted["gaussian_sigma"], fitted["amplitudes"],
    ):
        reconstructed += amplitude * _normalized_voigt(
            x, center, gamma, sigma
        )
    return reconstructed


def _score_instance(fit_spectrum, instance):
    try:
        returned = fit_spectrum(instance["x"].copy(), instance["spectrum"].copy())
        fitted = _validate_result(returned, instance)
        supported = instance["kind"] == "in_library"
        confidence_score = 1.0 - (
            fitted["confidence"] - float(supported)
        ) ** 2
        if not supported:
            correct_abstention = bool(fitted["abstain"])
            return {
                "name": instance["name"], "split": instance["split"],
                "kind": instance["kind"], "valid": True,
                "mechanism_score": 1.0 if correct_abstention else 0.0,
                "reconstruction_score": None,
                "confidence_calibration_score": confidence_score,
                "correct_abstention": correct_abstention,
                "abstained": bool(fitted["abstain"]),
                "false_discovery": not correct_abstention,
                "n_true_peaks": 0, "n_predicted_peaks": len(fitted["centers"]),
                "noise_sigma": instance["noise_sigma"],
            }
        if fitted["abstain"]:
            return {
                "name": instance["name"], "split": instance["split"],
                "kind": instance["kind"], "valid": True,
                "abstained": True,
                "mechanism_score": 0.0, "reconstruction_score": 0.0,
                "confidence_calibration_score": confidence_score,
                "correct_abstention": False, "false_discovery": False,
                "n_true_peaks": len(instance["centers"]),
                "n_predicted_peaks": 0, "matched_quality_sum": 0.0,
                "peak_count_score": 0.0, "noise_sigma": instance["noise_sigma"],
            }
        quality = _peak_quality_matrix(instance, fitted)
        truth_indices, fitted_indices = linear_sum_assignment(-quality)
        matched = quality[truth_indices, fitted_indices]
        denominator = max(len(instance["centers"]), len(fitted["centers"]))
        mechanism_score = float(np.sum(matched) / denominator)
        reconstructed = _reconstruct(instance["x"], fitted)
        residual = float(np.sqrt(np.mean(
            (reconstructed - instance["clean_spectrum"]) ** 2
        )))
        clean_rms = float(np.sqrt(np.mean(instance["clean_spectrum"] ** 2)))
        reconstruction_score = float(np.clip(
            1.0 - residual / max(clean_rms, 1.0e-12), 0.0, 1.0
        ))
        return {
            "name": instance["name"], "split": instance["split"],
            "kind": instance["kind"], "valid": True,
            "mechanism_score": mechanism_score,
            "reconstruction_score": reconstruction_score,
            "confidence_calibration_score": confidence_score,
            "correct_abstention": False, "false_discovery": False,
            "n_true_peaks": len(instance["centers"]),
            "n_predicted_peaks": len(fitted["centers"]),
            "matched_quality_sum": float(np.sum(matched)),
            "peak_count_score": min(
                len(instance["centers"]), len(fitted["centers"])
            ) / denominator,
            "clean_reconstruction_rms": residual,
            "noise_sigma": instance["noise_sigma"],
        }
    except Exception as exc:
        return {
            "name": instance["name"], "split": instance["split"],
            "kind": instance["kind"], "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "mechanism_score": 0.0, "reconstruction_score": 0.0,
            "confidence_calibration_score": 0.0,
            "correct_abstention": False, "false_discovery": False,
            "n_true_peaks": len(instance["centers"]),
            "n_predicted_peaks": 0, "noise_sigma": instance["noise_sigma"],
        }


def _split_summary(records, split):
    rows = [row for row in records if row["split"] == split]
    supported = [row for row in rows if row["kind"] == "in_library"]
    unsupported = [row for row in rows if row["kind"] != "in_library"]
    raw_mechanism = float(np.mean([row["mechanism_score"] for row in rows]))
    always_abstain = len(unsupported) / len(rows)
    normalized = float(np.clip(
        (raw_mechanism - always_abstain) / (1.0 - always_abstain), 0.0, 1.0
    ))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw_mechanism,
        "reconstruction": float(np.mean([
            row["reconstruction_score"] for row in supported
        ])),
        "confidence_calibration": float(np.mean([
            row["confidence_calibration_score"] for row in rows
        ])),
        "false_discovery_rate": float(np.mean([
            row["false_discovery"] for row in unsupported
        ])),
        "correct_refusal_rate": float(np.mean([
            row["correct_abstention"] for row in unsupported
        ])),
        # Whether a fit was attempted on the worlds that have one. Without it a run where every
        # proposal declined every spectrum is indistinguishable from one where the fitting was
        # too hard, and those need opposite responses.
        "discovery_coverage": float(np.mean([
            not row.get("abstained", False) for row in supported
        ])),
        "feasibility_rate": float(np.mean([row["valid"] for row in rows])),
        "all_valid": all(row["valid"] for row in rows),
    }


def evaluate(fit_spectrum):
    records = [_score_instance(fit_spectrum, instance) for instance in INSTANCES]
    development = _split_summary(records, "development")
    heldout = _split_summary(records, "heldout")
    combined = development["normalized_mechanism"] if development["all_valid"] else 0.0
    return {
        "combined_score": combined,
        "valid": 1.0 if development["all_valid"] else 0.0,
        "feasibility_rate": development["feasibility_rate"],
        "development_score": combined,
        "mechanism_score": development["raw_mechanism"],
        "robustness_score": (
            heldout["normalized_mechanism"] if heldout["all_valid"] else 0.0
        ),
        "heldout_mechanism_score": heldout["raw_mechanism"],
        "development_reconstruction_score": development["reconstruction"],
        "heldout_reconstruction_score": heldout["reconstruction"],
        "development_confidence_calibration_score": development[
            "confidence_calibration"
        ],
        "heldout_confidence_calibration_score": heldout[
            "confidence_calibration"
        ],
        "development_false_discovery_rate": development[
            "false_discovery_rate"
        ],
        "heldout_false_discovery_rate": heldout["false_discovery_rate"],
        "development_correct_refusal_rate": development[
            "correct_refusal_rate"
        ],
        "heldout_correct_refusal_rate": heldout["correct_refusal_rate"],
        "development_discovery_coverage": development["discovery_coverage"],
        "heldout_discovery_coverage": heldout["discovery_coverage"],
        "heldout_feasibility_rate": heldout["feasibility_rate"],
        "per_instance": records,
    }
