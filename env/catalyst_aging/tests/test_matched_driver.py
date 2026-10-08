import copy
import shutil
import sys
import numpy as np
import pytest
from env.catalyst_aging import matched_scoring as s, matched_driver
from env.catalyst_aging.world import World


def reports():
    w=World(0)
    out={}
    for k in ('conditions','interventions'):
        out[k]=[]
        for i,spec in enumerate(s.generate_panel(w,21,k,2)):
            truth=w.run(spec)
            out[k].append(dict(index=i,spec=spec,clean_truth=truth,prediction_values=copy.deepcopy(truth['values'])))
    return out


def test_four_arm_pooling_and_weak_span():
    r=reports()
    assert s.aggregate_episode(r,{})['score']==100
    r['conditions'][0]['prediction_values'][0][0]+=.1
    result=s.aggregate_episode(r,{})
    assert result['paired_metrics']['absolute_rmse']==pytest.approx(.1/np.sqrt(8))
    assert result['subscores']['effect']<100
    r['interventions'][1]['prediction_values']=[[r['interventions'][0]['prediction_values'][0][0]]]
    result=s.aggregate_episode(r,{})
    assert result['subscores']['effect']==0
    assert result['subscores']['absolute']>0
    assert result['paired_metrics']['weak_predicted_spans']==1
    r['conditions'][0]['prediction_values']=[[float('nan')]]
    with pytest.raises(ValueError): s.aggregate_episode(r,{})


def test_terminal_observation_executes_all_preparation():
    w=World(0)
    used,fresh=s.generate_panel(w,21,'conditions',1)
    assert used['events'][:-1]==fresh['events'][:-1]
    assert used['event_indices']==[12]
    full=dict(used,event_indices=list(range(1,13)))
    assert w.run(used)['values'][0]==w.run(full)['values'][-1]
    assert w.run(used)['values'][0]!=w.run(fresh)['values'][0]
    assert w.cost(used)==12
    assert 'every omitted claim slot' not in s.CANDIDATE_SYSTEM


def test_real_linux_pipeline(tmp_path):
    if sys.platform!='linux' or not shutil.which('bwrap'):
        pytest.skip('Linux+bwrap required')
    from env.runner import DEFAULT_LIMITS
    from env.analysis_api import PROTOCOL
    from env.tests.test_pilot_protocol import FakeClient
    from env.scoring import canonical_hash
    w=World(0)
    inst=dict(episode_id='catalyst-matched-engineering',environment=w.name,world_seed=0,panel_seed=21,
              confirmation_key='engineering',scoring_protocol=s.PROTOCOL,analysis_protocol=PROTOCOL)
    inst['panel_hashes']={k:canonical_hash(s.generate_panel(w,21,k,2)) for k in ('conditions','interventions')}
    code="def predict(spec):\n return [[1.5 if spec['events'][i-1]['kind']=='standard' else 0.] for i in spec['event_indices']]"
    client=FakeClient([
        {'note':'fixture','experiments':[s.generate_panel(w,21,'conditions',1)[0]]},
        {'note':'fixture','analyze':{'code':"result={'rows':len(records[0]['observation']['values'])}"}},
        {'note':'fixture','submit':{'predictor_code':code,'claims':[],'explanation':'Engineering fixture.'}}])
    limits=dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=2,wall_seconds=180,verification_reserve_seconds=30)
    report=matched_driver.run_model_episode(inst,limits,tmp_path,client)
    assert report['status']=='completed',report['stop_reason']
    assert report['history'][1]['analysis']['ok']
    assert set(report['subscores'])=={'absolute','effect'}
    assert report['score']==s.aggregate_episode(report['panels'],{})['score']
