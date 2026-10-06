import math
import pytest
from scipy.optimize import minimize_scalar
from env.seismic_aperture.kernel import travel_times


def test_homogeneous_limit_and_layer_permutation():
    xs=[0.,.1,.5,1.,2.,4.]
    a=travel_times([.5,1.5],[1.,3.],xs)
    assert a['times']==pytest.approx(travel_times([1.5,.5],[3.,1.],xs)['times'])
    assert travel_times([2.],[3.],xs)['times']==pytest.approx([math.hypot(4,x)/3 for x in xs])
    assert travel_times([2.],[3.],[-1.,1.])['times'][0]==pytest.approx(travel_times([2.],[3.],[-1.,1.])['times'][1])
    for x,t in zip(xs,a['times']):
        # Independently minimize allocation of half-offset between layers.
        f=lambda z:2*(math.hypot(.5,z)+math.hypot(1.5,x/2-z)/3)
        if x==0:expected=f(0)
        else:
            r=minimize_scalar(f,bounds=(0,x/2),method='bounded',options={'xatol':1e-12,'maxiter':100})
            assert r.success
            expected=r.fun
        assert t==pytest.approx(expected,abs=1e-10,rel=0)
