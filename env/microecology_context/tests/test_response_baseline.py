import json
from copy import deepcopy
import numpy as np
import pytest
from env.microecology_context.response_baseline import fit, predict
from env.microecology_context.world import validate, CHANNELS


def records(cross=0.):
    out=[]
    for a,b in [(0.,0.),(1.,0.),(0.,1.),(1.,1.)]:
        s=validate({'initial':{'A':a,'B':b,'C':.1},'times':[1.], 'temperature':30})
        out.append({'spec':s,'observation':{'times':[1.], 'channels':list(CHANNELS),
            'values':[[1+2*a+3*b+cross*a*b]*9]}})
    return out


def test_additive_recovery_and_json_snapshot():
    data=records(); old=deepcopy(data)
    model=json.loads(json.dumps(fit(data)))
    q=validate({'initial':{'A':.3,'B':.6,'C':.1},'times':[1.]})
    assert np.allclose(predict(model,[q]),[[3.4]*9])
    assert data==old


def test_interaction_control_and_all_repeats():
    data=records(4.)
    additive=fit(data); full=fit(data,interaction=True)
    assert min(additive['training_rmse_by_channel'])>.99
    assert max(full['training_rmse_by_channel'])<1e-12
    repeated=data+deepcopy(data)
    for r in repeated[4:]:r['observation']['values'][0]=[v+2 for v in r['observation']['values'][0]]
    model=fit(repeated,interaction=True)
    assert np.allclose(predict(model,[data[0]['spec']]),[[2.]*9])
    assert model['records']==8


def test_rank_confounds_and_malformed_observations_fail():
    data=records()
    with pytest.raises(ValueError):fit(data[:2])
    bad=deepcopy(data);bad[-1]['spec']['temperature']=35
    with pytest.raises(ValueError):fit(bad)
    bad=deepcopy(data);bad[0]['observation']['values'][0][0]=float('nan')
    with pytest.raises(ValueError):fit(bad)
    q=deepcopy(data[0]['spec']);q['initial']['C']=.2
    with pytest.raises(ValueError):predict(fit(data),[q])
