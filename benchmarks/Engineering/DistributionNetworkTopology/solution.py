"""Weak valid baseline: probes one route and blames its first pipe.

Confident, legal, and wrong on almost every world — it never checks identifiability
and never refuses the twin-corridor worlds.
"""

from __future__ import annotations


def recover_network(problem, probe, budget_units):
    del budget_units
    routes = problem["routes"]
    first_id = next(iter(routes))
    report = probe(first_id)
    if not report["arrived"]:
        return {"broken_pipes": [routes[first_id][0]], "abstain": False,
                "confidence": 0.9}
    return {"broken_pipes": ["h00"], "abstain": False, "confidence": 0.6}
