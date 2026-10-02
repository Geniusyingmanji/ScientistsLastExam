"""Experimental pattern world; operator identity never enters describe()."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .kernel import Kernel, Parameters, STRUCTURES, random_generator
from .protocol import CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name = "pattern_formation"
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
        return 8 + len(spec["times"]) + 2*len(spec["initial"]["modes"]) + int(math.ceil(spec["times"][-1]/4))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values, _ = self._kernel.trajectory(spec)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, spec], sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values += rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec["times"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-" + kind)
        specs = []
        for index in range(count):
            length, drive = float(rng.uniform(14, 30)), float(rng.uniform(-.35, .35))
            initial = {"mean": 0., "modes": [{"mode": 3, "amplitude": .08, "phase": 0.},
                                             {"mode": 4, "amplitude": .05, "phase": .4}]}
            if kind == "interventions" or (kind == "development" and index % 2):
                modes = rng.choice(np.arange(1, 9), size=2, replace=False)
                initial = {"mean": float(rng.uniform(-.12, .12)),
                           "modes": [{"mode": int(mode), "amplitude": float(rng.uniform(.03, .12)),
                                      "phase": float(rng.uniform(-np.pi, np.pi))} for mode in modes]}
            horizon = float(rng.choice([30., 45., 60.]))
            times = sorted(set([0., .25, 1., 2., 4., 8., 12., 20., horizon]))
            specs.append(self.validate({"length": length, "drive": drive, "initial": initial, "times": times}))
        return specs
