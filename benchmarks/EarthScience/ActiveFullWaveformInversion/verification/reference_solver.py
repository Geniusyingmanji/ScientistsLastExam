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
    from scipy.ndimage import zoom, gaussian_filter1d
    from scipy.optimize import least_squares
    del receiver_x_m
    count = min(int(budget_units), 3)
    indices = np.linspace(0, len(source_indices) - 1, count, dtype=int)
    gathers = [acquire(int(source_indices[i])) for i in indices]
    background = np.asarray(background_velocity_m_s, dtype=float)
    observed = np.asarray([row["pressure"] for row in gathers])
    sources = [int(row["source_index"]) for row in gathers]
    def forward(velocity):
        return np.asarray([_simulate(velocity, source, spacing_m, np.asarray(time_s)) for source in sources])
    background_traces = forward(background)
    relative = np.linalg.norm(observed - background_traces) / max(np.linalg.norm(background_traces), 1e-12)
    energy_ratio = np.linalg.norm(observed) / max(np.linalg.norm(background_traces), 1e-12)
    if relative < .006 or energy_ratio < .95:
        return {"velocity_m_s": [], "confidence": .1, "abstain": True}
    shape = (3, 5)
    scale = np.asarray(grid_shape) / np.asarray(shape)
    def velocity(parameters):
        correction = zoom(parameters.reshape(shape), scale, order=1)
        return np.clip(background + 900.0 * correction, *velocity_bounds_m_s)
    parameters = np.zeros(np.prod(shape))
    normalization = max(float(np.linalg.norm(observed)), 1e-12)
    for smoothing, iterations in ((3.0, 8), (0.0, 10)):
        target = gaussian_filter1d(observed, smoothing, axis=1) if smoothing else observed
        def residual(values):
            prediction = forward(velocity(values))
            if smoothing:
                prediction = gaussian_filter1d(prediction, smoothing, axis=1)
            data = ((prediction - target) / normalization).ravel()[::3]
            grid = values.reshape(shape)
            regularizer = .0005 * np.r_[np.diff(grid,axis=0).ravel(),np.diff(grid,axis=1).ravel()]
            return np.r_[data, regularizer]
        result = least_squares(residual, parameters, bounds=(-1.5,1.5), max_nfev=iterations,
                               diff_step=.002, ftol=1e-5, xtol=1e-5, gtol=1e-6)
        parameters = result.x
    prediction = velocity(parameters)
    misfit = np.linalg.norm(forward(prediction) - observed) / normalization
    if misfit > .12:
        return {"velocity_m_s": [], "confidence": .1, "abstain": True}
    return {"velocity_m_s": prediction, "confidence": .8, "abstain": False}
