"""Trusted real-DNS oracle for RANSCalibration, version 2.

Candidates return one interpretable algebraic eddy-viscosity closure.  The
trusted oracle solves channel mean momentum and compares velocity plus Reynolds
shear with independently simulated, CC-BY-4.0 DNS statistics.  Development,
held-out Reynolds numbers, coordinate perturbations and physics diagnostics stay
separate so a fit cannot be mistaken for universal turbulence closure.
"""

from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import numpy as np

VERIFICATION_DIR = Path(__file__).resolve().parent
if str(VERIFICATION_DIR) not in sys.path:
    sys.path.insert(0, str(VERIFICATION_DIR))
from closure_model import (
    PARAMETER_BOUNDS,
    PARAMETER_NAMES,
    STANDARD_PARAMETERS,
    closure_profiles,
    validate_parameters,
)


RANS_CALIBRATION_V2 = True
TASK_DIR = VERIFICATION_DIR.parent
DATA_PATH = VERIFICATION_DIR / "channel_dns_profiles_v1.json"
DEVELOPMENT_RE_TAU = (180, 395)
HELDOUT_RE_TAU = (590, 950)
SHIFT_FACTORS = (-0.025, 0.025)
NOMINAL_REFERENCE_PARAMETERS = np.asarray(
    (0.48663474137035673, 35.262103882288415,
     0.63124557167500384, -1.2612246455851348), dtype=float
)
ROBUST_REFERENCE_PARAMETERS = np.asarray(
    (0.52555341575918113, 38.874892487453089,
     0.38132393568562051, -0.86880133741023535), dtype=float
)
# Evaluator-only witnesses define held-out normalization scales.  They are
# never returned to the candidate or used to choose its artifact.
HELDOUT_NOMINAL_REFERENCE_PARAMETERS = np.asarray(
    (0.42321430249318076, 28.444608523496189,
     0.88105232038884596, -1.5453726214102792), dtype=float
)
HELDOUT_ROBUST_REFERENCE_PARAMETERS = np.asarray(
    (0.40703896837198661, 27.389843390864929,
     1.1335411937446844, -1.8349733571943241), dtype=float
)
REFERENCE_PARAMETERS = NOMINAL_REFERENCE_PARAMETERS
VELOCITY_SCALE = 0.30
SHEAR_SCALE = 0.05
DATA_SHA256 = "0f70ce507fa65175f044538b41a266d42347cdf9c1bf2e7fafd8f630f47ed9bf"


def _load_profiles():
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise ValueError("DNS aggregate hash differs from task contract")
    document = json.loads(payload.decode("utf-8"))
    if not (
        document.get("schema_version") == 1
        and document.get("source", {}).get("doi")
        == "10.5281/zenodo.5749302"
        and document.get("source", {}).get("license") == "CC-BY-4.0"
    ):
        raise ValueError("unexpected DNS data manifest")
    records = {}
    for key, row in document["profiles"].items():
        re_tau = int(key)
        y_plus = np.asarray(row["y_plus"], dtype=float)
        mean_u_plus = np.asarray(row["mean_u_plus"], dtype=float)
        uv_plus = np.asarray(row["uv_plus"], dtype=float)
        if not (
            row["re_tau"] == re_tau
            and len(y_plus) == len(mean_u_plus) == len(uv_plus)
            and len(y_plus) >= 180
            and np.all(np.isfinite(y_plus))
            and np.all(np.isfinite(mean_u_plus))
            and np.all(np.isfinite(uv_plus))
            and np.all(np.diff(y_plus) > 0.0)
            and y_plus[-1] < re_tau
        ):
            raise ValueError("invalid DNS profile")
        records[re_tau] = {
            "y_plus": y_plus,
            "mean_u_plus": mean_u_plus,
            # The archive stores <u'v'>; the modeled positive turbulent shear
            # is -<u'v'> on the lower channel half.
            "reynolds_shear_plus": -uv_plus,
        }
    if set(records) != set(DEVELOPMENT_RE_TAU + HELDOUT_RE_TAU):
        raise ValueError("DNS Reynolds-number set differs from task contract")
    return document["source"], records


DATA_SOURCE, DNS_PROFILES = _load_profiles()


def _sample_indices(y_plus):
    inner_stop = min(120.0, float(y_plus[-1]))
    targets = np.concatenate((
        np.geomspace(max(float(y_plus[0]), 0.5), inner_stop, 36),
        np.linspace(inner_stop, float(y_plus[-1]), 32),
    ))
    return np.unique([
        int(np.argmin(np.abs(y_plus - target))) for target in targets
    ])


SAMPLE_INDICES = {
    re_tau: _sample_indices(row["y_plus"])
    for re_tau, row in DNS_PROFILES.items()
}


def _profile_metrics(parameters, re_tau, eta_scale=1.0):
    row = DNS_PROFILES[int(re_tau)]
    # ``eta_scale`` models a bounded friction-velocity / wall-coordinate
    # calibration perturbation.  Both y+ and Re_tau scale together, so the
    # physical outer coordinate y/h remains inside the measured half-channel.
    # Scaling only Re_tau would move the last DNS point outside the channel for
    # one sign of the perturbation and incorrectly turn an evaluator shift into
    # a candidate failure.
    y_plus = row["y_plus"] * float(eta_scale)
    shifted_re_tau = float(re_tau) * float(eta_scale)
    mean_u, mean_shear, reynolds_shear = closure_profiles(
        parameters, shifted_re_tau, y_plus,
    )
    indices = SAMPLE_INDICES[int(re_tau)]
    velocity_rmse = float(np.sqrt(np.mean(
        (mean_u[indices] - row["mean_u_plus"][indices]) ** 2
    )))
    shear_rmse = float(np.sqrt(np.mean(
        (
            reynolds_shear[indices]
            - row["reynolds_shear_plus"][indices]
        ) ** 2
    )))
    total_shear = mean_shear + reynolds_shear
    expected_total_shear = 1.0 - y_plus / shifted_re_tau
    momentum_residual = float(np.max(np.abs(
        total_shear - expected_total_shear
    )))
    raw_loss = (
        0.75 * velocity_rmse / VELOCITY_SCALE
        + 0.25 * shear_rmse / SHEAR_SCALE
    )
    return {
        "re_tau": int(re_tau),
        "eta_scale": float(eta_scale),
        "velocity_rmse_plus": velocity_rmse,
        "reynolds_shear_rmse_plus": shear_rmse,
        "raw_loss": float(raw_loss),
        "momentum_residual": momentum_residual,
        "minimum_eddy_shear_plus": float(np.min(reynolds_shear)),
        "minimum_mean_shear_plus": float(np.min(mean_shear)),
        "maximum_mean_u_plus": float(np.max(mean_u)),
        "sample_count": int(len(indices)),
    }


def _split_rows(parameters, re_values, include_shifts):
    nominal = [_profile_metrics(parameters, re_tau) for re_tau in re_values]
    shifted = []
    if include_shifts:
        for re_tau in re_values:
            shifted.append({
                "re_tau": int(re_tau),
                "conditions": [
                    _profile_metrics(parameters, re_tau, 1.0 + shift)
                    for shift in SHIFT_FACTORS
                ],
            })
    return nominal, shifted


def _mean_loss(rows):
    return float(np.mean([row["raw_loss"] for row in rows]))


def _worst_shift_loss(nominal, shifted):
    return float(max(
        [row["raw_loss"] for row in nominal]
        + [
            condition["raw_loss"]
            for row in shifted for condition in row["conditions"]
        ]
    ))


BASELINE_ROWS = {
    "development": _split_rows(
        STANDARD_PARAMETERS, DEVELOPMENT_RE_TAU, False
    )[0],
    "heldout": _split_rows(STANDARD_PARAMETERS, HELDOUT_RE_TAU, False)[0],
}
NOMINAL_REFERENCE_ROWS = {
    "development": _split_rows(
        NOMINAL_REFERENCE_PARAMETERS, DEVELOPMENT_RE_TAU, False
    )[0],
    "heldout": _split_rows(
        HELDOUT_NOMINAL_REFERENCE_PARAMETERS, HELDOUT_RE_TAU, False
    )[0],
}
BASELINE_SHIFT_ROWS = {
    "development": _split_rows(
        STANDARD_PARAMETERS, DEVELOPMENT_RE_TAU, True
    )[1],
    "heldout": _split_rows(STANDARD_PARAMETERS, HELDOUT_RE_TAU, True)[1],
}
ROBUST_REFERENCE_ROWS = {}
ROBUST_REFERENCE_SHIFT_ROWS = {}
for _split, _re_values in (
    ("development", DEVELOPMENT_RE_TAU),
    ("heldout", HELDOUT_RE_TAU),
):
    _parameters = (
        ROBUST_REFERENCE_PARAMETERS if _split == "development"
        else HELDOUT_ROBUST_REFERENCE_PARAMETERS
    )
    (_nominal_rows, _shift_rows) = _split_rows(
        _parameters, _re_values, True
    )
    ROBUST_REFERENCE_ROWS[_split] = _nominal_rows
    ROBUST_REFERENCE_SHIFT_ROWS[_split] = _shift_rows

LOSS_ANCHORS = {
    split: {
        "nominal_baseline": _mean_loss(BASELINE_ROWS[split]),
        "nominal_reference": _mean_loss(NOMINAL_REFERENCE_ROWS[split]),
        "robust_baseline": _worst_shift_loss(
            BASELINE_ROWS[split], BASELINE_SHIFT_ROWS[split]
        ),
        "robust_reference": _worst_shift_loss(
            ROBUST_REFERENCE_ROWS[split],
            ROBUST_REFERENCE_SHIFT_ROWS[split],
        ),
    }
    for split in ("development", "heldout")
}


def _normalized_score(loss, split, objective):
    anchors = LOSS_ANCHORS[split]
    baseline = anchors[objective + "_baseline"]
    reference = anchors[objective + "_reference"]
    denominator = baseline - reference
    if denominator <= 0.0:
        raise ValueError("invalid normalization anchors")
    return float(np.clip(
        (baseline - float(loss)) / denominator,
        0.0, 1.0,
    ))


def _result_failure(kind):
    return {
        "combined_score": 0.0,
        "valid": 0.0,
        "feasibility_rate": 0.0,
        "raw_score": 0.0,
        "robustness_score": 0.0,
        "heldout_policy_score": 0.0,
        "heldout_robustness_score": 0.0,
        "heldout_feasibility_rate": 0.0,
        "candidate_failure_kind": kind,
        "error_message": "candidate invalid: " + kind,
    }


def evaluate(calibrate_rans):
    try:
        parameters = validate_parameters(calibrate_rans())
    except Exception:
        return _result_failure("candidate_return_contract_error")
    try:
        development, development_shifts = _split_rows(
            parameters, DEVELOPMENT_RE_TAU, True
        )
        heldout, heldout_shifts = _split_rows(
            parameters, HELDOUT_RE_TAU, True
        )
    except Exception:
        return _result_failure("candidate_closure_evaluation_error")

    all_nominal = development + heldout
    all_shift_conditions = [
        condition
        for row in development_shifts + heldout_shifts
        for condition in row["conditions"]
    ]
    all_conditions = all_nominal + all_shift_conditions
    physical = bool(
        all(row["momentum_residual"] <= 1.0e-12 for row in all_conditions)
        and all(row["minimum_eddy_shear_plus"] >= -1.0e-12 for row in all_conditions)
        and all(row["minimum_mean_shear_plus"] >= -1.0e-12 for row in all_conditions)
        and all(row["maximum_mean_u_plus"] <= 40.0 for row in all_conditions)
    )
    if not physical:
        return _result_failure("candidate_physics_gate_failure")

    development_loss = _mean_loss(development)
    heldout_loss = _mean_loss(heldout)
    development_shift_loss = _worst_shift_loss(
        development, development_shifts
    )
    heldout_shift_loss = _worst_shift_loss(
        heldout, heldout_shifts
    )
    development_score = _normalized_score(
        development_loss, "development", "nominal"
    )
    heldout_score = _normalized_score(
        heldout_loss, "heldout", "nominal"
    )
    development_robustness = _normalized_score(
        development_shift_loss, "development", "robust"
    )
    heldout_robustness = _normalized_score(
        heldout_shift_loss, "heldout", "robust"
    )
    return {
        "combined_score": development_score,
        "valid": 1.0,
        "feasibility_rate": 1.0,
        "raw_score": development_score,
        "robustness_score": development_robustness,
        "heldout_policy_score": heldout_score,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": 1.0,
        "development_raw_loss": development_loss,
        "heldout_raw_loss": heldout_loss,
        "development_worst_shift_loss": development_shift_loss,
        "heldout_worst_shift_loss": heldout_shift_loss,
        "development_velocity_rmse_plus": float(np.mean([
            row["velocity_rmse_plus"] for row in development
        ])),
        "heldout_velocity_rmse_plus": float(np.mean([
            row["velocity_rmse_plus"] for row in heldout
        ])),
        "development_reynolds_shear_rmse_plus": float(np.mean([
            row["reynolds_shear_rmse_plus"] for row in development
        ])),
        "heldout_reynolds_shear_rmse_plus": float(np.mean([
            row["reynolds_shear_rmse_plus"] for row in heldout
        ])),
        "candidate_parameter_count": 4,
        "candidate_parameter_vector": [float(value) for value in parameters],
        "physics_gate_passed": True,
        "loss_anchors": LOSS_ANCHORS,
        "per_condition": development + heldout,
        "shift_conditions": development_shifts + heldout_shifts,
        "data_source_doi": DATA_SOURCE["doi"],
        "data_source_license": DATA_SOURCE["license"],
    }


def standard_closure():
    return dict(zip(PARAMETER_NAMES, STANDARD_PARAMETERS))


def reference_closure():
    return dict(zip(PARAMETER_NAMES, NOMINAL_REFERENCE_PARAMETERS))


def robust_reference_closure():
    return dict(zip(PARAMETER_NAMES, ROBUST_REFERENCE_PARAMETERS))
