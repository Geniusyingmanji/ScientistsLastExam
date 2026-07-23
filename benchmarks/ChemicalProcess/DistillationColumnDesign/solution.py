"""Weak but feasible policy for the equilibrium-stage distillation task."""

from __future__ import annotations

import math


def _odds(value):
    value = min(max(float(value), 1.0e-8), 1.0 - 1.0e-8)
    return value / (1.0 - value)


def design_column(problem):
    """Return a conservative column design using only public problem fields."""
    lower_stages, upper_stages = problem["tray_count_bounds"]
    lower_reflux, upper_reflux = problem["reflux_ratio_bounds"]
    lower_distillate, upper_distillate = problem["distillate_fraction_bounds"]
    tray_count = int(upper_stages)

    alpha = float(problem["relative_volatility"])
    feed = float(problem["feed_light_mole_fraction"])
    top = float(problem["minimum_distillate_light_mole_fraction"])
    bottom = float(problem["maximum_bottoms_light_mole_fraction"])
    rectifying_difficulty = max(
        0.0, math.log(_odds(top) / _odds(feed)) / math.log(alpha)
    )
    stripping_difficulty = max(
        0.0, math.log(_odds(feed) / _odds(bottom)) / math.log(alpha)
    )
    fraction_above_feed = rectifying_difficulty / max(
        rectifying_difficulty + stripping_difficulty, 1.0e-12
    )
    feed_stage = int(round(1.0 + fraction_above_feed * (tray_count - 1)))
    feed_stage = min(max(feed_stage, 1), tray_count)

    target_distillate = (feed - bottom) / (top - bottom)
    minimum_split = (
        float(problem["minimum_light_recovery"]) * feed / top
    )
    maximum_split = 1.0 - (
        float(problem["minimum_heavy_recovery"]) * (1.0 - feed)
        / (1.0 - bottom)
    )
    if minimum_split <= maximum_split:
        target_distillate = min(
            max(target_distillate, minimum_split), maximum_split
        )
    distillate_fraction = min(
        max(target_distillate, float(lower_distillate)), float(upper_distillate)
    )
    reflux_ratio = min(
        max(0.86 * float(upper_reflux), float(lower_reflux)),
        float(upper_reflux),
    )
    return {
        "tray_count": tray_count,
        "feed_stage": feed_stage,
        "reflux_ratio": reflux_ratio,
        "distillate_fraction": distillate_fraction,
        "feed_split_gain": 1.0 / max(top - bottom, 0.20),
    }
