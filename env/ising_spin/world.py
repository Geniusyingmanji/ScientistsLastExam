"""Trusted finite Ising operator; its sampled model is never candidate-visible."""

import hashlib
import math
from itertools import combinations, product

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


NODES = ("A", "B", "C", "D", "E", "F")
PAIRS = tuple(combinations(range(6), 2))
CHANNELS = tuple("m_" + node for node in NODES) + tuple(
    "c_" + NODES[i] + "_" + NODES[j] for i, j in PAIRS
)
SCALES = (1.0,) * 21
NOISE_STD = (0.003,) * 21
_STATES = np.asarray(list(product((-1.0, 1.0), repeat=6)), dtype=float)
_FEATURES = np.column_stack([_STATES] + [_STATES[:, i] * _STATES[:, j] for i, j in PAIRS])
_STATES.setflags(write=False)
_FEATURES.setflags(write=False)
_MAX_SEED = 2 ** 63 - 1


def _integer(value, label, lower, upper):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError("%s must be an integer" % label)
    value = int(value)
    if not lower <= value <= upper:
        raise ValueError("%s must be in [%s, %s]" % (label, lower, upper))
    return value


def _number(value, label, lower, upper):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError("%s must be a finite number" % label)
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError("%s must be a finite number" % label) from None
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("%s must be finite and in [%s, %s]" % (label, lower, upper))
    return value


def _node(value, label):
    if not isinstance(value, str) or value not in NODES:
        raise ValueError("%s must be A, B, C, D, E, or F" % label)
    return value


def _validate(spec):
    if not isinstance(spec, dict):
        raise ValueError("experiment spec must be an object")
    allowed = {"temperatures", "external_field", "clamp", "suppress_bonds"}
    if any(not isinstance(key, str) or key not in allowed for key in spec):
        raise ValueError("unknown experiment field; see the public experiment schema")
    temperatures = spec.get("temperatures")
    if not isinstance(temperatures, (list, tuple)) or not 1 <= len(temperatures) <= 32:
        raise ValueError("temperatures must contain between 1 and 32 reduced temperatures")
    temperatures = [_number(t, "temperature", 0.35, 6.0) for t in temperatures]
    if any(b <= a for a, b in zip(temperatures, temperatures[1:])):
        raise ValueError("temperatures must be strictly increasing")
    field = spec.get("external_field", [0.0] * 6)
    if not isinstance(field, (list, tuple)) or len(field) != 6:
        raise ValueError("external_field must contain six numbers in node order A,B,C,D,E,F")
    field = [_number(x, "external_field", -2, 2) for x in field]
    clamp = spec.get("clamp", {})
    if not isinstance(clamp, dict) or len(clamp) > 6:
        raise ValueError("clamp must map distinct node names to integer spins -1 or +1")
    canonical_clamp = {}
    for node, value in clamp.items():
        node = _node(node, "clamp node")
        value = _integer(value, "clamp spin", -1, 1)
        if value == 0:
            raise ValueError("clamp spin must be -1 or +1")
        canonical_clamp[node] = value
    suppression = spec.get("suppress_bonds", [])
    if not isinstance(suppression, (list, tuple)) or len(suppression) > 15:
        raise ValueError("suppress_bonds must contain at most 15 distinct bond controls")
    canonical_suppression, seen = [], set()
    for entry in suppression:
        if not isinstance(entry, dict) or set(entry) != {"nodes", "fraction"}:
            raise ValueError("each suppressed bond must contain exactly nodes and fraction")
        pair = entry["nodes"]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("suppressed bond nodes must contain two distinct names")
        pair = tuple(sorted((_node(pair[0], "bond node"), _node(pair[1], "bond node"))))
        if pair[0] == pair[1]:
            raise ValueError("a suppressed bond must connect two distinct nodes")
        if pair in seen:
            raise ValueError("suppress_bonds contains a duplicate pair")
        seen.add(pair)
        fraction = _number(entry["fraction"], "suppression fraction", 0, 1)
        canonical_suppression.append({"nodes": list(pair), "fraction": fraction})
    return {
        "temperatures": temperatures,
        "external_field": field,
        "clamp": dict(sorted(canonical_clamp.items())),
        "suppress_bonds": sorted(canonical_suppression, key=lambda item: item["nodes"]),
    }


def _controls(spec):
    multiplier = np.ones(21)
    for entry in spec["suppress_bonds"]:
        i, j = (NODES.index(node) for node in entry["nodes"])
        multiplier[6 + PAIRS.index((i, j))] = 1 - entry["fraction"]
    allowed = np.ones(64, dtype=bool)
    for node, value in spec["clamp"].items():
        allowed &= _STATES[:, NODES.index(node)] == value
    return multiplier, allowed


def _expectations(spec, coefficients):
    multiplier, allowed = _controls(spec)
    temperatures = np.asarray(spec["temperatures"])
    logits = (_FEATURES.dot(coefficients * multiplier) + _STATES.dot(spec["external_field"]))[None, :] / temperatures[:, None]
    logits[:, ~allowed] = -np.inf
    probabilities = np.exp(logits - logsumexp(logits, axis=1, keepdims=True))
    return probabilities.dot(_FEATURES)


class World:
    name = "ising_spin"
    version = "ising_spin-0.2.0"
    axis_field = "temperatures"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD

    def __init__(self, seed):
        self._seed = _integer(seed, "seed", 0, _MAX_SEED)
        rng = np.random.default_rng(self._seed)
        fields = rng.uniform(-0.35, 0.35, 6)
        order = rng.permutation(6)
        edges = set()
        for i in range(1, 6):
            j = int(rng.integers(i))
            edges.add(tuple(sorted((int(order[i]), int(order[j])))))
        remaining = [pair for pair in PAIRS if pair not in edges]
        extra = int(rng.integers(0, 7))
        if extra:
            edges.update(remaining[int(i)] for i in rng.choice(len(remaining), extra, replace=False))
        coupling = [
            float(rng.choice((-1.0, 1.0)) * rng.uniform(0.2, 1.2)) if pair in edges else 0.0
            for pair in PAIRS
        ]
        self._coefficients = np.concatenate([fields, np.asarray(coupling)])

    def describe(self):
        return {
            "name": self.name,
            "version": self.version,
            "axis_field": self.axis_field,
            "summary": "A finite six-spin equilibrium system with unknown signed pair interactions and local fields. Each requested temperature is an independent equilibrium preparation, not a dynamical cooling trajectory.",
            "nodes": list(NODES),
            "channels": list(self.channels),
            "channel_units": ["dimensionless"] * 21,
            "channel_meanings": "m_i=<s_i> for six spins first; c_i_j=<s_i*s_j> for all 15 lexicographically ordered pairs next. Spins are -1 or +1. Correlations are raw second moments, not connected correlations; connected correlation is c_i_j-m_i*m_j.",
            "scales": list(self.scales),
            "noise_std": list(self.noise_std),
            "noise": "Independent additive Gaussian measurement noise, standard deviation 0.003 per row and channel, including clamped observables. No clipping; noisy measurements can exceed [-1,1]. Equilibrium expectations have no process or Monte Carlo noise.",
            "physical_family": {
                "energy": "H/epsilon = -sum_(i<j) J_ij*(1-suppression_ij)*s_i*s_j - sum_i (h_i+external_field_i)*s_i.",
                "equilibrium": "Probability is proportional to exp(-(H/epsilon)/temperature) over configurations consistent with the clamps. All free spins equilibrate jointly; there is no history dependence or metastability rule.",
                "units": "temperature = k_B*T/epsilon; J, h, external_field are in units of epsilon, with fixed known epsilon. All exposed numerical quantities are reduced/dimensionless.",
                "unknown_ranges": {"local_field": [-0.35, 0.35], "present_coupling_magnitude": [0.2, 1.2], "absent_coupling": 0.0},
                "structure": "Initially connected undirected graph; positive and negative couplings are allowed. Positive J favours alignment, negative J favours opposition. Hidden fields and bonds stay fixed within an instance.",
                "scope": "Pairwise finite equilibrium model only. There are no higher-order interactions, missing spins, unknown temperature scale, or thermodynamic-limit phase transitions.",
            },
            "experiment_schema": {
                "required": ["temperatures"],
                "unknown_fields": "Rejected at every experiment/control level.",
                "temperatures": "1 to 32 finite strictly increasing reduced temperatures in [0.35,6]. Output axis equals this list; each row is a separate equilibrium ensemble.",
                "external_field": "Six additive fields in [-2,2], node order A,B,C,D,E,F; default all zero. The same field applies to every temperature in the experiment.",
                "clamp": "Object mapping node names to integer -1 or +1, e.g. {\"A\":1,\"D\":-1}; default {}. Clamping fixes that spin and retains its interactions with other spins. All six may be clamped. A field on a clamped spin changes only a constant energy and has no effect on expectations.",
                "suppress_bonds": "At most 15 entries, each exactly {\"nodes\":[\"A\",\"B\"],\"fraction\":1.0}; default []. Pairs are unordered and must be distinct. A fraction in [0,1] multiplies that signed coupling by (1-fraction), without changing its sign. Suppressing an absent bond is a no-op.",
                "control_timing": "Controls are static and shared across the requested temperatures. Every row has a freshly equilibrated ensemble; there is no initial-state parameter.",
            },
            "cost": "1 + ceil(number_of_temperatures/4), from 2 to 9 units.",
            "examples": [
                {"temperatures": [0.5, 0.8, 1.2, 2.0, 3.5, 6.0]},
                {"temperatures": [0.7, 1.4, 2.8], "external_field": [0.6, 0, 0, 0, 0, 0]},
                {"temperatures": [0.5, 1.0, 2.0], "clamp": {"B": -1}, "suppress_bonds": [{"nodes": ["A", "C"], "fraction": 0.5}]},
            ],
            "discovery_guidance": "Use temperature and weak-field responses to estimate interactions; test fitted predictions with clamps and bond suppression. Nonzero correlation does not imply a direct bond. Frustrated cycles require interaction evidence. Finite response peaks can occur without a thermodynamic phase transition.",
        }

    def validate(self, spec):
        return _validate(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 1 + int(math.ceil(len(spec["temperatures"]) / 4))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values = _expectations(spec, self._coefficients)
        if noise_key is not None:
            try:
                material = ("ising-spin:" + str(self._seed) + "\0" + noise_key).encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("noise_key must be valid UTF-8 text") from None
            digest = hashlib.sha256(material).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:16], "big"))
            values += rng.normal(0.0, np.asarray(self.noise_std), values.shape)
        return {"axis": spec["temperatures"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = _integer(panel_seed, "panel_seed", 0, _MAX_SEED)
        count = _integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("panel kind must be development, conditions, or interventions")
        digest = hashlib.sha256(("ising-panel:" + kind + ":" + str(panel_seed)).encode("ascii")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:16], "big"))
        panel = []
        for index in range(count):
            low, high = float(rng.uniform(0.4, 0.75)), float(rng.uniform(2.8, 5.8))
            size = int(rng.integers(7, 14))
            temperatures = np.geomspace(low, high, size)
            if index % 2:
                temperatures = np.sort(rng.uniform(low, high, size))
            spec = {"temperatures": temperatures.tolist()}
            manipulate = kind == "interventions" or (kind == "development" and index % 2 == 1)
            if manipulate:
                mode = index % 4 if kind == "interventions" else (index // 2) % 4
                node = int(rng.integers(6))
                if mode == 0:
                    spec["external_field"] = [0.0] * 6
                    spec["external_field"][node] = float(rng.choice((-1, 1)) * rng.uniform(0.2, 1.0))
                elif mode == 1:
                    spec["clamp"] = {NODES[node]: int(rng.choice((-1, 1)))}
                elif mode == 2:
                    i, j = PAIRS[int(rng.integers(15))]
                    spec["suppress_bonds"] = [{"nodes": [NODES[i], NODES[j]], "fraction": float(rng.uniform(0.35, 1.0))}]
                else:
                    spec["external_field"] = rng.uniform(-0.7, 0.7, 6).tolist()
                    spec["clamp"] = {NODES[node]: int(rng.choice((-1, 1)))}
                    i, j = PAIRS[int(rng.integers(15))]
                    spec["suppress_bonds"] = [{"nodes": [NODES[i], NODES[j]], "fraction": 1.0}]
            panel.append(self.validate(spec))
        return panel


def _fit_public_model(records):
    """Bounded inverse-Ising moment fit from public records and public ranges."""
    if not isinstance(records, list) or len(records) > 256:
        raise ValueError("baseline records must be a list of at most 256 observations")
    rows = []
    for record in records:
        try:
            if not isinstance(record, dict):
                continue
            spec = _validate(record["spec"])
            observation = record["observation"]
            if not isinstance(observation, dict) or observation.get("channels") != list(CHANNELS):
                continue
            raw, axis = observation["values"], observation["axis"]
            if not isinstance(raw, list) or len(raw) != len(spec["temperatures"]):
                continue
            if any(not isinstance(row, list) or len(row) != 21 for row in raw):
                continue
            if not isinstance(axis, list) or len(axis) != len(spec["temperatures"]):
                continue
            observed = np.asarray(raw, dtype=float)
            if not np.isfinite(observed).all() or np.max(np.abs(observed)) > 2:
                continue
            if not np.array_equal(np.asarray(axis, dtype=float), spec["temperatures"]):
                continue
            multiplier, allowed = _controls(spec)
            for temperature, row in zip(spec["temperatures"], observed):
                rows.append((temperature, row, multiplier, allowed, spec["external_field"]))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not rows:
        return np.zeros(21)
    # Deterministic, evenly distributed subsampling bounds optimization work
    # even when the history contains 256 sweeps of 32 temperatures each.
    if len(rows) > 64:
        rows = [rows[int(i)] for i in np.linspace(0, len(rows) - 1, 64, dtype=int)]
    temperatures = np.asarray([row[0] for row in rows])[:, None]
    observed = np.asarray([row[1] for row in rows])
    multipliers = np.asarray([row[2] for row in rows])
    allowed = np.asarray([row[3] for row in rows])
    external = np.asarray([row[4] for row in rows]).dot(_STATES.T) / temperatures
    design = multipliers / temperatures
    # Clamped observables that are constants contain measurement noise but no
    # parameter information. Replace only those constants by their known values.
    for index, mask in enumerate(allowed):
        features = _FEATURES[mask]
        constants = np.all(features == features[0], axis=0)
        observed[index, constants] = features[0, constants]
    ridge = 1e-5

    def loss_and_gradient(parameters):
        logits = (design * parameters).dot(_FEATURES.T) + external
        logits[~allowed] = -np.inf
        normalizers = logsumexp(logits, axis=1, keepdims=True)
        probability = np.exp(logits - normalizers)
        model_moments = probability.dot(_FEATURES)
        loss = np.mean(normalizers[:, 0] - np.sum(observed * design * parameters, axis=1))
        loss += 0.5 * ridge * float(parameters.dot(parameters))
        gradient = np.mean((model_moments - observed) * design, axis=0) + ridge * parameters
        return float(loss), gradient

    fit = minimize(
        loss_and_gradient, np.zeros(21), jac=True, method="L-BFGS-B",
        bounds=[(-0.35, 0.35)] * 6 + [(-1.2, 1.2)] * 15,
        options={"maxiter": 120, "maxfun": 180, "ftol": 1e-12, "gtol": 1e-7, "maxls": 12},
    )
    if not np.isfinite(fit.x).all():
        return np.zeros(21)
    return fit.x


def baseline(records, spec):
    """Fit the stated equilibrium family using public observations only.

    At most 256 records are accepted, with at most 64 observed rows used by a
    bounded convex moment fit. Malformed observations are ignored. No usable
    records gives zero fields and couplings, with requested controls respected.
    No World is constructed or accessed and no topology prior is used.
    """
    spec = _validate(spec)
    coefficients = _fit_public_model(records)
    return _expectations(spec, coefficients).tolist()
