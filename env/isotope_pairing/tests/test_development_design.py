import json
import numpy as np
from env.isotope_pairing.development_design import design
from env.isotope_pairing.kernel import target
from env.isotope_pairing.world import World

def test_exposed_panel_scope_and_validity():
    d=design();w=World(0)
    train={json.dumps(s,sort_keys=True) for s in d['training']}
    for panel in d['panels']:
        for s in panel['specs']:
            assert w.validate(s)==s
            assert json.dumps(s,sort_keys=True) not in train
    history=next(p for p in d['panels'] if p['kind']=='new_history')
    assert max(len(s['source']) for s in d['training'])==2
    assert all(len(s['source'])==3 for s in history['specs'])
    assert d['structural_holdout'] is False

def test_ambiguity_control_is_non_discriminating():
    p=next(p for p in design()['panels'] if p['kind']=='ambiguity_control')
    q=p['specs'][0]['source'][0]['fractions']
    assert np.allclose(target(q,0),target(q,1))
