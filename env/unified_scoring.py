"""Opt-in common numerical protocol for the original seven and five frontier worlds.

No hidden family labels or mechanism matching are used. Frozen host panels test
full-output predictions; paired claims test agent-chosen numerical effects. The
bounded exponential scores are indices, not proper scoring rules or depth scores.
"""
import ast
from copy import deepcopy
import math

import numpy as np

from .claim_semantics import claim_eligibility as legacy_eligibility, policy_description
from .frontier_semantics import eligible_target, readout_key
from .unified_panels import evaluation_mask, mask_contract, cell_exclusions
from .registry import FRONTIER_ENVIRONMENTS
from .scoring import canonical_hash

PROTOCOL = "sle-unified-score-1.0"
WEIGHTS = {"conditions": .5, "interventions": .3, "claims": .2}
ERROR_SCALE = .1
CLAIM_SLOTS = 3
CONFIRMATION_REPLICATES = 32

CLAIM_SYSTEM = """Row is zero-based. Static configuration index zero and habitat zero are valid
readouts. Legacy dynamical worlds follow the public claim_eligibility minimum
lags and matching times; frontier readouts follow their public physical selectors.
The interval is a central 90% predictive interval for the mean of 32 independent
fresh noisy treatment-minus-control differences (32 measurements per arm).
References may be blank/empty controls, but at least one arm must be an eligible
nonempty target. Apparatus aliases and reversed contrasts do not create new
claims. Verification tests a numerical effect, not a unique mechanism.
"""


def score_contract():
    return {
        "protocol": PROTOCOL, "weights": dict(WEIGHTS),
        "prediction": "Host-selected, precommitted new-condition and intervention/control-shift panels are evaluated only after predictor freeze against noiseless expected responses. Compute normalized RMSE over all retained cells per experiment; score=100*exp(-RMSE/0.1), then average experiments equally. Do not discard a row merely because its axis is zero.",
        "prediction_cell_exclusions": mask_contract(),
        "claims": "Up to 3 agent-chosen paired quantitative effects. Freeze a central 90% predictive interval for the sample mean of 32 independent noisy treatment-control pairs. Raw interval loss=width+20*distance outside interval; index=100*exp(-loss/(0.1*channel_scale)). Missing or duplicate slots score zero; average exactly 3 slots. The raw interval loss is a proper interval scoring rule; its exponential index is not a proper scoring rule. This is a numerical performance index, not discovery depth.",
        "claim_eligibility": {"legacy_worlds": policy_description(),
            "unified_alias_guards": "Ignore future events after a dynamical readout; keep only the selected heat probe; retain hysteresis knots through the first at or after readout; catalyst reactions key on event counter and the selected identical coupon history without coupon labels. Both publicly assigned arms are ineligible. These explicit aliases are not an exhaustive equivalence solver.",
            "frontier_worlds": "Canonical frontier physical readout keys must differ. At least one arm must be an eligible target (nonblank catalyst event/nonempty phase sample); the other may be a reference. Index zero and habitat zero are permitted. Molecular rows identify prepared geometries; climate uses forcing prefix through endpoint; catalyst uses event history; ecology uses habitat and relevant visits; phase uses angle and preparation. No hidden mechanism is inspected."},
        "claim_evidence": "Prior observation IDs and a scope statement are required; scientific relevance requires evidence review.",
        "verified_effect": "A nonduplicate eligible claim whose fresh sample mean is inside its interval, interval width<=0.2*channel_scale, and absolute mean>max(3 estimated standard errors,1e-12). This is a descriptive replicated-effect endpoint, not a multiplicity-adjusted hypothesis test or mechanism certificate.",
        "baseline": "Truth-blind environment-specific baselines receive the same public exploration data and are evaluated using identical panels and masks.",
        "failure": "Healthy runs without a valid frozen predictor score zero. Infrastructure failures are excluded from model-only scores and retained in end-to-end accounting.",
        "aggregation": "Average runs within each environment, then average environments equally; uncertainty must cluster repeated runs by independent world instance. Environment difficulty and physical experimental cost are not made equal by score normalization."
    }


def _arm_key(world, spec, readout):
    row, channel = readout["row"], readout["channel"]
    if world.name == "catalyst_aging":
        index = spec["event_indices"][row]
        event = spec["events"][index-1]
        if event["kind"] in ("blank", "standard"):
            controls = {"event_index": index, "calibration_kind": event["kind"]}
        else:
            # Coupons are publicly identical and age only through their own
            # reactions; unrelated events affect the instrument counter only.
            controls = {"event_index": index, "reaction_history": [
                {key: value for key, value in past.items() if key != "coupon_id"}
                for past in spec["events"][:index]
                if past["kind"] == "reaction" and past["coupon_id"] == event["coupon_id"]]}
        return {"environment": world.name, "channel": channel, "controls": controls}
    if world.name in FRONTIER_ENVIRONMENTS:
        return readout_key(world.name, spec, row, channel)
    coordinate = spec[world.axis_field][row]
    controls = deepcopy({k: v for k, v in spec.items() if k != world.axis_field})
    events = {"microecology": ("events", "time_h"),
              "reaction_kinetics": ("interventions", "time_s"),
              "gene_regulation": ("interventions", "time_h")}.get(world.name)
    if events:
        field, time_field = events
        controls[field] = [event for event in controls.get(field, []) if event[time_field] <= coordinate]
    if world.name == "heat_transport":
        controls["probes"] = [spec["probes"][world.channels.index(channel)]]
        channel = "temperature"  # Probe labels do not define different quantities.
    if world.name == "hysteresis_material":
        # Keep the first following knot: it sets the slope before the readout.
        prefix = []
        for knot in controls["protocol"]:
            prefix.append(knot)
            if knot["time"] >= coordinate:
                break
        controls["protocol"] = prefix
    return {"environment": world.name, "channel": channel,
            "controls": controls, "coordinate": coordinate}


def claim_eligibility(world, control, treatment, readout):
    if world.name not in FRONTIER_ENVIRONMENTS:
        result = legacy_eligibility(world.name, control, treatment, readout, world.axis_field)
        if not result["eligible"]:
            return result
    else:
        valid = [eligible_target(world.name, spec, readout["row"], readout["channel"])
                 for spec in (control, treatment)]
        if not any(valid):
            return {"eligible": False, "reason": "empty_apparatus_targets_only"}
    if world.name not in FRONTIER_ENVIRONMENTS:
        reasons = []
        for spec in (control, treatment):
            layout = {"axis": spec[world.axis_field], "channels": list(world.channels)}
            reasons.append(cell_exclusions(world.name, spec, layout)[readout["row"]][world.channels.index(readout["channel"])])
        known_reasons = {"prescribed_initial_state", "zero_inoculum_strain", "complete_fraction_depletion",
                         "oscillator_clamp", "spin_clamped_constant"}
        if all(reason in known_reasons for reason in reasons):
            return {"eligible": False, "reason": "both_arms_publicly_assigned"}
    if canonical_hash(_arm_key(world, control, readout)) == canonical_hash(_arm_key(world, treatment, readout)):
        return {"eligible": False, "reason": "identical_physical_readout_controls"}
    return {"eligible": True, "reason": "passes_public_semantics_only"}


def validate_submission(value, world, records):
    if not isinstance(value, dict) or set(value) != {"predictor_code", "claims", "explanation"}:
        raise ValueError("submit requires exactly predictor_code, claims, explanation")
    for key, limit in (("predictor_code", 64000), ("explanation", 16000)):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= limit:
            raise ValueError("invalid " + key)
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
            raise ValueError("invalid claim fields")
        for key in ("id", "statement", "scope"):
            if not isinstance(claim[key], str) or not 1 <= len(claim[key]) <= (100 if key == "id" else 4000):
                raise ValueError("invalid claim " + key)
        if claim["id"] in ids:
            raise ValueError("duplicate claim id")
        ids.add(claim["id"])
        control, treatment = world.validate(claim["control"]), world.validate(claim["treatment"])
        readout = claim["readout"]
        if (not isinstance(readout, dict) or set(readout) != {"row", "channel"} or
                type(readout["row"]) is not int or readout["row"] < 0 or
                not isinstance(readout["channel"], str) or readout["channel"] not in world.channels):
            raise ValueError("readout requires nonnegative integer row and public channel name")
        if any(readout["row"] >= len(spec[world.axis_field]) for spec in (control, treatment)):
            raise ValueError("readout row outside public axis")
        eligibility = claim_eligibility(world, control, treatment, readout)
        if not eligibility["eligible"]:
            raise ValueError("claim is ineligible: " + eligibility["reason"])
        interval = claim["interval"]
        limit = 1e6 * world.scales[world.channels.index(readout["channel"])]
        if (not isinstance(interval, list) or len(interval) != 2 or
                any(isinstance(x, bool) or not isinstance(x, (int, float)) or not -limit <= x <= limit for x in interval)
                or interval[0] > interval[1]):
            raise ValueError("interval needs finite ordered bounded endpoints")
        evidence = claim["evidence_ids"]
        if (not isinstance(evidence, list) or not 1 <= len(evidence) <= 48 or
                any(not isinstance(x, str) or x not in known for x in evidence)):
            raise ValueError("evidence_ids must cite existing observations")
        canonical.append(dict(deepcopy(claim), control=control, treatment=treatment,
                              interval=[float(x) for x in interval]))
    return dict(value, claims=canonical)


def prediction_metrics(predicted, observed, scales, *, world, spec):
    target, pred = np.asarray(observed["values"], dtype=float), np.asarray(predicted, dtype=float)
    if (pred.shape != target.shape or pred.ndim != 2 or not np.isfinite(pred).all()
            or np.any(np.abs(pred) > 1e12)):
        raise ValueError("predictor returned invalid shape or nonfinite/unbounded values")
    keep = evaluation_mask(world.name, spec, observed)
    if keep.shape != target.shape or not keep.any():
        raise ValueError("host panel has no scoreable cells or an invalid public shape")
    error = (pred-target) / np.asarray(scales)
    nrmse = float(np.sqrt(np.mean(error[keep] ** 2)))
    per_channel = [float(np.sqrt(np.mean(error[keep[:, j], j] ** 2))) if keep[:, j].any() else None
                   for j in range(pred.shape[1])]
    return {"normalized_rmse": nrmse, "channel_normalized_rmse": per_channel,
            "score": 100*math.exp(-nrmse/ERROR_SCALE), "scored_rows": int(keep.any(axis=1).sum()),
            "scored_cells": int(keep.sum()), "excluded_cells": int((~keep).sum()),
            "scored_cell_mask": keep.tolist(), "mask_protocol": mask_contract()["protocol"],
            "cell_exclusion_reasons": cell_exclusions(world.name, spec, observed)}


def verify_claims(world, claims, confirmation_key):
    reports, seen = [], set()
    for index, claim in enumerate(claims):
        eligibility = claim_eligibility(world, claim["control"], claim["treatment"], claim["readout"])
        arms = [canonical_hash(_arm_key(world, claim[arm], claim["readout"])) for arm in ("control", "treatment")]
        signature = canonical_hash(sorted(arms))
        duplicate = signature in seen
        seen.add(signature)
        channel, row = world.channels.index(claim["readout"]["channel"]), claim["readout"]["row"]
        arm_values = {"control": [], "treatment": []}
        for replica in range(CONFIRMATION_REPLICATES):
            for arm in ("control", "treatment"):
                # Hash length is fixed even for a long operator confirmation key.
                key = canonical_hash([PROTOCOL, confirmation_key, index, arm, replica])
                arm_values[arm].append(float(world.run(claim[arm], noise_key=key)["values"][row][channel]))
        differences = np.asarray(arm_values["treatment"])-np.asarray(arm_values["control"])
        mean = float(differences.mean())
        se = float(differences.std(ddof=1)/math.sqrt(CONFIRMATION_REPLICATES))
        lower, upper = claim["interval"]
        width = upper-lower
        interval_score = width+20*max(lower-mean, mean-upper, 0)
        scale = world.scales[channel]
        score = 0. if duplicate or not eligibility["eligible"] else 100*math.exp(-interval_score/(ERROR_SCALE*scale))
        covered = lower <= mean <= upper
        nonzero = abs(mean) > max(3*se, 1e-12)
        reports.append({"id": claim["id"], "statement": claim["statement"], "scope": claim["scope"],
                        "evidence_ids": claim["evidence_ids"], "interval": [lower, upper],
                        "mean_difference": mean, "standard_error": se, "replicates": CONFIRMATION_REPLICATES,
                        "interval_score": interval_score, "normalized_interval_score": interval_score/scale,
                        "replicate_differences": differences.tolist(), "replicate_arm_values": arm_values,
                        "score": score, "covered": covered, "duplicate": duplicate, "eligibility": eligibility,
                        "physical_contrast_sha256": signature,
                        "verified_nonzero_effect": bool(eligibility["eligible"] and not duplicate and covered and width <= .2*scale and nonzero),
                        "mechanism_certified": False})
    return {"protocol": PROTOCOL, "score": sum(r["score"] for r in reports)/CLAIM_SLOTS,
            "verified_nonzero_effects": sum(r["verified_nonzero_effect"] for r in reports), "claims": reports}


def aggregate_episode(panel_reports, claim_report):
    parts = {kind: float(np.mean([r["score"] for r in panel_reports[kind]]))
             for kind in ("conditions", "interventions")}
    parts["claims"] = claim_report["score"]
    return {"protocol": PROTOCOL, "subscores": parts,
            "score": sum(WEIGHTS[k]*parts[k] for k in WEIGHTS)}
