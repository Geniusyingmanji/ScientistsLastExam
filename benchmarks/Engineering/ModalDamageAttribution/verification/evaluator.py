"""Hidden oracle for ModalDamageAttribution.

Structural health monitoring, reduced to the confound that defines the field. A structure is a
chain of `MASS_COUNT` masses joined by springs: two to ground at the ends and the rest between
neighbours. Its modal frequencies are the square roots of the eigenvalues of the stiffness matrix
against the mass matrix. Three things move those frequencies:

    temperature       every spring stiffens or softens together, so every eigenvalue is scaled by
                      one factor. The commissioning campaign measured the healthy structure only
                      between 5 and 25 degrees, and the true law has a knee at freezing, so a
                      healthy structure measured on a cold day looks damaged to anyone comparing
                      absolute frequencies against an extrapolated baseline.
    local damage      one internal spring loses stiffness. The shift of mode k is proportional to
                      that spring's share of mode k's strain energy, which differs between modes -
                      so damage changes the *ratios* between frequencies, and temperature does not.
    a support change  a ground spring changes instead. It is a real and common cause of a modal
                      shift, and it is outside the declared damage family: no single internal
                      element reproduces its ratio pattern. The honest answer is to decline.

The candidate buys measurements from a public calendar of days. Each day publishes its
temperature and an excitation quality, and the noise on that day's frequencies scales as
1/sqrt(excitation). A healthy structure is *not* the declining case: "no damage" is the finding.

Scoring keeps the discovery axes separate and normalises so that declining every structure earns
exactly zero.
"""
from __future__ import annotations

import math

import numpy as np

MASS_COUNT = 8
MODE_COUNT = 5
DEVELOPMENT_BUDGET = 9
HELDOUT_BUDGET = 9
CALENDAR_DAYS = 120

NOMINAL_STIFFNESS = 1.0
GROUND_STIFFNESS = 1.35
MASS_SPREAD = 0.06
# A real structure is not uniform, and a uniform chain would be mirror-symmetric: element j and
# element mass_count-j would shift the modes identically and no measurement could tell them apart.
# The spread is drawn per structure and published with the model, exactly as a validated finite
# element model would be.
STIFFNESS_SPREAD = 0.18
# The published model is a validated model, not the structure. Real finite element models carry a
# few per cent of error against the thing they describe, and that error is the reason the
# commissioning campaign exists: it measured the structure, so the healthy ratios it records are
# the truth the model only approximates. A candidate that takes the model's own healthy ratios as
# its reference point inherits this error as a permanent apparent shift.
MODEL_ERROR = 0.03
# Relative noise on each frequency at excitation quality 1.0. Chosen against the smallest
# damage signal the worlds contain: one day leaves the ratio shift barely above the noise,
# nine days do not, and a low-excitation day is three times worse than a high one. That is
# what makes the day choice and the budget decisions rather than formalities.
BASE_NOISE = 0.0060
DAMAGE_RANGE = (0.12, 0.40)
# A bearing loses restraint rather than gaining it, so the support worlds soften a ground spring.
# The multiplier range is chosen so their ratio signal overlaps the damage range: separating the
# two on the size of the shift will get it wrong, and the pattern has to be read instead.
SUPPORT_MULTIPLIER_RANGE = (0.45, 0.78)
# A support change that moves the ratio pattern by less than this is not evidence of
# anything: it sits inside the measurement noise, and refusing it could not be earned.
# The generator redraws until the change is visible, so every refusal world is decidable.
SUPPORT_MIN_RATIO_SIGNAL = 0.012
SEVERITY_TOLERANCE = 0.12           # absolute error at which the severity score reaches zero

# Commissioning campaign: the healthy structure, measured only in this temperature band.
BASELINE_TEMPERATURES = (5.0, 9.0, 13.0, 17.0, 21.0, 25.0)
BASELINE_REPEATS = 4
# Bilinear stiffness-temperature law with a knee at freezing. Above the knee the baseline band
# sees a gentle slope; below it the structure stiffens far faster, and nothing in the
# commissioning data says so.
IN_BAND_SLOPE = -0.0011
COLD_EXTRA_SLOPE = -0.0090
HOT_EXTRA_SLOPE = -0.0035
COLD_KNEE = 0.0
HOT_KNEE = 28.0
REFERENCE_TEMPERATURE = 15.0

WORLD_KINDS = ("healthy", "damaged", "support_change")


def _temperature_factor(celsius):
    """Stiffness against temperature: gentle inside the commissioning band, and steeper outside it
    at both ends. Nothing in the commissioning data reveals either knee, so any law fitted to that
    data and extrapolated is wrong in both directions - and the ratios do not care."""
    factor = 1.0 + IN_BAND_SLOPE * (celsius - REFERENCE_TEMPERATURE)
    if celsius < COLD_KNEE:
        factor += COLD_EXTRA_SLOPE * (celsius - COLD_KNEE)
    if celsius > HOT_KNEE:
        factor += HOT_EXTRA_SLOPE * (celsius - HOT_KNEE)
    return factor


def _springs(world, celsius):
    springs = np.array(world["springs"], dtype=float) * _temperature_factor(celsius)
    return springs


def _frequencies(world, celsius):
    """Undamped natural frequencies of the chain, in hertz, exact for the given springs."""
    springs = _springs(world, celsius)
    masses = world["masses"]
    n = masses.shape[0]
    stiffness = np.zeros((n, n))
    for i in range(n):
        stiffness[i, i] = springs[i] + springs[i + 1]
        if i + 1 < n:
            stiffness[i, i + 1] = -springs[i + 1]
            stiffness[i + 1, i] = -springs[i + 1]
    root_inverse = np.diag(1.0 / np.sqrt(masses))
    values = np.linalg.eigvalsh(root_inverse @ stiffness @ root_inverse)
    values = np.clip(values, 1e-12, None)
    return np.sqrt(values)[:MODE_COUNT] / (2.0 * math.pi)


def _calendar(seed):
    """A year of measurement opportunities.

    Excitation quality is drawn independently of temperature. An earlier version tied the two
    together, and it handed the task away: the best-signal days were the warm days, where a
    linear extrapolation of the commissioning law happens to be right, so a threshold rule on
    absolute frequencies scored 0.55 against a reference of 0.65 without ever using the ratios.
    With the two independent there is no day that is both quiet-proof and confound-proof, and the
    only way out of the temperature is the one that removes it exactly.
    """
    rng = np.random.default_rng((seed, 17))
    day = np.arange(CALENDAR_DAYS)
    seasonal = 15.0 - 21.0 * np.cos(2.0 * np.pi * (day + 20) / CALENDAR_DAYS)
    temperature = seasonal + rng.normal(0.0, 2.5, size=CALENDAR_DAYS)
    excitation = np.clip(rng.uniform(0.12, 1.0, size=CALENDAR_DAYS), 0.12, 1.0)
    return [{"day": int(d), "temperature_celsius": round(float(t), 2),
             "excitation_quality": round(float(e), 3)}
            for d, t, e in zip(day, temperature, excitation)]


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    masses = 1.0 + rng.uniform(-MASS_SPREAD, MASS_SPREAD, size=MASS_COUNT)
    springs = NOMINAL_STIFFNESS * (
        1.0 + rng.uniform(-STIFFNESS_SPREAD, STIFFNESS_SPREAD, size=MASS_COUNT + 1))
    springs[0] = GROUND_STIFFNESS * (1.0 + float(rng.uniform(-STIFFNESS_SPREAD, STIFFNESS_SPREAD)))
    springs[-1] = GROUND_STIFFNESS * (1.0 + float(rng.uniform(-STIFFNESS_SPREAD, STIFFNESS_SPREAD)))
    healthy = {"masses": masses, "springs": springs.copy()}
    published = {
        "masses": masses * (1.0 + rng.uniform(-MODEL_ERROR, MODEL_ERROR, size=MASS_COUNT)),
        "springs": springs * (1.0 + rng.uniform(-MODEL_ERROR, MODEL_ERROR, size=MASS_COUNT + 1)),
    }
    element, severity = None, 0.0
    if kind == "damaged":
        element = int(spec["element"])
        severity = float(rng.uniform(*DAMAGE_RANGE))
        springs[element] *= 1.0 - severity
    elif kind == "support_change":
        index = 0 if int(spec.get("end", 0)) == 0 else MASS_COUNT
        healthy_frequencies = _frequencies(healthy, REFERENCE_TEMPERATURE)
        healthy_ratios = healthy_frequencies / healthy_frequencies[0]
        multiplier = float(rng.uniform(*SUPPORT_MULTIPLIER_RANGE))
        for attempt in range(60):
            trial = healthy["springs"].copy()
            trial[index] *= multiplier * (0.94 ** attempt)
            frequencies = _frequencies({"masses": masses, "springs": trial}, REFERENCE_TEMPERATURE)
            ratios = frequencies / frequencies[0]
            if float(np.max(np.abs(ratios / healthy_ratios - 1.0))) >= SUPPORT_MIN_RATIO_SIGNAL:
                springs = trial
                break
        else:
            raise RuntimeError("could not draw a visible support change")
    return {"kind": kind, "seed": spec["seed"], "masses": masses, "springs": springs,
            "healthy": healthy, "published": published, "element": element, "severity": severity,
            "calendar": _calendar(spec["seed"]), "budget": int(spec["budget"])}


def _baseline_table(world):
    """Commissioning data: the healthy structure, several repeats per temperature, at the highest
    excitation the site ever sees. Free, and the only picture of the healthy structure there is."""
    rng = np.random.default_rng((world["seed"], 5))
    rows = []
    for celsius in BASELINE_TEMPERATURES:
        clean = _frequencies(world["healthy"], celsius)
        for _ in range(BASELINE_REPEATS):
            noise = rng.normal(0.0, BASE_NOISE, size=MODE_COUNT)
            rows.append({"temperature_celsius": celsius,
                         "frequencies_hz": [round(float(f * (1.0 + n)), 6)
                                            for f, n in zip(clean, noise)]})
    return rows


class _Campaign:
    """The candidate's only view of the structure as it is now: one day of measurements per call."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.calls = 0
        self.violated = False

    def __call__(self, day):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("measurement budget exhausted")
        if isinstance(day, bool) or not isinstance(day, (int, np.integer)):
            raise ValueError("day must be an integer index into the calendar")
        day = int(day)
        if not 0 <= day < CALENDAR_DAYS:
            raise ValueError("day must lie in 0..%d" % (CALENDAR_DAYS - 1))
        self.calls += 1
        entry = self.world["calendar"][day]
        clean = _frequencies(self.world, entry["temperature_celsius"])
        rng = np.random.default_rng((self.world["seed"], 9, day, self.calls))
        sigma = BASE_NOISE / math.sqrt(entry["excitation_quality"])
        noisy = clean * (1.0 + rng.normal(0.0, sigma, size=MODE_COUNT))
        return {"day": day, "temperature_celsius": entry["temperature_celsius"],
                "excitation_quality": entry["excitation_quality"],
                "frequencies_hz": [float(v) for v in noisy]}


PUBLIC_PROBLEM = {
    "mass_count": MASS_COUNT,
    "mode_count": MODE_COUNT,
    "measurement_budget_days": DEVELOPMENT_BUDGET,
    "damage_element_range": [1, MASS_COUNT - 1],
    "damage_severity_range": list(DAMAGE_RANGE),
    "severity_tolerance": SEVERITY_TOLERANCE,
    "base_relative_noise": BASE_NOISE,
    "baseline_temperature_range": [min(BASELINE_TEMPERATURES), max(BASELINE_TEMPERATURES)],
    "calendar": None,
    "commissioning_baseline": None,
    "nominal_masses": None,
    "nominal_springs": None,
    "model_error_scale": MODEL_ERROR,
    "structure_model": "a chain of mass_count masses joined by mass_count+1 springs, the first "
                       "and last of them to ground; nominal_masses and nominal_springs are the "
                       "validated healthy model at the reference temperature - validated, not "
                       "exact: each entry carries up to model_error_scale of relative error "
                       "against the structure the commissioning campaign measured - and the modal "
                       "frequencies are the square roots of the eigenvalues of the stiffness "
                       "matrix against the mass matrix, divided by two pi",
    "damage_model": "exactly one internal spring, indexed 1..mass_count-1, loses a fraction of its "
                    "stiffness; the ground springs are not part of the damage family",
    "temperature_model": "temperature scales every spring by one common factor, so it multiplies "
                         "every eigenvalue equally; the commissioning campaign measured only "
                         "inside baseline_temperature_range and the law is not linear outside it, "
                         "at either end",
    "measurement_model": "measure(day) returns that day's modal frequencies with relative noise "
                         "base_relative_noise / sqrt(excitation_quality)",
    "abstain_when": "the modal evidence is inconsistent with every single-element damage in the "
                    "declared family, because a support condition changed instead",
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
    if "damaged" not in submission:
        raise ValueError("damaged is required unless abstaining")
    damaged = bool(submission["damaged"])
    if not damaged:
        return {"damaged": False}, confidence, False
    element = submission.get("element")
    if isinstance(element, bool) or not isinstance(element, (int, np.integer)):
        raise ValueError("element must be an integer when damage is claimed")
    element = int(element)
    if not 1 <= element <= MASS_COUNT - 1:
        raise ValueError("element must lie in 1..%d" % (MASS_COUNT - 1,))
    severity = float(submission.get("severity", float("nan")))
    if not math.isfinite(severity) or not 0.0 < severity < 1.0:
        raise ValueError("severity must be a finite fraction in (0, 1)")
    return {"damaged": True, "element": element, "severity": severity}, confidence, False


def _metrics(world, claim, abstain):
    blank = {"decision_correct": False, "element_correct": False, "severity_score": 0.0,
             "mechanism_score": 0.0, "false_discovery": False, "correct_refusal": False}
    kind = world["kind"]
    if kind == "support_change":
        correct = bool(abstain)
        blank.update({"mechanism_score": 1.0 if correct else 0.0, "correct_refusal": correct,
                      "false_discovery": bool(claim and claim["damaged"])})
        return blank
    if abstain:
        return blank
    if kind == "healthy":
        correct = not claim["damaged"]
        blank.update({"decision_correct": correct, "mechanism_score": 1.0 if correct else 0.0,
                      "false_discovery": not correct})
        return blank
    if not claim["damaged"]:
        return blank
    element_correct = claim["element"] == world["element"]
    severity = float(np.clip(
        1.0 - abs(claim["severity"] - world["severity"]) / SEVERITY_TOLERANCE, 0.0, 1.0))
    blank.update({
        "decision_correct": True,
        "element_correct": element_correct,
        "severity_score": severity if element_correct else 0.0,
        # Naming the wrong element is a false discovery, not a partial credit: it sends a crew to
        # the wrong span.
        "mechanism_score": (0.5 + 0.5 * severity) if element_correct else 0.0,
        "false_discovery": not element_correct,
    })
    return blank


# Six damaged structures against two healthy and two with a changed support. The proportions are
# a design decision, not a default: an earlier split of four, three and three made blanket refusal
# above a shift threshold profitable - it bought three worlds and lost three - and a probe of
# low-dimensional strategies scored 0.55 that way without localising anything. Damage has to be
# the common case for localisation to be where the score lives.
DEVELOPMENT_WORLDS = (
    {"kind": "damaged", "element": 1, "seed": 41100301, "budget": DEVELOPMENT_BUDGET},
    {"kind": "damaged", "element": 2, "seed": 41100302, "budget": DEVELOPMENT_BUDGET},
    {"kind": "damaged", "element": 3, "seed": 41100303, "budget": DEVELOPMENT_BUDGET},
    {"kind": "damaged", "element": 4, "seed": 41100304, "budget": DEVELOPMENT_BUDGET},
    {"kind": "damaged", "element": 6, "seed": 41100305, "budget": DEVELOPMENT_BUDGET},
    {"kind": "damaged", "element": 7, "seed": 41100306, "budget": DEVELOPMENT_BUDGET},
    {"kind": "healthy", "seed": 41100307, "budget": DEVELOPMENT_BUDGET},
    {"kind": "healthy", "seed": 41100308, "budget": DEVELOPMENT_BUDGET},
    {"kind": "support_change", "end": 0, "seed": 41100309, "budget": DEVELOPMENT_BUDGET},
    {"kind": "support_change", "end": 1, "seed": 41100310, "budget": DEVELOPMENT_BUDGET},
)

HELDOUT_WORLDS = (
    {"kind": "damaged", "element": 2, "seed": 52210401, "budget": HELDOUT_BUDGET},
    {"kind": "damaged", "element": 3, "seed": 52210402, "budget": HELDOUT_BUDGET},
    {"kind": "damaged", "element": 5, "seed": 52210403, "budget": HELDOUT_BUDGET},
    {"kind": "damaged", "element": 6, "seed": 52210404, "budget": HELDOUT_BUDGET},
    {"kind": "damaged", "element": 7, "seed": 52210405, "budget": HELDOUT_BUDGET},
    {"kind": "healthy", "seed": 52210406, "budget": HELDOUT_BUDGET},
    {"kind": "healthy", "seed": 52210407, "budget": HELDOUT_BUDGET},
    {"kind": "support_change", "end": 0, "seed": 52210408, "budget": HELDOUT_BUDGET},
    {"kind": "support_change", "end": 1, "seed": 52210409, "budget": HELDOUT_BUDGET},
)

ROW_KEYS = ("decision_correct", "element_correct", "severity_score", "mechanism_score",
            "false_discovery", "correct_refusal")


def _evaluate_world(attribute_damage, spec, split, index):
    world = _world(spec)
    campaign = _Campaign(world)
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "measurement_budget_days": world["budget"],
        "calendar": [dict(entry) for entry in world["calendar"]],
        "commissioning_baseline": _baseline_table(world),
        "nominal_masses": [float(v) for v in world["published"]["masses"]],
        "nominal_springs": [float(v) for v in world["published"]["springs"]],
    })
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "true_element": world["element"], "true_severity": round(world["severity"], 6),
            "days_measured": 0}
    try:
        submission = attribute_damage(problem, campaign)
        claim, confidence, abstain = _validate_submission(submission)
        if campaign.violated:
            raise RuntimeError("measurement budget exceeded")
        metrics = _metrics(world, claim, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_damage": bool(claim and claim["damaged"]),
            "claimed_element": (claim or {}).get("element"),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "days_measured": campaign.calls,
        })
        for key in ("severity_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_damage": False,
            "claimed_element": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "days_measured": campaign.calls,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] != "support_change"]
    damaged = [r for r in records if r["kind"] == "damaged"]
    healthy = [r for r in records if r["kind"] == "healthy"]
    unsupported = [r for r in records if r["kind"] == "support_change"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "localisation_rate": float(np.mean([r["element_correct"] for r in damaged])),
        "severity_score": float(np.mean([r["severity_score"] for r in damaged])),
        "healthy_false_alarm_rate": float(np.mean([r["false_discovery"] for r in healthy])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in records])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_days_measured": float(np.mean([r["days_measured"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(attribute_damage):
    development = [_evaluate_world(attribute_damage, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(attribute_damage, spec, "heldout", index)
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
        "development_localisation_rate": dev["localisation_rate"],
        "development_severity_score": dev["severity_score"],
        "development_healthy_false_alarm_rate": dev["healthy_false_alarm_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_days_measured": dev["mean_days_measured"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_localisation_rate": held["localisation_rate"],
        "heldout_healthy_false_alarm_rate": held["healthy_false_alarm_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
