"""Public-information active-frontier witness for reaction-network discovery.

This module intentionally depends only on the problem mapping and the charged
probe callback.  Its qualitative bond-strength prior ranks bond types rather
than reproducing oracle parameters.  It neither imports the evaluator nor reads
frozen panel data.
"""
from __future__ import annotations

import itertools

_BOND_STRENGTH_RANK = {
    ("C", "C"): 3.0,
    ("C", "N"): 2.0,
    ("C", "O"): 4.0,
    ("N", "O"): 1.0,
}


def _graph_parts(graph, inventory, valence):
    atoms = tuple(graph["atoms"])
    if tuple(sorted(atoms)) != tuple(sorted(inventory)):
        raise ValueError("atom inventory changed")
    bonds = {tuple(sorted((int(left), int(right)))) for left, right, order in graph["bonds"]}
    if any(int(order) != 1 for _left, _right, order in graph["bonds"]):
        raise ValueError("only single bonds are supported")
    degree = [0] * len(atoms)
    for left, right in bonds:
        degree[left] += 1
        degree[right] += 1
    if any(degree[index] > valence[atom] for index, atom in enumerate(atoms)):
        raise ValueError("valence exceeded")
    seen = {0}
    frontier = [0]
    while frontier:
        node = frontier.pop()
        for left, right in bonds:
            neighbour = right if left == node else left if right == node else None
            if neighbour is not None and neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    if len(seen) != len(atoms):
        raise ValueError("disconnected graph")
    return atoms, bonds


def _canonical_graph(graph, inventory, valence):
    atoms, bonds = _graph_parts(graph, inventory, valence)
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
    return ",".join(labels) + "|" + "".join(str(value) for value in min(encodings))


def _key_to_graph(key):
    labels_text, bits_text = key.split("|", 1)
    atoms = labels_text.split(",")
    pairs = list(itertools.combinations(range(len(atoms)), 2))
    return {
        "atoms": atoms,
        "bonds": [
            [left, right, 1]
            for bit, (left, right) in zip(bits_text, pairs)
            if bit == "1"
        ],
    }


def _neighbours(graph, inventory, valence):
    key = _canonical_graph(graph, inventory, valence)
    canonical = _key_to_graph(key)
    atoms, bonds = _graph_parts(canonical, inventory, valence)
    pairs = set(itertools.combinations(range(len(atoms)), 2))
    neighbours = {}
    for removed in bonds:
        for formed in pairs - bonds:
            candidate = {
                "atoms": list(atoms),
                "bonds": [
                    [left, right, 1]
                    for left, right in sorted((bonds - {removed}) | {formed})
                ],
            }
            try:
                candidate_key = _canonical_graph(candidate, inventory, valence)
            except ValueError:
                continue
            if candidate_key != key:
                neighbours.setdefault(candidate_key, _key_to_graph(candidate_key))
    return dict(sorted(neighbours.items()))


def _exchange_channels(left_key, right_key):
    left_graph = _key_to_graph(left_key)
    right_graph = _key_to_graph(right_key)
    atoms = tuple(left_graph["atoms"])
    right_atoms = tuple(right_graph["atoms"])
    left_bonds = {tuple(bond[:2]) for bond in left_graph["bonds"]}
    right_bonds = {tuple(bond[:2]) for bond in right_graph["bonds"]}
    pairs = list(itertools.combinations(range(len(atoms)), 2))
    channels = set()
    for mapping in itertools.permutations(range(len(atoms))):
        if any(atoms[index] != right_atoms[mapping[index]] for index in range(len(atoms))):
            continue
        aligned_right = {
            pair
            for pair in pairs
            if tuple(sorted((mapping[pair[0]], mapping[pair[1]]))) in right_bonds
        }
        removed = left_bonds - aligned_right
        formed = aligned_right - left_bonds
        if len(removed) == 1 and len(formed) == 1:
            broken_atoms = tuple(sorted(atoms[index] for index in next(iter(removed))))
            formed_atoms = tuple(sorted(atoms[index] for index in next(iter(formed))))
            channels.add((broken_atoms, formed_atoms))
    return tuple(sorted(channels))


def _barrier_surrogate(left_key, right_key):
    estimates = []
    for broken_atoms, formed_atoms in _exchange_channels(left_key, right_key):
        broken = _BOND_STRENGTH_RANK[broken_atoms]
        formed = _BOND_STRENGTH_RANK[formed_atoms]
        endothermicity = max(broken - formed, 0.0)
        estimates.append(broken - 0.5 * formed + 0.5 * endothermicity)
    if not estimates:
        raise ValueError("frontier edge is not an elementary exchange")
    return min(estimates)


def discover_reaction_network(problem, probe):
    """Prioritize novel products with a qualitative low-barrier surrogate."""
    inventory = tuple(problem["atom_inventory"])
    valence = dict(problem["element_valence_bounds"])
    seed = problem["seed_species"][0]
    seed_key = _canonical_graph(seed, inventory, valence)
    graphs = {seed_key: _key_to_graph(seed_key)}
    attempted = set()
    supported = {}

    while len(attempted) < int(problem["probe_budget"]):
        frontier = [
            (left_key, right_key, right_graph)
            for left_key in sorted(graphs)
            for right_key, right_graph in _neighbours(
                graphs[left_key], inventory, valence
            ).items()
            if (left_key, right_key) not in attempted
        ]
        if not frontier:
            break
        left_key, right_key, right_graph = min(
            frontier,
            key=lambda item: (
                item[1] in graphs,
                _barrier_surrogate(item[0], item[1]),
                -len(_neighbours(item[2], inventory, valence)),
                item[0],
                item[1],
            ),
        )
        edge = (left_key, right_key)
        attempted.add(edge)
        response = probe({"reactant": graphs[left_key], "product": right_graph})
        if response["status"] == "model_inadequate":
            return {"abstain": True, "confidence": 0.0}
        if response["status"] == "supported":
            graphs.setdefault(right_key, right_graph)
            supported[edge] = float(response["activation_energy"])

    if not supported:
        return {"abstain": True, "confidence": 0.0}
    species_keys = sorted({key for edge in supported for key in edge})
    positions = {key: index for index, key in enumerate(species_keys)}
    return {
        "species": [graphs[key] for key in species_keys],
        "reactions": [
            {
                "reactant": positions[left],
                "product": positions[right],
                "activation_energy": barrier,
            }
            for (left, right), barrier in sorted(supported.items())
        ],
        "abstain": False,
        "confidence": 0.5,
    }
