"""Experimental ensemble wrapper; clean observations and strata are operator-only."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .generator import STRUCTURES, generate, random_generator
from .kernel import Kernel
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = "population_drift", VERSION, AXIS_FIELD
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRUCTURES

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed, "seed")
        if _operator_stratum is not None and _operator_stratum not in STRUCTURES:
            raise ValueError("invalid operator stratum")
        self._structure = (_operator_stratum if _operator_stratum is not None else
                           STRUCTURES[int(random_generator(self._seed, "structure").integers(len(STRUCTURES)))])
        self._kernel = Kernel(generate(self._seed, self._structure))

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 8+len(spec[AXIS_FIELD])*math.ceil((spec["population_size"]+1)/8)+math.ceil(spec[AXIS_FIELD][-1]/10)

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or text of at most256 characters")
        values, _ = self._kernel.trajectory(spec)
        if noise_key is not None:
            payload = json.dumps([VERSION, self._seed, self._structure, noise_key, spec], sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values = values+rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec[AXIS_FIELD], "channels": list(CHANNELS), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(seed, "panel-"+kind)
        rows = []
        for _ in range(count):
            size = int(rng.choice([8, 12, 16, 24, 32]))
            horizon = float(rng.choice([12, 24, 40, 60]))
            spec = {"population_size": size, "initial_A": int(rng.integers(0, size+1)),
                    AXIS_FIELD: np.linspace(0, horizon, 9).tolist()}
            if kind != "conditions":
                spec.update(selection_bias=float(rng.uniform(-.5, .5)), newborn_flip_probability=float(rng.uniform(0, .1)))
            rows.append(self.validate(spec))
        return rows
