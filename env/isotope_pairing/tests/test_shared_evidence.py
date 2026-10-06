from copy import deepcopy
import pytest
from env.evidence_packet import _record, _spec
from env.isotope_pairing.world import World


def test_shared_evidence_projection_and_channel_identity():
    s = World.example()
    raw = {'id': 'obs-1', 'spec': s, 'private_seed': 'CANARY',
           'observation': {'axis': s['times'], 'channels': list(World.channels),
                           'values': [[-.001, .3, .7] for _ in s['times']],
                           'clean_target': 'CANARY'}}
    result = _record(raw, 'isotope_pairing')
    assert 'CANARY' not in repr(result)
    assert result['observation']['values'][0][0] == -.001
    changed = deepcopy(raw)
    changed['observation']['channels'].reverse()
    with pytest.raises(ValueError, match='channel order'):
        _record(changed, 'isotope_pairing')
    s['source'][0]['private_parameter'] = 'CANARY'
    with pytest.raises(ValueError):
        _spec(s, 'isotope_pairing')


def test_shared_evidence_validates_legal_controls():
    s = World.example()
    s['source'][0]['fractions'] = [1., 1., 0., 0.]
    with pytest.raises(ValueError):
        _spec(s, 'isotope_pairing')
