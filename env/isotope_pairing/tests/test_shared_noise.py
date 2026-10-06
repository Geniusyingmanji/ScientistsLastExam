from copy import copy
import pytest
from env.isotope_pairing.world import World
from env.prospective_runner import _observation_contract
from env.registry import ENVIRONMENTS


def test_shared_noise_contract_version_bound_and_unregistered():
    w = World(0)
    result = _observation_contract(w)
    assert result['noise_mean_bias_bound'] == [0., 0., 0.]
    assert result['noise_std'] == [.002, .002, .002]
    assert 'isotope_pairing' not in ENVIRONMENTS
    for field, value in [('version', 'isotope_pairing-0.2.0'),
                         ('noise_std', (.01, .01, .01)),
                         ('channels', ('total',)), ('axis_field', 'temperatures'),
                         ('scales', (2., 2., 2.))]:
        changed = copy(w)
        setattr(changed, field, value)
        with pytest.raises(ValueError, match='unsupported isotope'):
            _observation_contract(changed)
