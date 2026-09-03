"""Frozen oracle for AMOCTippingRefusal (hidden from the agent).

A cubic fold (Stommel-like) is one hidden family. Equally plausible worlds have no fold:
red-noise monostable flow, or an ice-restored unique attractor that still declines with
freshwater. Quoting a collapse year on those worlds is a false discovery. This is not
ClimateScience/EnergyBalanceModel (named two-layer parameter inversion) and not
DynamicalSystems/ActiveLawDiscovery (sparse polynomial ODE library).
"""
from __future__ import annotations

import math

import numpy as np

YEAR0 = 1870
YEAR_NOW = 2020
DT = 0.25
PROBE_BUDGET = 6
MIN_DURATION = 20
MAX_DURATION = 100
OFFSET_BOUNDS = (-0.6, 0.6)
YEAR_TOLERANCE = 25.0
F0 = 0.48
F_SLOPE = -0.0040  # F(2020)=-0.12; fold F≈-0.385 at year ≈ 2086


def _F(year, offset=0.0):
    return F0 + F_SLOPE * (float(year) - YEAR0) + float(offset)


def _integrate(mu, k_restore, noise, x0, years, offset, seed, hold_F=None):
    rng = np.random.default_rng(seed)
    x = float(x0)
    out = np.empty(len(years), dtype=float)
    for i, year in enumerate(years):
        f = hold_F if hold_F is not None else _F(year, offset)
        drift = -x ** 3 + mu * x + f - k_restore * x
        x = x + DT * drift + noise * math.sqrt(DT) * rng.normal()
        out[i] = x
    return out


def _spec_params(kind):
    if kind == "fold":
        return 1.0, 0.0, 0.030, 1.00
    if kind == "red_noise":
        return -0.70, 0.0, 0.12, 0.35
    if kind == "ice":
        return 1.0, 1.55, 0.030, 1.00
    raise ValueError("unknown kind")


def _history(spec):
    mu, k, noise, x0 = _spec_params(spec["kind"])
    years = np.arange(YEAR0, YEAR_NOW + DT, DT)
    seed = (int(spec["seed"]), 3)
    hold = 0.0 if spec["kind"] == "red_noise" else None
    xs = _integrate(mu, k, noise, x0, years, 0.0, seed, hold_F=hold)
    # downsample to annual for the public series
    annual_years = np.arange(YEAR0, YEAR_NOW + 1)
    annual = np.interp(annual_years, years, xs)
    return annual_years, annual, xs[-1]


def _true_collapse_year(spec, x_now):
    if spec["kind"] != "fold":
        return None
    mu, k, noise, _ = _spec_params(spec["kind"])
    years = np.arange(YEAR_NOW, YEAR_NOW + 160 + DT, DT)
    xs = _integrate(mu, k, noise, x_now, years, 0.0, (int(spec["seed"]), 9), hold_F=None)
    for year, value, prev in zip(years[1:], xs[1:], xs[:-1]):
        if prev > 0.0 and value <= 0.0:
            return float(year)
    return None


PUBLIC_PROBLEM = {
    "year_start": YEAR0,
    "year_now": YEAR_NOW,
    "probe_budget": PROBE_BUDGET,
    "min_duration_years": MIN_DURATION,
    "max_duration_years": MAX_DURATION,
    "freshwater_offset_low": OFFSET_BOUNDS[0],
    "freshwater_offset_high": OFFSET_BOUNDS[1],
    "modes": ["plus", "minus", "continue"],
    "measurement_model": (
        "historical_years / historical_amoc are the public fingerprint through year_now; "
        "probe(offset, duration_years, mode) charges one call. mode plus/minus holds "
        "F(year_now)+offset and starts from x=+1 or x=-1; mode continue starts from the "
        "historical end state and keeps the hidden F(year)+offset"
    ),
    "abstain_when": (
        "the fingerprint is red noise with no fold, an ice-restored unique attractor, "
        "or hysteresis is not supported by plus/minus probes"
    ),
}


def public_problem():
    return {
        "year_start": YEAR0,
        "year_now": YEAR_NOW,
        "probe_budget": PROBE_BUDGET,
        "min_duration_years": MIN_DURATION,
        "max_duration_years": MAX_DURATION,
        "freshwater_offset_low": OFFSET_BOUNDS[0],
        "freshwater_offset_high": OFFSET_BOUNDS[1],
        "modes": ["plus", "minus", "continue"],
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


class _Lab:
    def __init__(self, spec, x_now):
        self.spec = spec
        self.x_now = float(x_now)
        self.used = 0
        self.violated = False
        self.mu, self.k, self.noise, _ = _spec_params(spec["kind"])

    def probe(self, freshwater_offset, duration_years, mode):
        if self.used >= PROBE_BUDGET:
            self.violated = True
            raise RuntimeError("probe budget exhausted")
        offset = float(freshwater_offset)
        if not math.isfinite(offset) or not (OFFSET_BOUNDS[0] <= offset <= OFFSET_BOUNDS[1]):
            raise ValueError("freshwater_offset outside bounds")
        duration = float(duration_years)
        if not math.isfinite(duration) or not (MIN_DURATION <= duration <= MAX_DURATION):
            raise ValueError("duration_years outside bounds")
        if mode not in {"plus", "minus", "continue"}:
            raise ValueError("mode must be plus, minus, or continue")
        self.used += 1
        years = np.arange(YEAR_NOW, YEAR_NOW + duration + DT, DT)
        hold = _F(YEAR_NOW, offset)
        if self.spec["kind"] == "red_noise":
            hold = offset  # no hidden ramp
        if mode == "plus":
            x0, hold_F = 1.0, hold
        elif mode == "minus":
            x0, hold_F = -1.0, hold
        else:
            x0, hold_F = self.x_now, None if self.spec["kind"] != "red_noise" else hold
            if self.spec["kind"] == "red_noise":
                hold_F = offset
        seed = (int(self.spec["seed"]), 20 + self.used)
        if mode == "continue" and self.spec["kind"] != "red_noise":
            xs = _integrate(self.mu, self.k, self.noise, x0, years, offset, seed, hold_F=None)
        else:
            xs = _integrate(self.mu, self.k, self.noise, x0, years, offset, seed, hold_F=hold_F)
        annual_years = np.arange(YEAR_NOW, int(math.floor(YEAR_NOW + duration)) + 1)
        annual = np.interp(annual_years, years[: len(xs)], xs)
        return {
            "years": [int(y) for y in annual_years],
            "amoc": [float(v) for v in annual],
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
        return False, None, confidence, True
    if "has_tipping" not in submission:
        raise ValueError("has_tipping is required unless abstaining")
    has = submission.get("has_tipping")
    if not isinstance(has, bool):
        raise ValueError("has_tipping must be a boolean")
    year = submission.get("collapse_year")
    if has:
        year = float(year)
        if not math.isfinite(year):
            raise ValueError("collapse_year must be finite when claiming a tip")
    else:
        year = None
    return has, year, confidence, False


def _metrics(kind, true_year, has, year, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "year_within_tolerance": False,
    }
    unsupported = kind in {"red_noise", "ice"}
    if unsupported:
        claimed = (not abstain) and bool(has)
        row.update({
            "mechanism_score": 1.0 if abstain else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": claimed,
        })
        return row
    if abstain or not has or year is None or true_year is None:
        return row
    within = abs(float(year) - float(true_year)) <= YEAR_TOLERANCE
    row.update({
        "mechanism_score": 1.0 if within else 0.0,
        "year_within_tolerance": bool(within),
    })
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "fold", "seed": 61001},
    {"kind": "fold", "seed": 61002},
    {"kind": "fold", "seed": 61003},
    {"kind": "red_noise", "seed": 62001},
    {"kind": "red_noise", "seed": 62002},
    {"kind": "ice", "seed": 63001},
    {"kind": "ice", "seed": 63002},
)

HELDOUT_WORLDS = (
    {"kind": "fold", "seed": 71001},
    {"kind": "fold", "seed": 71002},
    {"kind": "red_noise", "seed": 72001},
    {"kind": "red_noise", "seed": 72002},
    {"kind": "ice", "seed": 73001},
    {"kind": "ice", "seed": 73002},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "year_within_tolerance")


def _evaluate_world(interpret_amoc, spec, split, index):
    years, amoc, x_now = _history(spec)
    true_year = _true_collapse_year(spec, x_now)
    lab = _Lab(spec, x_now)
    problem = dict(PUBLIC_PROBLEM)
    problem["historical_years"] = [int(y) for y in years]
    problem["historical_amoc"] = [float(v) for v in amoc]
    base = {
        "split": split, "world_index": int(index), "kind": spec["kind"],
        "probe_calls": 0, "true_collapse_year": true_year,
    }
    try:
        submission = interpret_amoc(problem, lab.probe)
        has, year, confidence, abstain = _validate_submission(submission)
        if lab.violated:
            raise RuntimeError("probe budget exceeded")
        metrics = _metrics(spec["kind"], true_year, has, year, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_tip": bool(has) and not abstain,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "probe_calls": lab.used,
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
            "claimed_tip": False,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "probe_calls": lab.used,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "fold"]
    unsupported = [r for r in records if r["kind"] in {"red_noise", "ice"}]
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
        "mean_probe_calls": float(np.mean([r["probe_calls"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(interpret_amoc, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(interpret_amoc, "reset_session"):
            interpret_amoc.reset_session()
        records.append(_evaluate_world(interpret_amoc, spec, split, index))
    return records


def evaluate(interpret_amoc):
    development = _evaluate_specs(interpret_amoc, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        interpret_amoc, HELDOUT_WORLDS, "heldout", reset_before_first=True
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
        "development_mean_probe_calls": dev["mean_probe_calls"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
