"""Batch facade; private instance state is never returned to the candidate."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .kernel import Kernel, STRATA, generate, random_generator
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = "climate_response", VERSION, AXIS_FIELD
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRATA

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed, "seed")
        if _operator_stratum is not None and _operator_stratum not in STRATA:
            raise ValueError("invalid operator stratum")
        self._stratum = _operator_stratum or STRATA[int(random_generator(seed, "stratum-v1").integers(len(STRATA)))]
        self._kernel = Kernel(generate(seed, self._stratum))

    def operator_stratum(self):
        return self._stratum

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 8+len(spec[AXIS_FIELD])+int(math.ceil(len(spec["forcing_w_m2"])/10))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values, _ = self._kernel.trajectory(spec)
        if noise_key is not None:
            payload = json.dumps([VERSION, self._seed, self._stratum, noise_key, spec], sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))
            values += rng.normal(0, self.noise_std, values.shape)
        return {"axis": spec[AXIS_FIELD], "channels": list(CHANNELS), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-"+kind)
        result = []
        for i in range(count):
            years = int(rng.choice([40, 80, 120, 160]))
            amplitude = float(rng.uniform(.5, 7.5))
            if kind == "conditions" or i % 3 == 0:
                forcing = np.linspace(0, amplitude, years) if i % 2 else np.full(years, amplitude)
            elif i % 3 == 1:
                forcing = np.r_[np.full(years//3, amplitude), np.zeros(years-years//3)]
            else:
                forcing = (amplitude/2)*(1+np.sin(2*np.pi*np.arange(years)/float(rng.uniform(8, 45))))
            if kind == "interventions" and i % 2 == 0:
                forcing[:years//5] = float(rng.uniform(-1, 0))
            result.append(self.validate({"forcing_w_m2": forcing.tolist(),
                                         AXIS_FIELD: sorted(set([1, 2, 5]+list(range(10, years+1, 10))+[years]))}))
        return result
