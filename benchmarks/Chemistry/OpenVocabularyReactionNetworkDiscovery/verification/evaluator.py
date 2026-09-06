"""Deterministic synthetic oracle for open-vocabulary reaction-network discovery.

Species are small coloured molecular graphs.  A candidate must construct those
graphs and elementary bond-exchange edges; it is never handed a species or edge
catalogue.  The oracle is an analytic benchmark mechanism, not a claim about a
real reaction network or a quantum-chemistry replacement.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent.parent
CONTRACT_DIR = TASK_DIR / "frontier_eval" / "contracts"
PANEL_PATH = CONTRACT_DIR / "evaluation_panel_v1.json"

_PANEL = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
if _PANEL.get("schema_version") != 1:
    raise RuntimeError("unsupported reaction evaluation panel schema")
_GRAMMAR = _PANEL["grammar"]
_LIMITS = _PANEL["resource_limits"]
_ACTIVATION_MODEL = _PANEL["activation_model"]
_SCORING = _PANEL["scoring"]
ATOM_INVENTORY = tuple(_GRAMMAR["atom_inventory"])
MAX_VALENCE = {key: int(value) for key, value in _GRAMMAR["max_valence"].items()}
ALLOWED_BOND_ORDERS = tuple(int(value) for value in _GRAMMAR["allowed_bond_orders"])
PAIR_STRENGTH = {
    tuple(key.split("-")): float(value)
    for key, value in _GRAMMAR["pair_strength"].items()
}
MINIMUM_ATOMS = int(_GRAMMAR["minimum_atoms"])
MAXIMUM_ATOMS = int(_GRAMMAR["maximum_atoms"])
PROBE_BUDGET = int(_LIMITS["probe_calls_per_world"])
MAX_CLAIMED_SPECIES = int(_LIMITS["maximum_claimed_species"])
MAX_CLAIMED_REACTIONS = int(_LIMITS["maximum_claimed_reactions"])
ACTIVATION_ENERGY_BOUNDS = (
    float(_LIMITS["activation_energy_minimum"]),
    float(_LIMITS["activation_energy_maximum"]),
)
WORLD_SPECS = tuple(
    {**row, "favoured_pair": tuple(row["favoured_pair"])}
    for row in _PANEL["worlds"]
)
DEVELOPMENT_SPECS = tuple(
    spec for spec in WORLD_SPECS if spec["split"] == "development"
)
HELDOUT_SPECS = tuple(spec for spec in WORLD_SPECS if spec["split"] == "heldout")


def _load_contract(name, filename):
    spec = importlib.util.spec_from_file_location(name, CONTRACT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load frozen semantic contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_reference(name):
    frozen = _PANEL["reference_policy"]
    path = TASK_DIR / frozen["path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != frozen["sha256"]:
        raise RuntimeError("independent reference policy hash differs")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load independent reference policy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CANONICALIZER = _load_contract(
    "open_vocabulary_reaction_canonicalizer", "reaction_canonicalizer_v1.py"
)
_EVIDENCE = _load_contract(
    "open_vocabulary_reaction_evidence", "evidence_predicate_v1.py"
)
_REFERENCE = _load_reference("open_vocabulary_reaction_reference")
_reference_policy = _REFERENCE.discover_reaction_network


def _numeric(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise TypeError(name + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if low is not None and value < low:
        raise ValueError(name + " is below its public bound")
    if high is not None and value > high:
        raise ValueError(name + " is above its public bound")
    return value


def _graph_parts(graph, expected_inventory=None):
    if not isinstance(graph, Mapping) or set(graph) != {"atoms", "bonds"}:
        raise ValueError("a species must contain exactly atoms and bonds")
    atoms = graph["atoms"]
    if (
        not isinstance(atoms, (list, tuple))
        or not MINIMUM_ATOMS <= len(atoms) <= MAXIMUM_ATOMS
    ):
        raise ValueError("atoms must contain two to six element symbols")
    atoms = tuple(atoms)
    if any(not isinstance(atom, str) or atom not in MAX_VALENCE for atom in atoms):
        raise ValueError("unsupported atom symbol")
    if expected_inventory is not None and tuple(sorted(atoms)) != tuple(sorted(expected_inventory)):
        raise ValueError("every species must conserve the public atom inventory")
    bonds = graph["bonds"]
    if not isinstance(bonds, (list, tuple)):
        raise TypeError("bonds must be a sequence")
    parsed = set()
    degree = [0] * len(atoms)
    for bond in bonds:
        if not isinstance(bond, (list, tuple)) or len(bond) != 3:
            raise ValueError("each bond must be [left, right, order]")
        left, right, order = bond
        if any(isinstance(value, bool) or not isinstance(value, (int, np.integer))
               for value in (left, right, order)):
            raise ValueError("bond indices and order must be integers")
        left, right, order = int(left), int(right), int(order)
        if order not in ALLOWED_BOND_ORDERS:
            raise ValueError("this frozen cell supports single heavy-atom bonds only")
        if not 0 <= left < len(atoms) or not 0 <= right < len(atoms) or left == right:
            raise ValueError("bond endpoint is invalid")
        edge = tuple(sorted((left, right)))
        if edge in parsed:
            raise ValueError("duplicate bond")
        parsed.add(edge)
        degree[left] += 1
        degree[right] += 1
    if any(value > MAX_VALENCE[atoms[index]] for index, value in enumerate(degree)):
        raise ValueError("species exceeds a heavy-atom valence bound")
    seen = {0}
    frontier = [0]
    while frontier:
        node = frontier.pop()
        for left, right in parsed:
            neighbour = right if left == node else left if right == node else None
            if neighbour is not None and neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    if len(seen) != len(atoms):
        raise ValueError("species graph must be connected")
    return atoms, parsed


def _canonical_graph(graph, expected_inventory=None):
    """Canonical coloured-graph identity, independent of submitted atom order."""
    atoms, bonds = _graph_parts(graph, expected_inventory)
    labels = tuple(sorted(atoms))
    encodings = []
    for permutation in itertools.permutations(range(len(atoms))):
        if tuple(atoms[index] for index in permutation) != labels:
            continue
        adjacency = tuple(
            int(tuple(sorted((permutation[left], permutation[right]))) in bonds)
            for left in range(len(atoms))
            for right in range(left + 1, len(atoms))
        )
        encodings.append(adjacency)
    best = min(encodings)
    return ",".join(labels) + "|" + "".join(str(value) for value in best)


def _key_to_graph(key):
    labels_text, bits_text = key.split("|", 1)
    atoms = labels_text.split(",")
    pairs = list(itertools.combinations(range(len(atoms)), 2))
    bonds = [[left, right, 1] for bit, (left, right) in zip(bits_text, pairs) if bit == "1"]
    return {"atoms": atoms, "bonds": bonds}


def _enumerate_species_graphs(atom_inventory):
    """Enumerate the grammar, not a candidate list exposed in the problem."""
    atoms = tuple(sorted(atom_inventory))
    pairs = list(itertools.combinations(range(len(atoms)), 2))
    graphs = {}
    for mask in range(1 << len(pairs)):
        graph = {
            "atoms": list(atoms),
            "bonds": [
                [left, right, 1]
                for bit, (left, right) in enumerate(pairs)
                if mask & (1 << bit)
            ],
        }
        try:
            key = _canonical_graph(graph, atoms)
        except ValueError:
            continue
        graphs.setdefault(key, _key_to_graph(key))
    return dict(sorted(graphs.items()))


def _adjacency(key):
    return tuple(int(value) for value in key.split("|", 1)[1])


def _bond_exchange(left_key, right_key):
    """Find all one-delete/one-add channels across valid coloured-graph maps."""
    left_graph = _key_to_graph(left_key)
    right_graph = _key_to_graph(right_key)
    atoms = tuple(left_graph["atoms"])
    right_atoms = tuple(right_graph["atoms"])
    left_bonds = {tuple(bond[:2]) for bond in left_graph["bonds"]}
    right_bonds = {tuple(bond[:2]) for bond in right_graph["bonds"]}
    pairs = list(itertools.combinations(range(len(atoms)), 2))
    candidates = set()
    for mapping in itertools.permutations(range(len(atoms))):
        if any(atoms[index] != right_atoms[mapping[index]] for index in range(len(atoms))):
            continue
        aligned_right = {
            pair for pair in pairs
            if tuple(sorted((mapping[pair[0]], mapping[pair[1]]))) in right_bonds
        }
        removed_pairs = left_bonds - aligned_right
        formed_pairs = aligned_right - left_bonds
        if len(removed_pairs) == 1 and len(formed_pairs) == 1:
            removed = pairs.index(next(iter(removed_pairs)))
            formed = pairs.index(next(iter(formed_pairs)))
            candidates.add((removed, formed))
    if not candidates:
        return False, [], []
    ordered = sorted(candidates)
    return True, [removed for removed, _formed in ordered], [formed for _removed, formed in ordered]


def _pair_for_bit(index):
    atoms = tuple(sorted(ATOM_INVENTORY))
    left, right = list(itertools.combinations(range(len(atoms)), 2))[index]
    return tuple(sorted((atoms[left], atoms[right])))


def _species_energy(key):
    return -sum(
        PAIR_STRENGTH[_pair_for_bit(index)]
        for index, present in enumerate(_adjacency(key))
        if present
    )


def _activation_energy(left_key, right_key, spec):
    allowed, removed_channels, formed_channels = _bond_exchange(left_key, right_key)
    if not allowed:
        raise ValueError("proposal is not one elementary bond exchange")
    if len(removed_channels) != len(formed_channels):
        raise RuntimeError("bond-exchange channel counts differ")
    uphill = max(_species_energy(right_key) - _species_energy(left_key), 0.0)
    barriers = []
    for removed, formed in zip(removed_channels, formed_channels):
        broken_pair = _pair_for_bit(removed)
        formed_pair = _pair_for_bit(formed)
        selectivity = (
            _ACTIVATION_MODEL["favoured_formed_offset"]
            if formed_pair == spec["favoured_pair"]
            else _ACTIVATION_MODEL["other_formed_offset"]
        )
        if broken_pair == spec["favoured_pair"]:
            selectivity += _ACTIVATION_MODEL["favoured_broken_offset"]
        barriers.append(
            _ACTIVATION_MODEL["intercept"]
            + _ACTIVATION_MODEL["broken_bond_coefficient"] * PAIR_STRENGTH[broken_pair]
            + _ACTIVATION_MODEL["formed_bond_coefficient"] * PAIR_STRENGTH[formed_pair]
            + _ACTIVATION_MODEL["uphill_energy_coefficient"] * uphill
            + selectivity
            + spec["barrier_offset"]
        )
    return float(min(barriers))


def _truth(spec):
    graphs = _enumerate_species_graphs(ATOM_INVENTORY)
    if spec["kind"] != "supported":
        return graphs, {}
    possible = {}
    for left_key, right_key in itertools.permutations(graphs, 2):
        allowed, _removed, _formed = _bond_exchange(left_key, right_key)
        if not allowed:
            continue
        barrier = _activation_energy(left_key, right_key, spec)
        if barrier <= spec["barrier_limit"]:
            possible[(left_key, right_key)] = barrier
    seed = list(graphs)[spec["seed_index"] % len(graphs)]
    reachable = {seed}
    while True:
        products = {
            right for (left, right) in possible
            if left in reachable
        }
        enlarged = reachable | products
        if enlarged == reachable:
            break
        reachable = enlarged
    reactions = {
        edge: barrier for edge, barrier in possible.items()
        if edge[0] in reachable
    }
    if not reactions:
        raise RuntimeError("supported world has an empty analytic network")
    return graphs, reactions


def _problem(spec):
    graphs = _enumerate_species_graphs(ATOM_INVENTORY)
    graph_values = list(graphs.values())
    return {
        "atom_inventory": list(ATOM_INVENTORY),
        "seed_species": [graph_values[spec["seed_index"] % len(graph_values)]],
        "probe_budget": PROBE_BUDGET,
        "max_claimed_species": MAX_CLAIMED_SPECIES,
        "max_claimed_reactions": MAX_CLAIMED_REACTIONS,
        "allowed_bond_orders": list(ALLOWED_BOND_ORDERS),
        "element_valence_bounds": dict(MAX_VALENCE),
        "elementary_edge_rule": _GRAMMAR["elementary_edge_rule"],
        "probe_response": (
            "supported with an exact activation energy, unsupported, or model_inadequate"
        ),
        "abstain_when": (
            "no supported edge exists in the grammar, or probes diagnose model inadequacy"
        ),
    }


class _Probe:
    def __init__(self, spec):
        self.spec = spec
        self.calls = 0
        self.violation = None
        _graphs, self.truth = _truth(spec)

    def _fail(self, message):
        if self.violation is None:
            self.violation = str(message)
        raise ValueError(message)

    def __call__(self, proposal):
        if self.calls >= PROBE_BUDGET:
            self._fail("probe budget exceeded")
        if not isinstance(proposal, Mapping) or set(proposal) != {"reactant", "product"}:
            self._fail("a probe must contain exactly reactant and product")
        try:
            left = _canonical_graph(proposal["reactant"], ATOM_INVENTORY)
            right = _canonical_graph(proposal["product"], ATOM_INVENTORY)
            allowed, _removed, _formed = _bond_exchange(left, right)
            if left == right or not allowed:
                raise ValueError("probe must be a nontrivial elementary bond exchange")
        except (KeyError, TypeError, ValueError) as exc:
            self._fail(str(exc))
        self.calls += 1
        if self.spec["kind"] == "model_inadequate":
            status, barrier = "model_inadequate", None
        elif (left, right) in self.truth:
            status, barrier = "supported", self.truth[(left, right)]
        else:
            status, barrier = "unsupported", None
        return {
            "status": status,
            "activation_energy": barrier,
            "budget_cost": 1,
            "remaining_budget": PROBE_BUDGET - self.calls,
        }


def _validate_submission(submission):
    if not isinstance(submission, Mapping):
        raise TypeError("submission must be a mapping")
    allowed_fields = {"species", "reactions", "abstain", "confidence"}
    if not set(submission).issubset(allowed_fields) or "abstain" not in submission:
        raise ValueError("submission has unknown fields or no abstain decision")
    abstain = submission["abstain"]
    if not isinstance(abstain, bool):
        raise TypeError("abstain must be boolean")
    confidence = _numeric(submission.get("confidence", 0.0), "confidence", 0.0, 1.0)
    if abstain:
        if submission.get("species") not in (None, [], ()):
            raise ValueError("an abstention must not claim species")
        if submission.get("reactions") not in (None, [], ()):
            raise ValueError("an abstention must not claim reactions")
        return {}, {}, confidence, True
    species = submission.get("species")
    reactions = submission.get("reactions")
    if not isinstance(species, (list, tuple)) or not 2 <= len(species) <= MAX_CLAIMED_SPECIES:
        raise ValueError("species must contain two to max_claimed_species graphs")
    if not isinstance(reactions, (list, tuple)) or not 1 <= len(reactions) <= MAX_CLAIMED_REACTIONS:
        raise ValueError("reactions must contain one to max_claimed_reactions edges")
    canonical_species = []
    for graph in species:
        canonical_species.append(_canonical_graph(graph, ATOM_INVENTORY))
    if len(set(canonical_species)) != len(canonical_species):
        raise ValueError("isomorphic duplicate species are not distinct discoveries")
    parsed = {}
    for reaction in reactions:
        if not isinstance(reaction, Mapping) or set(reaction) != {
            "reactant", "product", "activation_energy"
        }:
            raise ValueError("each reaction has the wrong fields")
        left, right = reaction["reactant"], reaction["product"]
        if any(isinstance(index, bool) or not isinstance(index, (int, np.integer))
               for index in (left, right)):
            raise ValueError("reaction endpoints must be integer species indices")
        left, right = int(left), int(right)
        if not 0 <= left < len(species) or not 0 <= right < len(species) or left == right:
            raise ValueError("reaction endpoint is invalid")
        edge = (canonical_species[left], canonical_species[right])
        valid_edge, _removed, _formed = _bond_exchange(*edge)
        if not valid_edge:
            raise ValueError("claimed reaction is outside the public elementary grammar")
        if edge in parsed:
            raise ValueError("canonical duplicate reaction")
        parsed[edge] = _numeric(
            reaction["activation_energy"], "activation_energy", *ACTIVATION_ENERGY_BOUNDS
        )
    return dict.fromkeys(canonical_species), parsed, confidence, False


def _f1(predicted, truth):
    if not predicted and not truth:
        return 1.0
    if not predicted or not truth:
        return 0.0
    hits = len(set(predicted) & set(truth))
    precision = hits / len(predicted)
    recall = hits / len(truth)
    return 2.0 * precision * recall / (precision + recall) if hits else 0.0


def _metrics(spec, species, reactions, confidence, abstain):
    _graphs, truth = _truth(spec)
    supported = spec["kind"] == "supported"
    if not supported:
        correct_refusal = bool(abstain)
        false_discovery = 0.0 if abstain else 1.0
        return {
            "mechanism_recovery": 0.0,
            "world_score": 1.0 if correct_refusal else 0.0,
            "false_discovery_rate": false_discovery,
            "false_edge_count": float(len(reactions)) if not abstain else 0.0,
            "claimed_edge_count": float(len(reactions)) if not abstain else 0.0,
            "correct_refusal": correct_refusal,
            "calibrated_refusal_score": (
                (1.0 - confidence ** 2) if correct_refusal else 0.0
            ),
            "attempted_discovery": False,
            "confidence_calibration_score": 1.0 - confidence ** 2,
            "frontier_records": [],
        }
    if abstain:
        return {
            "mechanism_recovery": 0.0,
            "world_score": 0.0,
            "false_discovery_rate": 0.0,
            "false_edge_count": 0.0,
            "claimed_edge_count": 0.0,
            "correct_refusal": False,
            "calibrated_refusal_score": 0.0,
            "attempted_discovery": False,
            "confidence_calibration_score": 1.0 - confidence ** 2,
            "frontier_records": [],
        }
    truth_species = {key for edge in truth for key in edge}
    edge_f1 = _f1(reactions, truth)
    species_f1 = _f1(species, truth_species)
    matched = set(reactions) & set(truth)
    barrier_score = float(np.mean([
        math.exp(
            -abs(reactions[edge] - truth[edge]) / _SCORING["barrier_error_scale"]
        )
        for edge in matched
    ])) if matched else 0.0
    recovery = float(
        _SCORING["edge_f1_weight"] * edge_f1
        + _SCORING["species_f1_weight"] * species_f1
        + _SCORING["barrier_weight"] * barrier_score
    )
    false_discovery = 1.0 - len(matched) / len(reactions)
    condition = {
        "favoured_pair": list(spec["favoured_pair"]),
        "barrier_offset": spec["barrier_offset"],
        "barrier_limit": spec["barrier_limit"],
    }
    frontier_records = []
    for edge in sorted(matched):
        canonical_id = _CANONICALIZER.canonical_reaction_id(condition, *edge)
        record = _EVIDENCE.make_frontier_record(
            canonical_id, reactions[edge], truth[edge]
        )
        if record is not None:
            frontier_records.append(record)
    return {
        "mechanism_recovery": recovery,
        "world_score": recovery,
        "false_discovery_rate": false_discovery,
        "false_edge_count": float(len(reactions) - len(matched)),
        "claimed_edge_count": float(len(reactions)),
        "correct_refusal": False,
        "calibrated_refusal_score": 0.0,
        "attempted_discovery": bool(reactions),
        "confidence_calibration_score": 1.0 - (confidence - recovery) ** 2,
        "frontier_records": frontier_records,
    }


ROW_NUMERIC = (
    "mechanism_recovery", "world_score", "false_discovery_rate",
    "false_edge_count", "claimed_edge_count", "calibrated_refusal_score",
    "confidence_calibration_score",
)


def _evaluate_world(candidate, spec, split, index):
    probe = _Probe(spec)
    base = {
        "split": split,
        "world_index": int(index),
        "kind": spec["kind"],
        "probe_calls": 0,
    }
    try:
        submission = candidate(_problem(spec), probe)
        species, reactions, confidence, abstain = _validate_submission(submission)
        if probe.violation is not None:
            raise ValueError("probe contract was violated")
        values = _metrics(spec, species, reactions, confidence, abstain)
        return {
            **base,
            **values,
            "valid": True,
            "abstained": abstain,
            "claimed_species_count": len(species),
            "claimed_reaction_count": len(reactions),
            "confidence": confidence,
            "probe_calls": probe.calls,
        }
    except Exception as exc:  # noqa: BLE001 - candidate errors fail closed per world
        return {
            **base,
            **{key: 0.0 for key in ROW_NUMERIC},
            "valid": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "abstained": True,
            "claimed_species_count": 0,
            "claimed_reaction_count": 0,
            "confidence": 0.0,
            "correct_refusal": False,
            "calibrated_refusal_score": 0.0,
            "attempted_discovery": False,
            "probe_calls": probe.calls,
        }


def _mean(records, field):
    return float(np.mean([float(row[field]) for row in records]))


@lru_cache(maxsize=1)
def _reference_raw_scores():
    anchors = {}
    for split, specs in (
        ("development", DEVELOPMENT_SPECS),
        ("heldout", HELDOUT_SPECS),
    ):
        records = [
            _evaluate_world(_reference_policy, spec, split, index)
            for index, spec in enumerate(specs)
        ]
        if not all(row["valid"] for row in records):
            raise RuntimeError(split + " independent reaction reference is invalid")
        raw = _mean(records, "world_score")
        abstention_floor = sum(row["kind"] != "supported" for row in records) / len(records)
        if raw <= abstention_floor:
            raise RuntimeError(split + " reaction reference has no discovery headroom")
        anchors[split] = raw
    return anchors


def _split_summary(records, split):
    supported = [row for row in records if row["kind"] == "supported"]
    unsupported = [row for row in records if row["kind"] != "supported"]
    raw = _mean(records, "world_score")
    abstention_floor = len(unsupported) / len(records)
    reference_raw = _reference_raw_scores()[split]
    normalized = max((raw - abstention_floor) / (reference_raw - abstention_floor), 0.0)
    return {
        "normalized": float(normalized),
        "raw": raw,
        "reference_raw": reference_raw,
        "mechanism_recovery": _mean(supported, "mechanism_recovery"),
        "false_discovery_rate": (
            sum(row["false_edge_count"] for row in records)
            / sum(row["claimed_edge_count"] for row in records)
            if sum(row["claimed_edge_count"] for row in records) else 0.0
        ),
        "claimed_edge_count": float(sum(row["claimed_edge_count"] for row in records)),
        "correct_refusal_rate": _mean(unsupported, "correct_refusal"),
        "calibrated_refusal_score": _mean(unsupported, "calibrated_refusal_score"),
        "attempted_discovery_rate": _mean(supported, "attempted_discovery"),
        "confidence_calibration": _mean(records, "confidence_calibration_score"),
        "mean_probe_calls": _mean(records, "probe_calls"),
        "valid_rate": _mean(records, "valid"),
    }


def evaluate(discover_reaction_network):
    records = []
    all_specs = tuple(("development", spec) for spec in DEVELOPMENT_SPECS)
    all_specs += tuple(("heldout", spec) for spec in HELDOUT_SPECS)
    for index, (split, spec) in enumerate(all_specs):
        if index and hasattr(discover_reaction_network, "reset_session"):
            discover_reaction_network.reset_session()
        records.append(_evaluate_world(discover_reaction_network, spec, split, index))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    dev = _split_summary(development, "development")
    held = _split_summary(heldout, "heldout")
    development_valid = all(row["valid"] for row in development)
    result = {
        "combined_score": dev["normalized"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_rate"],
        "raw_score": dev["normalized"] if development_valid else 0.0,
        "development_mechanism_score": dev["normalized"],
        "development_raw_world_score": dev["raw"],
        "development_reference_raw_world_score": dev["reference_raw"],
        "development_mechanism_recovery": dev["mechanism_recovery"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_claimed_edge_count": dev["claimed_edge_count"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_calibrated_refusal_score": dev["calibrated_refusal_score"],
        "development_attempted_discovery_rate": dev["attempted_discovery_rate"],
        "development_discovery_coverage": dev["attempted_discovery_rate"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_probe_calls": dev["mean_probe_calls"],
        "heldout_mechanism_score": held["normalized"],
        "heldout_reference_raw_world_score": held["reference_raw"],
        "heldout_mechanism_recovery": held["mechanism_recovery"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_claimed_edge_count": held["claimed_edge_count"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_calibrated_refusal_score": held["calibrated_refusal_score"],
        "heldout_attempted_discovery_rate": held["attempted_discovery_rate"],
        "heldout_discovery_coverage": held["attempted_discovery_rate"],
        "heldout_confidence_calibration": held["confidence_calibration"],
        "heldout_feasibility_rate": held["valid_rate"],
        "frontier_records": list({
            record["canonical_id"]: record
            for row in development for record in row["frontier_records"]
        }.values()) if development_valid else [],
        "per_instance": development + heldout,
    }
    if not development_valid:
        result["error_message"] = "candidate invalid on one or more development worlds"
    return result
