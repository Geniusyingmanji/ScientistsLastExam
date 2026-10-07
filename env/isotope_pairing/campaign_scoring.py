"""Explicit isotope numerical scoring adapter; not yet enabled in model driver.

Independent version: frozen V1 protocol remains unchanged. Numeric effects do
not establish a mechanism. Selection requires a separate driver admission gate.
"""
import ast
from copy import deepcopy
import math
import numpy as np
from env.scoring import canonical_hash
from .eligibility import validate_spec, contrast_eligibility, prediction_mask
from .metrics import experiment_error

PROTOCOL = "isotope-batch-score-1.0"
WEIGHTS = {"conditions": .5, "interventions": .3, "claims": .2}
ERROR_SCALE = .1
CLAIM_SLOTS = 3
CONFIRMATION_REPLICATES = 32
CLAIM_SYSTEM = """Row is zero-based and must have positive time. Treatment and control
readouts must have the same time. A recipe change at or after that time cannot
change that readout. Freeze a central90% interval for the mean of32 independent
fresh treatment-control differences. Reversed and redundant history contrasts
are duplicates. Evidence IDs must refer to earlier observations. No mechanism
label or positive result is required."""


def score_contract():
    return {"protocol": PROTOCOL, "weights":dict(WEIGHTS),
        "prediction":"Separate fresh-recipe and pulse/chase panels; exclude t=0; scales1. Per experiment100*exp(-RMSE/.1), average experiments equally.",
        "claims":"Three slots,32 independent noisy pairs each. IS=width+20*distance outside interval;100*exp(-IS/.1). Missing, ineligible or duplicate slots zero.",
        "scope":"Development numerical prediction/effect index, not mechanism or discovery depth. Independent-position recipes can remain nonidentifiable."}


def _arm_key(world, spec, readout):
    s=validate_spec(spec);t=s['times'][readout['row']];history=[]
    for segment in s['source']:
        if segment['at']>=t:break
        if not history or history[-1]['fractions']!=segment['fractions']:
            history.append(segment)
    return {'channel':readout['channel'],'time':t,'history':history}


def claim_eligibility(world,control,treatment,readout):
    return contrast_eligibility(control,treatment,readout['row'],readout['channel'])


def prediction_metrics(predicted,observed,scales,*,world,spec):
    if world.name!='isotope_pairing' or tuple(scales)!=(1.,1.,1.):
        raise ValueError('isotope metric requires its explicit world and scales')
    r=experiment_error(spec,predicted,observed['values'])
    if r['status']!='scored':raise ValueError('no unassigned prediction cells')
    return {'normalized_rmse':r['rmse'],'score':100*math.exp(-r['rmse']/.1),
        'scored_cells':r['cells'],'mask_protocol':PROTOCOL}

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


def generate_panel(world, seed, kind, count=8):
    if world.name != 'isotope_pairing':
        raise ValueError('isotope adapter world mismatch')
    return world.panel(seed, kind, count)


def public_panel_domain(environment):
    if environment != 'isotope_pairing':
        raise ValueError('isotope adapter world mismatch')
    return {'protocol': PROTOCOL, 'conditions': 'Fresh constant source recipes across the legal simplex, observed over0..12.',
            'interventions': 'Fresh source recipe followed by an unlabeled chase at3; observed over0..12.',
            'scope': 'Prediction transfer within these domains, not unique mechanism identification.'}
