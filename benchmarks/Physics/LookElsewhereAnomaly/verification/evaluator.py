"""Frozen oracle for LookElsewhereAnomaly (hidden from the agent).

A mass histogram is Poisson in each window. The public background is flat. Four world
kinds exist: a narrow resonance that remains global-5σ after a trials factor; a local
~5σ fluke that dies after Bonferroni; a linearly sculpted background that only looks
like a bump against the flat prior; and a blank. Claiming a particle on the last three
is a false discovery. Declining every world scores exactly zero after normalisation.
"""
from __future__ import annotations

import math

import numpy as np

N_BINS = 40
MASS = np.linspace(100.0, 180.0, N_BINS)
DX = float(MASS[1] - MASS[0])
BKG = 80.0
SIGNAL_AMPLITUDE = 85.0
SIGNAL_WIDTH = 2.4
SCULPTED_SLOPE = 1.05
TOYS_BUDGET = 8
TOYS_BATCH = 25
FIVE_SIGMA_P = 2.87e-7
MASS_TOLERANCE = 2.05 * DX
SIDEBAND_EXCLUDE = 2
SIDEBAND_REFUSE = 2.5

PUBLIC_PROBLEM = {
    "expected_background": BKG,
    "n_mass_windows": N_BINS,
    "toys_budget_units": TOYS_BUDGET,
    "toys_batch_size": TOYS_BATCH,
    "five_sigma_global_p": FIVE_SIGMA_P,
    "measurement_model": (
        "each mass window is an independent Poisson count; toys(n) draws n histograms "
        "from the public expected_background and charges ceil(n / toys_batch_size) "
        "budget units"
    ),
    "abstain_when": (
        "the leading local excess is not global-5σ after a trials factor, the spectrum "
        "is consistent with background, or the sidebands reject the public background"
    ),
    "look_elsewhere_note": (
        "n_mass_windows independent searches inflate the local tail; a local 5σ is not "
        "a discovery"
    ),
}


def public_problem():
    """Static contract keys. Per-world mass_gev and counts are attached in evaluate."""
    return {
        "expected_background": BKG,
        "n_mass_windows": N_BINS,
        "toys_budget_units": TOYS_BUDGET,
        "toys_batch_size": TOYS_BATCH,
        "five_sigma_global_p": FIVE_SIGMA_P,
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
        "look_elsewhere_note": PUBLIC_PROBLEM["look_elsewhere_note"],
    }


def _world(spec):
    kind = spec["kind"]
    seed = int(spec["seed"])
    if kind == "signal":
        rng = np.random.default_rng((seed, 1))
        peak = float(MASS[int(spec["peak_bin"])])
        rate = BKG + SIGNAL_AMPLITUDE * np.exp(-0.5 * ((MASS - peak) / SIGNAL_WIDTH) ** 2)
        counts = rng.poisson(rate)
        return {"kind": kind, "seed": seed, "counts": counts, "peak_mass": peak}
    if kind in {"fluke", "blank"}:
        rng = np.random.default_rng((seed, 2))
        return {"kind": kind, "seed": seed, "counts": rng.poisson(BKG, size=N_BINS)}
    if kind == "sculpted":
        rng = np.random.default_rng((seed, 3))
        rate = np.clip(BKG + SCULPTED_SLOPE * (MASS - 140.0), 8.0, None)
        return {"kind": kind, "seed": seed, "counts": rng.poisson(rate)}
    raise ValueError("unknown world kind")


class _Toys:
    def __init__(self, world, budget):
        self.world = world
        self.budget = int(budget)
        self.spent = 0
        self.calls = 0
        self.violated = False

    def toys(self, n_toys):
        if isinstance(n_toys, bool):
            raise ValueError("n_toys must be an integer")
        n = int(n_toys)
        if n != n_toys or n < 1:
            raise ValueError("n_toys must be a positive integer")
        cost = int(math.ceil(n / float(TOYS_BATCH)))
        if self.spent + cost > self.budget:
            self.violated = True
            raise RuntimeError("toy budget exhausted")
        self.spent += cost
        self.calls += 1
        out = []
        for index in range(n):
            rng = np.random.default_rng((self.world["seed"], 100 + self.calls, index))
            out.append(rng.poisson(BKG, size=N_BINS).tolist())
        return out


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
        return False, None, confidence, True
    if "discovery" not in submission:
        raise ValueError("discovery is required unless abstaining")
    discovery = submission.get("discovery")
    if not isinstance(discovery, bool):
        raise ValueError("discovery must be a boolean")
    mass = submission.get("mass_gev")
    if discovery:
        mass = float(mass)
        if not math.isfinite(mass):
            raise ValueError("mass_gev must be finite when claiming a discovery")
        if not (float(MASS[0]) <= mass <= float(MASS[-1])):
            raise ValueError("mass_gev must lie inside the scanned range")
    else:
        mass = None
    return discovery, mass, confidence, False


def _metrics(world, discovery, mass, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "mass_within_tolerance": False,
    }
    unsupported = world["kind"] in {"fluke", "sculpted", "blank"}
    if unsupported:
        claimed = (not abstain) and bool(discovery)
        correct = bool(abstain)
        row.update({
            "mechanism_score": 1.0 if correct else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": claimed,
        })
        return row
    if abstain or not discovery or mass is None:
        return row
    within = abs(float(mass) - float(world["peak_mass"])) <= MASS_TOLERANCE
    row.update({
        "mechanism_score": 1.0 if within else 0.0,
        "mass_within_tolerance": bool(within),
    })
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "signal", "seed": 82100301, "peak_bin": 9},
    {"kind": "signal", "seed": 82100302, "peak_bin": 10},
    {"kind": "signal", "seed": 82100303, "peak_bin": 11},
    {"kind": "fluke", "seed": 93039836},
    {"kind": "fluke", "seed": 93215535},
    {"kind": "sculpted", "seed": 74400201},
    {"kind": "sculpted", "seed": 74400202},
    {"kind": "blank", "seed": 93210402},
    {"kind": "blank", "seed": 93210403},
)

HELDOUT_WORLDS = (
    {"kind": "signal", "seed": 82100304, "peak_bin": 12},
    {"kind": "signal", "seed": 82100305, "peak_bin": 13},
    {"kind": "fluke", "seed": 93065750},
    {"kind": "fluke", "seed": 93219877},
    {"kind": "sculpted", "seed": 74400203},
    {"kind": "sculpted", "seed": 74400204},
    {"kind": "blank", "seed": 93210404},
    {"kind": "blank", "seed": 93210405},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "mass_within_tolerance")


def _evaluate_world(interpret_spectrum, spec, split, index):
    world = _world(spec)
    instrument = _Toys(world, TOYS_BUDGET)
    problem = dict(PUBLIC_PROBLEM)
    problem["mass_gev"] = [float(x) for x in MASS]
    problem["counts"] = [int(x) for x in world["counts"]]
    base = {"split": split, "world_index": int(index), "kind": world["kind"], "toy_units_spent": 0}
    try:
        submission = interpret_spectrum(problem, instrument.toys)
        discovery, mass, confidence, abstain = _validate_submission(submission)
        if instrument.violated:
            raise RuntimeError("toy budget exceeded")
        metrics = _metrics(world, discovery, mass, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_discovery": bool(discovery) and not abstain,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "toy_units_spent": instrument.spent,
            "toy_calls": instrument.calls,
        })
        row["mechanism_score"] = round(float(row["mechanism_score"]), 6)
        return row
    except Exception as exc:  # noqa: BLE001
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_discovery": False,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "toy_units_spent": instrument.spent,
            "toy_calls": instrument.calls,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "signal"]
    unsupported = [r for r in records if r["kind"] in {"fluke", "sculpted", "blank"}]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "signal_recovery_rate": float(np.mean([r["mechanism_score"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in unsupported])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(
            np.mean([r["confidence_calibration_score"] for r in records])
        ),
        "mean_toy_units": float(np.mean([r["toy_units_spent"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(interpret_spectrum, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(interpret_spectrum, "reset_session"):
            interpret_spectrum.reset_session()
        records.append(_evaluate_world(interpret_spectrum, spec, split, index))
    return records


def evaluate(interpret_spectrum):
    development = _evaluate_specs(interpret_spectrum, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        interpret_spectrum, HELDOUT_WORLDS, "heldout", reset_before_first=True
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
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_toy_units": dev["mean_toy_units"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
