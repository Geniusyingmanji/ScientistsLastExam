"""Hidden oracle for EnzymeKineticsLaw.

The candidate is given a budgeted assay and must say which rate law the enzyme obeys, with its
parameters - or refuse, when the enzyme obeys no law in the published family.

Six laws are in the family. Three of them - competitive, uncompetitive and noncompetitive
inhibition - are *indistinguishable from a substrate titration alone*: at a single inhibitor
concentration all three produce a saturating hyperbola. Separating them requires titrating
substrate at two or more inhibitor levels and reading how the apparent Km and Vmax move. That is
the experiment-design content of this task.

Ablating the reference measures what each competence is worth. Holding the fit and the refusal
tests fixed and varying only the design:

    3 inhibitor levels, both refusal tests   0.990
    2 inhibitor levels                       0.986
    1 inhibitor level  (substrate only)      0.315
    3 levels, never refusing                 0.490
    1 level, never refusing                  0.000

So varying the inhibitor is worth about +0.67 and knowing when to refuse about +0.50, and the two
are close to independent. Blanket abstention also scores 0.000 - the same scalar as never
refusing - which is why the discovery axes are reported separately: the two failures have
opposite false-discovery rates (0.00 against 1.00) and opposite coverage (0.00 against 1.00).

Two world kinds carry no discoverable law:

    misspecified  a two-site enzyme, the sum of two hyperbolae with well-separated Km. It looks
                  saturating and fits any single law badly, so a candidate that reports the best
                  of six is reporting a mechanism that is not there.
    null          catalysis is dead: velocity does not depend on substrate at all.

Both must be refused. The score normalises so that refusing *everything* earns exactly zero, and
the three discovery axes are reported separately because one scalar cannot say whether a claimed
mechanism was right.
"""
from __future__ import annotations

import math

import numpy as np

# Assay calls a candidate may spend per world.
#
# It is not what makes the task hard, and an earlier comment here claiming it "bites" was wrong:
# the ablation above reaches 0.986 on sixteen calls, so at 40 the budget was never binding. What
# it does is rule out answering by exhaustion - a six-by-six grid over substrate and inhibitor
# costs 36 - and make replication a real trade against a third inhibitor level. The reference
# design costs 24, which leaves four spare.
ASSAY_BUDGET = 28

# Relative error on sealed-grid velocity predictions at which parameter recovery scores zero. The
# reference implementation lands near 0.05, so this leaves headroom above it.
PREDICTION_TOLERANCE = 0.35

LAWS = (
    "michaelis_menten",
    "hill",
    "substrate_inhibition",
    "competitive",
    "uncompetitive",
    "noncompetitive",
)

REQUIRED_PARAMETERS = {
    "michaelis_menten": ("vmax", "km"),
    "hill": ("vmax", "km", "hill_n"),
    "substrate_inhibition": ("vmax", "km", "ki"),
    "competitive": ("vmax", "km", "ki"),
    "uncompetitive": ("vmax", "km", "ki"),
    "noncompetitive": ("vmax", "km", "ki"),
}


def _velocity(law, parameters, substrate, inhibitor):
    """Initial velocity under a named law. Shared by the oracle and by scoring, so a candidate's
    reported parameters are read through exactly the same equations the world was generated
    from."""
    vmax = float(parameters["vmax"])
    km = max(float(parameters["km"]), 1e-9)
    s = np.asarray(substrate, dtype=float)
    i = np.asarray(inhibitor, dtype=float)
    if law == "michaelis_menten":
        return vmax * s / (km + s)
    if law == "hill":
        n = float(parameters["hill_n"])
        return vmax * s ** n / (km ** n + s ** n)
    ki = max(float(parameters["ki"]), 1e-9)
    if law == "substrate_inhibition":
        return vmax * s / (km + s + s * s / ki)
    if law == "competitive":
        return vmax * s / (km * (1.0 + i / ki) + s)
    if law == "uncompetitive":
        return vmax * s / (km + s * (1.0 + i / ki))
    if law == "noncompetitive":
        return vmax * s / ((km + s) * (1.0 + i / ki))
    raise ValueError("unknown law %r" % (law,))


def _two_site_velocity(parameters, substrate, inhibitor):
    """Two independent catalytic sites with separated affinities.

    No single law in the family reproduces this - the curve has two shoulders - but any of them
    can be fitted to it with a plausible-looking residual, which is exactly the trap.

    The high-affinity site is competitively inhibited. Without that, every misspecified world was
    flat in the inhibitor, and "the inhibitor does nothing" became a tell for "refuse" that has
    nothing to do with judging whether a law fits.
    """
    s = np.asarray(substrate, dtype=float)
    i = np.asarray(inhibitor, dtype=float)
    km_a = parameters["km_a"] * (1.0 + i / parameters["ki_a"])
    high = parameters["vmax_a"] * s / (km_a + s)
    low = parameters["vmax_b"] * s / (parameters["km_b"] + s)
    return high + low


def _hill_inhibited_velocity(parameters, substrate, inhibitor):
    """A cooperative enzyme that is *also* competitively inhibited.

    The family carries cooperativity (hill) and competitive inhibition (competitive) as separate
    laws, and no member carries both, so nothing in it reproduces this enzyme. What makes it the
    sharpest world on the task is that the shortfall is invisible from a single substrate
    titration: at zero inhibitor this *is* a Hill curve, and fits one to about 0.9 sigma. A
    candidate that titrates substrate once reports `hill` with high confidence and books a false
    discovery. Titrating at two more inhibitor levels puts the best fit in the family at 13 sigma,
    and the same candidate refuses correctly.

    So on this world the difference between a false discovery and a correct refusal is exactly
    whether the inhibitor was varied - which is the experiment-design content this task exists to
    measure, made load-bearing rather than merely available.
    """
    s = np.asarray(substrate, dtype=float)
    i = np.asarray(inhibitor, dtype=float)
    n = parameters["hill_n"]
    km = parameters["km"] * (1.0 + i / parameters["ki"])
    return parameters["vmax"] * s ** n / (km ** n + s ** n)


_MISSPECIFIED_SHAPES = {
    "two_site": _two_site_velocity,
    "hill_inhibited": _hill_inhibited_velocity,
}


def _world(spec):
    """Build one hidden enzyme. Every draw is seeded, so the world is a function of the spec."""
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    world = {"kind": kind, "noise": spec["noise"], "seed": spec["seed"]}
    if kind == "null":
        # Dead catalysis: a constant turnover with no substrate dependence at all.
        world["floor"] = float(rng.uniform(0.02, 0.08))
        return world
    if kind == "misspecified":
        # Which way this world falls outside the family. Both must be refused; they are separated
        # so that "misspecified" cannot be recognised by shape. A candidate that learns to look
        # for two shoulders refuses the two-site worlds and books a false discovery on the others.
        shape = spec.get("shape", "two_site")
        world["shape"] = shape
        if shape == "two_site":
            world["parameters"] = {
                "vmax_a": float(rng.uniform(0.9, 1.4)),
                "km_a": float(rng.uniform(1.5, 4.0)),
                "vmax_b": float(rng.uniform(0.5, 0.9)),
                "km_b": float(rng.uniform(90.0, 220.0)),
                "ki_a": float(rng.uniform(15.0, 45.0)),
            }
        elif shape == "hill_inhibited":
            world["parameters"] = {
                "vmax": float(rng.uniform(1.0, 1.8)),
                "km": float(rng.uniform(10.0, 30.0)),
                "hill_n": float(rng.choice([1.8, 2.4, 3.0])),
                "ki": float(rng.uniform(15.0, 40.0)),
            }
        else:
            raise ValueError("unknown misspecified shape: %r" % (shape,))
        return world
    law = spec["law"]
    parameters = {"vmax": float(rng.uniform(0.8, 2.0)), "km": float(rng.uniform(3.0, 40.0))}
    if law == "hill":
        # Away from 1.0 in both directions: cooperative and negatively cooperative both occur.
        parameters["hill_n"] = float(rng.choice([1.8, 2.4, 3.1, 0.55]))
    if law in {"substrate_inhibition", "competitive", "uncompetitive", "noncompetitive"}:
        parameters["ki"] = float(rng.uniform(8.0, 60.0))
    world["law"] = law
    world["parameters"] = parameters
    return world


def _true_velocity(world, substrate, inhibitor):
    if world["kind"] == "null":
        return np.full(np.shape(substrate), world["floor"], dtype=float)
    if world["kind"] == "misspecified":
        shape = _MISSPECIFIED_SHAPES[world.get("shape", "two_site")]
        return shape(world["parameters"], substrate, inhibitor)
    return _velocity(world["law"], world["parameters"], substrate, inhibitor)


class _Assay:
    """The candidate's only view of the enzyme: one measured initial velocity per call.

    Noise is drawn from a generator seeded by the world *and by the call index*, so the same
    query at the same point in a run returns the same number - repeating a measurement to average
    noise down is allowed, and costs budget, which is the trade the task is about.
    """

    def __init__(self, world, budget):
        self.world = world
        self.budget = int(budget)
        self.calls = 0
        self.violated = False
        self.log = []

    def __call__(self, substrate_um, inhibitor_um=0.0):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("assay budget exhausted")
        s = float(substrate_um)
        i = float(inhibitor_um)
        if not (math.isfinite(s) and math.isfinite(i)) or s < 0.0 or i < 0.0:
            raise ValueError("substrate and inhibitor concentrations must be finite and >= 0")
        # The declared bounds are enforced, not merely announced. Without this the assay answered
        # anywhere, and a candidate could measure the enzyme directly on the extrapolation grid -
        # which sits eight times outside the substrate range the problem declares - turning a
        # generalisation diagnostic into another in-range measurement.
        if s > PUBLIC_PROBLEM["substrate_bounds_um"][1]:
            raise ValueError("substrate concentration is outside substrate_bounds_um")
        if i > PUBLIC_PROBLEM["inhibitor_bounds_um"][1]:
            raise ValueError("inhibitor concentration is outside inhibitor_bounds_um")
        self.calls += 1
        rng = np.random.default_rng((self.world["seed"], self.calls))
        clean = float(_true_velocity(self.world, s, i))
        value = clean + float(rng.normal(0.0, self.world["noise"]))
        self.log.append({"call": self.calls, "substrate_um": s, "inhibitor_um": i})
        return value


# The sealed grid a claim is checked against. It is never shown to the candidate. It lies inside
# the assay bounds - an earlier comment here claimed it reached beyond them, and it does not - so
# it asks whether the claimed law reproduces the enzyme at points the candidate did not happen to
# measure, not whether it survives extrapolation.
SEALED_SUBSTRATE = (0.5, 2.0, 6.0, 18.0, 55.0, 160.0, 400.0)
SEALED_INHIBITOR = (0.0, 12.0, 40.0)

# Extrapolation is asked separately, well outside the assay bounds. It is a diagnostic, not part
# of the score: `mechanism_score` already gates on naming the right law, so nothing is added by
# scoring generalisation twice. What it records is the gap between fitting a curve and recovering
# a mechanism - a right law with right constants extrapolates for free, and on this task the
# reference stays under 0.034 relative error eight times outside the substrate range it measured.
EXTRAPOLATION_SUBSTRATE = (900.0, 1800.0, 4000.0)
EXTRAPOLATION_INHIBITOR = (0.0, 90.0, 150.0)


def _prediction_error(world, law, parameters, grid=None):
    """Relative error of the claimed law on a sealed grid, against the true velocities."""
    substrate, inhibitor = grid or (SEALED_SUBSTRATE, SEALED_INHIBITOR)
    s, i = np.meshgrid(np.array(substrate), np.array(inhibitor), indexing="ij")
    truth = _true_velocity(world, s, i)
    try:
        claimed = _velocity(law, parameters, s, i)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    claimed = np.asarray(claimed, dtype=float)
    if not np.all(np.isfinite(claimed)):
        return None
    scale = max(float(np.max(np.abs(truth))), 1e-9)
    return float(np.sqrt(np.mean((claimed - truth) ** 2))) / scale


def _validate_submission(submission):
    """Read the candidate's claim. Anything malformed is a candidate failure, never an oracle one."""
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = bool(submission.get("abstain", False))
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if abstain:
        return None, {}, confidence, True
    law = submission.get("law")
    if law not in LAWS:
        raise ValueError("law must be one of %s, or abstain" % (LAWS,))
    raw = submission.get("parameters")
    if not isinstance(raw, dict):
        raise ValueError("parameters must be a mapping")
    parameters = {}
    for name in REQUIRED_PARAMETERS[law]:
        if name not in raw:
            raise ValueError("law %s requires parameter %r" % (law, name))
        value = float(raw[name])
        if not math.isfinite(value):
            raise ValueError("parameter %r must be finite" % (name,))
        parameters[name] = value
    return law, parameters, confidence, False


def _mechanism_metrics(world, law, parameters, abstain):
    """The discovery triple for one world.

    A world with no law in the family scores on refusal alone; a world with one scores on whether
    the family was named *and* the parameters reproduce velocities the candidate never saw.
    """
    if world["kind"] in {"null", "misspecified"}:
        correct = bool(abstain)
        return {
            "law_correct": False,
            "prediction_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
            "extrapolation_score": 1.0 if correct else 0.0,
        }
    if abstain or law is None:
        return {
            "law_correct": False,
            "prediction_score": 0.0,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "extrapolation_score": 0.0,
        }
    law_correct = bool(law == world["law"])
    error = _prediction_error(world, law, parameters)
    if error is None:
        prediction = 0.0
    else:
        prediction = float(np.clip(1.0 - error / PREDICTION_TOLERANCE, 0.0, 1.0))
    far = _prediction_error(
        world, law, parameters, (EXTRAPOLATION_SUBSTRATE, EXTRAPOLATION_INHIBITOR))
    extrapolation = 0.0 if far is None else float(
        np.clip(1.0 - far / PREDICTION_TOLERANCE, 0.0, 1.0))
    # Naming the family is necessary but not sufficient: a right name with wrong constants
    # predicts badly and scores low, and a wrong name scores zero however well it happens to fit
    # inside the assay range.
    return {
        "law_correct": law_correct,
        "prediction_score": prediction,
        "mechanism_score": prediction if law_correct else 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "extrapolation_score": extrapolation if law_correct else 0.0,
    }


# Six in-library worlds, two that fall outside the family in different ways, and one dead enzyme.
# The two misspecified shapes are both present in both splits: a candidate that recognises only
# one of them refuses half the no-law worlds and books a false discovery on the other half.
DEVELOPMENT_WORLDS = (
    {"kind": "in_library", "law": "michaelis_menten", "seed": 20260902, "noise": 0.010},
    {"kind": "in_library", "law": "hill", "seed": 20260903, "noise": 0.010},
    {"kind": "in_library", "law": "competitive", "seed": 20260904, "noise": 0.008},
    {"kind": "in_library", "law": "uncompetitive", "seed": 20260905, "noise": 0.008},
    {"kind": "in_library", "law": "noncompetitive", "seed": 20260906, "noise": 0.008},
    {"kind": "in_library", "law": "substrate_inhibition", "seed": 20260907, "noise": 0.010},
    {"kind": "misspecified", "shape": "two_site", "seed": 20260908, "noise": 0.010},
    {"kind": "misspecified", "shape": "hill_inhibited", "seed": 20260910, "noise": 0.010},
    {"kind": "null", "seed": 20260909, "noise": 0.010},
)

# Held out with different seeds, different noise, and the two in-library laws the development
# split's held-out half was missing, so a candidate tuned to the development worlds is measured on
# laws it did not see saturate.
HELDOUT_WORLDS = (
    {"kind": "in_library", "law": "competitive", "seed": 771301, "noise": 0.012},
    {"kind": "in_library", "law": "hill", "seed": 771302, "noise": 0.012},
    {"kind": "in_library", "law": "noncompetitive", "seed": 771303, "noise": 0.012},
    {"kind": "in_library", "law": "uncompetitive", "seed": 771306, "noise": 0.012},
    {"kind": "in_library", "law": "substrate_inhibition", "seed": 771307, "noise": 0.012},
    {"kind": "misspecified", "shape": "two_site", "seed": 771304, "noise": 0.012},
    {"kind": "misspecified", "shape": "hill_inhibited", "seed": 771308, "noise": 0.012},
    {"kind": "null", "seed": 771305, "noise": 0.012},
)

PUBLIC_PROBLEM = {
    "assay_budget_calls": ASSAY_BUDGET,
    "substrate_bounds_um": [0.0, 500.0],
    "inhibitor_bounds_um": [0.0, 60.0],
    "candidate_laws": list(LAWS),
    "required_parameters": {k: list(v) for k, v in REQUIRED_PARAMETERS.items()},
    "velocity_units": "umol_per_min_per_mg",
    "noise_sigma_hint": "additive Gaussian, sigma between 0.008 and 0.012 in velocity units",
    "abstain_when": "the enzyme obeys no law in candidate_laws",
}


def _evaluate_world(discover_kinetics, spec, split, index):
    world = _world(spec)
    assay = _Assay(world, ASSAY_BUDGET)
    problem = dict(PUBLIC_PROBLEM)
    try:
        submission = discover_kinetics(problem, assay)
        law, parameters, confidence, abstain = _validate_submission(submission)
        if assay.violated:
            raise RuntimeError("assay budget exceeded")
        mechanism = _mechanism_metrics(world, law, parameters, abstain)
        target_confidence = (
            mechanism["mechanism_score"] if world["kind"] == "in_library" else 0.0
        )
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "law_correct": mechanism["law_correct"],
            "prediction_score": round(mechanism["prediction_score"], 6),
            "mechanism_score": round(mechanism["mechanism_score"], 6),
            "correct_refusal": mechanism["correct_refusal"],
            "false_discovery": mechanism["false_discovery"],
            "extrapolation_score": round(mechanism["extrapolation_score"], 6),
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - target_confidence) ** 2, 6
            ),
            "assay_calls": assay.calls,
        }
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            # Every key the aggregation reads, so a failed world cannot raise a KeyError two
            # hundred lines below and be reported as an infrastructure failure.
            "law_correct": False,
            "prediction_score": 0.0,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "extrapolation_score": 0.0,
            "abstained": True,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "assay_calls": assay.calls,
        }


def _split_summary(records):
    """Aggregate one split. The three discovery axes stay separate, and coverage is a fourth
    column rather than a fourth axis: the triple says how good a discovery was, coverage says
    whether one was attempted at all."""
    supported = [r for r in records if r["kind"] == "in_library"]
    unsupported = [r for r in records if r["kind"] != "in_library"]
    raw_mechanism = float(np.mean([r["mechanism_score"] for r in records]))
    # What a candidate scores by declining every world: it is right on every unsupported world
    # and wrong on every supported one. Subtracting it makes blanket abstention worth exactly
    # zero, which is the whole point of scoring refusal as an axis rather than as a score.
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip(
        (raw_mechanism - always_abstain) / (1.0 - always_abstain), 0.0, 1.0
    ))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw_mechanism,
        "law_identification_rate": float(np.mean([r["law_correct"] for r in supported])),
        "prediction_score": float(np.mean([r["prediction_score"] for r in supported])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in supported])),
        "extrapolation_score": float(np.mean([r["extrapolation_score"] for r in supported])),
        "confidence_calibration": float(
            np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_assay_calls": float(np.mean([r["assay_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(discover_kinetics):
    development = [
        _evaluate_world(discover_kinetics, spec, "development", index)
        for index, spec in enumerate(DEVELOPMENT_WORLDS)
    ]
    heldout = [
        _evaluate_world(discover_kinetics, spec, "heldout", index)
        for index, spec in enumerate(HELDOUT_WORLDS)
    ]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_law_identification_rate": dev["law_identification_rate"],
        "development_prediction_score": dev["prediction_score"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_extrapolation_score": dev["extrapolation_score"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_assay_calls": dev["mean_assay_calls"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_law_identification_rate": held["law_identification_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "heldout_extrapolation_score": held["extrapolation_score"],
        "per_instance": development + heldout,
    }
