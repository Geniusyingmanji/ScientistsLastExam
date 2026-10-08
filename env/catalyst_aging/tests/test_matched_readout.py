import pytest
from env.catalyst_aging.matched_readout import quartet, calibrated_contrast
from env.catalyst_aging.protocol import reaction


def test_affine_instrument_cancellation_and_prefix_alignment():
    event = reaction('A',500,.6,8)
    arms = quartet([event,event],event,'B')
    assert all(s['event_indices']==[3] for s in arms.values())
    assert all(s['events'][:-1]==[event,event] for s in arms.values())
    # Independent algebraic fixture, not a sampled simulator realization.
    for gain,offset in [(0.4,-.2),(1.,0.),(1.7,.3)]:
        values={k:gain*v+offset for k,v in {'used':.12,'fresh':.3,'blank':0.,'standard':1.5}.items()}
        assert calibrated_contrast(values)==pytest.approx(-.18)


def test_reject_nonfresh_control_and_weak_calibration():
    event=reaction('A',500,.6,8)
    with pytest.raises(ValueError):quartet([event],event,'A')
    with pytest.raises(ValueError):calibrated_contrast({'used':1.,'fresh':1.,'blank':0.,'standard':.01})
