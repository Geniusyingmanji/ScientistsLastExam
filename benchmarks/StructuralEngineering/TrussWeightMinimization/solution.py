"""Weak valid baseline: use the maximum public area for every truss member."""

import numpy as np


def design_truss(nodes, members, fixed_dofs, load_cases, youngs_modulus, density,
                 tension_allowable, compression_allowable, displacement_limit,
                 area_min, area_max, inertia_coefficient):
    del nodes, fixed_dofs, load_cases, youngs_modulus, density
    del tension_allowable, compression_allowable, displacement_limit
    del area_min, inertia_coefficient
    return np.full(len(members), float(area_max), dtype=float)
