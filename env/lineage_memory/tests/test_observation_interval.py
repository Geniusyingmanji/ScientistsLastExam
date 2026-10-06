import pytest
from env.lineage_memory.observation_interval import fixed_interval


def test_fixed_observed_contrast_and_symmetry():
    a = [[0.,1.]]*100
    b = [[.5,.5]]*100
    r = fixed_interval(a,b)
    assert r['estimate'] == .5
    assert r['interval'][1] == .5
    assert fixed_interval(b,a)['estimate'] == -.5
    assert fixed_interval(b,b)['interval'][0] < 0 < fixed_interval(b,b)['interval'][1]
    assert r['covariance_interpretation_verified'] is False
    with pytest.raises(ValueError): fixed_interval(a,b[:-1])
    with pytest.raises(ValueError): fixed_interval([[True,0.]]*2,b[:2])
    with pytest.raises(ValueError): fixed_interval(a,b,alpha=0.)
