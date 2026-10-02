"""Experimental wrapper; only describe and budgeted noisy readouts are public."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters, STRUCTURES, random_generator
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = "electrical_impedance", VERSION, AXIS_FIELD
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
        frequencies = spec[AXIS_FIELD]
        return 8 + 2*len(frequencies) + int(math.ceil(math.log10(frequencies[-1]/frequencies[0])))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values, _ = self._kernel.spectrum(spec)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, spec], sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values += rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec[AXIS_FIELD], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-"+kind)
        result = []
        for index in range(count):
            low, high = float(rng.uniform(2, 20)), float(rng.uniform(1500, 5000))
            spec = {AXIS_FIELD: np.geomspace(low, high, 13).tolist(), "source_ohm": 500.,
                    "load_ohm": 5000., "amplitude_v": float(rng.uniform(.5, 1.5))}
            if kind == "interventions" or (kind == "development" and index % 2):
                spec["source_ohm"] = float(rng.uniform(100, 2000))
                spec["load_ohm"] = float(rng.uniform(200, 20000))
            result.append(self.validate(spec))
        return result
