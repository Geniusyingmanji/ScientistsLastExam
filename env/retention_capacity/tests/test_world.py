import numpy as np
import pytest
from scipy.linalg import expm
from env.retention_capacity.world import World,baseline
from env.retention_capacity.kernel import derivative,predict


def rk4(family,p,spec):
    # Fixed stepping independently of the production adaptive solver.
    state=np.array([spec['load'],0.,0.]);now=0.;rate=spec['flow'][0]['rate'];events={r['at']:r['rate'] for r in spec['flow']};rows={}
    for end in sorted(set(spec['times']+list(events))):
        if end>spec['times'][-1]:break
        n=max(1,int(np.ceil((end-now)/.002)));h=(end-now)/n
        for _ in range(n):
            k1=derivative(family,p,rate,state);k2=derivative(family,p,rate,state+h*k1/2);k3=derivative(family,p,rate,state+h*k2/2);k4=derivative(family,p,rate,state+h*k3)
            state+=h*(k1+2*k2+2*k3+k4)/6
        rows[end]=state[2]/spec['load'];now=end
        if end in events:rate=events[end]
    return np.array([[rows[t]] for t in spec['times']])


@pytest.mark.parametrize('seed',[5000,5001])
def test_independent_integrator_extreme_and_limit(seed):
    w=World(seed);s={'load':3.,'times':[0.,1.,2.,4.,8.,12.],'flow':[{'at':0.,'rate':3.},{'at':1.,'rate':0.},{'at':4.,'rate':3.}]}
    actual=np.array(w.run(s)['values']);assert np.max(abs(actual-rk4(w._family,w._parameters,s)))<1e-5
    assert np.all(np.diff(actual[:,0])>=-1e-9) and actual.min()>=0 and actual.max()<=1+1e-9
    # Operator-only asymptotic check, not an available candidate experiment.
    p=[1.,.6,.3,.8];tiny={'load':1e-5,'times':[1.],'flow':[{'at':0.,'rate':1.}]}
    linear=expm(np.array([[-1.6,.3,0],[.6,-.3,0],[1,0,0]]))@np.array([1.,0,0])
    assert abs(predict(w._family,p,tiny)[0,0]-linear[2])<1e-5


def test_spec_noise_and_baseline():
    w=World(5000);s=w.example();a=w.run(s,noise_key='one');assert a==w.run(s,noise_key='one');assert a!=w.run(s,noise_key='two')
    assert baseline([{'spec':s,'observation':a}],s)==a['values']
    for load in [0,4,True,float('nan')]:
        with pytest.raises(ValueError):w.validate(dict(s,load=load))
    assert 'storage_capacity' not in str(w.describe())


def test_specific_rivals_separate_with_load():
    p=[1.,.6,.3,.8];s={'load':3.,'times':[1.,2.,4.],'flow':[{'at':0.,'rate':1.}]}
    assert np.max(abs(predict('storage_capacity',p,s)-predict('outlet_capacity',p,s)))>.1
    # A zero-flow preparation remains unresolved by recovered fraction alone.
    s['flow'][0]['rate']=0
    for family in World.operator_strata:assert np.max(abs(predict(family,p,s)))==0
