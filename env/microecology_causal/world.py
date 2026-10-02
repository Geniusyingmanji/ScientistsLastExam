"""Experimental multi-structure microecology, trusted operator interface."""

import hashlib
import json
import math

import numpy as np

from .baseline import baseline
from .kernel import A, B, C, S, X, Y, Z, Kernel, Parameters, STRUCTURES, random_generator
from .protocol import CHANNELS, NOISE_STD, SCALES, VERSION, describe, integer, validate_spec


class World:
    name = "microecology_causal"
    version = VERSION
    axis_field = "times_h"
    channels, scales, noise_std = CHANNELS, SCALES, NOISE_STD
    operator_strata = STRUCTURES

    def __init__(self, seed):
        self._seed = integer(seed, "seed")
        digest = hashlib.sha256(("microecology-causal-family-v1:%d" % self._seed).encode()).digest()
        self._structure = STRUCTURES[digest[0] % len(STRUCTURES)]
        self._kernel = Kernel(Parameters.generate(self._seed), self._structure)
        self._indices = [A, B, C, S] + random_generator(self._seed, "peak-permutation").permutation([X, Y, Z]).tolist()

    def operator_stratum(self):
        return self._structure

    def describe(self):
        return describe()

    def validate(self, spec):
        return validate_spec(spec)

    def cost(self, spec):
        value = self.validate(spec)
        return 8 + len(value["times_h"]) + 2 * len(value["events"]) + int(math.ceil(value["times_h"][-1] / 12))

    def _trajectory(self, spec):
        state = np.zeros(8)
        state[:4] = [spec["initial"][key] for key in ("nutrient", "A", "B", "C")]
        times = np.asarray(spec["times_h"])
        states = np.empty((len(times), 8))
        imported, exported = np.zeros(len(times)), np.zeros(len(times))
        feed_total, removed_total, temperature, current, cursor = 0.0, 0.0, spec["temperature_c"], 0.0, 0
        boundaries = sorted(set([0.0, times[-1]] + [event["time_h"] for event in spec["events"]]))
        for target in boundaries:
            selected = (times > current) & (times <= target)
            sampled, state = self._kernel.advance(state, target - current, temperature, times[selected] - current)
            states[selected] = sampled
            imported[selected], exported[selected] = feed_total, removed_total
            current = target
            while cursor < len(spec["events"]) and spec["events"][cursor]["time_h"] == target:
                event = spec["events"][cursor]
                if "feed" in event:
                    state[S] += event["feed"]
                    feed_total += event["feed"]
                elif "deplete" in event:
                    index = self._indices[self.channels.index(event["deplete"]["channel"])]
                    removed = state[index] * event["deplete"]["fraction"]
                    state[index] -= removed
                    removed_total += removed
                else:
                    temperature = event["temperature_c"]
                cursor += 1
            exact = times == target
            states[exact] = state
            imported[exact], exported[exact] = feed_total, removed_total
        return states, imported, exported

    def run(self, spec, *, noise_key=None):
        canonical = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        states, _, _ = self._trajectory(canonical)
        values = states[:, self._indices]
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, canonical], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
            values = np.maximum(values + np.random.default_rng(seed).normal(0.0, self.noise_std, values.shape), 0.0)
        return {"axis": canonical["times_h"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = integer(panel_seed, "panel_seed")
        count = integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("invalid panel kind")
        rng = random_generator(panel_seed, "panel-" + kind)
        panel = []
        for index in range(count):
            initial = {key: float(rng.uniform(0.035, 0.15)) for key in ("A", "B", "C")}
            initial["nutrient"] = float(rng.uniform(2.5, 7.0))
            if kind != "interventions" and index % 4 in (1, 2):
                initial[("B", "C")[index % 4 - 1]] = 0.0
            value = {"initial": initial, "temperature_c": float(rng.uniform(24, 36)),
                     "times_h": [0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0, 36.0, 48.0, 72.0], "events": []}
            if kind == "interventions":
                event_time = float(rng.choice([9.0, 12.0, 18.0]))
                if index % 5 < 3:
                    value["events"] = [{"time_h": event_time, "deplete": {"channel": self.channels[4 + index % 5], "fraction": float(rng.uniform(0.65, 1.0))}}]
                elif index % 5 == 3:
                    value["events"] = [{"time_h": event_time, "feed": float(rng.uniform(0.5, 2.5))}]
                else:
                    value["events"] = [{"time_h": event_time, "temperature_c": float(rng.uniform(21, 39))}]
            panel.append(self.validate(value))
        return panel
