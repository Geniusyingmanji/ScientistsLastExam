import importlib,shutil,sys
from copy import deepcopy
import numpy as np
import pytest
from env.runner import DEFAULT_LIMITS
from env.tests.test_pilot_protocol import FakeClient
from env.retention_capacity import scoring as s
from env.retention_capacity.world import World

def test_load_contrast_and_zero_mask():
    w=World(0);a=w.example();b=deepcopy(a);b["load"]=2.
    readout={"row":3,"channel":w.channels[0]}
    assert s.claim_eligibility(w,a,b,readout)["eligible"]
    assert not s.claim_eligibility(w,a,b,dict(readout,row=0))["eligible"]
    prediction=np.array(w.run(a)["values"]);prediction[0]=999
    assert s.prediction_metrics(prediction,w.run(a),w.scales,world=w,spec=a)["score"]==100
    assert s.PROTOCOL=="capacity-batch-score-1.0"

def test_real_linux_driver(tmp_path):
    name="retention_capacity"
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

