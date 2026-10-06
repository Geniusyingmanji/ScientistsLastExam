from copy import deepcopy
import pytest
from env.isotope_pairing.world import World
from env.isotope_pairing.evidence import record

def fixture():
    s=World.example()
    return s,{'axis':s['times'][:],'channels':['unlabeled','single_label','double_label'],'values':[[1.01,-.01,.003] for _ in s['times']]}

def test_noise_preservation_and_detached_output():
    s,o=fixture();r=record(s,o)
    assert r['observation']['values'][0]==[1.01,-.01,.003]
    assert r['prediction_mask'][0]==[False]*3
    r['spec']['source'][0]['fractions'][0]=0
    r['observation']['values'][0][0]=0
    assert s['source'][0]['fractions'][0]==.5 and o['values'][0][0]==1.01

def test_private_extras_and_bad_shapes_fail_closed():
    s,o=fixture()
    for field in ['world_seed','clean_truth','parameters']:
        bad=deepcopy(o);bad[field]=1
        with pytest.raises(ValueError):record(s,bad)
    for change in [lambda x:x['values'][0].pop(),lambda x:x['axis'].__setitem__(0,True),lambda x:x['values'][0].__setitem__(0,float('nan')),lambda x:x['channels'].reverse()]:
        bad=deepcopy(o);change(bad)
        with pytest.raises(ValueError):record(s,bad)
