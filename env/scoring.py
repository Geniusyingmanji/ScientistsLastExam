"""Frozen-output verification against simulations, not a list of golden discoveries."""
import hashlib
import json
import math

import numpy as np
from .claim_semantics import claim_eligibility, policy_description

PROTOCOL = "sle-pilot-score-0.3"
WEIGHTS = {"conditions": .5, "interventions": .3, "claims": .2}
ERROR_SCALE = .1
CLAIM_SLOTS = 3
CONFIRMATION_REPLICATES = 8


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def score_contract():
    return {
        "protocol": PROTOCOL, "weights": WEIGHTS,
        "claim_eligibility": policy_description(),
        "prediction": "For each held-out experiment compute RMSE after dividing channels by public scales. Exclude t=0 when there are other times. Score = 100*exp(-RMSE/0.1); average experiments equally, then apply weights.",
        "claims": "Up to 3 agent-chosen paired quantitative effects. Freeze a central 90% interval for the mean of 8 independent noisy treatment-control differences. Interval score = width + 20*distance outside interval. Slot score = 100*exp(-interval_score/(0.1*channel_scale)). Missing or duplicated slots score zero; average over exactly 3 slots.",
        "claim_evidence": "Cite prior observation IDs and describe scope. Citation presence is checked automatically; its scientific relevance and any mechanism explanation require evidence review.",
        "verified_effect": "A nonduplicated claim whose fresh mean is in its interval, interval width <=0.2*scale, and absolute mean exceeds 3 standard errors. This operational endpoint measures a replicated numerical effect, not discovery of a mechanism. Null effects still receive proper interval scores but are not counted as verified nonzero effects.",
        "baseline": "The same public exploration records feed an environment-specific, truth-blind baseline; raw errors and score differences are reported alongside absolute scores.",
        "failure": "Healthy runs without a valid frozen predictor get score 0. Infrastructure failures are excluded from the model-only denominator and included in end-to-end accounting."
    }


def validate_submission(value, world, records):
    if not isinstance(value, dict) or set(value) != {"predictor_code", "claims", "explanation"}:
        raise ValueError("submit requires exactly predictor_code, claims, explanation")
    if not isinstance(value["predictor_code"], str) or not 1 <= len(value["predictor_code"]) <= 64000:
        raise ValueError("predictor_code must be 1..64000 characters defining predict(spec)")
    if not isinstance(value["explanation"], str) or not 1 <= len(value["explanation"]) <= 16000:
        raise ValueError("explanation must be 1..16000 characters")
    import ast
    try:
        ast.parse(value["predictor_code"])
    except (SyntaxError, RecursionError, MemoryError):
        raise ValueError("predictor_code has invalid Python syntax") from None
    claims = value["claims"]
    if not isinstance(claims, list) or len(claims) > CLAIM_SLOTS:
        raise ValueError("claims must have 0..3 entries")
    known = {r["id"] for r in records}
    canonical, ids = [], set()
    for claim in claims:
        required = {"id", "statement", "control", "treatment", "readout", "interval", "evidence_ids", "scope"}
        if not isinstance(claim, dict) or set(claim) != required:
            raise ValueError("claim fields must be id, statement, control, treatment, readout, interval, evidence_ids, scope")
        for field in ("id", "statement", "scope"):
            if not isinstance(claim[field], str) or not 1 <= len(claim[field]) <= (100 if field == "id" else 4000):
                raise ValueError("invalid claim " + field)
        if claim["id"] in ids:
            raise ValueError("duplicate claim id")
        ids.add(claim["id"])
        control, treatment = world.validate(claim["control"]), world.validate(claim["treatment"])
        if canonical_hash(control) == canonical_hash(treatment):
            raise ValueError("claim control and treatment must differ")
        readout = claim["readout"]
        if not isinstance(readout, dict) or set(readout) != {"row", "channel"} or type(readout["row"]) is not int or readout["row"] < 0 or readout["channel"] not in world.channels:
            raise ValueError("readout requires nonnegative integer row and public channel name")
        # Read public coordinates, never call the hidden simulator for validation.
        for spec in (control, treatment):
            axis = spec[world.axis_field]
            if readout["row"] >= len(axis) or axis[readout["row"]] == 0:
                raise ValueError("claim row must be a valid post-initial observation")
        eligibility = claim_eligibility(world.name, control, treatment, readout, world.axis_field)
        if not eligibility["eligible"]:
            raise ValueError("claim is ineligible: " + eligibility["reason"])
        interval = claim["interval"]
        endpoint_limit = 1e6 * world.scales[world.channels.index(readout["channel"])]
        if not isinstance(interval, list) or len(interval) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not -endpoint_limit <= x <= endpoint_limit or not math.isfinite(x) for x in interval) or interval[0] > interval[1]:
            raise ValueError("interval needs finite ordered lower and upper limits")
        evidence = claim["evidence_ids"]
        if not isinstance(evidence, list) or not evidence or len(evidence) > 48 or any(not isinstance(x, str) or x not in known for x in evidence):
            raise ValueError("evidence_ids must cite existing observations")
        canonical.append(dict(claim, control=control, treatment=treatment, interval=[float(x) for x in interval]))
    return dict(value, claims=canonical)


def prediction_metrics(predicted, observed, scales):
    target = np.asarray(observed["values"], dtype=float)
    pred = np.asarray(predicted, dtype=float)
    if pred.shape != target.shape or pred.ndim != 2 or not np.isfinite(pred).all() or np.any(np.abs(pred) > 1e12):
        raise ValueError("predictor returned invalid shape or nonfinite/unbounded values")
    keep = np.ones(len(target), dtype=bool)
    if len(target) > 1 and observed["axis"][0] == 0:
        keep[0] = False
    error = (pred[keep] - target[keep]) / np.asarray(scales)
    nrmse = float(np.sqrt(np.mean(error ** 2)))
    channel_rmse = np.sqrt(np.mean(error ** 2, axis=0)).tolist()
    return {"normalized_rmse": nrmse, "channel_normalized_rmse": channel_rmse,
            "score": 100 * math.exp(-nrmse / ERROR_SCALE), "scored_rows": int(sum(keep))}


def verify_claims(world, claims, confirmation_key):
    reports, seen = [], set()
    for index, claim in enumerate(claims):
        eligibility = claim_eligibility(world.name, claim["control"], claim["treatment"], claim["readout"], world.axis_field)
        arms = []
        for arm in ("control", "treatment"):
            spec = world.validate(claim[arm])
            controls = {k: v for k, v in spec.items() if k != world.axis_field}
            arms.append(canonical_hash({"controls": controls, "coordinate": spec[world.axis_field][claim["readout"]["row"]]}))
        signature = canonical_hash({"pair": sorted(arms), "channel": claim["readout"]["channel"]})
        duplicate = signature in seen
        seen.add(signature)
        channel = world.channels.index(claim["readout"]["channel"])
        row = claim["readout"]["row"]
        differences = []
        for replica in range(CONFIRMATION_REPLICATES):
            values = []
            for arm in ("control", "treatment"):
                key = "%s:claim:%d:%s:%d" % (confirmation_key, index, arm, replica)
                values.append(world.run(claim[arm], noise_key=key)["values"][row][channel])
            differences.append(values[1] - values[0])
        mean = float(np.mean(differences))
        se = float(np.std(differences, ddof=1) / np.sqrt(CONFIRMATION_REPLICATES))
        lower, upper = claim["interval"]
        width = upper - lower
        interval_score = width + 20 * max(lower-mean, mean-upper, 0)
        scale = world.scales[channel]
        score = 0. if duplicate or not eligibility["eligible"] else 100 * math.exp(-interval_score / (ERROR_SCALE * scale))
        covered = lower <= mean <= upper
        nonzero = abs(mean) > max(3*se, 1e-12)
        reports.append({"id": claim["id"], "statement": claim["statement"], "scope": claim["scope"],
                        "evidence_ids": claim["evidence_ids"], "interval": [lower, upper], "mean_difference": mean,
                        "standard_error": se, "replicates": CONFIRMATION_REPLICATES, "interval_score": interval_score,
                        "score": score, "covered": covered, "duplicate": duplicate, "eligibility": eligibility,
                        "verified_nonzero_effect": bool(eligibility["eligible"] and not duplicate and covered and width <= .2*scale and nonzero),
                        "mechanism_certified": False})
    return {"score": sum(r["score"] for r in reports) / CLAIM_SLOTS,
            "verified_nonzero_effects": sum(r["verified_nonzero_effect"] for r in reports), "claims": reports}


def aggregate_episode(panel_reports, claim_report):
    parts = {kind: float(np.mean([r["score"] for r in panel_reports[kind]])) for kind in ("conditions", "interventions")}
    parts["claims"] = claim_report["score"]
    return {"protocol": PROTOCOL, "subscores": parts,
            "score": sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)}
