"""Trusted synthetic regulatory network; disclose describe(), not this recipe."""

import hashlib
import json
import math
import numbers

import numpy as np
from scipy.special import expit


_CHANNELS = ("G1", "G2", "G3", "G4")
_STEP_H = 0.04
_MAX_TIMES = 41
_MAX_EVENTS = 4


def _number(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite number" % label)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite number" % label) from None
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError("%s must be finite and in [%g, %g]" % (label, lower, upper))
    return result


def _integer(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ValueError("%s must be an integer" % label)
    result = int(value)
    if not lower <= result <= upper:
        raise ValueError("%s must be in [%d, %d]" % (label, lower, upper))
    return result


def _keys(value, required, optional, label):
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % label)
    if not set(required).issubset(value) or set(value) - set(required) - set(optional):
        raise ValueError("%s has missing or unsupported fields" % label)


def _vector(value, label, lower, upper):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("%s must have four entries in G1, G2, G3, G4 order" % label)
    return [_number(x, label, lower, upper) for x in value]


def _drive(value):
    result = _vector(value, "drive", -3.0, 3.0)
    if sum(x != 0.0 for x in result) > 2:
        raise ValueError("drive may target at most two genes at a time")
    return result


def _validate(spec):
    _keys(spec, ("initial_expression", "times_h"), ("initial_drive", "interventions"), "spec")
    initial = _vector(spec["initial_expression"], "initial_expression", 0.0, 1.0)
    initial_drive = _drive(spec.get("initial_drive", [0.0] * 4))
    raw_times = spec["times_h"]
    if not isinstance(raw_times, list) or not 2 <= len(raw_times) <= _MAX_TIMES:
        raise ValueError("times_h must be a list of 2 to 41 times")
    times = [_number(t, "times_h", 0.0, 24.0) for t in raw_times]
    if times[0] != 0.0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times_h must start at zero and strictly increase")
    raw_events = spec.get("interventions", [])
    if not isinstance(raw_events, list) or len(raw_events) > _MAX_EVENTS:
        raise ValueError("interventions must be a list of at most four events")
    events = []
    previous = 0.0
    for event in raw_events:
        _keys(event, ("time_h", "kind", "drive"), (), "intervention")
        if event["kind"] != "set_drive":
            raise ValueError("intervention kind must be set_drive")
        time = _number(event["time_h"], "intervention time_h", 0.0, times[-1])
        if time <= previous:
            raise ValueError("intervention times must strictly increase and be greater than zero")
        previous = time
        events.append({"time_h": time, "kind": "set_drive", "drive": _drive(event["drive"])})
    return {"initial_expression": initial, "initial_drive": initial_drive,
            "times_h": times, "interventions": events}


def _stable_seed(*parts):
    value = json.dumps(parts, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:16], "big")


def _advance(state, drive, duration, rhs, project=False):
    if duration == 0:
        return state
    steps = int(math.ceil(duration / _STEP_H))
    step = duration / steps
    for _ in range(steps):
        k1 = rhs(state, drive)
        k2 = rhs(state + step * k1 / 2.0, drive)
        k3 = rhs(state + step * k2 / 2.0, drive)
        k4 = rhs(state + step * k3, drive)
        state = state + step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        if project:
            state = np.clip(state, 0.0, 1.0)
    if not np.all(np.isfinite(state)) or (not project and (np.min(state) < -1e-9 or np.max(state) > 1 + 1e-9)):
        raise RuntimeError("gene integration did not produce valid expression")
    return np.clip(state, 0.0, 1.0)


def _simulate(spec, rhs, project=False):
    state = np.asarray(spec["initial_expression"], dtype=float)
    drive = np.asarray(spec["initial_drive"], dtype=float)
    current = 0.0
    event_index = 0
    rows = []
    events = spec["interventions"]
    for time in spec["times_h"]:
        while event_index < len(events) and events[event_index]["time_h"] <= time:
            event = events[event_index]
            state = _advance(state, drive, event["time_h"] - current, rhs, project)
            current = event["time_h"]
            drive = np.asarray(event["drive"], dtype=float)
            event_index += 1
        state = _advance(state, drive, time - current, rhs, project)
        current = time
        rows.append(state.tolist())
    return rows


class World:
    name = "gene_regulation"
    version = "gene_regulation-0.2.0"
    axis_field = "times_h"
    channels = _CHANNELS
    scales = (1.0, 1.0, 1.0, 1.0)
    noise_std = (0.004, 0.004, 0.004, 0.004)

    def __init__(self, seed):
        self._seed = _integer(seed, "seed", 0, 2 ** 63 - 1)
        rng = np.random.default_rng(self._seed)
        a, b, c, d = [int(x) for x in rng.permutation(4)]
        self._motif = int(rng.integers(3))
        self._weights = np.zeros((4, 4))  # Source by target.
        self._biases = rng.uniform(-0.6, 0.6, 4)
        self._decays = rng.uniform(0.25, 0.7, 4)

        def edge(source, target, sign=1.0, low=1.2, high=2.6):
            self._weights[source, target] = sign * rng.uniform(low, high)

        if self._motif == 0:
            # Delayed negative feedback with a downstream assay gene.
            edge(a, b)
            edge(b, c)
            edge(c, a, -1)
            edge(a if rng.random() < 0.5 else c, d, rng.choice([-1.0, 1.0]))
            if rng.random() < 0.5:
                edge(b, d, -1)
            self._decays[c] = rng.uniform(0.15, 0.25)
            self._decays[a] = rng.uniform(0.55, 0.8)
        elif self._motif == 1:
            # A sparse mutual-activation switch drives two downstream genes.
            edge(a, b, 1, 2.4, 3.2)
            edge(b, a, 1, 2.4, 3.2)
            self._biases[[a, b]] = rng.uniform(-0.12, 0.12, 2)
            edge(a, c, rng.choice([-1.0, 1.0]))
            edge(b, d, rng.choice([-1.0, 1.0]))
            if rng.random() < 0.5:
                edge(c, d, -1)
        else:
            # Fast activation and slow repression produce a transient response.
            edge(a, b, 1, 2.0, 3.0)
            edge(a, c, 1, 2.0, 3.0)
            edge(b, c, -1, 2.0, 3.0)
            edge(c, d)
            if rng.random() < 0.5:
                edge(d, a, -1, 0.65, 0.95)
            self._decays[b] = rng.uniform(0.15, 0.22)
            self._decays[c] = rng.uniform(0.65, 0.8)

    def _rhs(self, expression, drive):
        synthesis = expit(self._biases + self._weights.T.dot(2.0 * expression - 1.0) + drive)
        return self._decays * (synthesis - expression)

    def describe(self):
        return {
            "name": self.name, "version": self.version, "axis_field": self.axis_field,
            "channels": list(self.channels), "scales": list(self.scales), "noise_std": list(self.noise_std),
            "units": {"axis": "h", "channels": "normalized expression", "drive": "dimensionless synthesis log-odds"},
            "candidate_family": {
                "equation": "dx_j/dt = gamma_j * (sigmoid(b_j + sum_i W_ij*(2*x_i-1) + u_j) - x_j)",
                "sigmoid": "1/(1+exp(-z))", "weights_orientation": "source i by target j",
                "positive_weight": "activation", "negative_weight": "repression", "self_edges": False,
                "description": "Unknown sparse signed four-gene network. Saturation and feedback can produce threshold responses or delayed transients; these behaviors are instance dependent.",
            },
            "parameter_ranges": {"nonzero_weight_abs": [0.65, 3.2], "bias": [-0.6, 0.6],
                                 "decay_per_h": [0.15, 0.8], "absent_weight": 0.0},
            "experiment_schema": {
                "required": ["initial_expression", "times_h"], "optional": ["initial_drive", "interventions"],
                "unknown_fields": "rejected",
                "initial_expression": {"length": 4, "order": list(self.channels), "each_range": [0.0, 1.0]},
                "initial_drive": {"length": 4, "order": list(self.channels), "each_range": [-3.0, 3.0],
                                  "max_nonzero_entries": 2, "default": [0.0, 0.0, 0.0, 0.0]},
                "times_h": {"length_range": [2, _MAX_TIMES], "range": [0.0, 24.0],
                            "first": 0.0, "strictly_increasing": True},
                "interventions": {"max_length": _MAX_EVENTS,
                                  "time_h": "strictly increasing, greater than zero and no later than the final sample",
                                  "event": {"time_h": 4.0, "kind": "set_drive", "drive": [2.0, 0.0, 0.0, 0.0]},
                                  "drive_constraints": "same four-entry range and sparsity as initial_drive"},
            },
            "observation": {
                "axis": "requested times_h", "shape": "[len(times_h), 4]", "channel_order": list(self.channels),
                "noise": "independent additive Gaussian, standard deviation 0.004 per channel; not clipped",
                "process_noise": False, "clean_expression_range": [0.0, 1.0],
                "drive_semantics": "Each set_drive event replaces the entire drive vector and persists until replaced. Positive values increase synthesis log-odds; negative values decrease them. Drive is not a fold change or expression clamp.",
                "event_timing": "Expression is continuous at an input switch; its derivative uses the new drive after that time.",
                "pulse_semantics": "End a pulse explicitly with set_drive to a zero vector. Untargeted genes can change through regulation.",
                "reset": "Each experiment starts at initial_expression and initial_drive with the same hidden mechanism.",
            },
            "cost": "1 + ceil(len(times_h)/10) + len(interventions)",
            "examples": [
                {"initial_expression": [0.3, 0.3, 0.3, 0.3], "initial_drive": [0.0, -2.0, 0.0, 0.0],
                 "times_h": [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 12.0, 18.0, 24.0], "interventions": []},
                {"initial_expression": [0.4, 0.4, 0.4, 0.4], "initial_drive": [0.0, 0.0, 0.0, 0.0],
                 "times_h": [0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 14.0, 20.0, 24.0],
                 "interventions": [{"time_h": 2.0, "kind": "set_drive", "drive": [2.5, 0.0, 0.0, 0.0]},
                                   {"time_h": 8.0, "kind": "set_drive", "drive": [0.0, 0.0, 0.0, 0.0]}]},
            ],
        }

    def validate(self, spec):
        return _validate(spec)

    def cost(self, spec):
        canonical = self.validate(spec)
        return 1 + (len(canonical["times_h"]) + 9) // 10 + len(canonical["interventions"])

    def run(self, spec, *, noise_key=None):
        canonical = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or not 1 <= len(noise_key) <= 256):
            raise ValueError("noise_key must be null or a nonempty string of at most 256 characters")
        values = np.asarray(_simulate(canonical, self._rhs))
        if noise_key is not None:
            rng = np.random.default_rng(_stable_seed(self.version, self._seed, noise_key, canonical))
            values += rng.normal(0.0, self.noise_std, values.shape)
        return {"axis": canonical["times_h"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = _integer(panel_seed, "panel_seed", 0, 2 ** 63 - 1)
        count = _integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions, or interventions")
        rng = np.random.default_rng(_stable_seed(self.name, panel_seed, kind))
        result = []
        for index in range(count):
            drive = [0.0] * 4
            events = []
            if kind == "development":
                design = index % 16
                initial = [float(rng.uniform(0.3, 0.5))] * 4
                times = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 14.0, 18.0, 24.0]
                if design < 2:
                    initial = [0.2 + 0.6 * design] * 4
                elif design < 10:
                    drive[(design - 2) // 2] = -2.0 if design % 2 == 0 else 2.0
                elif design < 14:
                    pulse = [0.0] * 4
                    pulse[design - 10] = 2.5
                    events = [{"time_h": 2.0, "kind": "set_drive", "drive": pulse},
                              {"time_h": 8.0, "kind": "set_drive", "drive": [0.0] * 4}]
                else:
                    initial = rng.uniform(0.15, 0.85, 4).tolist()
                    selected = rng.choice(4, size=2, replace=False)
                    drive[int(selected[0])] = 1.6
                    drive[int(selected[1])] = -1.6
            else:
                initial = rng.uniform(0.1, 0.9, 4).tolist()
                horizon = float(rng.uniform(16.0, 24.0))
                times = [0.0] + np.geomspace(0.25, horizon, int(rng.integers(10, 17))).tolist()
                if kind == "interventions":
                    on = float(rng.uniform(1.5, 3.5))
                    off = float(rng.uniform(7.0, 10.0))
                    pulse = [0.0] * 4
                    for gene in rng.choice(4, size=1 + index % 2, replace=False):
                        pulse[int(gene)] = float(rng.choice([-1, 1]) * rng.uniform(1.0, 3.0))
                    events = [{"time_h": on, "kind": "set_drive", "drive": pulse},
                              {"time_h": off, "kind": "set_drive", "drive": [0.0] * 4}]
                    times = sorted(times + [on, off, (on + off) / 2])
            result.append(self.validate({"initial_expression": initial, "initial_drive": drive,
                                         "times_h": times, "interventions": events}))
        return result


def _fit_affine(records):
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    designs, changes = [], []
    for record in records[-128:]:
        try:
            spec = _validate(record["spec"])
            observation = record["observation"]
            values = np.asarray(observation["values"], dtype=float)
            if (observation.get("channels") != list(_CHANNELS)
                    or observation.get("axis") != spec["times_h"]
                    or values.shape != (len(spec["times_h"]), 4)
                    or not np.all(np.isfinite(values))):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        for row, (start, end) in enumerate(zip(spec["times_h"], spec["times_h"][1:])):
            if any(start < event["time_h"] < end for event in spec["interventions"]):
                continue
            drive = spec["initial_drive"]
            for event in spec["interventions"]:
                if event["time_h"] <= start:
                    drive = event["drive"]
            duration = end - start
            midpoint = np.clip((values[row] + values[row + 1]) / 2.0, 0.0, 1.0)
            weight = 1.0 / math.sqrt(max(duration, 0.25))
            designs.append(np.concatenate(([1.0], midpoint, drive)) * duration * weight)
            changes.append((values[row + 1] - values[row]) * weight)
    if len(designs) < 6:
        return None
    design = np.vstack((designs, np.eye(9) * 0.05))
    changes = np.vstack((changes, np.zeros((9, 4))))
    coefficients = np.linalg.lstsq(design, changes, rcond=None)[0]
    return np.clip(coefficients, -2.0, 2.0)


def baseline(records, spec):
    """Public-data affine approximation; saturation/feedback fitting is left open."""
    canonical = _validate(spec)
    coefficients = _fit_affine(records)

    def rhs(state, drive):
        if coefficients is None:
            # Midpoint-rate, zero-bias, unregulated public-family prior.
            return 0.475 * (expit(drive) - state)
        return np.concatenate(([1.0], state, drive)).dot(coefficients)

    return _simulate(canonical, rhs, project=True)
