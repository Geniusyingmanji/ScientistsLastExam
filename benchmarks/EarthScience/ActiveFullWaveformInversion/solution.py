"""Weak valid baseline: acquire one shot and decline to claim an anomaly."""


def invert_velocity_model(
    grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s,
    source_indices, receiver_x_m, time_s, acquire, budget_units,
):
    del grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s
    del receiver_x_m, time_s, budget_units
    acquire(int(source_indices[len(source_indices) // 2]))
    return {"velocity_m_s": [], "confidence": 0.0, "abstain": True}
