"""Private finite Bloch ensemble with exact piecewise free propagation."""

from dataclasses import dataclass
import math

import numpy as np

from .protocol import number, validate_spec


@dataclass(frozen=True)
class Parameters:
    offsets_hz: tuple
    weights: tuple
    r2_per_s: float

    def __post_init__(self):
        if not isinstance(self.offsets_hz, tuple) or not isinstance(self.weights, tuple) or not 1 <= len(self.offsets_hz) <= 9 or len(self.offsets_hz) != len(self.weights):
            raise ValueError("parameters need matching tuples of 1..9 frequencies and weights")
        offsets = tuple(number(x, -120, 120, "offset frequency") for x in self.offsets_hz)
        weights = tuple(number(x, 0, 1, "weight") for x in self.weights)
        if min(weights) <= 0 or abs(sum(weights) - 1) > 1e-12:
            raise ValueError("weights must be positive and sum to 1 within 1e-12")
        object.__setattr__(self, "offsets_hz", offsets)
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "r2_per_s", number(self.r2_per_s, 0, 40, "transverse decay rate"))


class Kernel:
    MAX_FREE_PROPAGATIONS = 141
    MAX_ROTATIONS = 12

    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise ValueError("expected validated Parameters")
        self.parameters = parameters

    def _free(self, state, dt_ms, detuning_hz):
        duration = dt_ms * .001
        phase = 2*math.pi*(np.asarray(self.parameters.offsets_hz) + detuning_hz)*duration
        decay = math.exp(-self.parameters.r2_per_s*duration)
        transverse = (state[:, 0] + 1j*state[:, 1])*decay*np.exp(1j*phase)
        return np.column_stack((transverse.real, transverse.imag, state[:, 2]))

    @staticmethod
    def _rotate(state, angle, phase):
        axis = np.asarray([math.cos(phase), math.sin(phase), 0.0])
        c, s = math.cos(angle), math.sin(angle)
        # Row states, with active n cross M rather than M cross n.
        return c*state + s*np.cross(axis, state) + (1-c)*(state @ axis)[:, None]*axis

    def trajectory(self, spec):
        spec = validate_spec(spec)
        state = np.tile(spec["initial_magnetization"], (len(self.parameters.weights), 1))
        weights = np.asarray(self.parameters.weights)
        anchor, cursor, free_calls, rotations = 0.0, 0, 0, 0
        rows = []

        def advance(values, elapsed):
            nonlocal free_calls
            if elapsed == 0:
                return values.copy()
            if free_calls >= self.MAX_FREE_PROPAGATIONS:
                raise RuntimeError("spin echo propagation budget exhausted")
            free_calls += 1
            result = self._free(values, elapsed, spec["detuning_hz"])
            if not np.isfinite(result).all():
                raise RuntimeError("spin echo propagation became nonfinite")
            return result

        for target in spec["times_ms"]:
            while cursor < len(spec["pulses"]) and spec["pulses"][cursor]["time_ms"] <= target:
                event = spec["pulses"][cursor]
                state = advance(state, event["time_ms"] - anchor)
                if rotations >= self.MAX_ROTATIONS:
                    raise RuntimeError("spin echo rotation budget exhausted")
                rotations += 1
                state = self._rotate(state, event["angle_rad"], event["phase_rad"])
                if not np.isfinite(state).all():
                    raise RuntimeError("spin echo rotation became nonfinite")
                anchor = event["time_ms"]
                cursor += 1
            # Always evaluate from the latest pulse anchor. A sample never
            # updates that anchor, making shared sample times exactly invariant.
            sample = advance(state, target - anchor)
            mean = weights @ sample
            if target == 0:
                mean = np.asarray(spec["initial_magnetization"], float)
            if not np.isfinite(mean).all():
                raise RuntimeError("spin echo observation became nonfinite")
            rows.append(mean)
        return np.asarray(rows), {"free_propagations": free_calls, "rotations": rotations,
                                  "subensembles": len(weights)}

