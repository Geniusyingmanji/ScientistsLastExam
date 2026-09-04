"""Weak but valid baseline for ModalDamageAttribution.

It does what the instrument invites: spread the measurement days over the widest temperature range
available - which is what you would do to validate a temperature law - fit a straight line to the
commissioning frequencies against temperature, extrapolate it to each measured day, and call any
mode that has moved further than a few standard deviations damage. The straight line is the trap:
the commissioning campaign covers only the warm band, the true stiffness law has a knee at
freezing, and half this budget lands below it. It never declines, so a support change is published
as damage too.
"""
from __future__ import annotations

import numpy as np


def attribute_damage(problem, measure):
    modes = int(problem["mode_count"])
    budget = int(problem["measurement_budget_days"])
    baseline = problem["commissioning_baseline"]
    temperatures = np.array([row["temperature_celsius"] for row in baseline], dtype=float)
    frequencies = np.array([row["frequencies_hz"] for row in baseline], dtype=float)
    fits = [np.polyfit(temperatures, frequencies[:, k], 1) for k in range(modes)]
    residual = float(np.std(frequencies / np.mean(frequencies, axis=0) - 1.0))

    # Spread the days over the widest temperature range: that is what you would do to validate a
    # temperature law, and it puts most of the budget on the coldest days on the calendar.
    calendar = problem["calendar"]
    order = sorted(range(len(calendar)), key=lambda d: calendar[d]["temperature_celsius"])
    chosen = order[: budget // 2] + order[-(budget - budget // 2):]

    worst_mode, worst_deviation = 0, 0.0
    for day in chosen:
        try:
            reading = measure(day)
        except Exception:
            break
        measured = np.asarray(reading["frequencies_hz"], dtype=float)
        expected = np.array([np.polyval(fit, reading["temperature_celsius"]) for fit in fits])
        deviation = measured / expected - 1.0
        index = int(np.argmax(np.abs(deviation)))
        if abs(deviation[index]) > abs(worst_deviation):
            worst_mode, worst_deviation = index, float(deviation[index])

    if abs(worst_deviation) < 3.0 * max(residual, 1e-6):
        return {"damaged": False, "abstain": False, "confidence": 0.8}
    element = int(np.clip(worst_mode + 1, 1, int(problem["mass_count"]) - 1))
    return {"damaged": True, "element": element, "severity": float(min(0.9, abs(worst_deviation))),
            "abstain": False, "confidence": 0.9}
