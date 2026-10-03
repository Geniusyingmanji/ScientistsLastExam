"""Operator-only deterministic thermal dynamics; no legacy evaluator import."""

import hashlib

import numpy as np
from scipy.linalg import expm

STRATA = ("two_layer", "state_dependent_feedback", "three_layer")


def random_generator(seed, purpose):
    data = (str(int(seed))+":"+purpose).encode("utf-8")
    return np.random.default_rng(int.from_bytes(hashlib.sha256(data).digest()[:16], "big"))


def generate(seed, stratum):
    rng = random_generator(seed, "parameters-v1")
    capacities = [float(rng.uniform(6, 15)), float(rng.uniform(70, 180))]
    exchanges = [float(rng.uniform(.35, 1.2))]
    if stratum == "three_layer":
        capacities.append(float(rng.uniform(300, 450)))
        exchanges.append(float(rng.uniform(1.0, 1.3)))
    return {"capacities": capacities, "exchanges": exchanges,
            "feedback": float(rng.uniform(.8, 2.2)), "forcing_scale": float(rng.uniform(.85, 1.15)),
            "curvature": float(rng.uniform(.04, .10)) if stratum == "state_dependent_feedback" else 0.0}


class Kernel:
    def __init__(self, parameters):
        self.capacities = np.asarray(parameters["capacities"], float)
        self.exchanges = np.asarray(parameters["exchanges"], float)
        self.feedback = float(parameters["feedback"])
        self.forcing_scale = float(parameters["forcing_scale"])
        self.curvature = float(parameters["curvature"])
        n = len(self.capacities)
        # Heat conductance is assembled as a conservative graph Laplacian.
        conductance = np.zeros((n, n))
        for i, value in enumerate(self.exchanges):
            conductance[i, i] += value
            conductance[i+1, i+1] += value
            conductance[i, i+1] -= value
            conductance[i+1, i] -= value
        conductance[0, 0] += self.feedback
        matrix = -conductance/self.capacities[:, None]
        augmented = np.zeros((n+1, n+1))
        augmented[:n, :n] = matrix
        augmented[0, n] = self.forcing_scale/self.capacities[0]
        transition = expm(augmented)
        self.transition, self.response = transition[:n, :n], transition[:n, n]
        self.matrix = matrix

    def radiative(self, state, forcing):
        return self.forcing_scale*forcing-self.feedback*state[0]-self.curvature*state[0]**3

    def derivative(self, state, forcing):
        result = self.matrix @ state
        result[0] += (self.forcing_scale*forcing-self.curvature*state[0]**3)/self.capacities[0]
        return result

    def trajectory(self, spec, substeps=20):
        state = np.zeros(len(self.capacities))
        rows, states = [], []
        selected = set(spec["times_years"])
        h = 1.0/substeps
        for year, forcing in enumerate(spec["forcing_w_m2"], start=1):
            if self.curvature:
                for _ in range(substeps):
                    k1 = self.derivative(state, forcing)
                    k2 = self.derivative(state+.5*h*k1, forcing)
                    k3 = self.derivative(state+.5*h*k2, forcing)
                    k4 = self.derivative(state+h*k3, forcing)
                    state = state+h*(k1+2*k2+2*k3+k4)/6
            else:
                state = self.transition @ state+self.response*forcing
            if year in selected:
                states.append(state.copy())
                rows.append([state[0], self.radiative(state, forcing)])
        values = np.asarray(rows)
        if not np.isfinite(values).all():
            raise ValueError("thermal solver produced nonfinite output")
        return values, np.asarray(states)
