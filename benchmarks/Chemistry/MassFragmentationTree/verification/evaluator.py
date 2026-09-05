"""Deterministic multi-energy MS/MS fragmentation-tree oracle.

An unknown protonated molecule fragments along a hidden tree of neutral losses. The
candidate chooses collision energies (and optional high-resolution zooms), receives
deterministic spectra, and must recover the fragmentation tree -- or refuse when the
measurement cannot support one (no surviving molecular ion, or a co-isolated isobar).
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"mass_noise_da": 0.004, "intensity_noise": 0.06, "decoy_range": (1, 3)},
    2: {"mass_noise_da": 0.007, "intensity_noise": 0.09, "decoy_range": (2, 5)},
    3: {"mass_noise_da": 0.012, "intensity_noise": 0.12, "decoy_range": (3, 6)},
}

ELEMENT_MASSES = {
    "H": 1.00782503223,
    "C": 12.0,
    "N": 14.00307400443,
    "O": 15.99491461957,
}
PROTON_MASS = 1.00727646662

LOSS_LIBRARY = {
    "H2O": (0, 2, 0, 1),
    "NH3": (0, 3, 1, 0),
    "CH4": (1, 4, 0, 0),
    "CO": (1, 0, 0, 1),
    "C2H2": (2, 2, 0, 0),
    "HCN": (1, 1, 1, 0),
    "C2H4": (2, 4, 0, 0),
    "CH2O": (1, 2, 0, 1),
    "C3H6": (3, 6, 0, 0),
    "CH3CN": (2, 3, 1, 0),
    "CO2": (1, 0, 0, 2),
    "C3H4": (3, 4, 0, 0),
}

FORMULA_RANGES = {"C": (0, 28), "H": (0, 58), "N": (0, 3), "O": (0, 6)}
MASS_TOLERANCE_DA = 0.015
ENERGY_BOUNDS = (10.0, 60.0)
ACQUIRE_COST = 1
ZOOM_COST = 2
BUDGET_UNITS = 8
MIN_RELATIVE_INTENSITY = 0.005
MIN_FRAGMENT_NEUTRAL_MASS = 27.0
ZOOM_MIN_WIDTH_DA = 0.1
ZOOM_MAX_WIDTH_DA = 3.0

_BASE_DEVELOPMENT_SPECS = (
    (51011, "supported"), (51017, "supported"), (51023, "supported"),
    (51029, "supported"), (51031, "supported"),
    (51037, "in_source"), (51041, "coisolate"),
)
HELDOUT_SPECS = (
    (61007, "supported"), (61013, "supported"), (61019, "supported"),
    (61023, "in_source"), (61029, "coisolate"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _formula_mass(formula):
    carbon, hydrogen, nitrogen, oxygen = formula
    return (carbon * ELEMENT_MASSES["C"] + hydrogen * ELEMENT_MASSES["H"]
            + nitrogen * ELEMENT_MASSES["N"] + oxygen * ELEMENT_MASSES["O"])


def problem_statement(precursor_mz):
    """The public measurement contract. Every key is documented in Task.md."""
    return {
        "precursor_mz": float(precursor_mz),
        "loss_library": {
            name: {"formula": "C%dH%dN%dO%d" % f, "neutral_mass": round(_formula_mass(f), 6)}
            for name, f in LOSS_LIBRARY.items()
        },
        "element_mass_table": dict(ELEMENT_MASSES),
        "proton_mass": PROTON_MASS,
        "fragment_formula_ranges": dict(FORMULA_RANGES),
        "mass_tolerance_da": MASS_TOLERANCE_DA,
        "energy_bounds": list(ENERGY_BOUNDS),
        "acquire_cost": ACQUIRE_COST,
        "zoom_cost": ZOOM_COST,
        "budget_units": BUDGET_UNITS,
        "min_relative_intensity": MIN_RELATIVE_INTENSITY,
        "background_note": (
            "spectra may contain a few low-intensity background peaks that do not belong "
            "to the analyte; background peaks keep a nearly flat intensity across energies"
        ),
        "zoom_note": (
            "a zoom reports monoisotopic peaks inside the window with their M+1/M isotope "
            "ratio; the ratio estimates the carbon count of the ion"
        ),
    }


def _plausible_formula(formula):
    carbon, hydrogen, nitrogen, oxygen = formula
    if min(formula) < 0:
        return False
    if carbon == 0:
        return hydrogen + nitrogen + oxygen > 0 and hydrogen <= 4
    dbe = carbon - hydrogen / 2.0 + nitrogen / 2.0 + 1.0
    return 0.0 <= dbe <= 13.0 and hydrogen <= 2 * carbon + 2 + nitrogen


def _sample_molecule(rng):
    for _ in range(512):
        carbon = int(rng.integers(12, 29))
        nitrogen = int(rng.integers(0, 4))
        oxygen = int(rng.integers(0, 7))
        dbe = float(rng.uniform(1.5, 11.0))
        hydrogen = int(round(2 * carbon + 2 + nitrogen - 2 * dbe))
        formula = (carbon, hydrogen, nitrogen, oxygen)
        if not _plausible_formula(formula):
            continue
        if 160.0 <= _formula_mass(formula) <= 460.0:
            return formula
    return (16, 22, 2, 4)


def _subtract(parent, loss):
    child = tuple(p - l for p, l in zip(parent, loss))
    if min(child) < 0 or not _plausible_formula(child):
        return None
    if _formula_mass(child) < MIN_FRAGMENT_NEUTRAL_MASS:
        return None
    return child


def _build_tree(rng, size_range=(9, 16)):
    root = _sample_molecule(rng)
    nodes = [root]
    edges = []
    target_size = int(rng.integers(*size_range))
    attempts = 0
    while len(nodes) < target_size and attempts < 600:
        attempts += 1
        parent = int(rng.integers(0, len(nodes)))
        depth = 0
        walk = parent
        while walk != 0:
            walk = next(e[0] for e in edges if e[1] == walk)
            depth += 1
        if depth >= 4:
            continue
        loss_name = list(LOSS_LIBRARY)[int(rng.integers(0, len(LOSS_LIBRARY)))]
        child = _subtract(nodes[parent], LOSS_LIBRARY[loss_name])
        if child is None or child in nodes:
            continue
        lability = float(rng.uniform(0.05, 0.95))
        nodes.append(child)
        edges.append((parent, len(nodes) - 1, loss_name, lability))
    return nodes, edges


def _break_fraction(lability, energy):
    midpoint = 14.0 + 46.0 * lability
    return 1.0 / (1.0 + math.exp(-(energy - midpoint) / 3.5))


def _abundances(nodes, edges, energy, root_alive=True):
    """Multiplicative survival cascade: each edge breaks an independent fraction."""
    children = {i: [] for i in range(len(nodes))}
    for parent, child, _name, _lab in edges:
        children[parent].append(child)
    abundance = np.zeros(len(nodes))
    abundance[0] = 1.0
    order = sorted(range(len(nodes)), key=lambda i: _root_distance(i, children))
    for node in order:
        base = abundance[node]
        retained = base
        for child in children[node]:
            lability = next(e[3] for e in edges if e[1] == child and e[0] == node)
            share = base * _break_fraction(lability, energy)
            abundance[child] = share
            retained -= share
        abundance[node] = max(retained, 0.0)
    if not root_alive:
        abundance[0] = 0.0
    return abundance


def _root_distance(node, children):
    distance = 0
    walk = node
    while walk != 0:
        walk = next(parent for parent, child in children.items() if walk in child)
        distance += 1
    return distance


_CONTAMINANT_DELTAS = (
    (-1, -1, 1, 0),   # -CH+N,  +0.9948 Da
    (1, 1, -1, 0),    # +CH-N,  -0.9948 Da
    (-1, -3, 0, 1),   # -CH3+O, +0.9717 Da
    (1, 3, 0, -1),    # +CH3-O, -0.9717 Da
)


def _contaminant_formula(rng, base_formula):
    """A second plausible formula about one dalton away with a different carbon count.

    Small CHNO composition changes either leave the mass within ~0.04 Da (isobaric
    degeneracy, indistinguishable) or move it by about one dalton. Only the latter is
    a separable co-isolate, and every such delta here shifts the carbon count by one
    so the M+1 isotope ratio can tell the two precursor ions apart.
    """
    order = list(range(len(_CONTAMINANT_DELTAS)))
    rng.shuffle(order)
    for index in order:
        delta = _CONTAMINANT_DELTAS[index]
        candidate = tuple(b + d for b, d in zip(base_formula, delta))
        if not _plausible_formula(candidate):
            continue
        if not 160.0 <= _formula_mass(candidate) <= 460.0:
            continue
        return candidate
    return None


def _world(spec):
    seed, kind = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    nodes, edges = _build_tree(rng)
    contaminant = None
    if kind == "coisolate":
        contaminant = _contaminant_formula(rng, nodes[0])
        # Re-draw so co-isolate worlds always carry a genuine second tree.
        while contaminant is None:
            nodes, edges = _build_tree(rng)
            contaminant = _contaminant_formula(rng, nodes[0])
    decoy_count = int(rng.integers(*profile["decoy_range"]))
    decoys = []
    precursor_mz = _formula_mass(nodes[0]) + PROTON_MASS
    for _ in range(decoy_count):
        decoy_mz = float(rng.uniform(70.0, precursor_mz * 1.05))
        decoy_intensity = float(rng.uniform(0.4, 2.2))
        decoys.append((decoy_mz, decoy_intensity))
    world = {
        "seed": int(seed), "kind": kind, "nodes": nodes, "edges": edges,
        "contaminant": contaminant, "decoys": decoys,
        "noise": profile["mass_noise_da"], "intensity_noise": profile["intensity_noise"],
    }
    if contaminant is not None:
        crng = np.random.default_rng(int(seed) + 997)
        world["contaminant_tree"] = _build_contaminant_tree(crng, contaminant)
    else:
        world["contaminant_tree"] = None
    return world


def _build_contaminant_tree(rng, root_formula):
    nodes = [root_formula]
    edges = []
    target = int(rng.integers(6, 11))
    attempts = 0
    while len(nodes) < target and attempts < 400:
        attempts += 1
        parent = int(rng.integers(0, len(nodes)))
        depth = 0
        walk = parent
        while walk != 0:
            walk = next(e[0] for e in edges if e[1] == walk)
            depth += 1
        if depth >= 4:
            continue
        loss_name = list(LOSS_LIBRARY)[int(rng.integers(0, len(LOSS_LIBRARY)))]
        child = _subtract(nodes[parent], LOSS_LIBRARY[loss_name])
        if child is None or child in nodes:
            continue
        lability = float(rng.uniform(0.05, 0.95))
        nodes.append(child)
        edges.append((parent, len(nodes) - 1, loss_name, lability))
    return nodes, edges


def _tree_peak_rows(world, energy, tree=None, root_alive=True):
    nodes, edges = tree if tree is not None else (world["nodes"], world["edges"])
    abundance = _abundances(nodes, edges, energy, root_alive=root_alive)
    rows = []
    top = float(np.max(abundance)) or 1.0
    for index, value in enumerate(abundance):
        relative = value / top
        if relative < MIN_RELATIVE_INTENSITY:
            continue
        mz = _formula_mass(nodes[index]) + PROTON_MASS
        rows.append((mz, relative * 100.0))
    return rows


def _call_rng(world, payload, count):
    digest = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
    return np.random.default_rng(world["seed"] + digest + 1009 * count)


class _Instrument:
    """Charged interface: energy scans and high-resolution zooms."""

    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def _charge(self, cost):
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("measurement budget exceeded")

    def acquire(self, collision_energy):
        try:
            energy = float(collision_energy)
            if not math.isfinite(energy) or not ENERGY_BOUNDS[0] <= energy <= ENERGY_BOUNDS[1]:
                self.violated = True
                raise ValueError("collision energy outside allowed bounds")
            self._charge(ACQUIRE_COST)
            self.used += ACQUIRE_COST
            self.calls += 1
            rng = _call_rng(self.world,
                            ("acquire %.6f" % energy).encode(), self.calls)
            peaks = []
            for mz, intensity in _tree_peak_rows(
                    self.world, energy,
                    root_alive=self.world["kind"] != "in_source"):
                mz_noisy = mz + rng.normal(0.0, self.world["noise"])
                intensity_noisy = intensity * math.exp(
                    rng.normal(0.0, self.world["intensity_noise"]))
                peaks.append({"mz": float(mz_noisy),
                              "intensity": float(max(intensity_noisy, 0.05))})
            if self.world["contaminant_tree"] is not None:
                for mz, intensity in _tree_peak_rows(
                        self.world, energy, tree=self.world["contaminant_tree"]):
                    mz_noisy = mz + rng.normal(0.0, self.world["noise"])
                    intensity_noisy = intensity * math.exp(
                        rng.normal(0.0, self.world["intensity_noise"]))
                    peaks.append({"mz": float(mz_noisy),
                                  "intensity": float(max(intensity_noisy, 0.05))})
            for mz, intensity in self.world["decoys"]:
                jitter = intensity * math.exp(rng.normal(0.0, 0.01))
                peaks.append({"mz": float(mz + rng.normal(0.0, self.world["noise"])),
                              "intensity": float(max(jitter, 0.05))})
            peaks.sort(key=lambda row: -row["intensity"])
            return {"collision_energy": energy, "peaks": peaks,
                    "budget_cost": ACQUIRE_COST}
        except Exception:
            self.violated = True
            raise

    def zoom(self, center_mz, window_width_da):
        try:
            center = float(center_mz)
            width = float(window_width_da)
            if (not math.isfinite(center) or not math.isfinite(width)
                    or not ZOOM_MIN_WIDTH_DA <= width <= ZOOM_MAX_WIDTH_DA):
                self.violated = True
                raise ValueError("zoom window outside allowed bounds")
            self._charge(ZOOM_COST)
            self.used += ZOOM_COST
            self.calls += 1
            rng = _call_rng(self.world,
                            ("zoom %.6f %.6f" % (center, width)).encode(), self.calls)
            lo, hi = center - width / 2.0, center + width / 2.0
            reference_energy = 18.0
            rows = []
            trees = [(self.world["nodes"], self.world["edges"])]
            if self.world["contaminant_tree"] is not None:
                trees.append(self.world["contaminant_tree"])
            for nodes, edges in trees:
                is_main = nodes is self.world["nodes"]
                for mz, intensity in _tree_peak_rows(
                        self.world, reference_energy, tree=(nodes, edges),
                        root_alive=(not is_main or self.world["kind"] != "in_source")):
                    if lo <= mz <= hi:
                        rows.append((mz, intensity, _carbon_count(nodes, mz)))
            peaks = []
            for mz, intensity, carbons in rows:
                ratio = 0.011 * carbons * (1.0 + rng.normal(0.0, 0.01))
                mz_noisy = mz + rng.normal(0.0, self.world["noise"] * 0.25)
                peaks.append({"mz": float(mz_noisy),
                              "intensity": float(intensity),
                              "m1_ratio": float(max(ratio, 1e-4))})
            for mz, intensity in self.world["decoys"]:
                if lo <= mz <= hi:
                    peaks.append({"mz": float(mz + rng.normal(0.0, self.world["noise"] * 0.25)),
                                  "intensity": float(intensity),
                                  "m1_ratio": float(max(rng.uniform(0.0, 0.004), 1e-4))})
            peaks.sort(key=lambda row: -row["intensity"])
            return {"window_center": center, "window_width": width,
                    "peaks": peaks, "budget_cost": ZOOM_COST}
        except Exception:
            self.violated = True
            raise


def _carbon_count(nodes, mz):
    for formula in nodes:
        if abs(_formula_mass(formula) + PROTON_MASS - mz) < 1e-9:
            return formula[0]
    return 4


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    nodes = np.asarray(submission.get("nodes"), dtype=float).reshape(-1)
    if bool(abstain):
        if nodes.size or submission.get("edges"):
            raise ValueError("abstention requires empty nodes and edges")
        return nodes, [], confidence, True
    if np.any(~np.isfinite(nodes)) or np.any(nodes <= 0.0):
        raise ValueError("nodes must be positive finite m/z values")
    if len(set(np.round(nodes, 4))) != len(nodes):
        raise ValueError("nodes must be unique")
    edges_raw = submission.get("edges") or []
    if not isinstance(edges_raw, (list, tuple)):
        raise ValueError("edges must be a list")
    edges = []
    for row in edges_raw:
        parent_mz, child_mz, loss_name = row
        if loss_name not in LOSS_LIBRARY:
            raise ValueError("edge loss must come from the public library")
        parent_mz, child_mz = float(parent_mz), float(child_mz)
        nearest_p = _nearest(nodes, parent_mz)
        nearest_c = _nearest(nodes, child_mz)
        if nearest_p is None or nearest_c is None or nearest_p == nearest_c:
            raise ValueError("edge endpoints must reference distinct submitted nodes")
        edges.append((nearest_p, nearest_c, loss_name))
    return nodes, edges, confidence, False


def _nearest(nodes, value):
    best, best_gap = None, None
    for node in nodes:
        gap = abs(node - value)
        if gap <= MASS_TOLERANCE_DA and (best_gap is None or gap < best_gap):
            best, best_gap = float(node), gap
    return best


def _match_nodes(predicted, truth):
    if not len(predicted) or not len(truth):
        return {}
    big = 1e6
    cost = np.full((len(predicted), len(truth)), big)
    for i, p in enumerate(predicted):
        for j, t in enumerate(truth):
            gap = abs(p - t)
            if gap <= MASS_TOLERANCE_DA:
                cost[i, j] = gap
    rows, cols = linear_sum_assignment(cost)
    return {int(j): int(i) for i, j in zip(rows, cols)
            if cost[i, j] < big}


def _mechanism_score(world, nodes, edges):
    truth_nodes = np.asarray([_formula_mass(f) + PROTON_MASS for f in world["nodes"]])
    matches = _match_nodes(nodes, truth_nodes)  # truth index -> predicted index
    matched = len(matches)
    node_precision = matched / len(nodes) if len(nodes) else 0.0
    node_recall = matched / len(truth_nodes) if len(truth_nodes) else 0.0
    node_f1 = (2 * node_precision * node_recall / (node_precision + node_recall)
               if matched else 0.0)
    truth_edges = [(p, c, name) for p, c, name, _lab in world["edges"]]
    edge_hits = 0
    for parent_mz, child_mz, name in edges:
        tp = _matched_truth_index(matches, nodes, parent_mz, truth_nodes)
        tc = _matched_truth_index(matches, nodes, child_mz, truth_nodes)
        if tp is None or tc is None:
            continue
        if (tp, tc, name) in truth_edges:
            edge_hits += 1
    edge_precision = edge_hits / len(edges) if edges else 0.0
    edge_recall = edge_hits / len(truth_edges) if truth_edges else 1.0
    edge_f1 = (2 * edge_precision * edge_recall / (edge_precision + edge_recall)
               if edge_hits else 0.0)
    return float(0.5 * (node_f1 + edge_f1)), node_f1, edge_f1


def _matched_truth_index(matches, nodes, node_mz, truth_nodes):
    for predicted_index, node in enumerate(nodes):
        if abs(node - node_mz) <= 1e-9:
            for truth_index, p_index in matches.items():
                if p_index == predicted_index:
                    return truth_index
    return None


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "node_f1": 0.0, "edge_f1": 0.0,
            "false_discovery": False, "correct_refusal": False,
            "confidence_score": 0.0, "measurement_cost": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    instrument = _Instrument(world)
    precursor_mz = _formula_mass(world["nodes"][0]) + PROTON_MASS
    try:
        submission = candidate(problem_statement(precursor_mz),
                               instrument.acquire, instrument.zoom, BUDGET_UNITS)
        nodes, edges, confidence, abstain = _validate(submission)
        if instrument.violated:
            raise ValueError("measurement contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            mechanism, node_f1, edge_f1 = _mechanism_score(world, nodes, edges)
        elif supported:
            mechanism = node_f1 = edge_f1 = 0.0
        else:
            correct = bool(abstain)
            mechanism = node_f1 = edge_f1 = 1.0 if correct else 0.0
        target_confidence = 1.0 if (supported and not abstain) else (
            1.0 if (not supported and abstain) else 0.0)
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": float(mechanism),
                    "node_f1": float(node_f1), "edge_f1": float(edge_f1),
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target_confidence) ** 2,
                    "measurement_cost": instrument.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "node_f1": float(np.mean([r["node_f1"] for r in supported])) if supported else 0.0,
        "edge_f1": float(np.mean([r["edge_f1"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(recover_fragmentation_tree):
    development = [_evaluate_world(recover_fragmentation_tree, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(recover_fragmentation_tree, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_node_f1": dev["node_f1"],
        "development_edge_f1": dev["edge_f1"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "discovery_attempt_count": dev["attempt_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "heldout_discovery_coverage": hold["attempt_count"] / hold["supported_count"],
        "per_world": development + heldout,
    }
