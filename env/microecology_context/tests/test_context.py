import numpy as np
import pytest
from env.microecology_context.kernel import Kernel,FAMILIES
from env.microecology_context.world import World,validate

@pytest.mark.parametrize('family',FAMILIES)
def test_independent_solver_and_mass(family):
    k=Kernel(15101,family);state=np.array([2,.2,.2,.2,.2,.2,.05,.08,0,0.])
    a=k.advance(state,24,35);b=k.advance(state,24,35,'Radau')
    assert np.max(abs(a-b))<1e-7
    assert abs(sum(a[:9])-sum(state[:9]))<1e-8
    assert min(a)>=-1e-9

def test_signal_and_memory_witness():
    state=np.array([1,.1,.3,.3,.5,.1,.02,.001,0,.1])
    changed=state.copy();changed[7]=.5
    fixed=Kernel(15101,'fixed');signal=Kernel(15101,'signal');memory=Kernel(15101,'context_memory')
    assert fixed.derivative(0,state,30)[5]==fixed.derivative(0,changed,30)[5]
    assert signal.derivative(0,state,30)[5]>signal.derivative(0,changed,30)[5]
    assert memory.derivative(0,state,30)[5]==memory.derivative(0,changed,30)[5]
    assert memory.derivative(0,state,30)[9]!=memory.derivative(0,changed,30)[9]

def test_event_and_readout_semantics():
    w=World(15101,'context_memory')
    s=dict(initial={'substrate':2,'A':.2,'B':.2,'C':.2},times=[0,4,12],events=[{'time':4,'channel':'m4','add':.3}])
    full=w.run(s,clean=True);terminal=w.run(dict(s,times=[12]),clean=True)
    assert np.allclose(full['values'][-1],terminal['values'][0],atol=1e-8)
    assert full['values'][1][7]>=.3
    with pytest.raises(ValueError):validate(dict(s,times=[float('nan')]))


def test_history_conditioned_interaction_changes_sign():
    w=World(15105,'context_memory')
    effects=[]
    for signal in (0,.5):
        values=[]
        for b in (0,.3):
            spec={'initial':{'A':.1,'C':.2,'m4':signal},'times':[16],
                  'events':[{'time':8,'channel':'B','add':b},
                            {'time':8,'channel':'m1','add':.5},
                            {'time':8,'channel':'m2','add':.2}]}
            values.append(w.run(spec,clean=True)['values'][0][3])
        effects.append(values[1]-values[0])
    assert effects[0]>.1 and effects[1]<-.004
