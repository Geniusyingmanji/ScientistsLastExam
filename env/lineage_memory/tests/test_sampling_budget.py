import pytest
from env.lineage_memory.sampling_budget import contrast_plan


def test_conservative_budget_scaling_and_kernel_limit():
    p = contrast_plan(.01)
    assert p['pairs_per_arm'] == 18445
    assert p['simulated_individuals'] == 2360960
    assert p['confidence_radius_bound'] <= .01
    assert p['fits_single_kernel_call_per_arm']
    assert not contrast_plan(.005)['fits_single_kernel_call_per_arm']
    with pytest.raises(ValueError): contrast_plan(True)
    with pytest.raises(ValueError): contrast_plan(.01, group_size=True)
