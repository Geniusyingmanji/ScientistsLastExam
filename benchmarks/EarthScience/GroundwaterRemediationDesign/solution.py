"""Weak valid baseline: a small archive of low-intensity downstream wells."""

import numpy as np


def design_remediation(problem):
    source_x, source_y = map(float, problem["source_location_m"])
    velocity = float(problem["groundwater_velocity_m_day"])
    horizon_days = 365.25 * float(problem["horizon_years"])
    center = min(float(problem["domain_size_m"][0]) * 0.8,
                 source_x + 0.55 * velocity * horizon_days)
    qmin = float(problem["pumping_rate_bounds_m3_day"][0])
    plans = []
    for offset in (-600.0, -200.0, 200.0, 600.0):
        plans.append(np.asarray([[center, np.clip(source_y + offset, 0.0, problem["domain_size_m"][1]),
                                  2.0, 1.15 * qmin]], dtype=float))
    return {"plans": plans}
