"""Operator-only 64-site Fourier-collocation model and work-bounded solver."""

from dataclasses import dataclass
import hashlib
import math

import numpy as np
from scipy.integrate import solve_ivp

from .protocol import GRID_SIZE, PROBE_COUNT, initial_values

STRUCTURES = ("positive_r0_unforced", "negative_r0_unforced", "anchored_forcing")
RTOL, ATOL, MAX_STEP = 1e-8, 1e-10, .5
MAX_EVALUATIONS, MAX_JACOBIANS, STATE_ABORT_BOUND = 12000, 1000, 8.


def random_generator(seed, purpose):
    payload = ("pattern-formation-v1:%d:%s" % (seed, purpose)).encode("ascii")
    return np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))


@dataclass(frozen=True)
class Parameters:
    r0: float = .24
    gain: float = .35
    q0: float = 1.
    cubic: float = 1.
    forcing: float = 0.
    forcing_mode: int = 3
    forcing_phase: float = 0.

    def __post_init__(self):
        values = (self.r0, self.gain, self.q0, self.cubic, self.forcing, self.forcing_phase)
        if not all(type(x) in (int, float) and math.isfinite(x) for x in values):
            raise ValueError("invalid internal parameters")
        if not (-.5 <= self.r0 <= .32 and .2 <= self.gain <= .7 and .85 <= self.q0 <= 1.15 and
                .8 <= self.cubic <= 1.3 and 0 <= self.forcing <= .07 and -math.pi <= self.forcing_phase <= math.pi and
                type(self.forcing_mode) is int and 2 <= self.forcing_mode <= 5):
            raise ValueError("internal parameters outside the bounded domain")

    @classmethod
    def generate(cls, seed, structure):
        if structure not in STRUCTURES:
            raise ValueError("unknown internal structure")
        rng = random_generator(seed, "parameters")
        q0, cubic = float(rng.uniform(.85, 1.15)), float(rng.uniform(.8, 1.3))
        positive, negative = float(rng.uniform(.16, .32)), float(rng.uniform(-.5, -.3))
        gain, forced_gain = float(rng.uniform(.2, .5)), float(rng.uniform(.4, .7))
        forced_r0, forcing = float(rng.uniform(-.18, -.08)), float(rng.uniform(.025, .07))
        mode, phase = int(rng.integers(2, 6)), float(rng.uniform(-np.pi, np.pi))
        forced = structure == STRUCTURES[2]
        return cls(r0=forced_r0 if forced else (positive if structure == STRUCTURES[0] else negative),
                   gain=forced_gain if forced else gain, q0=q0, cubic=cubic,
                   forcing=forcing if forced else 0., forcing_mode=mode, forcing_phase=phase)


class Kernel:
    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise ValueError("Kernel needs Parameters")
        self.parameters = parameters

    def operator(self, spec):
        p = self.parameters
        wave = 2*np.pi*np.fft.fftfreq(GRID_SIZE, d=spec["length"]/GRID_SIZE)
        eigenvalues = p.r0 + p.gain*spec["drive"] - (p.q0*p.q0 - wave*wave)**2
        matrix = np.fft.ifft(eigenvalues[:, None]*np.fft.fft(np.eye(GRID_SIZE), axis=0), axis=0).real
        forcing = p.forcing*np.cos(2*np.pi*p.forcing_mode*np.arange(GRID_SIZE)/GRID_SIZE + p.forcing_phase)
        return matrix, forcing, eigenvalues

    def trajectory(self, spec):
        times = np.asarray(spec["times"], dtype=float)
        initial = initial_values(spec, GRID_SIZE)
        matrix, force, _ = self.operator(spec)
        evaluations, jacobians = 0, 0

        def derivative(t, state):
            nonlocal evaluations
            evaluations += 1
            if evaluations > MAX_EVALUATIONS:
                raise RuntimeError("numerical RHS work limit exceeded")
            if not np.isfinite(state).all() or np.max(np.abs(state)) > STATE_ABORT_BOUND:
                raise RuntimeError("numerical state safety bound exceeded")
            return matrix.dot(state) - self.parameters.cubic*state**3 + force

        def jacobian(t, state):
            nonlocal jacobians
            jacobians += 1
            if jacobians > MAX_JACOBIANS:
                raise RuntimeError("numerical Jacobian work limit exceeded")
            return matrix - np.diag(3*self.parameters.cubic*state**2)

        if times[-1] == 0:
            full = initial[None, :]
            steps = 0
        else:
            solution = solve_ivp(derivative, (0., times[-1]), initial, method="BDF", jac=jacobian,
                                 rtol=RTOL, atol=ATOL, max_step=MAX_STEP, t_eval=times)
            if not solution.success or not np.isfinite(solution.y).all():
                raise RuntimeError("pattern integration failed")
            full = solution.y.T
            steps = int(solution.nlu)
        if times[0] == 0:
            full[0] = initial
        if not np.isfinite(full).all() or np.max(np.abs(full)) > STATE_ABORT_BOUND:
            raise RuntimeError("nonfinite or oversized output")
        return full[:, ::GRID_SIZE//PROBE_COUNT].copy(), {"rhs_evaluations": evaluations,
                "jacobian_evaluations": jacobians, "linear_factorizations": steps,
                "max_abs_internal_sample": float(np.max(np.abs(full)))}
