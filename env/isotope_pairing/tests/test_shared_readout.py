from copy import deepcopy
from env.frontier_semantics import readout_key, eligible_target
from env.isotope_pairing.world import World


def key(s, row=1):
    return readout_key('isotope_pairing', s, row, 'double_label')


def test_readout_ignores_future_and_redundant_events_not_causal_changes():
    s = World.example()
    s['times'] = [0., 2.]
    changed = deepcopy(s)
    changed['source'] += [{'at': 2., 'fractions': [1., 0., 0., 0.]}]
    assert key(s) == key(changed)
    changed['source'][1]['at'] = 1.
    assert key(s) != key(changed)
    changed['source'][1]['fractions'] = s['source'][0]['fractions'][:]
    assert key(s) == key(changed)
    other_rows = deepcopy(s)
    other_rows['times'] = [2., 3.]
    assert key(s) == key(other_rows, 0)


def test_assigned_initial_readout_excluded_and_recipe_independent():
    s = World.example()
    changed = deepcopy(s)
    changed['source'][0]['fractions'] = [1., 0., 0., 0.]
    assert key(s, 0) == key(changed, 0)
    assert not eligible_target('isotope_pairing', s, 0, 'double_label')
    assert eligible_target('isotope_pairing', s, 1, 'double_label')
