import json
import pytest
from env.microecology_context.matrix_episode import MatrixEpisode

SPEC={'initial':{'A':.8,'B':.8,'C':.2,'m2':.8},'times':[0,2]}

def test_real_world_registration_execution_and_no_reopening(tmp_path):
    e=MatrixEpisode(17101,'three_body',tmp_path,budget=3)
    receipt=e.call('register_prediction',experiment_id='future',spec=SPEC,prediction=[0.]*18,model_sha256='a'*64)
    assert set(receipt)=={'registered','receipt'}
    out=e.call('experiment',experiment_id='future',spec=SPEC)
    assert len(out['values'])==2 and out['remaining']==2
    rows=[json.loads(x) for x in (tmp_path/'prospective.jsonl').read_text().splitlines()]
    assert [x['kind'] for x in rows]==['prediction','attempt']
    with pytest.raises(ValueError):e.call('register_prediction',experiment_id='future',spec=SPEC,prediction=[0.]*18,model_sha256='b'*64)
    assert 'error' in e.call('experiment',experiment_id='future',spec=SPEC)
    with pytest.raises(FileExistsError):MatrixEpisode(17101,'three_body',tmp_path)

def test_invalid_and_changed_spec_consume_budget(tmp_path):
    e=MatrixEpisode(17101,'pairwise',tmp_path,budget=3)
    e.call('register_prediction',experiment_id='x',spec=SPEC,prediction=[0.]*18,model_sha256='a'*64)
    assert 'error' in e.call('experiment',experiment_id='x',spec=dict(SPEC,times=[1]))
    assert 'error' in e.call('experiment',experiment_id='bad',spec={})
    with pytest.raises(ValueError):e.call('register_prediction',experiment_id='bad',spec=SPEC,prediction=[0.]*18,model_sha256='a'*64)
    e.call('experiment',experiment_id='last',spec=SPEC)
    with pytest.raises(ValueError):e.call('experiment',experiment_id='over',spec=SPEC)
    assert e.world.calls==1

def test_submission_seals_and_preserves_evidence(tmp_path):
    e=MatrixEpisode(17101,'three_body',tmp_path,budget=2,applicable=('law/deduction',))
    e.call('register_prediction',experiment_id='x',spec=SPEC,prediction=[0.]*18,model_sha256='a'*64)
    e.call('experiment',experiment_id='x',spec=SPEC)
    value={'claims':[{'id':'c','cell':'law/deduction','statement':'Scoped prediction',
        'scope':'This configuration','alternatives':['unresolved'], 'evidence':['x']}]}
    out=e.call('submit_matrix',submission=value,model_sha256='a'*64)
    saved=(tmp_path/'submission.json').read_bytes()
    record=json.loads(saved)
    assert out['sealed'] and out['scientific_score'] is None
    assert record['audit']['claims'][0]['prospective_evidence']==['x']
    for name,args in [('experiment',{'experiment_id':'y','spec':SPEC}),
                      ('submit_matrix',{'submission':value,'model_sha256':'b'*64}),
                      ('register_prediction',{'experiment_id':'y','spec':SPEC,'prediction':[0.]*18,'model_sha256':'b'*64})]:
        with pytest.raises(ValueError,match='sealed'): e.call(name,**args)
    assert (tmp_path/'submission.json').read_bytes()==saved
    assert e.call('describe')['applicable_cells']==('law/deduction',)

def test_invalid_submission_does_not_close(tmp_path):
    e=MatrixEpisode(17101,'pairwise',tmp_path)
    with pytest.raises(ValueError):e.call('submit_matrix',submission={'claims':[]},model_sha256='bad')
    assert not (tmp_path/'submission.json').exists()
    assert e.call('submit_matrix',submission={'claims':[]},model_sha256='a'*64)['sealed']
