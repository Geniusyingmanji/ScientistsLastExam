"""Hidden oracle for PhaseDiagramDiscovery.

An isothermal section of a binary system A-B. The candidate has a synthesis budget: each call
prepares one composition and returns its powder diffraction pattern as a list of peaks. From
those patterns it must report the equilibrium phase set - each phase's signature peaks and its
single-phase composition range - or decline, when the evidence does not determine one.

Three ways to be wrong, and none is visible from a single pattern:

    a two-phase field   between two single-phase regions every pattern is a lever-rule
                        superposition of the two neighbours. It has more peaks than either and
                        looks like a new compound; it is not one, and the test is whether the
                        pattern decomposes as a mixture of its neighbours' signatures.
    an impurity         a contaminant appears in about a quarter of syntheses, adding peaks that
                        belong to no equilibrium phase. One pattern cannot distinguish it from a
                        real peak; a replicate can, because the impurity does not reproduce.
    a trapped region    in some systems the middle of the diagram never reaches equilibrium:
                        repeated synthesis at one composition returns different patterns each
                        time. No equilibrium phase set is supported there, and the honest answer
                        is to decline rather than to publish whichever mixture appeared.

What the budget buys is therefore a decision: scan points to find the regions, replicates to
strip impurities and detect a trapped system, and measurements *inside* the two-phase fields -
because the lever rule makes the mixing fraction linear in composition, so two or three points in
a gap locate both of its boundaries by regression far more cheaply than bisection can.

Scoring keeps the discovery axes separate and normalises so that declining every world earns
exactly zero. The phase set is gated: wrong set, zero mechanism, however good the boundaries.
"""
from __future__ import annotations

import math

import numpy as np

# Synthesis calls per world. A uniform grid dense enough to localise every boundary to the
# scoring tolerance would cost about 60; the coarse-scan-then-regress reference spends 24.
SYNTHESIS_BUDGET = 26

TWO_THETA_BOUNDS = (10.0, 90.0)
POSITION_NOISE_SIGMA = 0.08
INTENSITY_NOISE_REL = 0.05
DETECTION_LIMIT = 0.06
# A claimed peak matches a true one within this. Around 4 sigma of position noise.
PEAK_MATCH_TOLERANCE = 0.35
# Boundary error at which the boundary score reaches zero. The lever-rule reference lands near
# 0.01; a 26-point uniform grid cannot do better than about 0.02.
BOUNDARY_TOLERANCE = 0.05
# A claimed phase matches a true one when at least this fraction of the true signature is hit
# and the claim carries at most this many spurious peaks.
SIGNATURE_RECALL_FLOOR = 0.67
SIGNATURE_SPURIOUS_CAP = 2

PEAKS_PER_PHASE = 6
MAX_CLAIMED_PHASES = 6

WORLD_KINDS = ("no_intermediate", "with_intermediate", "two_intermediates", "metastable")


def _draw_phase_regions(rng, n_intermediates):
    """Single-phase intervals: two terminal solid solutions plus 0-2 line compounds."""
    w_a = float(rng.uniform(0.05, 0.12))
    w_b = float(rng.uniform(0.05, 0.12))
    regions = [("alpha", 0.0, w_a)]
    if n_intermediates == 1:
        c = float(rng.uniform(0.38, 0.62))
        w = float(rng.uniform(0.03, 0.06))
        regions.append(("gamma", c - w, c + w))
    elif n_intermediates == 2:
        c1 = float(rng.uniform(0.28, 0.40))
        c2 = float(rng.uniform(0.58, 0.72))
        w1 = float(rng.uniform(0.025, 0.05))
        w2 = float(rng.uniform(0.025, 0.05))
        regions.append(("gamma", c1 - w1, c1 + w1))
        regions.append(("delta", c2 - w2, c2 + w2))
    regions.append(("beta", 1.0 - w_b, 1.0))
    return regions


def _world(spec):
    """Build one hidden system. Every draw is seeded, so the world is a function of the spec."""
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    n_intermediates = {"no_intermediate": 0, "with_intermediate": 1,
                       "two_intermediates": 2, "metastable": 0}[kind]
    regions = _draw_phase_regions(rng, n_intermediates)
    phases = []
    used = []
    for name, lo, hi in regions:
        peaks = []
        while len(peaks) < PEAKS_PER_PHASE:
            pos = float(rng.uniform(*TWO_THETA_BOUNDS))
            # Signatures stay separable: no two peaks of different phases closer than 1.5.
            if all(abs(pos - u) > 1.5 for u in used):
                peaks.append(pos)
                used.append(pos)
        order = np.argsort(peaks)
        phases.append({
            "name": name, "lo": lo, "hi": hi,
            "peaks": [peaks[i] for i in order],
            "intensities": [float(v) for v in rng.uniform(0.35, 1.0, size=PEAKS_PER_PHASE)],
        })
    world = {
        "kind": kind, "seed": spec["seed"], "phases": phases,
        "impurity_peaks": sorted(float(rng.uniform(*TWO_THETA_BOUNDS)) for _ in range(3)),
        "impurity_rate": 0.25,
    }
    if kind == "metastable":
        # The trapped region spans everything between the terminals. Its patterns are built per
        # call: random fractions of the terminals plus a handful of transient peaks that never
        # reproduce. Nothing about it is an equilibrium phase.
        world["trapped"] = (phases[0]["hi"], phases[-1]["lo"])
    return world


def _pattern(world, x, call_index):
    """One synthesis and its diffraction pattern. Deterministic in (world, x, call_index)."""
    rng = np.random.default_rng((world["seed"], call_index))
    phases = world["phases"]
    components = []
    trapped = world.get("trapped")
    if trapped and trapped[0] < x < trapped[1]:
        # Kinetically trapped: whichever mixture happened to freeze in, plus transient peaks.
        f = float(rng.uniform(0.15, 0.85))
        components = [(phases[0], 1.0 - f), (phases[-1], f)]
        transient = [(float(rng.uniform(*TWO_THETA_BOUNDS)), float(rng.uniform(0.2, 0.6)))
                     for _ in range(int(rng.integers(3, 6)))]
    else:
        transient = []
        for index, phase in enumerate(phases):
            if phase["lo"] - 1e-12 <= x <= phase["hi"] + 1e-12:
                components = [(phase, 1.0)]
                break
        if not components:
            for index in range(len(phases) - 1):
                left, right = phases[index], phases[index + 1]
                if left["hi"] < x < right["lo"]:
                    f = (x - left["hi"]) / (right["lo"] - left["hi"])
                    components = [(left, 1.0 - f), (right, f)]
                    break
    peaks = []
    for phase, fraction in components:
        for pos, inten in zip(phase["peaks"], phase["intensities"]):
            value = fraction * inten * (1.0 + float(rng.normal(0.0, INTENSITY_NOISE_REL)))
            if value > DETECTION_LIMIT:
                peaks.append((pos + float(rng.normal(0.0, POSITION_NOISE_SIGMA)), value))
    for pos, inten in transient:
        peaks.append((pos + float(rng.normal(0.0, POSITION_NOISE_SIGMA)), inten))
    if float(rng.uniform()) < world["impurity_rate"]:
        for pos in world["impurity_peaks"]:
            peaks.append((pos + float(rng.normal(0.0, POSITION_NOISE_SIGMA)),
                          float(rng.uniform(0.08, 0.2))))
    peaks.sort()
    return [{"two_theta": round(p, 4), "intensity": round(v, 5)} for p, v in peaks]


class _Synthesizer:
    """The candidate's only view of the system: one synthesized sample per call.

    Calls are seeded by the call index, so repeating a composition re-draws the noise, the
    impurity and - in a trapped system - the frozen-in mixture. That is what makes replication
    informative, and it costs budget, which is the trade the task is about.
    """

    def __init__(self, world, budget):
        self.world = world
        self.budget = int(budget)
        self.calls = 0
        self.violated = False

    def __call__(self, composition):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("synthesis budget exhausted")
        x = float(composition)
        if not math.isfinite(x) or not 0.0 <= x <= 1.0:
            raise ValueError("composition must be finite and within [0, 1]")
        self.calls += 1
        return _pattern(self.world, x, self.calls)


PUBLIC_PROBLEM = {
    "synthesis_budget_calls": SYNTHESIS_BUDGET,
    "composition_bounds": [0.0, 1.0],
    "two_theta_bounds": [10.0, 90.0],
    "position_noise_sigma": POSITION_NOISE_SIGMA,
    "intensity_noise_relative": INTENSITY_NOISE_REL,
    "detection_limit": DETECTION_LIMIT,
    "max_claimed_phases": MAX_CLAIMED_PHASES,
    "measurement_model": "each call synthesizes one composition and returns its powder pattern "
                         "as peaks; two-phase fields return lever-rule superpositions of their "
                         "neighbours",
    "impurity_model": "a contaminant appears in a minority of syntheses, adding a few weak "
                      "peaks that belong to no equilibrium phase and do not reproduce",
    "abstain_when": "repeated synthesis at a composition keeps returning different patterns, so "
                    "no equilibrium phase set is supported",
}


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
        return [], confidence, True
    claimed = submission.get("phases")
    if not isinstance(claimed, list) or not claimed:
        raise ValueError("phases must be a non-empty list, or abstain")
    if len(claimed) > MAX_CLAIMED_PHASES:
        raise ValueError("at most %d phases may be claimed" % MAX_CLAIMED_PHASES)
    parsed = []
    for row in claimed:
        if not isinstance(row, dict):
            raise ValueError("each phase must be a mapping")
        rng_ = row.get("composition_range")
        if not (isinstance(rng_, (list, tuple)) and len(rng_) == 2):
            raise ValueError("composition_range must be [lo, hi]")
        lo, hi = float(rng_[0]), float(rng_[1])
        if not (math.isfinite(lo) and math.isfinite(hi)) or not 0.0 <= lo < hi <= 1.0:
            raise ValueError("composition_range must satisfy 0 <= lo < hi <= 1")
        peaks = row.get("peak_two_thetas")
        if not isinstance(peaks, (list, tuple)) or not 1 <= len(peaks) <= 12:
            raise ValueError("peak_two_thetas must list 1-12 positions")
        peaks = [float(p) for p in peaks]
        if not all(math.isfinite(p) and TWO_THETA_BOUNDS[0] <= p <= TWO_THETA_BOUNDS[1]
                   for p in peaks):
            raise ValueError("peak positions must be finite and inside two_theta_bounds")
        parsed.append({"lo": lo, "hi": hi, "peaks": sorted(peaks)})
    parsed.sort(key=lambda p: p["lo"])
    for left, right in zip(parsed, parsed[1:]):
        if left["hi"] > right["lo"] + 1e-9:
            raise ValueError("single-phase composition ranges must not overlap")
    return parsed, confidence, False


def _signature_match(claim_peaks, true_phase):
    """Whether a claimed peak list names this phase: most of the signature hit, little junk."""
    hits = 0
    for pos in true_phase["peaks"]:
        if any(abs(pos - c) <= PEAK_MATCH_TOLERANCE for c in claim_peaks):
            hits += 1
    spurious = sum(1 for c in claim_peaks
                   if not any(abs(c - pos) <= PEAK_MATCH_TOLERANCE
                              for pos in true_phase["peaks"]))
    recall = hits / len(true_phase["peaks"])
    return recall >= SIGNATURE_RECALL_FLOOR and spurious <= SIGNATURE_SPURIOUS_CAP


def _boundary_score(claimed, matched_truth):
    """How well the matched phases' interior boundaries are placed. The terminal endpoints 0 and
    1 are not boundaries anyone had to find, so they are excluded."""
    errors = []
    for claim, truth in matched_truth:
        if truth["lo"] > 0.0:
            errors.append(abs(claim["lo"] - truth["lo"]))
        if truth["hi"] < 1.0:
            errors.append(abs(claim["hi"] - truth["hi"]))
    if not errors:
        return 0.0
    return float(np.mean([np.clip(1.0 - err / BOUNDARY_TOLERANCE, 0.0, 1.0)
                          for err in errors]))


def _metrics(world, claimed, abstain):
    """The discovery axes for one world.

    The phase set is gated exactly: a missing phase, an extra one, or a double claim scores zero
    mechanism however well the boundaries sit, because "which phases exist" is the discovery and
    the boundaries are its parameters.
    """
    blank = {
        "phase_set_correct": False,
        "boundary_score": 0.0,
        "mechanism_score": 0.0,
        "claimed_false_phase": False,
        "correct_refusal": False,
        "false_discovery": False,
    }
    if world["kind"] == "metastable":
        correct = bool(abstain)
        blank.update({
            "boundary_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "claimed_false_phase": not correct,
            "correct_refusal": correct,
            "false_discovery": not correct,
        })
        return blank
    if abstain or not claimed:
        return blank
    truths = world["phases"]
    matched = []
    used = set()
    for claim in claimed:
        found = None
        for index, truth in enumerate(truths):
            if index not in used and _signature_match(claim["peaks"], truth):
                found = index
                break
        if found is None:
            matched.append((claim, None))
        else:
            used.add(found)
            matched.append((claim, truths[found]))
    unmatched_claims = [claim for claim, truth in matched if truth is None]
    pairs = [(claim, truth) for claim, truth in matched if truth is not None]
    set_correct = not unmatched_claims and len(pairs) == len(truths)
    boundary = _boundary_score(claimed, pairs) if pairs else 0.0
    blank.update({
        "phase_set_correct": bool(set_correct),
        "boundary_score": boundary,
        "mechanism_score": boundary if set_correct else 0.0,
        "claimed_false_phase": bool(unmatched_claims),
        "correct_refusal": False,
        "false_discovery": False,
    })
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "no_intermediate", "seed": 61100301},
    {"kind": "no_intermediate", "seed": 61100302},
    {"kind": "with_intermediate", "seed": 61100303},
    {"kind": "with_intermediate", "seed": 61100304},
    {"kind": "with_intermediate", "seed": 61100305},
    {"kind": "two_intermediates", "seed": 61100306},
    {"kind": "two_intermediates", "seed": 61100307},
    {"kind": "metastable", "seed": 61100308},
    {"kind": "metastable", "seed": 61100309},
)

HELDOUT_WORLDS = (
    {"kind": "no_intermediate", "seed": 77210401},
    {"kind": "with_intermediate", "seed": 77210402},
    {"kind": "with_intermediate", "seed": 77210403},
    {"kind": "two_intermediates", "seed": 77210404},
    {"kind": "two_intermediates", "seed": 77210405},
    {"kind": "metastable", "seed": 77210406},
    {"kind": "metastable", "seed": 77210407},
    {"kind": "no_intermediate", "seed": 77210408},
)

ROW_KEYS = (
    "phase_set_correct", "boundary_score", "mechanism_score", "claimed_false_phase",
    "correct_refusal", "false_discovery",
)


def _evaluate_world(discover_phases, spec, split, index):
    world = _world(spec)
    synthesizer = _Synthesizer(world, SYNTHESIS_BUDGET)
    problem = dict(PUBLIC_PROBLEM)
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "synthesis_calls": 0}
    try:
        submission = discover_phases(problem, synthesizer)
        claimed, confidence, abstain = _validate_submission(submission)
        if synthesizer.violated:
            raise RuntimeError("synthesis budget exceeded")
        metrics = _metrics(world, claimed, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_phase_count": len(claimed),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "synthesis_calls": synthesizer.calls,
        })
        for key in ("boundary_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        # Every key the aggregation reads, so a failed world cannot raise a KeyError inside the
        # summary and be reported as an infrastructure failure.
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_phase_count": 0,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "synthesis_calls": synthesizer.calls,
        })
        return row


def _split_summary(records):
    """Aggregate one split. The discovery axes stay separate; coverage is a column, not an axis."""
    determinable = [r for r in records if r["kind"] != "metastable"]
    trapped = [r for r in records if r["kind"] == "metastable"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    # What declining everything earns: right on every trapped world, wrong on every other.
    # Subtracting it makes blanket abstention worth exactly zero.
    always_abstain = len(trapped) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "phase_set_rate": float(np.mean([r["phase_set_correct"] for r in determinable])),
        "boundary_score": float(np.mean([r["boundary_score"] for r in determinable])),
        "false_phase_rate": float(np.mean([r["claimed_false_phase"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in trapped])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in trapped])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(
            np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_synthesis_calls": float(np.mean([r["synthesis_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(discover_phases):
    development = [
        _evaluate_world(discover_phases, spec, "development", index)
        for index, spec in enumerate(DEVELOPMENT_WORLDS)
    ]
    heldout = [
        _evaluate_world(discover_phases, spec, "heldout", index)
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
        "development_phase_set_rate": dev["phase_set_rate"],
        "development_boundary_score": dev["boundary_score"],
        "development_false_phase_rate": dev["false_phase_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_synthesis_calls": dev["mean_synthesis_calls"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_phase_set_rate": held["phase_set_rate"],
        "heldout_boundary_score": held["boundary_score"],
        "heldout_false_phase_rate": held["false_phase_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
