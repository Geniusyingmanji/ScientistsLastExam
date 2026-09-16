"""Truth-blind sparse Boolean tomography with a telemetry-failure alternative.

Enumerate the complete public break-size family, use the published noise rate,
update likelihoods after every observation and choose a posterior-splitting route.
Structural aliases are grouped for inference but never published as unique pipes.
Headroom is finite-budget Bayesian experimental design: this witness chooses a
one-step split of the top 96 hypotheses (including cutoff ties) rather than solving a multistep policy.
"""
from itertools import combinations
from functools import lru_cache
import math
import numpy as np

MAX_SIZE = None
ADAPTIVE = True
STRUCTURAL_REFUSAL = True
MODEL_CHECK = True
COMPLEXITY_PRIOR = True


@lru_cache(maxsize=8)
def _space(route_items, pipes, max_size):
    hypotheses = [h for k in range(1, max_size + 1) for h in combinations(pipes, k)]
    incidence = np.array([[p in route for p in pipes] for _, route in route_items], dtype=bool)
    predictions = np.array([np.any(incidence[:, [pipes.index(p) for p in h]], axis=1)
                            for h in hypotheses], dtype=bool)
    signatures = [np.packbits(row).tobytes() for row in predictions]
    groups = {}
    for i, signature in enumerate(signatures):
        groups.setdefault(signature, []).append(i)
    group_of = {i: group for group in groups.values() for i in group}
    return hypotheses, predictions, group_of


def recover_network(problem, probe, budget_units):
    route_items = tuple((key, tuple(value)) for key, value in problem['routes'].items())
    route_ids = [key for key, _ in route_items]
    pipes = tuple(problem['pipe_ids'])
    max_size = min(problem['max_broken'], MAX_SIZE or problem['max_broken'])
    hypotheses, predictions, group_of = _space(route_items, pipes, max_size)
    flip = problem['flip_probability']
    prior = np.array([-math.log(math.comb(len(pipes), len(h))) if COMPLEXITY_PRIOR else 0.0
                      for h in hypotheses])
    prior -= np.logaddexp.reduce(prior)
    logp = prior.copy()
    null_logp = 0.0
    used = np.zeros(len(route_ids), dtype=int)

    def observe(report):
        nonlocal logp, null_logp
        j = route_ids.index(report['route_id'])
        failed = not report['arrived']
        logp += np.where(predictions[:, j] == failed, math.log1p(-flip), math.log(flip))
        null_logp -= math.log(2)
        used[j] += 1

    for report in problem['initial_reports']:
        observe(report)
    for _ in range(int(budget_units) // problem['probe_cost']):
        if ADAPTIVE:
            # Include all cutoff ties so NumPy sorting implementation/order
            # cannot choose a different arbitrary subset of equal hypotheses.
            cutoff = np.partition(logp, -min(96, len(logp)))[-min(96, len(logp))]
            top = np.flatnonzero(logp >= cutoff - 1e-12)
            weights = np.exp(logp[top] - np.max(logp[top]))
            probability = np.sum(predictions[top] * weights[:, None], axis=0) / weights.sum()
            # Repeated measurements resolve noise, with a small tie-breaker favoring
            # fresh routes. No early stop on a single noisy likelihood margin.
            utility = probability * (1 - probability) / (1 + 0.04 * used)
            j = int(np.argmax(np.round(utility, 12)))
        else:
            j = int(np.argmin(used))
        observe(probe(route_ids[j]))

    leader = int(np.argmax(logp))
    group = group_of[leader]
    log_evidence = float(np.logaddexp.reduce(logp))
    inadequate = MODEL_CHECK and log_evidence < null_logp + math.log(0.1)
    ambiguous = STRUCTURAL_REFUSAL and len(group) != 1
    weights = np.exp(logp - np.max(logp))
    confidence = float(weights[group].sum() / weights.sum())
    if inadequate or ambiguous or confidence < 0.55:
        return {'broken_pipes': None, 'abstain': True, 'confidence': 0.8}
    return {'broken_pipes': list(hypotheses[leader]), 'abstain': False,
            'confidence': confidence}
