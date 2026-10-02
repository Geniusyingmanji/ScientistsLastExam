"""Experimental world wrapper; operator controls are not candidate actions."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .generator import STRUCTURES, generate, random_generator
from .kernel import Kernel
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = "spin_echo", VERSION, AXIS_FIELD
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRUCTURES

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed, "seed")
        if _operator_stratum is not None and _operator_stratum not in STRUCTURES:
            raise ValueError("invalid operator stratum")
        self._structure = (_operator_stratum if _operator_stratum is not None else
                           STRUCTURES[int(random_generator(seed, "structure").integers(len(STRUCTURES)))])
        self._kernel = Kernel(generate(self._seed, self._structure))

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 8 + len(spec[AXIS_FIELD]) + 3*len(spec["pulses"]) + math.ceil(spec[AXIS_FIELD][-1]/25)

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values, _ = self._kernel.trajectory(spec)
        if noise_key is not None:
            payload = json.dumps([VERSION, self._seed, self._structure, noise_key, spec], sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values = values + rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec[AXIS_FIELD], "channels": list(CHANNELS), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-" + kind)
        output = []
        for index in range(count):
            horizon = float(rng.choice([100, 150, 200, 250]))
            v = rng.normal(size=3)
            v = v / np.linalg.norm(v) * float(rng.uniform(.7, 1))
            spec = {"initial_magnetization": v.tolist(), "detuning_hz": float(rng.uniform(-20, 20)),
                    AXIS_FIELD: np.linspace(0, horizon, 17).tolist(), "pulses": []}
            if kind == "interventions" or (kind == "development" and index % 2):
                for fraction in ([.25, .6] if index % 3 == 0 else [.5]):
                    event = {"time_ms": fraction*horizon, "angle_rad": float(rng.choice([math.pi, math.pi/2, -math.pi/2])),
                             "phase_rad": float(rng.uniform(-math.pi, math.pi))}
                    spec["pulses"].append(event)
                    spec[AXIS_FIELD].append(event["time_ms"])
                spec[AXIS_FIELD] = sorted(set(spec[AXIS_FIELD]))
            output.append(self.validate(spec))
        return output
