"""Batch adapter for the original, fixed-mechanism microecology laboratory.

Operator-only module. The model sees describe() and noisy run() records only.
The persistent vessel CLI remains available for richer material transfers.
"""
import hashlib
import math

import numpy as np

from .kernel import Mechanism, MicroecologyKernel, X, Y, Z, rng_for


def _number(value, lo, hi, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a number")
    if not lo <= value <= hi or not math.isfinite(value):
        raise ValueError(name + " outside allowed range")
    return float(value)


class World:
    name = "microecology"
    version = "microecology-batch-0.2.0"
    axis_field = "times_h"
    channels = ("A", "B", "C", "nutrient", "peak-01", "peak-02", "peak-03")
    scales = (1., 1., 1., 5., 1., 1., 1.)
    noise_std = (.002, .002, .002, .004, .004, .004, .004)

    def __init__(self, seed):
        if type(seed) is not int or seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        self._seed = seed
        self._kernel = MicroecologyKernel(Mechanism.generate(seed))
        indices = [X, Y, Z]
        rng_for(seed, "channel-permutation").shuffle(indices)
        self._indices = [1, 2, 3, 0] + indices

    def describe(self):
        return {
            "name": self.name, "version": self.version,
            "research_prompt": "Study three unfamiliar microbial strains A, B, C and three anonymous extracellular fractions. Discover quantitative relationships, test competing explanations and identify the scope of your findings.",
            "channels": list(self.channels), "scales": list(self.scales),
            "noise_std": list(self.noise_std),
            "units": "All channels mmol carbon/L; time hours; temperature Celsius.",
            "semantics": [
                "Each experiment starts a fresh closed batch vessel with the same fixed hidden mechanism. No shared clock or vessel inventory in this batch interface.",
                "Strain counts and three anonymous chemical fractions can be measured at all requested times. Fraction labels are consistent inside this world; molecular identities are unknown.",
                "Dynamics are deterministic; measurements have independent additive Gaussian noise clipped at zero. The inert carbon pool is unobserved.",
                "An event at an observation time occurs BEFORE measurement. Depletion selectively removes one fraction without affecting other material. Feed adds nutrient; temperature changes persist.",
                "Zero-inoculum strains stay absent. Initial extracellular fractions are zero. Carbon can leave via depletion and enter via feed."
            ],
            "schema": {
                "initial": {"A": "[0,1]", "B": "[0,1]", "C": "[0,1]", "nutrient": "[0,10]"},
                "temperature_c": "20..40 (default 30)",
                "times_h": "1..32 strictly increasing finite times in [0,72]",
                "events": "0..4 events, sorted by time_h in [0,last observation]; each has exactly one action: deplete={channel: peak-01/02/03, fraction:0..1}, feed:0..3, or temperature_c:20..40"
            },
            "example": {"initial": {"A": .05, "B": .05, "C": .05, "nutrient": 5.},
                        "temperature_c": 30., "times_h": [0., 6., 12., 24., 48.],
                        "events": [{"time_h": 12., "deplete": {"channel": "peak-01", "fraction": .8}}]},
            "cost": "8 + number of times + 2*number of events + ceil(last time / 12)",
            "limitations": "Synthetic carbon-balanced ecology, not calibrated organisms. This adapter does not expose supernatant transfers."
        }

    def validate(self, spec):
        if not isinstance(spec, dict) or not {"initial", "times_h"} <= set(spec) or set(spec) - {"initial", "times_h", "temperature_c", "events"}:
            raise ValueError("expected initial, times_h and optional temperature_c, events")
        initial = spec["initial"]
        if not isinstance(initial, dict) or set(initial) != {"A", "B", "C", "nutrient"}:
            raise ValueError("initial requires A, B, C, nutrient")
        initial = {k: _number(initial[k], 0, 10 if k == "nutrient" else 1, k) for k in ("A", "B", "C", "nutrient")}
        temp = _number(spec.get("temperature_c", 30), 20, 40, "temperature_c")
        times = spec["times_h"]
        if not isinstance(times, list) or not 1 <= len(times) <= 32:
            raise ValueError("times_h requires 1..32 times")
        times = [_number(t, 0, 72, "time") for t in times]
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("times must be strictly increasing")
        events = spec.get("events", [])
        if not isinstance(events, list) or len(events) > 4:
            raise ValueError("events requires at most 4 events")
        canonical = []
        for event in events:
            if not isinstance(event, dict) or "time_h" not in event or len(event) != 2:
                raise ValueError("event needs time_h and one action")
            value = {"time_h": _number(event["time_h"], 0, times[-1], "event time")}
            if "deplete" in event:
                d = event["deplete"]
                if not isinstance(d, dict) or set(d) != {"channel", "fraction"} or d["channel"] not in self.channels[4:]:
                    raise ValueError("invalid depletion")
                value["deplete"] = {"channel": d["channel"], "fraction": _number(d["fraction"], 0, 1, "fraction")}
            elif "feed" in event:
                value["feed"] = _number(event["feed"], 0, 3, "feed")
            elif "temperature_c" in event:
                value["temperature_c"] = _number(event["temperature_c"], 20, 40, "temperature_c")
            else:
                raise ValueError("unknown event")
            canonical.append(value)
        if any(a["time_h"] > b["time_h"] for a, b in zip(canonical, canonical[1:])):
            raise ValueError("events must be sorted by time_h")
        return {"initial": initial, "temperature_c": temp, "times_h": times, "events": canonical}

    def cost(self, spec):
        s = self.validate(spec)
        return 8 + len(s["times_h"]) + 2 * len(s["events"]) + int(math.ceil(s["times_h"][-1] / 12))

    def run(self, spec, *, noise_key=None):
        s = self.validate(spec)
        state = np.zeros(8)
        state[:4] = [s["initial"][k] for k in ("nutrient", "A", "B", "C")]
        temperature, current = s["temperature_c"], 0.
        result, cursor = [], 0
        for target in s["times_h"]:
            while cursor < len(s["events"]) and s["events"][cursor]["time_h"] <= target:
                e = s["events"][cursor]
                state = self._kernel.advance(state, e["time_h"] - current, temperature)
                current = e["time_h"]
                if "deplete" in e:
                    idx = self._indices[self.channels.index(e["deplete"]["channel"])]
                    state[idx] *= 1 - e["deplete"]["fraction"]
                elif "feed" in e:
                    state[0] += e["feed"]
                else:
                    temperature = e["temperature_c"]
                cursor += 1
            state = self._kernel.advance(state, target - current, temperature)
            current = target
            result.append(state[self._indices].copy())
        values = np.asarray(result)
        if noise_key is not None:
            if not isinstance(noise_key, str):
                raise ValueError("noise_key must be string or None")
            seed = int.from_bytes(hashlib.sha256((str(self._seed) + ":" + noise_key).encode()).digest()[:8], "big")
            values = np.maximum(values + np.random.default_rng(seed).normal(size=values.shape) * self.noise_std, 0)
        return {"axis": s["times_h"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        if kind not in ("development", "conditions", "interventions") or type(count) is not int or not 1 <= count <= 64:
            raise ValueError("invalid panel request")
        rng = rng_for(panel_seed, "batch-panel-" + kind)
        panels = []
        for i in range(count):
            spec = {"initial": {"A": rng.uniform(.03, .15), "B": rng.uniform(.03, .12), "C": rng.uniform(.03, .12), "nutrient": rng.uniform(2., 7.)},
                    "temperature_c": rng.uniform(24., 36.), "times_h": [0., 4., 8., 12., 18., 24., 36., 48., 60.], "events": []}
            if kind == "conditions" and i % 3 == 0:
                spec["initial"][("B", "C")[i % 2]] = 0.
            if kind == "interventions":
                time = rng.choice([8., 12., 18., 24.])
                action = i % 3
                event = {"time_h": time}
                if action == 0:
                    event["deplete"] = {"channel": rng.choice(list(self.channels[4:])), "fraction": rng.uniform(.6, 1.)}
                elif action == 1:
                    event["feed"] = rng.uniform(.5, 2.5)
                else:
                    event["temperature_c"] = rng.uniform(22., 38.)
                spec["events"] = [event]
            panels.append(self.validate(spec))
        return panels


def baseline(records, spec):
    """Nearest public experiment, with time interpolation and initial-value correction."""
    def features(s):
        return np.array([s["initial"][k] for k in ("A", "B", "C", "nutrient")] + [s.get("temperature_c", 30.) / 10])
    if not records:
        return [[spec["initial"][k] for k in ("A", "B", "C", "nutrient")] + [0., 0., 0.] for _ in spec["times_h"]]
    item = min(records, key=lambda r: float(np.sum((features(r["spec"]) - features(spec)) ** 2)) + (0 if r["spec"].get("events", []) == spec.get("events", []) else .5))
    obs = item["observation"]
    values = np.asarray(obs["values"])
    return np.array([np.interp(spec["times_h"], obs["axis"], values[:, j]) for j in range(7)]).T.tolist()
