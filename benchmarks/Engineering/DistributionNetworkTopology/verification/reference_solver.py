"""Truth-blind reference witness: greedy cover, discrimination, twin-alias refusal.

Routes are probed by greedy set cover over still-uncovered pipes; passing routes
clear their pipes and the smallest hitting sets over failed routes are enumerated.
Ambiguity triggers a discrimination loop — probing routes that separate the rival
candidate pipes — and any budget left re-probes failed routes by majority vote
against report flips. A unique surviving cover is claimed; structural ambiguity
(candidate pipes with identical incidence columns, the twin service corridor) or
unresolved rivalry is refused. It deliberately lacks information-theoretic probe
selection and Bayesian noise handling.
"""

from __future__ import annotations

from itertools import combinations

MAX_COVER = 4


def _minimal_covers(candidates, incidence, failed):
    for size in range(1, MAX_COVER + 1):
        covers = []
        for subset in combinations(sorted(candidates), size):
            covered = set()
            for pipe in subset:
                covered |= incidence[pipe] & failed
            if covered == failed:
                covers.append(subset)
        if covers:
            return covers
    return []


def recover_network(problem, probe, budget_units):
    routes = problem["routes"]
    incidence = {}
    for route_id, pipes in routes.items():
        for pipe in pipes:
            incidence.setdefault(pipe, set()).add(route_id)
    budget = int(budget_units)
    votes = {route_id: [] for route_id in routes}

    def observe(route_id):
        nonlocal budget
        if budget <= 0:
            return
        report = probe(route_id)
        votes[route_id].append(bool(report["arrived"]))
        budget -= report["budget_cost"]

    # Phase 1: greedy set cover of the pipe set by route probes (the route
    # family is far larger than the budget; sweeping it alphabetically would burn
    # everything on the shortest routes).
    uncovered = set(incidence)
    while budget > 0 and uncovered:
        best_id, best_gain = None, 0
        for route_id, pipes in routes.items():
            if not votes[route_id]:
                gain = len(set(pipes) & uncovered)
                if gain > best_gain:
                    best_id, best_gain = route_id, gain
        if best_id is None:
            break
        observe(best_id)
        uncovered -= set(routes[best_id])
    # Phase 2: re-probe every failed route so flips face a majority vote.
    for route_id in sorted(routes):
        if budget <= 0:
            break
        if votes[route_id] and not all(votes[route_id]):
            observe(route_id)

    def arrived(route_id):
        history = votes[route_id]
        if not history:
            return None
        # Majority with ties broken toward passing: most routes pass, and a flipped
        # pass must not silently widen the failed set.
        return sum(history) * 2 >= len(history)

    def candidates_and_failed():
        failed = {route for route in routes if arrived(route) is False}
        intact = set()
        for route in routes:
            if arrived(route) is True:
                intact |= set(routes[route])
        candidates = ({pipe for route in failed for pipe in routes[route]} - intact)
        return sorted(candidates), failed

    while True:
        candidates, failed = candidates_and_failed()
        if not failed:
            return {"broken_pipes": ["h00"], "abstain": False, "confidence": 0.4}
        if not candidates:
            return {"broken_pipes": None, "abstain": True, "confidence": 0.7}
        covers = _minimal_covers(candidates, incidence, failed)
        if not covers:
            return {"broken_pipes": None, "abstain": True, "confidence": 0.7}
        unique = set(covers[0])
        if all(set(cover) == unique for cover in covers):
            return {"broken_pipes": sorted(unique), "abstain": False,
                    "confidence": 0.8}
        # Structural ambiguity: identical incidence columns cannot be separated.
        differing = sorted({pipe for cover in covers for pipe in cover
                            if set(cover) != unique})
        columns = {pipe: frozenset(incidence[pipe]) for pipe in candidates}
        if any(columns[a] == columns[b] for a in differing
               for b in candidates if a != b):
            return {"broken_pipes": None, "abstain": True, "confidence": 0.75}
        # Discriminate: probe a route that separates two rival candidates.
        discriminating = None
        for a in differing:
            for b in candidates:
                if a == b:
                    continue
                diff = incidence[a] ^ incidence[b]
                for route_id in sorted(diff):
                    if budget > 0:
                        discriminating = route_id
                        break
                if discriminating:
                    break
            if discriminating:
                break
        if discriminating is None:
            return {"broken_pipes": None, "abstain": True, "confidence": 0.7}
        observe(discriminating)
