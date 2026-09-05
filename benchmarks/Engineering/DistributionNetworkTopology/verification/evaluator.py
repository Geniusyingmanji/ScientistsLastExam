"""Deterministic distribution-network topology oracle.

A district water grid ships a public set of testable routes from the source to
district meters. Sending a release down a route reports whether it arrived: a route
fails exactly when any of its pipes is broken. Recovering the broken pipes from
budgeted route tests is boolean network tomography — and two worlds make a confident
broken-set claim a false discovery: symmetric pipes traversed by exactly the same
routes (indistinguishable by construction), and probe reports so noisy that no
consistent minimal set exists.
"""

from __future__ import annotations

import math
from itertools import combinations

import numpy as np

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"flip_probability": 0.02, "max_broken": 1},
    2: {"flip_probability": 0.04, "max_broken": 2},
    3: {"flip_probability": 0.07, "max_broken": 3},
}

# Pipes of a 4x4 grid, horizontal and vertical, with two parallel service pipes
# added between the same pair of junctions (aggregated service lines).
PIPES = []
for row in range(4):
    for column in range(3):
        PIPES.append("h%d%d" % (row, column))
for column in range(4):
    for row in range(3):
        PIPES.append("v%d%d" % (row, column))
PARALLEL_IDS = ("s11", "s21")
PIPE_IDS = PIPES + list(PARALLEL_IDS)

# Monotone routes from the left edge to the right edge of the grid (right and
# vertical moves only), plus one service corridor traversing both parallel lines.
ROUTES = []


def _pipes_of(cells):
    pipes = []
    for (r1, c1), (r2, c2) in zip(cells, cells[1:]):
        if r1 == r2:
            pipes.append("h%d%d" % (r1, min(c1, c2)))
        else:
            pipes.append("v%d%d" % (min(r1, r2), c1))
    return pipes


def _enumerate():
    stack = [(row, 0, frozenset({(row, 0)}), [(row, 0)]) for row in range(4)]
    while stack:
        row, column, visited, cells = stack.pop()
        if column == 3:
            # A route may take one closing vertical step inside the final column.
            ROUTES.append(_pipes_of(cells))
            for step in (-1, 1):
                if 0 <= row + step < 4 and (row + step, column) not in visited:
                    ROUTES.append(_pipes_of(cells + [(row + step, column)]))
            continue
        if (row, column + 1) not in visited:
            stack.append((row, column + 1,
                          visited | {(row, column + 1)},
                          cells + [(row, column + 1)]))
        for step in (-1, 1):
            if 0 <= row + step < 4 and (row + step, column) not in visited:
                stack.append((row + step, column,
                              visited | {(row + step, column)},
                              cells + [(row + step, column)]))


_enumerate()
_unique, _seen = [], set()
for route in sorted(ROUTES, key=lambda r: (len(r), r)):
    key = tuple(route)
    if key not in _seen:
        _seen.add(key)
        _unique.append(route)
ROUTES = _unique
# The service corridor crosses both parallel lines in series, so the two twins
# belong to exactly the same routes and are indistinguishable by construction.
ROUTES.append(["h10", "s11", "s21", "h12"])
ROUTE_IDS = ["R%02d" % index for index in range(len(ROUTES))]

PROBE_COST = 1
BUDGET_UNITS = 26

_BASE_DEVELOPMENT_SPECS = (
    (34011, "supported"), (34017, "supported"), (34023, "supported"),
    (34029, "supported"), (34031, "supported"),
    (34037, "alias"), (34041, "alias"),
)
HELDOUT_SPECS = (
    (35007, "supported"), (35013, "supported"), (35019, "alias"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _signature(broken):
    return frozenset(route_id for route_id, pipes in zip(ROUTE_IDS, ROUTES)
                     if set(pipes) & set(broken))


def _identifiable(broken, max_size):
    """A broken set is identifiable when no other small set shares its signature.

    The grid's mirror symmetries and the twin service corridor both create
    indistinguishable pairs; supported worlds must avoid them and alias worlds must
    be exactly them.
    """
    target = _signature(broken)
    pool = [name for name in PIPE_IDS]
    for size in range(1, max_size + 1):
        for subset in combinations(pool, size):
            if set(subset) == set(broken):
                continue
            if _signature(subset) == target:
                return False
    return True


def _world(spec):
    from itertools import combinations as _c
    seed, kind = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    if kind == "alias":
        # Structural ambiguity: the twin corridor, or a mirror-symmetric single
        # break -- no route family separates them.
        choice = int(rng.integers(0, 3))
        broken = [["s11"], ["s21"], ["h00"]][choice]
    else:
        pool = [name for name in PIPE_IDS if name not in PARALLEL_IDS]
        for _attempt in range(64):
            count = int(rng.integers(1, profile["max_broken"] + 1))
            indices = sorted(rng.choice(len(pool), size=count, replace=False))
            broken = [pool[index] for index in indices]
            if _identifiable(broken, profile["max_broken"] + 1):
                break
    return {"seed": int(seed), "kind": kind, "broken": sorted(broken),
            "flip": profile["flip_probability"]}


def problem_statement(world):
    del world
    return {
        "pipe_ids": list(PIPE_IDS),
        "parallel_service_pipes": list(PARALLEL_IDS),
        "routes": {route_id: list(pipes)
                   for route_id, pipes in zip(ROUTE_IDS, ROUTES)},
        "probe_cost": PROBE_COST,
        "budget_units": BUDGET_UNITS,
        "route_note": (
            "a route fails when any of its pipes is broken; reports flip with the "
            "published probability and repeats draw fresh noise"
        ),
        "claim_note": (
            "claim the broken pipe set; the two parallel service lines sit in series "
            "on the same corridor, so no route can tell which twin is broken -- a "
            "world whose failures concentrate there must be refused"
        ),
    }


class _Dispatch:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def probe(self, route_id):
        try:
            if route_id not in ROUTE_IDS:
                self.violated = True
                raise ValueError("unknown route id")
            if self.used + PROBE_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("probe budget exceeded")
            self.used += PROBE_COST
            self.calls += 1
            index = ROUTE_IDS.index(route_id)
            rng = np.random.default_rng(self.world["seed"] + 613 * index
                                        + 29 * self.calls)
            blocked = bool(set(ROUTES[index]) & set(self.world["broken"]))
            if rng.random() < self.world["flip"]:
                blocked = not blocked
            return {"route_id": route_id, "arrived": not blocked,
                    "budget_cost": PROBE_COST}
        except Exception:
            self.violated = True
            raise


def _validate(submission, world):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if bool(abstain):
        if submission.get("broken_pipes") is not None:
            raise ValueError("abstention requires an empty broken set")
        return [], confidence, True
    broken = submission.get("broken_pipes")
    if not isinstance(broken, (list, tuple)) or any(p not in PIPE_IDS for p in broken):
        raise ValueError("broken_pipes must list known pipe ids")
    if len(set(broken)) != len(broken) or not broken:
        raise ValueError("broken_pipes must be a nonempty unique list")
    if len(broken) > 6:
        raise ValueError("at most six broken pipes may be claimed")
    del world
    return list(broken), confidence, False


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "set_f1": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    dispatch = _Dispatch(world)
    try:
        submission = candidate(problem_statement(world), dispatch.probe,
                               BUDGET_UNITS)
        broken, confidence, abstain = _validate(submission, world)
        if dispatch.violated:
            raise ValueError("dispatch contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            claimed, truth = set(broken), set(world["broken"])
            intersection = len(claimed & truth)
            precision = intersection / len(claimed)
            recall = intersection / len(truth)
            f1 = 2 * precision * recall / (precision + recall) if intersection else 0.0
            mechanism = float(f1)
        elif supported:
            f1 = 0.0
            mechanism = 0.0
        else:
            correct = bool(abstain)
            f1 = 0.0
            mechanism = 1.0 if correct else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": mechanism, "set_f1": float(f1),
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": dispatch.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "set_f1": float(np.mean([r["set_f1"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(recover_network):
    development = [_evaluate_world(recover_network, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(recover_network, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_set_f1": dev["set_f1"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }
