"""Weak but valid baseline for AnomalyZoneSpeciesTree.

It does what the catalogue invites. Fast loci have the most variable sites and long loci the
best-resolved gene trees, so it buys the longest fast loci until the budget runs out,
concatenates them into one alignment, computes Jukes-Cantor distances on the whole thing and
builds one neighbour-joining tree - the classic "total evidence" analysis. Its internal branch
lengths are reported as they come out, in substitutions per site, as if that were a coalescent
unit. It never declines: every set of loci gets a tree, with confidence.

Three things are wrong with it. Concatenation is inconsistent in the anomaly zone. The plain
Jukes-Cantor distance ignores the published rate variation across sites, and on the fastest,
longest loci that omission is largest, so the two fast-evolving species are pulled together. And
a hybrid species gets a tree like everything else.
"""
from __future__ import annotations

import numpy as np


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


def _newick(adjacency, labels):
    root = max(adjacency)

    def render(node, parent):
        kids = [(nbr, length) for nbr, length in adjacency[node] if nbr != parent]
        if not kids:
            return labels[node]
        return "(" + ",".join("%s:%.6f" % (render(nbr, node), length) for nbr, length in kids) + ")"

    return render(root, None) + ";"


def infer_species_tree(problem, sequence):
    taxa = list(problem["taxa"])
    budget = int(problem["locus_budget"])
    order = sorted(problem["catalogue"],
                   key=lambda row: (row["rate_class"] != "fast", -int(row["sites"]), int(row["locus"])))
    spent = 0
    pieces = {t: [] for t in taxa}
    for row in order:
        cost = int(row["cost"])
        if spent + cost > budget:
            continue
        try:
            locus = sequence(int(row["locus"]))
        except Exception:
            break
        spent += cost
        for t in taxa:
            pieces[t].append(locus["alignment"][t])
    if not pieces[taxa[0]]:
        return {"verdict": "reticulate", "confidence": 0.1}
    concatenated = np.array([list("".join(pieces[t])) for t in taxa])
    n = len(taxa)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            p = float(np.mean(concatenated[i] != concatenated[j]))
            d[i, j] = d[j, i] = -0.75 * np.log(max(1e-9, 1.0 - 4.0 * p / 3.0)) if p < 0.75 else 10.0
    tree = _neighbour_joining(d)
    return {"verdict": "tree", "newick": _newick(tree, taxa), "confidence": 0.9}
