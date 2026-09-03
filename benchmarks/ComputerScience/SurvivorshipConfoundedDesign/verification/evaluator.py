"""Frozen oracle for SurvivorshipConfoundedDesign (hidden from the agent).

Units are generated from a linear SCM, then only survivors are returned. A hidden
confounder C opens T ← C → Y and also feeds the selection logit, so the survivor
cloud is associated even when there is no T→Y edge. Randomising T and reading the
change in survival probability identifies the edge; ordinary least squares on the
returned rows does not.

This is not InterventionalSCM (full samples, recover a 7-node DAG) and not
GeneNetworkIntervention (ODE network + phenotype).
"""
from __future__ import annotations

import math

import numpy as np

OBS_MAX = 800
INT_MAX = 800
SAMPLE_UNIT = 100
BUDGET_UNITS = 8
T_LOW = -1.2
T_HIGH = 1.2

PUBLIC_PROBLEM = {
    "treatment_name": "treatment",
    "outcome_name": "outcome",
    "observe_batch_max": OBS_MAX,
    "intervene_batch_max": INT_MAX,
    "budget_units": BUDGET_UNITS,
    "sample_unit": SAMPLE_UNIT,
    "treatment_probe_low": T_LOW,
    "treatment_probe_high": T_HIGH,
    "measurement_model": (
        "observe_survivors(n) draws n units from the observational SCM and returns "
        "only those that pass selection; intervene(t, n) draws n units from do(T=t) "
        "then applies the same selection. Both return n_requested and n_returned"
    ),
    "selection_note": (
        "returned rows are survivors; n_returned / n_requested is the survival rate "
        "under the queried regime. In this model class, selection probability increases "
        "with outcome Y and treatment T has no direct path to selection"
    ),
    "abstain_when": (
        "survivor association is explained by confounding plus selection, the "
        "survival rate does not move under do(T), or the returned sample is too small"
    ),
}


def public_problem():
    return {
        "treatment_name": "treatment",
        "outcome_name": "outcome",
        "observe_batch_max": OBS_MAX,
        "intervene_batch_max": INT_MAX,
        "budget_units": BUDGET_UNITS,
        "sample_unit": SAMPLE_UNIT,
        "treatment_probe_low": T_LOW,
        "treatment_probe_high": T_HIGH,
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "selection_note": PUBLIC_PROBLEM["selection_note"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


def _draw(spec, n, do_t, call_index):
    rng = np.random.default_rng((int(spec["seed"]), 17 + int(call_index)))
    n = int(n)
    c = rng.normal(size=n)
    if do_t is None:
        t = 0.85 * c + 0.60 * rng.normal(size=n)
    else:
        t = np.full(n, float(do_t))
    a_ty = float(spec.get("a_ty", 0.0))
    y = 0.95 * c + a_ty * t + 0.35 * rng.normal(size=n)
    logit = -0.15 + 1.55 * y + 0.55 * c + float(spec.get("logit_shift", 0.0))
    survive = rng.random(n) < 1.0 / (1.0 + np.exp(-logit))
    return {
        "treatment": t[survive].tolist(),
        "outcome": y[survive].tolist(),
        "n_requested": n,
        "n_returned": int(survive.sum()),
    }


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.calls = 0
        self.violated = False

    def _charge(self, n, maximum):
        if isinstance(n, bool):
            raise ValueError("n must be an integer")
        value = int(n)
        if value != n or value < 8 or value > maximum:
            raise ValueError("n outside the allowed range")
        cost = int(math.ceil(value / float(SAMPLE_UNIT)))
        if self.used + cost > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("experimental budget exceeded")
        self.used += cost
        self.calls += 1
        return value

    def observe_survivors(self, n):
        count = self._charge(n, OBS_MAX)
        return _draw(self.spec, count, None, self.calls)

    def intervene(self, t, n):
        level = float(t)
        if not math.isfinite(level) or not (T_LOW - 1e-9 <= level <= T_HIGH + 1e-9):
            raise ValueError("treatment value must lie in [treatment_probe_low, treatment_probe_high]")
        count = self._charge(n, INT_MAX)
        return _draw(self.spec, count, level, self.calls)


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
        return False, 0, confidence, True
    if "has_treatment_effect" not in submission:
        raise ValueError("has_treatment_effect is required unless abstaining")
    has_effect = submission.get("has_treatment_effect")
    if not isinstance(has_effect, bool):
        raise ValueError("has_treatment_effect must be a boolean")
    sign = 0
    if has_effect:
        effect_sign = float(submission.get("effect_sign", 0.0))
        if not math.isfinite(effect_sign):
            raise ValueError("effect_sign must be finite")
        sign = int(np.sign(effect_sign))
        if sign == 0:
            raise ValueError("effect_sign must be a nonzero number when claiming an effect")
    return has_effect, sign, confidence, False


def _metrics(world, has_effect, sign, abstain):
    row = {
        "mechanism_score": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "sign_correct": False,
    }
    unsupported = world["kind"] in {"collider", "blank"}
    if unsupported:
        claimed = (not abstain) and bool(has_effect)
        row.update({
            "mechanism_score": 1.0 if abstain else 0.0,
            "correct_refusal": bool(abstain),
            "false_discovery": claimed,
        })
        return row
    if abstain or not has_effect:
        return row
    true_sign = int(np.sign(world["a_ty"]))
    ok = sign == true_sign
    row.update({
        "mechanism_score": 1.0 if ok else 0.0,
        "sign_correct": bool(ok),
    })
    return row


DEVELOPMENT_WORLDS = (
    {"kind": "causal", "seed": 4100301, "a_ty": 0.95},
    {"kind": "causal", "seed": 4100302, "a_ty": -1.05},
    {"kind": "causal", "seed": 4100303, "a_ty": 0.85},
    {"kind": "collider", "seed": 4100401, "a_ty": 0.0},
    {"kind": "collider", "seed": 4100402, "a_ty": 0.0},
    {"kind": "blank", "seed": 4100501, "a_ty": 0.0, "logit_shift": 4.0},
    {"kind": "blank", "seed": 4100502, "a_ty": 0.0, "logit_shift": 4.0},
)

HELDOUT_WORLDS = (
    {"kind": "causal", "seed": 5100301, "a_ty": 1.00},
    {"kind": "causal", "seed": 5100302, "a_ty": -0.90},
    {"kind": "collider", "seed": 5100401, "a_ty": 0.0},
    {"kind": "collider", "seed": 5100402, "a_ty": 0.0},
    {"kind": "blank", "seed": 5100501, "a_ty": 0.0, "logit_shift": 4.0},
    {"kind": "blank", "seed": 5100502, "a_ty": 0.0, "logit_shift": 4.0},
)

ROW_KEYS = ("mechanism_score", "correct_refusal", "false_discovery", "sign_correct")


def _evaluate_world(recover_effect, spec, split, index):
    lab = _Lab(spec)
    problem = dict(PUBLIC_PROBLEM)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "budget_used": 0}
    try:
        submission = recover_effect(problem, lab.observe_survivors, lab.intervene)
        has_effect, sign, confidence, abstain = _validate_submission(submission)
        if lab.violated:
            raise RuntimeError("experimental budget exceeded")
        metrics = _metrics(spec, has_effect, sign, abstain)
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_effect": bool(has_effect) and not abstain,
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(
                1.0 - (confidence - metrics["mechanism_score"]) ** 2, 6
            ),
            "budget_used": lab.used,
            "experiment_calls": lab.calls,
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
            "claimed_effect": False,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "budget_used": lab.used,
            "experiment_calls": lab.calls,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] == "causal"]
    unsupported = [r for r in records if r["kind"] in {"collider", "blank"}]
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
        "mean_budget_used": float(np.mean([r["budget_used"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def _evaluate_specs(recover_effect, specs, split, *, reset_before_first=False):
    records = []
    for index, spec in enumerate(specs):
        if (index or reset_before_first) and hasattr(recover_effect, "reset_session"):
            recover_effect.reset_session()
        records.append(_evaluate_world(recover_effect, spec, split, index))
    return records


def evaluate(recover_effect):
    development = _evaluate_specs(recover_effect, DEVELOPMENT_WORLDS, "development")
    heldout = _evaluate_specs(
        recover_effect, HELDOUT_WORLDS, "heldout", reset_before_first=True
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
        "development_mean_budget_used": dev["mean_budget_used"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
