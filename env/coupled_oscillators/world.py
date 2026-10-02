"""Trusted oscillator operator and an explicitly public-data-only baseline.

Do not mount this operator source in a candidate sandbox. Candidates receive the
description, their experiment records, and a frozen prediction interface only.
"""

import hashlib
import math
from itertools import combinations

import numpy as np
from scipy.linalg import expm
from scipy.optimize import lsq_linear


NODES = ("A", "B", "C", "D")
PAIRS = tuple(combinations(range(4), 2))
CHANNELS = tuple("x_" + node for node in NODES) + tuple("v_" + node for node in NODES)
SCALES = (1.0,) * 4 + (2.0,) * 4
NOISE_STD = (0.002,) * 4 + (0.003,) * 4
_MAX_SEED = 2 ** 63 - 1


def _integer(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError("%s must be an integer" % label)
    value = int(value)
    if not lower <= value <= upper:
        raise ValueError("%s must be in [%s, %s]" % (label, lower, upper))
    return value


def _number(value, label, lower, upper):
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise ValueError("%s must be a finite number" % label)
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError("%s must be a finite number" % label) from None
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("%s must be finite and in [%s, %s]" % (label, lower, upper))
    return value


def _vector(value, label, lower, upper):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("%s must contain four numbers in node order A, B, C, D" % label)
    return [_number(x, "%s[%s]" % (label, i), lower, upper) for i, x in enumerate(value)]


def _node(value, label):
    if not isinstance(value, str) or value not in NODES:
        raise ValueError("%s must be A, B, C, or D" % label)
    return value


def _validate(spec):
    """Validate without constructing or consulting any hidden instance."""
    if not isinstance(spec, dict):
        raise ValueError("experiment spec must be an object")
    allowed = {
        "times", "initial_position", "initial_velocity", "mass_add",
        "damping_add", "cut_edges", "clamp", "drive",
    }
    if any(not isinstance(key, str) or key not in allowed for key in spec):
        raise ValueError("unknown experiment field; see the public experiment schema")
    times = spec.get("times")
    if not isinstance(times, (list, tuple)) or not 1 <= len(times) <= 241:
        raise ValueError("times must contain between 1 and 241 times in seconds")
    times = [_number(t, "time", 0.0, 24.0) for t in times]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("times must be strictly increasing")
    out = {
        "times": times,
        "initial_position": _vector(spec.get("initial_position", [0.0] * 4), "initial_position", -1, 1),
        "initial_velocity": _vector(spec.get("initial_velocity", [0.0] * 4), "initial_velocity", -2, 2),
        "mass_add": _vector(spec.get("mass_add", [0.0] * 4), "mass_add", 0, 3),
        "damping_add": _vector(spec.get("damping_add", [0.0] * 4), "damping_add", 0, 2),
    }
    cut_edges = spec.get("cut_edges", [])
    if not isinstance(cut_edges, (list, tuple)) or len(cut_edges) > 6:
        raise ValueError("cut_edges must contain at most six distinct node pairs")
    canonical_edges = []
    for pair in cut_edges:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each cut edge must contain two distinct node names")
        a, b = sorted((_node(pair[0], "cut edge node"), _node(pair[1], "cut edge node")))
        if a == b:
            raise ValueError("a cut edge must connect two distinct nodes")
        if [a, b] in canonical_edges:
            raise ValueError("cut_edges contains a duplicate pair")
        canonical_edges.append([a, b])
    out["cut_edges"] = sorted(canonical_edges)
    clamp = spec.get("clamp", [])
    if not isinstance(clamp, (list, tuple)) or len(clamp) > 4:
        raise ValueError("clamp must be a list of at most four distinct nodes")
    clamp = [_node(node, "clamp node") for node in clamp]
    if len(set(clamp)) != len(clamp):
        raise ValueError("clamp contains a duplicate node")
    out["clamp"] = sorted(clamp)
    for node in clamp:
        i = NODES.index(node)
        if out["initial_position"][i] != 0 or out["initial_velocity"][i] != 0:
            raise ValueError("a clamped node must have zero initial position and velocity")
    drive = spec.get("drive")
    if drive is not None:
        if not isinstance(drive, dict) or set(drive) != {"node", "amplitude", "frequency", "phase"}:
            raise ValueError("drive must be null or contain node, amplitude, frequency, phase")
        drive = {
            "node": _node(drive["node"], "drive.node"),
            "amplitude": _number(drive["amplitude"], "drive.amplitude", -2, 2),
            "frequency": _number(drive["frequency"], "drive.frequency", 0, 2),
            "phase": _number(drive["phase"], "drive.phase", -math.pi, math.pi),
        }
        if drive["node"] in clamp and drive["amplitude"] != 0:
            raise ValueError("nonzero drive cannot target a clamped node")
    out["drive"] = drive
    return out


def _trajectory(spec, grounding, damping, springs):
    """Evaluate a passive linear mechanical model with a bounded 10 by 10 kernel."""
    stiffness = np.diag(grounding).astype(float)
    cuts = set(tuple(pair) for pair in spec["cut_edges"])
    for (i, j), spring in zip(PAIRS, springs):
        if (NODES[i], NODES[j]) not in cuts:
            stiffness[i, i] += spring
            stiffness[j, j] += spring
            stiffness[i, j] -= spring
            stiffness[j, i] -= spring
    mass = 1.0 + np.asarray(spec["mass_add"], dtype=float)
    drag = np.asarray(damping, dtype=float) + spec["damping_add"]
    active = np.asarray([node not in spec["clamp"] for node in NODES], dtype=float)
    # Keeping the full stiffness diagonal makes intact links to clamped nodes
    # act as springs to a fixed anchor. All clamped coordinates remain zero.
    matrix = np.zeros((10, 10), dtype=float)
    matrix[:4, 4:8] = np.diag(active)
    matrix[4:8, :4] = -stiffness * (active / mass)[:, None]
    matrix[4:8, 4:8] = -np.diag(drag * active / mass)
    state = np.zeros(10, dtype=float)
    state[:4] = spec["initial_position"]
    state[4:8] = spec["initial_velocity"]
    drive = spec["drive"]
    if drive is not None:
        i = NODES.index(drive["node"])
        omega = 2 * math.pi * drive["frequency"]
        matrix[4 + i, 8] = drive["amplitude"] * active[i] / mass[i]
        matrix[8, 9], matrix[9, 8] = omega, -omega
        state[8], state[9] = math.sin(drive["phase"]), math.cos(drive["phase"])
    rows = []
    propagators = {}
    previous = 0.0
    for time in spec["times"]:
        delta = time - previous
        if delta:
            # Reuse genuinely equal increments only: no time quantization.
            if delta not in propagators:
                propagators[delta] = expm(matrix * delta)
            state = propagators[delta].dot(state)
        rows.append(state[:8].copy())
        previous = time
    return np.asarray(rows)


class World:
    axis_field = "times"
    name = "coupled_oscillators"
    version = "coupled_oscillators-0.2.0"
    channels = CHANNELS
    scales = SCALES
    noise_std = NOISE_STD

    def __init__(self, seed):
        self._seed = _integer(seed, "seed", 0, _MAX_SEED)
        rng = np.random.default_rng(self._seed)
        self._grounding = rng.uniform(0.5, 2.0, 4)
        self._damping = rng.uniform(0.04, 0.25, 4)
        # A connected graph, with varied topology and 3--6 active pair springs.
        # The generator is an operator detail, never included in describe().
        order = rng.permutation(4)
        edges = set()
        for i in range(1, 4):
            j = int(rng.integers(i))
            edges.add(tuple(sorted((int(order[i]), int(order[j])))))
        remaining = [edge for edge in PAIRS if edge not in edges]
        extra = int(rng.integers(4))
        if extra:
            for index in rng.choice(len(remaining), extra, replace=False):
                edges.add(remaining[int(index)])
        self._springs = np.asarray([
            rng.uniform(0.25, 1.2) if pair in edges else 0.0 for pair in PAIRS
        ])

    def describe(self):
        return {
            "name": self.name,
            "version": self.version,
            "summary": "Four labelled mechanical masses with an unknown connected spring network, grounding springs and viscous drag. Every experiment starts at time zero.",
            "nodes": list(NODES),
            "channels": list(self.channels),
            "units": {"time": "s", "position": "m", "velocity": "m/s", "mass": "kg", "stiffness": "N/m", "damping": "N s/m", "force": "N", "frequency": "Hz", "phase": "rad"},
            "channel_units": ["m"] * 4 + ["m/s"] * 4,
            "scales": list(self.scales),
            "noise_std": list(self.noise_std),
            "noise": "Independent additive Gaussian measurement noise on each channel and time, including time zero and clamped nodes. No clipping and no process noise. Repeated experiments use fresh measurement noise.",
            "physical_family": {
                "force_balance": "(1 + mass_add_i) * d(v_i)/dt = -g_i*x_i - (c_i + damping_add_i)*v_i - sum_j k_ij*(x_i-x_j) + drive_i(t); d(x_i)/dt = v_i.",
                "symmetry": "k_ij = k_ji >= 0; absent links have k_ij = 0. No coupling drag, nonlinear force, delay or unobserved mass.",
                "baseline_mass_kg": [1.0] * 4,
                "unknown_ranges": {"grounding_stiffness_N_per_m": [0.5, 2.0], "intrinsic_drag_N_s_per_m": [0.04, 0.25], "present_pair_stiffness_N_per_m": [0.25, 1.2], "absent_pair_stiffness_N_per_m": 0.0},
                "initial_network": "Connected; the active pairs and coefficients are fixed within an instance and unknown. Labels are sensor/actuator names, not a spatial ordering.",
            },
            "experiment_schema": {
                "required": ["times"],
                "unknown_fields": "Rejected at every level.",
                "times": "1 to 241 finite, strictly increasing times in [0, 24] s. Zero is optional; each output row corresponds to the requested time.",
                "initial_position": "Four numbers in [-1, 1] m, node order A,B,C,D; default all zero.",
                "initial_velocity": "Four numbers in [-2, 2] m/s, node order A,B,C,D; default all zero.",
                "mass_add": "Four added masses in [0, 3] kg; default all zero. Loading changes inertia, preserving springs and intrinsic drag.",
                "damping_add": "Four added ground drag coefficients in [0, 2] N s/m; default all zero.",
                "cut_edges": "List of at most six distinct unordered node pairs, e.g. [[\"A\",\"C\"]]; default []. Cutting an absent link is a no-op. Both force directions of an existing link are removed.",
                "clamp": "Distinct node names; default []. These positions and velocities are fixed at zero. Their initial values must be zero; intact springs to a clamped node remain attached to a fixed anchor.",
                "drive": "Null (default), or exactly {node, amplitude, frequency, phase}: F(t)=amplitude*sin(2*pi*frequency*t+phase) N at the selected node; amplitude in [-2,2], frequency in [0,2] Hz, phase in [-pi,pi]. A zero-frequency, pi/2-phase drive is constant. Nonzero drive on a clamped node is invalid.",
                "control_timing": "All controls apply at time zero and remain fixed for the experiment. Every run is a fresh preparation, with no carryover.",
            },
            "cost": "1 + ceil(last_requested_time/4) + ceil(number_of_rows/32), an integer from 2 to 15.",
            "examples": [
                {"times": [round(i * 0.1, 4) for i in range(81)], "initial_position": [0.6, 0.0, 0.0, 0.0]},
                {"times": [0.0, 0.5, 1.0, 2.0, 4.0], "initial_velocity": [0.0, 0.0, 0.8, 0.0], "cut_edges": [["A", "C"]], "mass_add": [0, 0, 1, 0]},
                {"times": [0.0, 1.0, 3.0, 6.0], "clamp": ["D"], "drive": {"node": "B", "amplitude": 0.5, "frequency": 0.25, "phase": 0.0}},
            ],
            "discovery_guidance": "Excite different masses, use sufficiently dense time series to resolve dynamics, and test predictions under cuts, loading, damping or clamps. A missing response in one experiment does not establish a missing spring.",
        }

    def validate(self, spec):
        return _validate(spec)

    def cost(self, spec):
        spec = self.validate(spec)
        return 1 + int(math.ceil(spec["times"][-1] / 4)) + int(math.ceil(len(spec["times"]) / 32))

    def run(self, spec, *, noise_key=None):
        spec = self.validate(spec)
        if noise_key is not None and (not isinstance(noise_key, str) or len(noise_key) > 256):
            raise ValueError("noise_key must be null or a string of at most 256 characters")
        values = _trajectory(spec, self._grounding, self._damping, self._springs)
        if noise_key is not None:
            try:
                material = (str(self._seed) + "\0" + noise_key).encode("utf-8")
            except UnicodeEncodeError:
                raise ValueError("noise_key must be valid UTF-8 text") from None
            digest = hashlib.sha256(material).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:16], "big"))
            values += rng.normal(0.0, np.asarray(self.noise_std), values.shape)
        if not np.isfinite(values).all():
            raise ValueError("experiment exceeded the finite numerical range")
        return {"axis": spec["times"], "channels": list(self.channels), "values": values.tolist()}

    def panel(self, panel_seed, kind, count=8):
        panel_seed = _integer(panel_seed, "panel_seed", 0, _MAX_SEED)
        count = _integer(count, "count", 1, 64)
        if not isinstance(kind, str) or kind not in ("development", "conditions", "interventions"):
            raise ValueError("panel kind must be development, conditions, or interventions")
        # Independent of the hidden instance. Panel kind uses a stable domain
        # separation so equal seeds do not accidentally share a conditions set.
        digest = hashlib.sha256(("oscillator-panel:" + kind + ":" + str(panel_seed)).encode("ascii")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:16], "big"))
        result = []
        for index in range(count):
            duration = float(rng.uniform(6.0, 18.0))
            size = int(rng.integers(35, 82))
            times = np.linspace(0.0, duration, size)
            if index % 3 == 1:
                times = np.sort(rng.uniform(0.1, duration, size))
            spec = {
                "times": times.tolist(),
                "initial_position": rng.uniform(-0.8, 0.8, 4).tolist(),
                "initial_velocity": rng.uniform(-0.8, 0.8, 4).tolist(),
            }
            # Conditions are always an unmanipulated network. Interventions
            # cover all five control classes; development mixes both regimes.
            manipulate = kind == "interventions" or (kind == "development" and index % 2 == 1)
            if manipulate:
                mode = index % 5 if kind == "interventions" else (index // 2) % 5
                node = int(rng.integers(4))
                if mode == 0:
                    i, j = PAIRS[int(rng.integers(len(PAIRS)))]
                    spec["cut_edges"] = [[NODES[i], NODES[j]]]
                elif mode == 1:
                    spec["mass_add"] = [0.0] * 4
                    spec["mass_add"][node] = float(rng.uniform(0.5, 2.5))
                elif mode == 2:
                    spec["damping_add"] = [0.0] * 4
                    spec["damping_add"][node] = float(rng.uniform(0.3, 1.4))
                elif mode == 3:
                    spec["clamp"] = [NODES[node]]
                    spec["initial_position"][node] = spec["initial_velocity"][node] = 0.0
                else:
                    spec["drive"] = {"node": NODES[node], "amplitude": float(rng.uniform(0.3, 1.1)), "frequency": float(rng.uniform(0.12, 0.65)), "phase": float(rng.uniform(-math.pi, math.pi))}
            result.append(self.validate(spec))
        return result


def _force_integral(spec, start, end, node):
    drive = spec["drive"]
    if drive is None or drive["node"] != NODES[node]:
        return 0.0
    omega = 2 * math.pi * drive["frequency"]
    if omega == 0:
        return drive["amplitude"] * math.sin(drive["phase"]) * (end - start)
    return drive["amplitude"] * (
        math.cos(omega * start + drive["phase"]) - math.cos(omega * end + drive["phase"])
    ) / omega


def _fit_public_coefficients(records):
    """Fit the stated force balance from observations; never accesses World."""
    if not isinstance(records, list) or len(records) > 256:
        raise ValueError("baseline records must be a list of at most 256 observations")
    design, targets = [], []
    # Prior midpoints of the documented coefficient bounds, including absent
    # links at zero. This is a generic dense passive model, not a sampled recipe.
    prior = np.asarray([1.25] * 4 + [0.145] * 4 + [0.6] * 6)
    for record in records:
        try:
            if not isinstance(record, dict):
                continue
            spec = _validate(record["spec"])
            obs = record["observation"]
            if not isinstance(obs, dict) or obs.get("channels") != list(CHANNELS):
                continue
            raw = obs["values"]
            if not isinstance(raw, list) or len(raw) != len(spec["times"]):
                continue
            if any(not isinstance(row, list) or len(row) != 8 for row in raw):
                continue
            raw_axis = obs["axis"]
            if not isinstance(raw_axis, list) or len(raw_axis) != len(spec["times"]):
                continue
            values = np.asarray(raw, dtype=float)
            times = np.asarray(raw_axis, dtype=float)
            if times.shape != (len(spec["times"]),) or not np.array_equal(times, spec["times"]):
                continue
            if not np.isfinite(values).all() or np.max(np.abs(values)) > 1e6:
                continue
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        x, v = values[:, :4], values[:, 4:]
        cuts = set(tuple(pair) for pair in spec["cut_edges"])
        # Integrating the balance avoids differentiating noisy velocity data.
        # Hermite quadrature uses both measured position and velocity. Windows
        # span up to four sample intervals, with bounded overlap.
        for start in range(0, len(times) - 1, 2):
            end = min(start + 4, len(times) - 1)
            dt = np.diff(times[start:end + 1])
            if len(dt) == 0 or np.max(dt) > 0.5 or times[end] - times[start] < 0.05:
                continue
            area = np.sum(
                dt[:, None] * (x[start:end] + x[start + 1:end + 1]) / 2
                + dt[:, None] ** 2 * (v[start:end] - v[start + 1:end + 1]) / 12,
                axis=0,
            )
            delta_x = x[end] - x[start]
            delta_v = v[end] - v[start]
            for i, node in enumerate(NODES):
                if node in spec["clamp"]:
                    continue
                row = np.zeros(14)
                row[i], row[4 + i] = area[i], delta_x[i]
                for p, (a, b) in enumerate(PAIRS):
                    if (NODES[a], NODES[b]) in cuts:
                        continue
                    if i == a:
                        row[8 + p] = area[a] - area[b]
                    elif i == b:
                        row[8 + p] = area[b] - area[a]
                force = _force_integral(spec, times[start], times[end], i)
                target = force - (1 + spec["mass_add"][i]) * delta_v[i] - spec["damping_add"][i] * delta_x[i]
                design.append(row)
                targets.append(target)
    if not design:
        return prior[:4], prior[4:8], prior[8:]
    ridge = 0.01
    matrix = np.vstack([np.asarray(design), ridge * np.eye(14)])
    target = np.concatenate([np.asarray(targets), ridge * prior])
    fitted = lsq_linear(matrix, target, bounds=(
        [0.5] * 4 + [0.04] * 4 + [0.0] * 6,
        [2.0] * 4 + [0.25] * 4 + [1.2] * 6,
    ), tol=1e-9, max_iter=100).x
    return fitted[:4], fitted[4:8], fitted[8:]


def baseline(records, spec):
    """Fit a passive linear model using only public records and stated ranges.

    Records with invalid/misaligned observations are ignored. Up to 256 records
    are accepted. Sparse intervals above 0.5 s are not used for coefficient fits;
    prediction still accepts every legal time grid. No data gives a documented
    midpoint prior. This function never instantiates or accesses a World.
    """
    spec = _validate(spec)
    coefficients = _fit_public_coefficients(records)
    return _trajectory(spec, *coefficients).tolist()
