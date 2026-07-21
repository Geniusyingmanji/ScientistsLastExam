"""Oracle for identifiable 1D layered seismic-refraction inversion.

Observed picks are noisy first-arrival times from direct and critically refracted head waves in
horizontal, monotonically faster layers of known thickness. Unlike the superseded mean-velocity
proxy, every layer controls the slope or intercept of an observable first-arrival branch.
"""

from __future__ import annotations

import numpy as np


LAYER_THICKNESS_M = 400.0
VELOCITY_MIN = 1400.0
VELOCITY_MAX = 7000.0
PICK_NOISE_S = 0.00075
SCENARIO_CONFIGS = (
    (701, 4),
    (719, 5),
    (733, 6),
    (751, 4),
    (769, 5),
    (787, 6),
)


def first_arrival_times(velocities, offsets):
    """Return direct/head-wave first arrivals for a horizontal layered half-space.

    All finite layers have ``LAYER_THICKNESS_M`` thickness and the last layer is a half-space.
    Nondecreasing velocity is required for real critical refraction angles. Equal velocities
    are allowed so the constant-velocity baseline remains a valid model.
    """
    velocities = np.asarray(velocities, dtype=float)
    offsets = np.asarray(offsets, dtype=float)
    if velocities.ndim != 1 or velocities.size < 2:
        raise ValueError("velocities must be a one-dimensional layered profile")
    if offsets.ndim != 1 or np.any(offsets < 0.0):
        raise ValueError("offsets must be a nonnegative one-dimensional array")
    if not np.all(np.isfinite(velocities)) or not np.all(np.isfinite(offsets)):
        raise ValueError("non-finite velocity or offset")
    if np.any(np.diff(velocities) < -1e-10) or np.any(velocities <= 0.0):
        raise ValueError("layer velocities must be positive and nondecreasing")

    intercepts = np.zeros(len(velocities), dtype=float)
    for layer in range(1, len(velocities)):
        inverse_square = (
            1.0 / velocities[:layer] ** 2 - 1.0 / velocities[layer] ** 2
        )
        intercepts[layer] = 2.0 * LAYER_THICKNESS_M * float(
            np.sum(np.sqrt(np.maximum(inverse_square, 0.0)))
        )
    branches = intercepts[:, None] + offsets[None, :] / velocities[:, None]
    return np.min(branches, axis=0)


def make_scenario(seed, n_layers):
    """Generate a deterministic identifiable refraction survey."""
    rng = np.random.default_rng(seed)
    velocities = np.empty(n_layers, dtype=float)
    velocities[0] = rng.uniform(1650.0, 2050.0)
    for layer in range(1, n_layers):
        lower = 350.0 + 100.0 * layer
        upper = 550.0 + 140.0 * layer
        velocities[layer] = velocities[layer - 1] + rng.uniform(lower, upper)

    # Dense near-offset coverage resolves the intermediate head-wave branches; long offsets
    # identify the deepest half-space. Random absolute positions prevent an implementation from
    # accidentally treating receiver coordinates as offsets.
    offsets = np.concatenate((
        np.arange(200.0, 6200.0, 100.0),
        np.arange(6500.0, 12001.0, 500.0),
    ))
    offsets = np.sort(offsets + rng.uniform(-25.0, 25.0, len(offsets)))
    sources = rng.uniform(-1000.0, 2000.0, len(offsets))
    receivers = sources + rng.choice((-1.0, 1.0), len(offsets)) * offsets
    clean_times = first_arrival_times(velocities, offsets)
    observed_times = clean_times + rng.normal(0.0, PICK_NOISE_S, len(offsets))

    holdout_offsets = np.linspace(150.0, 14000.0, 96)
    holdout_offsets += rng.uniform(-20.0, 20.0, len(holdout_offsets))
    return {
        "seed": int(seed),
        "n_layers": int(n_layers),
        "true_v": velocities,
        "sources": sources,
        "receivers": receivers,
        "offsets": offsets,
        "times": observed_times,
        "clean_times": clean_times,
        "holdout_offsets": holdout_offsets,
    }


SCENARIOS = [make_scenario(seed, n_layers) for seed, n_layers in SCENARIO_CONFIGS]


def _constant_velocity(sc):
    velocity = float(np.mean(sc["offsets"]) / max(np.mean(sc["times"]), 1e-12))
    return np.full(sc["n_layers"], np.clip(velocity, VELOCITY_MIN, VELOCITY_MAX))


def _rmse(left, right):
    return float(np.sqrt(np.mean((np.asarray(left) - np.asarray(right)) ** 2)))


def _relative_velocity_error(estimate, truth):
    return float(np.sqrt(np.mean(((np.asarray(estimate) - truth) / truth) ** 2)))


def _normalized_improvement(error, baseline_error, reference_error=0.0):
    denominator = baseline_error - reference_error
    if denominator <= 1e-15:
        return 1.0 if error <= reference_error + 1e-15 else 0.0
    return float(np.clip((baseline_error - error) / denominator, 0.0, 1.0))


def _score_profile(sc, estimate):
    baseline = _constant_velocity(sc)
    predicted = first_arrival_times(estimate, sc["offsets"])
    baseline_predicted = first_arrival_times(baseline, sc["offsets"])
    development_rmse = _rmse(predicted, sc["times"])
    baseline_development_rmse = _rmse(baseline_predicted, sc["times"])
    # Perfectly fitting noisy observations defines the visible optimization ceiling. The true
    # profile usually scores just below one because it does not fit measurement noise.
    development_score = _normalized_improvement(
        development_rmse, baseline_development_rmse
    )

    mechanism_error = _relative_velocity_error(estimate, sc["true_v"])
    baseline_mechanism_error = _relative_velocity_error(baseline, sc["true_v"])
    mechanism_score = _normalized_improvement(
        mechanism_error, baseline_mechanism_error
    )

    expected_holdout = first_arrival_times(sc["true_v"], sc["holdout_offsets"])
    predicted_holdout = first_arrival_times(estimate, sc["holdout_offsets"])
    baseline_holdout = first_arrival_times(baseline, sc["holdout_offsets"])
    holdout_rmse = _rmse(predicted_holdout, expected_holdout)
    baseline_holdout_rmse = _rmse(baseline_holdout, expected_holdout)
    holdout_score = _normalized_improvement(holdout_rmse, baseline_holdout_rmse)
    return {
        "development_score": development_score,
        "mechanism_score": mechanism_score,
        "holdout_prediction_score": holdout_score,
        "development_rmse_ms": 1000.0 * development_rmse,
        "velocity_relative_error": mechanism_error,
        "holdout_rmse_ms": 1000.0 * holdout_rmse,
    }


def evaluate(invert_seismic):
    results = []
    for sc in SCENARIOS:
        try:
            estimate = np.asarray(invert_seismic(
                sc["times"].copy(),
                sc["sources"].copy(),
                sc["receivers"].copy(),
                sc["n_layers"],
            ), dtype=float)
            if estimate.shape != (sc["n_layers"],):
                raise ValueError("velocity profile has the wrong shape")
            if not np.all(np.isfinite(estimate)):
                raise ValueError("velocity profile contains non-finite values")
            if np.any(estimate < VELOCITY_MIN) or np.any(estimate > VELOCITY_MAX):
                raise ValueError("velocity outside the physical bounds [1400,7000] m/s")
            if np.any(np.diff(estimate) < -1e-8):
                raise ValueError("velocity profile must be nondecreasing with depth")
            metrics = _score_profile(sc, estimate)
            metrics.update({"valid": True, "n_layers": sc["n_layers"]})
            results.append(metrics)
        except Exception as exc:
            results.append({
                "valid": False,
                "n_layers": sc["n_layers"],
                "reason": str(exc),
                "development_score": 0.0,
                "mechanism_score": 0.0,
                "holdout_prediction_score": 0.0,
            })

    valid = all(row["valid"] for row in results)
    development = float(np.mean([row["development_score"] for row in results]))
    mechanism = float(np.mean([row["mechanism_score"] for row in results]))
    holdout = float(np.mean([row["holdout_prediction_score"] for row in results]))
    development_rmse = [row.get("development_rmse_ms") for row in results if row["valid"]]
    holdout_rmse = [row.get("holdout_rmse_ms") for row in results if row["valid"]]
    return {
        "combined_score": development if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": float(np.mean([row["valid"] for row in results])),
        "raw_score": -float(np.mean(development_rmse)) if development_rmse else -1e9,
        "development_score": development,
        "mechanism_score": mechanism,
        # This is a separate held-out diagnostic. It is not yet called strictly sealed because
        # all upstream framework adapters do not yet redact non-selection metrics.
        "holdout_prediction_score": holdout,
        "mean_development_rmse_ms": (
            float(np.mean(development_rmse)) if development_rmse else 1e12
        ),
        "mean_holdout_rmse_ms": float(np.mean(holdout_rmse)) if holdout_rmse else 1e12,
        "per_scenario": results,
    }
