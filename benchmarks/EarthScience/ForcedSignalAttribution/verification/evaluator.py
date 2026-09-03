"""Hidden oracle for ForcedSignalAttribution.

Detection and attribution, reduced to its skeleton. A regional field is observed for T years.
It may contain a forced response - a fixed spatial pattern growing along a known time profile,
scaled by an unknown amplitude beta - on top of internal variability that is red in time and
correlated in space. A climate model supplies two things: a fingerprint (the ensemble mean of a
few forced runs) and, on request, unforced control runs of the same model. Control years are the
budget: they are the only source of information about what internal variability can do to the
detection statistic.

The question is whether the observations carry the forced response, how big beta is, and - before
either - whether the model can be trusted to answer at all.

Three ways to be wrong:

    red noise           the leading modes of internal variability have year-to-year memory, and
                        a 60-year record of red noise contains trends that look forced. A test
                        that assumes white noise, or too few control years, detects a forced
                        response in unforced worlds.
    the fingerprint     projecting onto the model's pattern is only as good as the pattern. When
                        the model's forced pattern is wrong, the regression still returns a
                        number and a confidence interval; the residual, not the fit, says the
                        answer is untrustworthy.
    model variability   when the model's control runs are too quiet, every interval is too
                        narrow and every detection too confident. The residual consistency check
                        - does what is left after the fit look like the model's own variability -
                        is what catches it. Failing that check is a reason to decline, not to
                        publish a tighter interval.

An unforced world with a trustworthy model is *not* the declining case: "no detectable forced
response" is the finding. Declining there is a missed finding; detecting there is a false one.

Scoring keeps the discovery axes separate and normalises so that declining every world earns
exactly zero.
"""
from __future__ import annotations

import math

import numpy as np

DEVELOPMENT_REGIONS = 24
DEVELOPMENT_YEARS = 60
DEVELOPMENT_CONTROL_BUDGET = 600
HELDOUT_REGIONS = 30
HELDOUT_YEARS = 80
HELDOUT_CONTROL_BUDGET = 800
MIN_SEGMENT_YEARS = 20

MODE_COUNT = 4
MODE_STD = (1.0, 0.7, 0.5, 0.35)
MODE_MEMORY = (0.9, 0.7, 0.5, 0.3)
WHITE_STD = 0.3
FORCING_AMPLITUDE = 2.5
FORCED_ENSEMBLE_SIZE = 3
# A misspecified model is either too quiet or points the wrong way.
QUIET_FACTOR = 0.55
PATTERN_ROTATION = 0.5   # cosine between the model's fingerprint pattern and the true one
AMPLITUDE_TOLERANCE = 0.5  # relative error at which the amplitude score reaches zero

WORLD_KINDS = ("forced", "unforced", "quiet_model", "wrong_pattern")


def _time_profile(years):
    t = np.arange(1, years + 1) / years
    return t ** 1.5


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    regions, years = int(spec["regions"]), int(spec["years"])
    basis = np.linalg.qr(rng.normal(size=(regions, regions)))[0]
    modes = basis[:, :MODE_COUNT]
    # The forced pattern projects partly onto the reddest mode of variability, which is what makes
    # a 60-year record of red noise able to imitate it.
    orthogonal = basis[:, MODE_COUNT + 1]
    pattern = 0.75 * modes[:, 0] + 0.66 * orthogonal
    pattern /= np.linalg.norm(pattern)
    if kind == "wrong_pattern":
        other = basis[:, MODE_COUNT + 2]
        model_pattern = PATTERN_ROTATION * pattern + math.sqrt(1 - PATTERN_ROTATION ** 2) * other
        model_pattern /= np.linalg.norm(model_pattern)
    else:
        model_pattern = pattern.copy()
    beta = float(spec.get("beta", 0.0)) if kind != "unforced" else 0.0
    model_scale = QUIET_FACTOR if kind == "quiet_model" else 1.0
    return {
        "kind": kind, "seed": spec["seed"], "regions": regions, "years": years,
        "budget": int(spec["budget"]), "modes": modes, "pattern": pattern,
        "model_pattern": model_pattern, "beta": beta, "model_scale": model_scale,
    }


def _internal(rng, world, years, scale):
    """Red, spatially correlated internal variability: AR(1) mode amplitudes plus white noise."""
    coefficients = np.zeros((years, MODE_COUNT))
    state = np.array([rng.normal(0.0, s) for s in MODE_STD])
    for t in range(years):
        innovations = np.array([rng.normal(0.0, s * math.sqrt(1 - phi ** 2))
                                for s, phi in zip(MODE_STD, MODE_MEMORY)])
        state = np.array(MODE_MEMORY) * state + innovations
        coefficients[t] = state
    field = coefficients @ world["modes"].T + rng.normal(0.0, WHITE_STD, size=(years, world["regions"]))
    return scale * field


def _observations(world):
    rng = np.random.default_rng((world["seed"], 1))
    forced = world["beta"] * FORCING_AMPLITUDE * np.outer(_time_profile(world["years"]), world["pattern"])
    return forced + _internal(rng, world, world["years"], 1.0)


def _fingerprint(world):
    """Ensemble mean of a few forced model runs: the model's pattern along the profile, plus the
    model's own internal variability averaged down by the ensemble size."""
    rng = np.random.default_rng((world["seed"], 2))
    forced = FORCING_AMPLITUDE * np.outer(_time_profile(world["years"]), world["model_pattern"])
    noise = np.mean([_internal(rng, world, world["years"], world["model_scale"])
                     for _ in range(FORCED_ENSEMBLE_SIZE)], axis=0)
    return forced + noise


class _ControlRuns:
    """The candidate's only handle on internal variability: model control years, charged."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.spent = 0
        self.calls = 0
        self.violated = False

    def __call__(self, years):
        if isinstance(years, bool) or not isinstance(years, (int, np.integer)):
            raise ValueError("years must be an integer")
        years = int(years)
        if years < MIN_SEGMENT_YEARS:
            raise ValueError("a control segment must be at least %d years" % MIN_SEGMENT_YEARS)
        if self.spent + years > self.budget:
            self.violated = True
            raise RuntimeError("control budget exhausted")
        self.spent += years
        self.calls += 1
        rng = np.random.default_rng((self.world["seed"], 3, self.calls))
        segment = _internal(rng, self.world, years, self.world["model_scale"])
        return [[float(v) for v in row] for row in segment]


PUBLIC_PROBLEM = {
    "regions": DEVELOPMENT_REGIONS,
    "years": DEVELOPMENT_YEARS,
    "control_budget_years": DEVELOPMENT_CONTROL_BUDGET,
    "min_segment_years": MIN_SEGMENT_YEARS,
    "forced_ensemble_size": FORCED_ENSEMBLE_SIZE,
    "amplitude_tolerance": AMPLITUDE_TOLERANCE,
    "observations": None,
    "fingerprint": None,
    "forcing_time_profile": None,
    "measurement_model": "observations = beta * forced_response + internal variability; the "
                         "fingerprint is the ensemble mean of forced_ensemble_size model runs of "
                         "the forced response, so it carries the model's internal variability "
                         "averaged down by that number",
    "control_model": "run_control(years) returns one unforced model segment of that many years "
                     "over all regions and charges it against control_budget_years",
    "abstain_when": "what remains after removing the fitted forced response is inconsistent with "
                    "the model's own internal variability, so neither the model's fingerprint nor "
                    "its control runs can be trusted to answer",
}


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = bool(submission.get("abstain", False))
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if abstain:
        return None, confidence, True
    if "detected" not in submission:
        raise ValueError("detected is required unless abstaining")
    detected = bool(submission["detected"])
    scaling = float(submission.get("scaling_factor", float("nan")))
    interval = submission.get("interval")
    if not (isinstance(interval, (list, tuple)) and len(interval) == 2):
        raise ValueError("interval must be [low, high]")
    low, high = float(interval[0]), float(interval[1])
    if not (math.isfinite(scaling) and math.isfinite(low) and math.isfinite(high)) or low > high:
        raise ValueError("scaling_factor and interval must be finite with low <= high")
    return {"detected": detected, "scaling": scaling, "low": low, "high": high}, confidence, False


def _metrics(world, claim, abstain):
    blank = {
        "detection_correct": False,
        "amplitude_score": 0.0,
        "interval_covers": False,
        "mechanism_score": 0.0,
        "false_discovery": False,
        "correct_refusal": False,
    }
    kind = world["kind"]
    if kind in ("quiet_model", "wrong_pattern"):
        correct = bool(abstain)
        blank.update({
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": correct,
            "false_discovery": bool(claim and claim["detected"]),
        })
        return blank
    if abstain:
        return blank
    if kind == "unforced":
        correct = not claim["detected"]
        blank.update({
            "detection_correct": correct,
            "mechanism_score": 1.0 if correct else 0.0,
            "false_discovery": not correct,
        })
        return blank
    beta = world["beta"]
    detected = claim["detected"]
    amplitude = float(np.clip(1.0 - abs(claim["scaling"] - beta) / (AMPLITUDE_TOLERANCE * beta), 0.0, 1.0))
    covers = claim["low"] <= beta <= claim["high"]
    blank.update({
        "detection_correct": bool(detected),
        "amplitude_score": amplitude if detected else 0.0,
        "interval_covers": bool(covers),
        "mechanism_score": (amplitude * (1.0 if covers else 0.5)) if detected else 0.0,
    })
    return blank


def _specs(kinds_and_betas, seeds, regions, years, budget):
    out = []
    for (kind, beta), seed in zip(kinds_and_betas, seeds):
        out.append({"kind": kind, "beta": beta, "seed": seed, "regions": regions,
                    "years": years, "budget": budget})
    return tuple(out)


DEVELOPMENT_WORLDS = _specs(
    [("forced", 0.7), ("forced", 0.9), ("forced", 1.1), ("forced", 1.4),
     ("unforced", 0.0), ("unforced", 0.0), ("unforced", 0.0),
     ("quiet_model", 1.0), ("quiet_model", 1.2), ("wrong_pattern", 1.1)],
    [93100301 + i for i in range(10)],
    DEVELOPMENT_REGIONS, DEVELOPMENT_YEARS, DEVELOPMENT_CONTROL_BUDGET,
)

HELDOUT_WORLDS = _specs(
    [("forced", 0.6), ("forced", 1.0), ("forced", 1.3),
     ("unforced", 0.0), ("unforced", 0.0),
     ("quiet_model", 0.9), ("wrong_pattern", 1.0), ("wrong_pattern", 1.3)],
    [94210401 + i for i in range(8)],
    HELDOUT_REGIONS, HELDOUT_YEARS, HELDOUT_CONTROL_BUDGET,
)

ROW_KEYS = ("detection_correct", "amplitude_score", "interval_covers", "mechanism_score",
            "false_discovery", "correct_refusal")


def _evaluate_world(attribute, spec, split, index):
    world = _world(spec)
    controls = _ControlRuns(world)
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "regions": world["regions"], "years": world["years"], "control_budget_years": world["budget"],
        "observations": [[float(v) for v in row] for row in _observations(world)],
        "fingerprint": [[float(v) for v in row] for row in _fingerprint(world)],
        "forcing_time_profile": [float(v) for v in _time_profile(world["years"])],
    })
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "true_scaling_factor": world["beta"], "control_years_used": 0}
    try:
        submission = attribute(problem, controls)
        claim, confidence, abstain = _validate_submission(submission)
        if controls.violated:
            raise RuntimeError("control budget exceeded")
        metrics = _metrics(world, claim, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_detection": bool(claim and claim["detected"]),
            "claimed_scaling_factor": (round(claim["scaling"], 6) if claim else None),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "control_years_used": controls.spent,
        })
        for key in ("amplitude_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_detection": False,
            "claimed_scaling_factor": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "control_years_used": controls.spent,
        })
        return row


def _split_summary(records):
    trustworthy = [r for r in records if r["kind"] in ("forced", "unforced")]
    forced = [r for r in records if r["kind"] == "forced"]
    unforced = [r for r in records if r["kind"] == "unforced"]
    untrustworthy = [r for r in records if r["kind"] not in ("forced", "unforced")]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(untrustworthy) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "detection_rate": float(np.mean([r["detection_correct"] for r in forced])),
        "amplitude_score": float(np.mean([r["amplitude_score"] for r in forced])),
        "interval_coverage": float(np.mean([r["interval_covers"] for r in forced])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unforced + untrustworthy])),
        "unforced_false_detection_rate": float(np.mean([r["false_discovery"] for r in unforced])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in untrustworthy])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in trustworthy])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_control_years": float(np.mean([r["control_years_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(attribute):
    development = [_evaluate_world(attribute, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(attribute, spec, "heldout", index)
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
        "development_detection_rate": dev["detection_rate"],
        "development_amplitude_score": dev["amplitude_score"],
        "development_interval_coverage": dev["interval_coverage"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_unforced_false_detection_rate": dev["unforced_false_detection_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_control_years": dev["mean_control_years"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_detection_rate": held["detection_rate"],
        "heldout_amplitude_score": held["amplitude_score"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
