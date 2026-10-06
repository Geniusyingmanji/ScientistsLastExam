from copy import deepcopy
import pytest
from env.isotope_pairing.world import World
from env.isotope_pairing.eligibility import validate_spec,prediction_mask,contrast_eligibility

def test_assigned_only_query_has_no_score_cells():
    s=World.example();s['times']=[0.]
    assert prediction_mask(s)==[[False]*3]
    assert not contrast_eligibility(s,s,0,'double_label')['eligible']

def test_future_and_same_time_changes_are_not_effects():
    a=World.example();b=deepcopy(a)
    b['source'].append({'at':3.,'fractions':[1.,0,0,0]})
    assert not contrast_eligibility(a,b,2,'double_label')['eligible']
    assert contrast_eligibility(a,b,3,'double_label')['eligible']
    assert not contrast_eligibility(a,a,3,'double_label')['eligible']

def test_public_validator_agrees_with_world():
    w=World(100)
    for s in w.panel(12,'interventions',3):assert validate_spec(s)==w.validate(s)
    s=w.example();s['source'][0]['fractions']=[True,0,0,0]
    with pytest.raises(ValueError):validate_spec(s)
    with pytest.raises(ValueError):contrast_eligibility(w.example(),w.example(),True,'double_label')
    with pytest.raises(ValueError):contrast_eligibility(w.example(),w.example(),1,'sum_of_fractions')
