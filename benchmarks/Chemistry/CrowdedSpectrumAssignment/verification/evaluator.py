"""Hidden oracle for CrowdedSpectrumAssignment.

A mixture of library species is measured as one 1-D vibrational spectrum. At the instrument's
default resolution, lines closer than about two Gaussian widths merge into a single peak, so a
two-species blend of a close pair is indistinguishable from a third library species whose lines
sit at the merge centres. A charged zoom narrows the instrument function inside a window and
splits the blend; without it the honest answer on an alias world is not a guess.

Three ways to be wrong, none visible from the default scan alone:

    an alias          four blended peaks match both {gamma, delta} and {epsilon}. Zooming each
                      peak splits a true blend into a doublet and leaves a true singlet alone.
    a contaminant     extra lines belong to no library species. Publishing the nearest library
                      names is a false discovery; the honest answer is to decline.
    a blank           noise only. Any claimed species is a false discovery.

The library is public. The skill is combinatorial assignment under blending, and knowing when
the default scan does not determine a unique subset. NMRSpectrumFitting recovers continuous
Voigt parameters of unknown peaks; this task names species from a closed library. PhaseDiagram
asks which phases exist on a composition axis; this asks which species exist in a spectrum.

Scoring keeps the discovery axes separate and normalises so that declining every world earns
exactly zero. The species set is gated: wrong set, zero mechanism, however good the fractions.
"""
from __future__ import annotations

import math

import numpy as np

ZOOM_BUDGET = 8
DEFAULT_SIGMA = 12.0
ZOOM_SIGMA = 2.5
WN_BOUNDS = (400.0, 4000.0)
GRID_N = 720
DETECTION_FLOOR = 0.09
NOISE_SIGMA = 0.018
MAX_CLAIMED = 4
MIN_ZOOM_WIDTH = 30.0
MAX_ZOOM_WIDTH = 250.0
FRACTION_TOLERANCE = 0.25

# Hand-placed so that (gamma, delta) is an 8 cm-1 pair at every line, and epsilon sits on the
# merge centres. Other species are isolated at default resolution.
LIBRARY = {
    "alpha": [520.0, 1100.0, 1710.0, 2880.0],
    "beta": [640.0, 1240.0, 1850.0, 3010.0],
    "gamma": [800.0, 1420.0, 2100.0, 3200.0],
    "delta": [808.0, 1428.0, 2108.0, 3208.0],
    "epsilon": [804.0, 1424.0, 2104.0, 3204.0],
    "zeta": [960.0, 1960.0, 2580.0, 3720.0],
    "eta": [1080.0, 2040.0, 2760.0, 3880.0],
}

WORLD_KINDS = ("simple", "crowded", "alias", "contaminant", "blank")


def _components(kind, rng, variant=None):
    if kind == "simple":
        pair = [["alpha", "beta"], ["zeta", "eta"], ["alpha", "zeta"]][int(rng.integers(0, 3))]
        f = float(rng.uniform(0.35, 0.65))
        return [(pair[0], f), (pair[1], 1.0 - f)], []
    if kind == "crowded":
        f1 = float(rng.uniform(0.28, 0.40))
        f2 = float(rng.uniform(0.28, 0.40))
        f3 = 1.0 - f1 - f2
        return [("alpha", f1), ("zeta", f2), ("eta", f3)], []
    if kind == "alias":
        if variant == "epsilon":
            return [("epsilon", 1.0)], []
        f = float(rng.uniform(0.40, 0.60))
        return [("gamma", f), ("delta", 1.0 - f)], []
    if kind == "contaminant":
        extra = sorted(float(rng.uniform(1300.0, 2500.0)) for _ in range(3))
        # Keep extras off the library by at least 40 cm-1.
        used = [w for lines in LIBRARY.values() for w in lines]
        cleaned = []
        for pos in extra:
            if all(abs(pos - u) > 40.0 for u in used + cleaned):
                cleaned.append(pos)
        while len(cleaned) < 3:
            pos = float(rng.uniform(1300.0, 2500.0))
            if all(abs(pos - u) > 40.0 for u in used + cleaned):
                cleaned.append(pos)
        f = float(rng.uniform(0.4, 0.6))
        return [("alpha", f), ("beta", 1.0 - f)], [(p, 0.55) for p in cleaned]
    if kind == "blank":
        return [], []
    raise ValueError("unknown world kind: %r" % (kind,))


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    components, extra = _components(kind, rng, spec.get("variant"))
    return {
        "kind": kind, "seed": spec["seed"],
        "observation_seed": spec.get("observation_seed", spec["seed"]),
        "components": components, "extra_lines": extra,
    }


def _intensity(world, sigma, wn):
    y = np.zeros_like(wn)
    # The alias pair is deliberately identical at default resolution. This makes experiment
    # design, rather than a frozen amplitude artefact, the only route to identifying the truth.
    components = world["components"]
    if world["kind"] == "alias" and sigma == DEFAULT_SIGMA:
        components = [("epsilon", 1.0)]
    for name, fraction in components:
        for pos in LIBRARY[name]:
            y += fraction * np.exp(-0.5 * ((wn - pos) / sigma) ** 2)
    for pos, inten in world.get("extra_lines") or []:
        y += inten * np.exp(-0.5 * ((wn - pos) / sigma) ** 2)
    return y


def _peaks(wn, y, rng):
    noisy = np.clip(y + rng.normal(0.0, NOISE_SIGMA, size=y.shape), 0.0, None)
    peaks = []
    for index in range(1, len(noisy) - 1):
        if noisy[index] >= DETECTION_FLOOR and noisy[index] >= noisy[index - 1] and noisy[index] >= noisy[index + 1]:
            peaks.append({
                "wavenumber": round(float(wn[index]), 3),
                "intensity": round(float(noisy[index]), 5),
            })
    return peaks


class _Instrument:
    def __init__(self, world, budget):
        self.world = world
        self.budget = int(budget)
        self.calls = 0
        self.violated = False
        self._scanned = False

    def scan(self):
        rng = np.random.default_rng((self.world["observation_seed"], 0))
        wn = np.linspace(*WN_BOUNDS, GRID_N)
        self._scanned = True
        return _peaks(wn, _intensity(self.world, DEFAULT_SIGMA, wn), rng)

    def zoom(self, lo, hi):
        if self.calls >= self.budget:
            self.violated = True
            raise RuntimeError("zoom budget exhausted")
        lo_f, hi_f = float(lo), float(hi)
        if not (math.isfinite(lo_f) and math.isfinite(hi_f)):
            raise ValueError("zoom window must be finite")
        if not (WN_BOUNDS[0] <= lo_f < hi_f <= WN_BOUNDS[1]):
            raise ValueError("zoom window must lie inside wavenumber_bounds")
        width = hi_f - lo_f
        if not (MIN_ZOOM_WIDTH <= width <= MAX_ZOOM_WIDTH):
            raise ValueError("zoom width must be in [%s, %s]" % (MIN_ZOOM_WIDTH, MAX_ZOOM_WIDTH))
        self.calls += 1
        rng = np.random.default_rng((self.world["seed"], self.calls))
        wn = np.linspace(lo_f, hi_f, 240)
        return _peaks(wn, _intensity(self.world, ZOOM_SIGMA, wn), rng)


PUBLIC_PROBLEM = {
    "library": {name: list(lines) for name, lines in LIBRARY.items()},
    "wavenumber_bounds": [WN_BOUNDS[0], WN_BOUNDS[1]],
    "default_resolution_sigma": DEFAULT_SIGMA,
    "zoom_resolution_sigma": ZOOM_SIGMA,
    "zoom_budget_calls": ZOOM_BUDGET,
    "min_zoom_width": MIN_ZOOM_WIDTH,
    "max_zoom_width": MAX_ZOOM_WIDTH,
    "max_claimed_species": MAX_CLAIMED,
    "detection_floor": DETECTION_FLOOR,
    "measurement_model": "scan() is free and returns the default-resolution peak list; "
                         "zoom(lo, hi) charges one call and returns peaks in that window at "
                         "narrower resolution, which splits an 8 cm-1 blend",
    "impurity_model": "a contaminant adds a few strong lines that belong to no library species",
    "abstain_when": "the default scan is an unresolved alias, the spectrum is blank, or "
                    "unexplained lines remain after zooms",
}


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return [], confidence, True
    claimed = submission.get("species")
    if not isinstance(claimed, list) or not claimed:
        raise ValueError("species must be a non-empty list, or abstain")
    if len(claimed) > MAX_CLAIMED:
        raise ValueError("at most %d species may be claimed" % MAX_CLAIMED)
    parsed = []
    used = set()
    total = 0.0
    for row in claimed:
        if not isinstance(row, dict):
            raise ValueError("each species must be a mapping")
        name = row.get("name")
        if name not in LIBRARY:
            raise ValueError("claimed name is not in the library")
        if name in used:
            raise ValueError("duplicate species name")
        used.add(name)
        fraction = float(row.get("fraction", 0.0))
        if not math.isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
            raise ValueError("fraction must be in (0, 1]")
        parsed.append({"name": name, "fraction": fraction})
        total += fraction
    if abs(total - 1.0) > 0.05:
        raise ValueError("fractions must sum to one")
    parsed.sort(key=lambda row: row["name"])
    return parsed, confidence, False


def _metrics(world, claimed, abstain):
    blank = {
        "species_set_correct": False,
        "fraction_score": 0.0,
        "mechanism_score": 0.0,
        "claimed_false_species": False,
        "correct_refusal": False,
        "false_discovery": False,
    }
    unsupported = world["kind"] in {"contaminant", "blank"}
    if unsupported:
        correct = bool(abstain)
        blank.update({
            "fraction_score": 1.0 if correct else 0.0,
            "mechanism_score": 1.0 if correct else 0.0,
            "claimed_false_species": not correct,
            "correct_refusal": correct,
            "false_discovery": not correct,
        })
        return blank
    if abstain or not claimed:
        return blank
    truth = {name: frac for name, frac in world["components"]}
    names = {row["name"] for row in claimed}
    set_correct = names == set(truth)
    errors = [abs(row["fraction"] - truth.get(row["name"], 0.0)) for row in claimed]
    for name in truth:
        if name not in names:
            errors.append(truth[name])
    fraction = float(np.mean([np.clip(1.0 - err / FRACTION_TOLERANCE, 0.0, 1.0) for err in errors])) if errors else 0.0
    blank.update({
        "species_set_correct": bool(set_correct),
        "fraction_score": fraction,
        "mechanism_score": fraction if set_correct else 0.0,
        "claimed_false_species": bool(names - set(truth)),
        "correct_refusal": False,
        "false_discovery": False,
    })
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "simple", "seed": 82100301},
    {"kind": "simple", "seed": 82100302},
    {"kind": "simple", "seed": 82100303},
    {"kind": "crowded", "seed": 82100304},
    {"kind": "crowded", "seed": 82100305},
    {"kind": "alias", "variant": "blend", "seed": 82100306, "observation_seed": 82100360},
    {"kind": "alias", "variant": "epsilon", "seed": 82100307, "observation_seed": 82100360},
    {"kind": "contaminant", "seed": 82100308},
    {"kind": "blank", "seed": 82100309},
)

HELDOUT_WORLDS = (
    {"kind": "simple", "seed": 93210401},
    {"kind": "simple", "seed": 93210402},
    {"kind": "crowded", "seed": 93210403},
    {"kind": "crowded", "seed": 93210404},
    {"kind": "alias", "variant": "blend", "seed": 93210405, "observation_seed": 93210450},
    {"kind": "alias", "variant": "epsilon", "seed": 93210406, "observation_seed": 93210450},
    {"kind": "contaminant", "seed": 93210407},
    {"kind": "blank", "seed": 93210408},
)

ROW_KEYS = (
    "species_set_correct", "fraction_score", "mechanism_score", "claimed_false_species",
    "correct_refusal", "false_discovery",
)


def _evaluate_world(assign_species, spec, split, index):
    world = _world(spec)
    instrument = _Instrument(world, ZOOM_BUDGET)
    problem = dict(PUBLIC_PROBLEM)
    # Nested dicts must be copies so a candidate cannot mutate the library for later worlds.
    problem["library"] = {name: list(lines) for name, lines in LIBRARY.items()}
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "zoom_calls": 0}
    try:
        submission = assign_species(problem, instrument.scan, instrument.zoom)
        claimed, confidence, abstain = _validate_submission(submission)
        if instrument.violated:
            raise RuntimeError("zoom budget exceeded")
        metrics = _metrics(world, claimed, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_species_count": len(claimed),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "zoom_calls": instrument.calls,
            "scanned": instrument._scanned,
        })
        for key in ("fraction_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_species_count": 0,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "zoom_calls": instrument.calls,
            "scanned": instrument._scanned,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] not in {"contaminant", "blank"}]
    unsupported = [r for r in records if r["kind"] in {"contaminant", "blank"}]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "species_set_rate": float(np.mean([r["species_set_correct"] for r in determinable])),
        "fraction_score": float(np.mean([r["fraction_score"] for r in determinable])),
        "false_species_rate": float(np.mean([r["claimed_false_species"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(
            np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_zoom_calls": float(np.mean([r["zoom_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(assign_species, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(assign_species, "reset_session"):
            assign_species.reset_session()
        records.append(_evaluate_world(assign_species, spec, split, index))
    return records


def evaluate(assign_species):
    development = _evaluate_specs(assign_species, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        assign_species, HELDOUT_WORLDS, "heldout", reset_before_first=True
    )
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_species_set_rate": dev["species_set_rate"],
        "development_fraction_score": dev["fraction_score"],
        "development_false_species_rate": dev["false_species_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_zoom_calls": dev["mean_zoom_calls"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_species_set_rate": held["species_set_rate"],
        "heldout_fraction_score": held["fraction_score"],
        "heldout_false_species_rate": held["false_species_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
