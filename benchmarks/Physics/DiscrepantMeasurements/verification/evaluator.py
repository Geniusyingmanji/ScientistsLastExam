"""Hidden oracle for DiscrepantMeasurements.

Eight groups have measured the same physical constant. Each publishes a value and a one-sigma
uncertainty. The values do not agree as well as those uncertainties say they should. The candidate
must say what is wrong with the body of evidence, give a best value with an honest uncertainty -
or say that no single best value is defensible.

Four things can be wrong, and *they are not separable from the published table*:

    consistent      nothing is wrong. The scatter matches the quoted errors, and a weighted mean
                    with its usual uncertainty is the right answer. Declaring a discrepancy here
                    is a false discovery.
    underestimated  every group has quoted an honest central value and an uncertainty that is too
                    small by a common factor. The weighted mean is still unbiased; what is wrong
                    is the error bar on it, which must be inflated.
    outlier         one group has an unquoted systematic. Its central value is displaced. The
                    other seven are fine, and the answer is to find that one group.
    two_populations two methods disagree with each other by more than either can explain. Each
                    group is internally sound. There is no defensible single number, and the
                    honest answer is to decline to give one.

From the published table alone the last three are confusable: an eight-measurement sample drawn
with errors understated by 2.5x produces a largest deviation about as extreme as a genuine single
outlier, and both look like scatter that "must mean something".

What separates them is a *split test*, which costs budget. Asking group k to report its value
separately on two halves of its data reveals whether the group is internally consistent:

    consistent      every split is clean
    underestimated  every split is inconsistent - the understatement is inside every group
    outlier         exactly one split is inconsistent - the drifting systematic shows up as a
                    difference between the halves
    two_populations every split is clean; the disagreement lives *between* methods, not inside
                    any group

So the diagnosis is only reachable by choosing which groups to interrogate, which is the
experiment-design content of this task, and the method labels have to be read to catch the last
case at all.

Scoring keeps the discovery axes separate and normalises so that declining every world earns
exactly zero.
"""
from __future__ import annotations

import math

import numpy as np

# Split tests a candidate may buy per world, against eight groups. Fewer than the table, so
# splitting everything is not available and *which* groups to interrogate is a decision.
#
# It is the decision the task is about. Splitting only the most deviant groups finds a single
# unquoted systematic but cannot tell it from a table that understates everywhere - the most
# deviant groups split badly under both. Splitting only typical groups shows whether the
# understatement is global but can miss the one group that carries it. The diagnosis needs both,
# which is what makes five a budget rather than a formality.
SPLIT_BUDGET = 5

N_GROUPS = 8

DIAGNOSES = ("consistent", "underestimated", "outlier", "two_populations")

METHODS = ("spectroscopy", "scattering")


def _world(spec):
    """Build one body of evidence. Every draw is seeded, so the world is a function of the spec.

    Each group's data is modelled as two halves. What it publishes is the mean of the two and a
    quoted uncertainty; what a split test buys is the two halves separately. A group whose
    calibration drifted during its run has halves that differ, and a displaced central value is
    the *consequence* of that drift rather than an independent fact - which is why a split test
    can find it and reading the published table cannot.
    """
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    truth = float(rng.uniform(1.0, 2.0))
    quoted = np.exp(rng.uniform(math.log(0.004), math.log(0.016), size=N_GROUPS))
    methods = [METHODS[i % 2] for i in range(N_GROUPS)]
    rng.shuffle(methods)

    # The statistical uncertainty each half actually has. A half holds half the data, so it is
    # sqrt(2) times the full-sample sigma - `real` when the group's error bar is honest, larger
    # when the world says the whole table understates.
    real = quoted.copy()
    # Systematic offset of the second half relative to the first, in absolute units. The published
    # central value carries half of it; a split test sees all of it.
    drift = np.zeros(N_GROUPS)
    # A shift common to both halves. Invisible to a split test by construction - this is how two
    # methods can disagree while every group is internally sound.
    common = np.zeros(N_GROUPS)
    culprit = None

    if kind == "consistent":
        pass
    elif kind == "underestimated":
        real = quoted * float(spec.get("scale_factor", 2.5))
    elif kind == "outlier":
        culprit = int(rng.integers(0, N_GROUPS))
        displacement = float(spec.get("displacement_sigma", 4.5))
        drift[culprit] = 2.0 * displacement * quoted[culprit] * float(rng.choice([-1.0, 1.0]))
    elif kind == "two_populations":
        separation = float(spec.get("separation_sigma", 4.0))
        scale = float(np.mean(quoted))
        for index, method in enumerate(methods):
            common[index] = (separation * scale / 2.0) * (
                1.0 if method == METHODS[0] else -1.0)
    else:
        raise ValueError("unknown world kind: %r" % (kind,))

    # The first half carries the correct calibration and the second carries the drifted one, so
    # the published mean is displaced by half the drift. Writing this symmetrically about the
    # truth - minus delta/2 and plus delta/2 - cancels the drift in the mean, which leaves a world
    # whose central values are perfectly sound and whose only defect is one noisy split. That is
    # not what an outlier is.
    half_sigma = real * math.sqrt(2.0)
    first = truth + common + rng.normal(0.0, half_sigma)
    second = truth + common + drift + rng.normal(0.0, half_sigma)
    values = (first + second) / 2.0

    return {
        "kind": kind,
        "seed": spec["seed"],
        "truth": truth,
        "values": values,
        "quoted": quoted,
        "real": real,
        "methods": methods,
        "halves": (first, second),
        "half_sigma": half_sigma,
        "drift": drift,
        "culprit": culprit,
    }


class _SplitTests:
    """The candidate's only way past the published table: ask one group to split its data.

    A split is charged. Repeating the same group's split returns the same numbers - the halves are
    a property of the group's data, not a fresh experiment - so paying twice for one group buys
    nothing, and the budget is spent on *which* groups to interrogate.
    """

    def __init__(self, world, budget):
        self.world = world
        self.budget = int(budget)
        self.calls = 0
        self.violated = False
        self.requested = []

    def __call__(self, group_index):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("split-test budget exhausted")
        index = int(group_index)
        if not 0 <= index < N_GROUPS:
            raise ValueError("group_index must be in [0, %d)" % N_GROUPS)
        self.calls += 1
        self.requested.append(index)
        first, second = self.world["halves"]
        # The halves are quoted with the group's own error bar scaled for half the data. When the
        # world understates, this is understated in exactly the same way - which is what makes the
        # split test able to reveal the understatement.
        half_quoted = float(self.world["quoted"][index]) * math.sqrt(2.0)
        return {
            "group_index": index,
            "first_half_value": float(first[index]),
            "second_half_value": float(second[index]),
            "half_quoted_sigma": half_quoted,
        }


def _ideal_uncertainty(world):
    """The uncertainty an honest analysis of this world would report on its best value."""
    quoted = world["quoted"]
    if world["kind"] == "outlier":
        keep = np.ones(N_GROUPS, dtype=bool)
        keep[world["culprit"]] = False
        return float(1.0 / math.sqrt(np.sum(1.0 / quoted[keep] ** 2)))
    weight = float(np.sum(1.0 / quoted ** 2))
    base = 1.0 / math.sqrt(weight)
    if world["kind"] == "underestimated":
        # The scale factor is what the inflation is for: the weighted mean is unbiased, its error
        # bar is not.
        return base * float(np.mean(world["real"] / quoted))
    return base


# Relative accuracy at which a best value scores zero, in units of the honest uncertainty.
ACCURACY_TOLERANCE_SIGMA = 6.0

# How far a claimed uncertainty may be from the honest one before it scores zero, as a ratio.
# Three, symmetric in the logarithm: understating by 3x and inflating by 3x are both wrong, and a
# candidate that reports a huge uncertainty to make its pull look good must not be rewarded.
CALIBRATION_TOLERANCE_RATIO = 3.0

PUBLIC_PROBLEM = {
    "split_test_budget": SPLIT_BUDGET,
    "group_count": N_GROUPS,
    "candidate_diagnoses": list(DIAGNOSES),
    "abstain_when": "no single best value is defensible for this body of evidence",
    "diagnosis_meanings": {
        "consistent": "the scatter matches the quoted uncertainties",
        "underestimated": "every group's quoted uncertainty is too small by a common factor",
        "outlier": "one group carries an unquoted systematic; name it in culprit_index",
        "two_populations": "two methods disagree by more than either can explain",
    },
}


def _published_table(world):
    """What every candidate sees before spending anything."""
    return [
        {
            "group_index": index,
            "value": float(world["values"][index]),
            "quoted_sigma": float(world["quoted"][index]),
            "method": world["methods"][index],
        }
        for index in range(N_GROUPS)
    ]


def _validate_submission(submission):
    """Read the candidate's claim. Anything malformed is a candidate failure, never an oracle one."""
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = bool(submission.get("abstain", False))
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    diagnosis = submission.get("diagnosis")
    if diagnosis is not None and diagnosis not in DIAGNOSES:
        raise ValueError("diagnosis must be one of %s or null" % (DIAGNOSES,))
    culprit = submission.get("culprit_index")
    if culprit is not None:
        culprit = int(culprit)
        if not 0 <= culprit < N_GROUPS:
            raise ValueError("culprit_index must be in [0, %d)" % N_GROUPS)
    if abstain:
        return None, None, diagnosis, culprit, confidence, True
    estimate = float(submission["best_value"])
    uncertainty = float(submission["uncertainty"])
    if not (math.isfinite(estimate) and math.isfinite(uncertainty)):
        raise ValueError("best_value and uncertainty must be finite")
    if uncertainty <= 0.0:
        raise ValueError("uncertainty must be positive")
    return estimate, uncertainty, diagnosis, culprit, confidence, False


def _metrics(world, estimate, uncertainty, diagnosis, culprit, abstain):
    """The discovery axes for one world.

    `mechanism_score` is the one that is averaged. It asks for the diagnosis *and* a best value
    that survives comparison with the truth, because naming the defect without being able to
    correct for it is not a finished piece of evidence synthesis. Calibration is reported beside
    it rather than inside it: a candidate can be accurate and overconfident, and averaging the two
    hides which.
    """
    blank = {
        "diagnosis_correct": False,
        "accuracy_score": 0.0,
        "calibration_score": 0.0,
        "culprit_correct": False,
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
    }
    if world["kind"] == "two_populations":
        correct = bool(abstain)
        blank.update({
            "diagnosis_correct": bool(diagnosis == "two_populations"),
            "accuracy_score": 1.0 if correct else 0.0,
            "calibration_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": not correct,
        })
        return blank
    if abstain or estimate is None:
        # A defensible value existed and none was given. That is not a false discovery - nothing
        # was claimed - but it is not a discovery either.
        return blank

    ideal = _ideal_uncertainty(world)
    error = abs(estimate - world["truth"])
    accuracy = float(np.clip(1.0 - error / (ACCURACY_TOLERANCE_SIGMA * ideal), 0.0, 1.0))
    ratio = uncertainty / ideal
    calibration = float(np.clip(
        1.0 - abs(math.log(ratio)) / math.log(CALIBRATION_TOLERANCE_RATIO), 0.0, 1.0))
    diagnosis_correct = bool(diagnosis == world["kind"])
    culprit_correct = bool(
        world["kind"] != "outlier" or (culprit is not None and culprit == world["culprit"]))
    earned = diagnosis_correct and culprit_correct
    blank.update({
        "diagnosis_correct": diagnosis_correct,
        "accuracy_score": accuracy,
        "calibration_score": calibration,
        "culprit_correct": culprit_correct,
        "mechanism_score": accuracy if earned else 0.0,
        "correct_refusal": False,
        "false_discovery": False,
    })
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "consistent", "seed": 5100301},
    {"kind": "consistent", "seed": 5100302},
    {"kind": "underestimated", "seed": 5100303, "scale_factor": 2.5},
    {"kind": "underestimated", "seed": 5100304, "scale_factor": 3.2},
    {"kind": "outlier", "seed": 5100305, "displacement_sigma": 4.5},
    {"kind": "outlier", "seed": 5100306, "displacement_sigma": 5.5},
    {"kind": "two_populations", "seed": 5100307, "separation_sigma": 4.0},
    {"kind": "two_populations", "seed": 5100308, "separation_sigma": 5.0},
)

HELDOUT_WORLDS = (
    {"kind": "consistent", "seed": 7710401},
    {"kind": "underestimated", "seed": 7710402, "scale_factor": 2.0},
    {"kind": "underestimated", "seed": 7710403, "scale_factor": 4.0},
    {"kind": "outlier", "seed": 7710404, "displacement_sigma": 3.8},
    {"kind": "outlier", "seed": 7710405, "displacement_sigma": 6.0},
    {"kind": "two_populations", "seed": 7710406, "separation_sigma": 3.5},
    {"kind": "two_populations", "seed": 7710407, "separation_sigma": 6.0},
    {"kind": "consistent", "seed": 7710408},
)


ROW_KEYS = (
    "diagnosis_correct", "accuracy_score", "calibration_score", "culprit_correct",
    "mechanism_score", "correct_refusal", "false_discovery",
)


def _evaluate_world(synthesize_evidence, spec, split, index):
    world = _world(spec)
    tests = _SplitTests(world, SPLIT_BUDGET)
    problem = dict(PUBLIC_PROBLEM)
    problem["measurements"] = _published_table(world)
    base = {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "split_tests_used": 0,
    }
    try:
        submission = synthesize_evidence(problem, tests)
        estimate, uncertainty, diagnosis, culprit, confidence, abstain = _validate_submission(
            submission)
        if tests.violated:
            raise RuntimeError("split-test budget exceeded")
        metrics = _metrics(world, estimate, uncertainty, diagnosis, culprit, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "split_tests_used": tests.calls,
            "distinct_groups_split": len(set(tests.requested)),
        })
        for key in ("accuracy_score", "calibration_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        # Every key the aggregation reads. A failure row that carries fewer keys than a scored one
        # raises a KeyError inside the summary and is reported as an infrastructure failure, which
        # aborts the campaign instead of scoring the submission.
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "split_tests_used": tests.calls,
            "distinct_groups_split": len(set(tests.requested)),
        })
        return row


def _split_summary(records):
    """Aggregate one split. The discovery axes stay separate, and coverage is a column rather than
    an axis: the axes say how good a synthesis was, coverage says whether one was attempted."""
    answerable = [r for r in records if r["kind"] != "two_populations"]
    unanswerable = [r for r in records if r["kind"] == "two_populations"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    # What declining everything earns: right on every unanswerable world, wrong on every other.
    # Subtracting it makes blanket abstention worth exactly zero.
    always_abstain = len(unanswerable) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "diagnosis_rate": float(np.mean([r["diagnosis_correct"] for r in records])),
        "accuracy_score": float(np.mean([r["accuracy_score"] for r in answerable])),
        "calibration_score": float(np.mean([r["calibration_score"] for r in answerable])),
        "culprit_rate": float(np.mean(
            [r["culprit_correct"] for r in records if r["kind"] == "outlier"])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unanswerable])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unanswerable])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in answerable])),
        "confidence_calibration": float(
            np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_split_tests": float(np.mean([r["split_tests_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(synthesize_evidence):
    development = [
        _evaluate_world(synthesize_evidence, spec, "development", index)
        for index, spec in enumerate(DEVELOPMENT_WORLDS)
    ]
    heldout = [
        _evaluate_world(synthesize_evidence, spec, "heldout", index)
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
        "development_diagnosis_rate": dev["diagnosis_rate"],
        "development_accuracy_score": dev["accuracy_score"],
        "development_calibration_score": dev["calibration_score"],
        "development_culprit_rate": dev["culprit_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_split_tests": dev["mean_split_tests"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_diagnosis_rate": held["diagnosis_rate"],
        "heldout_accuracy_score": held["accuracy_score"],
        "heldout_calibration_score": held["calibration_score"],
        "heldout_culprit_rate": held["culprit_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
