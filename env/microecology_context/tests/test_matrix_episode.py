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
