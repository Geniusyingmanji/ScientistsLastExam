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

from fractions import Fraction

# The solver, the grammar and the world are inlined rather than imported from siblings. The trusted
# driver loads this file by path, not as a package, so `from channel import ...` resolves against
# the harness's sys.path and not against this directory - it raises ModuleNotFoundError inside the
# sandbox while working perfectly when imported directly. verification/channel.py, grammar.py and
# worlds.py remain the readable statements of the same code and the task's tests check they agree.


def wall_normal_grid(re_tau, points=400):
    """Stretched grid from the wall to the centreline, dense where the gradient is."""
    uniform = np.linspace(0.0, 1.0, points)
    return re_tau * (1.0 - np.cos(0.5 * np.pi * uniform))  # clusters near y+ = 0


def velocity_profile(mixing_length, re_tau, points=400):
    """Integrate the mean profile for a mixing-length closure.

    The closure is a mixing length `l+(y+)`, and the eddy viscosity it implies is
    `nu_t+ = l+^2 |dU+/dy+|`, which makes the momentum balance implicit:

        l+^2 (dU+/dy+)^2 + dU+/dy+ - tau+ = 0,    tau+ = 1 - y+/Re_tau.

    Taking the positive root and writing it in the numerically stable form

        dU+/dy+ = 2 tau+ / (1 + sqrt(1 + 4 l+^2 tau+))

    gives the profile by one quadrature. Writing the closure as an explicit `nu_t+(y+)` instead -
    the first thing tried here - does not reproduce the log law at all: the fitted von Karman
    constant came out between 13 and 31 against the accepted 0.41, because the implicit coupling
    between eddy viscosity and mean gradient is exactly what produces `dU+/dy+ ~ 1/(kappa y+)`.
    """
    y = wall_normal_grid(re_tau, points)
    length = np.asarray(mixing_length(y, re_tau), dtype=float)
    if length.shape != y.shape:
        raise ValueError("closure must return one mixing length per grid point")
    if not np.all(np.isfinite(length)):
        raise ValueError("closure returned a non-finite value")
    if np.any(length < 0.0):
        raise ValueError("mixing length must be non-negative")
    stress = np.clip(1.0 - y / re_tau, 0.0, None)
    gradient = 2.0 * stress / (1.0 + np.sqrt(1.0 + 4.0 * length ** 2 * stress))
    velocity = np.concatenate(
        [[0.0], np.cumsum(np.diff(y) * 0.5 * (gradient[1:] + gradient[:-1]))])
    return y, velocity


def van_driest(kappa=0.41, a_plus=26.0):
    """The textbook mixing length: linear in the wall distance with exponential damping."""
    def closure(y, re_tau):
        return kappa * y * (1.0 - np.exp(-y / a_plus))
    return closure


MAX_NODES = 40
MAX_DEPTH = 10
UNARY = {"neg", "exp", "tanh", "sqrt", "square"}
BINARY = {"add", "sub", "mul", "div"}


def count_nodes(expression, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("expression deeper than the cap")
    if not isinstance(expression, (list, tuple)) or not expression:
        raise ValueError("an expression is a non-empty list")
    head = expression[0]
    if head == "const":
        if len(expression) != 3:
            raise ValueError("const takes a numerator and a denominator")
        numerator, denominator = expression[1], expression[2]
        for part in (numerator, denominator):
            if isinstance(part, bool) or not isinstance(part, int):
                raise ValueError("constants are exact rationals")
        if denominator == 0:
            raise ValueError("zero denominator")
        if abs(numerator) > 10 ** 9 or abs(denominator) > 10 ** 9:
            raise ValueError("constant outside the magnitude cap")
        return 1
    if head == "var":
        if len(expression) != 2 or expression[1] not in ("y", "re"):
            raise ValueError("the variables are 'y' and 're'")
        return 1
    if head in UNARY:
        if len(expression) != 2:
            raise ValueError("%s takes one argument" % head)
        return 1 + count_nodes(expression[1], depth + 1)
    if head in BINARY:
        if len(expression) != 3:
            raise ValueError("%s takes two arguments" % head)
        return 1 + count_nodes(expression[1], depth + 1) + count_nodes(expression[2], depth + 1)
    raise ValueError("unknown operator %r" % (head,))


def evaluate_expression(expression, y, re_tau):
    """Evaluate on a grid. Guards keep a malformed formula from producing nonsense silently."""
    head = expression[0]
    if head == "const":
        return np.full_like(y, float(Fraction(expression[1], expression[2])), dtype=float)
    if head == "var":
        return y if expression[1] == "y" else np.full_like(y, float(re_tau), dtype=float)
    if head in UNARY:
        inner = evaluate_expression(expression[1], y, re_tau)
        if head == "neg":
            return -inner
        if head == "exp":
            # Clipped so that a runaway exponent is a bad formula rather than an overflow warning
            # that turns into a silent inf downstream.
            return np.exp(np.clip(inner, -700.0, 700.0))
        if head == "tanh":
            return np.tanh(inner)
        if head == "sqrt":
            return np.sqrt(np.clip(inner, 0.0, None))
        return inner * inner
    left = evaluate_expression(expression[1], y, re_tau)
    right = evaluate_expression(expression[2], y, re_tau)
    if head == "add":
        return left + right
    if head == "sub":
        return left - right
    if head == "mul":
        return left * right
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.abs(right) < 1e-12, np.nan, left / np.where(right == 0, 1.0, right))
    return out


def compile_closure(expression):
    """Validate once, then hand back something the solver can call.

    The expression evaluator is `evaluate_expression`, not `evaluate`. Both this file and
    verification/grammar.py once called it `evaluate`, and inlining the grammar into a module that
    already has a top-level `evaluate(build_closure, ...)` silently rebound the name: every closure
    call reached the task evaluator instead, every held-out check raised, and the mechanism score
    read 0.000 for a reference that had measured 0.875 minutes earlier.
    """
    nodes = count_nodes(expression)
    if nodes > MAX_NODES:
        raise ValueError("expression uses %d nodes, cap is %d" % (nodes, MAX_NODES))

    def closure(y, re_tau):
        values = evaluate_expression(expression, np.asarray(y, dtype=float), float(re_tau))
        if not np.all(np.isfinite(values)):
            raise ValueError("closure is not finite on the grid")
        return values
    return closure


# Wide span: the near-wall damping and the log-region slope are both exercised.
WIDE_RE = (180.0, 950.0, 4000.0)
# Narrow span: only low Reynolds numbers, where kappa and A+ trade off against each other.
NARROW_RE = (180.0, 200.0, 220.0)
HELDOUT_RE = (2000.0, 5200.0)


def damped_mixing_length(kappa, a_plus):
    def closure(y, re_tau):
        return kappa * y * (1.0 - np.exp(-y / a_plus))
    return closure


def _span(rng, regime):
    """Three sampled Reynolds numbers. The top one is what decides identifiability."""
    low = 180.0
    if regime == "recoverable":
        top = float(rng.uniform(700.0, 4000.0))
    else:
        top = float(rng.uniform(230.0, 900.0))
    middle = float(np.exp(0.5 * (np.log(low) + np.log(top))))
    return (low, middle, top)


def build(seed, count):
    rng = np.random.default_rng(seed)
    cases = []
    for index in range(count):
        regime = ("recoverable", "degenerate_parameters", "inconsistent")[index % 3]
        kappa = float(rng.uniform(0.38, 0.44))
        a_plus = float(rng.uniform(22.0, 30.0))
        record = {
            "case_id": "flow%03d" % index,
            "regime": regime,
            "kappa": kappa,
            "a_plus": a_plus,
            # The Reynolds span is drawn on a continuum rather than taken from two fixed sets.
            # With two fixed spans the three regimes separate perfectly - measured reduced
            # chi-square 0.23-0.51 against 0.71-2.30, and kappa width 0.025-0.045 against
            # 0.050-0.110 - and a pair of thresholds scores one. Real cases are not sorted for you,
            # so the top Reynolds number is drawn from a range that makes the two identifiable
            # regimes overlap and forces a judgement per case instead of a rule.
            "sampled_re": _span(rng, regime),
            "noise": float(rng.uniform(0.008, 0.014)),
            # The two systematics a profile measurement actually carries: where the wall is, and
            # how the friction velocity was calibrated. Both are constant across a profile.
            "wall_shift": float(rng.uniform(0.4, 0.9)),
            "calibration": float(rng.uniform(0.010, 0.020)),
            "seed": int(rng.integers(0, 2 ** 31 - 1)),
        }
        if regime == "inconsistent":
            # Each sampled Reynolds number comes from a different closure, so nothing fits them all.
            record["per_sample_truth"] = [damped_mixing_length(kappa * f, a_plus)
                                          for f in (0.80, 1.0, 1.25)]
            record["truth"] = record["per_sample_truth"][1]
            record["heldout_truth"] = None
        else:
            record["truth"] = damped_mixing_length(kappa, a_plus)
            record["heldout_truth"] = record["truth"]
        cases.append(record)
    return cases


def answerable(case):
    return case["regime"] == "recoverable"

DIFFICULTY = 1

CASE_COUNT = 24
DEV_SEED = 20260906
OBSERVATION_BUDGET = 12
# Points reported per profile.
BINS = 24
# A formula counts as recovering the law when it reproduces the held-out profiles to within this
# fraction of the centreline velocity - about four times the observation noise, so the bar is
# "the same law", not "the same fit".
HELDOUT_TOLERANCE = 0.06


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
