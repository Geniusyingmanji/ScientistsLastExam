"""Trusted array-synthesis oracle with evaluator-only hardware/frequency shifts.

Candidates receive every quantity needed to synthesize the nominal far-field pattern.  The
oracle removes the physically irrelevant overall complex scale by enforcing unit response in
the requested look direction, then rejects non-finite, zero-response, excessive-norm or
excessive-per-element excitations.  Frequency offsets, deterministic calibration/position
errors and every single-element failure are evaluated separately and never control search.
"""

from __future__ import annotations

import math

import numpy as np


ANGLE_LIMIT_DEG = 75.0
ANGLE_COUNT = 1501
NULL_HALF_WIDTH_DEG = 1.0
NULL_GRID_COUNT = 17
NULL_WEIGHT = 3.0
MIN_SHIFTED_TARGET_GAIN = 0.80


# Reference parameters were independently selected over beta in linspace(0, 6, 25) and alpha
# in {0} union logspace(-3, 4, 29).  They define strong reproducible domain witnesses inside a
# Kaiser-taper plus regularized-null-projection family; they are not global optima.
INSTANCE_SPECS = (
    {
        "name": "dev_broadside12", "split": "development", "n_elements": 12,
        "spacing_lambda": 0.48, "steering_angle_deg": 0.0,
        "interference_angles_deg": (-38.0, 42.0), "seed": 11,
        "nonuniform": False, "nominal_beta": 3.0,
        "nominal_alpha": 0.03162277660168379, "robust_beta": 1.25,
        "robust_alpha": 5623.413251903491,
    },
    {
        "name": "heldout_scan14", "split": "heldout", "n_elements": 14,
        "spacing_lambda": 0.47, "steering_angle_deg": -15.0,
        "interference_angles_deg": (22.0, 48.0), "seed": 21,
        "nonuniform": True, "nominal_beta": 3.0,
        "nominal_alpha": 0.31622776601683794, "robust_beta": 1.25,
        "robust_alpha": 3162.2776601683795,
    },
    {
        "name": "dev_scan16", "split": "development", "n_elements": 16,
        "spacing_lambda": 0.45, "steering_angle_deg": 20.0,
        "interference_angles_deg": (-32.0, -8.0), "seed": 31,
        "nonuniform": False, "nominal_beta": 3.0,
        "nominal_alpha": 0.05623413251903491, "robust_beta": 1.5,
        "robust_alpha": 1000.0,
    },
    {
        "name": "heldout_scan22", "split": "heldout", "n_elements": 22,
        "spacing_lambda": 0.44, "steering_angle_deg": 30.0,
        "interference_angles_deg": (-28.0, 0.0), "seed": 41,
        "nonuniform": True, "nominal_beta": 3.0, "nominal_alpha": 0.0,
        "robust_beta": 2.0, "robust_alpha": 177.82794100389228,
    },
    {
        "name": "dev_scan20", "split": "development", "n_elements": 20,
        "spacing_lambda": 0.50, "steering_angle_deg": -25.0,
        "interference_angles_deg": (8.0, 38.0), "seed": 51,
        "nonuniform": False, "nominal_beta": 3.0, "nominal_alpha": 0.0,
        "robust_beta": 1.75, "robust_alpha": 100.0,
    },
    {
        "name": "dev_scan24", "split": "development", "n_elements": 24,
        "spacing_lambda": 0.46, "steering_angle_deg": 10.0,
        "interference_angles_deg": (-42.0, 48.0), "seed": 61,
        "nonuniform": False, "nominal_beta": 3.0, "nominal_alpha": 0.0,
        "robust_beta": 2.0, "robust_alpha": 10.0,
    },
)


def _steering_matrix(positions_lambda, angles_deg, frequency_scale=1.0,
                     element_gains=None):
    positions = np.asarray(positions_lambda, dtype=float)
    angles = np.asarray(angles_deg, dtype=float)
    phase = 2.0 * math.pi * np.outer(
        np.sin(np.deg2rad(angles)), positions * float(frequency_scale)
    )
    matrix = np.exp(1j * phase)
    if element_gains is not None:
        matrix = matrix * np.asarray(element_gains, dtype=complex)[None, :]
    return matrix


def _reference_weights(instance, beta, alpha):
    """Kaiser taper with Tikhonov-regularized null projection and unit response."""
    positions = instance["positions_lambda"]
    steering = instance["steering_angle_deg"]
    target = _steering_matrix(positions, [steering])[0]
    taper = np.kaiser(len(positions), float(beta))
    initial = taper * np.conj(target)
    initial = initial / (target @ initial)
    null_matrix = _steering_matrix(positions, instance["null_grid_deg"])
    normal = (
        np.eye(len(positions), dtype=complex)
        + float(alpha) * (null_matrix.conj().T @ null_matrix) / len(null_matrix)
    )
    base = np.linalg.solve(normal, initial)
    direction = np.linalg.solve(normal, np.conj(target))
    multiplier = (1.0 - target @ base) / (target @ direction)
    weights = base + multiplier * direction
    return np.asarray(weights / (target @ weights), dtype=complex)


def _uniform_steering_weights(instance):
    target = _steering_matrix(
        instance["positions_lambda"], [instance["steering_angle_deg"]]
    )[0]
    return np.conj(target) / len(target)


def _shift_scenarios(instance):
    n_elements = len(instance["positions_lambda"])
    indices = np.arange(n_elements, dtype=float)
    seed = float(instance["seed"])
    rows = [
        {
            "name": "frequency_low", "frequency_scale": 0.96,
            "positions_lambda": instance["positions_lambda"],
            "element_gains": np.ones(n_elements, dtype=complex),
        },
        {
            "name": "frequency_high", "frequency_scale": 1.04,
            "positions_lambda": instance["positions_lambda"],
            "element_gains": np.ones(n_elements, dtype=complex),
        },
    ]
    position_error = 0.008 * np.sin((indices + 1.0) * (0.13 * seed + 0.70))
    rows.append({
        "name": "position_error", "frequency_scale": 1.0,
        "positions_lambda": instance["positions_lambda"] + position_error,
        "element_gains": np.ones(n_elements, dtype=complex),
    })
    gain_amplitude = 1.0 + 0.025 * np.cos(
        (indices + 1.0) * (0.17 * seed + 0.50)
    )
    gain_phase = np.deg2rad(2.0) * np.sin(
        (indices + 1.0) * (0.11 * seed + 0.90)
    )
    rows.append({
        "name": "gain_phase_error", "frequency_scale": 1.0,
        "positions_lambda": instance["positions_lambda"],
        "element_gains": gain_amplitude * np.exp(1j * gain_phase),
    })
    for failed in range(n_elements):
        gains = np.ones(n_elements, dtype=complex)
        gains[failed] = 0.0
        rows.append({
            "name": "element_failure_%d" % failed, "frequency_scale": 1.0,
            "positions_lambda": instance["positions_lambda"],
            "element_gains": gains,
        })
    return tuple(rows)


def _pattern_metrics(instance, weights, scenario=None):
    scenario = scenario or {
        "name": "nominal", "frequency_scale": 1.0,
        "positions_lambda": instance["positions_lambda"],
        "element_gains": np.ones(len(instance["positions_lambda"]), dtype=complex),
    }
    positions = scenario["positions_lambda"]
    scale = scenario["frequency_scale"]
    gains = scenario["element_gains"]
    target_vector = _steering_matrix(
        positions, [instance["steering_angle_deg"]], scale, gains
    )[0]
    target_gain = float(abs(target_vector @ weights))
    denominator = max(target_gain, 1.0e-15)
    sidelobes = abs(_steering_matrix(
        positions, instance["sidelobe_angles_deg"], scale, gains
    ) @ weights) / denominator
    nulls = abs(_steering_matrix(
        positions, instance["null_grid_deg"], scale, gains
    ) @ weights) / denominator
    peak_sidelobe = float(np.max(sidelobes))
    peak_null = float(np.max(nulls))
    composite = max(peak_sidelobe, float(instance["null_weight"]) * peak_null)
    suppression = float(-20.0 * math.log10(max(composite, 1.0e-15)))
    target_penalty = min(
        0.0,
        20.0 * math.log10(max(target_gain, 1.0e-15) / MIN_SHIFTED_TARGET_GAIN),
    )
    quality = suppression + target_penalty
    return {
        "name": scenario["name"],
        "quality_db": quality,
        "suppression_db": suppression,
        "peak_sidelobe_level_db": float(20.0 * math.log10(max(peak_sidelobe, 1e-15))),
        "peak_null_level_db": float(20.0 * math.log10(max(peak_null, 1e-15))),
        "target_gain": target_gain,
        "target_gain_feasible": bool(target_gain >= MIN_SHIFTED_TARGET_GAIN),
    }


def _normalized_quality_score(baseline_quality, reference_quality, candidate_quality):
    denominator = float(reference_quality) - float(baseline_quality)
    if denominator <= 1.0e-8:
        raise RuntimeError("invalid array-quality normalization")
    relative = (float(candidate_quality) - float(baseline_quality)) / denominator
    if abs(relative) <= 1.0e-12:
        return 0.0
    return float(np.clip(relative, 0.0, 1.0))


def _make_instance(spec):
    n_elements = int(spec["n_elements"])
    centered = (
        np.arange(n_elements, dtype=float) - (n_elements - 1.0) / 2.0
    ) * float(spec["spacing_lambda"])
    if spec["nonuniform"]:
        centered = centered + 0.018 * np.sin(
            (np.arange(n_elements, dtype=float) + 1.0)
            * (0.07 * float(spec["seed"]) + 0.41)
        )
    aperture = float(np.max(centered) - np.min(centered))
    mainlobe_half_width_sine = 1.25 / aperture
    angle_grid = np.linspace(-ANGLE_LIMIT_DEG, ANGLE_LIMIT_DEG, ANGLE_COUNT)
    target_sine = math.sin(math.radians(float(spec["steering_angle_deg"])))
    sidelobe_mask = (
        np.abs(np.sin(np.deg2rad(angle_grid)) - target_sine)
        >= mainlobe_half_width_sine
    )
    interference = np.asarray(spec["interference_angles_deg"], dtype=float)
    null_grid = np.concatenate([
        np.linspace(
            angle - NULL_HALF_WIDTH_DEG,
            angle + NULL_HALF_WIDTH_DEG,
            NULL_GRID_COUNT,
        ) for angle in interference
    ])
    instance = {
        "name": str(spec["name"]), "split": str(spec["split"]),
        "seed": int(spec["seed"]), "positions_lambda": centered,
        "steering_angle_deg": float(spec["steering_angle_deg"]),
        "interference_angles_deg": interference,
        "mainlobe_half_width_sine": mainlobe_half_width_sine,
        "angle_limit_deg": ANGLE_LIMIT_DEG,
        "null_half_width_deg": NULL_HALF_WIDTH_DEG,
        "null_weight": NULL_WEIGHT,
        "l2_norm_limit": 1.8 / math.sqrt(n_elements),
        "element_amplitude_limit": 2.5 / n_elements,
        "sidelobe_angles_deg": angle_grid[sidelobe_mask],
        "null_grid_deg": null_grid,
        "nominal_beta": float(spec["nominal_beta"]),
        "nominal_alpha": float(spec["nominal_alpha"]),
        "robust_beta": float(spec["robust_beta"]),
        "robust_alpha": float(spec["robust_alpha"]),
    }
    instance["shift_scenarios"] = _shift_scenarios(instance)
    instance["baseline_weights"] = _uniform_steering_weights(instance)
    instance["nominal_reference_weights"] = _reference_weights(
        instance, instance["nominal_beta"], instance["nominal_alpha"]
    )
    instance["robust_reference_weights"] = _reference_weights(
        instance, instance["robust_beta"], instance["robust_alpha"]
    )
    instance["baseline_nominal_metrics"] = _pattern_metrics(
        instance, instance["baseline_weights"]
    )
    instance["nominal_reference_metrics"] = _pattern_metrics(
        instance, instance["nominal_reference_weights"]
    )
    instance["baseline_shift_metrics"] = tuple(
        _pattern_metrics(instance, instance["baseline_weights"], scenario)
        for scenario in instance["shift_scenarios"]
    )
    instance["robust_reference_shift_metrics"] = tuple(
        _pattern_metrics(instance, instance["robust_reference_weights"], scenario)
        for scenario in instance["shift_scenarios"]
    )
    instance["baseline_robust_quality_db"] = min(
        row["quality_db"] for row in instance["baseline_shift_metrics"]
    )
    instance["robust_reference_quality_db"] = min(
        row["quality_db"] for row in instance["robust_reference_shift_metrics"]
    )
    return instance


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "development"
)
HELDOUT_INSTANCES = tuple(row for row in INSTANCES if row["split"] == "heldout")


def _validate_weights(value, instance):
    raw = np.asarray(value, dtype=complex)
    expected = (len(instance["positions_lambda"]),)
    if raw.shape != expected or np.any(~np.isfinite(raw.real)) or np.any(
        ~np.isfinite(raw.imag)
    ):
        raise ValueError("weights must be one finite complex value per element")
    target = _steering_matrix(
        instance["positions_lambda"], [instance["steering_angle_deg"]]
    )[0]
    response = target @ raw
    if not np.isfinite(response.real) or not np.isfinite(response.imag) or abs(response) <= 1e-12:
        raise ValueError("nominal target response must be finite and nonzero")
    weights = raw / response
    l2_norm = float(np.linalg.norm(weights))
    max_amplitude = float(np.max(abs(weights)))
    if l2_norm > instance["l2_norm_limit"] * (1.0 + 1.0e-9):
        raise ValueError("normalized excitation l2 norm exceeds public limit")
    if max_amplitude > instance["element_amplitude_limit"] * (1.0 + 1.0e-9):
        raise ValueError("normalized per-element amplitude exceeds public limit")
    return weights, l2_norm, max_amplitude


def _score_instance(design_array, instance):
    try:
        returned = design_array(
            instance["positions_lambda"].copy(),
            float(instance["steering_angle_deg"]),
            instance["interference_angles_deg"].copy(),
            float(instance["mainlobe_half_width_sine"]),
            float(instance["angle_limit_deg"]),
            float(instance["null_half_width_deg"]),
            float(instance["null_weight"]),
            float(instance["l2_norm_limit"]),
            float(instance["element_amplitude_limit"]),
        )
        weights, l2_norm, max_amplitude = _validate_weights(returned, instance)
        nominal = _pattern_metrics(instance, weights)
        nominal_score = _normalized_quality_score(
            instance["baseline_nominal_metrics"]["quality_db"],
            instance["nominal_reference_metrics"]["quality_db"],
            nominal["quality_db"],
        )
        shifted = tuple(
            _pattern_metrics(instance, weights, scenario)
            for scenario in instance["shift_scenarios"]
        )
        worst_shifted_quality = min(row["quality_db"] for row in shifted)
        worst_shifted_suppression = min(row["suppression_db"] for row in shifted)
        minimum_shifted_target_gain = min(row["target_gain"] for row in shifted)
        robustness_score = _normalized_quality_score(
            instance["baseline_robust_quality_db"],
            instance["robust_reference_quality_db"],
            worst_shifted_quality,
        )
        return {
            "name": instance["name"], "split": instance["split"], "valid": True,
            "score": nominal_score, "robustness_score": robustness_score,
            "nominal_quality_db": nominal["quality_db"],
            "nominal_suppression_db": nominal["suppression_db"],
            "nominal_peak_sidelobe_level_db": nominal["peak_sidelobe_level_db"],
            "nominal_peak_null_level_db": nominal["peak_null_level_db"],
            "baseline_nominal_quality_db": instance[
                "baseline_nominal_metrics"
            ]["quality_db"],
            "nominal_reference_quality_db": instance[
                "nominal_reference_metrics"
            ]["quality_db"],
            "baseline_robust_quality_db": instance["baseline_robust_quality_db"],
            "robust_reference_quality_db": instance["robust_reference_quality_db"],
            "worst_shifted_quality_db": worst_shifted_quality,
            "worst_shifted_suppression_db": worst_shifted_suppression,
            "minimum_shifted_target_gain": minimum_shifted_target_gain,
            "shifted_target_gain_feasibility_rate": float(np.mean([
                row["target_gain_feasible"] for row in shifted
            ])),
            "normalized_l2_norm": l2_norm,
            "normalized_max_element_amplitude": max_amplitude,
            "nominal": nominal,
            "shifted": shifted,
        }
    except Exception as exc:
        return {
            "name": instance["name"], "split": instance["split"], "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0, "robustness_score": 0.0,
            "worst_shifted_quality_db": -1.0e6,
            "worst_shifted_suppression_db": -1.0e6,
            "minimum_shifted_target_gain": 0.0,
            "shifted_target_gain_feasibility_rate": 0.0,
        }


def evaluate(design_array):
    records = [_score_instance(design_array, instance) for instance in INSTANCES]
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_score = float(np.mean([row["score"] for row in development]))
    development_robustness = float(np.mean([
        row["robustness_score"] for row in development
    ]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    heldout_robustness = float(np.mean([
        row["robustness_score"] for row in heldout
    ]))
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    return {
        "combined_score": development_score,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "development_score": development_score,
        "robustness_score": development_robustness,
        "development_validation_gap": development_score - development_robustness,
        "heldout_policy_score": heldout_score,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "mean_worst_shifted_quality_db": float(np.mean([
            row["worst_shifted_quality_db"] for row in development
        ])),
        "mean_shifted_target_gain_feasibility_rate": float(np.mean([
            row["shifted_target_gain_feasibility_rate"] for row in development
        ])),
        "per_instance": records,
    }
