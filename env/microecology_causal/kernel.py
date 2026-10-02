"""Trusted carbon-transfer kinetics. This file is not an agent attachment."""

import hashlib
from dataclasses import dataclass, fields

import numpy as np
from scipy.integrate import solve_ivp


S, A, B, C, X, Y, Z, W = range(8)
STRUCTURES = ("inhibitory_feedback", "feedback_cut", "direct_toxin_detox")


def random_generator(seed, purpose):
    digest = hashlib.sha256(("microecology-causal:" + purpose + ":" + str(seed)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], "big"))


@dataclass(frozen=True)
class Parameters:
    uptake_a: float = 0.95
    uptake_b: float = 0.8
    uptake_c: float = 0.65
    half_s: float = 0.3
    half_x: float = 0.12
    half_consumer: float = 0.1
    inhibition_producer: float = 0.32
    inhibition_consumer: float = 0.18
    death: float = 0.012
    decay_x: float = 0.012
    decay_y: float = 0.025

    @classmethod
    def generate(cls, seed):
        rng = random_generator(seed, "parameters")
        base = cls()
        return cls(**{field.name: float(getattr(base, field.name) * rng.uniform(0.88, 1.12)) for field in fields(base)})


class Kernel:
    def __init__(self, parameters, structure):
        if structure not in STRUCTURES:
            raise ValueError("invalid operator structure")
        self.parameters = parameters
        self.structure = structure

    def derivative(self, time, state, temperature_c):
        # Nonnegative extension is used only for solver trial states at roundoff
        # below zero. Every physical boundary has nonnegative inward flux.
        s, a, b, c, x, y, z, _ = np.maximum(state, 0.0)
        p = self.parameters
        scale = 2.0 ** ((temperature_c - 30.0) / 10.0)
        producer_inhibitor = y if self.structure == "direct_toxin_detox" else z
        qa = scale * p.uptake_a * a * s / (p.half_s + s) / (1.0 + (producer_inhibitor / p.inhibition_producer)**2)
        qb = scale * p.uptake_b * b * x / (p.half_x + x)
        consumer_substrate = y if self.structure == "direct_toxin_detox" else z
        inhibition = 1.0 + (y / p.inhibition_consumer)**2 if self.structure == "inhibitory_feedback" else 1.0
        qc = scale * p.uptake_c * c * consumer_substrate / (p.half_consumer + consumer_substrate) / inhibition
        deaths = scale * p.death * np.asarray([a, b, c])
        decay_x, decay_y = scale * p.decay_x * x, scale * p.decay_y * y
        derivative = np.asarray([-qa, 0.4 * qa - deaths[0], 0.45 * qb - deaths[1],
                                 0.5 * qc - deaths[2], 0.35 * qa - qb - decay_x,
                                 0.55 * qb - decay_y, 0.25 * qa,
                                 0.5 * qc + float(deaths.sum()) + decay_x + decay_y])
        # Exactly ONE consumer substrate is removed in each structure.
        derivative[Y if self.structure == "direct_toxin_detox" else Z] -= qc
        return derivative

    @staticmethod
    def physical(state, expected_total):
        state = np.asarray(state, dtype=float).copy()
        if not np.isfinite(state).all() or state.min() < -1e-9 or abs(float(state.sum()) - expected_total) > 1e-7:
            raise RuntimeError("ecology integration failed physical checks")
        # Remove at most roundoff-sized negative entries, conserving carbon by
        # taking the same mass from the largest pool. This is not rate clipping.
        negative = state < 0.0
        if negative.any():
            correction = -float(state[negative].sum())
            state[negative] = 0.0
            largest = int(np.argmax(state))
            if state[largest] < correction:
                raise RuntimeError("ecology integration failed physical checks")
            state[largest] -= correction
        return state

    def advance(self, state, hours, temperature_c, sample_times=()):
        initial = np.asarray(state, dtype=float)
        total = float(initial.sum())
        if hours == 0:
            return np.repeat(initial[None, :], len(sample_times), axis=0), initial.copy()
        solution = solve_ivp(lambda t, y: self.derivative(t, y, temperature_c), (0.0, hours), initial,
                             method="LSODA", rtol=1e-9, atol=1e-12, max_step=0.5, dense_output=True)
        if not solution.success or solution.nfev > 50000:
            raise RuntimeError("ecology numerical integration failed")
        samples = np.asarray([self.physical(row, total) for row in solution.sol(sample_times).T]) if len(sample_times) else np.empty((0, 8))
        return samples, self.physical(solution.y[:, -1], total)
