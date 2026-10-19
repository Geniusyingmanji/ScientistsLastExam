import pytest
from env.discovery_layers.protocol import contract,summarize
from env.discovery_layers.episode import LayeredEpisode

def test_continuous_and_pending():
    c=contract('ecology');rows=[dict(level=l,criterion=k,score=37.5,reason='partial scientific recovery',evidence=['archive:observation']) for l,cs in c['criteria'].items() for k in cs]
    assert summarize(c,rows)['weighted_score']==37.5
    assert summarize(c,rows[:-1])['weighted_score'] is None
    with pytest.raises(ValueError): summarize(c,rows+rows[:1])
    rows[0]['score']=float('nan')
    with pytest.raises(ValueError): summarize(c,rows)

@pytest.mark.parametrize('world',['ecology','oscillator'])
def test_complete_seal(world,tmp_path):
    e=LayeredEpisode(world,123,tmp_path)
    d=e.call('describe'); assert 'applicable_cells' not in d
    assert 'L5' not in d['discovery_contract']['weights']
    spec={'times':[0,0.1]}
    result=e.call('experiment',experiment_id='observed',spec=spec)
    assert 'error' not in result
    assert result['remaining']==47
    e.call('submit_discovery',model_sha256='a'*64,submission={'claims':[]})
    with pytest.raises(ValueError): e.call('experiment',experiment_id='late',spec={})
    with pytest.raises(ValueError): e.call('submit_matrix')
