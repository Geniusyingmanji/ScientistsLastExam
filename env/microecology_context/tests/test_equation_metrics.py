import pytest
from env.microecology_context.equation_metrics import derivative_errors, effect_errors


def test_zero_regions_cannot_dilute_active_error():
    r=derivative_errors([0.]*100+[0.], [0.]*100+[2.], ['zero']*100+['active'], 2.)
    assert r['groups']['zero']['normalized_rmse']==0
    assert r['groups']['active']['normalized_rmse']==1
    assert r['discovery_score'] is None


def test_exact_and_missing_interaction():
    # Algebraically equivalent evaluations receive identical errors.
    target=[2.,2.,1.,4.]
    exact=effect_errors(target,target,1.)
    assert all(v['normalized_absolute_error']==0 for v in exact['effects'].values())
    omitted=effect_errors([2.]*4,target,1.)
    assert omitted['effects']['AB_interaction']['normalized_absolute_error']==3
    assert omitted['effects']['B_at_A_low']['target']==-1
    assert omitted['effects']['B_at_A_high']['target']==2


def test_invalid_prediction_preserves_failure_and_counts():
    r=derivative_errors([float('nan')],[1.],['active'],1.)
    assert r['failed_prediction'] and r['groups']['active']['count']==1
    assert r['groups']['active']['normalized_rmse'] is None
    assert effect_errors(None,[1,2,3,4],1)['failed_prediction']
    with pytest.raises(ValueError):derivative_errors([1.],[1.],['active'],0)
