"""Weak valid baseline for the room-acoustic treatment task."""

import numpy as np


def _allocate_area(total_area, weights, maximum_areas):
    weights = np.maximum(np.asarray(weights, dtype=float), 0.0)
    maximum_areas = np.asarray(maximum_areas, dtype=float)
    allocation = np.zeros_like(maximum_areas)
    active = maximum_areas > 0.0
    total_area = min(float(total_area), float(np.sum(maximum_areas)))
    for _ in range(len(allocation) + 1):
        remaining = total_area - float(np.sum(allocation))
        if remaining <= 1.0e-12 or not np.any(active):
            break
        active_weights = weights * active
        if float(np.sum(active_weights)) <= 1.0e-12:
            active_weights = active.astype(float)
        proposed = remaining * active_weights / float(np.sum(active_weights))
        capacity = np.maximum(maximum_areas - allocation, 0.0)
        addition = np.minimum(proposed, capacity)
        allocation += addition
        active = capacity - addition > 1.0e-12
    return allocation


def design_room(problem):
    """Return source position followed by six finite treatment areas in m2."""
    source_bounds = np.asarray(problem["source_position_bounds_m"], dtype=float)
    source_position = np.mean(source_bounds, axis=1)
    surface_areas = np.asarray(problem["surface_areas_m2"], dtype=float)
    maximum_areas = surface_areas * np.asarray(
        problem["maximum_treatment_fraction_by_surface"], dtype=float
    )
    treatment_area = _allocate_area(
        0.52 * float(problem["maximum_treatment_area_m2"]),
        surface_areas,
        maximum_areas,
    )
    return np.concatenate((source_position, treatment_area))
