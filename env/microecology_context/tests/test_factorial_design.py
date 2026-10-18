from copy import deepcopy
import pytest
from env.microecology_context.factorial_design import build_design,validate_design

BASE={'initial':{'C':.15,'m2':.7},'times':[0,1,3]}

def test_orthogonal_eight_conditions_and_immutable_input():
    original=deepcopy(BASE)
    arms=build_design(BASE,[.1,.8],[.2,.8],[25,35])
    assert validate_design(arms)['temperature_blocks']==[[0,1,2,3],[4,5,6,7]]
    assert BASE==original
    assert len({(s['initial']['A'],s['initial']['B'],s['temperature']) for s in arms})==8
    assert {s['initial']['m2'] for s in arms}=={.7}

def test_confounds_duplicates_and_illegal_levels_rejected():
    arms=build_design(BASE,[.1,.8],[.2,.8],[25,35])
    bad=deepcopy(arms);bad[3]['initial']['C']=.3
    with pytest.raises(ValueError):validate_design(bad)
    with pytest.raises(ValueError):validate_design(arms[:-1]+[arms[0]])
    with pytest.raises(ValueError):build_design(BASE,[.1,.1],[.2,.8],[25,35])
    with pytest.raises(ValueError):build_design(BASE,[.1,2],[.2,.8],[25,35])
    with pytest.raises(ValueError):build_design(dict(BASE,events=[{'time':1,'channel':'C','add':.1}]),[.1,.8],[.2,.8],[25,35])
