"""Closed, isothermal-between-events reaction kinetics for the trusted operator.

Only ``World.describe()`` and experiment responses form the agent-facing API.
This source contains the private instance generator and must not be attached to
an agent session. The baseline uses records and public constants only.
"""

import hashlib
import json
import math
import numbers

import numpy as np
from scipy.linalg import expm
from scipy.optimize import nnls


_CHANNELS = ("A", "B", "C", "D")
_GAS_CONSTANT = 8.31446261815324
_REFERENCE_TEMPERATURE = 325.0
_TEMPERATURE_RANGE = (285.0, 365.0)
_RATE_RANGE = (0.006, 0.14)
_ACTIVATION_RANGE = (14000.0, 48000.0)
_MAX_TIMES = 33
_MAX_EVENTS = 4
_MAX_TOTAL = 6.0
_PAIRS = tuple((i, j) for i in range(4) for j in range(4) if i != j)


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


def _concentrations(value, label, maximum, total_lower, total_upper):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("%s must be a four-element list in A, B, C, D order" % label)
    result = [_number(x, label, 0.0, maximum) for x in value]
    total = sum(result)
    if not total_lower <= total <= total_upper:
        raise ValueError("%s total must be in [%g, %g] mM" %
                         (label, total_lower, total_upper))
    return result


def _validate(spec):
    _keys(spec, ("temperature_k", "initial_mM", "times_s"), ("interventions",), "spec")
    temperature = _number(spec["temperature_k"], "temperature_k", *_TEMPERATURE_RANGE)
    initial = _concentrations(spec["initial_mM"], "initial_mM", 2.0, 0.05, 3.0)
    raw_times = spec["times_s"]
    if not isinstance(raw_times, list) or not 2 <= len(raw_times) <= _MAX_TIMES:
        raise ValueError("times_s must be a list of 2 to 33 times")
    times = [_number(t, "times_s", 0.0, 120.0) for t in raw_times]
    if times[0] != 0.0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times_s must start at zero and strictly increase")
    raw_events = spec.get("interventions", [])
    if not isinstance(raw_events, list) or len(raw_events) > _MAX_EVENTS:
        raise ValueError("interventions must be a list of at most four events")
    events = []
    previous_time = 0.0
    total = sum(initial)
    for event in raw_events:
        if not isinstance(event, dict) or event.get("kind") not in ("temperature", "add"):
            raise ValueError("intervention kind must be temperature or add")
        kind = event["kind"]
        payload_key = "temperature_k" if kind == "temperature" else "amounts_mM"
        _keys(event, ("time_s", "kind", payload_key), (), "intervention")
        time = _number(event["time_s"], "intervention time_s", 0.0, times[-1])
        if time <= previous_time:
            raise ValueError("intervention times must strictly increase and be greater than zero")
        previous_time = time
        canonical = {"time_s": time, "kind": kind}
        if kind == "temperature":
            canonical[payload_key] = _number(event[payload_key], payload_key, *_TEMPERATURE_RANGE)
        else:
            amounts = _concentrations(event[payload_key], payload_key, 1.0, 0.000001, 1.5)
            total += sum(amounts)
            if total > _MAX_TOTAL:
                raise ValueError("total concentration including all additions must not exceed 6 mM")
            canonical[payload_key] = amounts
        events.append(canonical)
    return {"temperature_k": temperature, "initial_mM": initial,
            "times_s": times, "interventions": events}


def _stable_seed(*parts):
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:16], "big")


def _advance(state, matrix, duration):
    if duration == 0.0:
        return state
    result = expm(matrix * duration).dot(state)
    if not np.all(np.isfinite(result)) or np.min(result) < -1e-9:
        raise RuntimeError("reaction integration did not produce a valid concentration")
    # Remove only floating-point drift; a generator conserves concentration.
    result = np.maximum(result, 0.0)
    return result * (float(np.sum(state)) / float(np.sum(result)))


def _simulate(spec, generator):
    state = np.asarray(spec["initial_mM"], dtype=float)
    temperature = spec["temperature_k"]
    current = 0.0
    event_index = 0
    events = spec["interventions"]
    matrices = {}

    def at_temperature(value):
        if value not in matrices:
            matrices[value] = generator(value)
        return matrices[value]

    rows = []
    for sample_time in spec["times_s"]:
        while event_index < len(events) and events[event_index]["time_s"] <= sample_time:
            event = events[event_index]
            state = _advance(state, at_temperature(temperature), event["time_s"] - current)
            current = event["time_s"]
            if event["kind"] == "temperature":
                temperature = event["temperature_k"]
            else:
                state = state + np.asarray(event["amounts_mM"], dtype=float)
            event_index += 1
        state = _advance(state, at_temperature(temperature), sample_time - current)
        current = sample_time
        rows.append(state.tolist())
    return rows


class World:
    axis_field = "times_s"
    name = "reaction_kinetics"
    version = "reaction_kinetics-0.2.0"
    channels = _CHANNELS
    scales = (1.0, 1.0, 1.0, 1.0)
    noise_std = (0.002, 0.002, 0.002, 0.002)

    def __init__(self, seed):
        self._seed = _integer(seed, "seed", 0, 2 ** 63 - 1)
        rng = np.random.default_rng(self._seed)
        # Connected sparse reversible graphs include paths, stars and loops.
        order = rng.permutation(4)
        edges = {tuple(sorted((int(order[i]), int(order[rng.integers(i)]))))
                 for i in range(1, 4)}
        remaining = [(i, j) for i in range(4) for j in range(i + 1, 4) if (i, j) not in edges]
        rng.shuffle(remaining)
        edges.update(remaining[:int(rng.integers(0, 3))])
        self._edges = tuple(sorted(edges))
        self._log_weights = rng.uniform(-0.8, 0.8, 4)
        self._enthalpies = rng.uniform(-5000.0, 5000.0, 4)
        self._conductances = np.exp(rng.uniform(np.log(0.016), np.log(0.055), len(edges)))
        self._barriers = rng.uniform(20000.0, 42000.0, len(edges))

    def _generator(self, temperature):
        matrix = np.zeros((4, 4), dtype=float)
        reciprocal_change = 1.0 / temperature - 1.0 / _REFERENCE_TEMPERATURE
        for index, (left, right) in enumerate(self._edges):
            for source, target in ((left, right), (right, left)):
                reference_rate = self._conductances[index] * math.exp(-self._log_weights[source])
                activation = self._barriers[index] - self._enthalpies[source]
                rate = reference_rate * math.exp(-activation / _GAS_CONSTANT * reciprocal_change)
                matrix[target, source] += rate
                matrix[source, source] -= rate
        return matrix

    def describe(self):
        return {
            "name": self.name, "version": self.version,
            "channels": list(self.channels), "scales": list(self.scales),
            "noise_std": list(self.noise_std),
            "units": {"axis": "s", "channels": "mM", "temperature": "K", "scales": "mM"},
            "candidate_family": (
                "Closed, well-mixed four-species batch reactors. Unknown sparse reversible "
                "first-order transfer reactions conserve total concentration and obey detailed "
                "balance. All ordered transfers between different species are candidates. "
                "Each present directed rate follows k(T)=k(325 K)*exp[-E/R*(1/T-1/325 K)], "
                "R=8.31446261815324 J/(mol K). The topology and rates must be inferred."
            ),
            "parameter_ranges": {
                "present_rate_at_325_k_per_s": list(_RATE_RANGE),
                "activation_energy_j_per_mol": list(_ACTIVATION_RANGE),
                "absent_rate_per_s": 0.0,
            },
            "experiment_schema": {
                "required": ["temperature_k", "initial_mM", "times_s"],
                "optional": ["interventions"], "unknown_fields": "rejected",
                "temperature_k": {"type": "number", "range": list(_TEMPERATURE_RANGE), "unit": "K"},
                "initial_mM": {"type": "list", "length": 4, "order": list(self.channels),
                               "each_range": [0.0, 2.0], "total_range": [0.05, 3.0], "unit": "mM"},
                "times_s": {"type": "list", "length_range": [2, _MAX_TIMES],
                            "range": [0.0, 120.0], "first": 0.0, "strictly_increasing": True, "unit": "s"},
                "interventions": {
                    "type": "list", "max_length": _MAX_EVENTS,
                    "time_s": "strictly increasing, greater than zero, at most the final sample time",
                    "temperature": {"time_s": 30.0, "kind": "temperature", "temperature_k": 345.0},
                    "add": {"time_s": 45.0, "kind": "add", "amounts_mM": [0.0, 0.25, 0.0, 0.0]},
                    "amounts_mM": {"length": 4, "order": list(self.channels), "each_range": [0.0, 1.0],
                                   "total_range": [0.000001, 1.5]},
                    "total_mM_after_all_additions_max": _MAX_TOTAL,
                },
            },
            "observation": {
                "axis": "requested times_s", "shape": "[len(times_s), 4]", "channel_order": list(self.channels),
                "measurement_noise": "independent additive Gaussian, standard deviation 0.002 mM per channel; not clipped",
                "process_noise": False,
                "event_timing": "rows at an intervention time are observed after the intervention",
                "addition_semantics": "instantaneous concentration addition at fixed volume; no dilution",
                "temperature_semantics": "instantaneous switch, held until the next temperature event",
                "reset": "each experiment starts from initial_mM with the same hidden mechanism",
            },
            "cost": "1 + ceil(len(times_s)/8) + len(interventions)",
            "examples": [
                {"temperature_k": 325.0, "initial_mM": [1.0, 0.0, 0.0, 0.0],
                 "times_s": [0.0, 1.0, 3.0, 8.0, 20.0, 45.0, 80.0], "interventions": []},
                {"temperature_k": 305.0, "initial_mM": [0.0, 0.6, 0.0, 0.4],
                 "times_s": [0.0, 5.0, 15.0, 30.0, 45.0, 60.0, 90.0],
                 "interventions": [
                     {"time_s": 30.0, "kind": "temperature", "temperature_k": 345.0},
                     {"time_s": 45.0, "kind": "add", "amounts_mM": [0.25, 0.0, 0.0, 0.0]},
                 ]},
            ],
        }

    def validate(self, spec):
        return _validate(spec)

    def cost(self, spec):
        canonical = self.validate(spec)
        return 1 + (len(canonical["times_s"]) + 7) // 8 + len(canonical["interventions"])

    def run(self, spec, *, noise_key=None):
        canonical = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or not 1 <= len(noise_key) <= 256):
            raise ValueError("noise_key must be null or a nonempty string of at most 256 characters")
        values = np.asarray(_simulate(canonical, self._generator))
        if noise_key is not None:
            rng = np.random.default_rng(_stable_seed(self.version, self._seed, noise_key, canonical))
            values = values + rng.normal(0.0, self.noise_std, values.shape)
        return {"axis": canonical["times_s"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = _integer(panel_seed, "panel_seed", 0, 2 ** 63 - 1)
        count = _integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions, or interventions")
        rng = np.random.default_rng(_stable_seed(self.name, panel_seed, kind))
        result = []
        for index in range(count):
            if kind == "development":
                initial = [0.0] * 4
                initial[index % 4] = float(rng.uniform(0.7, 1.5))
                temperature = [305.0, 325.0, 345.0][(index // 4) % 3]
                times = [0.0, 0.5, 1.5, 3.0, 5.0, 8.0, 12.0, 18.0, 27.0, 40.0, 60.0, 90.0, 120.0]
            else:
                initial = (rng.dirichlet(np.ones(4) * 0.8) * rng.uniform(0.5, 1.8)).tolist()
                temperature = float(rng.uniform(305.0, 345.0))
                horizon = float(rng.uniform(70.0, 120.0))
                times = [0.0] + np.geomspace(0.6, horizon, int(rng.integers(8, 16))).tolist()
            events = []
            if kind == "interventions":
                change_time = float(rng.uniform(15.0, 28.0))
                pulse_time = float(rng.uniform(35.0, 50.0))
                new_temperature = float(rng.uniform(285.0, 300.0) if index % 2 else rng.uniform(350.0, 365.0))
                amounts = [0.0] * 4
                amounts[int(rng.integers(4))] = float(rng.uniform(0.2, 0.8))
                events = [{"time_s": change_time, "kind": "temperature", "temperature_k": new_temperature},
                          {"time_s": pulse_time, "kind": "add", "amounts_mM": amounts}]
                # Include event-boundary assays to test the public right-continuous convention.
                times = sorted(times + [change_time, pulse_time])
            result.append(self.validate({"temperature_k": temperature, "initial_mM": initial,
                                         "times_s": times, "interventions": events}))
        return result


def _fit_record_rates(records):
    """Fit nonnegative rates from observed trapezoidal concentration integrals."""
    groups = {}
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    for record in records[-128:]:
        try:
            spec = _validate(record["spec"])
            observation = record["observation"]
            values = np.asarray(observation["values"], dtype=float)
            if (observation.get("channels") != list(_CHANNELS)
                    or observation.get("axis") != spec["times_s"]
                    or values.shape != (len(spec["times_s"]), 4)
                    or not np.all(np.isfinite(values))):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        times = spec["times_s"]
        for row in range(len(times) - 1):
            start, end = times[row:row + 2]
            # Avoid intervals containing a pulse or temperature boundary. A row
            # at a boundary already includes its event, so subsequent intervals
            # remain usable.
            if any(start < event["time_s"] <= end for event in spec["interventions"]):
                continue
            temperature = spec["temperature_k"]
            for event in spec["interventions"]:
                if event["time_s"] <= start and event["kind"] == "temperature":
                    temperature = event["temperature_k"]
            integral = np.maximum((values[row] + values[row + 1]) * (end - start) / 2.0, 0.0)
            design = np.zeros((4, 12))
            for column, (source, target) in enumerate(_PAIRS):
                design[source, column] -= integral[source]
                design[target, column] += integral[source]
            # Late long intervals otherwise dominate sparse early transient data.
            weight = 1.0 / math.sqrt(max(end - start, 0.25))
            group = groups.setdefault(temperature, [[], []])
            group[0].append(design * weight)
            group[1].append((values[row + 1] - values[row]) * weight)
    fits = []
    for temperature, (designs, changes) in sorted(groups.items()):
        if len(designs) < 3:
            continue
        design = np.vstack(designs)
        changes = np.concatenate(changes)
        # Small public-data ridge stabilizes incomplete excitation. It does not
        # encode the hidden graph, instance rates or equilibrium distribution.
        design = np.vstack((design, np.eye(12) * 0.01))
        changes = np.concatenate((changes, np.zeros(12)))
        try:
            rates, _ = nnls(design, changes, maxiter=1200)
        except (RuntimeError, ValueError):
            continue
        fits.append((temperature, rates))
    return fits


def baseline(records, spec):
    """Observation-only first-order fit; no records means no inferred reaction.

    Trapezoidal integration biases coarse-sampling estimates, and nearest-
    temperature selection does not fit activation energies. This intentionally
    modest baseline nevertheless handles additions and switches consistently.
    """
    canonical = _validate(spec)
    fits = _fit_record_rates(records)

    def generator(temperature):
        matrix = np.zeros((4, 4))
        if not fits:
            return matrix
        _, rates = min(fits, key=lambda item: abs(item[0] - temperature))
        # Clamp only to a loose public physical bound, never to instance values.
        maximum = _RATE_RANGE[1] * math.exp(
            -_ACTIVATION_RANGE[1] / _GAS_CONSTANT * min(0.0, 1.0 / temperature - 1.0 / 325.0))
        for rate, (source, target) in zip(np.minimum(rates, maximum), _PAIRS):
            matrix[target, source] += rate
            matrix[source, source] -= rate
        return matrix

    return _simulate(canonical, generator)
