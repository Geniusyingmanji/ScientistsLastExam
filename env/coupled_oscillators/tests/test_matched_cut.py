from copy import deepcopy
import pytest
from env.coupled_oscillators.matched_cut import build, validate_pair

BASE={'times':[0,.5,1.], 'initial_position':[.5,0,0,0]}


def test_one_cut_preserves_every_other_control_and_input():
    old=deepcopy(BASE);p=build(BASE,['B','A'])
    assert validate_pair(p)['edge']==['A','B']
    assert BASE==old
    assert validate_pair(p)['discovery_score'] is None


def test_loading_and_timing_confounds_rejected():
    for key,value in [('mass_add',[1,0,0,0]),('times',[0,.5,2.]),('initial_position',[.4,0,0,0])]:
        p=build(BASE,['A','B']);p['cut'][key]=value
        with pytest.raises(ValueError):validate_pair(p)


def test_duplicate_clamped_and_unobserved_interventions_rejected():
    with pytest.raises(ValueError):build(dict(BASE,cut_edges=[['A','B']]),['B','A'])
    with pytest.raises(ValueError):build(dict(BASE,clamp=['B']),['A','B'])
    with pytest.raises(ValueError):build(dict(BASE,times=[0]),['A','B'])
    p=build(BASE,['A','B']);p['cut']['cut_edges'].append(['A','C'])
    with pytest.raises(ValueError):validate_pair(p)
