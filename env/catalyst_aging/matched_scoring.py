"""Opt-in matched-history endpoint task. Historical cohorts remain unchanged."""
import math
import numpy as np
from env import unified_scoring
from .matched_readout import quartet

PROTOCOL = 'catalyst-matched-task-0.1'
CONFIRMATION_REPLICATES = 0
CLAIM_SYSTEM = 'Submit claims: []. This task scores terminal signals and calibrated used-minus-fresh effects derived from the same four predictions. Explain competing explanations and uncertainty. '


def score_contract():
    return {'protocol': PROTOCOL, 'weights': {'absolute': .5, 'effect': .5},
            'absolute': '100*exp(-pooled RMSE/0.1), instrument signal units, all four arms.',
            'effect': '100*exp(-pooled RMSE/0.05), product units; 1.5*(used-fresh)/(standard-blank). Derived from the same four predicted signals.',
            'minimum_calibration_span': .15,
            'weak_prediction': 'Any predicted standard-minus-blank span below 0.15 makes the entire effect component zero; absolute component remains.',
            'invalid_prediction': 'Invalid shape, nonfinite or unbounded output fails prediction validation.',
            'claims': 'No claim score or omission penalty; claims must be [].',
            'history': 'Execute every preparation event, including events absent from event_indices. Each arm starts from a reset laboratory.'}


def public_panel_domain(environment):
    if environment != 'catalyst_aging':
        raise ValueError('catalyst world required')
    return {'protocol': PROTOCOL, 'domain': 'Four reset arms share an 11-event prefix: three A reactions each preceded by blank and standard, then two blanks. Terminal event 12 is used A, fresh B, blank or standard. Reaction temperature 440..560 K, feed 0.1..1.2, duration 2..15 min vary independently. Only the terminal signal is requested.',
            'scope': 'Predict signals and calibrated effects; no unique parameter or mechanism identification is required.'}


def generate_panel(world, seed, kind, count=8):
    public_panel_domain(world.name)
    if kind not in ('conditions', 'interventions') or type(count) is not int or not 1 <= count <= 64:
        raise ValueError('valid kind and 1..64 quartets required')
    rng = np.random.default_rng(seed)
    def reaction():
        return dict(kind='reaction', coupon_id='A', temperature_k=float(rng.uniform(440,560)),
                    feed_concentration=float(rng.uniform(.1,1.2)), duration_min=float(rng.uniform(2,15)))
    out = []
    for _ in range(count):
        prefix = []
        for _ in range(3):
            prefix.extend([{'kind':'blank'}, {'kind':'standard'}, reaction()])
        prefix.extend([{'kind':'blank'}, {'kind':'blank'}])
        arms = quartet(prefix, reaction(), 'B')
        out.extend(arms[k] for k in (('used','fresh') if kind == 'conditions' else ('blank','standard')))
    return out


def validate_submission(value, world, records):
    if not isinstance(value, dict) or value.get('claims') != []:
        raise ValueError('this task requires claims: []')
    return unified_scoring.validate_submission(value, world, records)


def verify_claims(world, claims, confirmation_key):
    if claims != []:
        raise ValueError('no claim slots')
    return {'protocol': PROTOCOL, 'score': 0., 'verified_nonzero_effects': 0, 'claims': []}


prediction_metrics = unified_scoring.prediction_metrics


def aggregate_episode(panel_reports, claim_report):
    a,b = (panel_reports[k] for k in ('conditions','interventions'))
    if not a or len(a) != len(b) or len(a)%2:
        raise ValueError('complete matched quartets required')
    predicted, target = [], []
    for i in range(0,len(a),2):
        rows = [a[i],a[i+1],b[i],b[i+1]]
        if [r['index'] for r in rows] != [i,i+1,i,i+1]:
            raise ValueError('quartet index mismatch')
        predicted.append([r['prediction_values'][0][0] for r in rows])
        target.append([r['clean_truth']['values'][0][0] for r in rows])
    p,t = np.asarray(predicted,dtype=float),np.asarray(target,dtype=float)
    if not np.isfinite(p).all() or not np.isfinite(t).all() or np.max(np.abs(p))>1e12:
        raise ValueError('invalid signals')
    ps,ts = p[:,3]-p[:,2],t[:,3]-t[:,2]
    if np.any(ts < .15):
        raise ValueError('host target calibration gate failed')
    weak = int(np.sum(ps < .15))
    absolute_rmse = float(np.sqrt(np.mean((p-t)**2)))
    effect_rmse = None if weak else float(np.sqrt(np.mean((1.5*(p[:,0]-p[:,1])/ps-1.5*(t[:,0]-t[:,1])/ts)**2)))
    absolute = 100*math.exp(-absolute_rmse/.1)
    effect = 0. if weak else 100*math.exp(-effect_rmse/.05)
    return {'protocol': PROTOCOL, 'score': .5*(absolute+effect),
            'subscores': {'absolute': absolute, 'effect': effect},
            'paired_metrics': {'absolute_rmse': absolute_rmse, 'effect_rmse': effect_rmse,
                               'weak_predicted_spans': weak, 'quartets': len(p)}}
