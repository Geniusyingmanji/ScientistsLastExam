"""Transient diffusion, advection and heat loss in a one-dimensional material.

This module is trusted operator code, not an agent attachment. Public experiment
semantics are supplied by World.describe(); instance parameters stay private.
"""

import hashlib
import json
import math
import numbers

import numpy as np
from scipy.linalg import eigh_tridiagonal, solve_banded


CHANNELS = ("probe_1_temperature", "probe_2_temperature", "probe_3_temperature")
SCALES = (20.0, 20.0, 20.0)
NOISE_STD = (0.04, 0.04, 0.04)
_FIELDS = frozenset(("times", "probes", "initial_temperature",
                     "boundary_temperatures", "ambient_temperature", "heaters",
                     "flow", "cooling"))


def _number(value, name, lower, upper):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("%s must be a finite number" % name)
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("%s must be a finite number" % name) from None
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("%s must lie in [%g, %g]" % (name, lower, upper))
    return value


def _sequence(value, name, minimum, maximum):
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= maximum:
        raise ValueError("%s must be an array with %d to %d entries" %
                         (name, minimum, maximum))
    return value


def _seed(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise ValueError("%s must be an integer in [0, 2**63 - 1]" % name)
    if not 0 <= int(value) <= 2**63 - 1:
        raise ValueError("%s must be an integer in [0, 2**63 - 1]" % name)
    return int(value)


def _validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != _FIELDS:
        raise ValueError("spec must contain exactly: %s" % ", ".join(sorted(_FIELDS)))
    times = [_number(v, "times entry", 0.0, 30.0)
             for v in _sequence(spec["times"], "times", 1, 25)]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    probes = [_number(v, "probes entry", 0.05, 0.95)
              for v in _sequence(spec["probes"], "probes", 3, 3)]
    if any(b <= a for a, b in zip(probes, probes[1:])):
        raise ValueError("probes must be strictly increasing")
    boundaries = [_number(v, "boundary_temperatures entry", 0.0, 80.0)
                  for v in _sequence(spec["boundary_temperatures"],
                                     "boundary_temperatures", 2, 2)]
    heaters = []
    for heater in _sequence(spec["heaters"], "heaters", 0, 3):
        if not isinstance(heater, dict) or set(heater) != {"position", "power", "width"}:
            raise ValueError("each heater must contain exactly position, power, width")
        heaters.append({"position": _number(heater["position"], "heater position", 0.05, 0.95),
                        "power": _number(heater["power"], "heater power", 0.0, 8.0),
                        "width": _number(heater["width"], "heater width", 0.04, 0.20)})
    if sum(h["power"] for h in heaters) > 12.0:
        raise ValueError("total heater power must be at most 12 K/s")
    return {"times": times, "probes": probes,
            "initial_temperature": _number(spec["initial_temperature"],
                                            "initial_temperature", 0.0, 80.0),
            "boundary_temperatures": boundaries,
            "ambient_temperature": _number(spec["ambient_temperature"],
                                            "ambient_temperature", 0.0, 40.0),
            "heaters": heaters,
            "flow": _number(spec["flow"], "flow", -1.0, 1.0),
            "cooling": _number(spec["cooling"], "cooling", 0.0, 3.0)}


def _example():
    return {"times": [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0],
            "probes": [0.2, 0.5, 0.8], "initial_temperature": 20.0,
            "boundary_temperatures": [20.0, 20.0], "ambient_temperature": 20.0,
            "heaters": [{"position": 0.3, "power": 4.0, "width": 0.08}],
            "flow": 0.0, "cooling": 1.0}


class World:
    name = "heat_transport"
    axis_field = "times"
    version = "heat_transport-0.2.0"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD

    def __init__(self, seed):
        self._seed = _seed(seed, "seed")
        rng = np.random.default_rng(self._seed)
        self._diffusivity_left = float(rng.uniform(0.008, 0.035))
        self._diffusivity_right = self._diffusivity_left
        if rng.random() < 0.65:
            self._diffusivity_right = float(rng.uniform(0.006, 0.055))
        self._interface = float(rng.uniform(0.32, 0.68))
        self._flow_gain = float(rng.uniform(0.025, 0.10))
        self._loss = float(rng.uniform(0.012, 0.075))
        self._intervals = 100

    def describe(self):
        return {
            "name": self.name, "version": self.version,
            "description": "A fresh transient heating experiment on a 1 m material at each call.",
            "channels": list(self.channels), "channel_units": ["degC"] * 3,
            "axis": {"name": "time", "unit": "s", "rows": "requested times in order"},
            "scales": list(self.scales), "noise_std": list(self.noise_std),
            "noise": "Independent additive Gaussian temperature measurement noise; no clipping or process noise.",
            "cost": "One unit per valid experiment; each experiment resets the material.",
            "physics": {
                "equation": "dT/dt = d/dx(D(x) dT/dx) - u dT/dx - cooling*loss*(T-ambient_temperature) + Q(x)",
                "source": "Q(x) = sum(power * exp(-(x-position)^2/(2*width^2)))",
                "boundaries": "The two endpoint temperatures are held fixed from t=0 onward.",
                "initial": "All interior positions start at initial_temperature.",
                "flow": "u = flow * unknown positive flow_gain; positive flow transports toward larger x.",
                "material": "D(x) is either uniform or has two constant regions separated by one internal interface; temperature and diffusive heat flux are continuous there.",
                "unknown_ranges": {"diffusivity_m2_per_s": [0.006, 0.06],
                                   "interface_position_m": [0.3, 0.7],
                                   "flow_gain_m_per_s": [0.02, 0.10],
                                   "loss_per_s": [0.01, 0.08]},
                "numerics": "A convergent spatial discretization with exact propagation in time is used; continuum-model predictions may retain small spatial discretization error."
            },
            "schema": {
                "type": "object", "required": sorted(_FIELDS), "additional_fields": False,
                "times": {"type": "number array", "length": [1, 25], "range": [0.0, 30.0],
                          "unit": "s", "order": "strictly increasing"},
                "probes": {"type": "number array", "length": 3, "range": [0.05, 0.95],
                           "unit": "m", "order": "strictly increasing; one channel per probe"},
                "initial_temperature": {"type": "number", "range": [0.0, 80.0], "unit": "degC"},
                "boundary_temperatures": {"type": "number array", "length": 2,
                                          "range": [0.0, 80.0], "unit": "degC", "order": "x=0, x=1"},
                "ambient_temperature": {"type": "number", "range": [0.0, 40.0], "unit": "degC"},
                "flow": {"type": "number", "range": [-1.0, 1.0], "unit": "dimensionless"},
                "cooling": {"type": "number", "range": [0.0, 3.0], "unit": "dimensionless"},
                "heaters": {"type": "object array", "length": [0, 3], "total_power_max": 12.0,
                            "required": ["position", "power", "width"], "additional_fields": False,
                            "position": {"type": "number", "range": [0.05, 0.95], "unit": "m"},
                            "power": {"type": "number", "range": [0.0, 8.0], "unit": "K/s peak heating rate"},
                            "width": {"type": "number", "range": [0.04, 0.20], "unit": "m Gaussian standard deviation"}},
                "validation": "All numbers must be finite real numbers, not booleans. Arrays are bounded; unknown fields are rejected."
            },
            "examples": [_example(), dict(_example(), heaters=[], flow=-0.75,
                                          initial_temperature=40.0, cooling=2.0)],
            "discovery": "Use spatial and temporal responses, mirrored sources, signed flow, and cooling contrasts to test transport explanations. Identifying a numerical contrast does not establish a unique mechanism."
        }

    def validate(self, spec):
        return _validate_spec(spec)

    def cost(self, spec):
        self.validate(spec)
        return 1

    def _operator(self, spec):
        """Return the positive tridiagonal decay operator and forcing."""
        n = self._intervals
        dx = 1.0 / n
        edges = np.linspace(0.0, 1.0, n + 1)
        x = edges[1:-1]
        fraction_left = np.clip((self._interface - edges[:-1]) / dx, 0.0, 1.0)
        face_d = 1.0 / (fraction_left / self._diffusivity_left +
                        (1.0 - fraction_left) / self._diffusivity_right)
        diffusion = face_d / dx**2
        advection = spec["flow"] * self._flow_gain / (2.0 * dx)
        loss = spec["cooling"] * self._loss
        diagonal = diffusion[:-1] + diffusion[1:] + loss
        left = diffusion[:-1] + advection
        right = diffusion[1:] - advection
        forcing = np.full(n - 1, loss * spec["ambient_temperature"])
        for heater in spec["heaters"]:
            forcing += heater["power"] * np.exp(-0.5 * ((x - heater["position"]) /
                                                       heater["width"])**2)
        forcing[0] += left[0] * spec["boundary_temperatures"][0]
        forcing[-1] += right[-1] * spec["boundary_temperatures"][1]
        return x, diagonal, -left[1:], -right[:-1], forcing

    def _clean(self, spec):
        x, diagonal, lower, upper, forcing = self._operator(spec)
        band = np.zeros((3, len(diagonal)))
        band[0, 1:] = upper
        band[1] = diagonal
        band[2, :-1] = lower
        equilibrium = solve_banded((1, 1), band, forcing, check_finite=False)
        # Positive off-diagonal transport rates allow a diagonal similarity
        # transform to a symmetric tridiagonal matrix, even with signed flow.
        similarity = np.concatenate(([1.0], np.exp(0.5 * np.cumsum(np.log(lower / upper)))))
        eigenvalues, eigenvectors = eigh_tridiagonal(diagonal, -np.sqrt(lower * upper),
                                                    check_finite=False)
        initial = np.full(len(x), spec["initial_temperature"])
        amplitudes = eigenvectors.T.dot((initial - equilibrium) / similarity)
        time_modes = np.exp(-np.outer(spec["times"], eigenvalues)) * amplitudes
        interior = equilibrium + time_modes.dot(eigenvectors.T) * similarity
        # Avoid cancellation from equilibrium decomposition at t=0.
        if spec["times"][0] == 0.0:
            interior[0] = initial
        values = np.asarray([np.interp(spec["probes"], x, row) for row in interior])
        if not np.isfinite(values).all():
            raise RuntimeError("Heat transport numerical solve failed")
        return values

    def run(self, spec, *, noise_key=None):
        canonical = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values = self._clean(canonical)
        if noise_key is not None:
            payload = json.dumps([self._seed, noise_key, canonical], sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            noise_seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")
            rng = np.random.default_rng(noise_seed)
            values += rng.normal(size=values.shape) * np.asarray(self.noise_std)
        return {"axis": canonical["times"], "channels": list(self.channels),
                "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = _seed(panel_seed, "panel_seed")
        if kind not in ("development", "conditions", "interventions"):
            raise ValueError("kind must be development, conditions or interventions")
        if isinstance(count, (bool, np.bool_)) or not isinstance(count, numbers.Integral) or not 1 <= count <= 64:
            raise ValueError("count must be an integer in [1, 64]")
        kind_offset = {"development": 17, "conditions": 29, "interventions": 43}[kind]
        rng = np.random.default_rng(np.random.SeedSequence([panel_seed, kind_offset]))
        result = []
        for index in range(int(count)):
            spec = _example()
            if kind == "conditions":
                spec["times"] = [0.0] + sorted(rng.uniform(0.1, 30.0, 9).tolist())
                spec["probes"] = [float(rng.uniform(0.07, 0.29)), float(rng.uniform(0.38, 0.62)),
                                  float(rng.uniform(0.71, 0.93))]
                spec["initial_temperature"] = float(rng.uniform(10.0, 55.0))
                spec["boundary_temperatures"] = rng.uniform(5.0, 45.0, 2).tolist()
                spec["ambient_temperature"] = float(rng.uniform(10.0, 30.0))
            elif kind == "interventions":
                # Adjacent entries are paired controls and treatments. Their
                # contrast targets source placement, advection or heat loss.
                pair = index // 2
                treatment = index % 2 == 1
                if not treatment:
                    paired = _example()
                    paired["initial_temperature"] = float(rng.uniform(30.0, 50.0))
                    paired["heaters"][0].update(position=float(rng.uniform(0.2, 0.4)),
                                                 power=float(rng.uniform(3.0, 6.0)),
                                                 width=float(rng.uniform(0.065, 0.11)))
                spec = json.loads(json.dumps(paired))
                spec["flow"] = (-0.8 if not treatment else 0.8) if pair % 3 == 0 else 0.0
                spec["cooling"] = (0.0 if not treatment else 2.5) if pair % 3 == 1 else 1.0
                if pair % 3 == 2 and treatment:
                    spec["heaters"][0]["position"] = 1.0 - spec["heaters"][0]["position"]
            else:
                spec["flow"] = float(rng.uniform(-0.75, 0.75))
                spec["cooling"] = float(rng.uniform(0.25, 2.0))
                spec["heaters"] = [{"position": float(rng.uniform(0.15, 0.85)),
                                     "power": float(rng.uniform(1.0, 5.0)),
                                     "width": float(rng.uniform(0.06, 0.13))}]
                spec["initial_temperature"] = float(rng.uniform(15.0, 35.0))
            result.append(self.validate(spec))
        return result


def _features(spec):
    source = np.zeros(11)
    locations = np.linspace(0.0, 1.0, 11)
    for heater in spec["heaters"]:
        source += heater["power"] * np.exp(-0.5 * ((locations - heater["position"]) /
                                                 heater["width"])**2)
    return np.concatenate(([spec["initial_temperature"] / 20.0,
                            spec["boundary_temperatures"][0] / 20.0,
                            spec["boundary_temperatures"][1] / 20.0,
                            spec["ambient_temperature"] / 20.0,
                            spec["flow"], spec["cooling"] / 2.0], source / 4.0))


def baseline(records, spec):
    """Interpolate the three closest public experiments; no parameter fitting."""
    spec = _validate_spec(spec)
    target = _features(spec)
    candidates = []
    if not isinstance(records, (list, tuple)):
        raise ValueError("records must be an array")
    for record in records:
        try:
            previous = _validate_spec(record["spec"])
            observation = record["observation"]
            values = np.asarray(observation["values"], dtype=float)
            axis = np.asarray(observation["axis"], dtype=float)
            if (values.shape != (len(previous["times"]), 3) or
                    axis.shape != (len(previous["times"]),) or
                    not np.isfinite(values).all() or not np.isfinite(axis).all() or
                    observation["channels"] != list(CHANNELS) or
                    not np.array_equal(axis, previous["times"])):
                continue
            distance = float(np.sum((_features(previous) - target)**2))
            candidates.append((distance, previous, values))
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            continue
    if not candidates:
        return np.full((len(spec["times"]), 3), spec["initial_temperature"]).tolist()
    candidates.sort(key=lambda item: item[0])
    candidates = candidates[:3]
    weights = 1.0 / (np.asarray([item[0] for item in candidates]) + 1e-8)
    weights /= weights.sum()
    prediction = np.zeros((len(spec["times"]), 3))
    for weight, (_, previous, values) in zip(weights, candidates):
        positions = [0.0] + previous["probes"] + [1.0]
        temporal = np.column_stack([
            np.interp(spec["times"], previous["times"], values[:, index]) for index in range(3)])
        for row, temperatures in enumerate(temporal):
            extended = [previous["boundary_temperatures"][0]] + temperatures.tolist() + [previous["boundary_temperatures"][1]]
            prediction[row] += weight * np.interp(spec["probes"], positions, extended)
    for row, time in enumerate(spec["times"]):
        if time == 0.0:
            prediction[row] = spec["initial_temperature"]
    return prediction.tolist()
