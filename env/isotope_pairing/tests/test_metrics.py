import pytest
from env.isotope_pairing.world import World
from env.isotope_pairing.metrics import experiment_error,summarize

def test_initial_exclusion_and_equal_experiment_weight():
    s=World.example();y=[[0.,0.,0.] for _ in s['times']];p=[[1.,1.,1.] for _ in s['times']];p[0]=[999.,999.,999.]
    assert experiment_error(s,p,y)['rmse']==pytest.approx(1.)
    short={'times':[1.],'source':s['source']}
    r=summarize([{'axis':'new_recipe','spec':s,'prediction':p,'target':y},{'axis':'new_recipe','spec':short,'prediction':[[3.,3.,3.]],'target':[[0.,0.,0.]]}])
    assert r['axes']['new_recipe']['mean_experiment_rmse']==pytest.approx(2.)
    assert r['axes']['new_history']['mean_experiment_rmse'] is None
    assert r['overall_score'] is None

def test_missing_cells_not_zero_score_and_invalid_not_skipped():
    s=World.example();s['times']=[0.]
    assert experiment_error(s,[[0.,0.,0.]],[[1.,0.,0.]])['rmse'] is None
    with pytest.raises(ValueError):experiment_error(s,[[float('nan'),0.,0.]],[[1.,0.,0.]])
    with pytest.raises(ValueError):summarize([{'axis':'unknown','spec':s,'prediction':[],'target':[]}])
