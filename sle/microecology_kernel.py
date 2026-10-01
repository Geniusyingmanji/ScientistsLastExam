"""Operator-only carbon-balanced synthetic microcosm; never mount in an agent.

Amounts are represented as carbon-equivalent concentrations (mmol C / L).
This is an invented ecological model, not a calibrated biological organism.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp


STATE_NAMES = ("nutrient", "A", "B", "C", "crossfeed", "inhibitor", "waste", "inert")
S, A, B, C, X, Y, Z, W = range(8)
VERSION = "microecology-0.1.0"


def rng_for(seed, purpose):
    value = hashlib.sha256((str(seed) + ":" + purpose).encode()).digest()
    return random.Random(int.from_bytes(value, "big"))


@dataclass(frozen=True)
class Mechanism:
    uptake_a: float = 0.95
    uptake_b: float = 0.8
    uptake_c: float = 0.65
    half_s: float = 0.3
    half_x: float = 0.12
    half_z: float = 0.1
    inhibition_a: float = 0.32
    inhibition_c: float = 0.18
    death: float = 0.012
    decay_x: float = 0.012
    decay_y: float = 0.025

    @classmethod
    def generate(cls, seed):
        rng = rng_for(seed, "mechanism")
        base = cls()
        return cls(**{name: value * rng.uniform(0.9, 1.1)
                      for name, value in vars(base).items()})


class MicroecologyKernel:
    """Same immutable mechanism across all vessels and confirmation experiments."""

    def __init__(self, mechanism, *, rtol=1e-9, atol=1e-11, method="DOP853"):
        self.mechanism = mechanism
        self.rtol, self.atol, self.method = rtol, atol, method

    def derivative(self, _time, state, temperature_c):
        s, a, b, c, x, y, z, _w = np.maximum(state, 0.0)
        p = self.mechanism
        scale = 2.0 ** ((temperature_c - 30.0) / 10.0)
        qa = scale * p.uptake_a * a * s / (p.half_s + s) / (1 + (z / p.inhibition_a) ** 2)
        qb = scale * p.uptake_b * b * x / (p.half_x + x)
        qc = scale * p.uptake_c * c * z / (p.half_z + z) / (1 + (y / p.inhibition_c) ** 2)
        deaths = scale * p.death * np.array([a, b, c])
        dx, dy = scale * p.decay_x * x, scale * p.decay_y * y
        # A converts substrate to 40% biomass, 35% crossfeed, 25% waste.
        # B converts crossfeed to biomass + inhibitor; C consumes waste.
        # Mortality and abiotic decay enter an inert carbon pool.
        return np.array([
            -qa, 0.4 * qa - deaths[0], 0.45 * qb - deaths[1],
            0.5 * qc - deaths[2], 0.35 * qa - qb - dx,
            0.55 * qb - dy, 0.25 * qa - qc,
            0.5 * qc + float(sum(deaths)) + dx + dy,
        ])

    def advance(self, state, hours, temperature_c):
        if hours == 0:
            return np.array(state, dtype=float, copy=True)
        result = solve_ivp(lambda t, y: self.derivative(t, y, temperature_c),
                           (0.0, hours), np.array(state, dtype=float),
                           method=self.method, rtol=self.rtol, atol=self.atol, max_step=0.5)
        if not result.success:
            raise RuntimeError("integration_failed")
        final = result.y[:, -1]
        if not np.isfinite(final).all() or final.min() < -1e-8:
            raise RuntimeError("nonphysical_state")
        final = np.maximum(final, 0.0)
        if abs(float(final.sum() - np.sum(state))) > 1e-7:
            raise RuntimeError("carbon_balance_failed")
        return final
