"""Experimental world; operator methods never enter agent context."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters, STRUCTURES, random_generator
from .protocol import CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name = "orbital_dynamics"
    version = VERSION
    axis_field = "times"
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRUCTURES

    def __init__(self, seed):
        self._seed = integer(seed, "seed")
        self._structure = STRUCTURES[int(random_generator(self._seed, "structure").integers(len(STRUCTURES)))]
        self._kernel = Kernel(Parameters.generate(self._seed, self._structure))

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 8 + len(spec["times"]) + 4 * len(spec["impulses"]) + int(math.ceil(spec["times"][-1] / 2))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values, _ = self._kernel.trajectory(spec)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, spec], sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values = values + rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec["times"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-" + kind)
        rows = []
        for index in range(count):
            angle, radius = float(rng.uniform(-np.pi, np.pi)), float(rng.uniform(.85, 1.8))
            radial = np.asarray([math.cos(angle), math.sin(angle)])
            tangent = np.asarray([-radial[1], radial[0]])
            speed, drift = float(rng.uniform(.45, 1.02)), float(rng.uniform(-.15, .15))
            direction = -1 if index % 2 else 1
            horizon = float(rng.choice([6., 8., 10., 12.]))
            spec = {"position": (radius * radial).tolist(), "velocity": (direction * speed * tangent + drift * radial).tolist(),
                    "times": np.linspace(0, horizon, 17).tolist(), "impulses": []}
            if kind == "interventions" or (kind == "development" and index % 4 == 3):
                for fraction in ([.3, .65] if index % 3 == 0 else [.4]):
                    t = fraction * horizon
                    impulse = float(rng.uniform(.12, .28)) * (radial if index % 2 else tangent)
                    if fraction > .5:
                        impulse = -impulse
                    spec["impulses"].append({"time": t, "delta_v": impulse.tolist()})
                    spec["times"].append(t)
                spec["times"] = sorted(set(spec["times"]))
            rows.append(self.validate(spec))
        return rows
