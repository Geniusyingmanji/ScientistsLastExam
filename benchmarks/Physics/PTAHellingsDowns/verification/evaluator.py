"""Frozen oracle for PTAHellingsDowns (hidden from the agent).

Pulsar-pair correlations are drawn from one of four spatial kernels. A Hellings-Downs
quadrupole is a gravitational-wave background. A monopole is a clock error, a dipole an
ephemeris error, and an uncorrelated common process is CURN. Claiming HD on the last
three is the false discovery the PTA literature spent a decade separating from a GWB.
This is not LookElsewhereAnomaly (a mass histogram) and not a strain-amplitude fit.
"""
from __future__ import annotations

import math

import numpy as np

N_PULSARS = 18
NOISE = 0.11
BOOT_BUDGET = 6
BOOT_BATCH = 20

PUBLIC_PROBLEM = {
    "n_pulsars": N_PULSARS,
    "bootstrap_budget_units": BOOT_BUDGET,
    "bootstrap_batch_size": BOOT_BATCH,
    "kernel_names": ["hellings_downs", "monopole", "dipole", "uncorrelated"],
    "measurement_model": (
        "each row is one pulsar pair: theta_rad and rho. The legacy-named bootstrap(n) "
        "draws n parametric replicate tables from the hidden kernel and charges "
        "ceil(n / bootstrap_batch_size) units"
    ),
    "hellings_downs_note": (
        "an isotropic GWB produces the Hellings-Downs quadrupole of pulsar angle; "
        "a clock error is a monopole and an ephemeris error is a dipole"
    ),
    "abstain_when": (
        "the correlations prefer a monopole, a dipole, or no spatial kernel, or "
        "Hellings-Downs is not uniquely supported"
    ),
}


def public_problem():
    return {
        "n_pulsars": N_PULSARS,
        "bootstrap_budget_units": BOOT_BUDGET,
        "bootstrap_batch_size": BOOT_BATCH,
        "kernel_names": PUBLIC_PROBLEM["kernel_names"],
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "hellings_downs_note": PUBLIC_PROBLEM["hellings_downs_note"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


def hellings_downs_orf(theta):
    """Overlap reduction for distinct pulsars. HD(0+)=1/2, HD(pi)=1/4."""
    x = 0.5 * (1.0 - np.cos(theta))
    x = np.clip(x, 1e-15, 1.0)
    return 0.5 - 0.25 * x + 1.5 * x * np.log(x)


def _positions(seed):
    rng = np.random.default_rng((int(seed), 1))
    vecs = rng.normal(size=(N_PULSARS, 3))
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs


def _pairs(vecs):
    theta = []
    i_idx = []
    j_idx = []
    for i in range(N_PULSARS):
        for j in range(i + 1, N_PULSARS):
            c = float(np.clip(np.dot(vecs[i], vecs[j]), -1.0, 1.0))
            theta.append(math.acos(c))
            i_idx.append(i)
            j_idx.append(j)
    return np.asarray(theta), i_idx, j_idx


def _kernel(kind, theta):
    if kind == "hellings_downs":
        return hellings_downs_orf(theta)
    if kind == "monopole":
        return np.ones_like(theta)
    if kind == "dipole":
        return np.cos(theta)
    return np.zeros_like(theta)


def _draw_rho(kind, theta, seed, stream):
    rng = np.random.default_rng((int(seed), int(stream)))
    return _kernel(kind, theta) + NOISE * rng.normal(size=theta.shape)


class _Lab:
    def __init__(self, spec, theta):
        self.spec = spec
        self.theta = theta
        self.used = 0
        self.calls = 0
        self.violated = False

    def bootstrap(self, n):
        if isinstance(n, bool):
            raise ValueError("n must be an integer")
        count = int(n)
        if count != n or count < 1:
            raise ValueError("n must be a positive integer")
        cost = int(math.ceil(count / float(BOOT_BATCH)))
        if self.used + cost > BOOT_BUDGET:
            self.violated = True
            raise RuntimeError("bootstrap budget exhausted")
        self.used += cost
        self.calls += 1
        tables = []
        for index in range(count):
            rho = _draw_rho(self.spec["kind"], self.theta, self.spec["seed"], 50 + self.calls * 100 + index)
            tables.append({"theta_rad": self.theta.tolist(), "rho": rho.tolist()})
        return tables


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
        return None, confidence, True
    kernel = submission.get("kernel")
    if kernel not in PUBLIC_PROBLEM["kernel_names"]:
        raise ValueError("kernel must be one of kernel_names")
    return kernel, confidence, False


def _metrics(kind, kernel, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "kernel_correct": False,
    }
    unsupported = kind != "hellings_downs"
    if unsupported:
        claimed_hd = (not abstain) and kernel == "hellings_downs"
        row.update({
            "mechanism_score": 1.0 if abstain else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": claimed_hd,
        })
        return row
    if abstain or kernel != "hellings_downs":
        return row
    row.update({"mechanism_score": 1.0, "kernel_correct": True})
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "hellings_downs", "seed": 81001},
    {"kind": "hellings_downs", "seed": 81002},
    {"kind": "hellings_downs", "seed": 81003},
    {"kind": "monopole", "seed": 82001},
    {"kind": "monopole", "seed": 82002},
    {"kind": "dipole", "seed": 83001},
    {"kind": "uncorrelated", "seed": 84001},
)

HELDOUT_WORLDS = (
    {"kind": "hellings_downs", "seed": 91001},
    {"kind": "hellings_downs", "seed": 91002},
    {"kind": "monopole", "seed": 92001},
    {"kind": "dipole", "seed": 93001},
    {"kind": "uncorrelated", "seed": 94001},
    {"kind": "uncorrelated", "seed": 94002},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "kernel_correct")


def _evaluate_world(interpret_correlations, spec, split, index):
    vecs = _positions(spec["seed"])
    theta, _, _ = _pairs(vecs)
    rho = _draw_rho(spec["kind"], theta, spec["seed"], 7)
    lab = _Lab(spec, theta)
    problem = dict(PUBLIC_PROBLEM)
    problem["theta_rad"] = [float(x) for x in theta]
    problem["rho"] = [float(x) for x in rho]
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "boot_units": 0}
    try:
        submission = interpret_correlations(problem, lab.bootstrap)
        kernel, confidence, abstain = _validate_submission(submission)
        if lab.violated:
            raise RuntimeError("bootstrap budget exceeded")
        metrics = _metrics(spec["kind"], kernel, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_hd": (not abstain) and kernel == "hellings_downs",
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "boot_units": lab.used,
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
            "claimed_hd": False,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "boot_units": lab.used,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "hellings_downs"]
    unsupported = [r for r in records if r["kind"] != "hellings_downs"]
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
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_boot_units": float(np.mean([r["boot_units"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(interpret_correlations, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(interpret_correlations, "reset_session"):
            interpret_correlations.reset_session()
        records.append(_evaluate_world(interpret_correlations, spec, split, index))
    return records


def evaluate(interpret_correlations):
    development = _evaluate_specs(
        interpret_correlations, DEVELOPMENT_WORLDS, "development"
    )
    heldout = _evaluate_specs(
        interpret_correlations, HELDOUT_WORLDS, "heldout", reset_before_first=True
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
        "development_mean_boot_units": dev["mean_boot_units"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
