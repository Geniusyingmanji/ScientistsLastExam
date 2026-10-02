"""Private unregistered wrapper; clean path is operator-only."""
import hashlib
import json
import random

from .baseline import baseline
from .generator import STRUCTURES, generate, random_generator
from .kernel import Kernel
from .protocol import AXIS_FIELD, CHANNELS, NOISE_STD, SCALES, VERSION, cost, describe, integer, public_panel, validate_spec


class World:
    name, version, axis_field = "optical_diffraction", VERSION, AXIS_FIELD
    channels, scales, noise_std = tuple(CHANNELS), tuple(SCALES), tuple(NOISE_STD)
    operator_strata = STRUCTURES

    def __init__(self, seed, *, _operator_stratum=None):
        self._seed = integer(seed)
        self._structure = (_operator_stratum if _operator_stratum is not None else random_generator(seed, "family").choice(STRUCTURES))
        if self._structure not in STRUCTURES:
            raise ValueError("invalid operator stratum")
        self._kernel = Kernel(generate(seed, self._structure))

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        return cost(spec)

    def run(self, spec, *, noise_key=None):
        spec = validate_spec(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or text of at most 256 characters")
        values, _ = self._kernel.intensity(spec)
        if noise_key is not None:
            payload = json.dumps([VERSION, self._seed, self._structure, noise_key, spec], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            rng = random.Random(int.from_bytes(hashlib.sha256(payload).digest(), "big"))
            values = [[row[0] + rng.gauss(0., NOISE_STD[0])] for row in values]
        return {"axis": list(spec[AXIS_FIELD]), "channels": list(CHANNELS), "values": values}

    def panel(self, panel_seed, kind, count=8):
        panel_seed, count = integer(panel_seed, "panel_seed"), integer(count, "count", 1, 64)
        if kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        offset = {"development": 0, "conditions": 1, "interventions": 2}[kind]
        result = []
        for index in range(count):
            row = public_panel((panel_seed + index * 3 + offset) % 2**63)[index % 3]
            if kind == "conditions":
                row["contrast_b"] = 1.
            result.append(row)
        return result
