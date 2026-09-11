"""Weak valid baseline: one shot, then confidently retain the background model."""


def invert_velocity_model(
    grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s,
    source_indices, receiver_x_m, time_s, acquire, budget_units,
):
    del grid_shape, spacing_m, velocity_bounds_m_s, receiver_x_m, time_s, budget_units
    acquire(int(source_indices[len(source_indices) // 2]))
    # A background-only interpretation neither recovers anomalies nor checks
    # whether the acoustic model is appropriate for the acquired data.
    return {"velocity_m_s": background_velocity_m_s, "confidence": 0.9, "abstain": False}
