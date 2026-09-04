"""Truth-blind plume-aligned multirate archive witness."""

import numpy as np


def design_remediation(problem):
    source_x, source_y = map(float, problem["source_location_m"])
    velocity = float(problem["groundwater_velocity_m_day"])
    plans = []
    for count in (2, 3, 4, 5):
        for rate in (420.0, 620.0, 820.0):
            rate = min(rate, float(problem["max_total_pumping_m3_day"]) / count)
            xs = np.linspace(source_x + 1400.0,
                             min(float(problem["domain_size_m"][0]) - 300.0,
                                 source_x + velocity * 365.25 * 13.0), count)
            wells = np.column_stack((xs, source_y + np.linspace(-180.0, 180.0, count),
                                     np.linspace(0.5, 2.5, count), np.full(count, rate)))
            if not any(np.array_equal(wells, old) for old in plans):
                plans.append(wells)
    return {"plans": plans}
