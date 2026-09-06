"""Truth-blind UPGMA plus rooted NNI hill-climb used to audit score headroom."""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def _upgma(problem):
    seq = problem["alignment"]
    n = len(seq)
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(i):
            distances[i, j] = distances[j, i] = sum(
                a != b for a, b in zip(seq[i], seq[j])
            ) / len(seq[i])
    merges = linkage(squareform(distances), method="average")
    nodes = {i: problem["taxa"][i] for i in range(n)}
    for k, row in enumerate(merges):
        nodes[n + k] = (nodes[int(row[0])], nodes[int(row[1])])
    return nodes[2 * n - 2]


def _fitch(tree, problem):
    sequences = dict(zip(problem["taxa"], problem["alignment"]))
    total = 0

    def visit(node, site):
        nonlocal total
        if isinstance(node, str):
            return {sequences[node][site]}
        left = visit(node[0], site)
        right = visit(node[1], site)
        overlap = left & right
        if overlap:
            return overlap
        total += 1
        return left | right

    for site in range(len(problem["alignment"][0])):
        visit(tree, site)
    return total


def _local_rotations(tree):
    """Generate rooted representations of NNI-adjacent unrooted topologies."""
    if isinstance(tree, str):
        return
    left, right = tree
    if not isinstance(left, str):
        a, b = left
        yield (a, (b, right))
        yield (b, (a, right))
    if not isinstance(right, str):
        a, b = right
        yield ((left, a), b)
        yield ((left, b), a)
    for replacement in _local_rotations(left):
        yield (replacement, right)
    for replacement in _local_rotations(right):
        yield (left, replacement)


def _newick(tree):
    if isinstance(tree, str):
        return tree
    return f"({_newick(tree[0])},{_newick(tree[1])})"


def build_tree(problem):
    tree = _upgma(problem)
    score = _fitch(tree, problem)
    while True:
        best_tree, best_score = tree, score
        for neighbor in _local_rotations(tree):
            candidate = _fitch(neighbor, problem)
            if candidate < best_score:
                best_tree, best_score = neighbor, candidate
        if best_score >= score:
            return _newick(tree) + ";"
        tree, score = best_tree, best_score
