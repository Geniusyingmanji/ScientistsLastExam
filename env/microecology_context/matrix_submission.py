"""Structural matrix submission and trusted evidence audit, not semantic grading.

A valid citation or accurate prediction does not prove a mechanism. Scientific
cell verdicts remain unset until independent review against frozen task criteria.
"""
import hashlib
import math
from .prospective import canonical

FORMS = ('law', 'structure')
DIMENSIONS = ('deduction', 'mechanism', 'unification', 'counterfactual')
CELLS = tuple(f'{f}/{d}' for f in FORMS for d in DIMENSIONS)


def validate_submission(value, applicable):
    if not isinstance(value, dict) or set(value) != {'claims'} or not isinstance(value['claims'], list):
        raise ValueError('claims array required')
    if not set(applicable) <= set(CELLS):
        raise ValueError('unknown applicability cell')
    ids = set()
    for claim in value['claims']:
        if not isinstance(claim, dict) or set(claim) != {'id', 'cell', 'statement', 'scope', 'alternatives', 'evidence'}:
            raise ValueError('claim fields invalid')
        if not isinstance(claim['id'],str) or not claim['id'] or claim['id'] in ids:
            raise ValueError('unique claim ID required')
        ids.add(claim['id'])
        if claim['cell'] not in applicable:
            raise ValueError('cell not applicable to frozen task')
        if any(not isinstance(claim[k],str) or not claim[k].strip() for k in ('statement','scope')):
            raise ValueError('statement and scope required')
        for key in ('alternatives','evidence'):
            if not isinstance(claim[key],list) or any(not isinstance(x,str) or not x for x in claim[key]):
                raise ValueError('string lists required')
        if len(set(claim['evidence'])) != len(claim['evidence']):
            raise ValueError('duplicate evidence citation')
    return value


def audit(value, applicable, journal, observations):
    """Inputs are trusted archives; no clean/hidden outputs or label matching."""
    validate_submission(value, applicable)
    previous = '0'*64
    predictions, attempts, observed = {}, {}, {}
    for index, row in enumerate(journal):
        item = dict(row); digest = item.pop('sha256')
        if item['sequence'] != index or item['previous'] != previous or hashlib.sha256(canonical(item).encode()).hexdigest() != digest:
            raise ValueError('journal integrity failure')
        previous = digest; eid = item['experiment_id']
        if item['kind'] == 'prediction':
            if eid in predictions or eid in attempts: raise ValueError('late or duplicate prediction')
            predictions[eid] = row
        elif item['kind'] == 'attempt':
            if eid in attempts: raise ValueError('duplicate attempt')
            attempts[eid] = row
        else: raise ValueError('unknown journal event')
    for row in observations:
        response = row['response']
        if 'error' in response: continue
        eid = response['experiment_id']
        if eid in observed or eid not in attempts or response['receipt'] != attempts[eid]['sha256']:
            raise ValueError('unbound observation receipt')
        observed[eid] = response
    evidence = {}
    for eid, obs in observed.items():
        record = {'observed': True, 'prospective': False, 'observation_rmse': None}
        if eid in predictions:
            pred = predictions[eid]; attempt = attempts[eid]
            if pred['sequence'] >= attempt['sequence'] or canonical(pred['specification']) != canonical(attempt['specification']):
                raise ValueError('prediction not bound to executed specification')
            target = [x for row in obs['values'] for x in row]
            values = pred['prediction']
            if len(target) != len(values) or not target or any(type(x) not in (float,int) or not math.isfinite(x) for x in target+values):
                raise ValueError('invalid prediction or observation vector')
            record.update(prospective=True, observation_rmse=math.sqrt(sum((a-b)**2 for a,b in zip(target,values))/len(target)), model_sha256=pred['model_sha256'])
        evidence[eid] = record
    claims = []
    for claim in value['claims']:
        refs = claim['evidence']
        claims.append({'id':claim['id'], 'cell':claim['cell'], 'missing_evidence':[x for x in refs if x not in evidence],
            'prospective_evidence':[x for x in refs if x in evidence and evidence[x]['prospective']],
            'scientific_verdict':None})
    return {'cells':{cell: {'applicable':cell in applicable, 'claim_ids':[x['id'] for x in claims if x['cell']==cell], 'scientific_score':None} for cell in CELLS},
        'claims':claims,'evidence':evidence,'scope':'Evidence bookkeeping only; no scientific correctness, coverage or mechanism score. RMSE is against noisy observations.'}
