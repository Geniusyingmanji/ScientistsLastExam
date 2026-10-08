"""Capacity-only frozen adapter derived from history1.1; old cohorts unchanged."""
import ast
from copy import deepcopy
import math
import numpy as np
from env.scoring import canonical_hash


PROTOCOL = "capacity-batch-score-1.0"
# Keep confirmation sampling stable across documentation-only revisions.
CONFIRMATION_NOISE_NAMESPACE = "capacity-batch-score-1.0"
WEIGHTS = {"conditions": .5, "interventions": .3, "claims": .2}
ERROR_SCALE = .1
CLAIM_SLOTS = 3
CONFIRMATION_REPLICATES = 32
CLAIM_SYSTEM = """Row is zero-based and must have positive time. Treatment and control
readouts must have the same time. A continuous-history control change at or after that time cannot
change that readout. All interval endpoints use the public observable units; claim scores normalize by its public channel scale. Freeze a central90% interval for the mean of32 independent
fresh treatment-control differences. Reversed and redundant history contrasts
are duplicates. Evidence IDs must refer to earlier observations. No mechanism
label or positive result is required."""


def score_contract():
    return {"protocol": PROTOCOL, "weights":dict(WEIGHTS),
        "prediction":"Separate condition and intervention panels; exclude assigned zero prefixes; public channel scales. Per experiment100*exp(-RMSE/.1), average experiments equally.",
        "claims":"Three slots,32 independent noisy pairs each. IS=width+20*distance outside interval;100*exp(-IS/(.1*public_channel_scale)). Missing, ineligible or duplicate slots zero.",
        "scope":"Development numerical prediction/effect index, not mechanism or discovery depth. Restricted histories can remain nonidentifiable."}


SUPPORTED = {'retention_capacity'}


def _check(world):
    if world.name not in SUPPORTED:
        raise ValueError('explicit history world required')


def _arm_key(world, spec, readout):
    _check(world)
    s=world.validate(spec); t=s['times'][readout['row']]
    field, value = ('stimulus','level') if world.name=='adaptive_signaling' else ('flow','rate')
    history=[]
    for seg in s[field]:
        if seg['at']>=t: break
        if not history or history[-1][value]!=seg[value]: history.append(seg)
    result={'channel':readout['channel'],'time':t,'history':history,'load':s['load']}
    if world.name=='adaptive_signaling':
        reset=s['reset_at']
        excited=any(seg['at']<reset and seg['level']>0 for seg in s['stimulus'])
        if 0<reset<t and s['retained_fraction']<1 and excited:
            result['reset']=[reset,s['retained_fraction']]
    return result


def _unassigned(world,spec,t):
    field,value=('stimulus','level') if world.name=='adaptive_signaling' else ('flow','rate')
    return t>0 and any(x['at']<t and x[value]>0 for x in spec[field])


def claim_eligibility(world,control,treatment,readout):
    _check(world)
    a,b=world.validate(control),world.validate(treatment)
    row=readout['row']; channel=readout['channel']
    if type(row) is not int or row<0 or row>=min(len(a['times']),len(b['times'])) or channel not in world.channels:
        raise ValueError('invalid readout')
    t=a['times'][row]
    if t!=b['times'][row]: raise ValueError('paired readout times differ')
    if not any(_unassigned(world,s,t) for s in (a,b)):
        return {'eligible':False,'reason':'assigned_zero_response'}
    eligible=_arm_key(world,a,readout)!=_arm_key(world,b,readout)
    return {'eligible':eligible,'reason':'different_causal_history_not_mechanism_certificate' if eligible else 'identical_causal_history'}


def prediction_metrics(predicted,observed,scales,*,world,spec):
    _check(world); s=world.validate(spec)
    if tuple(scales)!=tuple(world.scales):raise ValueError('world scale mismatch')
    arr=np.asarray(predicted)
    expected=(len(s['times']),len(world.channels))
    if arr.dtype.kind not in 'fiu' or arr.shape!=expected or not np.isfinite(arr).all():
        raise ValueError('finite real numeric matrix required')
    mask=np.array([_unassigned(world,s,t) for t in s['times']])
    if not mask.any(): raise ValueError('no unassigned prediction cells')
    truth=np.asarray(observed['values'],dtype=float)
    if truth.shape!=expected or not np.isfinite(truth).all():raise ValueError('invalid target')
    rmse=float(np.sqrt(np.mean(((arr[mask]-truth[mask])/np.asarray(scales))**2)))
    return {'normalized_rmse':rmse,'score':100*math.exp(-rmse/.1),
            'scored_cells':int(mask.sum()*len(scales)),'mask_protocol':PROTOCOL}

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
                key = canonical_hash([CONFIRMATION_NOISE_NAMESPACE, confirmation_key, index, arm, replica])
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


def generate_panel(world,seed,kind,count=8):
    _check(world)
    return world.panel(seed,kind,count)


def public_panel_domain(environment):
    if environment not in SUPPORTED:raise ValueError('explicit history world required')
    if environment=='adaptive_signaling':
        conditions='Two stimulus levels over0..12, no auxiliary reset.'
        interventions='Two stimulus levels plus one auxiliary-state partial reset over0..12.'
    else:
        conditions='Fresh constant-flow recovery histories over0..12, independently varied injection load[0.1,3].'
        interventions='Flow, pause and resumed flow over0..12, independently varied injection load[0.1,3].'
    return {'protocol':PROTOCOL,'conditions':conditions,'interventions':interventions,
            'scope':'Numerical transfer within domains, not unique mechanism identification.'}
