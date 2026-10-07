import importlib
import shutil
import sys
from copy import deepcopy
import numpy as np
import pytest
from env import history_scoring as s
from env.runner import DEFAULT_LIMITS
from env.tests.test_pilot_protocol import FakeClient

NAMES=('adaptive_signaling','retention_transport')

@pytest.mark.parametrize('name',NAMES)
def test_numeric_mask_and_contract(name):
    world=importlib.import_module('env.'+name+'.world').World(100)
    spec=world.example(); truth=world.run(spec); prediction=np.array(truth['values'])
    prediction[0]=999
    assert s.prediction_metrics(prediction,truth,world.scales,world=world,spec=spec)['score']==100
    for bad in (prediction.astype(bool),prediction.astype(complex),np.full(prediction.shape,np.nan),prediction[:-1]):
        with pytest.raises(ValueError):s.prediction_metrics(bad,truth,world.scales,world=world,spec=spec)
    assert world.describe()==importlib.import_module('env.'+name+'.world').World(101).describe()
    assert s.public_panel_domain(name)['protocol']==s.PROTOCOL

@pytest.mark.parametrize('name',NAMES)
def test_causal_history_and_duplicates(name):
    world=importlib.import_module('env.'+name+'.world').World(0)
    a=world.example(); b=deepcopy(a); readout={'row':3,'channel':world.channels[0]}
    field,key=('stimulus','level') if name=='adaptive_signaling' else ('flow','rate')
    b[field].append({'at':2.,key:2.})
    assert not s.claim_eligibility(world,a,b,readout)['eligible']
    b[field][-1]['at']=1.
    assert s.claim_eligibility(world,a,b,readout)['eligible']
    claim=dict(id='a',statement='finite contrast',control=a,treatment=b,readout=readout,interval=[-1,1],evidence_ids=['obs-0001'],scope='development')
    rev=dict(claim,id='b',control=b,treatment=a)
    c=s.validate_submission(dict(predictor_code='def predict(spec): return []',claims=[claim,rev],explanation='test'),world,[{'id':'obs-0001'}])
    report=s.verify_claims(world,c['claims'],'test-only')
    assert report['claims'][1]['duplicate'] and report['claims'][1]['score']==0
    assert not report['claims'][0]['mechanism_certified']
    b=deepcopy(a);b[field].insert(1,{'at':.5,key:b[field][0][key]})
    assert not s.claim_eligibility(world,a,b,readout)['eligible']


def test_null_reset_does_not_create_claim():
    from env.adaptive_signaling.world import World
    w=World(0);a=w.example();b=deepcopy(a);b.update(reset_at=0.,retained_fraction=0.)
    assert not s.claim_eligibility(w,a,b,{'row':3,'channel':w.channels[0]})['eligible']

@pytest.mark.parametrize('name',NAMES)
def test_real_linux_driver(name,tmp_path):
    if sys.platform!='linux' or not shutil.which('bwrap'):pytest.skip('Linux+bwrap required')
    module=importlib.import_module('env.'+name+'.model_driver');w=module.World(0)
    from env.analysis_api import PROTOCOL
    from env.scoring import canonical_hash
    inst=dict(episode_id='history-smoke-'+name,environment=name,world_seed=0,panel_seed=1,confirmation_key='development',scoring_protocol=s.PROTOCOL,analysis_protocol=PROTOCOL)
    inst['panel_hashes']={k:canonical_hash(s.generate_panel(w,1,k,1)) for k in ('conditions','interventions')}
    client=FakeClient([{'note':'engineering','experiments':[w.example()]},{'note':'engineering','analyze':{'code':"result={'rows':len(records[0]['observation']['values'])}"}},{'note':'engineering','submit':{'predictor_code':"import numpy as np\ndef predict(spec): return np.zeros((len(spec['times']),1))",'claims':[],'explanation':'fixture only'}}])
    limits=dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=1,wall_seconds=180,verification_reserve_seconds=30)
    r=module.run_model_episode(inst,limits,tmp_path,client)
    assert r['status']=='completed',r['stop_reason']
    assert r['history'][1]['analysis']['ok']
    assert all(p['valid'] for ps in r['panels'].values() for p in ps)


def test_claim_normalization_and_noise_namespace():
    import math
    from env.adaptive_signaling.world import World
    from env.scoring import canonical_hash
    w=World(100);a=w.example();b=deepcopy(a);b['stimulus'][0]['level']=1.5
    claim=dict(id='scale',statement='test',control=a,treatment=b,
        readout={'row':3,'channel':w.channels[0]},interval=[-1,1],evidence_ids=['obs-0001'],scope='test')
    result=s.verify_claims(w,[claim],'namespace-fixture')['claims'][0]
    expected=100*math.exp(-result['interval_score']/(.1*w.scales[0]))
    assert result['score']==pytest.approx(expected)
    key=canonical_hash(['history-batch-score-1.0','namespace-fixture',0,'control',0])
    assert result['replicate_arm_values']['control'][0]==w.run(a,noise_key=key)['values'][3][0]
    assert 'public_channel_scale' in s.score_contract()['claims']
