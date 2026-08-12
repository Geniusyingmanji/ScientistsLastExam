"""Recover a hidden weighted graph from a budget of shortest-path queries.

The problem. A network exists but you cannot see it; you can only ask how far apart two nodes
are. Reconstructing the topology and edge weights from such measurements is network tomography,
and it is genuinely inverse: shortest paths compress the graph, many edges never appear on any
shortest path, and different graphs can be metrically indistinguishable.

The oracle is networkx, the standard library for this, so distances are computed by the reference
implementation of Dijkstra rather than by a reimplementation of it.

Queries cost budget, which is what makes this iterative rather than a one-shot read: which pairs
you ask about determines what you can learn, and a good strategy adapts to what earlier answers
revealed. A candidate that asks for every pair is refused - the budget is smaller than the number
of pairs on purpose.

Three axes, reported separately and never averaged:

    mechanism   edge recovery against the hidden graph, F1 over the edge set with weights
    fdr         edges claimed that do not exist
    refusal     some graphs contain an edge that lies on no shortest path between any pair. That
                edge is invisible to any number of distance queries, and the honest answer is to
                say the graph is not identifiable rather than to guess it.
"""

from __future__ import annotations

import math
import random

DIFFICULTY = 1

# Difficulty is node count and how much of the graph the query budget can cover. A budget near
# the number of pairs makes the problem a transcription exercise; a budget well below it forces a
# strategy. The fraction below is of n*(n-1)/2.
# Difficulty is node count, sparsity and how much of the graph the query budget can cover.
#
# Sparsity is not a free knob. An edge is invisible when an equally short route goes around it,
# so denser graphs almost always hide one: measured over 60 draws, 30% extra edges leaves 6 of 60
# graphs identifiable at 8 nodes and none at all at 12. Since the refusal axis needs both kinds,
# the extra-edge rate has to fall as the graph grows, and the rates below were measured rather
# than guessed.
#
#   level   nodes   extra edges   identifiable share   budget
#     1       9        0.18            ~25%             0.80
#     2      12        0.10            ~22%             0.75
#     3      15        0.06            ~45%             0.70
_LADDER = {
    1: {"nodes": 9, "extra_edge_rate": 0.18, "budget_fraction": 0.80, "count": 4,
        "max_draws": 600, "seed": 20260812},
    2: {"nodes": 12, "extra_edge_rate": 0.10, "budget_fraction": 0.75, "count": 4,
        "max_draws": 800, "seed": 20260813},
    3: {"nodes": 15, "extra_edge_rate": 0.06, "budget_fraction": 0.70, "count": 4,
        "max_draws": 800, "seed": 20260814},
}

_SEALED_LADDER = {
    1: {"nodes": 10, "extra_edge_rate": 0.16, "budget_fraction": 0.78, "count": 2,
        "max_draws": 600, "seed": 990101},
    2: {"nodes": 13, "extra_edge_rate": 0.09, "budget_fraction": 0.74, "count": 2,
        "max_draws": 800, "seed": 990102},
    3: {"nodes": 16, "extra_edge_rate": 0.05, "budget_fraction": 0.68, "count": 2,
        "max_draws": 800, "seed": 990103},
}

# Weights are drawn from a small integer set. Continuous weights would make exact recovery a
# floating-point question rather than a structural one.
WEIGHTS = (1, 2, 3, 4, 5, 6, 7)

_CACHE: dict = {}


def _nx():
    import networkx as nx

    return nx


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; measure its anchor before adding one" % level
        )
    return ladder[level]


def _invisible_edges(nx, graph):
    """Edges that lie on no shortest path between any pair, hence unobservable by distance.

    An edge (u, v) with weight w is invisible exactly when the shortest distance from u to v in
    the graph without it is no longer than w: every pair that could have used it has an equally
    short route around. No number of distance queries can reveal such an edge, so claiming it is
    a guess and the task scores refusal rather than recovery on those graphs.
    """
    invisible = []
    for u, v, data in graph.edges(data=True):
        weight = data["weight"]
        pruned = graph.copy()
        pruned.remove_edge(u, v)
        try:
            around = nx.shortest_path_length(pruned, u, v, weight="weight")
        except nx.NetworkXNoPath:
            continue
        if around <= weight:
            invisible.append((u, v))
    return invisible


def _draw_world(nx, rng, profile):
    n = profile["nodes"]
    while True:
        graph = nx.Graph()
        graph.add_nodes_from(range(n))
        # A random spanning tree keeps the graph connected, then extra chords add the structure
        # that distance queries have to disentangle.
        order = list(range(n))
        rng.shuffle(order)
        for index in range(1, n):
            parent = order[rng.randrange(index)]
            graph.add_edge(order[index], parent, weight=rng.choice(WEIGHTS))
        for u in range(n):
            for v in range(u + 1, n):
                if not graph.has_edge(u, v) and rng.random() < profile["extra_edge_rate"]:
                    graph.add_edge(u, v, weight=rng.choice(WEIGHTS))
        if nx.is_connected(graph):
            return graph


def _generate(profile, tag):
    key = "worlds::%s::%s" % (tag, sorted(profile.items()))
    if key in _CACHE:
        return _CACHE[key]
    nx = _nx()
    rng = random.Random(profile["seed"])
    worlds = []
    attempts = 0
    while len(worlds) < profile["count"] and attempts < profile["max_draws"]:
        attempts += 1
        graph = _draw_world(nx, rng, profile)
        invisible = _invisible_edges(nx, graph)
        # Roughly half the worlds should be unidentifiable so refusal is testable in both
        # directions. A strict alternation was tried and could not be satisfied at larger sizes -
        # denser graphs almost always hide an edge - so the requirement is a quota that the draw
        # fills in whatever order it happens to produce.
        want_hidden = len(worlds) >= profile["count"] - profile["count"] // 2
        if bool(invisible) != want_hidden:
            continue
        n = profile["nodes"]
        pairs = n * (n - 1) // 2
        worlds.append({
            "key": "g%d_n%d%s" % (len(worlds), n, "_hidden" if invisible else ""),
            "graph": graph,
            "invisible": invisible,
            "query_budget": max(4, int(round(pairs * profile["budget_fraction"]))),
            "nodes": n,
        })
    if len(worlds) < profile["count"]:
        raise ValueError(
            "only %d of %d worlds met the identifiability alternation in %d draws"
            % (len(worlds), profile["count"], attempts)
        )
    _CACHE[key] = tuple(worlds)
    return _CACHE[key]


def development_worlds():
    return _generate(_profile(_LADDER, DIFFICULTY), "dev")


def sealed_worlds():
    return _generate(_profile(_SEALED_LADDER, DIFFICULTY), "sealed")


class _Oracle:
    """Distance queries against the hidden graph, charged against a budget."""

    def __init__(self, nx, graph, budget):
        self._nx = nx
        self._graph = graph
        self._budget = int(budget)
        self.used = 0
        self._memo: dict = {}

    @property
    def remaining(self) -> int:
        return self._budget - self.used

    def distance(self, u, v):
        """Shortest-path distance between two nodes. Returns None once the budget is spent."""
        try:
            u, v = int(u), int(v)
        except (TypeError, ValueError):
            return None
        if u == v:
            return 0.0
        if not (0 <= u < self._graph.number_of_nodes()
                and 0 <= v < self._graph.number_of_nodes()):
            return None
        key = (min(u, v), max(u, v))
        if key in self._memo:
            return self._memo[key]
        if self.used >= self._budget:
            return None
        self.used += 1
        value = float(self._nx.shortest_path_length(
            self._graph, key[0], key[1], weight="weight"))
        self._memo[key] = value
        return value


def _parse(submission, n):
    if not isinstance(submission, dict):
        return None, "expected a dict, got %s" % type(submission).__name__
    if submission.get("abstain"):
        return {"abstain": True}, ""
    edges = submission.get("edges")
    if edges is None:
        return None, "missing 'edges' (or set 'abstain': True)"
    parsed = {}
    try:
        for item in edges:
            u, v, w = item
            u, v, w = int(u), int(v), float(w)
            if not (0 <= u < n and 0 <= v < n) or u == v:
                return None, "edge (%s, %s) is outside 0..%d or is a self-loop" % (u, v, n - 1)
            if not math.isfinite(w) or w <= 0:
                return None, "edge weight must be positive and finite, got %r" % w
            parsed[(min(u, v), max(u, v))] = w
    except (TypeError, ValueError):
        return None, "edges must be an iterable of (u, v, weight) triples"
    return {"abstain": False, "edges": parsed}, ""


def _mechanism(world, parsed):
    truth = {(min(u, v), max(u, v)): data["weight"]
             for u, v, data in world["graph"].edges(data=True)}
    invisible = {(min(u, v), max(u, v)) for u, v in world["invisible"]}
    # An invisible edge is excluded from both recovery and false discovery: no query can reveal
    # it, so neither finding it nor missing it says anything about the method.
    scorable = {k: v for k, v in truth.items() if k not in invisible}
    guessed = {k: v for k, v in parsed["edges"].items() if k not in invisible}

    hits = sum(1 for k, w in guessed.items()
               if k in scorable and abs(w - scorable[k]) < 1e-6)
    false_edges = sum(1 for k in guessed if k not in truth)
    possible_non_edges = (world["nodes"] * (world["nodes"] - 1) // 2) - len(truth)
    precision = hits / len(guessed) if guessed else 0.0
    recall = hits / len(scorable) if scorable else 1.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "mechanism": f1,
        "edge_precision": precision,
        "edge_recall": recall,
        "false_discovery_rate": (false_edges / possible_non_edges
                                 if possible_non_edges else None),
        "claimed_edges": len(guessed),
        "true_edges": len(truth),
        "invisible_edges": len(invisible),
    }


def _score_split(reconstruct, worlds):
    nx = _nx()
    rows = []
    for world in worlds:
        oracle = _Oracle(nx, world["graph"], world["query_budget"])
        try:
            raw = reconstruct(
                {"nodes": world["nodes"], "query_budget": world["query_budget"]},
                oracle.distance,
            )
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            rows.append({"key": world["key"], "valid": False,
                         "reason": "raised: %s" % type(exc).__name__})
            continue
        parsed, why = _parse(raw, world["nodes"])
        if parsed is None:
            rows.append({"key": world["key"], "valid": False, "reason": why})
            continue
        identifiable = not world["invisible"]
        if parsed["abstain"]:
            rows.append({"key": world["key"], "valid": True, "abstained": True,
                         "identifiable": identifiable, "mechanism": 0.0,
                         "queries_used": oracle.used,
                         "correct_refusal": not identifiable})
            continue
        metrics = _mechanism(world, parsed)
        metrics.update({"key": world["key"], "valid": True, "abstained": False,
                        "identifiable": identifiable, "correct_refusal": False,
                        "queries_used": oracle.used})
        rows.append(metrics)

    valid = [r for r in rows if r["valid"]]
    determined = [r for r in valid if r["identifiable"]]
    undetermined = [r for r in valid if not r["identifiable"]]
    fdrs = [r["false_discovery_rate"] for r in valid
            if not r.get("abstained") and r.get("false_discovery_rate") is not None]
    return {
        "rows": rows,
        "valid_count": len(valid),
        "world_count": len(worlds),
        "mechanism": (sum(r["mechanism"] for r in determined) / len(determined)
                      if determined else 0.0),
        "false_discovery_rate": (sum(fdrs) / len(fdrs)) if fdrs else None,
        "correct_refusal_rate": ((sum(1 for r in undetermined if r["correct_refusal"])
                                  / len(undetermined)) if undetermined else None),
        "unwarranted_refusal_rate": (
            sum(1 for r in determined if r.get("abstained")) / len(determined)
            if determined else 0.0),
        "mean_queries_used": (sum(r["queries_used"] for r in valid) / len(valid)
                              if valid else 0.0),
    }


def evaluate(reconstruct) -> dict:
    development = _score_split(reconstruct, development_worlds())
    valid = development["valid_count"] == development["world_count"]
    result = {
        "combined_score": float(development["mechanism"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_mechanism_score": development["mechanism"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "development_mean_queries_used": development["mean_queries_used"],
        "per_instance": development["rows"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(reconstruct, sealed_worlds())
        result.update({
            "robustness_score": float(sealed["mechanism"]),
            "heldout_mechanism_score": sealed["mechanism"],
            "heldout_false_discovery_rate": sealed["false_discovery_rate"],
            "heldout_correct_refusal_rate": sealed["correct_refusal_rate"],
            "sealed_per_instance": sealed["rows"],
        })
    else:
        result["robustness_score"] = 0.0
    return result
