import pytest
from env.prospective_runner import ProspectiveTask
from env.registry import ENVIRONMENTS


def test_prototype_entry_explicit_and_closed_by_default(tmp_path):
    assert 'isotope_pairing' not in ENVIRONMENTS
    for kwargs in ({}, {'frontier': True}, {'prototype': True},
                   {'frontier': True, 'prototype': 1}):
        with pytest.raises(ValueError):
            ProspectiveTask('isotope_pairing', 100, tmp_path / 'denied', **kwargs)
    assert not (tmp_path / 'denied').exists()
    task = ProspectiveTask('isotope_pairing', 100, tmp_path / 'accepted', frontier=True, prototype=True)
    assert task.describe()['observation_contract']['environment'] == 'isotope_pairing'
    task.close('driver_stopped')
