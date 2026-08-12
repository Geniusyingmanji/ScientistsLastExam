"""Baseline: claim the three strongest periodogram peaks as planets.

This is the mistake the task is about. The strongest peak in a radial-velocity periodogram is
often stellar rotation, and the next ones are frequently its harmonics or cadence aliases. Valid
by construction and deliberately weak.
"""


def detect_planets(observation):
    import numpy as np
    from astropy.timeseries import LombScargle

    t = np.asarray(observation["times"], dtype=float)
    y = np.asarray(observation["velocities"], dtype=float)
    dy = np.asarray(observation["uncertainties"], dtype=float)
    freq, power = LombScargle(t, y, dy).autopower(
        minimum_frequency=1.0 / 200.0, maximum_frequency=1.0 / 0.5)
    order = np.argsort(power)[::-1][:3]
    return {"planets": [{"period": float(1.0 / freq[i])} for i in order]}
