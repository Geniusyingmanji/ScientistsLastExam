"""Weak valid baseline: a conservative condition-aware reheat archive."""

import numpy as np


def design_rankine_archive(problem):
    bounds = np.asarray(problem["design_bounds"], dtype=float)
    condition = problem["operating_condition"]
    pressure_high = min(
        bounds[0, 1], float(condition["max_boiler_pressure_mpa"]) - 1.25
    )
    pressure_low = max(bounds[0, 0], pressure_high - 3.0)
    temperature_high = min(
        bounds[1, 1], float(condition["max_steam_temperature_c"]) - 25.0
    )
    temperature_low = max(bounds[1, 0], temperature_high - 45.0)
    rows = []
    for fraction in np.linspace(0.0, 1.0, 8):
        rows.append((
            pressure_low + fraction * (pressure_high - pressure_low),
            temperature_low + 0.65 * fraction * (
                temperature_high - temperature_low
            ),
            0.14 + 0.10 * fraction,
            temperature_low + (0.35 + 0.65 * fraction) * (
                temperature_high - temperature_low
            ),
        ))
    return np.asarray(rows, dtype=float)
