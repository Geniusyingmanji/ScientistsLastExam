"""Trusted batch wrapper; every run freshly prepares one sample."""
import hashlib
import json
import math
import numpy as np
from .baseline import baseline
from .kernel import Kernel, STRUCTURES, generate, random_generator
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name, version, axis_field = 'phase_equilibria', VERSION, AXIS_FIELD
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRUCTURES

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed, 'seed')
        if _operator_stratum is not None and _operator_stratum not in STRUCTURES:
            raise ValueError('invalid operator stratum')
        self._structure = (_operator_stratum if _operator_stratum is not None else
                           STRUCTURES[int(random_generator(seed, 'structure').integers(len(STRUCTURES)))])
        self._kernel = Kernel(generate(seed, self._structure))

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 8 + math.ceil(len(spec[AXIS_FIELD])/8) + math.ceil(spec['hold_time']/10)

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError('noise_key must be null or a string of at most 256 characters')
        values = self._kernel.spectrum(spec)
        if noise_key is not None:
            payload = json.dumps([VERSION, self._seed, self._structure, noise_key, spec],
                                 sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], 'big'))
            values += rng.normal(0, NOISE_STD, values.shape)
        return {'axis': spec[AXIS_FIELD], 'channels': list(CHANNELS), 'values': values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, 'panel_seed'), integer(count, 'count', 1, 64)
        if not isinstance(kind, str) or kind not in ('development', 'conditions', 'interventions'):
            raise ValueError('invalid panel kind')
        rng = random_generator(panel_seed, 'panel-'+kind)
        result = []
        for i in range(count):
            spec = {'composition': float(rng.uniform(0, 1)), 'hold_time': float(rng.uniform(0, 120)),
                    'preparation': 'quenched' if i % 2 else 'powder_blend',
                    'loading': float(rng.uniform(.3, 1)) if kind == 'interventions' else 1.,
                    AXIS_FIELD: np.linspace(10, 90, 161).tolist()}
            if kind == 'interventions' and i == 0:
                spec['loading'] = 0.
            result.append(self.validate(spec))
        return result
