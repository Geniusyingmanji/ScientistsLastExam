"""Public response basis and population prediction helpers; no private worlds."""
import numpy as np


def dose_basis(dose):
    dose = np.asarray(dose, dtype=float)
    return np.stack((3 * dose * (1 - dose) ** 2, 3 * dose ** 2 * (1 - dose), dose ** 3), axis=-1)


def population_effect(cell_coefficients, cell_weights, doses):
    return np.asarray(cell_weights).dot(np.asarray(cell_coefficients)).dot(dose_basis(doses).T)
