"""Hidden oracle for JuntaVariableDiscovery.

A Boolean function of n variables depends on only a few of them, a junta. The candidate may query
the function at points it chooses, under a query budget; every answer is flipped independently
with a published noise rate. It must name the relevant variables, the ones the function truly
depends on, or decline when no junta of the published size can explain the answers.

The score is exact and campaign independent. A variable is relevant exactly when flipping it
changes the function on a positive fraction of inputs, so the true relevant set R and each
variable's influence are functions of the world alone. A named variable that is in fact irrelevant
is a false discovery and costs the world; a named set that misses relevant variables scores the
fraction of R it recovers. Whether any junta of the published size explains the function at all is
measured by kappa*, the total influence that any set of that size must leave uncovered, zero
exactly on the worlds that are juntas.

What makes it hard:

    interaction        a variable can matter only through a parity or a gate with others, so its
                       single-variable correlation with the output is zero; only a query that
                       flips it against a fixed background reveals it
    weak variables     some relevant variables are pivotal on a small fraction of inputs, so their
                       influence is a few hundredths and the budget barely certifies them
    noise              every answer is flipped with the published rate, so a variable's influence
                       is read through a binomial haze and a family-wise margin is what keeps a
                       named irrelevant variable below delta per world
    not a junta        in some worlds the function depends on more variables than any junta of the
                       published size, and the right answer is to decline; the excess influence is
                       spread so that no single query settles it
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog  # noqa: F401  (kept for parity with the sibling tasks' imports)

N = 28                  # number of variables, published
MAX_JUNTA = 12          # the largest junta the answer may name, published
NOISE = 0.10            # the probability each answer is flipped, published
BUDGET = 20_000         # the number of queries, published
_INFLUENCE_SAMPLES = 400_000   # Monte-Carlo sample size for the exact-influence oracle


# ---- the world ---------------------------------------------------------------------------------
def _make_function(spec):
    """Return (f, relevant_set). Supported worlds are a multiplexer of an additive block and a
    parity block, gated so influences span a wide range; unsupported worlds are a parity of more
    than MAX_JUNTA variables, which no junta of that size can explain."""
    rng = np.random.default_rng(spec["seed"])
    idx = rng.permutation(N)
    fault = spec.get("fault")
    if fault == "bigparity":
        size = spec["size"]
        vars_ = list(idx[:size])

        def f(X):
            X = np.atleast_2d(X)
            return np.bitwise_xor.reduce(X[:, vars_], axis=1).astype(int)

        return f, set(vars_)
    sel = int(idx[0])
    add = list(idx[1:5])
    weights = np.array(spec.get("weights", [3.0, 2.0, 1.2, 0.7]))
    par = list(idx[5:8])
    gate_ctrl = list(idx[8:10])
    gate_par = list(idx[10:12])
    relevant = {sel} | set(add) | set(par) | set(gate_ctrl) | set(gate_par)

    def f(X):
        X = np.atleast_2d(X)
        g = ((X[:, add] * 2 - 1) @ weights > 0).astype(int)
        p = np.bitwise_xor.reduce(X[:, par], axis=1)
        gate = (X[:, gate_ctrl].sum(1) == len(gate_ctrl))
        gp = np.bitwise_xor.reduce(X[:, gate_par], axis=1) & gate.astype(int)
        return np.where(X[:, sel] == 0, g, p ^ gp).astype(int)

    return f, relevant


def make_world(spec):
    f, relevant = _make_function(spec)
    world = {"n": N, "f": f, "relevant": relevant, "fault": spec.get("fault", "") or "",
             "kind": "unsupported" if spec.get("fault") else "supported"}
    return world


def influence(world, i):
    """Pr over uniform x that flipping variable i changes the function; exact up to the fixed
    Monte-Carlo sample, and computed with the world's own seed so it never varies."""
    rng = np.random.default_rng(1_000 + i)
    X = rng.integers(0, 2, size=(_INFLUENCE_SAMPLES, world["n"]))
    Y = world["f"](X)
    X2 = X.copy(); X2[:, i] ^= 1
    return float(np.mean(world["f"](X2) != Y))


def influences(world):
    return {i: influence(world, i) for i in range(world["n"])}


def detectability(world):
    """kappa*: the least total influence a junta of MAX_JUNTA variables must leave uncovered.
    Zero exactly when the function is a junta of that size; for a parity of s > MAX_JUNTA
    variables every variable has influence one, so it is s - MAX_JUNTA."""
    infl = np.array([influence(world, i) for i in range(world["n"])])
    keep = np.sort(infl)[::-1][:MAX_JUNTA]
    return float(infl.sum() - keep.sum())


# ---- the campaign ------------------------------------------------------------------------------
class _Bench:
    """The candidate's only access to the function. The candidate receives the query closure, not
    this object, so the ledger is out of its reach."""

    def __init__(self, world, run_seed):
        self.world = world
        self.budget = BUDGET
        self.used = 0
        self.violated = False
        self.rng = np.random.default_rng(run_seed)

    def oracle(self):
        state, w = self, self.world
        n = w["n"]

        def query(points):
            X = np.asarray(points)
            if X.ndim != 2 or X.shape[1] != n:
                raise ValueError("points must be a k x %d array of bits" % n)
            if X.dtype == bool:
                X = X.astype(int)
            if not np.issubdtype(X.dtype, np.integer) or not np.isin(X, (0, 1)).all():
                raise ValueError("points must be 0/1 integers")
            k = int(X.shape[0])
            if k < 1:
                raise ValueError("query needs at least one point")
            if state.used + k > state.budget:
                state.violated = True
                raise RuntimeError("query budget exhausted")
            state.used += k
            clean = w["f"](X)
            flip = state.rng.random(k) < NOISE
            return (clean ^ flip.astype(int)).astype(int)

        return query


# ---- the problem and the answer ----------------------------------------------------------------
PUBLIC_PROBLEM = {
    "function_model": "an unknown Boolean function f of n variables depends on an unknown subset "
                      "of them; query(points) returns f at each row of points, each answer flipped "
                      "independently with probability noise_rate",
    "query_model": "query(points) takes a k x n array of bits and returns k noisy labels in {0, 1}; "
                   "at most budget answers may be drawn in all",
    "answer_format": "verdict junta with relevant, the sorted list of variables the function "
                     "depends on (naming an irrelevant variable is a false discovery); or verdict "
                     "no_junta when no junta of at most max_junta_size variables can explain the "
                     "answers",
}


def public_problem(world):
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "n": world["n"],
        "max_junta_size": MAX_JUNTA,
        "noise_rate": NOISE,
        "budget": BUDGET,
    })
    return problem


def _validate_submission(submission, n):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    conf = submission.get("confidence", 0.0)
    if isinstance(conf, bool) or not isinstance(conf, (int, float, np.integer, np.floating)):
        raise ValueError("confidence must be a number")
    conf = float(conf)
    if not math.isfinite(conf):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(conf, 0.0, 1.0))
    if submission.get("abstain", False) is True:
        return None, confidence
    verdict = submission.get("verdict")
    if verdict == "no_junta":
        return None, confidence
    if verdict != "junta":
        raise ValueError("verdict must be 'junta' or 'no_junta'")
    relevant = submission.get("relevant")
    if not isinstance(relevant, (list, tuple, np.ndarray)):
        raise ValueError("relevant must be a list of variables")
    out = set()
    for value in relevant:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError("a variable must be an integer")
        v = int(value)
        if not 0 <= v < n:
            raise ValueError("a variable must lie in 0..%d" % (n - 1))
        if v in out:
            raise ValueError("variable %d named twice" % v)
        out.add(v)
    if len(out) > MAX_JUNTA:
        raise ValueError("a junta names at most %d variables" % MAX_JUNTA)
    return out, confidence


def _metrics(world, relevant):
    row = {"covered": False, "sharpness": 0.0, "mechanism_score": 0.0, "false_discovery": False,
           "correct_refusal": False}
    refusal_world = world["kind"] == "unsupported"
    if relevant is None:
        row.update({"mechanism_score": 1.0 if refusal_world else 0.0, "correct_refusal": refusal_world})
        return row
    if refusal_world:
        # no junta of the published size explains the function, so any named set is a false
        # discovery; it scores zero where declining would have scored one
        row["false_discovery"] = True
        return row
    R = world["relevant"]
    for v in relevant:
        if v not in R:
            row.update({"false_discovery": True, "mechanism_score": -1.0})
            return row
    recall = len(relevant & R) / len(R)
    row.update({"covered": True, "sharpness": recall, "mechanism_score": recall})
    return row


# ---- the worlds --------------------------------------------------------------------------------
# `seed` draws the function and which variables it depends on; `run_seed` draws the query noise.
# Unsupported worlds are a parity of `size` > MAX_JUNTA variables.
def _w(name, seed, run_seed, **more):
    return dict(name=name, seed=seed, run_seed=run_seed, **more)


DEVELOPMENT_WORLDS = (
    _w("dev-01", 300, 440000),
    _w("dev-02", 301, 440001),
    _w("dev-03", 302, 440002),
    _w("dev-04", 303, 440003),
    _w("dev-05", 304, 440004),
    _w("dev-06", 305, 440005),
    _w("dev-07", 306, 440006),
    _w("dev-08", 360, 441000, fault="bigparity", size=14),
    _w("dev-09", 361, 441001, fault="bigparity", size=15),
    _w("dev-10", 362, 441002, fault="bigparity", size=16),
    _w("dev-11", 363, 441003, fault="bigparity", size=17),
    _w("dev-12", 364, 441004, fault="bigparity", size=18),
)

HELDOUT_WORLDS = (
    _w("held-01", 500, 550000),
    _w("held-02", 501, 550001),
    _w("held-03", 502, 550002),
    _w("held-04", 503, 550003),
    _w("held-05", 560, 551000, fault="bigparity", size=15),
    _w("held-06", 561, 551001, fault="bigparity", size=17),
)

_WORLDS = {}


def _world(spec):
    key = (spec["name"], spec["seed"])
    if key not in _WORLDS:
        _WORLDS[key] = make_world(spec)
    return _WORLDS[key]


ROW_KEYS = ("covered", "sharpness", "mechanism_score", "false_discovery", "correct_refusal")


def _evaluate_world(identify, spec, split, index):
    world = _world(spec)
    bench = _Bench(world, spec["run_seed"])
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "queries_used": 0}
    try:
        query = bench.oracle()
        submission = identify(public_problem(world), query)
        relevant, confidence = _validate_submission(submission, world["n"])
        if bench.violated:
            raise RuntimeError("query budget exceeded")
        metrics = _metrics(world, relevant)
        target = max(metrics["mechanism_score"], 0.0)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": relevant is None,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "queries_used": bench.used,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        row["sharpness"] = round(float(row["sharpness"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key in ("sharpness", "mechanism_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "queries_used": bench.used,
        })
        return row


def _split_summary(records):
    supported = [r for r in records if r["kind"] == "supported"]
    unsupported = [r for r in records if r["kind"] == "unsupported"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "interval_sharpness": float(np.mean([r["sharpness"] for r in supported])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in records])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in supported])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_queries_used": float(np.mean([r["queries_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(identify):
    development = [_evaluate_world(identify, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(identify, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    valid = 1.0 if dev["valid_count"] > 0 else 0.0
    return {
        "combined_score": dev["normalized_mechanism"] if valid else 0.0,
        "valid": valid,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"] if valid else 0.0,
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_interval_sharpness": dev["interval_sharpness"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_probes_used": dev["mean_queries_used"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_interval_sharpness": held["interval_sharpness"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
