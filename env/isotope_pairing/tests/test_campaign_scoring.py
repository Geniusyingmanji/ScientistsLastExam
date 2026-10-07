from copy import deepcopy
import pytest
from env.isotope_pairing.world import World
from env.isotope_pairing import campaign_scoring as score

def pair():
    a={'times':[0.,1.,3.],'source':[{'at':0.,'fractions':[1.,0.,0.,0.]}]}
    b=deepcopy(a);b['source'][0]['fractions']=[.5,0.,0.,.5]
    return a,b

def test_initial_mask_and_no_target_leak():
    w=World(0);a,_=pair();obs=w.run(a);pred=deepcopy(obs['values']);pred[0]=[99,99,99]
    assert score.prediction_metrics(pred,obs,w.scales,world=w,spec=a)['score']==100
    assert score.prediction_metrics(pred,obs,w.scales,world=w,spec=a)['scored_cells']==6

def test_future_and_redundant_history_aliases():
    w=World(0);a,b=pair();r={'row':1,'channel':'double_label'}
    future=deepcopy(a);future['source'].append({'at':1.,'fractions':[.5,0.,0.,.5]})
    assert not score.claim_eligibility(w,a,future,r)['eligible']
    redundant=deepcopy(b);redundant['source'].append({'at':.5,'fractions':b['source'][0]['fractions']})
    assert score._arm_key(w,b,r)==score._arm_key(w,redundant,r)

def test_submission_validation_and_reversed_duplicate():
    w=World(0);a,b=pair();c=dict(id='c1',statement='effect',scope='one contrast',control=a,treatment=b,readout={'row':1,'channel':'double_label'},interval=[-1.,1.],evidence_ids=['obs-1'])
    sub={'predictor_code':'def predict(spec): return []','claims':[c],'explanation':'test'}
    validated=score.validate_submission(sub,w,[{'id':'obs-1'}])
    rev=deepcopy(validated['claims'][0]);rev.update(id='c2',control=b,treatment=a)
    calls=[];original=w.run
    def counted(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    w.run=counted
    out=score.verify_claims(w,[c,rev],'fixed-development-check')
    assert len(calls)==128
    assert out['claims'][1]['duplicate'] and out['claims'][1]['score']==0
    assert out['score']==out['claims'][0]['score']/3
    sub['claims'][0]['interval']=[0.,float('nan')]
    with pytest.raises(ValueError):score.validate_submission(sub,w,[{'id':'obs-1'}])


def test_numeric_ndarray_matches_list_and_rejects_invalid_types():
    import numpy as np
    w=World(0);spec,_=pair();observed=w.run(spec)
    array=np.asarray(observed['values'])
    assert score.prediction_metrics(array,observed,w.scales,world=w,spec=spec)==score.prediction_metrics(array.tolist(),observed,w.scales,world=w,spec=spec)
    for invalid in (array.astype(bool),array.astype(complex),array.astype(object),array[:1],array*np.nan):
        with pytest.raises(ValueError):
            score.prediction_metrics(invalid,observed,w.scales,world=w,spec=spec)
