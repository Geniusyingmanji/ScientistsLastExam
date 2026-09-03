"""Hidden oracle for HiddenCouplingNetwork.

A network of N observed units relaxes to a steady state under constant drive. Each unit decays
towards zero at its own rate and receives saturating input from the units coupled into it:

    gamma_i * x_i  =  sum_j A_ij * tanh(x_j)  +  u_i          (steady state)

The candidate chooses the drive vector u for each experiment - any pattern over the observed
units within the amplitude bound - and receives the noisy steady state of every observed unit.
The budget is fewer experiments than there are units, so driving one unit at a time cannot even
touch every node. From those experiments it must report the direct coupling graph among the
observed units, with signs, or decline when direct couplings are not identifiable.

Three ways to be wrong:

    indirect paths       a drive at j moves every unit downstream of j. A candidate that reads
                         "responds to j" as "coupled to j" books the whole transitive closure.
                         The direct structure is the sparse solution of the steady-state
                         equation, not the pattern of responses.
    the nonlinearity     the equation is linear in tanh(x_j), not in x_j. Regressing on x_j is
                         fine at small amplitude and biased at the amplitude a good signal-to-
                         noise ratio wants; the bias looks like weak extra edges.
    hidden units         some networks contain units that are never measured and never driven.
                         Their effect on the observed units is a dense, low-rank coupling that
                         no sparse direct graph explains. The trap: a dense regression fits it
                         perfectly and produces a confident, wrong graph. The tell: no sparse
                         model reaches the noise floor. The honest answer is to decline.

A network with no couplings at all is *not* the hidden case: its steady state is diagonal and
"no edges" is a claim the evidence supports. Declining there is a missed discovery.

Scoring keeps the discovery axes separate and normalises so that declining every network earns
exactly zero. On a fully observed network the score is the signed-edge F1 of the claimed graph.
"""
from __future__ import annotations

import math

import numpy as np

# Experiments per network. Fewer than the number of units: single-unit drives cannot cover the
# network, and the direct graph has to be recovered from multi-unit drives by sparse regression.
DEVELOPMENT_UNITS = 12
DEVELOPMENT_BUDGET = 10
HELDOUT_UNITS = 16
HELDOUT_BUDGET = 13

DRIVE_BOUND = 1.0
NOISE_SIGMA = 0.02
MAX_IN_DEGREE = 3
WEIGHT_RANGE = (0.35, 0.8)
DECAY_RANGE = (0.9, 1.4)
HIDDEN_UNITS = 2
HIDDEN_WEIGHT_RANGE = (0.4, 0.8)
# Spectral abscissa of the linearisation the generator insists on, so every drive relaxes.
STABILITY_MARGIN = -0.15
MAX_CLAIMED_EDGES_PER_UNIT = 4

WORLD_KINDS = ("sparse", "null", "hidden")


def _stable(gamma, A):
    J = A - np.diag(gamma)
    return float(np.max(np.linalg.eigvals(J).real)) < STABILITY_MARGIN


def _draw_network(rng, n_observed, kind):
    """Coupling matrix over observed + hidden units; hidden units come last."""
    n_hidden = HIDDEN_UNITS if kind == "hidden" else 0
    m = n_observed + n_hidden
    for _attempt in range(200):
        gamma = rng.uniform(*DECAY_RANGE, size=m)
        A = np.zeros((m, m))
        if kind != "null":
            for i in range(n_observed):
                k = int(rng.integers(1, MAX_IN_DEGREE + 1))
                sources = rng.choice([j for j in range(n_observed) if j != i], size=k, replace=False)
                for j in sources:
                    A[i, j] = float(rng.choice([-1.0, 1.0]) * rng.uniform(*WEIGHT_RANGE))
            for h in range(n_observed, m):
                # Each hidden unit listens to a few observed units and feeds a few others, so the
                # observed sub-network inherits an effective coupling that is dense and low-rank.
                fed_by = rng.choice(n_observed, size=int(rng.integers(2, 4)), replace=False)
                feeds = rng.choice(n_observed, size=int(rng.integers(2, 4)), replace=False)
                for j in fed_by:
                    A[h, j] = float(rng.choice([-1.0, 1.0]) * rng.uniform(*HIDDEN_WEIGHT_RANGE))
                for i in feeds:
                    A[i, h] = float(rng.choice([-1.0, 1.0]) * rng.uniform(*HIDDEN_WEIGHT_RANGE))
        if _stable(gamma, A):
            return gamma, A
    raise RuntimeError("could not draw a stable network")


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    n_observed = int(spec["units"])
    gamma, A = _draw_network(rng, n_observed, kind)
    return {"kind": kind, "seed": spec["seed"], "n_observed": n_observed,
            "gamma": gamma, "A": A, "budget": int(spec["budget"])}


def _steady_state(world, drive):
    """Solve gamma * x = A tanh(x) + u by damped fixed-point iteration, Newton-polished."""
    gamma, A = world["gamma"], world["A"]
    m = gamma.shape[0]
    u = np.zeros(m)
    u[:world["n_observed"]] = drive
    x = np.zeros(m)
    for _ in range(500):
        x_new = (A @ np.tanh(x) + u) / gamma
        x = 0.5 * x + 0.5 * x_new
    for _ in range(20):
        t = np.tanh(x)
        residual = gamma * x - A @ t - u
        J = np.diag(gamma) - A * (1.0 - t * t)[None, :]
        step = np.linalg.solve(J, residual)
        x = x - step
        if float(np.max(np.abs(step))) < 1e-12:
            break
    return x


class _Laboratory:
    """The candidate's only view of the network: one driven steady state per call."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.calls = 0
        self.violated = False

    def __call__(self, drive):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("experiment budget exhausted")
        u = np.asarray(drive, dtype=float).reshape(-1)
        n = self.world["n_observed"]
        if u.shape[0] != n:
            raise ValueError("drive must have one entry per observed unit (%d)" % n)
        if not np.all(np.isfinite(u)) or float(np.max(np.abs(u))) > DRIVE_BOUND + 1e-12:
            raise ValueError("drive entries must be finite and within [-%g, %g]" % (DRIVE_BOUND, DRIVE_BOUND))
        self.calls += 1
        x = _steady_state(self.world, u)
        rng = np.random.default_rng((self.world["seed"], self.calls))
        observed = x[:n] + rng.normal(0.0, NOISE_SIGMA, size=n)
        return [float(v) for v in observed]


PUBLIC_PROBLEM = {
    "units": DEVELOPMENT_UNITS,
    "experiment_budget": DEVELOPMENT_BUDGET,
    "drive_bound": DRIVE_BOUND,
    "noise_sigma": NOISE_SIGMA,
    "max_in_degree": MAX_IN_DEGREE,
    "coupling_weight_range": list(WEIGHT_RANGE),
    "decay_rate_range": list(DECAY_RANGE),
    "max_claimed_edges_per_unit": MAX_CLAIMED_EDGES_PER_UNIT,
    "dynamics": "steady state of gamma_i * x_i = sum_j A_ij * tanh(x_j) + u_i; you choose u over "
                "the observed units, you read the noisy steady state of the observed units",
    "hidden_unit_model": "some networks contain unmeasured, undriven units coupled into and out "
                         "of the observed ones; their effect on the observed units is not a "
                         "sparse direct graph",
    "abstain_when": "no sparse direct graph among the observed units explains the steady states "
                    "to the noise floor, because unmeasured units are coupled in",
}


def _validate_submission(submission, n_units):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = bool(submission.get("abstain", False))
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if abstain:
        return set(), confidence, True
    edges = submission.get("edges")
    if not isinstance(edges, list):
        raise ValueError("edges must be a list (possibly empty), or abstain")
    if len(edges) > MAX_CLAIMED_EDGES_PER_UNIT * n_units:
        raise ValueError("too many claimed edges")
    parsed = set()
    for row in edges:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("each edge must be [source, target, sign]")
        source, target, sign = row
        if isinstance(source, bool) or isinstance(target, bool):
            raise ValueError("edge endpoints must be integers")
        source, target = int(source), int(target)
        sign = float(sign)
        if not (0 <= source < n_units and 0 <= target < n_units) or source == target:
            raise ValueError("edge endpoints must be distinct observed unit indices")
        if sign not in (-1.0, 1.0):
            raise ValueError("edge sign must be -1 or +1")
        if any((source, target) == (s, t) for s, t, _g in parsed):
            raise ValueError("duplicate edge %r" % ((source, target),))
        parsed.add((source, target, sign))
    return parsed, confidence, False


def _true_edges(world):
    n = world["n_observed"]
    A = world["A"]
    return {(j, i, float(np.sign(A[i, j]))) for i in range(n) for j in range(n) if A[i, j] != 0.0}


def _metrics(world, claimed, abstain):
    blank = {
        "edge_f1": 0.0,
        "mechanism_score": 0.0,
        "claimed_edge_count": 0,
        "false_edge_count": 0,
        "correct_refusal": False,
        "false_discovery": False,
    }
    kind = world["kind"]
    if kind == "hidden":
        correct = bool(abstain)
        blank.update({
            "mechanism_score": 1.0 if correct else 0.0,
            "claimed_edge_count": 0 if abstain else len(claimed),
            "false_edge_count": 0 if abstain else len(claimed),
            "correct_refusal": correct,
            "false_discovery": not correct,
        })
        return blank
    if abstain:
        return blank
    truth = _true_edges(world)
    tp = len(truth & claimed)
    # A claimed edge is false when its pair does not exist or its sign is wrong.
    false_edges = len(claimed - truth)
    blank["claimed_edge_count"] = len(claimed)
    blank["false_edge_count"] = int(false_edges)
    if kind == "null":
        correct = len(claimed) == 0
        blank.update({
            "edge_f1": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "false_discovery": not correct,
        })
        return blank
    precision = tp / len(claimed) if claimed else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    blank.update({"edge_f1": float(f1), "mechanism_score": float(f1)})
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "sparse", "seed": 71200301, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "sparse", "seed": 71200302, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "sparse", "seed": 71200303, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "sparse", "seed": 71200304, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "sparse", "seed": 71200305, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "null", "seed": 71200306, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "null", "seed": 71200307, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "hidden", "seed": 71200308, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "hidden", "seed": 71200309, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
    {"kind": "hidden", "seed": 71200310, "units": DEVELOPMENT_UNITS, "budget": DEVELOPMENT_BUDGET},
)

HELDOUT_WORLDS = (
    {"kind": "sparse", "seed": 88310401, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "sparse", "seed": 88310402, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "sparse", "seed": 88310403, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "sparse", "seed": 88310404, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "null", "seed": 88310405, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "hidden", "seed": 88310406, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "hidden", "seed": 88310407, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
    {"kind": "hidden", "seed": 88310408, "units": HELDOUT_UNITS, "budget": HELDOUT_BUDGET},
)

ROW_KEYS = ("edge_f1", "mechanism_score", "claimed_edge_count", "false_edge_count",
            "correct_refusal", "false_discovery")


def _evaluate_world(discover_couplings, spec, split, index):
    world = _world(spec)
    lab = _Laboratory(world)
    problem = dict(PUBLIC_PROBLEM)
    problem["units"] = world["n_observed"]
    problem["experiment_budget"] = world["budget"]
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "units": world["n_observed"], "experiments": 0}
    try:
        submission = discover_couplings(problem, lab)
        claimed, confidence, abstain = _validate_submission(submission, world["n_observed"])
        if lab.violated:
            raise RuntimeError("experiment budget exceeded")
        metrics = _metrics(world, claimed, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "experiments": lab.calls,
        })
        for key in ("edge_f1", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith(("_f1", "_score")) else
                          (0 if key.endswith("_count") else False)) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "experiments": lab.calls,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] != "hidden"]
    sparse = [r for r in records if r["kind"] == "sparse"]
    hidden = [r for r in records if r["kind"] == "hidden"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(hidden) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    claimed = sum(r["claimed_edge_count"] for r in determinable)
    false_edges = sum(r["false_edge_count"] for r in determinable)
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "edge_f1": float(np.mean([r["edge_f1"] for r in sparse])),
        "false_edge_rate": (false_edges / claimed) if claimed else 0.0,
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in hidden])),
        "null_false_discovery_rate": float(np.mean([r["false_discovery"] for r in records if r["kind"] == "null"])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in hidden])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_experiments": float(np.mean([r["experiments"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(discover_couplings):
    development = [_evaluate_world(discover_couplings, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(discover_couplings, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_edge_f1": dev["edge_f1"],
        "development_false_edge_rate": dev["false_edge_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_null_false_discovery_rate": dev["null_false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_experiments": dev["mean_experiments"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_edge_f1": held["edge_f1"],
        "heldout_false_edge_rate": held["false_edge_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
