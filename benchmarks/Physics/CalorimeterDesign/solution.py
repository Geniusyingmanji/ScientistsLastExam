"""Weak valid baseline: three uniform designs at 90% of each cost cap."""

import numpy as np


def design_calorimeter(problem):
    n_layers = int(problem["n_layers"])
    archive_size = int(problem["archive_size"])
    passive = np.full(
        (archive_size, n_layers),
        float(problem["baseline_absorber_depth_x0"])
        * float(problem["radiation_length_pb_mm"])
        / n_layers,
        dtype=float,
    )
    lead_mass = (
        float(np.sum(passive[0]))
        * 1.0e-3
        * float(problem["lead_density_kg_m3"])
    )
    passive_cost = float(problem["lead_cost_per_kg"]) * lead_mass
    fixed_cost = (
        float(problem["readout_areal_cost_per_layer"]) * n_layers
    )
    active = np.empty_like(passive)
    for option, cap in enumerate(problem["option_cost_caps"]):
        active_total = (
            float(problem["baseline_cost_fraction"]) * float(cap)
            - passive_cost
            - fixed_cost
        ) / float(problem["active_cost_per_liter"])
        active[option] = active_total / n_layers
    return {
        "passive_thicknesses_mm": passive,
        "active_thicknesses_mm": active,
    }
