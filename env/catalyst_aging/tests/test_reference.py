import pytest
from env.catalyst_aging.reference import fit


def test_missing_calibration_fails_closed():
    with pytest.raises(ValueError,match='calibration'):
        fit([])


def test_budget_is_hard_limit_and_data_only_fit():
    records=[{'spec':{'events':[{'kind':'blank'},{'kind':'standard'}],'event_indices':[1,2]},
              'observation':{'values':[[.02],[1.52]]}}]
    # No World or hidden instance is accepted by the reference API.
    with pytest.raises(RuntimeError,match='no reference'):
        fit(records,max_calls=0)
    result=fit(records,max_calls=1)
    assert result['forward_calls']==1
    assert any('failure' in x for x in result['attempts'])
