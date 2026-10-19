"""Continuous evidence-backed judgments, never checklist-completion scores."""
import math

VERSION = 'discovery-layers-1'
WEIGHTS = {'L1':10, 'L2':20, 'L3':25, 'L4':25, 'L5':20}
CRITERIA = {
 'L1': {'effect':50, 'scope':30, 'uncertainty':20},
 'L2': {'dependencies':30, 'functional_form':40, 'quantitative_recovery':30},
 'L3': {'mechanistic_account':30, 'discrimination':40, 'evidence_update':30},
 'L4': {'shared_model_transfer':60, 'intervention_effect':30, 'inference_scope':10},
 'L5': {'boundary':25, 'revision':25, 'new_validation_and_retention':50},
}

def contract(environment):
    if environment not in ('ecology', 'oscillator'):
        raise ValueError('unsupported task')
    return {'protocol':VERSION, 'environment':environment,
            'objects':['law','structure'], 'weights':{k:WEIGHTS[k] for k in ('L1','L2','L3','L4')},
            'criteria':{k:CRITERIA[k] for k in ('L1','L2','L3','L4')},
            'inapplicable':{'L5':'No independently validated model-boundary phase in this task'},
            'prior_exclusions': ['Public linear force law is not a discovery'] if environment=='oscillator' else [],
            'judgment':'Each criterion rates scientific recovery continuously from 0 to 100, with evidence and rationale; citation counts earn no points.'}

def summarize(frozen, decisions):
    """Missing review is pending. Explicit scientific rejection is score zero.

    Inputs are independent reviewer judgments, not agent self-reported scores.
    Evidence validity and semantic accuracy require external review.
    """
    expected={(l,c) for l,cs in frozen['criteria'].items() for c in cs}
    seen={}
    for row in decisions:
        key=(row['level'],row['criterion'])
        if key not in expected or key in seen: raise ValueError('unexpected/duplicate decision')
        score=row['score']
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=100:
            raise ValueError('score must be finite 0..100')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip() or not isinstance(row.get('evidence'),list) or not row['evidence'] or any(not isinstance(x,str) or not x.strip() for x in row['evidence']):
            raise ValueError('review reason and evidence required, including zero judgments')
        seen[key]=score
    levels={l: None if any((l,c) not in seen for c in cs) else sum(seen[l,c]*w for c,w in cs.items())/sum(cs.values()) for l,cs in frozen['criteria'].items()}
    total=None if any(v is None for v in levels.values()) else sum(levels[l]*w for l,w in frozen['weights'].items())/sum(frozen['weights'].values())
    return {'protocol':frozen['protocol'],'levels':levels,'weighted_score':total,'status':'pending' if total is None else 'reviewed', 'review_independence':'same-family','acceptance_status':'provisional'}
