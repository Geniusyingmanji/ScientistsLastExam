import numpy as np
from env.lineage_memory.kernel import moments,sample

def test_analytic_limits():
    mean,var,cov=moments(.3,.1,.8,0,32)
    assert cov==0 and np.isclose(var,mean*(1-mean)/32)
    assert moments(0,.1,.8,1,32)[2]==0
    assert moments(.3,.5,.5,1,32)[2]==0
    assert np.isclose(moments(.3,.1,.8,.5,32)[2],moments(.3,.1,.8,1,32)[2]/4)

def test_fixed_sampling_witness():
    for rho,related in [(1.,True),(.1,True),(1.,False)]:
        x=sample(.3,.1,.8,rho,32,20000,430,related)
        mean,var,cov=moments(.3,.1,.8,rho,32)
        assert np.max(abs(x.mean(axis=0)-mean))<6*np.sqrt(var/len(x))
        # Independent estimate of sampling error for the paired centered product.
        products=(x[:,0]-mean)*(x[:,1]-mean)
        expected=cov if related else 0.
        assert abs(products.mean()-expected)<6*products.std(ddof=1)/np.sqrt(len(x))

def test_crossed_grouping_distinguishes_confounds():
    from env.lineage_memory.kernel import crossed_sample
    for founder,batch in [(False,False),(True,False),(False,True),(True,True)]:
        x=crossed_sample(.5,.3,.3,.5,.5,32,20000,731,founder,batch)
        products=(x[:,0]-.5)*(x[:,1]-.5)
        expected=(int(founder)+int(batch))*.3**2*.25
        assert abs(products.mean()-expected)<6*products.std(ddof=1)/np.sqrt(len(x))

def test_confound_boundary_validation():
    import pytest
    from env.lineage_memory.kernel import crossed_sample
    with pytest.raises(ValueError):crossed_sample(.9,.8,.8,.5,.5,32,100,731)
    with pytest.raises(ValueError):crossed_sample(.5,.3,.3,.5,.5,32,100,731,1,True)
