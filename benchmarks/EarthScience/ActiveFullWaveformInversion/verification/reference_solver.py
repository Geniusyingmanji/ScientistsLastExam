"""Truth-blind reconnaissance witness for the public FWI contract."""

import numpy as np


def _ricker(time_s, frequency_hz):
    delay = 1.5 / frequency_hz
    arg = np.pi * frequency_hz * (time_s - delay)
    return (1.0 - 2.0 * arg * arg) * np.exp(-arg * arg)


def _simulate(velocity, source_index, spacing_m, time_s):
    velocity = np.asarray(velocity, dtype=float)
    dt = float(time_s[1] - time_s[0])
    previous = np.zeros_like(velocity)
    current = np.zeros_like(velocity)
    receiver_indices = np.arange(2, velocity.shape[1] - 2, 2, dtype=int)
    traces = np.zeros((len(time_s), len(receiver_indices)))
    damping = np.ones_like(velocity)
    damping[[0, -1], :] = 0.86
    damping[:, [0, -1]] = 0.86
    damping[[1, -2], :] = 0.94
    damping[:, [1, -2]] = 0.94
    coefficient = (velocity * dt / spacing_m) ** 2
    wavelet = _ricker(np.asarray(time_s), 12.0)
    for step in range(len(time_s)):
        lap = np.zeros_like(current)
        lap[1:-1, 1:-1] = (current[1:-1, 2:] + current[1:-1, :-2]
                            + current[2:, 1:-1] + current[:-2, 1:-1]
                            - 4.0 * current[1:-1, 1:-1])
        following = (2.0 * current - previous + coefficient * lap) * damping
        following[2, int(source_index)] += wavelet[step]
        traces[step] = following[2, receiver_indices]
        previous, current = current, following
    return traces


def invert_velocity_model(
    grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s,
    source_indices, receiver_x_m, time_s, acquire, budget_units,
):
    del receiver_x_m, budget_units
    gathers = [acquire(int(source_indices[index])) for index in (0, 2, 4)]
    background = np.asarray(background_velocity_m_s, dtype=float)
    residuals = []
    energy_ratios = []
    for row in gathers:
        observed = np.asarray(row["pressure"], dtype=float)
        predicted = _simulate(background, int(row["source_index"]), float(spacing_m), np.asarray(time_s))
        residuals.append(np.linalg.norm(observed - predicted) / max(np.linalg.norm(predicted), 1e-12))
        energy_ratios.append(np.linalg.norm(observed) / max(np.linalg.norm(predicted), 1e-12))
    relative = float(np.mean(residuals))
    energy_ratio = float(np.mean(energy_ratios))
    if relative < 0.006 or relative > 0.28 or energy_ratio < 0.95:
        return {"velocity_m_s": [], "confidence": 0.15, "abstain": True}
    # A conservative smooth low-velocity lens is a useful but intentionally non-oracle witness.
    zz, xx = np.mgrid[0:grid_shape[0], 0:grid_shape[1]]
    lens = np.exp(-0.5 * (((xx - 0.5 * grid_shape[1]) / 4.5) ** 2
                         + ((zz - 0.58 * grid_shape[0]) / 3.0) ** 2))
    amplitude = np.clip(180.0 + 950.0 * relative, 180.0, 620.0)
    velocity = np.clip(background - amplitude * lens, *velocity_bounds_m_s)
    return {"velocity_m_s": velocity, "confidence": 0.55, "abstain": False}
