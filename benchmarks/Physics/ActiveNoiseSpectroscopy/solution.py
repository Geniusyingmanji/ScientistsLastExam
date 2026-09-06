"""Weak baseline: fit no data and call every device a single fluctuator.

The generic midpoint parameters are legal, but a PSD-matched Gaussian or a
multi-fluctuator environment becomes a false discovery.
"""

from __future__ import annotations


def discover_noise(problem, measure):
    del measure
    bounds = problem["parameter_bounds"]
    return {
        "abstain": False,
        "noise_model": "single_telegraph",
        "switching_rate_per_us": sum(bounds["switching_rate_per_us"]) / 2.0,
        "noise_variance_rad2_per_us2": (
            sum(bounds["noise_variance_rad2_per_us2"]) / 2.0
        ),
        "high_state_probability": sum(bounds["high_state_probability"]) / 2.0,
        "confidence": 0.75,
    }
