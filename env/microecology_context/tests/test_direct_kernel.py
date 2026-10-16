import numpy as np
import pytest
from env.microecology_context.direct_kernel import DirectKernel

@pytest.mark.parametrize('seed',[17101,17102,17103])
def test_local_three_body_witness(seed):
    k=DirectKernel(seed);p=DirectKernel(seed,'pairwise')
    def flux(model,a,b):
        z=np.array([0,a,b,.2,0,.8,0,0,0,0.])
        return model.derivative(0,z,30)[3]
    for model in (k,p):
        assert flux(model,.2,.4)==pytest.approx(flux(p,.2,.4))
    assert flux(k,0,.4)-flux(k,0,0)<0
    assert flux(k,.8,.4)-flux(k,.8,0)>0
    assert (flux(p,.8,.4)-flux(p,.8,0))==pytest.approx(flux(p,0,.4)-flux(p,0,0))
    # With no nutrient, local C uptake cannot reveal either mechanism.
    z=np.array([0,.8,.4,.2,0,0,0,0,0,0.])
    np.testing.assert_allclose(k.derivative(0,z,30),p.derivative(0,z,30))

@pytest.mark.parametrize('seed',[17101,17102,17103])
@pytest.mark.parametrize('family',['pairwise','three_body'])
def test_independent_integrator(seed,family):
    k=DirectKernel(seed,family)
    for temp in (20,40):
        z=np.array([5,1,1,1,2,2,2,2,2,0.])
        a=k.advance(z,48,temp);b=k.advance(z,48,temp,method='Radau')
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-7)
        assert abs(sum(a[:9])-sum(z[:9]))<1e-7
        assert min(a[:9])>=-1e-8
        assert .5<=k.modulation(100,100)<=2
