"""Truth-blind reference for AnomalyZoneSpeciesTree: re-estimate every gene tree under the
published model, assemble the species tree from quartet majorities, read branch lengths off the
quartet frequencies, and decline when the minority quartets are too unequal for any tree.

Reads only the public problem and the budgeted sequencing campaign. The ideas it is built on:

    loci        buy slow loci of 800 sites. The slow class is the least saturated, so the gamma
                correction has the least to repair there and its corrected trees recover the most
                true splits per locus; 800 sites at cost two buys five hundred loci. An
                anomaly-zone world needs that many: two hundred and forty true gene trees pick
                its species tree only about nineteen times in twenty.
    shape       the sites evolve with gamma-distributed rates whose shape is not published.
                Pairwise comparisons cannot see it, so it is read from a joint statistic: the
                share of sites that are constant across all eight sequences. For each candidate
                shape, the distances are corrected with it, a tree is built, and the share of
                constant sites that tree predicts under that shape (the gamma integral done by
                generalised Gauss-Laguerre quadrature) is compared with the observed share,
                pooled over the first sixty loci; the shape that matches is kept.
    gene trees  the oracle's neighbour-joining tree is discarded. It uses the plain Jukes-Cantor
                distance, so the distances are recomputed with the gamma correction at the
                estimated shape and neighbour joining is run again. Without this the two
                fast-evolving species attract each other, and - worse - the attraction is a
                systematic imbalance between minority quartet topologies, which is exactly the
                signature of reticulation.
    topology    count the three topologies of every quartet across the gene trees and pick the
                one of the 10395 unrooted eight-taxon trees that agrees with the most quartet
                observations. No quartet is anomalous under the coalescent, so this is
                consistent where the most frequent gene tree, the greedy consensus and
                concatenation are not.
    refusal     under any species tree the two minority topologies of a quartet have equal
                probability. For each species, sum (n1 - n2)^2 / (n1 + n2) over the 35 quartets
                that contain it; a hybrid species lifts this far above what sampling alone does.
    lengths     an internal branch of t coalescent units gives its quartets a majority topology
                with probability 1 - (2/3) exp(-t); invert that on the median frequency over the
                quartets whose path is exactly that branch.

Deliberately not at the ceiling. Three things are left: the gene trees are distance trees, and
every quartet is counted with the same weight whether the gene tree resolved it well or barely;
the branch-length inversion ignores gene-tree estimation error, which flattens the frequencies
towards a third and biases every length downward; and the refusal is a fixed threshold on one
statistic rather than a test of the fitted tree against the whole quartet spectrum.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

CHOSEN_CLASS = "slow"
CHOSEN_SITES = 800
SHAPE_GRID = (0.15, 0.18, 0.22, 0.26, 0.31, 0.37, 0.44, 0.52, 0.62, 0.74, 0.88, 1.05, 1.25, 1.5, 1.8, 2.2)
SHAPE_LOCI = 60
QUADRATURE_NODES = 12
REFUSAL_STATISTIC = 260.0
MIN_LENGTH = 0.01
PENDANT_LENGTH = 1.0
SATURATED = 10.0


# ----------------------------------------------------------------------------------------------
# distances and neighbour joining
# ----------------------------------------------------------------------------------------------

def _encode(alignment, taxa):
    table = {"A": 0, "C": 1, "G": 2, "T": 3}
    return np.array([[table.get(ch, 0) for ch in alignment[t]] for t in taxa], dtype=np.int8)


def _gamma_distances(seqs, shape):
    n = seqs.shape[0]
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            p = float(np.mean(seqs[i] != seqs[j]))
            if p >= 0.75:
                value = SATURATED
            else:
                value = 0.75 * shape * ((1.0 - 4.0 * p / 3.0) ** (-1.0 / shape) - 1.0)
            d[i, j] = d[j, i] = value
    return d


def _neighbour_joining(distance):
    d = np.array(distance, dtype=float)
    n = d.shape[0]
    active = list(range(n))
    adjacency = {i: [] for i in range(n)}
    nxt = n
    while len(active) > 2:
        m = len(active)
        sub = d[np.ix_(active, active)]
        totals = sub.sum(axis=1)
        q = (m - 2) * sub - totals[:, None] - totals[None, :]
        np.fill_diagonal(q, np.inf)
        i, j = divmod(int(np.argmin(q)), m)
        if i > j:
            i, j = j, i
        a, b = active[i], active[j]
        dij = sub[i, j]
        la = max(0.5 * dij + (totals[i] - totals[j]) / (2.0 * (m - 2)), 0.0)
        lb = max(dij - la, 0.0)
        u = nxt
        nxt += 1
        adjacency[u] = [(a, la), (b, lb)]
        adjacency[a].append((u, la))
        adjacency[b].append((u, lb))
        d = np.pad(d, ((0, 1), (0, 1)))
        for k in active:
            if k not in (a, b):
                d[u, k] = d[k, u] = 0.5 * (d[a, k] + d[b, k] - dij)
        active = [k for k in active if k not in (a, b)] + [u]
    a, b = active
    adjacency[a].append((b, max(float(d[a, b]), 0.0)))
    adjacency[b].append((a, max(float(d[a, b]), 0.0)))
    return adjacency


# ----------------------------------------------------------------------------------------------
# the site-rate shape, from the share of constant sites
# ----------------------------------------------------------------------------------------------

def _gamma_quadrature(shape, nodes):
    """Nodes and weights integrating f(r) against the Gamma(shape, 1/shape) density: generalised
    Gauss-Laguerre with weight x^(shape-1) e^(-x), by the Golub-Welsch eigenvalue construction."""
    beta = shape - 1.0
    k = np.arange(nodes)
    diagonal = 2.0 * k + beta + 1.0
    off = np.sqrt((k[1:]) * (k[1:] + beta))
    values, vectors = np.linalg.eigh(np.diag(diagonal) + np.diag(off, 1) + np.diag(off, -1))
    weights = vectors[0] ** 2  # already normalised so the weights sum to one
    return values / shape, weights


def _constant_site_probability(adjacency, shape):
    """Probability under Jukes-Cantor with gamma rates of the given shape that a site is the same
    nucleotide in all N leaves of the tree, by pruning at every quadrature node."""
    rates, weights = _gamma_quadrature(shape, QUADRATURE_NODES)
    root = max(adjacency)
    order = []
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        order.append((node, parent))
        for nbr, _ in adjacency[node]:
            if nbr != parent:
                stack.append((nbr, node))
    lengths = {}
    for node, parent in order:
        if parent is not None:
            lengths[node] = next(length for nbr, length in adjacency[node] if nbr == parent)
    total = 0.0
    for rate, weight in zip(rates, weights):
        # partial[node] = (same, other): probability of the all-A pattern below the node given the
        # node is A, and given it is one of the three other states.
        partial = {}
        for node, parent in reversed(order):
            if node < N:
                partial[node] = (1.0, 0.0)
            else:
                same = other = 1.0
                for nbr, length in adjacency[node]:
                    if nbr == parent:
                        continue
                    kid_same, kid_other = partial[nbr]
                    e = math.exp(-4.0 / 3.0 * max(length, 0.0) * rate)
                    p_stay = 0.25 + 0.75 * e
                    p_move = 0.25 - 0.25 * e
                    same *= p_stay * kid_same + 3.0 * p_move * kid_other
                    other *= p_move * kid_same + (p_stay + 2.0 * p_move) * kid_other
                partial[node] = (same, other)
        root_same, root_other = partial[root]
        total += weight * (0.25 * root_same + 0.75 * root_other)
    return 4.0 * total


def _estimate_shape(loci):
    """The grid shape whose corrected-distance trees predict the observed share of constant sites."""
    observed = sum(int(np.sum(np.all(seqs == seqs[0], axis=0))) for seqs in loci)
    sites = sum(seqs.shape[1] for seqs in loci)
    best, best_error = SHAPE_GRID[0], math.inf
    for shape in SHAPE_GRID:
        predicted = 0.0
        for seqs in loci:
            adjacency = _neighbour_joining(_gamma_distances(seqs, shape))
            predicted += _constant_site_probability(adjacency, shape) * seqs.shape[1]
        error = abs(math.log(max(predicted, 1e-9) / max(float(observed), 1e-9)))
        if error < best_error:
            best, best_error = shape, error
    return best, observed / float(sites), best_error


# ----------------------------------------------------------------------------------------------
# splits and quartets
# ----------------------------------------------------------------------------------------------

N = 8
FULL = (1 << N) - 1
QUARTETS = tuple(itertools.combinations(range(N), 4))


def _side(adjacency, start, blocked):
    mask = 0
    stack = [(start, blocked)]
    while stack:
        node, parent = stack.pop()
        if node < N:
            mask |= 1 << node
        for nbr, _ in adjacency[node]:
            if nbr != parent:
                stack.append((nbr, node))
    return mask


def _canonical(mask):
    return (FULL ^ mask) if mask & 1 else mask


def _splits(adjacency):
    found = {}
    for node in adjacency:
        for nbr, length in adjacency[node]:
            if node < nbr:
                mask = _canonical(_side(adjacency, nbr, node))
                if 2 <= bin(mask).count("1") <= N - 2:
                    found[mask] = length
    return found


def _quartet_topology(splits, quartet):
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


def _all_trees():
    """Every unrooted binary tree on eight taxa by stepwise addition: edges, splits, quartets."""
    trees = [[(0, 8), (1, 8), (2, 8)]]
    nxt = 9
    for taxon in range(3, N):
        grown = []
        for edges in trees:
            for k, (u, v) in enumerate(edges):
                grown.append(edges[:k] + edges[k + 1:] + [(u, nxt), (nxt, v), (nxt, taxon)])
        trees = grown
        nxt += 1
    table = np.zeros((len(trees), len(QUARTETS)), dtype=np.int8)
    split_sets = []
    for row, edges in enumerate(trees):
        adjacency = {}
        for u, v in edges:
            adjacency.setdefault(u, []).append((v, 1.0))
            adjacency.setdefault(v, []).append((u, 1.0))
        splits = _splits(adjacency)
        split_sets.append(splits)
        table[row] = [_quartet_topology(splits, q) for q in QUARTETS]
    return trees, split_sets, table


# ----------------------------------------------------------------------------------------------
# branch lengths from quartet frequencies
# ----------------------------------------------------------------------------------------------

def _parts(splits, side):
    """Maximal clades strictly inside `side` (the subtrees hanging off the branch's endpoint)."""
    candidates = set()
    for mask in list(splits) + [1 << t for t in range(N)]:
        for oriented in (mask, FULL ^ mask):
            if oriented and oriented != side and not (oriented & ~side & FULL):
                candidates.add(oriented)
    parts, covered = [], 0
    for mask in sorted(candidates, key=lambda m: -bin(m).count("1")):
        if not mask & covered:
            parts.append(mask)
            covered |= mask
    return parts


def _members(mask):
    return [t for t in range(N) if (mask >> t) & 1]


def _branch_quartets(splits, mask):
    result = []
    for pa, pb in itertools.combinations(_parts(splits, mask), 2):
        for pc, pd in itertools.combinations(_parts(splits, FULL ^ mask), 2):
            for a in _members(pa):
                for b in _members(pb):
                    for c in _members(pc):
                        for d in _members(pd):
                            quartet = tuple(sorted((a, b, c, d)))
                            result.append((QUARTETS.index(quartet), _quartet_topology(splits, quartet)))
    return result


def _render(edges, lengths, labels):
    adjacency = {}
    for (u, v), length in zip(edges, lengths):
        adjacency.setdefault(u, []).append((v, length))
        adjacency.setdefault(v, []).append((u, length))
    root = max(adjacency)

    def render(node, parent):
        kids = [(nbr, length) for nbr, length in adjacency[node] if nbr != parent]
        if not kids:
            return labels[node]
        return "(" + ",".join("%s:%.6f" % (render(nbr, node), length) for nbr, length in kids) + ")"

    return render(root, None) + ";"


# ----------------------------------------------------------------------------------------------
# the candidate
# ----------------------------------------------------------------------------------------------

# Only world-independent quantities may be cached here: the 10395 trees and their quartet table.
# Anything read from a world (loci, shape, counts) must stay local to one call.
_CACHE = {}


def infer_species_tree(problem, sequence):
    taxa = list(problem["taxa"])
    budget = int(problem["locus_budget"])
    catalogue = problem["catalogue"]

    chosen = [row for row in catalogue
              if row["rate_class"] == CHOSEN_CLASS and int(row["sites"]) == CHOSEN_SITES]
    spent = 0
    bought = []
    for row in chosen:
        cost = int(row["cost"])
        if spent + cost > budget:
            break
        try:
            locus = sequence(int(row["locus"]))
        except Exception:
            break
        spent += cost
        bought.append(_encode(locus["alignment"], taxa))
    if not bought:
        return {"verdict": "reticulate", "confidence": 0.1}

    shape, _observed, _error = _estimate_shape(bought[:SHAPE_LOCI])
    counts = np.zeros((len(QUARTETS), 3))
    for seqs in bought:
        splits = _splits(_neighbour_joining(_gamma_distances(seqs, shape)))
        for q, quartet in enumerate(QUARTETS):
            topology = _quartet_topology(splits, quartet)
            if topology >= 0:
                counts[q, topology] += 1

    # Refusal: minority imbalance summed over the quartets containing each species.
    ordered = np.sort(counts, axis=1)[:, ::-1]
    imbalance = (ordered[:, 1] - ordered[:, 2]) ** 2 / np.maximum(1.0, ordered[:, 1] + ordered[:, 2])
    worst = 0.0
    for taxon in range(N):
        idx = [q for q, quartet in enumerate(QUARTETS) if taxon in quartet]
        worst = max(worst, float(imbalance[idx].sum()))
    if worst > REFUSAL_STATISTIC:
        return {"verdict": "reticulate", "confidence": 0.7}

    if "trees" not in _CACHE:
        _CACHE["trees"] = _all_trees()
    edges_list, split_sets, table = _CACHE["trees"]
    score = counts[np.arange(len(QUARTETS))[None, :], table].sum(axis=1)
    best = int(np.argmax(score))
    edges, splits = edges_list[best], split_sets[best]

    lengths = {}
    totals = counts.sum(axis=1)
    for mask in splits:
        estimates = []
        for q, topology in _branch_quartets(splits, mask):
            if totals[q] <= 0:
                continue
            p = counts[q, topology] / totals[q]
            estimates.append(max(MIN_LENGTH, -math.log(max(1e-9, 1.5 * (1.0 - p)))))
        lengths[mask] = float(np.median(estimates)) if estimates else MIN_LENGTH

    adjacency = {}
    for u, v in edges:
        adjacency.setdefault(u, []).append(v)
        adjacency.setdefault(v, []).append(u)
    rendered = []
    for u, v in edges:
        adj = {n: [(m, 1.0) for m in adjacency[n]] for n in adjacency}
        mask = _canonical(_side(adj, v, u))
        rendered.append(lengths.get(mask, PENDANT_LENGTH))
    return {"verdict": "tree", "newick": _render(edges, rendered, taxa), "confidence": 0.75}
