"""Truth-blind reference: iterative pre-whitening with a false-alarm cut. Calibration only.

The standard procedure. Take the strongest periodogram peak, keep it only if its false-alarm
probability clears a threshold, subtract the fitted sinusoid, and repeat on the residual. Stop
when no peak survives. The known weakness is that the procedure has no way to tell a planet from
stellar rotation, so the activity signal is usually claimed - which is exactly the failure the
false-discovery axis is there to expose.

It never sees the truth. It reads only what a candidate reads.
"""

from __future__ import annotations

FAP_THRESHOLD = 1e-3
MAX_SIGNALS = 4


def detect_planets(observation):
    import numpy as np
    from astropy.timeseries import LombScargle

    t = np.asarray(observation["times"], dtype=float)
    residual = np.asarray(observation["velocities"], dtype=float).copy()
    dy = np.asarray(observation["uncertainties"], dtype=float)

    found = []
    for _ in range(MAX_SIGNALS):
        model = LombScargle(t, residual, dy)
        freq, power = model.autopower(
            minimum_frequency=1.0 / 200.0, maximum_frequency=1.0 / 0.5)
        peak = int(np.argmax(power))
        if model.false_alarm_probability(power[peak]) > FAP_THRESHOLD:
            break
        period = float(1.0 / freq[peak])
        found.append(period)
        residual = residual - model.model(t, freq[peak])
    return {"planets": [{"period": p} for p in found]}
