"""Weak valid baseline: one measurement followed by calibrated refusal."""


def discover_critical_behavior(
    lattice_sizes, temperature_bounds, experiment, budget_units
):
    size = int(lattice_sizes[0])
    midpoint = 0.5 * (float(temperature_bounds[0]) + float(temperature_bounds[1]))
    experiment(size, midpoint, 128)
    return {"abstain": True, "confidence": 0.0}
