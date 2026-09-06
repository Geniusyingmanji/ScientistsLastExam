"""Hidden oracle for WallClosureDiscovery.

Data-driven turbulence closure is one of the most worked-on problems in engineering fluid
mechanics, and its standing criticism is not that the fits are bad. It is that they are validated
where they were trained. A closure fitted to profiles at one set of Reynolds numbers can reproduce
them perfectly and say nothing about a flow ten times larger, because the observations never
reached the wall distances where the rest of the closure lives.

So this task does not ask only for a law. It asks whether a searcher knows when the data it has
cannot support one.

Three regimes, one answerable:

  * `recoverable` - a single closure generated every profile and the sampled Reynolds numbers reach
    where its parameters bite. Submit the formula; it is scored on *held-out* Reynolds numbers an
    order of magnitude larger.
  * `outer_unconstrained` - a single closure generated every profile, but part of its structure
    switches on above the largest `y+` any sampled flow reaches. Measured: the correction changes
    the sampled centreline velocity by 0.0000 and the held-out one by 1.23 against a noise level of
    0.18. A fit will look excellent and be wrong. Abstention is correct.
  * `inconsistent` - no single closure generated the profiles. Abstention is correct, and here the
    residuals show it.

The last two fail differently on purpose. A searcher that abstains when its residuals are large
catches `inconsistent` and walks straight into `outer_unconstrained`, which is the mistake the
literature is about.

The product is a **formula**, not a fitted function: an expression over `y+` and `Re_tau` in a small
grammar with a 40-node cap, submitted as data. It is scored by running it through the same frozen
solver at held-out Reynolds numbers. The node cap is what keeps this a search for a law rather than
for a flexible interpolant.

Three axes, reported separately and never averaged, with denominators, plus a coverage counter -
the same contract every discovery task here uses.
"""
from __future__ import annotations

import math

import numpy as np

from channel import velocity_profile
from grammar import MAX_DEPTH, MAX_NODES, compile_closure, count_nodes
from worlds import HELDOUT_RE, answerable, build

DIFFICULTY = 1

CASE_COUNT = 24
DEV_SEED = 20260906
OBSERVATION_BUDGET = 12
# Points reported per profile.
BINS = 24
# A formula counts as recovering the law when it reproduces the held-out profiles to within this
# fraction of the centreline velocity - about four times the observation noise, so the bar is
# "the same law", not "the same fit".
HELDOUT_TOLERANCE = 0.04


class Windtunnel:
    """Returns noisy mean profiles at sampled Reynolds numbers, charged against a run budget."""

    def __init__(self, case, budget):
        self._case = case
        self._remaining = int(budget)
        self._calls = 0

    @property
    def remaining(self):
        return self._remaining

    def observe(self, re_tau):
        self._calls += 1
        if self._calls > 64:
            raise ValueError("too many observation calls")
        if isinstance(re_tau, bool) or not isinstance(re_tau, (int, float)):
            raise ValueError("re_tau must be a number")
        value = float(re_tau)
        sampled = self._case["sampled_re"]
        if value not in sampled:
            raise ValueError("re_tau must be one of the sampled Reynolds numbers")
        if self._remaining <= 0:
            raise ValueError("observation budget exhausted")
        self._remaining -= 1
        index = sampled.index(value)
        truth = self._case.get("per_sample_truth", [self._case["truth"]] * len(sampled))[index]
        y, u = velocity_profile(truth, value)
        rng = np.random.default_rng((self._case["seed"] * 131 + index * 7919) & 0xFFFFFFFF)
        # Correlated error, not independent per-point noise. A profile measurement carries an
        # unknown wall position and an unknown friction-velocity calibration, and both are constant
        # across the profile - which is why averaging over four hundred points does not beat them
        # down. With independent noise only, the kappa/A+ degeneracy this task turns on disappears:
        # the fit resolves a pair that differs by 0.165 in the sampled range because sqrt(1200)
        # shrinks the uncertainty to 0.005. With the systematics it survives, which is also what
        # happens in the laboratory.
        wall_shift = rng.normal(0.0, self._case["wall_shift"])
        calibration = 1.0 + rng.normal(0.0, self._case["calibration"])
        shifted = np.interp(np.clip(y + wall_shift, 0.0, None), y, u)
        noisy = calibration * shifted + rng.normal(
            0.0, self._case["noise"] * max(u[-1], 1.0), size=u.shape)
        # Binned to what an experiment or a coarse simulation actually delivers. Handing back all
        # four hundred solver nodes gives the fit sqrt(1200) worth of averaging and dissolves the
        # kappa/A+ degeneracy this task turns on - measured: a pair separated by 0.165 in the
        # sampled range, at a noise scale of 0.167, was still resolved.
        edges = np.geomspace(max(y[1], 0.3), y[-1], BINS + 1)
        centres, means = [], []
        for low, high in zip(edges[:-1], edges[1:]):
            mask = (y >= low) & (y <= high)
            if not mask.any():
                continue
            centres.append(float(y[mask].mean()))
            means.append(float(noisy[mask].mean()))
        return {"re_tau": value,
                "y_plus": centres,
                "u_plus": means,
                "noise_sigma": float(self._case["noise"] * max(u[-1], 1.0)),
                "remaining_runs": self._remaining}


def _public_case(case, budget):
    return {
        "case_id": case["case_id"],
        "sampled_re_tau": [float(v) for v in case["sampled_re"]],
        "heldout_re_tau": list(HELDOUT_RE),
        "observation_budget": budget,
        "max_formula_nodes": MAX_NODES,
        "max_formula_depth": MAX_DEPTH,
        "grammar": {
            "variables": ["y", "re"],
            "unary": ["neg", "exp", "tanh", "sqrt", "square"],
            "binary": ["add", "sub", "mul", "div"],
            "constant": "[\"const\", numerator, denominator]",
        },
        "closure_meaning": "the mixing length l+(y+), from which nu_t+ = l+^2 |dU+/dy+|",
        "heldout_tolerance": HELDOUT_TOLERANCE,
    }


def _read_report(value):
    if not isinstance(value, dict):
        raise ValueError("a report is a mapping")
    abstain = value.get("abstain")
    if not isinstance(abstain, bool):
        raise ValueError("'abstain' must be a boolean")
    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("'confidence' must be a number")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must lie in [0, 1]")
    formula = None
    if not abstain:
        formula = value.get("mixing_length")
        if formula is None:
            raise ValueError("'mixing_length' is required when not abstaining")
        count_nodes(formula)
    return abstain, formula, confidence


def _reproduces_heldout(formula, case):
    """Does this formula reproduce the held-out profiles, at Reynolds numbers never sampled?"""
    closure = compile_closure(formula)
    truth = case.get("heldout_truth")
    if truth is None:
        return False
    for re_tau in HELDOUT_RE:
        _y, predicted = velocity_profile(closure, re_tau)
        _y2, actual = velocity_profile(truth, re_tau)
        scale = max(abs(actual[-1]), 1.0)
        if float(np.max(np.abs(predicted - actual))) > HELDOUT_TOLERANCE * scale:
            return False
    return True


def evaluate(build_closure, seed=DEV_SEED, count=CASE_COUNT, budget=OBSERVATION_BUDGET):
    cases = build(seed, count)
    rows = []
    for case in cases:
        record = {"case_id": case["case_id"], "regime": case["regime"],
                  "answerable": answerable(case)}
        try:
            tunnel = Windtunnel(case, budget)
            abstain, formula, confidence = _read_report(
                build_closure(_public_case(case, budget), tunnel.observe))
            generalises = bool(not abstain and _reproduces_heldout(formula, case))
            record.update({
                "valid": True, "abstained": abstain, "confidence": confidence,
                "runs_used": budget - tunnel.remaining,
                "formula_nodes": count_nodes(formula) if formula is not None else 0,
                "recovered": bool(generalises and answerable(case)),
                # Submitting a law that does not survive the held-out flows is the false discovery
                # this field is about, and it is the failure the literature reports.
                "false_law": bool(not abstain and not generalises),
                "laws_submitted": 0 if abstain else 1,
            })
        except Exception as exc:  # noqa: BLE001 - a bad report scores zero, it does not crash this
            record.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "abstained": False, "confidence": 0.0, "runs_used": 0, "formula_nodes": 0,
                "recovered": False, "false_law": False, "laws_submitted": 0,
            })
        rows.append(record)

    findable = [r for r in rows if r["answerable"]]
    unfindable = [r for r in rows if not r["answerable"]]
    recovery = (sum(1 for r in findable if r["recovered"]) / len(findable)) if findable else 0.0
    submitted = sum(r["laws_submitted"] for r in rows)
    false_laws = sum(1 for r in rows if r["false_law"])
    false_discovery = (false_laws / submitted) if submitted else 0.0
    refusal = (sum(1 for r in unfindable if r["abstained"]) / len(unfindable)) if unfindable else 0.0
    coverage = sum(1 for r in rows if not r["abstained"]) / len(rows) if rows else 0.0

    combined = recovery * (1.0 - false_discovery) * refusal
    return {
        "combined_score": float(max(0.0, combined)),
        "valid": 1.0 if any(r["valid"] for r in rows) else 0.0,
        "feasibility_rate": sum(1 for r in rows if r["valid"]) / len(rows),
        "raw_score": float(combined),
        "mechanism_score": float(recovery),
        "mechanism_score_denominator": len(findable),
        "false_discovery_rate": float(false_discovery),
        "false_discovery_denominator": submitted,
        "correct_refusal_rate": float(refusal),
        "correct_refusal_denominator": len(unfindable),
        "discovery_coverage": float(coverage),
        "per_case": rows,
    }
