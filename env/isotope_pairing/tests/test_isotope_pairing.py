import numpy as np
import pytest
from scipy.integrate import solve_ivp
from env.isotope_pairing.kernel import target,predict
from env.isotope_pairing.world import World,baseline

def test_bookkeeping_and_discrimination():
    for q in ([.25]*4,[.5,0,0,.5],[0,.5,.5,0]):
        for a in (0,.4,1):
            y=target(q,a);assert np.all(y>=0);assert np.isclose(sum(y),1)
            assert np.isclose(y[1]+2*y[2],q[1]+q[2]+2*q[3])
    assert np.allclose(target([.25]*4,0),target([.25]*4,1))
    assert abs(target([.5,0,0,.5],0)[2]-target([.5,0,0,.5],1)[2])>.2

def test_independent_step_solver():
    s=World.example();q=s['source'][0]['fractions'];g=target(q,.6)
    y=solve_ivp(lambda t,x:.8*(g-x),(0,12),[1,0,0],t_eval=s['times'],rtol=1e-10,atol=1e-12).y.T
    assert np.allclose(predict(.8,.6,s),y,atol=1e-9)

def test_contract_panels_noise():
    w=World(100);assert w.describe()==World(101).describe()
    for s in w.panel(10,'interventions',3):
        y=np.array(w.run(s)['values']);assert np.allclose(y.sum(axis=1),1);assert np.all(y>=0)
        assert w.run(s,noise_key='a')==w.run(s,noise_key='a')
        assert w.run(s,noise_key='a')!=w.run(s,noise_key='b')
        assert np.asarray(baseline([],s)).shape==y.shape
    bad=World.example();bad['source'][0]['fractions']=[1,0,0]
    with pytest.raises(ValueError):w.validate(bad)

def test_chase_and_reset():
    s=World.example();s['source'].append({'at':3.,'fractions':[1.,0.,0.,0.]})
    y=predict(1,.5,s);assert np.allclose(y[0],[1,0,0]);assert y[-1,2]<y[2,2]
    assert World(202).run(s)==World(202).run(s)

def test_piecewise_independent_solver_and_extremes():
    s={'times':[0.,.1,3.,3.1,7.,12.],'source':[{'at':0.,'fractions':[0.,0.,0.,1.]},{'at':3.,'fractions':[1.,0.,0.,0.]},{'at':7.,'fractions':[0.,1.,0.,0.]}]}
    state=np.array([1.,0.,0.]);last=0.;out=[]
    for t in s['times']:
        cuts=sorted(set([last,t]+[x['at'] for x in s['source'] if last<x['at']<t]))
        for a,b in zip(cuts,cuts[1:]):
            q=next(x['fractions'] for x in reversed(s['source']) if x['at']<=a)
            goal=target(q,.4)
            state=solve_ivp(lambda _,y:2*(goal-y),(a,b),state,rtol=1e-10,atol=1e-12).y[:,-1]
        out.append(state.copy());last=t
    assert np.allclose(predict(2,.4,s),out,atol=1e-9)
