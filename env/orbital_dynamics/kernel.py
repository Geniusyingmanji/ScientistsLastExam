"""Trusted smooth force model and bounded event-split integrator."""

from dataclasses import dataclass
import hashlib
import math

import numpy as np
from scipy.integrate import solve_ivp

from .protocol import RESOLUTION_RADIUS


STRUCTURES = ("softened_inverse_square", "softened_alternative_power", "softened_inverse_square_drag")
RTOL, ATOL, MAX_STEP, MAX_EVALUATIONS = 2e-10, 2e-12, 0.08, 60000


def random_generator(seed, purpose):
    payload = ("orbital-dynamics-v1:%d:%s" % (seed, purpose)).encode("ascii")
    return np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))


@dataclass(frozen=True)
class Parameters:
    mu: float = 1.0
    exponent: float = 2.0
    drag: float = 0.0
    softening: float = RESOLUTION_RADIUS

    def __post_init__(self):
        values = (self.mu, self.exponent, self.drag, self.softening)
        if not all(type(x) in (int, float) and math.isfinite(x) for x in values):
            raise ValueError("invalid internal parameters")
        if not (0 <= self.mu <= 1.3 and 1 <= self.exponent <= 2.65 and
                0 <= self.drag <= 0.12 and self.softening == RESOLUTION_RADIUS):
            raise ValueError("internal parameters outside bounded kernel domain")

    @classmethod
    def generate(cls, seed, structure):
        if structure not in STRUCTURES:
            raise ValueError("unknown internal structure")
        rng = random_generator(seed, "parameters")
        mu = float(rng.uniform(0.8, 1.2))
        p = float(rng.uniform(1.35, 1.65) if rng.integers(2) == 0 else rng.uniform(2.35, 2.65))
        gamma = float(rng.uniform(0.045, 0.10))
        return cls(mu=mu, exponent=p if structure == STRUCTURES[1] else 2.0,
                   drag=gamma if structure == STRUCTURES[2] else 0.0)


class Kernel:
    def __init__(self, parameters):
        self.parameters = parameters

    def derivative(self, time, state):
        p = self.parameters
        x, y, vx, vy = state
        factor = p.mu / (x*x + y*y + p.softening*p.softening)**((p.exponent + 1) / 2)
        return np.asarray([vx, vy, -factor*x - p.drag*vx, -factor*y - p.drag*vy])

    def potential(self, positions):
        """Potential per unit mass, zero at infinity for p>1; log at p=1."""
        p = self.parameters
        q = np.sum(np.asarray(positions, dtype=float)**2, axis=-1) + p.softening**2
        if p.exponent == 1:
            return 0.5 * p.mu * np.log(q)
        return -p.mu / (p.exponent - 1) * q**((1 - p.exponent) / 2)

    def trajectory(self, spec):
        times = np.asarray(spec["times"], dtype=float)
        state = np.asarray(spec["position"] + spec["velocity"], dtype=float)
        output = np.empty((len(times), 4))
        evaluations, segments, cursor, current = 0, 0, 0, 0.0

        def derivative(t, y):
            nonlocal evaluations
            evaluations += 1
            if evaluations > MAX_EVALUATIONS:
                raise RuntimeError("numerical work limit exceeded")
            return self.derivative(t, y)

        boundaries = sorted(set([0.0, times[-1]] + [e["time"] for e in spec["impulses"]]))
        for target in boundaries:
            if target > current:
                solution = solve_ivp(derivative, (current, target), state, method="DOP853",
                                     rtol=RTOL, atol=ATOL, max_step=MAX_STEP, dense_output=True)
                if not solution.success or not np.isfinite(solution.y).all():
                    raise RuntimeError("trajectory integration failed")
                selected = (times > current) & (times <= target)
                if np.any(selected):
                    output[selected] = solution.sol(times[selected]).T
                state = solution.y[:, -1].copy()
                segments += 1
            current = target
            if cursor < len(spec["impulses"]) and spec["impulses"][cursor]["time"] == target:
                state[2:] += spec["impulses"][cursor]["delta_v"]
                cursor += 1
            output[times == target] = state
        if not np.isfinite(output).all():
            raise RuntimeError("nonfinite trajectory output")
        return output, {"rhs_evaluations": evaluations, "segments": segments}
