"""Recover a spin-chain Hamiltonian from the dynamics it generates.

The physics. A closed quantum system evolves under a Hamiltonian, and what an experiment records
is not the Hamiltonian but expectation values of a few observables as a function of time. Reading
the couplings and fields back out of those traces is Hamiltonian learning, an active problem in
quantum simulation and device characterisation: the map from parameters to dynamics is highly
non-linear, different Hamiltonians can generate identical traces on a restricted observable set,
and the information available falls off sharply once the evolution has dephased.

The oracle is QuTiP, the standard library for open and closed quantum dynamics, so the traces are
produced by its Schrodinger solver rather than by a reimplementation of one.

Measurements cost budget. A candidate chooses which times to sample, which makes the task
iterative rather than a fit to a fixed table: where you look determines what you can identify.

Three axes, reported separately and never averaged:

    mechanism   how close the recovered fields and couplings are to the truth
    fdr         couplings claimed between spins that are in fact uncoupled
    refusal     some chains carry a symmetry that makes two parameters exchangeable - the traces
                of the measured observables are identical under the swap. Nothing in the data
                distinguishes them, and the honest answer is to decline rather than to pick one.
"""

from __future__ import annotations

import math
import random

DIFFICULTY = 1

# Difficulty is chain length, how many couplings are genuinely zero, and how many time samples
# the budget affords. A two-spin chain measured densely is a curve fit; a longer chain sampled
# sparsely, with some couplings absent, is an identification problem.
_LADDER = {
    1: {"spins": 3, "sparsity": 0.34, "samples": 24, "t_max": 6.0, "count": 4,
        "seed": 20260812},
    2: {"spins": 4, "sparsity": 0.40, "samples": 20, "t_max": 8.0, "count": 4,
        "seed": 20260813},
    3: {"spins": 5, "sparsity": 0.45, "samples": 16, "t_max": 10.0, "count": 4,
        "seed": 20260814},
}

_SEALED_LADDER = {
    1: {"spins": 3, "sparsity": 0.34, "samples": 22, "t_max": 6.5, "count": 2,
        "seed": 991201},
    2: {"spins": 4, "sparsity": 0.40, "samples": 18, "t_max": 8.5, "count": 2,
        "seed": 991202},
    3: {"spins": 5, "sparsity": 0.45, "samples": 14, "t_max": 11.0, "count": 2,
        "seed": 991203},
}

# A coupling weaker than this moves the measured traces by less than the sampling can resolve, so
# claiming or missing one is unfalsifiable. Truth values are kept away from the boundary.
RESOLVABLE = 0.15
FIELD_RANGE = (-1.2, 1.2)
COUPLING_RANGE = (0.4, 1.6)

_CACHE: dict = {}


def _qutip():
    import qutip

    return qutip


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; measure its anchor before adding one" % level
        )
    return ladder[level]


def _operators(qutip, n):
    sx, sy, sz = [], [], []
    for index in range(n):
        for store, op in ((sx, qutip.sigmax()), (sy, qutip.sigmay()), (sz, qutip.sigmaz())):
            factors = [qutip.qeye(2)] * n
            factors[index] = op
            store.append(qutip.tensor(factors))
    return sx, sy, sz


def _hamiltonian(qutip, fields, couplings):
    n = len(fields)
    sx, sy, sz = _operators(qutip, n)
    H = sum(fields[i] * sz[i] for i in range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if couplings[i][j]:
                H += couplings[i][j] * (sx[i] * sx[j] + sy[i] * sy[j])
    return H


def _simulate(qutip, fields, couplings, times):
    """Single-site magnetisation traces, which is what such an experiment records."""
    import numpy as np

    n = len(fields)
    _sx, _sy, sz = _operators(qutip, n)
    H = _hamiltonian(qutip, fields, couplings)
    # A domain-wall initial state: one spin up, the rest down. It has overlap with many
    # eigenstates, so the dynamics carry information about the whole chain.
    psi0 = qutip.tensor([qutip.basis(2, 0)] + [qutip.basis(2, 1)] * (n - 1))
    result = qutip.sesolve(H, psi0, list(times), e_ops=sz)
    return [[float(v) for v in trace] for trace in result.expect]


def _symmetric_pair(fields, couplings):
    """Two spins whose exchange leaves every measured single-site trace unchanged.

    If spins i and j carry the same field and couple identically to every other spin, then
    swapping them is a symmetry of the Hamiltonian. It maps the initial state to itself whenever
    neither is the excited site, so the measured magnetisations are identical and no amount of
    data separates the two labellings.
    """
    n = len(fields)
    for i in range(1, n):
        for j in range(i + 1, n):
            if abs(fields[i] - fields[j]) > 1e-9:
                continue
            if abs(couplings[i][j]) > 1e-9:
                continue
            others = [k for k in range(n) if k not in (i, j)]
            if all(abs(couplings[i][k] - couplings[j][k]) < 1e-9 for k in others):
                return (i, j)
    return None


def _draw_world(rng, profile, want_symmetry: bool):
    n = profile["spins"]
    fields = [rng.uniform(*FIELD_RANGE) for _ in range(n)]
    couplings = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < profile["sparsity"]:
                continue
            value = rng.uniform(*COUPLING_RANGE)
            couplings[i][j] = couplings[j][i] = value
    if want_symmetry and n >= 3:
        # Make spins 1 and 2 exchangeable: identical field, no direct coupling, identical
        # coupling to everyone else.
        fields[2] = fields[1]
        couplings[1][2] = couplings[2][1] = 0.0
        for k in range(n):
            if k in (1, 2):
                continue
            couplings[2][k] = couplings[k][2] = couplings[1][k]
    return fields, couplings


def _generate(profile, tag):
    key = "worlds::%s::%s" % (tag, sorted(profile.items()))
    if key in _CACHE:
        return _CACHE[key]
    import numpy as np

    qutip = _qutip()
    rng = random.Random(profile["seed"])
    times = [float(t) for t in np.linspace(0.0, profile["t_max"], profile["samples"])]
    worlds = []
    attempts = 0
    while len(worlds) < profile["count"] and attempts < 600:
        attempts += 1
        want_symmetry = len(worlds) >= profile["count"] - profile["count"] // 2
        fields, couplings = _draw_world(rng, profile, want_symmetry)
        pair = _symmetric_pair(fields, couplings)
        if bool(pair) != want_symmetry:
            continue
        # Every world must contain at least one true zero, or the false-discovery axis has no
        # denominator, and at least one real coupling, or mechanism has nothing to recover.
        offdiag = [couplings[i][j] for i in range(profile["spins"])
                   for j in range(i + 1, profile["spins"])]
        if not any(v == 0.0 for v in offdiag) or not any(v > 0 for v in offdiag):
            continue
        worlds.append({
            "key": "h%d_n%d%s" % (len(worlds), profile["spins"], "_sym" if pair else ""),
            "fields": fields,
            "couplings": couplings,
            "symmetric_pair": pair,
            "times": times,
            "traces": _simulate(qutip, fields, couplings, times),
        })
    if len(worlds) < profile["count"]:
        raise ValueError(
            "only %d of %d worlds met the symmetry quota in %d draws"
            % (len(worlds), profile["count"], attempts)
        )
    _CACHE[key] = tuple(worlds)
    return _CACHE[key]


def development_worlds():
    return _generate(_profile(_LADDER, DIFFICULTY), "dev")


def sealed_worlds():
    return _generate(_profile(_SEALED_LADDER, DIFFICULTY), "sealed")


def _observation(world):
    return {
        "spins": len(world["fields"]),
        "times": list(world["times"]),
        "magnetisation": [list(tr) for tr in world["traces"]],
        "resolvable_coupling": RESOLVABLE,
        "field_range": list(FIELD_RANGE),
        "coupling_range": list(COUPLING_RANGE),
    }


def _parse(submission, n):
    if not isinstance(submission, dict):
        return None, "expected a dict, got %s" % type(submission).__name__
    if submission.get("abstain"):
        return {"abstain": True}, ""
    fields = submission.get("fields")
    couplings = submission.get("couplings")
    if fields is None or couplings is None:
        return None, "missing 'fields' or 'couplings' (or set 'abstain': True)"
    try:
        fields = [float(x) for x in fields]
        couplings = [[float(x) for x in row] for row in couplings]
    except (TypeError, ValueError):
        return None, "fields and couplings must be numbers"
    if len(fields) != n:
        return None, "expected %d fields, got %d" % (n, len(fields))
    if len(couplings) != n or any(len(row) != n for row in couplings):
        return None, "couplings must be %dx%d" % (n, n)
    if any(not math.isfinite(x) for x in fields):
        return None, "non-finite field"
    if any(not math.isfinite(x) for row in couplings for x in row):
        return None, "non-finite coupling"
    return {"abstain": False, "fields": fields, "couplings": couplings}, ""


def _mechanism(world, parsed):
    fields = world["fields"]
    truth = world["couplings"]
    n = len(fields)
    pair = world["symmetric_pair"]

    field_hits = sum(1 for i in range(n)
                     if abs(parsed["fields"][i] - fields[i]) <= 0.1)
    field_score = field_hits / n

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if pair:
        # The exchangeable spins' parameters are not determined by the data; exclude anything
        # that differs between the two labellings rather than scoring a coin flip.
        a, b = pair
        pairs = [(i, j) for i, j in pairs if a not in (i, j) and b not in (i, j)]
    hits = claimed_false = true_zero = real = 0
    for i, j in pairs:
        truth_value = truth[i][j]
        guess = abs(parsed["couplings"][i][j])
        if truth_value >= RESOLVABLE:
            real += 1
            if abs(guess - truth_value) <= max(0.1, 0.15 * truth_value):
                hits += 1
        else:
            true_zero += 1
            if guess >= RESOLVABLE:
                claimed_false += 1
    coupling_score = hits / real if real else 1.0
    return {
        "field_recovery": field_score,
        "coupling_recovery": coupling_score,
        "mechanism": 0.5 * field_score + 0.5 * coupling_score,
        "false_discovery_rate": (claimed_false / true_zero) if true_zero else None,
        "scorable_pairs": len(pairs),
        "resolvable_couplings": real,
    }


def _score_split(learn, worlds):
    rows = []
    for world in worlds:
        try:
            raw = learn(_observation(world))
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            rows.append({"key": world["key"], "valid": False,
                         "reason": "raised: %s" % type(exc).__name__})
            continue
        parsed, why = _parse(raw, len(world["fields"]))
        if parsed is None:
            rows.append({"key": world["key"], "valid": False, "reason": why})
            continue
        determined = world["symmetric_pair"] is None
        if parsed["abstain"]:
            rows.append({"key": world["key"], "valid": True, "abstained": True,
                         "determined": determined, "mechanism": 0.0,
                         "correct_refusal": not determined})
            continue
        metrics = _mechanism(world, parsed)
        metrics.update({"key": world["key"], "valid": True, "abstained": False,
                        "determined": determined, "correct_refusal": False})
        rows.append(metrics)

    valid = [r for r in rows if r["valid"]]
    determined = [r for r in valid if r["determined"]]
    undetermined = [r for r in valid if not r["determined"]]
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
    }


def evaluate(learn_hamiltonian) -> dict:
    development = _score_split(learn_hamiltonian, development_worlds())
    valid = development["valid_count"] == development["world_count"]
    result = {
        "combined_score": float(development["mechanism"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_mechanism_score": development["mechanism"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "per_instance": development["rows"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(learn_hamiltonian, sealed_worlds())
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
