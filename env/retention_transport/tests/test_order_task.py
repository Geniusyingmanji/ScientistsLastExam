import numpy as np
import pytest
from env.retention_transport.world import World
from env.retention_transport.order_task import pair,observe,score


def test_order_witness_and_null_control():
    design=pair(0,2,2)
    # Exposed development instances, not future evaluation targets.
    for seed in (4000,4002):
        w=World(seed)
        effect=observe(w,design,noise_key=None)
        assert abs(effect)>5*np.sqrt(2)*.002
        assert observe(w,{'left':design['right'],'right':design['left']},noise_key=None)==pytest.approx(-effect)
    for seed in (4001,4003):
        assert abs(observe(World(seed),design,noise_key=None))<1e-10


def test_noise_is_independent_and_signed():
    w=World(4000);design=pair(.5,1.5,1)
    clean=observe(w,design,noise_key=None)
    errors=np.array([observe(w,design,noise_key=f'order-test-{i}')-clean for i in range(256)])
    assert .0022<errors.std()<.0035
    assert abs(errors.mean())<.0006


def test_public_validation_and_score():
    for args in [(1,1,1),(0,4,1),(0,2,7),(False,2,1),(0,float('nan'),1)]:
        with pytest.raises(ValueError):pair(*args)
    assert score([.1,-.1],[.1,-.1])['score']==100
    assert score([0,0],[.1,-.1])['score']==pytest.approx(100/np.e)
    for bad in [[float('nan')],[True],['0'],[[0]]]:
        with pytest.raises(ValueError):score(bad,[0])
