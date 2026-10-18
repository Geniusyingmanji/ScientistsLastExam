import json
import pytest
from env.electrical_impedance.restricted_episode import RestrictedEpisode
S={'frequencies_hz':[2.,10.],'source_ohm':500.,'load_ohm':5000.,'amplitude_v':1.}

def make(tmp):
    return RestrictedEpisode(17201,tmp,[2,10],[(500,5000)],1,[dict(S,frequencies_hz=[7])],max_attempts=3)

def test_reject_reservation_without_world_call_and_charge(tmp_path,monkeypatch):
    e=make(tmp_path);calls=[]
    monkeypatch.setattr(e.world,'run',lambda *a,**k:calls.append(a))
    out=e.call('experiment',experiment_id='blocked',spec=dict(S,frequencies_hz=[7]))
    assert 'error' in out and out['remaining_units']==279 and out['remaining_attempts']==2
    assert not calls
    with pytest.raises(ValueError):e.call('register_prediction',experiment_id='blocked',spec=S,prediction=[0]*4,model_sha256='a'*64)
    assert 'reserved' not in e.call('describe')['acquisition_domain']
    rows=[json.loads(x) for x in (tmp_path/'observations.jsonl').read_text().splitlines()]
    assert rows[0]['request']['spec']['frequencies_hz']==[7]

def test_allowed_noisy_measurement_and_reopen_refused(tmp_path):
    e=make(tmp_path)
    out=e.call('experiment',experiment_id='ok',spec=S)
    assert len(out['values'])==2 and 'error' not in out
    with pytest.raises(FileExistsError):make(tmp_path)
