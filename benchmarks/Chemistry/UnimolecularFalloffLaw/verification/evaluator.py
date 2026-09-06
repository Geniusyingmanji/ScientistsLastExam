"""Frozen oracle for UnimolecularFalloffLaw."""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 18
T_BOUNDS = (300.0, 1200.0)
P_BOUNDS = (1.0e-3, 1.0e2)
SUPPORTED = {"lindemann", "troe"}

PUBLIC_PROBLEM = {
    "temperature_bounds_K": list(T_BOUNDS),
    "pressure_bounds_bar": list(P_BOUNDS),
    "measure_budget_calls": MEASURE_BUDGET,
    "family_names": ["lindemann", "troe"],
    "rate_law": (
        "k(T,P) = k_inf(T) * Pr/(1+Pr) * F(Pr); Pr = k0(T)*[M]/k_inf(T); "
        "Lindemann has F=1; Troe uses a constant Fcent in (0,1)"
    ),
    "measurement_model": (
        "measure(temperature_K, pressure_bar) returns ln k in 1/s plus frozen Gaussian noise"
    ),
    "abstain_when": (
        "a second pressure-independent channel is open, or k falls as pressure rises"
    ),
}


def public_problem():
    return dict(PUBLIC_PROBLEM)


def k_inf(spec, temperature):
    return float(spec["A_inf"]) * math.exp(-float(spec["E_inf"]) / max(float(temperature), 1.0))


def k0_m(spec, temperature, pressure):
    return (
        float(spec["A0"])
        * (float(pressure) / max(float(temperature), 1.0))
        * math.exp(-float(spec["E0"]) / max(float(temperature), 1.0))
    )


def true_k(spec, temperature, pressure):
    kind = spec["kind"]
    temperature = float(temperature)
    pressure = float(pressure)
    kinf = k_inf(spec, temperature)
    k0 = k0_m(spec, temperature, pressure)
    pr = k0 / max(kinf, 1e-30)
    lindemann = kinf * pr / (1.0 + pr)
    if kind == "lindemann":
        return lindemann
    if kind == "troe":
        fcent = float(spec["Fcent"])
        log_pr = math.log10(max(pr, 1e-12))
        n = 0.75 - 1.27 * math.log10(max(fcent, 1e-6))
        log_f = math.log10(max(fcent, 1e-6)) / (1.0 + (log_pr / max(n, 0.1)) ** 2)
        return lindemann * (10.0 ** log_f)
    if kind == "two_channel":
        extra = float(spec["A2"]) * math.exp(-float(spec["E2"]) / max(temperature, 1.0))
        return lindemann + extra
    if kind == "negative":
        return kinf / (1.0 + 0.35 * math.log10(max(pressure, 1e-6) * 1.0e3))
    raise ValueError("unknown family")


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False

    def measure(self, temperature_K, pressure_bar):
        t = float(temperature_K)
        p = float(pressure_bar)
        if not math.isfinite(t) or not math.isfinite(p):
            raise ValueError("temperature and pressure must be finite")
        if not (T_BOUNDS[0] <= t <= T_BOUNDS[1] and P_BOUNDS[0] <= p <= P_BOUNDS[1]):
            raise ValueError("assay outside public bounds")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        rng = np.random.default_rng((int(self.spec["seed"]), 17, self.used))
        value = math.log(max(true_k(self.spec, t, p), 1e-30))
        return float(value + 0.04 * rng.normal())


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return True, None, None, None, 1.0, confidence
    family = submission.get("family")
    if family not in PUBLIC_PROBLEM["family_names"]:
        raise ValueError("family must be one of family_names")
    log_kinf = float(submission.get("log_k_inf_300K"))
    log_pr = float(submission.get("log_Pr_300K_1bar"))
    fcent = float(submission.get("Fcent", 1.0))
    if not all(math.isfinite(v) for v in (log_kinf, log_pr, fcent)):
        raise ValueError("rate parameters must be finite")
    if family == "lindemann" and abs(fcent - 1.0) > 1e-6:
        raise ValueError("Lindemann submissions must set Fcent to 1")
    if family == "troe" and not (0.05 <= fcent < 1.0):
        raise ValueError("Troe Fcent must lie in [0.05, 1)")
    return False, family, log_kinf, log_pr, fcent, confidence


def _mechanism(spec, abstain, family, log_kinf, log_pr, fcent):
    if spec["kind"] not in SUPPORTED:
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    kinf = k_inf(spec, 300.0)
    pr = k0_m(spec, 300.0, 1.0) / max(kinf, 1e-30)
    e_inf = abs(log_kinf - math.log(kinf)) / 1.2
    e_pr = abs(log_pr - math.log(max(pr, 1e-12))) / 1.6
    if spec["kind"] == "lindemann":
        e_f = 0.0 if family == "lindemann" else 0.8
    else:
        e_f = abs(float(fcent) - spec["Fcent"]) / 0.35 if family == "troe" else 0.8
    err = 0.40 * min(e_inf, 1.0) + 0.35 * min(e_pr, 1.0) + 0.25 * min(e_f, 1.0)
    return float(np.clip(1.0 - err / 0.55, 0.0, 1.0)), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "lindemann", "seed": 11001, "A_inf": 2.4e7, "E_inf": 2100.0, "A0": 4.8e9, "E0": 900.0},
    {"kind": "troe", "seed": 11002, "A_inf": 1.1e8, "E_inf": 2450.0, "A0": 2.2e10, "E0": 700.0, "Fcent": 0.42},
    {"kind": "troe", "seed": 11003, "A_inf": 6.5e7, "E_inf": 1800.0, "A0": 9.4e9, "E0": 1100.0, "Fcent": 0.28},
    {"kind": "two_channel", "seed": 12001, "A_inf": 3.0e7, "E_inf": 2000.0, "A0": 5.0e9, "E0": 800.0, "A2": 4.0e5, "E2": 900.0},
    {"kind": "two_channel", "seed": 12002, "A_inf": 8.0e7, "E_inf": 2600.0, "A0": 1.5e10, "E0": 600.0, "A2": 1.2e6, "E2": 1400.0},
    {"kind": "negative", "seed": 13001, "A_inf": 5.0e7, "E_inf": 2200.0, "A0": 3.0e9, "E0": 850.0},
    {"kind": "negative", "seed": 13002, "A_inf": 9.0e6, "E_inf": 1600.0, "A0": 1.0e9, "E0": 500.0},
)
HELDOUT_WORLDS = (
    {"kind": "lindemann", "seed": 21001, "A_inf": 4.1e7, "E_inf": 1950.0, "A0": 7.7e9, "E0": 950.0},
    {"kind": "troe", "seed": 21002, "A_inf": 2.0e8, "E_inf": 2300.0, "A0": 3.3e10, "E0": 750.0, "Fcent": 0.51},
    {"kind": "two_channel", "seed": 22001, "A_inf": 1.5e7, "E_inf": 1700.0, "A0": 2.8e9, "E0": 1000.0, "A2": 8.0e5, "E2": 1100.0},
    {"kind": "negative", "seed": 23001, "A_inf": 3.2e7, "E_inf": 2050.0, "A0": 4.4e9, "E0": 720.0},
    {"kind": "negative", "seed": 23002, "A_inf": 1.8e7, "E_inf": 2400.0, "A0": 6.1e9, "E0": 880.0},
)


def _evaluate_world(identify, spec, split, index):
    lab = _Lab(spec)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = identify(public_problem(), lab.measure)
        abstain, family, log_kinf, log_pr, fcent, confidence = _validate(submission)
        if lab.violated:
            raise RuntimeError("measure budget exceeded")
        mech, refused, false = _mechanism(spec, abstain, family, log_kinf, log_pr, fcent)
        return {
            **base,
            "mechanism_score": round(float(mech), 6),
            "correct_refusal": refused,
            "false_discovery": false,
            "valid": True,
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "measure_calls": lab.used,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "measure_calls": lab.used,
        }


def _split_summary(records):
    supported = [row for row in records if row["kind"] in SUPPORTED]
    unsupported = [row for row in records if row["kind"] not in SUPPORTED]
    raw = float(np.mean([row["mechanism_score"] for row in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "signal_recovery_rate": float(np.mean([row["mechanism_score"] for row in supported])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in unsupported])),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "discovery_coverage": float(np.mean([not row["abstained"] for row in supported])),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "world_count": len(records),
    }


def _run(identify, worlds, split, reset_before_first=False):
    rows = []
    for index, spec in enumerate(worlds):
        if (index or reset_before_first) and hasattr(identify, "reset_session"):
            identify.reset_session()
        rows.append(_evaluate_world(identify, spec, split, index))
    return rows


def evaluate(identify_falloff):
    development = _run(identify_falloff, DEVELOPMENT_WORLDS, "development")
    heldout = _run(identify_falloff, HELDOUT_WORLDS, "heldout", reset_before_first=True)
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
