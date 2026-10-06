import pytest
from env.lineage_memory.exact_variance import difference_moments


def test_bernoulli_limit_and_crossed_covariance():
    a = difference_moments(.5,0.,0.,.5,.5,1,False,False)
    assert a['mean_squared_difference'] == pytest.approx(.5)
    assert a['variance_squared_difference'] == pytest.approx(.25)
    u = difference_moments(.5,.4,.2,.5,.5,32,False,False)
    s = difference_moments(.5,.4,.2,.5,.5,32,True,False)
    assert (u['mean_squared_difference']-s['mean_squared_difference'])/2 == pytest.approx(.04)
    with pytest.raises(ValueError): difference_moments(.5,2.,0.,.5,.5,32,True,False)
