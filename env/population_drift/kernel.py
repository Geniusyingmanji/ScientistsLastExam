"""Private finite-state Poissonized Moran dynamics using matrix exponentials."""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from .protocol import number, validate_spec


@dataclass(frozen=True)
class Parameters:
    selection: float
    frequency_effect: float
    mutation_probability: float

    def __post_init__(self):
        for name, low, high in (("selection", -1, 1), ("frequency_effect", -2, 2), ("mutation_probability", 0, .05)):
            object.__setattr__(self, name, number(getattr(self, name), low, high, name))


class Kernel:
    MAX_EXPONENTIALS = 33
    MASS_TOLERANCE = 2e-11
    BOUND_TOLERANCE = 2e-12

    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise ValueError("expected validated Parameters")
        self.parameters = parameters

    def _rates(self, spec):
        n = spec["population_size"]
        count = np.arange(n+1, dtype=float)
        relative = np.exp(self.parameters.selection + self.parameters.frequency_effect*(2*count/n-1) + spec["selection_bias"])
        parent_a = count*relative/(count*relative+(n-count))
        m, a = self.parameters.mutation_probability, spec["newborn_flip_probability"]
        flip = m+a-2*m*a
        newborn_a = flip+(1-2*flip)*parent_a
        return (n-count)*newborn_a, count*(1-newborn_a)

    def generator(self, spec):
        up, down = self._rates(spec)
        n = spec["population_size"]
        if np.shape(up) != (n+1,) or np.shape(down) != (n+1,) or not np.isfinite(up).all() or not np.isfinite(down).all():
            raise RuntimeError("population generator rates became nonfinite or malformed")
        if min(float(np.min(up)), float(np.min(down))) < 0 or np.any(up+down > n+1e-12) or up[-1] != 0 or down[0] != 0:
            raise RuntimeError("population generator violates rate bounds")
        q = np.diag(-up-down)+np.diag(up[:-1], 1)+np.diag(down[1:], -1)
        if float(np.max(np.abs(q.sum(axis=1)))) > 1e-12:
            raise RuntimeError("population generator row sum is not zero")
        return q

    def _matrices(self, spec):
        q = self.generator(spec)
        n = spec["population_size"]
        matrices, calls = [], 0
        for t in spec["times"]:
            if t == 0:
                transition = np.eye(n+1)
            else:
                if calls >= self.MAX_EXPONENTIALS:
                    raise RuntimeError("population matrix exponential budget exhausted")
                calls += 1
                transition = expm(q*t)
            if not np.isfinite(transition).all():
                raise RuntimeError("population transition became nonfinite")
            if transition.min() < -self.BOUND_TOLERANCE or transition.max() > 1+self.BOUND_TOLERANCE:
                raise RuntimeError("population transition left probability bounds")
            if np.max(np.abs(transition.sum(axis=1)-1)) > self.MASS_TOLERANCE:
                raise RuntimeError("population transition lost probability mass")
            # No probability clipping or renormalization is performed.
            matrices.append(transition)
        values = np.asarray(matrices)
        diagnostics = {"matrix_exponentials": calls, "states": n+1,
                       "maximum_row_mass_error": float(np.max(np.abs(values.sum(axis=2)-1))),
                       "minimum_transition_entry": float(values.min()),
                       "generator_maximum_exit_rate": float((-np.diag(q)).max())}
        return values, diagnostics

    def transition_matrices(self, spec):
        """Private operator route used only by the charged semigroup fixtures."""
        return self._matrices(validate_spec(spec))

    def trajectory(self, spec):
        spec = validate_spec(spec)
        matrices, diagnostics = self._matrices(spec)
        probabilities = matrices[:, spec["initial_A"], :]
        x = np.arange(spec["population_size"]+1)/spec["population_size"]
        values = np.column_stack((probabilities @ x, probabilities @ (2*x*(1-x)),
                                  probabilities[:, -1], probabilities[:, 0]))
        if not np.isfinite(values).all():
            raise RuntimeError("population ensemble readout became nonfinite")
        diagnostics["probabilities"] = probabilities.tolist()
        return values, diagnostics
