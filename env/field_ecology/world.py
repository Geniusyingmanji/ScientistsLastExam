"""Batch adapter with independently redrawn ecological panels."""

import hashlib
import json

import numpy as np

from .baseline import baseline
from .kernel import Kernel, STRATA, generate, random_generator
from .protocol import AXIS_FIELD, CHANNELS, METHOD_COST, NOISE_STD, PANEL_SIZE, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = "field_ecology", VERSION, AXIS_FIELD
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRATA
    noise_model = "independent_ecological_panels_bounded_fraction"
    noise_mean_bias_bound = (0.0,0.0,0.0)

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed,"seed")
        if _operator_stratum is not None and _operator_stratum not in STRATA:
            raise ValueError("invalid operator stratum")
        self._stratum = _operator_stratum or STRATA[int(random_generator(seed,"stratum-v1").integers(len(STRATA)))]
        self._kernel = Kernel(generate(seed,self._stratum))

    def operator_stratum(self):
        return self._stratum

    def describe(self):
        return describe()

    def validate(self,spec):
        return validate_spec(spec)

    def cost(self,spec):
        spec = self.validate(spec)
        return 4+len(spec[AXIS_FIELD])*sum(METHOD_COST[v] for v in spec["visits"])

    def run(self,spec,*,noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key,str) or len(noise_key)>256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        psi,detection = self._kernel.probabilities(spec)
        if noise_key is None:
            values = self._kernel.expectations(psi,detection)
        else:
            payload = json.dumps([VERSION,self._seed,self._stratum,noise_key,spec],sort_keys=True,
                                 separators=(",",":"),allow_nan=False).encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16],"big"))
            values = self._kernel.sample(psi,detection,rng,PANEL_SIZE)
        return {"axis":spec[AXIS_FIELD],"channels":list(CHANNELS),"values":values.tolist()}

    def panel(self,panel_seed,kind,count=8):
        panel_seed,count = integer(panel_seed,"panel_seed"),integer(count,"count",1,64)
        if kind not in ("development","conditions","interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed,"panel-"+kind)
        result = []
        for i in range(count):
            h = sorted(rng.uniform(-1.6,1.6,size=7).tolist())
            visits = ["rapid"] if kind == "conditions" else [str(v) for v in rng.choice(["rapid","intensive"],size=1+i%3)]
            result.append(self.validate({AXIS_FIELD:h,"visits":visits}))
        return result
