"""Trusted world wrapper: independent prepared geometries, no persistent state."""
import hashlib
import json
import numpy as np
from .baseline import baseline
from .kernel import STRATA, energy_forces, make_instance
from .protocol import CHANNELS, SCALES, NOISE_STD, VERSION, describe, integer, validate_spec


class World:
    name = "molecular_forces"
    version = VERSION
    axis_field = "configuration_ids"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD
    operator_strata = STRATA

    def __init__(self, seed):
        self._seed = integer(seed, "seed", 0, 2**63 - 1)
        self._parameters = make_instance(self._seed)

    def operator_stratum(self):
        return self._parameters["stratum"]

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        return len(self.validate(spec)["configurations"])

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string with at most 256 characters")
        values = []
        for points in spec["configurations"]:
            e, f = energy_forces(points, spec["temperature_k"], self._parameters)
            values.append([e] + f.ravel().tolist())
        values = np.asarray(values)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, spec], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
            values += np.random.default_rng(seed).normal(0., self.noise_std, values.shape)
        return {"axis": spec["configuration_ids"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = integer(panel_seed, "panel_seed", 0, 2**63 - 1)
        count = integer(count, "count", 1, 128)
        if kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions or interventions")
        rng = np.random.default_rng(np.random.SeedSequence([panel_seed, {"development": 71, "conditions": 73, "interventions": 79}[kind]]))
        result = []
        for _ in range(count):
            points_list = []
            for row in range(4):
                # At most64 draws, followed by a fixed legal fallback, bounds work.
                for attempt in range(64):
                    sides = rng.uniform(2.3, 5.2, 3)
                    x, y, z = sides
                    if x + y > z and x + z > y and y + z > x:
                        break
                else:
                    x, y, z = 3., 3.2, 3.4
                px = (x*x + y*y - z*z) / (2*x)
                p = np.asarray([[0., 0., 0.], [x, 0., 0.], [px, np.sqrt(max(0., y*y-px*px)), 0.]])
                p -= p.mean(axis=0)
                q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
                p = p.dot(q)
                points_list.append(p.tolist())
            temperature = 450. if kind == "development" else float(rng.uniform(180., 900.))
            result.append(self.validate({"configurations": points_list, "configuration_ids": list(range(4)), "temperature_k": temperature}))
        return result
