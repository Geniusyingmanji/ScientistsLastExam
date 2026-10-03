"""Trusted whole-history wrapper; every call repeats a fresh laboratory."""
import hashlib
import json
import numpy as np
from .baseline import baseline
from .kernel import STRATA, make_instance, run_history
from .protocol import CHANNELS, SCALES, NOISE_STD, VERSION, describe, integer, reaction, validate_spec


class World:
    name = "catalyst_aging"
    version = VERSION
    axis_field = "event_indices"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD
    operator_strata = STRATA

    def __init__(self, seed):
        self._seed = integer(seed, "seed", 0, 2**63-1)
        self._parameters = make_instance(self._seed)

    def operator_stratum(self):
        return self._parameters["stratum"]

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        return len(self.validate(spec)["events"])

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key)>256):
            raise ValueError("noise_key must be null or a string with at most256 characters")
        values = run_history(spec, self._parameters)
        if noise_key is not None:
            # Key each event readout, not the output array shape: changing the
            # requested subset preserves any shared event's replay noise.
            for row, event_index in enumerate(spec["event_indices"]):
                payload = json.dumps([self._seed, noise_key, spec["events"][:event_index], event_index], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                key = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
                values[row, 0] += np.random.default_rng(key).normal(0., self.noise_std[0])
        return {"axis": spec["event_indices"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = integer(panel_seed, "panel_seed", 0, 2**63-1)
        count = integer(count, "count", 1, 128)
        if kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions or interventions")
        rng = np.random.default_rng(np.random.SeedSequence([panel_seed, {"development": 83, "conditions": 89, "interventions": 97}[kind]]))
        result = []
        for query in range(count):
            events = [{"kind": "blank"}, {"kind": "standard"}]
            t, c, d = float(rng.uniform(450,550)), float(rng.uniform(.2,1.1)), float(rng.uniform(3,14))
            for cycle in range(4):
                if kind == "interventions":
                    temp = float(rng.uniform(440,560))
                    concentration = float(rng.uniform(.1,1.2))
                else:
                    temp, concentration = t, c
                events.append(reaction("A", temp, concentration, d))
                events.append(reaction("B" if cycle % 2 == 0 else "C", t, c, d))
                if cycle in (1,3):
                    events.extend([{"kind": "blank"}, {"kind": "standard"}])
            result.append(self.validate({"events": events, "event_indices": list(range(1,len(events)+1))}))
        return result
