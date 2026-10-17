import pytest
from env.electrical_impedance.protocol import example
from env.electrical_impedance.matrix_task import transfer_kind,prediction_metrics,APPLICABILITY


def test_public_scaling_not_discovery():
    s=example()
    with pytest.raises(ValueError):transfer_kind(s,dict(s,amplitude_v=.5))
    assert transfer_kind(s,dict(s,load_ohm=1000))=='apparatus_transfer'
    assert transfer_kind(s,dict(s,frequencies_hz=[7.,45.]))=='frequency_transfer'
    assert transfer_kind(s,dict(s,frequencies_hz=[7.,45.],load_ohm=1000))=='joint_transfer'
    assert APPLICABILITY['structure/counterfactual'] is None


def test_failure_in_denominator_and_no_semantic_score():
    s=example();q=dict(s,frequencies_hz=[7.,45.])
    p=dict(source=s,query=q,target=[[.1,.2],[.3,.4]],prediction=[[.1,.2],[.3,.4]])
    r=prediction_metrics([p,dict(p,prediction=[[float('nan')]])])
    assert r['groups']['frequency_transfer']==dict(total=2,valid=1,score_including_failures=50.)
    assert r['scientific_matrix_scores'] is None
    with pytest.raises(ValueError):prediction_metrics([dict(p,target=[])])
