import pytest
from env.coupled_oscillators.matrix_episode import MatrixEpisode

def test_noisy_prospective_seal_and_failure_accounting(tmp_path):
    e=MatrixEpisode(1,tmp_path/'episode',budget=4)
    s={'times':[0,.5],'initial_position':[.5,0,0,0]}
    e.call('register_prediction',experiment_id='p1',spec=s,prediction=[0.]*16,model_sha256='a'*64)
    a=e.call('experiment',experiment_id='p1',spec=s)
    b=e.call('experiment',experiment_id='p2',spec=s)
    assert a['channels']==list(e.channels)
    assert a['values']!=b['values']
    assert e.call('experiment',experiment_id='bad',spec={})['remaining']==1
    r=e.call('submit_matrix',submission={'claims':[]},model_sha256='a'*64)
    assert r['sealed'] and r['scientific_score'] is None
    with pytest.raises(ValueError):e.call('experiment',experiment_id='late',spec=s)
