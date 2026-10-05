import numpy as np
import pytest
from scipy.integrate import solve_ivp
from env.adaptive_signaling.world import World, baseline
from env.adaptive_signaling.kernel import predict


def test_exact_ambiguity_and_reset_witness():
    # Transfer functions are exactly equal for all stimulus histories, before a reset.
    a,b,g=.4,1.1,1.3
    p=[a,b,g];q=[a*b/(a+b),a+b,g*b/(a+b)]
    s=World.example();s['times']=np.linspace(0,12,49).tolist()
    s['stimulus']=[{'at':0.,'level':1.},{'at':2.,'level':.4},{'at':7.,'level':1.5}]
    assert np.max(np.abs(predict('feedforward',p,s)-predict('feedback',q,s)))<1e-12
    s['retained_fraction']=0.;s['reset_at']=1.
    assert np.max(np.abs(predict('feedforward',p,s)-predict('feedback',q,s)))>.05


@pytest.mark.parametrize('family',['feedforward','feedback'])
def test_independent_time_solver(family):
    p=[.45,1.2,1.1];s=World.example();s['retained_fraction']=.2
    def rhs(t,z):
        x,y=z;a,b,g=p
        return [a*(g-x) if family=='feedforward' else a*y,b*(g-x-y)]
    pre=solve_ivp(rhs,[0,3],[0,0],rtol=1e-11,atol=1e-13,dense_output=True)
    z=pre.y[:,-1].copy();z[0]*=.2
    post=solve_ivp(rhs,[3,12],z,rtol=1e-11,atol=1e-13,dense_output=True)
    ref=[pre.sol(t)[1] if t<=3 else post.sol(t)[1] for t in s['times']]
    assert np.allclose(predict(family,p,s)[:,0],ref,atol=2e-10)


def test_contract_and_no_stimulus_limit():
    w=World(100);s=w.example();s['stimulus'][0]['level']=0.
    assert np.allclose(w.run(s)['values'],0)
    assert World(100).describe()==World(101).describe()
    s=w.example();assert w.run(s,noise_key='a')==w.run(s,noise_key='a')
    assert w.run(s,noise_key='a')!=w.run(s,noise_key='b')
    assert np.asarray(baseline([],s)).shape==(len(s['times']),1)
    for kind in ['development','conditions','interventions']:
        for p in w.panel(11,kind): assert w.cost(p)>0 and np.isfinite(w.run(p)['values']).all()
    for bad in [dict(s,times=[True]),dict(s,retained_fraction=float('nan')),dict(s,extra=1),dict(s,times=list(range(50)))]:
        with pytest.raises(ValueError):w.run(bad)
