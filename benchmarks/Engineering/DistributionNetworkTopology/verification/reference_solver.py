"""Truth-blind reference witness: likelihood-tracked hypothesis search.

Hypotheses are break sets of at most the published size; every probe updates a
log-likelihood under the published flip probability; the next route is chosen to
split the surviving plausible set as evenly as possible (an information-gain
greedy over the hypothesis set, not a fixed cover). A single surviving hypothesis
is claimed; structural survivors (candidates differing only in pipes with
identical route signatures, the twin corridor) and unresolvable ties are refused.
It deliberately lacks full entropy computation, adaptive re-planning after every
single observation, and Bayesian model averaging.
"""

from __future__ import annotations

import math
from itertools import combinations

MAX_HYPOTHESIS_SIZE = 2
EXTENSION_TRIGGER = -6.0  # flip penalties this heavy mean a bigger break set is live
DECISION_MARGIN = 3.0     # log-likelihood lead that settles a claim
RUNNER_UP_GAP = 5.5       # cluster of near-explanations tracked for refusal checks
COMPLEXITY_PENALTY = 0.7  # per extra broken pipe, so supersets never tie the truth


def recover_network(problem, probe, budget_units):
    routes = problem["routes"]
    incidence = {}
    for route_id, pipes in routes.items():
        for pipe in pipes:
            incidence.setdefault(pipe, set()).add(route_id)
    pipes = sorted(incidence)
    flip = 0.04  # the published order of magnitude; robust within 2-8 percent

    def build(size):
        space = [frozenset({pipe}) for pipe in pipes]
        if size >= 2:
            space += [frozenset(pair) for pair in combinations(pipes, 2)]
        if size >= 3:
            space += [frozenset(triple) for triple in combinations(pipes, 3)]
        return space

    hypotheses = build(MAX_HYPOTHESIS_SIZE)
    log_likelihood = {h: -COMPLEXITY_PENALTY * len(h) for h in hypotheses}
    probed = {}

    def best_and_runner_up():
        ranked = sorted(log_likelihood.values(), reverse=True)
        best = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else best - 100.0
        return best, runner

    budget = int(budget_units)
    while budget > 0:
        best, runner = best_and_runner_up()
        if best - runner >= DECISION_MARGIN:
            break  # the leader has settled the claim
        plausible = [h for h in hypotheses
                     if log_likelihood[h] >= best - RUNNER_UP_GAP]
        # Choose the unprobed route that best splits the plausible set.
        best_route, best_split = None, -1.0
        for route_id in routes:
            if route_id in probed:
                continue
            hits = sum(1 for h in plausible
                       if set(routes[route_id]) & set(h))
            misses = len(plausible) - hits
            split = min(hits, misses)
            if split > best_split:
                best_route, best_split = route_id, split
        if best_route is None or best_split <= 0:
            break
        report = probe(best_route)
        budget -= report["budget_cost"]
        arrived = bool(report["arrived"])
        probed[best_route] = arrived
        route_pipes = set(routes[best_route])
        for h in hypotheses:
            blocked = bool(route_pipes & set(h))
            agrees = (arrived and not blocked) or (not arrived and blocked)
            log_likelihood[h] += math.log(1.0 - flip) if agrees else math.log(flip)
        # Heavy flip penalties on every hypothesis mean the break set is bigger
        # than the current space allows; extend once.
        if max(log_likelihood.values()) < EXTENSION_TRIGGER \
                and MAX_HYPOTHESIS_SIZE < 3:
            extra = build(3)
            for h in extra:
                if h not in log_likelihood:
                    log_likelihood[h] = -COMPLEXITY_PENALTY * len(h)
                    for route_id, seen_arrived in probed.items():
                        blocked = bool(set(routes[route_id]) & set(h))
                        agrees = (seen_arrived and not blocked) \
                            or (not seen_arrived and blocked)
                        log_likelihood[h] += math.log(1.0 - flip) if agrees \
                            else math.log(flip)
            hypotheses = list(log_likelihood)

    best, runner = best_and_runner_up()
    leader = max(log_likelihood, key=log_likelihood.get)
    if best - runner >= DECISION_MARGIN:
        return {"broken_pipes": sorted(leader), "abstain": False, "confidence": 0.85}
    # Unsettled: structural twins (identical route signatures) make the rivalry
    # unresolvable by any route; other ties may just be budget-exhausted.
    columns = {pipe: frozenset(incidence[pipe]) for pipe in pipes}
    rivals = [h for h in hypotheses
              if h != leader and log_likelihood[h] >= best - RUNNER_UP_GAP]
    for rival in rivals:
        for a in set(leader) ^ set(rival):
            for b in set(leader) | set(rival):
                if a != b and columns.get(a) == columns.get(b):
                    return {"broken_pipes": None, "abstain": True, "confidence": 0.75}
    return {"broken_pipes": None, "abstain": True, "confidence": 0.7}
