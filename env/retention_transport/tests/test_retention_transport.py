import numpy as np
import pytest
from scipy.integrate import solve_ivp
from env.retention_transport.world import World, baseline
from env.retention_transport.kernel import predict


def test_fixed_flow_ambiguity_and_pause_witness():
    v,on,off=1.,.6,.3
    fast,slow=sorted(np.roots([1,-(v+on+off),v*off]),reverse=True)
    fraction=(v-slow)/(fast-slow)
    p=[v,on,off];q=[fast,slow,fraction]
    s=World.example();s['times']=np.linspace(0,12,49).tolist()
    assert np.max(np.abs(predict('exchange',p,s)-predict('parallel',q,s)))<1e-12
    s['flow']=[{'at':0.,'rate':1.},{'at':1.,'rate':0.},{'at':4.,'rate':1.}]
    assert np.max(np.abs(predict('exchange',p,s)-predict('parallel',q,s)))>.01


@pytest.mark.parametrize('family',['exchange','parallel'])
def test_independent_solver_conservation_and_pause(family):
    p=[1.,.6,.3] if family=='exchange' else [1.7,.2,.55]
    def rhs(t,z):
        m,r,q=z
        if family=='exchange':
            v,on,off=p;return [-v*m-on*m+off*r,on*m-off*r,v*m]
        fast,slow,_=p;return [-fast*m,-slow*r,fast*m+slow*r]
    z=[1.,0.,0.] if family=='exchange' else [p[2],1-p[2],0.]
    s=World.example();ref=solve_ivp(rhs,[0,12],z,t_eval=s['times'],rtol=1e-11,atol=1e-13)
    assert np.allclose(ref.y.sum(axis=0),1,atol=1e-11)
    assert np.allclose(predict(family,p,s)[:,0],ref.y[2],atol=2e-10)
    s['flow'][0]['rate']=0.;assert np.allclose(predict(family,p,s),0)


def test_contract_and_extremes():
    w=World(100);s=w.example()
    assert w.describe()==World(101).describe()
    assert w.run(s,noise_key='a')==w.run(s,noise_key='a')
    assert w.run(s,noise_key='a')!=w.run(s,noise_key='b')
    rec={'spec':s,'observation':w.run(s,noise_key='a')};assert np.asarray(baseline([rec],s)).shape==(len(s['times']),1)
    for kind in ['development','conditions','interventions']:
        for p in w.panel(11,kind):
            y=np.asarray(w.run(p)['values'])[:,0];assert w.cost(p)>0 and y.min()>=-1e-12 and y.max()<=1+1e-12 and np.min(np.diff(y))>=-1e-12
    for bad in [dict(s,times=[0,0]),dict(s,flow=[{'at':0,'rate':float('inf')}]),dict(s,extra=1)]:
        with pytest.raises(ValueError):w.run(bad)
