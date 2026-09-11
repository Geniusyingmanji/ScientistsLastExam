"""Multispecies coalescent, sequence evolution and tree arithmetic for AnomalyZoneSpeciesTree.

Everything the oracle and the reference share lives here so that neither can quietly use a
different definition of a tree than the other. Nothing in this file reads a world's truth; the
evaluator passes what a routine needs as arguments.

Trees come in two shapes:

    rooted, ultrametric   the species trees and the simulated gene trees. Stored as a `Rooted`
                          with children lists and node heights in coalescent units.
    unrooted              what the candidate returns and what the oracle's neighbour-joining
                          produces. Stored as an adjacency list with edge lengths, and compared
                          through their nontrivial bipartitions.

The coalescent is the standard one-lineage-per-species multispecies coalescent (Rannala and Yang
2003), run branch by branch from the tips towards the root with a per-species rate multiplier
applied to every lineage while it sits in that species' branch. A reticulate world is a pair of
parental species trees: each locus follows parent one with probability gamma, which is the
network coalescent exactly when one lineage is sampled per species (Meng and Kubatko 2009).

Sequences evolve under Jukes-Cantor with gamma-distributed rates across sites. The oracle's
gene-tree estimate is neighbour joining on the plain Jukes-Cantor distance, which does not know
about the rate variation: the correction it omits is what pulls long branches together.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

TAXA = ("A", "B", "C", "D", "E", "F", "G", "H")
N_TAXA = len(TAXA)
FULL_MASK = (1 << N_TAXA) - 1
QUARTETS = tuple(itertools.combinations(range(N_TAXA), 4))
QUARTET_INDEX = {quartet: index for index, quartet in enumerate(QUARTETS)}
# Distance assigned to a saturated pair (p-distance at or above 3/4), where the Jukes-Cantor
# correction is undefined.
SATURATED_DISTANCE = 10.0


# ----------------------------------------------------------------------------------------------
# Rooted trees
# ----------------------------------------------------------------------------------------------

class Rooted:
    """A rooted binary tree: leaves 0..n-1 are taxa, internal nodes follow, the root is last."""

    def __init__(self, children, height):
        self.children = [tuple(c) for c in children]
        self.height = [float(h) for h in height]
        self.root = len(children) - 1

    @property
    def size(self):
        return len(self.children)

    def parent_map(self):
        parent = [None] * self.size
        for node, kids in enumerate(self.children):
            for kid in kids:
                parent[kid] = node
        return parent

    def postorder(self):
        order = []

        def visit(node):
            for kid in self.children[node]:
                visit(kid)
            order.append(node)

        visit(self.root)
        return order

    def clade_masks(self):
        masks = [0] * self.size
        for node in self.postorder():
            if not self.children[node]:
                masks[node] = 1 << node
            else:
                masks[node] = sum(masks[k] for k in self.children[node])
        return masks

    def unrooted_splits(self):
        """Nontrivial bipartitions with their branch lengths, root edges merged into one."""
        masks = self.clade_masks()
        parent = self.parent_map()
        splits = {}
        root_kids = self.children[self.root]
        for node in range(self.size):
            if node == self.root:
                continue
            length = self.height[parent[node]] - self.height[node]
            mask = canonical_split(masks[node])
            if not nontrivial(mask):
                continue
            if parent[node] == self.root:
                # The two root edges are one unrooted branch.
                splits[mask] = splits.get(mask, 0.0) + length
            else:
                splits[mask] = length
        if len(root_kids) == 2 and all(not nontrivial(canonical_split(masks[k])) for k in root_kids):
            pass
        return splits

    def newick(self, labels=TAXA, lengths=True):
        parent = self.parent_map()

        def render(node):
            if not self.children[node]:
                text = labels[node]
            else:
                text = "(" + ",".join(render(k) for k in self.children[node]) + ")"
            if lengths and parent[node] is not None:
                text += ":%.6f" % (self.height[parent[node]] - self.height[node])
            return text

        return render(self.root) + ";"


def rooted_from_newick(text):
    """Parse a rooted binary newick with branch lengths into a `Rooted` (ultrametric assumed)."""
    labels, adjacency = parse_newick(text, rooted=True)
    root = max(adjacency)
    children = {}
    depth = {}

    def visit(node, parent, d):
        depth[node] = d
        kids = [(nbr, length) for nbr, length in adjacency[node] if nbr != parent]
        children[node] = [nbr for nbr, _ in kids]
        for nbr, length in kids:
            visit(nbr, node, d + length)

    visit(root, None, 0.0)
    if any(len(children[node]) not in (0, 2) for node in children):
        raise ValueError("species tree must be binary")
    max_depth = max(depth[node] for node in children if not children[node])
    order = _relabel_order(children, labels, root)
    index = {node: i for i, node in enumerate(order)}
    kids = [tuple(index[k] for k in children[node]) for node in order]
    heights = [max_depth - depth[node] for node in order]
    return Rooted(kids, heights)


def _relabel_order(children, labels, root):
    """Leaves in taxon order first, then internal nodes in postorder, root last."""
    leaf_nodes = sorted((node for node in children if not children[node]), key=lambda n: labels[n])
    if [labels[n] for n in leaf_nodes] != list(TAXA):
        raise ValueError("tree must carry exactly the taxa %s" % (TAXA,))
    internal = []

    def visit(node):
        for kid in children[node]:
            visit(kid)
        if children[node]:
            internal.append(node)

    visit(root)
    return leaf_nodes + internal


# ----------------------------------------------------------------------------------------------
# Multispecies coalescent
# ----------------------------------------------------------------------------------------------

def simulate_gene_tree(species, rng, rate_multiplier=None):
    """One gene tree under the multispecies coalescent with one lineage per species.

    Returns a `Rooted` gene tree whose heights are in coalescent units, together with the
    substitution-scaled length of every branch: the time a lineage spends in each species branch
    is weighted by that species' rate multiplier, so a lineage accelerated in one species carries
    the acceleration only while it is there.
    """
    n = N_TAXA
    parent = species.parent_map()
    if rate_multiplier is None:
        rate_multiplier = [1.0] * species.size
    gene_children = [() for _ in range(n)]
    gene_height = [0.0] * n
    scaled = {}          # gene node -> substitution-scaled length of the branch above it
    accum = {}           # live lineage -> scaled length accumulated so far
    last = {}            # live lineage -> height at which accumulation last advanced
    pool_at = {}
    for node in species.postorder():
        if not species.children[node]:
            pool = [node]
            accum[node] = 0.0
            last[node] = 0.0
        else:
            pool = []
            for kid in species.children[node]:
                pool.extend(pool_at.pop(kid))
        start = species.height[node]
        end = species.height[parent[node]] if parent[node] is not None else math.inf
        mult = float(rate_multiplier[node])
        t = start
        while len(pool) > 1:
            k = len(pool)
            t = t + rng.exponential(2.0 / (k * (k - 1)))
            if t > end:
                break
            i, j = sorted(rng.choice(k, size=2, replace=False).tolist())
            a, b = pool[j], pool[i]
            new = len(gene_children)
            gene_children.append((b, a))
            gene_height.append(t)
            for lineage in (a, b):
                scaled[lineage] = accum.pop(lineage) + (t - last.pop(lineage)) * mult
            accum[new] = 0.0
            last[new] = t
            pool = [x for idx, x in enumerate(pool) if idx not in (i, j)] + [new]
        if end != math.inf:
            for lineage in pool:
                accum[lineage] += (end - last[lineage]) * mult
                last[lineage] = end
        pool_at[node] = pool
    tree = Rooted(gene_children, gene_height)
    lengths = [scaled.get(node, 0.0) for node in range(tree.size)]
    return tree, lengths


# ----------------------------------------------------------------------------------------------
# Sequence evolution and distances
# ----------------------------------------------------------------------------------------------

def simulate_alignment(tree, scaled_lengths, rate, length, gamma_shape, rng):
    """Jukes-Cantor with gamma rates across sites, along a gene tree.

    `scaled_lengths[node]` is the coalescent-unit length of the branch above `node`, already
    weighted by species rate multipliers; `rate` converts it into substitutions per site.
    """
    site_rate = rng.gamma(gamma_shape, 1.0 / gamma_shape, size=length)
    sequences = [None] * tree.size
    sequences[tree.root] = rng.integers(0, 4, size=length)
    order = list(reversed(tree.postorder()))
    for node in order:
        for kid in tree.children[node]:
            branch = scaled_lengths[kid] * rate
            p_change = 0.75 * (1.0 - np.exp(-4.0 / 3.0 * branch * site_rate))
            changed = rng.random(length) < p_change
            shift = rng.integers(1, 4, size=length)
            seq = sequences[node].copy()
            seq[changed] = (seq[changed] + shift[changed]) % 4
            sequences[kid] = seq
    return np.array(sequences[:N_TAXA], dtype=np.int8)


def to_strings(alignment):
    letters = np.array(list("ACGT"))
    return ["".join(letters[row]) for row in alignment]


def from_strings(rows):
    table = {"A": 0, "C": 1, "G": 2, "T": 3}
    return np.array([[table[ch] for ch in row] for row in rows], dtype=np.int8)


def p_distances(alignment):
    n = alignment.shape[0]
    p = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            p[i, j] = p[j, i] = float(np.mean(alignment[i] != alignment[j]))
    return p


def jc_distances(alignment):
    p = p_distances(alignment)
    d = np.where(p < 0.75, -0.75 * np.log(np.clip(1.0 - 4.0 * p / 3.0, 1e-12, None)), SATURATED_DISTANCE)
    np.fill_diagonal(d, 0.0)
    return d


def jc_gamma_distances(alignment, gamma_shape):
    p = p_distances(alignment)
    inner = np.clip(1.0 - 4.0 * p / 3.0, 1e-12, None)
    d = np.where(p < 0.75, 0.75 * gamma_shape * (inner ** (-1.0 / gamma_shape) - 1.0), SATURATED_DISTANCE)
    np.fill_diagonal(d, 0.0)
    return d


# ----------------------------------------------------------------------------------------------
# Neighbour joining and unrooted trees
# ----------------------------------------------------------------------------------------------

def neighbour_joining(distance):
    """Saitou-Nei neighbour joining. Returns an unrooted adjacency {node: [(nbr, length), ...]}."""
    d = np.array(distance, dtype=float)
    n = d.shape[0]
    active = list(range(n))
    adjacency = {i: [] for i in range(n)}
    next_node = n
    while len(active) > 2:
        m = len(active)
        sub = d[np.ix_(active, active)]
        totals = sub.sum(axis=1)
        q = (m - 2) * sub - totals[:, None] - totals[None, :]
        np.fill_diagonal(q, np.inf)
        flat = int(np.argmin(q))
        i, j = divmod(flat, m)
        if i > j:
            i, j = j, i
        a, b = active[i], active[j]
        dij = sub[i, j]
        la = 0.5 * dij + (totals[i] - totals[j]) / (2.0 * (m - 2))
        lb = dij - la
        la, lb = max(la, 0.0), max(lb, 0.0)
        u = next_node
        next_node += 1
        adjacency[u] = [(a, la), (b, lb)]
        adjacency[a].append((u, la))
        adjacency[b].append((u, lb))
        new_row = np.zeros(d.shape[0] + 1)
        d = np.pad(d, ((0, 1), (0, 1)))
        for k in active:
            if k in (a, b):
                continue
            d[u, k] = d[k, u] = 0.5 * (d[a, k] + d[b, k] - dij)
        active = [k for k in active if k not in (a, b)] + [u]
    a, b = active
    length = max(float(d[a, b]), 0.0)
    adjacency[a].append((b, length))
    adjacency[b].append((a, length))
    return adjacency


def unrooted_newick(adjacency, labels=TAXA):
    """Render an unrooted adjacency as newick, rooted for display at an internal node."""
    root = max(node for node in adjacency if node >= N_TAXA) if len(adjacency) > N_TAXA else 0

    def render(node, parent):
        kids = [(nbr, length) for nbr, length in adjacency[node] if nbr != parent]
        if not kids:
            return labels[node]
        return "(" + ",".join("%s:%.6f" % (render(nbr, node), length) for nbr, length in kids) + ")"

    return render(root, None) + ";"


def parse_newick(text, rooted=False):
    """Parse newick into (labels, adjacency). Leaves are numbered by taxon order when the leaf
    labels are exactly the eight taxa; internal nodes follow. Unrooted parsing merges a bifurcating
    root into one edge."""
    if not isinstance(text, str):
        raise ValueError("newick must be a string")
    s = text.strip()
    if not s.endswith(";"):
        raise ValueError("newick must end with ';'")
    s = s[:-1].strip()
    tokens = _tokenize(s)
    pos = [0]
    nodes = []          # list of (label, children[(child_index, length)])

    def parse_subtree():
        if pos[0] >= len(tokens):
            raise ValueError("unexpected end of newick")
        token = tokens[pos[0]]
        if token == "(":
            pos[0] += 1
            kids = []
            while True:
                child = parse_subtree()
                length = None
                if pos[0] < len(tokens) and tokens[pos[0]] == ":":
                    pos[0] += 1
                    length = _length(tokens, pos)
                kids.append((child, length))
                if pos[0] >= len(tokens):
                    raise ValueError("unbalanced parentheses")
                if tokens[pos[0]] == ",":
                    pos[0] += 1
                    continue
                if tokens[pos[0]] == ")":
                    pos[0] += 1
                    break
                raise ValueError("unexpected token %r" % tokens[pos[0]])
            label = ""
            if pos[0] < len(tokens) and tokens[pos[0]] not in ("(", ")", ",", ":"):
                label = tokens[pos[0]]
                pos[0] += 1
            nodes.append((label, kids))
            return len(nodes) - 1
        if token in (")", ",", ":"):
            raise ValueError("unexpected token %r" % token)
        pos[0] += 1
        nodes.append((token, []))
        return len(nodes) - 1

    root = parse_subtree()
    if pos[0] < len(tokens) and tokens[pos[0]] == ":":
        pos[0] += 1
        _length(tokens, pos)
    if pos[0] != len(tokens):
        raise ValueError("trailing characters in newick")
    leaves = [i for i, (label, kids) in enumerate(nodes) if not kids]
    labels_found = sorted(nodes[i][0] for i in leaves)
    if labels_found != list(TAXA):
        raise ValueError("tree must carry exactly the taxa %s once each" % (TAXA,))
    order = sorted(leaves, key=lambda i: nodes[i][0]) + [i for i, (l, k) in enumerate(nodes) if k]
    index = {node: pos_ for pos_, node in enumerate(order)}
    labels = {index[i]: nodes[i][0] for i in leaves}
    adjacency = {index[i]: [] for i in range(len(nodes))}
    for i, (label, kids) in enumerate(nodes):
        for child, length in kids:
            if length is None:
                raise ValueError("every branch needs a length")
            adjacency[index[i]].append((index[child], length))
            adjacency[index[child]].append((index[i], length))
    if rooted:
        return labels, adjacency
    root_index = index[root]
    if len(adjacency[root_index]) == 2:
        (a, la), (b, lb) = adjacency[root_index]
        adjacency[a] = [(n, l) for n, l in adjacency[a] if n != root_index] + [(b, la + lb)]
        adjacency[b] = [(n, l) for n, l in adjacency[b] if n != root_index] + [(a, la + lb)]
        del adjacency[root_index]
    elif len(adjacency[root_index]) < 2:
        raise ValueError("degenerate root")
    return labels, adjacency


def _tokenize(s):
    tokens = []
    buffer = ""
    for ch in s:
        if ch in "(),:":
            if buffer.strip():
                tokens.append(buffer.strip())
            buffer = ""
            tokens.append(ch)
        elif ch.isspace():
            continue
        else:
            buffer += ch
    if buffer.strip():
        tokens.append(buffer.strip())
    return tokens


def _length(tokens, pos):
    if pos[0] >= len(tokens):
        raise ValueError("missing branch length")
    try:
        value = float(tokens[pos[0]])
    except ValueError:
        raise ValueError("branch length %r is not a number" % tokens[pos[0]])
    if not math.isfinite(value):
        raise ValueError("branch length must be finite")
    pos[0] += 1
    return value


def canonical_split(mask):
    """The side of a bipartition that does not contain taxon 0."""
    mask &= FULL_MASK
    return (FULL_MASK ^ mask) if mask & 1 else mask


def nontrivial(mask):
    count = bin(mask).count("1")
    return 2 <= count <= N_TAXA - 2


def splits_of(adjacency):
    """Nontrivial bipartitions of an unrooted adjacency, mapped to their branch lengths."""
    splits = {}
    seen = set()
    for node in adjacency:
        for nbr, length in adjacency[node]:
            key = (min(node, nbr), max(node, nbr))
            if key in seen:
                continue
            seen.add(key)
            mask = _side_mask(adjacency, nbr, node)
            mask = canonical_split(mask)
            if nontrivial(mask):
                if mask in splits:
                    raise ValueError("tree contains a duplicated split")
                splits[mask] = float(length)
    return splits


def _side_mask(adjacency, start, blocked):
    mask = 0
    stack = [(start, blocked)]
    while stack:
        node, parent = stack.pop()
        if node < N_TAXA:
            mask |= 1 << node
        for nbr, _ in adjacency[node]:
            if nbr != parent:
                stack.append((nbr, node))
    return mask


def quartet_topology(splits, quartet):
    """0 for ab|cd, 1 for ac|bd, 2 for ad|bc, -1 if the tree does not resolve the quartet."""
    a, b, c, d = quartet
    for mask in splits:
        inside = [(mask >> t) & 1 for t in (a, b, c, d)]
        if sum(inside) != 2:
            continue
        if inside[0] == inside[1]:
            return 0
        if inside[0] == inside[2]:
            return 1
        return 2
    return -1


def quartet_signature(splits):
    return np.array([quartet_topology(splits, q) for q in QUARTETS], dtype=np.int8)


def same_topology(splits_a, splits_b):
    return set(splits_a) == set(splits_b)


_TOPOLOGY_TABLE = None


def all_topologies():
    """Every unrooted binary tree on the eight taxa as (list of split sets, quartet table).

    Built once by stepwise addition. 10395 trees; the table is (10395, 70) of topology indices.
    """
    global _TOPOLOGY_TABLE
    if _TOPOLOGY_TABLE is not None:
        return _TOPOLOGY_TABLE
    trees = [[(0, 8), (1, 8), (2, 8)]]
    next_internal = 9
    for taxon in range(3, N_TAXA):
        grown = []
        for edges in trees:
            for k, (u, v) in enumerate(edges):
                w = next_internal
                new = edges[:k] + edges[k + 1:] + [(u, w), (w, v), (w, taxon)]
                grown.append(new)
        trees = grown
        next_internal += 1
    split_sets = []
    table = np.zeros((len(trees), len(QUARTETS)), dtype=np.int8)
    for row, edges in enumerate(trees):
        adjacency = {}
        for u, v in edges:
            adjacency.setdefault(u, []).append((v, 1.0))
            adjacency.setdefault(v, []).append((u, 1.0))
        splits = splits_of(adjacency)
        split_sets.append(frozenset(splits))
        table[row] = quartet_signature(splits)
    _TOPOLOGY_TABLE = (split_sets, table)
    return _TOPOLOGY_TABLE


def splits_to_newick(splits, labels=TAXA):
    """Build newick from a compatible set of nontrivial splits with lengths (pendant edges 0)."""
    # Grow the tree by inserting splits from smallest clade to largest.
    masks = sorted(splits, key=lambda m: bin(m).count("1"))
    # Start with a star.
    center = N_TAXA
    adjacency = {center: []}
    for t in range(N_TAXA):
        adjacency[t] = [(center, 0.0)]
        adjacency[center].append((t, 0.0))
    next_node = N_TAXA + 1
    for mask in masks:
        members = [t for t in range(N_TAXA) if (mask >> t) & 1]
        # The node whose neighbourhood currently holds all members on distinct edges.
        node = _node_holding(adjacency, members)
        new = next_node
        next_node += 1
        moving = []
        for nbr, length in adjacency[node]:
            side = _side_mask(adjacency, nbr, node)
            if side & mask and not (side & ~mask & FULL_MASK):
                moving.append((nbr, length))
        adjacency[node] = [(n, l) for n, l in adjacency[node] if (n, l) not in moving]
        adjacency[new] = list(moving) + [(node, splits[mask])]
        for nbr, length in moving:
            adjacency[nbr] = [(n, l) if n != node else (new, l) for n, l in adjacency[nbr]]
        adjacency[node].append((new, splits[mask]))
    return unrooted_newick(adjacency, labels)


def _node_holding(adjacency, members):
    target = sum(1 << t for t in members)
    for node in adjacency:
        if node < N_TAXA:
            continue
        sides = [_side_mask(adjacency, nbr, node) for nbr, _ in adjacency[node]]
        covered = 0
        for side in sides:
            if side & target and not (side & ~target & FULL_MASK):
                covered |= side
        if covered == target:
            return node
    raise ValueError("splits are not compatible")


def branch_length_quartets(splits, mask):
    """Quartets whose induced path is exactly the branch `mask`: one taxon from each of the two
    subtrees on either side. Returns (list of quartet indices, dominant topology per quartet)."""
    # Sides adjacent to the branch: find the two splits on each side that partition it.
    side_a = mask
    side_b = FULL_MASK ^ mask
    parts_a = _adjacent_parts(splits, side_a)
    parts_b = _adjacent_parts(splits, side_b)
    result = []
    for pa1, pa2 in itertools.combinations(parts_a, 2):
        for pb1, pb2 in itertools.combinations(parts_b, 2):
            for a in _members(pa1):
                for b in _members(pa2):
                    for c in _members(pb1):
                        for d in _members(pb2):
                            quartet = tuple(sorted((a, b, c, d)))
                            topo = quartet_topology(splits, quartet)
                            result.append((QUARTET_INDEX[quartet], topo))
    return result


def _adjacent_parts(splits, side):
    """The maximal proper sub-clades of `side` among the tree's clades, plus singletons."""
    candidates = []
    for mask in list(splits) + [1 << t for t in range(N_TAXA)]:
        for oriented in (mask, FULL_MASK ^ mask):
            if oriented & ~side & FULL_MASK:
                continue
            if oriented == side or oriented == 0:
                continue
            candidates.append(oriented)
    candidates = sorted(set(candidates), key=lambda m: -bin(m).count("1"))
    parts = []
    covered = 0
    for m in candidates:
        if m & covered:
            continue
        parts.append(m)
        covered |= m
    return parts


def _members(mask):
    return [t for t in range(N_TAXA) if (mask >> t) & 1]
