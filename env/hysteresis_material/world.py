"""Trusted operator kernel. Do not attach this file to discovery agents."""

import hashlib
import json

import numpy as np
from scipy.integrate import solve_ivp

from .baseline import baseline
from .protocol import (CHANNELS, NOISE_STD, RESET_SECONDS, SCALES, VERSION,
                       describe, integer, validate_spec)


class World:
    name = "hysteresis_material"
    version = VERSION
    axis_field = "times"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD
    # Trusted cohort construction only; never included in describe()/observations.
    operator_strata = ("relaxation", "bistable")

    def operator_stratum(self):
        return self._family

    def __init__(self, seed):
        self._seed = integer(seed, "seed", 0, 2**63 - 1)
        # Separate the structural draw from the parameter stream. Nothing in the
        # public schema or panel distribution depends on this private choice.
        digest = hashlib.sha256(("hysteresis-material-family-v1:%d" % self._seed).encode()).digest()
        self._family = "relaxation" if digest[0] % 2 == 0 else "bistable"
        rng = np.random.default_rng(self._seed)
        self._gain = float(rng.uniform(0.85, 1.15))
        self._offset = float(rng.uniform(-0.04, 0.04))
        if self._family == "relaxation":
            self._tau = float(rng.uniform(5.0, 14.0))
            self._coupling = float(rng.uniform(1.0, 1.8))
            self._bias = float(rng.uniform(-0.06, 0.06))
            self._a = 0.0
        else:
            # The mobility-time range overlaps exactly with the other family;
            # fast versus slow hidden parameter bins must not define the class.
            self._tau = float(rng.uniform(5.0, 14.0))
            self._coupling = float(rng.uniform(0.6, 0.9))
            self._bias = float(rng.uniform(-0.025, 0.025))
            self._a = float(rng.uniform(0.75, 1.15))

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        self.validate(spec)
        return 1

    def _rhs(self, state, field):
        if self._family == "relaxation":
            return (np.tanh(self._coupling * field + self._bias) - state) / self._tau
        return (self._a * state - state**3 + self._coupling * field + self._bias) / self._tau

    def _advance(self, initial, duration, start_field, end_field, sample_times):
        """Propagate a single continuous-field segment, including its endpoint."""
        if duration == 0.0:
            return np.full(len(sample_times), initial), float(initial)
        sample_times = np.asarray(sample_times, dtype=float)
        if self._family == "relaxation" and start_field == end_field:
            equilibrium = np.tanh(self._coupling * start_field + self._bias)
            samples = equilibrium + (initial - equilibrium) * np.exp(-sample_times / self._tau)
            final = equilibrium + (initial - equilibrium) * np.exp(-duration / self._tau)
            return samples, float(final)
        slope = (end_field - start_field) / duration

        def derivative(time, state):
            return [self._rhs(state[0], start_field + slope * time)]

        # Dense output separates the integration mesh from the observation grid.
        # LSODA resolves transitions and then takes long steps on quiet dwells.
        solution = solve_ivp(derivative, (0.0, duration), [initial], method="LSODA",
                             rtol=2e-9, atol=2e-11, dense_output=True,
                             max_step=max(0.001, duration / 8.0))
        if not solution.success or solution.nfev > 50000:
            raise RuntimeError("Material response integration failed")
        samples = solution.sol(sample_times)[0] if len(sample_times) else np.empty(0)
        final = float(solution.y[0, -1])
        if not np.isfinite(samples).all() or not np.isfinite(final) or abs(final) > 2.0 + 1e-6:
            raise RuntimeError("Material response integration failed")
        return samples, final

    def _prepared_state(self, spec):
        reset_field = -1.5 if spec["reset"] == "negative" else 1.5
        # The reference state and finite reset duration are identical on every
        # call. This is a fixed history, never an equilibrium-root assignment.
        _, state = self._advance(0.0, RESET_SECONDS, reset_field, reset_field, [])
        for step in spec["preparation"]:
            _, state = self._advance(state, step["duration"], step["field"], step["field"], [])
        return state

    def _clean(self, spec):
        state = self._prepared_state(spec)
        times = np.asarray(spec["times"], dtype=float)
        values = np.empty(len(times), dtype=float)
        values[times == 0.0] = state
        knots = list(spec["protocol"])
        if knots[-1]["time"] < times[-1]:
            knots.append({"time": float(times[-1]), "field": knots[-1]["field"]})
        for left, right in zip(knots, knots[1:]):
            start, end = left["time"], right["time"]
            selected = (times > start) & (times <= end)
            samples, state = self._advance(state, end - start, left["field"], right["field"], times[selected] - start)
            values[selected] = samples
        values = self._gain * values + self._offset
        if not np.isfinite(values).all() or np.any(np.abs(values) > 2.5):
            raise RuntimeError("Material response integration failed")
        return values.reshape(-1, 1)

    def run(self, spec, *, noise_key=None):
        canonical = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string with at most 256 characters")
        values = self._clean(canonical)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, canonical], sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
            values = values + np.random.default_rng(seed).normal(0.0, self.noise_std, values.shape)
        return {"axis": canonical["times"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = integer(panel_seed, "panel_seed", 0, 2**63 - 1)
        count = integer(count, "count", 1, 128)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions or interventions")
        salt = {"development": 113, "conditions": 277, "interventions": 401}[kind]
        rng = np.random.default_rng(np.random.SeedSequence([panel_seed, salt]))
        result = []
        for index in range(count):
            reset = "negative" if index % 2 == 0 else "positive"
            sign = -1.0 if reset == "negative" else 1.0
            preparation = []
            mode = index % 4
            if kind == "interventions":
                # Minor loops and interrupted ramps transfer preparation/history.
                amplitude = float(rng.uniform(0.85, 1.45))
                leg = float(np.exp(rng.uniform(np.log(8.0), np.log(180.0))))
                reversal = float(rng.uniform(-0.25, 0.5)) * sign
                dwell = float(rng.uniform(20.0, 100.0))
                if mode % 2:
                    preparation = [{"field": -sign * amplitude, "duration": float(rng.uniform(15.0, 70.0))}]
                knots = [(0.0, sign * amplitude), (leg, -sign * amplitude),
                         (1.5 * leg, reversal), (1.5 * leg + dwell, reversal),
                         (2.0 * leg + dwell, -sign * amplitude), (3.0 * leg + dwell, 0.0)]
            elif mode in (0, 1):
                amplitude = float(rng.uniform(0.85, 1.4))
                leg = float(rng.uniform(8.0, 22.0) if mode == 0 else rng.uniform(220.0, 420.0))
                knots = [(0.0, sign * amplitude), (leg, -sign * amplitude), (2.0 * leg, sign * amplitude)]
            else:
                field = float(rng.uniform(-0.2, 0.2))
                preparation = [{"field": -sign * float(rng.uniform(1.0, 1.5)), "duration": float(rng.uniform(30.0, 90.0))}]
                horizon = float(rng.uniform(140.0, 260.0))
                if mode == 2:
                    knots = [(0.0, field), (horizon, field)]
                else:
                    turn = float(rng.uniform(10.0, 35.0))
                    knots = [(0.0, -sign), (turn, field), (horizon, field)]
            horizon = knots[-1][0]
            # Include knots as well as a regular grid without exceeding row cap.
            times = sorted(set(np.linspace(0.0, horizon, 25).tolist() + [k[0] for k in knots]))
            result.append(self.validate({"reset": reset, "preparation": preparation,
                                         "protocol": [{"time": t, "field": h} for t, h in knots],
                                         "times": times}))
        return result
